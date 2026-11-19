"""Closed, immutable World/Event batch snapshots and normalized EI audit data.

This module projects existing application and Core records.  It does not
construct a CoreCaseContext on reads or add an EI acceptance authority.
"""

from __future__ import annotations

import datetime
import hashlib
import json
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
    EventSourceReference,
    EventStatement,
    EventStatementKind,
    EventUnderlyingHypothesis,
    HypothesisReassessment,
    MethodologizedDateRange,
    ReassessmentBasisKind,
    assess_event_intelligence_submission,
)
from .host_core_snapshot import decode_core_result, encode_core_result
from .host_profile import (
    _profile_for_snapshot,
    _request_has_conflicting_registered_profile,
)
from .host_source_coverage import HostSourceCoverageAudit
from .market_data import UnderlyingKey, UnderlyingSecurityType
from .option_chain_discovery import (
    ExplorationLead,
    ExploratoryOptionChainRequest,
    HypothesisMaturityAlignment,
    OptionMaturityAuthority,
    validate_exploration_lead,
    validate_exploratory_option_chain_request,
)


SCHEMA_VERSION = "host-batch-snapshot-v0.1"
SOURCE_COVERAGE_SCHEMA_VERSION = "host-batch-snapshot-v0.2"
EXPLORATION_SCHEMA_VERSION = "host-batch-snapshot-v0.3"
OUTCOME_SCHEMA_VERSION = "host-batch-outcome-v0.1"
AUDIT_SCHEMA_VERSION = "host-ei-batch-audit-v0.1"
EXPLORATION_AUDIT_SCHEMA_VERSION = "host-exploration-batch-audit-v0.1"
EXPLORATION_POLICY_SCHEMA_VERSION = "structure-first-exploration-v0.1"
EXPLORATION_AUTHORITY = "exploratory_structure_research"
EXPLORATION_MINIMUM_DTE_DAYS = 30
EXPLORATION_MAXIMUM_DTE_DAYS = 150
PARTIAL_SOURCE_COVERAGE_DISCLOSURE = (
    "来源提取覆盖不完整；仅核验已取得正文，失败来源未被视为事实或反证不存在。"
)
_CASE_KEY_RE = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_LIMIT_REASON_RE = re.compile(
    r"(submissions|source_items|hypotheses|hypotheses_and_exploration_leads|browser_rows|cases):([1-9][0-9]*)>(0|[1-9][0-9]*)\Z",
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
_ARCHIVE_FIELDS_V0_2 = _ARCHIVE_FIELDS | frozenset(("source_coverage_by_unit",))
_ARCHIVE_FIELDS_V0_3 = _ARCHIVE_FIELDS | frozenset(("exploration_audit",))
_ARCHIVE_FIELDS_V0_3_WITH_SOURCE_COVERAGE = _ARCHIVE_FIELDS_V0_3 | frozenset(("source_coverage_by_unit",))
_SOURCE_COVERAGE_UNIT_FIELDS = frozenset(
    ("unit_id", "source_coverage", "submission_ids", "case_ids")
)
_SOURCE_COVERAGE_UNIT_FIELDS_V0_3 = _SOURCE_COVERAGE_UNIT_FIELDS | frozenset(
    ("exploration_lead_ids",)
)
_EXPLORATION_POLICY_FIELDS = frozenset((
    "schema_version", "authority", "minimum_dte_days", "maximum_dte_days", "enabled"
))
_EXPLORATION_AUDIT_FIELDS = frozenset(("schema_version", "status", "leads"))
_EXPLORATION_LEAD_FIELDS = frozenset((
    "lead_id", "event_description", "observed_at", "underlying_key", "sources",
    "statements", "event_statement_id", "exposure_statement_id",
    "underlying_reference", "validation_reference", "uncertainties",
))
_EXPLORATION_PUBLIC_LEAD_FIELDS = frozenset((
    "lead_id", "event_description", "underlying_key", "sources", "statements",
    "event_statement_id", "exposure_statement_id", "uncertainties",
))
_EXPLORATION_SOURCE_FIELDS = frozenset(("source_id", "locator", "title", "published_at"))
_EXPLORATION_STATEMENT_FIELDS = frozenset((
    "statement_id", "kind", "text", "source_ids", "dependency_statement_ids",
))
_EXPLORATION_REQUEST_FIELDS = frozenset((
    "request_type", "evaluation_date", "minimum_expiration_date",
    "maximum_expiration_date", "maturity_authority",
    "hypothesis_maturity_alignment",
))
_EXPLORATION_VALIDATION_FIELDS = frozenset((
    "schema_version", "run_id", "canonical_input_hash", "envelope_hash",
    "event_anchor", "exposure_statement_id", "claim_dependency_closure",
    "verified_claim_ids", "verified_entity_bindings", "coverage",
    "coverage_outcomes", "sources", "listing_reference_sha256", "entity_ref",
))
_LINEAGE_FIELDS_V0_3 = _LINEAGE_FIELDS | frozenset(("lead_id",))
_BATCH_CASE_FIELDS_V0_3 = _BATCH_CASE_FIELDS | frozenset(("exploration_request",))
_UNAVAILABLE_FIELDS_V0_3 = _UNAVAILABLE_FIELDS | frozenset(("exploration_request",))


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


def _source_coverage_unit_rows(value: Any, *, host_run_id: str) -> List[Dict[str, Any]]:
    """Revalidate and detach the closed per-unit coverage sidecar."""

    if type(value) not in (tuple, list):
        raise TypeError("source_coverage_by_unit must be a sequence")
    rows: List[Dict[str, Any]] = []
    seen_units = set()
    seen_submissions = set()
    seen_cases = set()
    for item in value:
        _keys(item, _SOURCE_COVERAGE_UNIT_FIELDS, "source coverage unit")
        unit_id = _text(item["unit_id"], "source coverage unit_id")
        if unit_id in seen_units:
            raise ValueError("source coverage unit IDs must be unique")
        seen_units.add(unit_id)
        audit_value = item["source_coverage"]
        audit = None
        if audit_value is not None:
            audit = HostSourceCoverageAudit.from_dict(audit_value)
            if audit.host_run_id != host_run_id or audit.unit_id != unit_id:
                raise ValueError("source coverage audit is bound to a different Host run or unit")
            audit_value = audit.to_dict()
        submission_ids = _strings(item["submission_ids"], "source coverage submission_ids")
        case_ids = _strings(item["case_ids"], "source coverage case_ids")
        if len(submission_ids) != len(set(submission_ids)):
            raise ValueError("source coverage submission IDs must be unique within a unit")
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("source coverage case IDs must be unique within a unit")
        if seen_submissions.intersection(submission_ids):
            raise ValueError("a submission cannot be linked to multiple coverage units")
        if seen_cases.intersection(case_ids):
            raise ValueError("a Core case cannot be linked to multiple coverage units")
        seen_submissions.update(submission_ids)
        seen_cases.update(case_ids)
        if audit is None or audit.status == "EMPTY":
            if submission_ids or case_ids:
                raise ValueError("unknown or EMPTY coverage cannot authorize submissions or Core cases")
        rows.append(
            {
                "unit_id": unit_id,
                "source_coverage": audit_value,
                "submission_ids": submission_ids,
                "case_ids": case_ids,
            }
        )
    return rows


def _world_exploration_coverage_rows(
    value: Any,
    *,
    host_run_id: str,
    leads: Tuple[ExplorationLead, ...],
    archived: bool,
) -> List[Dict[str, Any]]:
    """Retain every World coverage unit and close its exact lead-ID links."""

    if type(value) not in (tuple, list):
        raise TypeError("source_coverage_by_unit must be a sequence")
    base_rows = []
    for item in value:
        if archived:
            _keys(item, _SOURCE_COVERAGE_UNIT_FIELDS_V0_3, "source coverage unit v0.3")
            base_rows.append({key: item[key] for key in _SOURCE_COVERAGE_UNIT_FIELDS})
        else:
            _keys(item, _SOURCE_COVERAGE_UNIT_FIELDS, "source coverage unit")
            base_rows.append(dict(item))
    rows = _source_coverage_unit_rows(base_rows, host_run_id=host_run_id)
    by_coverage_run = {}
    for row in rows:
        audit_payload = row["source_coverage"]
        if audit_payload is None:
            continue
        audit = HostSourceCoverageAudit.from_dict(audit_payload)
        if audit.run_id in by_coverage_run:
            raise ValueError("one Grounder coverage run cannot bind multiple World units")
        by_coverage_run[audit.run_id] = row

    lead_ids_by_unit = {row["unit_id"]: [] for row in rows}
    seen_lead_ids = set()
    for lead in leads:
        lead = validate_exploration_lead(lead)
        if lead.lead_id in seen_lead_ids:
            raise ValueError("World exploration lead IDs must be unique")
        seen_lead_ids.add(lead.lead_id)
        proof = _exploration_validation_reference(lead)
        row = by_coverage_run.get(proof["run_id"])
        if row is None or row["source_coverage"] is None:
            raise ValueError("World exploration lead has no exact source-coverage run link")
        audit = HostSourceCoverageAudit.from_dict(row["source_coverage"])
        if audit.status == "EMPTY":
            raise ValueError("World exploration lead cannot bind an EMPTY coverage unit")
        entries = audit.to_dict()["entries"]
        failed_ids = {
            item["source_id"] for item in entries if item["status"] == "FAILED"
        }
        failed_locators = {
            item["locator"] for item in entries if item["status"] == "FAILED"
        }
        available = {
            item["source_id"]: item
            for item in entries if item["status"] == "BODY_AVAILABLE"
        }
        for source in lead.sources:
            if (
                source.source_id in failed_ids
                or source.locator in failed_locators
                or (
                    source.source_id in available
                    and source.locator != available[source.source_id]["locator"]
                )
            ):
                raise ValueError("World exploration source conflicts with extraction coverage")
        lead_ids_by_unit[row["unit_id"]].append(lead.lead_id)

    projected = []
    for row in rows:
        item = dict(row)
        item["exploration_lead_ids"] = lead_ids_by_unit[row["unit_id"]]
        projected.append(item)
    if archived and projected != value:
        raise ValueError("World v0.3 coverage rows are not the canonical exact lead-linked form")
    return projected


def _validate_source_coverage_links(
    rows: List[Dict[str, Any]],
    *,
    host_run_id: str,
    submissions: List[Dict[str, Any]],
    cases: List[Dict[str, Any]],
    unavailable: List[Dict[str, Any]],
    exploration_leads: Tuple[ExplorationLead, ...] = (),
) -> None:
    """Check sidecar IDs against actual EI and Core archive relationships."""

    audited_submission_ids = [item["submission_id"] for item in submissions]
    if len(audited_submission_ids) != len(set(audited_submission_ids)):
        raise ValueError("EI archive has duplicate submission IDs")
    actual_submissions = set(audited_submission_ids)
    submission_by_id = {
        item["submission_id"]: item for item in submissions
    }
    unit_by_submission: Dict[str, str] = {}
    row_by_unit = {item["unit_id"]: item for item in rows}
    unit_by_coverage_run: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        audit_value = row["source_coverage"]
        audit = (
            None
            if audit_value is None
            else HostSourceCoverageAudit.from_dict(audit_value)
        )
        if audit is not None and (
            audit.host_run_id != host_run_id or audit.unit_id != row["unit_id"]
        ):
            raise ValueError("source coverage audit is bound to a different Host run or unit")
        if audit is not None:
            if audit.run_id in unit_by_coverage_run:
                raise ValueError("one Grounder coverage run cannot bind multiple World units")
            unit_by_coverage_run[audit.run_id] = row
        for submission_id in row["submission_ids"]:
            if submission_id not in actual_submissions:
                raise ValueError("coverage submission ID does not resolve to the EI audit")
            if audit is None or audit.status == "EMPTY":
                raise ValueError("submission linkage requires non-EMPTY source coverage")
            if audit.run_id != submission_id:
                raise ValueError("coverage Grounder run ID differs from the linked EI submission")
            audit_entries = audit.to_dict()["entries"]
            available_by_id = {
                entry["source_id"]: entry
                for entry in audit_entries
                if entry["status"] == "BODY_AVAILABLE"
            }
            available_by_locator = {
                entry["locator"]: entry
                for entry in audit_entries
                if entry["status"] == "BODY_AVAILABLE"
            }
            failed_ids = {
                entry["source_id"]
                for entry in audit_entries
                if entry["status"] == "FAILED"
            }
            failed_locators = {
                entry["locator"]
                for entry in audit_entries
                if entry["status"] == "FAILED"
            }
            for source in submission_by_id[submission_id]["sources"]:
                if (
                    source["source_id"] in failed_ids
                    or source["locator"] in failed_locators
                ):
                    raise ValueError(
                        "EI source conflicts with a failed extraction outcome"
                    )
                by_id = available_by_id.get(source["source_id"])
                by_locator = available_by_locator.get(source["locator"])
                if (by_id is None) != (by_locator is None) or (
                    by_id is not None
                    and (
                        by_id["source_id"] != by_locator["source_id"]
                        or by_id["locator"] != source["locator"]
                    )
                ):
                    raise ValueError(
                        "EI source identity conflicts with an Extract success binding"
                    )
                # A source absent from the extraction partition may have entered
                # through the existing authenticated admission pipeline.  This
                # archive does not grant or independently re-prove that authority.
            unit_by_submission[submission_id] = row["unit_id"]

    lead_ids_by_unit: Dict[str, List[str]] = {
        unit_id: [] for unit_id in row_by_unit
    }
    unit_by_lead_id: Dict[str, str] = {}
    for lead in exploration_leads:
        validation = _exploration_validation_reference(lead)
        row = unit_by_coverage_run.get(validation["run_id"])
        if row is None or row["source_coverage"] is None:
            raise ValueError("exploration lead has no exact covered World unit link")
        audit = HostSourceCoverageAudit.from_dict(row["source_coverage"])
        if audit.status == "EMPTY":
            raise ValueError("exploration lead cannot bind an EMPTY coverage unit")
        entries = audit.to_dict()["entries"]
        failed_ids = {
            item["source_id"] for item in entries if item["status"] == "FAILED"
        }
        failed_locators = {
            item["locator"] for item in entries if item["status"] == "FAILED"
        }
        available = {
            item["source_id"]: item
            for item in entries if item["status"] == "BODY_AVAILABLE"
        }
        for source in lead.sources:
            if (
                source.source_id in failed_ids
                or source.locator in failed_locators
                or (
                    source.source_id in available
                    and source.locator != available[source.source_id]["locator"]
                )
            ):
                raise ValueError("exploration lead source conflicts with World coverage")
        lead_ids_by_unit[row["unit_id"]].append(lead.lead_id)
        unit_by_lead_id[lead.lead_id] = row["unit_id"]

    if exploration_leads:
        for row in rows:
            if row.get("exploration_lead_ids") != lead_ids_by_unit[row["unit_id"]]:
                raise ValueError("World coverage lead links differ from validated lead run IDs")
    if set(unit_by_submission) != actual_submissions:
        raise ValueError("every EI submission must map to exactly one covered World unit")

    expected_cases_by_unit: Dict[str, List[str]] = {
        unit_id: [] for unit_id in row_by_unit
    }
    for item in cases:
        lineage = item["lineage"]
        lead_id = lineage.get("lead_id")
        unit_id = (
            unit_by_lead_id.get(lead_id)
            if lead_id is not None
            else unit_by_submission.get(lineage["submission_id"])
        )
        if unit_id is None:
            raise ValueError("Core case lineage has no covered World unit")
        audit = HostSourceCoverageAudit.from_dict(row_by_unit[unit_id]["source_coverage"])
        if audit.status == "EMPTY":
            raise ValueError("Core case linkage requires non-EMPTY source coverage")
        expected_cases_by_unit[unit_id].append(item["case_id"])

    for item in unavailable:
        lineage = item["lineage"]
        lead_id = lineage.get("lead_id")
        if lead_id is not None:
            unit_id = unit_by_lead_id.get(lead_id)
            if unit_id is None:
                raise ValueError("exploratory unavailable lineage has no covered World unit")
            if item["case_id"] in row_by_unit:
                raise ValueError("exploratory unavailable case cannot alias a coverage unit")
            audit = HostSourceCoverageAudit.from_dict(
                row_by_unit[unit_id]["source_coverage"]
            )
            if audit.status == "EMPTY":
                raise ValueError("exploratory unavailable linkage requires non-EMPTY source coverage")
            continue
        submission_id = lineage["submission_id"]
        if submission_id is None:
            unit_row = row_by_unit.get(item["case_id"])
            if unit_row is not None and (
                unit_row["submission_ids"] or unit_row["case_ids"]
            ):
                raise ValueError(
                    "no-submission unavailable unit identity conflicts with linked records"
                )
            continue
        unit_id = unit_by_submission.get(submission_id)
        if unit_id is None:
            raise ValueError("unavailable EI lineage has no covered World unit")
        identity_row = row_by_unit.get(item["case_id"])
        if identity_row is not None and identity_row["unit_id"] != unit_id:
            raise ValueError("unavailable case identity conflicts with its submission unit")
        audit = HostSourceCoverageAudit.from_dict(row_by_unit[unit_id]["source_coverage"])
        if audit.status == "EMPTY":
            raise ValueError("unavailable EI linkage requires non-EMPTY source coverage")

    actual_case_ids = {item["case_id"] for item in cases}
    linked_case_ids = set()
    for row in rows:
        listed = row["case_ids"]
        expected = expected_cases_by_unit[row["unit_id"]]
        if set(listed) != set(expected) or len(listed) != len(expected):
            raise ValueError("coverage case IDs differ from actual CoreCaseRecord linkage")
        if any(case_id not in actual_case_ids for case_id in listed):
            raise ValueError("coverage case IDs must identify actual CoreCaseRecord rows")
        linked_case_ids.update(listed)
    if linked_case_ids != actual_case_ids:
        raise ValueError("every CoreCaseRecord must map to exactly one covered World unit")


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


def _exploration_policy(metadata: Any, *, mode: str) -> Dict[str, Any]:
    configuration = metadata.get("configuration_snapshot") if type(metadata) is dict else None
    policy = (
        configuration.get("exploration_policy")
        if type(configuration) is dict
        else None
    )
    _keys(policy, _EXPLORATION_POLICY_FIELDS, "exploration policy")
    if (
        mode not in ("event", "world")
        or type(policy["schema_version"]) is not str
        or policy["schema_version"] != EXPLORATION_POLICY_SCHEMA_VERSION
        or type(policy["authority"]) is not str
        or policy["authority"] != EXPLORATION_AUTHORITY
        or type(policy["minimum_dte_days"]) is not int
        or policy["minimum_dte_days"] != EXPLORATION_MINIMUM_DTE_DAYS
        or type(policy["maximum_dte_days"]) is not int
        or policy["maximum_dte_days"] != EXPLORATION_MAXIMUM_DTE_DAYS
        or type(policy["enabled"]) is not bool
        or policy["enabled"] is not True
    ):
        raise ValueError("exploration archive requires the approved immutable enabled policy")
    return dict(policy)


def _enum_text(value: Any, label: str) -> str:
    result = getattr(value, "value", None)
    if type(result) is not str:
        raise TypeError("{} must be a closed enum value".format(label))
    return result


def _exploration_validation_reference(value: Any) -> Dict[str, Any]:
    """Validate the closed, private receipt/listing lineage retained by a lead."""

    lead = validate_exploration_lead(value)
    raw = lead.validation_reference
    if len(raw.encode("utf-8", "strict")) > 100_000:
        raise ValueError("exploration validation reference exceeds its archive bound")
    try:
        payload = json.loads(raw)
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("exploration validation reference is not canonical JSON") from error
    _keys(payload, _EXPLORATION_VALIDATION_FIELDS, "exploration validation reference")
    if canonical != raw:
        raise ValueError("exploration validation reference is not canonical JSON")
    for name in ("canonical_input_hash", "envelope_hash", "listing_reference_sha256"):
        if type(payload[name]) is not str or re.fullmatch(r"[0-9a-f]{64}", payload[name], re.ASCII) is None:
            raise ValueError("exploration validation reference has an invalid digest")
    for name in ("run_id", "event_anchor", "exposure_statement_id", "entity_ref"):
        _text(payload[name], "exploration validation reference " + name)
    if (
        payload["schema_version"] != "host-exploration-lead-validation-v0.1"
        or payload["event_anchor"] != lead.event_statement_id
        or payload["exposure_statement_id"] != lead.exposure_statement_id
        or payload["listing_reference_sha256"]
        != hashlib.sha256(lead.underlying_reference.encode("utf-8", "strict")).hexdigest()
    ):
        raise ValueError("exploration validation reference does not bind the exact lead")
    closure = _strings(payload["claim_dependency_closure"], "exploration claim closure", nonempty=True)
    verified = _strings(payload["verified_claim_ids"], "exploration verified claim IDs", nonempty=True)
    statement_ids = [item.statement_id for item in lead.statements]
    if (
        not closure
        or len(closure) != len(set(closure))
        or closure != statement_ids
        or verified != sorted(closure)
        or payload["event_anchor"] not in closure
        or payload["exposure_statement_id"] not in closure
        or len(lead_id := "exploration-" + hashlib.sha256(
            json.dumps(
                [payload["run_id"], payload["event_anchor"],
                 payload["exposure_statement_id"], lead.underlying_key.symbol],
                ensure_ascii=False, separators=(",", ":"),
            ).encode("utf-8", "strict")
        ).hexdigest()) == 0
        or lead.lead_id != lead_id
    ):
        raise ValueError("exploration validation reference has a dangling lead or claim closure")
    event_statement = next(
        item for item in lead.statements
        if item.statement_id == lead.event_statement_id
    )
    if lead.event_description != event_statement.text:
        raise ValueError("exploration event description differs from its retained statement")

    sources = payload["sources"]
    if type(sources) is not list or not 1 <= len(sources) <= 32:
        raise ValueError("exploration source proof rows are outside the archive bound")
    source_by_id = {}
    for item in sources:
        _keys(
            item,
            frozenset(("source_id", "final_locator", "body_sha256", "retrieved_at", "admission")),
            "exploration source proof",
        )
        source_id = _text(item["source_id"], "exploration source proof source_id")
        locator = _text(item["final_locator"], "exploration source proof locator")
        digest = item["body_sha256"]
        if (
            source_id in source_by_id
            or type(digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", digest, re.ASCII) is None
        ):
            raise ValueError("exploration source proof identity or digest is invalid")
        _parse_datetime(item["retrieved_at"], "exploration source proof retrieved_at")
        if item["admission"] is not None and type(item["admission"]) is not dict:
            raise ValueError("exploration source admission proof must be an object or null")
        source_by_id[source_id] = (locator, digest)
    lead_sources = {item.source_id: item for item in lead.sources}
    if set(source_by_id) != set(lead_sources):
        raise ValueError("exploration proof source IDs differ from retained lead sources")
    for source_id, source in lead_sources.items():
        if source_by_id[source_id][0] != source.locator:
            raise ValueError("exploration proof locator differs from retained lead source")

    bindings = payload["verified_entity_bindings"]
    if type(bindings) is not list or not 1 <= len(bindings) <= 128:
        raise ValueError("exploration entity proof rows are outside the archive bound")
    binding_indexes = set()
    for item in bindings:
        _keys(
            item, frozenset(("index", "field_path", "source_id", "quote", "start", "end")),
            "exploration verified entity binding",
        )
        if (
            type(item["index"]) is not int or item["index"] < 0
            or item["index"] in binding_indexes
            or type(item["start"]) is not int or item["start"] < 0
            or type(item["end"]) is not int or item["end"] <= item["start"]
            or item["source_id"] not in source_by_id
        ):
            raise ValueError("exploration verified entity binding is invalid")
        _text(item["field_path"], "exploration entity binding field_path")
        _text(item["quote"], "exploration entity binding quote")
        binding_indexes.add(item["index"])
    if not any("/entity_refs/" in item["field_path"] for item in bindings):
        raise ValueError("exploration proof has no verified entity binding")

    if (
        type(payload["coverage"]) is not list or len(payload["coverage"]) > 128
        or type(payload["coverage_outcomes"]) is not list
        or len(payload["coverage_outcomes"]) > 128
    ):
        raise ValueError("exploration semantic coverage proof exceeds its archive bound")
    return payload


def _validated_exploration_listing_reference(lead: ExplorationLead) -> Dict[str, Any]:
    raw = lead.underlying_reference
    if len(raw.encode("utf-8", "strict")) > 100_000:
        raise ValueError("exploration listing reference exceeds its archive bound")
    try:
        payload = json.loads(raw)
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("exploration listing reference is not canonical JSON") from error
    _keys(
        payload,
        frozenset(("rule_version", "symbol", "security_type", "listing_mic", "currency", "currency_basis", "sources")),
        "exploration listing reference",
    )
    if (
        canonical != raw
        or payload["rule_version"] not in {
            "host-listing-source-composite-v0.1",
            "host-listing-source-composite-v0.2",
            "host-listing-source-composite-v0.3",
            "host-listing-source-composite-v0.4",
            "host-listing-source-composite-v0.5",
        }
        or payload["symbol"] != lead.underlying_key.symbol
        or payload["security_type"] != lead.underlying_key.security_type.name
        or payload["listing_mic"] != lead.underlying_key.listing_mic
        or payload["currency"] != lead.underlying_key.currency
        or payload["currency_basis"] != "yahoo_provider_reported_quote_denomination"
        or type(payload["sources"]) is not list
        or len(payload["sources"]) != 3
    ):
        raise ValueError("exploration listing reference does not bind its exact underlying")
    roles = set()
    source_ids = set()
    allowed_source_fields = frozenset((
        "role", "source_id", "locator", "origin", "body_sha256", "issuer",
        "share_class", "symbol", "registered_exchange", "security_class_authority",
        "currency", "currency_basis", "excerpts", "source_admission",
        "cik", "issuer_name", "exchange",
    ))
    for item in payload["sources"]:
        if type(item) is not dict or not set(item).issubset(allowed_source_fields):
            raise ValueError("exploration listing source has an unknown field")
        if not {"role", "source_id", "locator", "body_sha256"}.issubset(item):
            raise ValueError("exploration listing source is incomplete")
        role = _text(item["role"], "exploration listing source role")
        source_id = _text(item["source_id"], "exploration listing source_id")
        _text(item["locator"], "exploration listing locator")
        digest = item["body_sha256"]
        if (
            role in roles or source_id in source_ids
            or type(digest) is not str
            or re.fullmatch(r"[0-9a-f]{64}", digest, re.ASCII) is None
            or ("symbol" in item and item["symbol"] != lead.underlying_key.symbol)
            or ("currency" in item and item["currency"] != lead.underlying_key.currency)
        ):
            raise ValueError("exploration listing source identity is inconsistent")
        roles.add(role)
        source_ids.add(source_id)
        if "source_admission" in item and type(item["source_admission"]) is not dict:
            raise ValueError("listing admission provenance must be an object")
        if "excerpts" not in item or type(item["excerpts"]) is not list:
            raise ValueError("exploration listing source excerpts are malformed")
    allowed_roles = {
        frozenset(("sec_listing_class", "nasdaq_instrument_heading", "yahoo_quote_denomination")),
        frozenset(("sec_issuer_reference", "sec_cover_security_class", "yahoo_quote_denomination")),
    }
    if frozenset(roles) not in allowed_roles:
        raise ValueError("exploration listing source roles do not match an approved route")
    return payload


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


def _exploration_lead_projection(value: ExplorationLead) -> Dict[str, Any]:
    lead = validate_exploration_lead(value)
    _exploration_validation_reference(lead)
    _validated_exploration_listing_reference(lead)
    projected = {
        "lead_id": _text(lead.lead_id, "exploration lead_id"),
        "event_description": _text(lead.event_description, "exploration event_description"),
        "observed_at": _datetime(lead.observed_at, "exploration observed_at"),
        "underlying_key": {
            "symbol": _text(lead.underlying_key.symbol, "exploration underlying symbol"),
            "listing_mic": (
                None if lead.underlying_key.listing_mic is None
                else _text(lead.underlying_key.listing_mic, "exploration listing MIC")
            ),
            "security_type": _enum_text(
                lead.underlying_key.security_type, "exploration security_type"
            ),
            "currency": _text(lead.underlying_key.currency, "exploration currency"),
        },
        "sources": [
            {
                "source_id": _text(source.source_id, "exploration source_id"),
                "locator": _text(source.locator, "exploration source locator"),
                "title": None if source.title is None else _text(source.title, "exploration source title"),
                "published_at": _datetime(source.published_at, "exploration source published_at"),
            }
            for source in lead.sources
        ],
        "statements": [
            {
                "statement_id": _text(statement.statement_id, "exploration statement_id"),
                "kind": _enum_text(statement.kind, "exploration statement kind"),
                "text": _text(statement.text, "exploration statement text"),
                "source_ids": list(_strings(statement.source_ids, "exploration statement source_ids")),
                "dependency_statement_ids": list(
                    _strings(
                        statement.dependency_statement_ids,
                        "exploration statement dependencies",
                    )
                ),
            }
            for statement in lead.statements
        ],
        "event_statement_id": _text(lead.event_statement_id, "event_statement_id"),
        "exposure_statement_id": _text(lead.exposure_statement_id, "exposure_statement_id"),
        "underlying_reference": _text(lead.underlying_reference, "underlying_reference"),
        "validation_reference": _text(lead.validation_reference, "validation_reference"),
        "uncertainties": list(_strings(lead.uncertainties, "exploration uncertainties")),
    }
    return projected


def _exploration_lead_public_projection(value: Any) -> Dict[str, Any]:
    """Project admitted lead material without private listing proof references."""

    if type(value) is ExplorationLead:
        lead = validate_exploration_lead(value)
        key = lead.underlying_key
        sources = [
            {
                "source_id": source.source_id,
                "locator": source.locator,
                "title": source.title,
                "published_at": _datetime(source.published_at, "exploration source published_at"),
            }
            for source in lead.sources
        ]
        statements = [
            {
                "statement_id": statement.statement_id,
                "kind": _enum_text(statement.kind, "exploration statement kind"),
                "text": statement.text,
                "source_ids": list(statement.source_ids),
                "dependency_statement_ids": list(statement.dependency_statement_ids),
            }
            for statement in lead.statements
        ]
        return {
            "lead_id": lead.lead_id,
            "event_description": lead.event_description,
            "underlying_key": {
                "symbol": key.symbol,
                "listing_mic": key.listing_mic,
                "security_type": _enum_text(key.security_type, "exploration security_type"),
                "currency": key.currency,
            },
            "sources": sources,
            "statements": statements,
            "event_statement_id": lead.event_statement_id,
            "exposure_statement_id": lead.exposure_statement_id,
            "uncertainties": list(lead.uncertainties),
        }
    _keys(value, _EXPLORATION_LEAD_FIELDS, "exploration lead")
    # Public material is a deliberate allowlist; proof references remain in
    # the private batch archive and are never copied into the research view.
    return {
        key: value[key]
        for key in (
            "lead_id", "event_description", "underlying_key", "sources", "statements",
            "event_statement_id", "exposure_statement_id", "uncertainties",
        )
    }


def _validate_exploration_public_lead(value: Any) -> Dict[str, Any]:
    _keys(value, _EXPLORATION_PUBLIC_LEAD_FIELDS, "public exploration lead")
    key_value = value["underlying_key"]
    _keys(
        key_value,
        frozenset(("symbol", "listing_mic", "security_type", "currency")),
        "public exploration underlying key",
    )
    try:
        key = UnderlyingKey(
            _text(key_value["symbol"], "public exploration symbol"),
            _optional_text(key_value["listing_mic"], "public exploration listing MIC"),
            UnderlyingSecurityType(_text(key_value["security_type"], "public exploration security_type")),
            _text(key_value["currency"], "public exploration currency"),
        )
    except ValueError as error:
        raise ValueError("public exploration underlying key is invalid") from error
    if type(value["sources"]) is not list or type(value["statements"]) is not list:
        raise TypeError("public exploration sources and statements must be arrays")
    sources = []
    for source in value["sources"]:
        _keys(source, _EXPLORATION_SOURCE_FIELDS, "public exploration source")
        sources.append(EventSourceReference(
            _text(source["source_id"], "public exploration source_id"),
            _text(source["locator"], "public exploration source locator"),
            _optional_text(source["title"], "public exploration source title"),
            _parse_datetime(source["published_at"], "public exploration source published_at", optional=True),
        ))
    statements = []
    for statement in value["statements"]:
        _keys(statement, _EXPLORATION_STATEMENT_FIELDS, "public exploration statement")
        try:
            kind = EventStatementKind(_text(statement["kind"], "public exploration statement kind"))
        except ValueError as error:
            raise ValueError("public exploration statement kind is invalid") from error
        statements.append(EventStatement(
            _text(statement["statement_id"], "public exploration statement_id"),
            kind,
            _text(statement["text"], "public exploration statement text"),
            tuple(_strings(statement["source_ids"], "public exploration statement source_ids")),
            tuple(_strings(
                statement["dependency_statement_ids"],
                "public exploration statement dependencies",
            )),
        ))
    lead = ExplorationLead(
        _text(value["lead_id"], "public exploration lead_id"),
        _text(value["event_description"], "public exploration event_description"),
        datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc),
        key,
        tuple(sources),
        tuple(statements),
        _text(value["event_statement_id"], "public exploration event statement_id"),
        _text(value["exposure_statement_id"], "public exploration exposure statement_id"),
        "public-proof-reference",
        "public-validation-reference",
        tuple(_strings(value["uncertainties"], "public exploration uncertainties")),
    )
    validate_exploration_lead(lead)
    if _exploration_lead_public_projection(lead) != value:
        raise ValueError("public exploration lead is not canonical structured material")
    return dict(value)


def _decode_exploration_lead(value: Any) -> ExplorationLead:
    _keys(value, _EXPLORATION_LEAD_FIELDS, "exploration lead")
    key_value = value["underlying_key"]
    _keys(
        key_value,
        frozenset(("symbol", "listing_mic", "security_type", "currency")),
        "exploration underlying key",
    )
    try:
        security_type = UnderlyingSecurityType(
            _text(key_value["security_type"], "exploration security_type")
        )
    except ValueError as error:
        raise ValueError("unknown exploration security type") from error
    underlying_key = UnderlyingKey(
        _text(key_value["symbol"], "exploration underlying symbol"),
        _optional_text(key_value["listing_mic"], "exploration listing MIC"),
        security_type,
        _text(key_value["currency"], "exploration currency"),
    )
    if type(value["sources"]) is not list or type(value["statements"]) is not list:
        raise TypeError("exploration source and statement records must be arrays")
    sources = []
    for source in value["sources"]:
        _keys(source, _EXPLORATION_SOURCE_FIELDS, "exploration source")
        sources.append(
            EventSourceReference(
                _text(source["source_id"], "exploration source_id"),
                _text(source["locator"], "exploration source locator"),
                _optional_text(source["title"], "exploration source title"),
                _parse_datetime(source["published_at"], "exploration source published_at", optional=True),
            )
        )
    statements = []
    for statement in value["statements"]:
        _keys(statement, _EXPLORATION_STATEMENT_FIELDS, "exploration statement")
        try:
            kind = EventStatementKind(_text(statement["kind"], "exploration statement kind"))
        except ValueError as error:
            raise ValueError("unknown exploration statement kind") from error
        statements.append(
            EventStatement(
                _text(statement["statement_id"], "exploration statement_id"),
                kind,
                _text(statement["text"], "exploration statement text"),
                tuple(_strings(statement["source_ids"], "exploration statement source_ids")),
                tuple(_strings(
                    statement["dependency_statement_ids"],
                    "exploration statement dependencies",
                )),
            )
        )
    lead = ExplorationLead(
        _text(value["lead_id"], "exploration lead_id"),
        _text(value["event_description"], "exploration event_description"),
        _parse_datetime(value["observed_at"], "exploration observed_at"),
        underlying_key,
        tuple(sources),
        tuple(statements),
        _text(value["event_statement_id"], "event_statement_id"),
        _text(value["exposure_statement_id"], "exposure_statement_id"),
        _text(value["underlying_reference"], "underlying_reference"),
        _text(value["validation_reference"], "validation_reference"),
        tuple(_strings(value["uncertainties"], "exploration uncertainties")),
    )
    validate_exploration_lead(lead)
    if _exploration_lead_projection(lead) != value:
        raise ValueError("exploration lead is not the canonical normalized projection")
    return lead


def _exploration_audit_projection(
    value: Any,
    *,
    bounds: Dict[str, Any],
) -> Dict[str, Any]:
    if type(value) is not tuple or not value:
        raise TypeError("exploration leads must be a non-empty detached tuple")
    lead_limit = bounds["max_submissions"]
    nested_limit = (
        bounds["max_submissions"] + bounds["max_hypotheses"]
        + bounds["max_browser_rows"] + bounds["max_cases"]
    )
    if len(value) > lead_limit:
        raise ValueError("exploration lead count exceeds immutable Core bounds")
    leads = []
    seen = set()
    nested_count = 0
    for lead in value:
        projected = _exploration_lead_projection(lead)
        if projected["lead_id"] in seen:
            raise ValueError("exploration lead IDs must be unique")
        seen.add(projected["lead_id"])
        nested_count += (
            len(projected["sources"]) + len(projected["statements"])
            + len(projected["uncertainties"])
        )
        if nested_count > nested_limit:
            raise ValueError("exploration evidence count exceeds bound-derived archive limit")
        leads.append(projected)
    return {
        "schema_version": EXPLORATION_AUDIT_SCHEMA_VERSION,
        "status": "ADMITTED",
        "leads": leads,
    }


def _validate_exploration_audit(value: Any, *, bounds: Dict[str, Any]) -> Dict[str, Any]:
    _keys(value, _EXPLORATION_AUDIT_FIELDS, "exploration audit")
    if (
        value["schema_version"] != EXPLORATION_AUDIT_SCHEMA_VERSION
        or value["status"] != "ADMITTED"
        or type(value["leads"]) is not list
    ):
        raise ValueError("exploration audit version, status, or lead array is invalid")
    reconstructed = []
    for item in value["leads"]:
        reconstructed.append(_decode_exploration_lead(item))
    canonical = _exploration_audit_projection(tuple(reconstructed), bounds=bounds)
    if canonical != value:
        raise ValueError("exploration audit is not the canonical structured projection")
    return canonical


def _exploration_request_projection(value: Any) -> Dict[str, Any]:
    request = validate_exploratory_option_chain_request(value)
    return {
        "request_type": "ExploratoryOptionChainRequest",
        "evaluation_date": _date(request.evaluation_date, "exploration evaluation_date"),
        "minimum_expiration_date": _date(
            request.minimum_expiration_date, "exploration minimum expiration"
        ),
        "maximum_expiration_date": _date(
            request.maximum_expiration_date, "exploration maximum expiration"
        ),
        "maturity_authority": _enum_text(
            request.maturity_authority, "exploration maturity authority"
        ),
        "hypothesis_maturity_alignment": _enum_text(
            request.hypothesis_maturity_alignment,
            "exploration hypothesis maturity alignment",
        ),
    }


def _validate_exploration_request_projection(value: Any, lead: ExplorationLead) -> Dict[str, Any]:
    _keys(value, _EXPLORATION_REQUEST_FIELDS, "exploration request")
    if value["request_type"] != "ExploratoryOptionChainRequest":
        raise ValueError("exploration request discriminator is invalid")
    request = ExploratoryOptionChainRequest(
        lead, _parse_date(value["evaluation_date"], "exploration evaluation_date")
    )
    expected = _exploration_request_projection(request)
    if expected != value:
        raise ValueError("exploration request does not derive from its retained lead and policy")
    return expected


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


def _lineage(
    context: Any,
    submissions: Optional[SourceSubmissionBatch],
    *,
    include_exploration: bool = False,
) -> Dict[str, Optional[str]]:
    lineage: Dict[str, Optional[str]] = {
        "submission_id": None,
        "hypothesis_id": None,
    }
    if include_exploration:
        lineage["lead_id"] = None
    if context is None:
        return lineage
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
    lineage.update({"submission_id": submission_id, "hypothesis_id": hypothesis_id})
    lead = getattr(context, "exploration_lead", None)
    request = getattr(context, "discovery_request", None)
    if lead is not None:
        if not include_exploration:
            raise ValueError("exploration lineage requires the v0.3 batch archive")
        lead = validate_exploration_lead(lead)
        if (
            submissions is None
            or not any(lead is item for item in submissions.exploration_leads)
            or type(request) is not ExploratoryOptionChainRequest
            or validate_exploratory_option_chain_request(request) != request
            or request.lead is not lead
            or assessment is not None
            or hypothesis is not None
            or context.automated_handoff is not None
        ):
            raise ValueError("exploration lineage is not bound to its exact source-batch lead and request")
        lineage["lead_id"] = lead.lead_id
    elif type(request) is ExploratoryOptionChainRequest:
        raise ValueError("exploratory request has no exact retained lead")
    return lineage


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


def _profile_check(result: CoreResearchResult, profile_snapshot: Dict[str, Any]) -> None:
    request = result.request
    profile = _profile_for_snapshot(profile_snapshot)
    risk = request.risk_policy
    approved = profile.to_core_risk_policy(request.structure)
    if risk is None or type(risk) is not type(approved) or risk != approved:
        raise ValueError("Core risk inputs differ from the approved Standard Research Profile")
    if profile.version == "v0.1":
        if request.cost_ledger is not None or request.sensitivity is not None:
            raise ValueError("v0.1 batch Core request must retain absent cost and sensitivity inputs")
        if _request_has_conflicting_registered_profile(request, profile.version):
            raise ValueError("v0.1 batch Core request contains successor-profile provenance")
    else:
        expected = profile.request_factory(
            case_id=request.case_id, structure=request.structure, context=None
        )
        if request != expected:
            raise ValueError("batch Core request differs from the registered v0.2 profile factory")


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
    has_valid_exploration: bool = False,
    limit_exceeded: bool,
) -> Dict[str, Any]:
    if not (has_valid_submission or has_valid_exploration) or limit_exceeded:
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


def _effective_batch_source_counts(
    batch: Optional[SourceSubmissionBatch],
    *,
    raw_input: Any,
    submissions: Tuple[EventIntelligenceSubmission, ...],
    leads: Tuple[ExplorationLead, ...],
    assessed_submissions: List[Tuple[EventIntelligenceAcceptanceResult, EventIntelligenceSubmission]],
) -> Any:
    """Use Core's shared accepted-priority helper for archive bound replay."""

    from .core_application import effective_source_batch_counts

    effective_batch = batch or SourceSubmissionBatch(raw_input, submissions, leads)
    accepted_hypotheses = tuple(
        (assessment, submission, hypothesis)
        for assessment, submission in assessed_submissions
        if assessment.status is EventIntelligenceAcceptanceStatus.ACCEPTED
        for hypothesis in submission.hypotheses
    )
    return effective_source_batch_counts(effective_batch, accepted_hypotheses)


def _validate_limit_diagnostics(
    reasons: List[str],
    *,
    submission_count: int,
    hypothesis_count: int,
    exploration_lead_count: int = 0,
    bounds: Dict[str, Any],
    case_count: int,
    unavailable_count: int,
) -> bool:
    """Validate Core's exact over-bound diagnostic and require no prefix."""

    has_limit = "LIMIT_EXCEEDED" in reasons
    source_item_count = submission_count + exploration_lead_count
    total_hypothesis_count = hypothesis_count + exploration_lead_count
    raw_submissions_over = submission_count > bounds["max_submissions"]
    raw_hypotheses_over = hypothesis_count > bounds["max_hypotheses"]
    source_items_over = source_item_count > bounds["max_submissions"]
    hypotheses_and_leads_over = total_hypothesis_count > bounds["max_hypotheses"]
    if not has_limit:
        if source_items_over or hypotheses_and_leads_over:
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
        "source_items": "max_submissions",
        "hypotheses": "max_hypotheses",
        "hypotheses_and_exploration_leads": "max_hypotheses",
        "browser_rows": "max_browser_rows",
        "cases": "max_cases",
    }[name]
    if recorded_limit != bounds[bound_name] or observed <= recorded_limit:
        raise ValueError("LIMIT_EXCEEDED diagnostic does not exceed the immutable run bound")
    if raw_submissions_over:
        if name != "submissions" or observed != submission_count:
            raise ValueError("raw submission overflow differs from Core's first exceeded bound")
    elif raw_hypotheses_over:
        if name != "hypotheses" or observed != hypothesis_count:
            raise ValueError("raw hypothesis overflow differs from Core's first exceeded bound")
    elif source_items_over:
        if name != "source_items" or observed != source_item_count:
            raise ValueError("effective source-item overflow differs from Core's first exceeded bound")
    elif hypotheses_and_leads_over:
        if name != "hypotheses_and_exploration_leads" or observed != total_hypothesis_count:
            raise ValueError("effective hypothesis overflow differs from Core's first exceeded bound")
    elif name in (
        "submissions", "source_items", "hypotheses",
        "hypotheses_and_exploration_leads",
    ):
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
    source_coverage_by_unit: Any = None,
) -> Dict[str, Any]:
    """Build one complete archive or reject it; never emit a partial prefix."""

    if type(result) is not CoreRunResult:
        raise TypeError("batch save requires exact CoreRunResult")
    result.__post_init__()
    case_set = result.case_set
    case_set.__post_init__()
    if type(mode) is not str or mode not in ("world", "event"):
        raise ValueError("batch archive requires a World or Event run")
    if source_coverage_by_unit is not None and mode != "world":
        raise ValueError("source coverage sidecars are World-only")
    configuration = metadata.get("configuration_snapshot")
    query_policy = (
        configuration.get("world_source_query_policy")
        if type(configuration) is dict
        else None
    )
    partial_policy = (
        type(query_policy) is dict
        and query_policy.get("schema_version") == "world-source-query-v0.5"
    )
    if partial_policy != (source_coverage_by_unit is not None):
        raise ValueError("World partial-coverage policy and archive sidecar must be paired")
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
    exploration_leads = () if batch is None else batch.exploration_leads
    exploration_audit = None
    if exploration_leads:
        _exploration_policy(metadata, mode=mode)
        exploration_audit = _exploration_audit_projection(
            exploration_leads, bounds=_bounds(bounds)
        )
        for lead in exploration_leads:
            for source in lead.sources:
                validate_locator(source.locator)
    hypothesis_count = sum(len(submission.hypotheses) for submission in submissions)
    preassessed_submissions = [
        (assess_event_intelligence_submission(submission), submission)
        for submission in submissions
    ]
    effective_counts = _effective_batch_source_counts(
        batch,
        raw_input=raw_input,
        submissions=submissions,
        leads=exploration_leads,
        assessed_submissions=preassessed_submissions,
    )
    limit_exceeded = _validate_limit_diagnostics(
        list(case_set.reasons),
        submission_count=len(submissions),
        hypothesis_count=hypothesis_count,
        exploration_lead_count=len(effective_counts.effective_exploration_leads),
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
    preassessed_by_identity = {
        id(submission): assessment
        for assessment, submission in preassessed_submissions
    }
    for submission in submissions:
        # Reuse the existing deterministic EI assessor only where a submission
        # has no case context to retain its assessment (for example, an empty
        # Browser result). This adds no acceptance rule or authority.
        assessment = by_identity.get(id(submission))
        if assessment is None:
            assessment = preassessed_by_identity[id(submission)]
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
        _profile_check(record.kernel_result, profile_snapshot)
        snapshot = encode_core_result(record.kernel_result)
        validate_source_uris(snapshot)
        digest = hashlib.sha256(canonical_json(snapshot, "Core snapshot").encode("utf-8")).hexdigest()
        application_reasons = _reason_tuple(record.reasons, "case reasons")
        reasons = list(dict.fromkeys(application_reasons + tuple(item.value for item in record.kernel_result.reasons)))
        lineage = _lineage(
            record.context, batch, include_exploration=exploration_audit is not None
        )
        request_projection = None
        if lineage.get("lead_id") is None:
            if lineage["submission_id"] is None or lineage["hypothesis_id"] is None:
                raise ValueError("evaluated legacy case must retain its submitted hypothesis lineage")
            if type(record.discovery_request) is ExploratoryOptionChainRequest:
                raise ValueError("exploratory request is not bound to the archived lead")
        else:
            if lineage["submission_id"] is not None or lineage["hypothesis_id"] is not None:
                raise ValueError("exploratory case cannot claim EI submission or hypothesis lineage")
            request_projection = _exploration_request_projection(record.discovery_request)
        case_entry = {
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
        if exploration_audit is not None:
            case_entry["exploration_request"] = request_projection
        core_cases.append(case_entry)

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
        lineage = _lineage(
            record.context, batch, include_exploration=exploration_audit is not None
        )
        request_projection = None
        if lineage.get("lead_id") is not None:
            if lineage["submission_id"] is not None or lineage["hypothesis_id"] is not None:
                raise ValueError("exploratory unavailable branch cannot claim EI lineage")
            request = None if record.context is None else record.context.discovery_request
            if type(request) is not ExploratoryOptionChainRequest:
                raise ValueError("exploratory unavailable branch must retain its exact request")
            request_projection = _exploration_request_projection(request)
        elif record.context is not None and type(
            record.context.discovery_request
        ) is ExploratoryOptionChainRequest:
            raise ValueError("unavailable exploratory request has no archived lead binding")
        unavailable_entry = {
                "case_id": case_id,
                "case_key": key,
                "classification": "UNAVAILABLE",
                "reasons": list(_reason_tuple(record.reasons, "unavailable reasons")),
                "lineage": lineage,
            }
        if exploration_audit is not None:
            unavailable_entry["exploration_request"] = request_projection
        unavailable.append(unavailable_entry)

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
        has_valid_exploration=exploration_audit is not None,
        limit_exceeded=limit_exceeded,
    )
    summary = dict(compact_fields)
    summary["host_status"] = outcome["status"]
    summary["unavailable_cases"] = [
        {key: item[key] for key in ("case_id", "case_key", "reasons")}
        for item in unavailable
    ]
    archive = {
        "schema_version": (
            EXPLORATION_SCHEMA_VERSION
            if exploration_audit is not None
            else SOURCE_COVERAGE_SCHEMA_VERSION
            if source_coverage_by_unit is not None
            else SCHEMA_VERSION
        ),
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
    if exploration_audit is not None:
        archive["exploration_audit"] = exploration_audit
    if source_coverage_by_unit is not None:
        coverage_rows = (
            _world_exploration_coverage_rows(
                source_coverage_by_unit,
                host_run_id=run_id,
                leads=exploration_leads,
                archived=False,
            )
            if exploration_audit is not None
            else _source_coverage_unit_rows(
                source_coverage_by_unit, host_run_id=run_id
            )
        )
        _validate_source_coverage_links(
            coverage_rows,
            host_run_id=run_id,
            submissions=audit_submissions,
            cases=core_cases,
            unavailable=unavailable,
            exploration_leads=exploration_leads,
        )
        archive["source_coverage_by_unit"] = coverage_rows
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

    if type(archive) is not dict:
        raise TypeError("Host batch archive must be an object")
    schema_version = archive.get("schema_version")
    if schema_version == SCHEMA_VERSION:
        archive_fields = _ARCHIVE_FIELDS
    elif schema_version == SOURCE_COVERAGE_SCHEMA_VERSION:
        if mode != "world":
            raise ValueError("source coverage batch archives are World-only")
        archive_fields = _ARCHIVE_FIELDS_V0_2
    elif schema_version == EXPLORATION_SCHEMA_VERSION:
        has_coverage_sidecar = "source_coverage_by_unit" in archive
        if has_coverage_sidecar and mode != "world":
            raise ValueError("source coverage batch archives are World-only")
        archive_fields = (
            _ARCHIVE_FIELDS_V0_3_WITH_SOURCE_COVERAGE
            if has_coverage_sidecar
            else _ARCHIVE_FIELDS_V0_3
        )
    else:
        raise ValueError("unsupported Host batch archive schema")
    _keys(archive, archive_fields, "Host batch archive")
    if (
        archive["schema_version"] != schema_version
        or archive["run_id"] != run_id
        or archive["mode"] != mode
        or mode not in ("world", "event")
        or archive["input_sha256"] != input_sha256
        or archive["profile_snapshot"] != profile_snapshot
    ):
        raise ValueError("batch archive does not match its immutable run snapshot")
    configuration = metadata.get("configuration_snapshot")
    query_policy = (
        configuration.get("world_source_query_policy")
        if type(configuration) is dict
        else None
    )
    partial_policy = (
        type(query_policy) is dict
        and query_policy.get("schema_version") == "world-source-query-v0.5"
    )
    if schema_version == SCHEMA_VERSION and partial_policy:
        raise ValueError("World partial-coverage policy requires its successor archive schema")
    if schema_version == SOURCE_COVERAGE_SCHEMA_VERSION and not partial_policy:
        raise ValueError("World source-coverage archive requires its immutable v0.5 policy")
    if schema_version == EXPLORATION_SCHEMA_VERSION:
        _exploration_policy(metadata, mode=mode)
        if partial_policy != ("source_coverage_by_unit" in archive):
            raise ValueError("World partial-coverage policy and v0.3 sidecar must be paired")
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
    if schema_version == EXPLORATION_SCHEMA_VERSION:
        exploration_audit = _validate_exploration_audit(
            archive["exploration_audit"], bounds=bounds
        )
        for lead_item in exploration_audit["leads"]:
            for source in lead_item["sources"]:
                validate_locator(source["locator"])
        exploration_leads = tuple(
            _decode_exploration_lead(item)
            for item in exploration_audit["leads"]
        )
    else:
        exploration_audit = None
        exploration_leads = ()
    exploration_by_id = {
        lead.lead_id: lead for lead in exploration_leads
    }
    decoded_submission_values = tuple(
        submission for submission, _assessment in decoded_submissions
    )
    assessed_submission_values = [
        (assessment, submission)
        for submission, assessment in decoded_submissions
    ]
    effective_counts = _effective_batch_source_counts(
        SourceSubmissionBatch(run_input, decoded_submission_values, exploration_leads),
        raw_input=run_input,
        submissions=decoded_submission_values,
        leads=exploration_leads,
        assessed_submissions=assessed_submission_values,
    )

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
        _keys(
            item,
            _BATCH_CASE_FIELDS_V0_3
            if schema_version == EXPLORATION_SCHEMA_VERSION
            else _BATCH_CASE_FIELDS,
            "batch Core case",
        )
        case_id = _text(item["case_id"], "case_id")
        key = validate_case_key(item["case_key"])
        if key != case_key(case_id) or key in key_map:
            raise ValueError("batch navigation key mismatch or collision")
        key_map[key] = case_id
        if type(item["classification"]) is not str:
            raise TypeError("case classification must be text")
        _strings(item["reasons"], "case reasons", nonempty=False)
        _strings(item["application_reasons"], "application reasons", nonempty=False)
        _keys(
            item["lineage"],
            _LINEAGE_FIELDS_V0_3
            if schema_version == EXPLORATION_SCHEMA_VERSION
            else _LINEAGE_FIELDS,
            "case lineage",
        )
        submission_id = _optional_text(item["lineage"]["submission_id"], "lineage.submission_id")
        hypothesis_id = _optional_text(item["lineage"]["hypothesis_id"], "lineage.hypothesis_id")
        lead_id = (
            _optional_text(item["lineage"]["lead_id"], "lineage.lead_id")
            if schema_version == EXPLORATION_SCHEMA_VERSION
            else None
        )
        if lead_id is None:
            if submission_id is None or hypothesis_id is None:
                raise ValueError("evaluated legacy case must retain actual submission and hypothesis IDs")
            submission_entry = submission_map.get(submission_id)
            if submission_entry is None:
                raise ValueError("evaluated case lineage does not resolve to audited EI IDs")
            submission, assessment = submission_entry
            if (
                assessment.status is not EventIntelligenceAcceptanceStatus.ACCEPTED
                or hypothesis_id not in {h.hypothesis_id for h in submission.hypotheses}
            ):
                raise ValueError("case lineage does not resolve to audited EI IDs")
            if schema_version == EXPLORATION_SCHEMA_VERSION and item["exploration_request"] is not None:
                raise ValueError("EI case cannot retain an exploratory request")
        else:
            if (
                schema_version != EXPLORATION_SCHEMA_VERSION
                or submission_id is not None
                or hypothesis_id is not None
                or lead_id not in exploration_by_id
            ):
                raise ValueError("exploratory case lineage does not resolve to one retained lead")
            _validate_exploration_request_projection(
                item["exploration_request"], exploration_by_id[lead_id]
            )
        _keys(item["disclosures"], _DISCLOSURE_FIELDS, "case disclosures")
        if item["disclosures"]["maturity_authority"] not in {e.value for e in OptionMaturityAuthority}:
            raise ValueError("unknown case maturity authority")
        if item["disclosures"]["hypothesis_maturity_alignment"] not in {"unknown"} | {e.value for e in HypothesisMaturityAlignment}:
            raise ValueError("unknown hypothesis maturity alignment")
        if item["disclosures"]["quote_reference_temporal_alignment"] != "not_established" or item["disclosures"]["cross_structure_quote_synchronicity"] != "not_established":
            raise ValueError("batch authority disclosures are invalid")
        if lead_id is not None and (
            item["disclosures"]["maturity_authority"]
            != OptionMaturityAuthority.EXPLORATORY_STRUCTURE_RESEARCH.value
            or item["disclosures"]["hypothesis_maturity_alignment"]
            != HypothesisMaturityAlignment.NOT_ESTABLISHED.value
        ):
            raise ValueError("exploratory case maturity authority or alignment is invalid")
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
        _profile_check(core_result, profile_snapshot)
        expected_reasons = list(dict.fromkeys(
            tuple(item["application_reasons"]) + tuple(reason.value for reason in core_result.reasons)
        ))
        if item["reasons"] != expected_reasons:
            raise ValueError("case reasons differ from the retained Core/application reasons")
        decoded_cases[case_id] = core_result
        canonical_case_entries.append(item)

    canonical_unavailable = []
    for item in archive["unavailable"]:
        _keys(
            item,
            _UNAVAILABLE_FIELDS_V0_3
            if schema_version == EXPLORATION_SCHEMA_VERSION
            else _UNAVAILABLE_FIELDS,
            "unavailable sidecar",
        )
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
        _keys(
            item["lineage"],
            _LINEAGE_FIELDS_V0_3
            if schema_version == EXPLORATION_SCHEMA_VERSION
            else _LINEAGE_FIELDS,
            "unavailable lineage",
        )
        submission_id = _optional_text(item["lineage"]["submission_id"], "lineage.submission_id")
        hypothesis_id = _optional_text(item["lineage"]["hypothesis_id"], "lineage.hypothesis_id")
        lead_id = (
            _optional_text(item["lineage"]["lead_id"], "lineage.lead_id")
            if schema_version == EXPLORATION_SCHEMA_VERSION
            else None
        )
        if lead_id is not None:
            if (
                schema_version != EXPLORATION_SCHEMA_VERSION
                or submission_id is not None
                or hypothesis_id is not None
                or lead_id not in exploration_by_id
            ):
                raise ValueError("exploratory unavailable lineage does not resolve to one retained lead")
            _validate_exploration_request_projection(
                item["exploration_request"], exploration_by_id[lead_id]
            )
        elif schema_version == EXPLORATION_SCHEMA_VERSION and item["exploration_request"] is not None:
            raise ValueError("unavailable EI branch cannot retain an exploratory request")
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

    if "source_coverage_by_unit" in archive:
        coverage_rows = (
            _world_exploration_coverage_rows(
                archive["source_coverage_by_unit"],
                host_run_id=run_id,
                leads=exploration_leads,
                archived=schema_version == EXPLORATION_SCHEMA_VERSION,
            )
            if schema_version == EXPLORATION_SCHEMA_VERSION
            else _source_coverage_unit_rows(
                archive["source_coverage_by_unit"], host_run_id=run_id
            )
        )
        if coverage_rows != archive["source_coverage_by_unit"]:
            raise ValueError("source coverage sidecar is not in its canonical closed shape")
        _validate_source_coverage_links(
            coverage_rows,
            host_run_id=run_id,
            submissions=archive["ei_audit"]["submissions"],
            cases=archive["cases"],
            unavailable=archive["unavailable"],
            exploration_leads=exploration_leads,
        )

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
        exploration_lead_count=len(effective_counts.effective_exploration_leads),
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
        has_valid_exploration=bool(exploration_leads),
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


def _coverage_public_projection(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if row is None or row["source_coverage"] is None:
        value = {
            "unit_id": None if row is None else row["unit_id"],
            "status": "UNKNOWN",
            "successful_count": None,
            "requested_count": None,
            "failed_sources": [],
        }
        if row is not None and "exploration_lead_ids" in row:
            value["exploration_lead_ids"] = list(row["exploration_lead_ids"])
        return value
    audit = HostSourceCoverageAudit.from_dict(row["source_coverage"])
    entries = audit.to_dict()["entries"]
    successful_count = sum(item["status"] == "BODY_AVAILABLE" for item in entries)
    failed_sources = [
        {
            "source_id": item["source_id"],
            "locator": item["locator"],
            "reason_code": item["reason_code"],
        }
        for item in entries
        if item["status"] == "FAILED"
    ]
    value = {
        "unit_id": row["unit_id"],
        "status": audit.status,
        "successful_count": successful_count,
        "requested_count": len(entries),
        "failed_sources": failed_sources,
    }
    if "exploration_lead_ids" in row:
        value["exploration_lead_ids"] = list(row["exploration_lead_ids"])
    return value


def _coverage_unit_by_submission(archive: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if archive.get("schema_version") not in (
        SOURCE_COVERAGE_SCHEMA_VERSION, EXPLORATION_SCHEMA_VERSION
    ) or "source_coverage_by_unit" not in archive:
        return {}
    return {
        submission_id: row
        for row in archive["source_coverage_by_unit"]
        for submission_id in row["submission_ids"]
    }


def _coverage_unit_by_lead(archive: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if (
        archive.get("schema_version") != EXPLORATION_SCHEMA_VERSION
        or "source_coverage_by_unit" not in archive
    ):
        return {}
    return {
        lead_id: row
        for row in archive["source_coverage_by_unit"]
        for lead_id in row["exploration_lead_ids"]
    }


def _coverage_for_lineage(
    archive: Dict[str, Any],
    lineage: Dict[str, Any],
    *,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    by_submission = _coverage_unit_by_submission(archive)
    row = by_submission.get(lineage.get("submission_id"))
    by_lead = _coverage_unit_by_lead(archive)
    lead_row = by_lead.get(lineage.get("lead_id"))
    if row is not None and lead_row is not None and row is not lead_row:
        raise ValueError("case EI and exploration coverage links identify different units")
    if row is None:
        row = lead_row
    by_unit = {
        item["unit_id"]: item for item in archive["source_coverage_by_unit"]
    }
    identity_row = by_unit.get(case_id) if type(case_id) is str else None
    if row is not None and identity_row is not None and row is not identity_row:
        raise ValueError("case identity conflicts with its linked coverage unit")
    if row is None:
        row = identity_row
    return _coverage_public_projection(row)


def _coverage_report_text(coverage: Dict[str, Any]) -> str:
    status = coverage["status"]
    if status == "UNKNOWN":
        return "来源提取覆盖：UNKNOWN；没有可验证的来源覆盖审计。"
    successful = coverage["successful_count"]
    requested = coverage["requested_count"]
    lines = [
        "来源提取覆盖：{}；已取得正文 {}/{}。".format(
            status, successful, requested
        )
    ]
    failed = coverage["failed_sources"]
    if failed:
        lines.append(
            "失败来源：" + "；".join(
                "{} {}（{}）".format(
                    item["source_id"], item["locator"], item["reason_code"]
                )
                for item in failed
            )
        )
    if status == "PARTIAL":
        lines.append(PARTIAL_SOURCE_COVERAGE_DISCLOSURE)
    return "\n".join(lines)


def _archive_ei_status(archive: Dict[str, Any]) -> Tuple[str, List[Dict[str, str]]]:
    assessments = [
        {
            "submission_id": item["submission_id"],
            "status": item["assessment"]["status"].upper(),
        }
        for item in archive["ei_audit"]["submissions"]
    ]
    if not assessments:
        return "NOT_RUN", []
    statuses = {item["status"] for item in assessments}
    return (next(iter(statuses)) if len(statuses) == 1 else "MIXED"), assessments


def _public_exploration_disclosure(
    archive: Dict[str, Any],
    *,
    lineage: Dict[str, Any],
    disclosures: Optional[Dict[str, Any]] = None,
    exploration_request: Optional[Dict[str, Any]] = None,
    include_lead: bool = False,
) -> Dict[str, Any]:
    status, assessments = _archive_ei_status(archive)
    lead_id = lineage.get("lead_id")
    lead_map = {
        item["lead_id"]: item for item in archive["exploration_audit"]["leads"]
    }
    lead = lead_map.get(lead_id)
    if lead_id is not None and lead is None:
        raise ValueError("public exploration lineage does not resolve to an archived lead")
    authority = (
        disclosures.get("maturity_authority")
        if disclosures is not None
        else None if exploration_request is None
        else exploration_request["maturity_authority"]
    )
    alignment = (
        disclosures.get("hypothesis_maturity_alignment")
        if disclosures is not None
        else "unknown" if exploration_request is None
        else exploration_request["hypothesis_maturity_alignment"]
    )
    value = {
        "exploration_status": "ADMITTED",
        "maturity_authority": authority,
        "hypothesis_maturity_alignment": alignment,
        "lead_id": lead_id,
        "ei_status": status,
        "ei_assessment_statuses": assessments,
        "ei_lead_association": (
            "NOT_ESTABLISHED" if lead_id is not None else "NOT_APPLICABLE"
        ),
    }
    if include_lead and lead is not None:
        value["lead_material"] = _exploration_lead_public_projection(lead)
    return value


def public_summary(archive: Dict[str, Any]) -> Dict[str, Any]:
    # The caller has decoded a fresh immutable JSON value from SQLite.
    result = {key: value for key, value in archive["summary"].items()}
    schema_version = archive.get("schema_version")
    if schema_version == EXPLORATION_SCHEMA_VERSION:
        result["case_summaries"] = [dict(item) for item in result["case_summaries"]]
        result["unavailable_cases"] = [dict(item) for item in result["unavailable_cases"]]
        result["exploration_status"] = "ADMITTED"
        result["exploration_lead_count"] = len(archive["exploration_audit"]["leads"])
        result["ei_status"], result["ei_assessment_statuses"] = _archive_ei_status(archive)
        result["ei_lead_association"] = "NOT_ESTABLISHED"
        cases_by_id = {item["case_id"]: item for item in archive["cases"]}
        unavailable_by_id = {item["case_id"]: item for item in archive["unavailable"]}
        for item in result["case_summaries"]:
            archived = cases_by_id[item["case_id"]]
            item.update(_public_exploration_disclosure(
                archive,
                lineage=archived["lineage"],
                disclosures=archived["disclosures"],
            ))
        for item in result["unavailable_cases"]:
            archived = unavailable_by_id[item["case_id"]]
            item.update(_public_exploration_disclosure(
                archive,
                lineage=archived["lineage"],
                exploration_request=archived["exploration_request"],
            ))
    if schema_version != SOURCE_COVERAGE_SCHEMA_VERSION and not (
        schema_version == EXPLORATION_SCHEMA_VERSION
        and "source_coverage_by_unit" in archive
    ):
        return result

    result["case_summaries"] = [dict(item) for item in result["case_summaries"]]
    result["unavailable_cases"] = [dict(item) for item in result["unavailable_cases"]]
    cases_by_id = {item["case_id"]: item for item in archive["cases"]}
    unavailable_by_id = {
        item["case_id"]: item for item in archive["unavailable"]
    }
    for item in result["case_summaries"]:
        item["source_coverage"] = _coverage_for_lineage(
            archive, cases_by_id[item["case_id"]]["lineage"]
        )
    for item in result["unavailable_cases"]:
        archived = unavailable_by_id[item["case_id"]]
        item["source_coverage"] = _coverage_for_lineage(
            archive,
            archived["lineage"],
            case_id=archived["case_id"],
        )
    result["source_coverage_by_unit"] = [
        _coverage_public_projection(row)
        for row in archive["source_coverage_by_unit"]
    ]
    return result


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
    if archive.get("schema_version") == EXPLORATION_SCHEMA_VERSION:
        cases_by_id = {item["case_id"]: item for item in archive["cases"]}
        unavailable_by_id = {item["case_id"]: item for item in archive["unavailable"]}
        for item in result:
            archived = (
                cases_by_id[item["case_id"]]
                if item["classification"] != "UNAVAILABLE"
                else unavailable_by_id[item["case_id"]]
            )
            item.update(_public_exploration_disclosure(
                archive,
                lineage=archived["lineage"],
                disclosures=archived.get("disclosures"),
                exploration_request=archived.get("exploration_request"),
            ))
    if archive.get("schema_version") == SOURCE_COVERAGE_SCHEMA_VERSION or (
        archive.get("schema_version") == EXPLORATION_SCHEMA_VERSION
        and "source_coverage_by_unit" in archive
    ):
        cases_by_id = {item["case_id"]: item for item in archive["cases"]}
        unavailable_by_id = {
            item["case_id"]: item for item in archive["unavailable"]
        }
        for item in result:
            source = (
                cases_by_id[item["case_id"]]
                if item["classification"] != "UNAVAILABLE"
                else unavailable_by_id[item["case_id"]]
            )
            item["source_coverage"] = _coverage_for_lineage(
                archive,
                source["lineage"],
                case_id=(
                    source["case_id"]
                    if item["classification"] == "UNAVAILABLE"
                    else None
                ),
            )
    return result


def public_case(archive: Dict[str, Any], key: str, decoded_cases: Mapping[str, CoreResearchResult]) -> Optional[Dict[str, Any]]:
    validate_case_key(key)
    for item in archive["cases"]:
        if item["case_key"] == key:
            from .core_presentation import _render_core_report

            result = decoded_cases[item["case_id"]]
            if item["lineage"].get("lead_id") is not None:
                lead = next(
                    (
                        candidate
                        for candidate in archive["exploration_audit"]["leads"]
                        if candidate["lead_id"] == item["lineage"]["lead_id"]
                    ),
                    None,
                )
                if lead is None:
                    raise ValueError("public exploratory case has no audited lead")
                audit_entries = tuple(
                    audited["submission_id"] + ":" + audited["assessment"]["status"]
                    for audited in archive["ei_audit"]["submissions"]
                )
                audit_text = repr(audit_entries) if audit_entries else "未提交"
                disclosure = (
                    "来源路径=Host投影的结构探索线索；来源准入、receipt与listing核验由Host负责，Core不重做；"
                    "独立结构探索，不形成EI支持的分布声明；"
                    "独立EI批次审计=" + audit_text + "; "
                    "lead_id=" + lead["lead_id"] + "; event_statement_id="
                    + lead["event_statement_id"] + "; exposure_statement_id="
                    + lead["exposure_statement_id"] + "; maturity_authority="
                    + item["disclosures"]["maturity_authority"]
                    + "; hypothesis_maturity_alignment=not_established; uncertainties="
                    + repr(tuple(lead["uncertainties"]))
                )
            else:
                submission_id = item["lineage"]["submission_id"]
                submission = next(
                    (
                        audited
                        for audited in archive["ei_audit"]["submissions"]
                        if audited["submission_id"] == submission_id
                    ),
                    None,
                )
                if submission is None:
                    raise ValueError("public EI case has no audited submission status")
                disclosure = (
                    "来源路径=Event Intelligence hypothesis; "
                    "event_intelligence_status="
                    + submission["assessment"]["status"]
                    + "; maturity_authority="
                    + item["disclosures"]["maturity_authority"]
                    + "; hypothesis_maturity_alignment="
                    + item["disclosures"]["hypothesis_maturity_alignment"]
                )
            value = {
                "case_id": item["case_id"],
                "case_key": item["case_key"],
                "classification": item["classification"],
                "reasons": list(item["reasons"]),
                "report": _render_core_report(
                    item["case_id"], result, tuple(item["reasons"]), disclosure
                ),
            }
            if archive.get("schema_version") == EXPLORATION_SCHEMA_VERSION:
                disclosure = _public_exploration_disclosure(
                    archive,
                    lineage=item["lineage"],
                    disclosures=item["disclosures"],
                    exploration_request=item["exploration_request"],
                    include_lead=True,
                )
                value.update(disclosure)
                if item["lineage"]["lead_id"] is not None:
                    value["report"] += (
                        "\n\n结构探索披露：maturity_authority="
                        + disclosure["maturity_authority"]
                        + "; hypothesis_maturity_alignment="
                        + disclosure["hypothesis_maturity_alignment"]
                        + "; EI batch status=" + disclosure["ei_status"]
                        + " (lead association NOT_ESTABLISHED)."
                    )
            if archive.get("schema_version") == SOURCE_COVERAGE_SCHEMA_VERSION or (
                archive.get("schema_version") == EXPLORATION_SCHEMA_VERSION
                and "source_coverage_by_unit" in archive
            ):
                coverage = _coverage_for_lineage(archive, item["lineage"])
                value["source_coverage"] = coverage
                value["report"] += "\n\n" + _coverage_report_text(coverage)
            return value
    for item in archive["unavailable"]:
        if item["case_key"] == key:
            value = {
                "case_id": item["case_id"],
                "case_key": item["case_key"],
                "classification": "UNAVAILABLE",
                "reasons": list(item["reasons"]),
                "report": None,
            }
            if archive.get("schema_version") == EXPLORATION_SCHEMA_VERSION:
                value.update(_public_exploration_disclosure(
                    archive,
                    lineage=item["lineage"],
                    exploration_request=item["exploration_request"],
                    include_lead=True,
                ))
            if archive.get("schema_version") == SOURCE_COVERAGE_SCHEMA_VERSION or (
                archive.get("schema_version") == EXPLORATION_SCHEMA_VERSION
                and "source_coverage_by_unit" in archive
            ):
                value["source_coverage"] = _coverage_for_lineage(
                    archive, item["lineage"], case_id=item["case_id"]
                )
            return value
    return None
