"""Bounded Event Grounder composition over the existing Host adapters.

This module performs source acquisition and the pre-Core Grounder run only. It
does not assess EI, invoke market data, persist records, or fabricate Event
dates/listing evidence. Its default context preparer may bind a sole verified
observed fact, or one uniquely covered verified fact when several exist, and a
narrowly source-bound SEC 8-K occurrence date or SEC Nasdaq SRO approval date.
Unsupported dates and listing bindings remain unknown. This is not a complete
product Grounder. Credentials remain external references and are resolved
only by the existing clients when a request is made.
"""

from __future__ import annotations

import datetime
import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Optional, Union
from urllib.parse import urlsplit

from .core_application import CoreOperationalBounds
from .event_entry import UserEventInput
from .event_intelligence import MethodologizedDateRange
from .host_grounder_builder import HostBuildContext, HostSourceBody
from .host_grounder_evidence_catalog import (
    HostEvidenceCatalogAuditHolder,
    _line_paragraph_spans,
)
from .host_grounder_receipt import ValidatedEnvelopeSnapshot
from .host_grounder_run_input import (
    HostGrounderRunInput,
    HostGrounderRunInputBounds,
    HostGrounderSubquestion,
)
from .host_grounder_runtime import (
    HostGrounderEvidenceCatalogRuntimeResult,
    HostGrounderRuntimeError,
    _EventFactAnchorOutcome,
    _run_host_grounder_same_run_evidence_catalog_v0_9,
    _stamp_event_fact_anchor_outcome,
    run_host_grounder_same_run_evidence_catalog_v0_6,
)
from .market_data import UnderlyingKey, UnderlyingSecurityType
from .host_model import (
    ChatCompletionsClient,
    ModelCredential,
    ModelRuntimeConfig,
    ModelTransportError,
)
from .host_sources import (
    TavilyCredentialRef,
    TavilySourceClient,
    TavilySourceConfig,
    TavilyTransportError,
)
from .host_source_admission import (
    AdmissionBatch,
    MAX_SOURCE_ADMISSION_REQUESTS,
    _SourceAdmissionClient,
    SourceAdmission,
    _create_source_admission_client,
    _revalidate_source_admission,
    _sec_cover_layout_v4_fold,
)


__all__ = ("HostEventGrounderConfig", "create_event_grounder")


_PRODUCER_ID = "convexity-hunter-event-grounder"
_PRODUCER_VERSION = "v0.1"
_SUBQUESTION_ID = "user_event_input"
_EVENT_FACT_ANCHOR_SUBQUESTION_ID = "event_fact_anchor_v0_1"
_EVENT_FACT_ANCHOR_QUESTION = (
    "Does exactly one registered source-backed observed_fact directly state "
    "the event described by the user's event input? Assess only event identity "
    "and direct relevance. Do not assess economic materiality, market impact, "
    "transmission mechanism, underlying or listing identity, event timing, or "
    "completeness of the broader research answer. Identify exactly one "
    "claim_id only when that fact is uniquely supported and unambiguous; "
    "otherwise leave this subquestion unresolved and state the gap."
)
_FORBIDDEN_CREDENTIAL_BASENAME = "futu_api_config.properties"
_APPROVED_MODEL_PROVIDER = "deepseek"
_APPROVED_MODEL_BASE_ENDPOINT = "https://api.deepseek.com"
_SEC_EDGAR_LOCATOR = re.compile(
    r"/Archives/edgar/data/(?P<cik>[0-9]{1,10})/"
    r"(?P<accession>(?:[0-9]{18}|[0-9]{10}-[0-9]{2}-[0-9]{6}))/"
    r"(?P<filename>[A-Za-z0-9][A-Za-z0-9._-]*)\Z"
)
_SEC_ACCESSION = re.compile(r"(?:[0-9]{18}|[0-9]{10}-[0-9]{2}-[0-9]{6})\Z")
_SEC_CIK = re.compile(r"[0-9]{10}\Z")
_ENGLISH_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December"
)
_ENGLISH_MONTH_NUMBERS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}
_SOURCE_DATE_TOKEN = re.compile(
    r"(?i)\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+[0-9]{1,2},?\s+[0-9]{4}\b"
    r"|\b[0-9]{4}-[0-9]{2}-[0-9]{2}\b"
    r"|\b[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}\b"
)
_UNCERTAIN_ACTION = re.compile(
    r"\b(?:may|might|could|would|will|shall|if|unless|pending|conditional|"
    r"contingent|proposed?|intend(?:s|ed|ing)?|plan(?:s|ned|ning)?|"
    r"expect(?:s|ed|ing)?|scheduled|subject\s+to|and|or|then|followed\s+by)\b",
    re.IGNORECASE,
)
_ACTION_VERB = r"(?:entered into|completed|closed|executed|signed)"
_ACTION_VERB_V0_2 = r"(?:entered into|completed|closed|executed|signed|announced)"
_SRO_ASCII_WS = r"[ \t\r\n\f\v]"
_SRO_ASCII_WS_RUN = re.compile(_SRO_ASCII_WS + r"+")
_SRO_LOCATOR = re.compile(
    r"https://www\.sec\.gov/files/rules/sro/nasdaq/"
    r"(?P<year>[0-9]{4})/34-(?P<release>[0-9]+)\.pdf\Z"
)
_SRO_RELEASE_FILE = re.compile(
    r"\[Release" + _SRO_ASCII_WS + r"+No\." + _SRO_ASCII_WS
    + r"+(?P<release>34-[0-9]+);" + _SRO_ASCII_WS + r"+File"
    + _SRO_ASCII_WS + r"+No\." + _SRO_ASCII_WS
    + r"+(?P<file>SR-Nasdaq-[0-9]{4}-[0-9]+)\]"
)
_SRO_SEC_HEADING = re.compile(
    r"SECURITIES" + _SRO_ASCII_WS + r"+AND" + _SRO_ASCII_WS
    + r"+EXCHANGE" + _SRO_ASCII_WS + r"+COMMISSION"
)
_SRO_IDENTITY_HEADING = re.compile(
    r"Self-Regulatory" + _SRO_ASCII_WS + r"+Organizations;"
    + _SRO_ASCII_WS + r"+The" + _SRO_ASCII_WS + r"+Nasdaq"
    + _SRO_ASCII_WS + r"+Stock" + _SRO_ASCII_WS + r"+Market"
    + _SRO_ASCII_WS + r"+LLC;"
)
_SRO_AMENDMENT_NOTICE_PREFIX = re.compile(
    r"Notice of Filing of Amendment Nos\. [1-9][0-9]* and [1-9][0-9]* and",
    re.ASCII,
)
_SRO_COVER_STATUS_LABEL = re.compile(
    r"\b(?:DRAFT|PRELIMINARY|PENDING)\b",
    re.IGNORECASE | re.ASCII,
)
_SRO_TITLE = re.compile(
    r"Order" + _SRO_ASCII_WS + r"+Granting" + _SRO_ASCII_WS
    + r"+Accelerated" + _SRO_ASCII_WS + r"+Approval" + _SRO_ASCII_WS
    + r"+of" + _SRO_ASCII_WS + r"+a" + _SRO_ASCII_WS
    + r"+Proposed" + _SRO_ASCII_WS + r"+Rule" + _SRO_ASCII_WS
    + r"+Change"
)
_SRO_FULL_MONTH = (
    r"January|February|March|April|May|June|July|August|September|"
    r"October|November|December"
)
_SRO_MONTH_NUMBERS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2,
    "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
_SRO_DATE_MONTH = (
    _SRO_FULL_MONTH
    + r"|Jan\.?|Feb\.?|Mar\.?|Apr\.?|May\.?|Jun\.?|Jul\.?|"
    r"Aug\.?|Sep\.?|Oct\.?|Nov\.?|Dec\.?"
)
_SRO_DATE_TOKEN = re.compile(
    r"(?<![A-Za-z0-9-])(?P<month>" + _SRO_DATE_MONTH + r")"
    + _SRO_ASCII_WS + r"+(?P<day>[0-9]{1,2})," + _SRO_ASCII_WS
    + r"+(?P<year>[0-9]{4})(?![A-Za-z0-9-])"
    r"|(?<![A-Za-z0-9-])(?P<iso>[0-9]{4}-[0-9]{2}-[0-9]{2})"
    r"(?![A-Za-z0-9-])",
    re.IGNORECASE | re.ASCII,
)
_SRO_COVER_DATE = re.compile(
    _SRO_ASCII_WS + r"+(?P<token>(?P<month>" + _SRO_FULL_MONTH + r")"
    + _SRO_ASCII_WS + r"+(?P<day>[0-9]{1,2})," + _SRO_ASCII_WS
    + r"+(?P<year>[0-9]{4}))\."
)
_SRO_ORDER_START = re.compile(
    r"IT" + _SRO_ASCII_WS + r"+IS" + _SRO_ASCII_WS + r"+THEREFORE"
    + _SRO_ASCII_WS + r"+ORDERED"
)
_SRO_APPROVAL_END = re.compile(
    r"be," + _SRO_ASCII_WS + r"*and" + _SRO_ASCII_WS + r"+is"
    + _SRO_ASCII_WS + r"+hereby," + _SRO_ASCII_WS + r"*approved"
    + _SRO_ASCII_WS + r"+on" + _SRO_ASCII_WS + r"+an"
    + _SRO_ASCII_WS + r"+accelerated" + _SRO_ASCII_WS + r"+basis\."
)
_SRO_DATE_LABEL = re.compile(
    r"^[ \t]*(?:Order date:|Approval date:|Dated:)",
    re.IGNORECASE | re.MULTILINE | re.ASCII,
)
_SRO_SIGNATURE = re.compile(
    r"^[ \t]*(?:For|By)" + _SRO_ASCII_WS + r"+the"
    + _SRO_ASCII_WS + r"+Commission\b",
    re.IGNORECASE | re.MULTILINE | re.ASCII,
)
_SRO_NONOPERATIVE = re.compile(
    r"\b(?:conditional(?:ly)?|pending|contingent|subject\s+to|if|unless|"
    r"not|never|denied|rejected|disapproved|withdrawn|vacated|rescinded|"
    r"partial(?:ly)?|recommendation|recommended)\b",
    re.IGNORECASE | re.ASCII,
)
_SEC_HEADER_LABELS = {
    "form": "CONFORMED SUBMISSION TYPE",
    "accession": "ACCESSION NUMBER",
    "registrant": "COMPANY CONFORMED NAME",
    "cik": "CENTRAL INDEX KEY",
}
_RECEIPT_MAPPING_TYPE = type(MappingProxyType({}))


def _positive_int(name: str, value: object) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError("{} must be a positive integer".format(name))


def _is_loopback_endpoint(endpoint: str) -> bool:
    hostname = urlsplit(endpoint).hostname
    if hostname is None:
        return True
    normalized = hostname.rstrip(".").casefold()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _reject_futu_credential_path(credential: object) -> None:
    path = getattr(credential, "properties_path", None)
    if path is None:
        return
    try:
        supplied = Path(path)
        resolved = supplied.resolve(strict=False)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise ValueError("credential reference is invalid") from None
    if any(
        candidate.name.casefold() == _FORBIDDEN_CREDENTIAL_BASENAME
        for candidate in (supplied, resolved)
    ):
        raise ValueError("futu credential files are not valid Grounder credentials")


@dataclass(frozen=True, repr=False)
class HostEventGrounderConfig:
    """All non-economic budgets and external client settings for Event Grounder.

    A strict external loader can construct this record from the following
    existing typed components: ``TavilySourceConfig``, two role-specific
    ``ModelRuntimeConfig``/``ModelCredential`` pairs, and
    ``HostGrounderRunInputBounds``. The five Grounder limits are mandatory;
    this layer introduces no numeric defaults.
    """

    source: TavilySourceConfig
    discovery_model: ModelRuntimeConfig
    discovery_credential: ModelCredential
    semantic_model: ModelRuntimeConfig
    semantic_credential: ModelCredential
    run_input_bounds: HostGrounderRunInputBounds
    max_json_bytes: int
    max_source_body_bytes: int
    max_catalog_entries: int
    max_catalog_bytes: int
    max_catalog_paragraphs: int

    def __post_init__(self) -> None:
        if type(self.source) is not TavilySourceConfig:
            raise TypeError("source must be TavilySourceConfig")
        for name, config, credential, role in (
            ("discovery", self.discovery_model, self.discovery_credential, "discovery"),
            ("semantic", self.semantic_model, self.semantic_credential, "semantic"),
        ):
            if type(config) is not ModelRuntimeConfig:
                raise TypeError("{}_model must be ModelRuntimeConfig".format(name))
            if config.role != role:
                raise ValueError("{}_model has the wrong role".format(name))
            if type(credential) is not ModelCredential:
                raise TypeError("{}_credential must be ModelCredential".format(name))
            if not config.remote_enabled or not config.fee_authorized:
                raise ValueError("{} model must be explicitly remote and fee-authorized".format(name))
            if _is_loopback_endpoint(config.base_endpoint):
                raise ValueError("local model endpoints are not supported")
            _reject_futu_credential_path(credential)
        _reject_futu_credential_path(self.source.credential_ref)
        if type(self.run_input_bounds) is not HostGrounderRunInputBounds:
            raise TypeError("run_input_bounds must be HostGrounderRunInputBounds")
        for name in (
            "max_json_bytes",
            "max_source_body_bytes",
            "max_catalog_entries",
            "max_catalog_bytes",
            "max_catalog_paragraphs",
        ):
            _positive_int(name, getattr(self, name))

    def __repr__(self) -> str:
        return "HostEventGrounderConfig(<redacted>)"


def _revalidate_config(config: object) -> HostEventGrounderConfig:
    """Re-run every nested constructor, including after frozen-object bypasses."""
    if type(config) is not HostEventGrounderConfig:
        raise TypeError("config must be HostEventGrounderConfig")
    source_config = config.source
    if type(source_config) is not TavilySourceConfig:
        raise TypeError("source must be TavilySourceConfig")
    source_credential_ref = source_config.credential_ref
    if type(source_credential_ref) is not TavilyCredentialRef:
        raise TypeError("source credential reference is invalid")
    source_credential_ref = TavilyCredentialRef(
        properties_path=source_credential_ref.properties_path,
        env_name=source_credential_ref.env_name,
    )
    source = TavilySourceConfig(
        credential_ref=source_credential_ref,
        paygo_off_confirmed=source_config.paygo_off_confirmed,
        request_budget=source_config.request_budget,
        credit_budget=source_config.credit_budget,
        max_request_bytes=source_config.max_request_bytes,
        max_response_bytes=source_config.max_response_bytes,
        timeout_seconds=source_config.timeout_seconds,
        time_budget_seconds=source_config.time_budget_seconds,
        byte_budget=source_config.byte_budget,
        max_search_results=source_config.max_search_results,
        max_extract_urls=source_config.max_extract_urls,
    )

    def checked_model(
        model_config: object, credential: object, role: str
    ) -> tuple:
        if type(model_config) is not ModelRuntimeConfig:
            raise TypeError("{}_model must be ModelRuntimeConfig".format(role))
        if type(credential) is not ModelCredential:
            raise TypeError("{}_credential must be ModelCredential".format(role))
        if (
            model_config.provider != _APPROVED_MODEL_PROVIDER
            or model_config.base_endpoint != _APPROVED_MODEL_BASE_ENDPOINT
        ):
            raise ValueError("UNAPPROVED_MODEL_CONFIGURATION")
        checked_config = ModelRuntimeConfig(
            provider=model_config.provider,
            model=model_config.model,
            base_endpoint=model_config.base_endpoint,
            role=model_config.role,
            capabilities=model_config.capabilities,
            timeout_seconds=model_config.timeout_seconds,
            request_budget=model_config.request_budget,
            max_tokens=model_config.max_tokens,
            max_input_bytes=model_config.max_input_bytes,
            max_output_bytes=model_config.max_output_bytes,
            remote_enabled=model_config.remote_enabled,
            fee_authorized=model_config.fee_authorized,
            json_mode=model_config.json_mode,
            thinking_enabled=model_config.thinking_enabled,
        )
        checked_credential = ModelCredential(
            properties_path=credential.properties_path,
            env_name=credential.env_name,
        )
        return checked_config, checked_credential

    discovery_model, discovery_credential = checked_model(
        config.discovery_model, config.discovery_credential, "discovery"
    )
    semantic_model, semantic_credential = checked_model(
        config.semantic_model, config.semantic_credential, "semantic"
    )
    input_bounds = config.run_input_bounds
    if type(input_bounds) is not HostGrounderRunInputBounds:
        raise TypeError("run_input_bounds must be HostGrounderRunInputBounds")
    checked_input_bounds = HostGrounderRunInputBounds(
        max_run_input_bytes=input_bounds.max_run_input_bytes,
        max_string_bytes=input_bounds.max_string_bytes,
        max_array_items=input_bounds.max_array_items,
    )
    return HostEventGrounderConfig(
        source=source,
        discovery_model=discovery_model,
        discovery_credential=discovery_credential,
        semantic_model=semantic_model,
        semantic_credential=semantic_credential,
        run_input_bounds=checked_input_bounds,
        max_json_bytes=config.max_json_bytes,
        max_source_body_bytes=config.max_source_body_bytes,
        max_catalog_entries=config.max_catalog_entries,
        max_catalog_bytes=config.max_catalog_bytes,
        max_catalog_paragraphs=config.max_catalog_paragraphs,
    )


def _retain_unknown_context(
    snapshot: object,
    receipt: object,
    original_context: HostBuildContext,
) -> HostBuildContext:
    """Fill only a unique verified fact and its narrowly source-bound SEC date."""
    if type(original_context) is not HostBuildContext:
        raise TypeError("original_context must be HostBuildContext")
    evidence = _preparation_evidence(snapshot, receipt, original_context)
    if evidence is None:
        return original_context
    envelope, verified_claim_ids, verified_binding_indices = evidence

    claims = envelope.get("claims")
    if type(claims) is not list:
        return original_context
    candidates = []
    for index, claim in enumerate(claims):
        if type(claim) is not dict:
            continue
        claim_id = claim.get("claim_id")
        source_id = claim.get("source_id")
        if (
            type(claim_id) is not str
            or claim_id not in verified_claim_ids
            or claim.get("kind") != "observed_fact"
            or type(source_id) is not str
        ):
            continue
        source = original_context.source_bodies.get(source_id)
        if type(source) is not HostSourceBody:
            continue
        if claim.get("locator") != source.final_locator:
            continue
        quote = claim.get("quote")
        if type(quote) is not str or not quote:
            continue
        first_quote = source.body.find(quote)
        if first_quote < 0 or source.body.find(quote, first_quote + 1) >= 0:
            continue
        candidates.append((index, claim, source))

    # A verified fact is not a subjective selection menu. Multiple candidates
    # leave both inferred fields unknown.
    if len(candidates) != 1:
        return original_context

    claim_index, claim, source = candidates[0]
    description = original_context.event_description_binding
    if description is not None and description != claim["claim_id"]:
        # Do not attach another fact's occurrence date to a supplied binding.
        return original_context
    if description is None:
        description = claim["claim_id"]

    date_range = original_context.event_date_range
    if date_range is None:
        occurrence = _resolve_sec_occurrence_date(
            claim_index,
            claim,
            source,
            envelope,
            verified_binding_indices,
            original_context,
        )
        if occurrence is not None:
            event_date, start, end = occurrence
            methodology = json.dumps(
                {
                    "rule_version": "host-event-source-facts-v0.1/sec-8-k-occurrence-date",
                    "source_id": claim["source_id"],
                    "body_sha256": source.body_sha256,
                    "start": start,
                    "end": end,
                    "locator": source.final_locator,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            date_range = MethodologizedDateRange(
                event_date, event_date, methodology
            )

    if (
        description is original_context.event_description_binding
        and date_range is original_context.event_date_range
    ):
        return original_context
    return replace(
        original_context,
        event_description_binding=description,
        event_date_range=date_range,
    )


def _preparation_evidence(snapshot: object, receipt: object, context: HostBuildContext):
    """Recheck the exact Host snapshot, receipt bindings, and retained bodies."""
    if (
        type(snapshot) is not ValidatedEnvelopeSnapshot
        or type(receipt) is not _RECEIPT_MAPPING_TYPE
        or type(snapshot.canonical_bytes) is not bytes
        or type(snapshot.envelope_hash) is not str
        or re.fullmatch(r"[0-9a-f]{64}", snapshot.envelope_hash) is None
        or type(context.source_bodies) is not _RECEIPT_MAPPING_TYPE
    ):
        return None
    if hashlib.sha256(snapshot.canonical_bytes).hexdigest() != snapshot.envelope_hash:
        return None
    try:
        envelope = json.loads(snapshot.canonical_bytes.decode("utf-8", errors="strict"))
        canonical = json.dumps(
            envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeDecodeError, RecursionError):
        return None
    if (
        type(envelope) is not dict
        or canonical != snapshot.canonical_bytes
        # The v0.3 producer wire is normalized by the existing parser to the
        # v0.1 internal envelope before it is retained in the snapshot.
        or envelope.get("schema_version") != "grounder-output-v0.1"
        or envelope.get("stage") != "semantic"
        or envelope.get("request_id") != context.run_id
        or receipt.get("schema_version") != "semantic-validation-v0.2"
        or receipt.get("run_id") != context.run_id
        or receipt.get("canonical_input_hash") != context.canonical_input_hash
        or receipt.get("envelope_hash") != snapshot.envelope_hash
    ):
        return None

    source_hashes = []
    try:
        for source_id, source in sorted(context.source_bodies.items()):
            if type(source_id) is not str or type(source) is not HostSourceBody:
                return None
            checked_source = HostSourceBody(
                source.body,
                source.body_sha256,
                source.final_locator,
                source.retrieved_at,
                source.title,
                source.published_at,
            )
            source_hashes.append((source_id, checked_source.body_sha256))
    except (AttributeError, TypeError, UnicodeEncodeError, ValueError):
        return None
    receipt_source_hashes = receipt.get("source_body_hashes")
    if (
        type(receipt_source_hashes) is not tuple
        or receipt_source_hashes != tuple(source_hashes)
    ):
        return None

    verified_claim_ids = receipt.get("verified_claim_ids")
    verified_binding_indices = receipt.get("verified_binding_indices")
    if (
        type(verified_claim_ids) is not tuple
        or any(type(value) is not str for value in verified_claim_ids)
        or len(set(verified_claim_ids)) != len(verified_claim_ids)
        or type(verified_binding_indices) is not tuple
        or any(type(value) is not int or value < 0 for value in verified_binding_indices)
        or len(set(verified_binding_indices)) != len(verified_binding_indices)
    ):
        return None
    return envelope, frozenset(verified_claim_ids), frozenset(verified_binding_indices)


def _covered_event_fact(
    envelope: dict,
    receipt: object,
    claims: list,
    candidates: list,
    verified_claim_ids: frozenset,
):
    """Select one eligible fact only from one complete supported coverage root."""
    coverage = envelope.get("coverage")
    if type(coverage) is not list or type(receipt) is not _RECEIPT_MAPPING_TYPE:
        return None
    if any(type(item) is not dict for item in coverage):
        return None

    coverage_ids = []
    for item in coverage:
        subquestion_id = item.get("subquestion_id")
        if type(subquestion_id) is not str or not subquestion_id:
            return None
        coverage_ids.append(subquestion_id)
    if len(set(coverage_ids)) != len(coverage_ids):
        return None
    matching_indexes = [
        index
        for index, item in enumerate(coverage)
        if item.get("subquestion_id") == _SUBQUESTION_ID
    ]
    if len(matching_indexes) != 1:
        return None
    coverage_index = matching_indexes[0]
    selected_coverage = coverage[coverage_index]
    listed_claim_ids = selected_coverage.get("claim_ids")
    if (
        selected_coverage.get("status") != "supported"
        or "gap" not in selected_coverage
        or selected_coverage["gap"] is not None
        or type(listed_claim_ids) is not list
        or any(type(claim_id) is not str or not claim_id for claim_id in listed_claim_ids)
        or len(set(listed_claim_ids)) != len(listed_claim_ids)
        or any(claim_id not in verified_claim_ids for claim_id in listed_claim_ids)
    ):
        return None

    # A coverage ID must resolve to one exact envelope claim; receipt membership
    # alone cannot turn a missing or duplicate claim root into evidence.
    for claim_id in listed_claim_ids:
        if sum(
            type(claim) is dict and claim.get("claim_id") == claim_id
            for claim in claims
        ) != 1:
            return None

    outcomes = receipt.get("coverage_outcomes")
    if type(outcomes) is not tuple or len(outcomes) != len(coverage):
        return None
    outcomes_by_index = {}
    seen_outcome_ids = set()
    for outcome in outcomes:
        if (
            type(outcome) is not tuple
            or len(outcome) != 4
            or type(outcome[0]) is not int
            or outcome[0] < 0
            or outcome[0] >= len(coverage)
            or type(outcome[1]) is not str
            or not outcome[1]
            or type(outcome[2]) is not str
            or outcome[2] not in ("supported", "unresolved", "contradicted")
            or type(outcome[3]) is not str
            or not outcome[3]
            or outcome[0] in outcomes_by_index
            or outcome[1] in seen_outcome_ids
            or outcome[1] != coverage_ids[outcome[0]]
        ):
            return None
        outcomes_by_index[outcome[0]] = outcome
        seen_outcome_ids.add(outcome[1])
    if set(outcomes_by_index) != set(range(len(coverage))):
        return None
    selected_outcome = outcomes_by_index[coverage_index]
    if (
        selected_outcome[1] != _SUBQUESTION_ID
        or selected_outcome[2] != "supported"
    ):
        return None

    covered_ids = frozenset(listed_claim_ids)
    covered_candidates = [
        candidate for candidate in candidates if candidate[1].get("claim_id") in covered_ids
    ]
    if len(covered_candidates) != 1:
        return None
    return covered_candidates[0]


def _event_fact_anchor_claim_id(
    snapshot: object,
    receipt: object,
    context: HostBuildContext,
) -> Optional[str]:
    """Return only the uniquely verified claim named by the fixed anchor row."""
    evidence = _preparation_evidence(snapshot, receipt, context)
    if evidence is None:
        return None
    envelope, verified_claim_ids, _verified_binding_indices = evidence
    coverage = envelope.get("coverage")
    claims = envelope.get("claims")
    if type(coverage) is not list or type(claims) is not list or len(coverage) != 2:
        return None
    expected_ids = (_SUBQUESTION_ID, _EVENT_FACT_ANCHOR_SUBQUESTION_ID)
    if any(
        type(row) is not dict or row.get("subquestion_id") != expected
        for row, expected in zip(coverage, expected_ids)
    ):
        return None
    anchor = coverage[1]
    claim_ids = anchor.get("claim_ids")
    if (
        anchor.get("status") != "supported"
        or "gap" not in anchor
        or anchor["gap"] is not None
        or type(claim_ids) is not list
        or len(claim_ids) != 1
        or type(claim_ids[0]) is not str
        or not claim_ids[0]
        or claim_ids[0] not in verified_claim_ids
    ):
        return None

    outcomes = receipt.get("coverage_outcomes")
    if type(outcomes) is not tuple or len(outcomes) != 2:
        return None
    for index, (outcome, expected_id) in enumerate(zip(outcomes, expected_ids)):
        if (
            type(outcome) is not tuple
            or len(outcome) != 4
            or type(outcome[0]) is not int
            or outcome[0] != index
            or type(outcome[1]) is not str
            or outcome[1] != expected_id
            or type(outcome[2]) is not str
            or outcome[2] not in ("supported", "unresolved", "contradicted")
            or type(outcome[3]) is not str
            or not outcome[3]
        ):
            return None
    if outcomes[1][2] != "supported":
        return None

    claim_id = claim_ids[0]
    matches = [
        claim for claim in claims
        if type(claim) is dict and claim.get("claim_id") == claim_id
    ]
    if len(matches) != 1:
        return None
    claim = matches[0]
    source_id = claim.get("source_id")
    source = context.source_bodies.get(source_id) if type(source_id) is str else None
    quote = claim.get("quote")
    if (
        claim.get("kind") != "observed_fact"
        or type(source) is not HostSourceBody
        or claim.get("locator") != source.final_locator
        or type(quote) is not str
        or not quote
    ):
        return None
    quote_start = source.body.find(quote)
    if quote_start < 0 or source.body.find(quote, quote_start + 1) >= 0:
        return None
    return claim_id


def _retain_unknown_context_v0_5(
    snapshot: object,
    receipt: object,
    original_context: HostBuildContext,
    admission_by_id: dict,
) -> tuple[HostBuildContext, Optional[str]]:
    """Apply the independent anchor gate, then only v0.4 date derivation."""
    if type(original_context) is not HostBuildContext:
        raise TypeError("original_context must be HostBuildContext")
    selected_claim_id = None
    prepared = original_context
    if original_context.event_description_binding is None:
        selected_claim_id = _event_fact_anchor_claim_id(
            snapshot, receipt, original_context
        )
        if selected_claim_id is not None:
            prepared = replace(
                original_context,
                event_description_binding=selected_claim_id,
            )
    if selected_claim_id is not None and prepared.event_date_range is None:
        prepared = _retain_unknown_context_v0_4(
            snapshot, receipt, original_context, prepared, admission_by_id
        )
    return prepared, selected_claim_id


def _retain_unknown_context_v0_2(
    snapshot: object,
    receipt: object,
    original_context: HostBuildContext,
) -> HostBuildContext:
    """Successor default: bind one exact fact, using supported coverage if needed."""
    if type(original_context) is not HostBuildContext:
        raise TypeError("original_context must be HostBuildContext")
    evidence = _preparation_evidence(snapshot, receipt, original_context)
    if evidence is None:
        return original_context
    envelope, verified_claim_ids, verified_binding_indices = evidence

    claims = envelope.get("claims")
    if type(claims) is not list:
        return original_context
    candidates = []
    for index, claim in enumerate(claims):
        if type(claim) is not dict:
            continue
        claim_id = claim.get("claim_id")
        source_id = claim.get("source_id")
        if (
            type(claim_id) is not str
            or claim_id not in verified_claim_ids
            or claim.get("kind") != "observed_fact"
            or type(source_id) is not str
        ):
            continue
        source = original_context.source_bodies.get(source_id)
        if type(source) is not HostSourceBody:
            continue
        if claim.get("locator") != source.final_locator:
            continue
        quote = claim.get("quote")
        if type(quote) is not str or not quote:
            continue
        first_quote = source.body.find(quote)
        if first_quote < 0 or source.body.find(quote, first_quote + 1) >= 0:
            continue
        candidates.append((index, claim, source))

    if not candidates:
        return original_context

    supplied_description = original_context.event_description_binding
    if supplied_description is not None:
        selected = [
            candidate
            for candidate in candidates
            if candidate[1].get("claim_id") == supplied_description
        ]
        if len(selected) != 1:
            return original_context
        claim_index, claim, source = selected[0]
        description = supplied_description
    elif len(candidates) == 1:
        claim_index, claim, source = candidates[0]
        description = claim["claim_id"]
    else:
        selected = _covered_event_fact(
            envelope, receipt, claims, candidates, verified_claim_ids
        )
        if selected is None:
            return original_context
        claim_index, claim, source = selected
        description = claim["claim_id"]

    date_range = original_context.event_date_range
    if date_range is None:
        occurrence = _resolve_sec_occurrence_date_v0_2(
            claim_index,
            claim,
            source,
            envelope,
            verified_binding_indices,
            original_context,
        )
        if occurrence is not None:
            event_date, start, end, verb = occurrence
            methodology = json.dumps(
                {
                    "rule_version": "host-event-source-facts-v0.2/sec-8-k-occurrence-date",
                    "verb": verb,
                    "source_id": claim["source_id"],
                    "body_sha256": source.body_sha256,
                    "start": start,
                    "end": end,
                    "locator": source.final_locator,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            date_range = MethodologizedDateRange(event_date, event_date, methodology)

    if (
        description is original_context.event_description_binding
        and date_range is original_context.event_date_range
    ):
        return original_context
    return replace(
        original_context,
        event_description_binding=description,
        event_date_range=date_range,
    )


def _retain_unknown_context_v0_3(
    snapshot: object,
    receipt: object,
    original_context: HostBuildContext,
) -> HostBuildContext:
    """Reuse v0.2 selection and add only the frozen Nasdaq SRO date case."""
    prepared = _retain_unknown_context_v0_2(snapshot, receipt, original_context)
    if prepared.event_date_range is not None:
        return prepared
    selected_id = prepared.event_description_binding
    if type(selected_id) is not str:
        return prepared
    evidence = _preparation_evidence(snapshot, receipt, original_context)
    if evidence is None:
        return prepared
    envelope, verified_claim_ids, verified_binding_indices = evidence
    claims = envelope.get("claims")
    if type(claims) is not list:
        return prepared
    selected = [
        (index, claim)
        for index, claim in enumerate(claims)
        if type(claim) is dict
        and claim.get("claim_id") == selected_id
        and claim.get("kind") == "observed_fact"
        and selected_id in verified_claim_ids
    ]
    if len(selected) != 1:
        return prepared
    claim_index, claim = selected[0]
    source_id = claim.get("source_id")
    if type(source_id) is not str or claim.get("locator") is None:
        return prepared
    source = original_context.source_bodies.get(source_id)
    if type(source) is not HostSourceBody or claim.get("locator") != source.final_locator:
        return prepared
    occurrence = _resolve_sec_sro_approval_occurrence_date_v0_3(
        claim_index,
        claim,
        source,
        envelope,
        verified_binding_indices,
        original_context,
    )
    if occurrence is None:
        return prepared
    event_date, fields = occurrence
    methodology = json.dumps(
        {
            "rule_version": (
                "host-event-source-facts-v0.3/"
                "sec-sro-accelerated-approval-occurrence-date"
            ),
            "source_id": source_id,
            "body_sha256": source.body_sha256,
            "locator": source.final_locator,
            **fields,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return replace(
        prepared,
        event_date_range=MethodologizedDateRange(
            event_date, event_date, methodology
        ),
    )


_LISTING_TICKER = re.compile(r"[A-Z0-9]+(?:[.-][A-Z0-9]+)*\Z")
_LISTING_ASCII_CASEFOLD = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"
)
_LISTING_SEC_MARKER = "(Exact name of registrant as specified in its charter)"
_LISTING_SEC_LABELS = (
    "Title of each class",
    "Trading Symbol(s)",
    "Name of each exchange on which registered",
)
_LISTING_MD_SEPARATOR = re.compile(r":?-{3,}:?\Z")
_LISTING_NASDAQ_HEADING = re.compile(
    r"#{1,6} (?P<issuer>.+) Ordinary Shares \((?P<symbol>[^()]*)\)\Z"
)
_LISTING_YAHOO_HEADING = re.compile(
    r"# (?P<issuer>.+) \((?P<symbol>[^()]*)\)(?P<suffix>.*)\Z"
)
_LISTING_YAHOO_QUOTE = "NasdaqGS - Delayed Quote•USD"
_LISTING_SEC_PRIMARY_SHARE_CLASS = re.compile(
    r"Common Stock(?:, par value \$[0-9]+(?:\.[0-9]+)? per share)?\Z"
)
_LISTING_SEC_PRIMARY_EXCHANGE = "The Nasdaq Capital Market"
_LISTING_SEC_REFERENCE_LOCATOR = (
    "https://www.sec.gov/files/company_tickers_exchange.json"
)
_LISTING_YAHOO_V2_LABEL = "NasdaqCM - Nasdaq Real Time Price USD"
_LISTING_CURRENCY_BASIS = "yahoo_provider_reported_quote_denomination"


def _listing_lines(body: str):
    """Split only LF/CRLF while keeping zero-based code-point spans."""
    result = []
    start = 0
    while start < len(body):
        newline = body.find("\n", start)
        if newline < 0:
            end = len(body)
            next_start = end
        else:
            end = newline - 1 if newline > start and body[newline - 1] == "\r" else newline
            next_start = newline + 1
        result.append((body[start:end], start, end))
        if newline < 0:
            break
        start = next_start
    return result


def _listing_ascii_field(value: object):
    if type(value) is not str or any(
        (ord(char) < 0x20 and char != "\t") or ord(char) > 0x7E
        for char in value
    ):
        return None
    normalized = re.sub(r"[ \t]+", " ", value).strip(" \t")
    return normalized or None


def _listing_issuer(value: object):
    issuer = _listing_ascii_field(value)
    if issuer is None or any(char in issuer for char in "<>[]{}|`*_#"):
        return None
    return value


def _listing_markdown_cells(line: str):
    stripped = line.strip(" \t")
    if "|" not in stripped:
        return None
    cells = stripped.split("|")
    if cells and not cells[0].strip(" \t"):
        cells = cells[1:]
    if cells and not cells[-1].strip(" \t"):
        cells = cells[:-1]
    if len(cells) != 3:
        return None
    return tuple(cell.strip(" \t") for cell in cells)


def _listing_excerpt(source_id: str, source: HostSourceBody, start: int, end: int):
    text = source.body[start:end]
    return {
        "start": start,
        "end": end,
        "text": text,
        "sha256": hashlib.sha256(text.encode("utf-8", errors="strict")).hexdigest(),
    }


def _listing_url_info(locator: object):
    if type(locator) is not str or not locator or locator != locator.strip():
        return None
    if any(ord(char) <= 0x20 or ord(char) == 0x7F for char in locator):
        return None
    try:
        parsed = urlsplit(locator)
    except ValueError:
        return None
    host = parsed.hostname
    if host not in ("sec.gov", "www.sec.gov", "www.nasdaq.com", "finance.yahoo.com"):
        return None
    try:
        port = parsed.port
    except ValueError:
        port = -1
    expected_authority = (host, host + ":443")
    valid = (
        parsed.scheme.casefold() == "https"
        and parsed.username is None
        and parsed.password is None
        and port in (None, 443)
        and parsed.netloc.casefold() in expected_authority
        and "?" not in locator
        and "#" not in locator
        and not parsed.query
        and not parsed.fragment
        and parsed.path.isascii()
        and "%" not in parsed.path
        and "\\" not in parsed.path
        and "//" not in parsed.path
        and all(segment not in (".", "..") for segment in parsed.path.split("/"))
    )
    return {
        "host": host,
        "path": parsed.path,
        "origin": "{}://{}".format(parsed.scheme, parsed.netloc),
        "valid": valid,
    }


def _parse_sec_listing_body(source_id: str, source: HostSourceBody, symbol: str):
    lines = _listing_lines(source.body)
    markers = [index for index, item in enumerate(lines) if item[0] == _LISTING_SEC_MARKER]
    expected_labels = tuple(_listing_ascii_field(label).casefold() for label in _LISTING_SEC_LABELS)
    headers = []
    for index, (line, _start, _end) in enumerate(lines):
        cells = _listing_markdown_cells(line)
        if cells is not None and tuple(
            _listing_ascii_field(cell).casefold()
            if _listing_ascii_field(cell) is not None
            else None
            for cell in cells
        ) == expected_labels:
            headers.append((index, cells))

    target_row_seen = False
    parsed_rows = []
    for header_index, _cells in headers:
        separator_index = header_index + 1
        if separator_index >= len(lines):
            continue
        separator = _listing_markdown_cells(lines[separator_index][0])
        if separator is None or not all(_LISTING_MD_SEPARATOR.fullmatch(cell) for cell in separator):
            continue
        rows = []
        cursor = separator_index + 1
        malformed = False
        while cursor < len(lines):
            line = lines[cursor][0]
            if not line.strip(" \t") or "|" not in line:
                break
            cells = _listing_markdown_cells(line)
            if cells is None:
                malformed = True
                break
            if _listing_ascii_field(cells[1]) == symbol:
                target_row_seen = True
            rows.append((cursor, cells))
            cursor += 1
        if not malformed and len(rows) == 1:
            parsed_rows.append((header_index, separator_index, rows[0]))

    issuer = None
    issuer_index = None
    if len(markers) == 1:
        issuer_index = markers[0] - 1
        while issuer_index >= 0 and not lines[issuer_index][0].strip(" \t"):
            issuer_index -= 1
        if issuer_index >= 0:
            issuer = _listing_issuer(lines[issuer_index][0])

    if (
        len(markers) != 1
        or issuer is None
        or len(headers) != 1
        or len(parsed_rows) != 1
    ):
        return None, target_row_seen

    header_index, separator_index, (row_index, row) = parsed_rows[0]
    class_name = _listing_ascii_field(row[0])
    row_symbol = _listing_ascii_field(row[1])
    exchange = _listing_ascii_field(row[2])
    target_row_seen = target_row_seen or row_symbol == symbol
    if (
        class_name != "Ordinary shares, no par value"
        or row_symbol != symbol
        or exchange != "The Nasdaq Stock Market LLC"
    ):
        return None, target_row_seen

    if issuer_index is None or issuer_index < 0:
        return None, target_row_seen
    spans = [
        _listing_excerpt(source_id, source, lines[issuer_index][1], lines[issuer_index][2]),
        _listing_excerpt(source_id, source, lines[markers[0]][1], lines[markers[0]][2]),
        _listing_excerpt(source_id, source, lines[header_index][1], lines[header_index][2]),
        _listing_excerpt(source_id, source, lines[separator_index][1], lines[separator_index][2]),
        _listing_excerpt(source_id, source, lines[row_index][1], lines[row_index][2]),
    ]
    return {
        "role": "sec_listing_class",
        "source_id": source_id,
        "locator": source.final_locator,
        "origin": "https://{}".format(urlsplit(source.final_locator).netloc),
        "body_sha256": hashlib.sha256(source.body.encode("utf-8", errors="strict")).hexdigest(),
        "issuer": issuer,
        "share_class": row[0],
        "symbol": row_symbol,
        "registered_exchange": row[2],
        "excerpts": spans,
    }, target_row_seen


def _nasdaq_listing_path(info: dict, symbol: str):
    if info["host"] != "www.nasdaq.com":
        return False, False
    prefix = "/market-activity/stocks/{}".format(symbol.lower())
    path = info["path"]
    if path == prefix:
        return True, True
    if not path.startswith(prefix + "/"):
        return False, False
    suffix = path[len(prefix) + 1:]
    safe_segment = bool(re.fullmatch(r"[A-Za-z0-9._~-]+", suffix)) and suffix not in (".", "..")
    return True, safe_segment


def _parse_nasdaq_listing_body(source_id: str, source: HostSourceBody, symbol: str):
    lines = _listing_lines(source.body)
    instrument_headings = []
    for line, start, end in lines:
        if not re.match(r"^#{1,6} ", line) or "Ordinary Shares" not in line:
            continue
        instrument_headings.append((line, start, end))
    if len(instrument_headings) != 1:
        return None
    line, start, end = instrument_headings[0]
    match = _LISTING_NASDAQ_HEADING.fullmatch(line)
    if match is None:
        return None
    issuer = _listing_issuer(match.group("issuer"))
    observed_symbol = match.group("symbol")
    if issuer is None or not _LISTING_TICKER.fullmatch(observed_symbol) or observed_symbol != symbol:
        return None
    info = _listing_url_info(source.final_locator)
    return {
        "role": "nasdaq_instrument_heading",
        "source_id": source_id,
        "locator": source.final_locator,
        "origin": "https://{}".format(urlsplit(source.final_locator).netloc),
        "body_sha256": hashlib.sha256(source.body.encode("utf-8", errors="strict")).hexdigest(),
        "issuer": issuer,
        "share_class": "Ordinary Shares",
        "symbol": observed_symbol,
        "excerpts": [_listing_excerpt(source_id, source, start, end)],
    }


def _yahoo_listing_path(info: dict, symbol: str):
    if info["host"] != "finance.yahoo.com":
        return False, False
    exact = "/quote/{}/".format(symbol)
    prefix = "/quote/{}".format(symbol)
    path = info["path"]
    if path == exact:
        return True, True
    if path == prefix or path.startswith(prefix + "/"):
        return True, False
    return False, False


def _parse_yahoo_listing_body(source_id: str, source: HostSourceBody, symbol: str):
    lines = _listing_lines(source.body)
    quote_headers = [
        (index, line, start, end)
        for index, (line, start, end) in enumerate(lines)
        if "quote" in line.translate(_LISTING_ASCII_CASEFOLD)
    ]
    instrument_headings = []
    for index, (line, start, end) in enumerate(lines):
        match = _LISTING_YAHOO_HEADING.fullmatch(line)
        if match is not None:
            instrument_headings.append((index, match, start, end))
    if len(quote_headers) != 1 or len(instrument_headings) != 1:
        return None
    quote_index, quote_line, quote_start, quote_end = quote_headers[0]
    heading_index, match, heading_start, heading_end = instrument_headings[0]
    if (
        quote_line != _LISTING_YAHOO_QUOTE
        or match.group("suffix")
        or not _LISTING_TICKER.fullmatch(match.group("symbol"))
        or match.group("symbol") != symbol
    ):
        return None
    next_nonblank = quote_index + 1
    while next_nonblank < len(lines) and not lines[next_nonblank][0].strip(" \t"):
        next_nonblank += 1
    issuer = _listing_issuer(match.group("issuer"))
    if issuer is None or next_nonblank != heading_index:
        return None
    info = _listing_url_info(source.final_locator)
    return {
        "role": "yahoo_quote_denomination",
        "source_id": source_id,
        "locator": source.final_locator,
        "origin": "https://{}".format(urlsplit(source.final_locator).netloc),
        "body_sha256": hashlib.sha256(source.body.encode("utf-8", errors="strict")).hexdigest(),
        "issuer": issuer,
        "symbol": match.group("symbol"),
        "currency": "USD",
        "currency_basis": _LISTING_CURRENCY_BASIS,
        "excerpts": [
            _listing_excerpt(source_id, source, quote_start, quote_end),
            _listing_excerpt(source_id, source, heading_start, heading_end),
        ],
    }


def _parse_sec_primary_cover(
    source_id: str,
    source: HostSourceBody,
    symbol: str,
    cik: int,
    admission: SourceAdmission,
):
    if (
        type(admission) is not SourceAdmission
        or admission.source_id != source_id
        or admission.parser_id != "sec-edgar-cover-layout-v4"
        or admission.parser_version != "4"
        or admission.parsed_body != source.body
        or admission.parsed_body_sha256 != source.body_sha256
    ):
        return None
    info = _listing_url_info(source.final_locator)
    parts = _sec_locator_parts(source.final_locator)
    if (
        info is None
        or not info["valid"]
        or info["host"] not in ("sec.gov", "www.sec.gov")
        or parts is None
        or int(parts[0]) != cik
    ):
        return None
    lines = _listing_lines(source.body)
    issuer_anchors = tuple(
        anchor for anchor in admission.raw_anchors
        if anchor.field == "sec_cover.registrant"
    )
    marker_anchors = tuple(
        anchor for anchor in admission.raw_anchors
        if anchor.field == "sec_cover.registrant_marker"
    )
    if len(issuer_anchors) != 1 or len(marker_anchors) != 1:
        return None
    issuer_anchor, marker_anchor = issuer_anchors[0], marker_anchors[0]
    if any(
        not 0 <= anchor.parsed_start < anchor.parsed_end <= len(source.body)
        for anchor in (issuer_anchor, marker_anchor)
    ):
        return None
    issuer_text = _sec_cover_layout_v4_fold(
        source.body[issuer_anchor.parsed_start:issuer_anchor.parsed_end]
    )
    marker_text = _sec_cover_layout_v4_fold(
        source.body[marker_anchor.parsed_start:marker_anchor.parsed_end]
    )
    issuer = _listing_issuer(issuer_text)
    if issuer is None or marker_text != _LISTING_SEC_MARKER:
        return None
    expected_labels = tuple(_listing_ascii_field(label).translate(
        _LISTING_ASCII_CASEFOLD
    ) for label in _LISTING_SEC_LABELS)
    headers = []
    for index, (line, _start, _end) in enumerate(lines):
        cells = _listing_markdown_cells(line)
        if cells is not None and tuple(
            _listing_ascii_field(cell).translate(_LISTING_ASCII_CASEFOLD)
            if _listing_ascii_field(cell) is not None else None
            for cell in cells
        ) == expected_labels:
            headers.append(index)
    if len(headers) != 1:
        return None
    header_index = headers[0]
    separator_index = header_index + 1
    if separator_index >= len(lines):
        return None
    separator = _listing_markdown_cells(lines[separator_index][0])
    if separator is None or not all(
        _LISTING_MD_SEPARATOR.fullmatch(cell) for cell in separator
    ):
        return None
    rows = []
    cursor = separator_index + 1
    while cursor < len(lines) and lines[cursor][0].strip(" \t") and "|" in lines[cursor][0]:
        row = _listing_markdown_cells(lines[cursor][0])
        if row is None:
            return None
        rows.append((cursor, row))
        cursor += 1
    if len(rows) != 1:
        return None
    row_index, row = rows[0]
    share_class, row_symbol, exchange = row
    if (
        issuer is None
        or row_symbol != symbol
        or not _LISTING_SEC_PRIMARY_SHARE_CLASS.fullmatch(share_class)
        or exchange != _LISTING_SEC_PRIMARY_EXCHANGE
    ):
        return None
    excerpts = [
        _listing_excerpt(
            source_id, source, issuer_anchor.parsed_start, issuer_anchor.parsed_end
        ),
        _listing_excerpt(
            source_id, source, marker_anchor.parsed_start, marker_anchor.parsed_end
        ),
        *(
            _listing_excerpt(source_id, source, lines[index][1], lines[index][2])
            for index in (header_index, separator_index, row_index)
        ),
    ]
    return {
        "role": "sec_cover_security_class",
        "source_id": source_id,
        "locator": source.final_locator,
        "origin": info["origin"],
        "body_sha256": hashlib.sha256(source.body.encode("utf-8", errors="strict")).hexdigest(),
        "issuer": issuer,
        "share_class": share_class,
        "symbol": row_symbol,
        "registered_exchange": exchange,
        "security_class_authority": "SEC cover row",
        "excerpts": excerpts,
    }


def _parse_sec_reference_selected(
    source_id: str, source: HostSourceBody, admission: SourceAdmission, symbols: tuple
):
    if source.final_locator != _LISTING_SEC_REFERENCE_LOCATOR:
        return None
    try:
        document = json.loads(source.body)
    except (TypeError, ValueError, RecursionError):
        return None
    if (
        type(document) is not dict
        or set(document) != {"fields", "data"}
        or document.get("fields") != ["cik", "name", "ticker", "exchange"]
        or type(document.get("data")) is not list
        or len(document["data"]) != len(symbols)
    ):
        return None
    parsed_rows = []
    for row in document["data"]:
        if (
            type(row) is not list
            or len(row) != 4
            or type(row[0]) is not int
            or not 0 < row[0] < 10**10
            or type(row[1]) is not str
            or type(row[2]) is not str
            or type(row[3]) is not str
        ):
            return None
        parsed_rows.append(row)
    if tuple(row[2] for row in parsed_rows) != symbols:
        return None
    anchor_by_symbol = {
        anchor.field.removeprefix("sec_issuer_reference.data."): anchor
        for anchor in admission.raw_anchors
        if anchor.field.startswith("sec_issuer_reference.data.")
    }
    if len(anchor_by_symbol) != len(symbols):
        return None
    result = {}
    for row in parsed_rows:
        symbol = row[2]
        anchor = anchor_by_symbol.get(symbol)
        try:
            anchored_row = json.loads(
                source.body[anchor.parsed_start:anchor.parsed_end]
            ) if anchor is not None else None
        except (TypeError, ValueError, RecursionError):
            return None
        if anchor is None or anchored_row != row:
            return None
        result[symbol] = (
            row,
            _listing_excerpt(
                source_id, source, anchor.parsed_start, anchor.parsed_end
            ),
        )
    return result


def _parse_yahoo_listing_body_v2(source_id: str, source: HostSourceBody, symbol: str):
    lines = _listing_lines(source.body)
    labels = [(index, start, end) for index, (line, start, end) in enumerate(lines)
              if re.sub(r"[ \t]+", " ", line).strip(" \t") == _LISTING_YAHOO_V2_LABEL]
    headings = []
    for index, (line, start, end) in enumerate(lines):
        match = re.fullmatch(r"# (?P<issuer>.+) \((?P<symbol>[^()]*)\)", line)
        if match is not None and match.group("symbol") == symbol:
            headings.append((index, match, start, end))
    if len(labels) != 1 or len(headings) != 1:
        return None
    label_index, label_start, label_end = labels[0]
    heading_index, match, heading_start, heading_end = headings[0]
    low, high = sorted((label_index, heading_index))
    if label_index == heading_index or any(
        lines[index][0].strip(" \t") for index in range(low + 1, high)
    ):
        return None
    issuer = _listing_issuer(match.group("issuer"))
    if issuer is None or not _LISTING_TICKER.fullmatch(match.group("symbol")):
        return None
    return {
        "role": "yahoo_quote_denomination",
        "source_id": source_id,
        "locator": source.final_locator,
        "origin": "https://{}".format(urlsplit(source.final_locator).netloc),
        "body_sha256": hashlib.sha256(source.body.encode("utf-8", errors="strict")).hexdigest(),
        "issuer": issuer,
        "symbol": symbol,
        "currency": "USD",
        "currency_basis": _LISTING_CURRENCY_BASIS,
        "excerpts": [
            _listing_excerpt(source_id, source, label_start, label_end),
            _listing_excerpt(source_id, source, heading_start, heading_end),
        ],
    }


def _listing_sec_primary_evidence(
    context: HostBuildContext,
    records: tuple,
    symbols: tuple,
    symbol: str,
):
    if type(records) is not tuple or type(symbols) is not tuple or symbol not in symbols:
        return None
    count = len(symbols)
    if len(records) != count * 2 + 1:
        return None
    cover_records = records[:count]
    reference = records[count]
    yahoo_records = records[count + 1:]
    covers = [record for record in cover_records if record.parsed_symbol == symbol]
    yahoos = [record for record in yahoo_records if record.parsed_symbol == symbol]
    if (
        len(covers) != 1
        or len(yahoos) != 1
        or reference.parser_id != "sec-issuer-reference-v2"
        or reference.parser_version != "2"
        or reference.family != "sec"
    ):
        return None
    cover_record = covers[0]
    yahoo_record = yahoos[0]
    if (
        cover_record.parser_id != "sec-edgar-cover-layout-v4"
        or cover_record.parser_version != "4"
        or yahoo_record.parser_id != "yahoo-quote-header-v2"
        or yahoo_record.parser_version != "2"
    ):
        return None
    source_by_record = {}
    for record in (reference, cover_record, yahoo_record):
        source = context.source_bodies.get(record.source_id)
        if (
            type(source) is not HostSourceBody
            or source.body != record.parsed_body
            or source.body_sha256 != record.parsed_body_sha256
            or source.final_locator != record.final_locator
            or source.retrieved_at != record.retrieved_at
        ):
            return None
        source_by_record[record.source_id] = source
    reference_source = source_by_record[reference.source_id]
    reference_rows = _parse_sec_reference_selected(
        reference.source_id, reference_source, reference, symbols
    )
    if reference_rows is None:
        return None
    reference_row, reference_excerpt = reference_rows[symbol]
    cik, reference_name, reference_symbol, reference_exchange = reference_row
    if reference_symbol != symbol or reference_exchange != "Nasdaq":
        return None
    cover_source = source_by_record[cover_record.source_id]
    cover = _parse_sec_primary_cover(
        cover_record.source_id, cover_source, symbol, cik, cover_record
    )
    yahoo_source = source_by_record[yahoo_record.source_id]
    yahoo = _parse_yahoo_listing_body_v2(yahoo_record.source_id, yahoo_source, symbol)
    if cover is None or yahoo is None:
        return None
    cover_issuer = _listing_ascii_field(cover["issuer"])
    yahoo_issuer = _listing_ascii_field(yahoo["issuer"])
    if (
        cover_issuer is None
        or yahoo_issuer is None
        or cover_issuer.translate(_LISTING_ASCII_CASEFOLD)
        != yahoo_issuer.translate(_LISTING_ASCII_CASEFOLD)
    ):
        return None
    reference_evidence = {
        "role": "sec_issuer_reference",
        "source_id": reference.source_id,
        "locator": reference.final_locator,
        "origin": reference.origin,
        "body_sha256": reference.parsed_body_sha256,
        "cik": cik,
        "issuer_name": reference_name,
        "symbol": symbol,
        "exchange": reference_exchange,
        "excerpts": [reference_excerpt],
    }
    return reference_evidence, cover, yahoo


def _listing_evidence_for_symbol(
    context: HostBuildContext, authorized_source_ids: tuple, symbol: str
):
    sec_sources = []
    nasdaq_sources = []
    yahoo_sources = []
    conflict = False
    for source_id in authorized_source_ids:
        source = context.source_bodies.get(source_id)
        if type(source) is not HostSourceBody:
            continue
        info = _listing_url_info(source.final_locator)
        if info is None:
            continue
        if info["host"] in ("sec.gov", "www.sec.gov") and info["path"].startswith(
            "/Archives/edgar/data/"
        ):
            parsed, target_row_seen = _parse_sec_listing_body(source_id, source, symbol)
            locator_valid = _sec_locator_parts(source.final_locator) is not None and info["valid"]
            if target_row_seen and (parsed is None or not locator_valid):
                conflict = True
            elif parsed is not None and parsed["symbol"] == symbol:
                if locator_valid:
                    sec_sources.append(parsed)
                else:
                    conflict = True
        elif info["host"] == "www.nasdaq.com":
            target_path, suffix_valid = _nasdaq_listing_path(info, symbol)
            if target_path:
                parsed = _parse_nasdaq_listing_body(source_id, source, symbol)
                if not info["valid"] or not suffix_valid or parsed is None:
                    conflict = True
                else:
                    nasdaq_sources.append(parsed)
        elif info["host"] == "finance.yahoo.com":
            target_path, path_valid = _yahoo_listing_path(info, symbol)
            if target_path:
                parsed = _parse_yahoo_listing_body(source_id, source, symbol)
                if not info["valid"] or not path_valid or parsed is None:
                    conflict = True
                else:
                    yahoo_sources.append(parsed)

    if conflict or not (
        len(sec_sources) == len(nasdaq_sources) == len(yahoo_sources) == 1
    ):
        return None
    evidence = (sec_sources[0], nasdaq_sources[0], yahoo_sources[0])
    issuers = tuple(_listing_ascii_field(item["issuer"]).casefold() for item in evidence)
    if len(set(issuers)) != 1:
        return None
    return evidence


def _make_listing_source_preparer(
    authorized_source_ids: tuple,
    *,
    admission_records: tuple = (),
    sec_composite=None,
    _event_fact_anchor_capture: Optional[list] = None,
) -> Callable[[object, object, HostBuildContext], HostBuildContext]:
    """Create an opt-in preparer over an exact, trusted source-ID tuple."""
    if type(authorized_source_ids) is not tuple:
        raise TypeError("authorized_source_ids must be an exact tuple")
    if any(
        type(source_id) is not str
        or not source_id
        or source_id != source_id.strip()
        for source_id in authorized_source_ids
    ):
        raise ValueError("authorized_source_ids must contain canonical nonempty IDs")
    try:
        for source_id in authorized_source_ids:
            source_id.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise ValueError("authorized_source_ids must contain valid UTF-8 IDs") from None
    if len(set(authorized_source_ids)) != len(authorized_source_ids):
        raise ValueError("authorized_source_ids must be unique")
    if type(admission_records) is not tuple or any(
        type(item) is not SourceAdmission for item in admission_records
    ):
        raise TypeError("admission_records must be a tuple of successful Host admissions")
    if _event_fact_anchor_capture is not None and type(_event_fact_anchor_capture) is not list:
        raise TypeError("private event fact-anchor capture must be an exact list")
    admission_by_id = {item.source_id: item for item in admission_records}
    if (
        len(admission_by_id) != len(admission_records)
        or any(source_id not in authorized_source_ids for source_id in admission_by_id)
    ):
        raise ValueError("admission records must match the exact authorized source IDs")
    if sec_composite is not None and (
        type(sec_composite) is not tuple
        or len(sec_composite) != 5
        or type(sec_composite[0]) is not _SourceAdmissionClient
        or type(sec_composite[1]) is not tuple
        or not sec_composite[1]
        or type(sec_composite[2]) is not tuple
        or type(sec_composite[3]) is not int
        or type(sec_composite[4]) is not int
        or any(record.source_id not in admission_by_id for record in sec_composite[2])
    ):
        raise ValueError("SEC composite must retain its issuing client receipt")
    if sec_composite is not None and (
        len(sec_composite[2]) != len(sec_composite[1]) * 2 + 1
        or len(set(sec_composite[1])) != len(sec_composite[1])
    ):
        raise ValueError("SEC composite selection is incomplete")
    listing_source_ids = tuple(
        source_id
        for source_id in authorized_source_ids
        if not (
            source_id in admission_by_id
            and admission_by_id[source_id].parser_id
            in ("sec-edgar-cover-layout-v3", "sec-edgar-cover-layout-v4")
        )
    )

    def prepare_listing_sources(
        snapshot: object, receipt: object, original_context: HostBuildContext
    ) -> HostBuildContext:
        if _event_fact_anchor_capture is None:
            prepared = _retain_unknown_context_v0_3(snapshot, receipt, original_context)
            if prepared.event_date_range is None:
                prepared = _retain_unknown_context_v0_4(
                    snapshot, receipt, original_context, prepared, admission_by_id
                )
        else:
            prepared, selected_claim_id = _retain_unknown_context_v0_5(
                snapshot, receipt, original_context, admission_by_id
            )
            _event_fact_anchor_capture.append(
                _EventFactAnchorOutcome(
                    (_SUBQUESTION_ID, _EVENT_FACT_ANCHOR_SUBQUESTION_ID),
                    original_context.event_description_binding,
                    selected_claim_id,
                )
            )
        if not listing_source_ids:
            return prepared
        composite_records = ()
        composite_symbols = ()
        if sec_composite is not None:
            composite_client, composite_symbols, issued_records, max_raw, max_parsed = sec_composite
            composite_records = _SourceAdmissionClient._revalidate_sec_composite(
                composite_client,
                issued_records,
                composite_symbols,
                max_raw_bytes=max_raw,
                max_parsed_bytes=max_parsed,
            )
            if composite_records is None:
                return prepared
        validation = _preparation_evidence(snapshot, receipt, original_context)
        if validation is None or type(receipt) is not _RECEIPT_MAPPING_TYPE:
            return prepared
        envelope, _verified_claim_ids, verified_binding_indices = validation
        verified_hypothesis_ids = receipt.get("verified_hypothesis_ids")
        hypotheses = envelope.get("hypotheses")
        field_bindings = envelope.get("field_bindings")
        if (
            type(verified_hypothesis_ids) is not tuple
            or any(type(value) is not str or not value for value in verified_hypothesis_ids)
            or len(set(verified_hypothesis_ids)) != len(verified_hypothesis_ids)
            or type(hypotheses) is not list
            or type(field_bindings) is not list
        ):
            return prepared

        verified_hypothesis_set = frozenset(verified_hypothesis_ids)
        bindings = dict(prepared.underlying_bindings)
        changed = False
        evidence_by_symbol = {}
        for hypothesis_index, hypothesis in enumerate(hypotheses):
            if type(hypothesis) is not dict:
                continue
            hypothesis_id = hypothesis.get("hypothesis_id")
            symbol = hypothesis.get("underlying_symbol")
            if (
                type(hypothesis_id) is not str
                or hypothesis_id not in verified_hypothesis_set
                or type(symbol) is not str
                or not _LISTING_TICKER.fullmatch(symbol)
            ):
                continue
            pair = (hypothesis_id, symbol)
            if pair in bindings:
                continue
            expected_path = "/hypotheses/{}/underlying_symbol".format(hypothesis_index)
            matching = [
                (index, item)
                for index, item in enumerate(field_bindings)
                if type(item) is dict and item.get("field_path") == expected_path
            ]
            if (
                len(matching) != 1
                or matching[0][1].get("semantic_role") != "entity"
                or matching[0][0] not in verified_binding_indices
            ):
                continue
            if sec_composite is not None and symbol in composite_symbols:
                if symbol not in evidence_by_symbol:
                    evidence_by_symbol[symbol] = _listing_sec_primary_evidence(
                        original_context, composite_records, composite_symbols, symbol
                    )
                evidence = evidence_by_symbol[symbol]
                if evidence is None:
                    continue
                reference_source, cover_evidence, yahoo_evidence = evidence
                source_evidence_items = (reference_source, cover_evidence, yahoo_evidence)
                rule_version = "host-listing-source-composite-v0.2"
            else:
                if symbol not in evidence_by_symbol:
                    evidence_by_symbol[symbol] = _listing_evidence_for_symbol(
                        original_context, listing_source_ids, symbol
                    )
                evidence = evidence_by_symbol[symbol]
                if evidence is None:
                    continue
                sec_evidence, nasdaq_evidence, yahoo_evidence = evidence
                source_evidence_items = (sec_evidence, nasdaq_evidence, yahoo_evidence)
                rule_version = "host-listing-source-composite-v0.1"
            admission_mismatch = False
            for source_evidence in source_evidence_items:
                admission = admission_by_id.get(source_evidence["source_id"])
                if admission is not None:
                    if (
                        admission.final_locator != source_evidence["locator"]
                        or admission.parsed_body_sha256 != source_evidence["body_sha256"]
                    ):
                        admission_mismatch = True
                        break
                    source_evidence["source_admission"] = admission.provenance()
            if admission_mismatch:
                continue
            reference = json.dumps(
                {
                    "rule_version": rule_version,
                    "symbol": symbol,
                    "security_type": "EQUITY",
                    "listing_mic": None,
                    "currency": "USD",
                    "currency_basis": _LISTING_CURRENCY_BASIS,
                    "sources": list(source_evidence_items),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            bindings[pair] = (
                UnderlyingKey(symbol, None, UnderlyingSecurityType.EQUITY, "USD"),
                reference,
            )
            changed = True
        return replace(prepared, underlying_bindings=bindings) if changed else prepared

    return prepare_listing_sources


def _sec_locator_parts(locator: object):
    """Return exact SEC archive path identity, rejecting URL/path ambiguity."""
    if type(locator) is not str or not locator or locator != locator.strip():
        return None
    try:
        parsed = urlsplit(locator)
        port = parsed.port
    except ValueError:
        return None
    hostname = parsed.hostname
    if (
        parsed.scheme.casefold() != "https"
        or hostname not in ("sec.gov", "www.sec.gov")
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or "?" in locator
        or "#" in locator
        or parsed.query
        or parsed.fragment
        or "\\" in parsed.path
        or "%" in parsed.path
    ):
        return None
    expected_authority = hostname if port is None else "{}:443".format(hostname)
    if parsed.netloc.casefold() != expected_authority:
        return None
    match = _SEC_EDGAR_LOCATOR.fullmatch(parsed.path)
    if match is None:
        return None
    return match.group("cik"), match.group("accession")


def _sec_submission_header(body: str, locator_parts):
    """Require one consistent set of explicit SEC submission-header fields."""
    if locator_parts is None:
        return None
    values = {}
    for key, label in _SEC_HEADER_LABELS.items():
        label_occurrences = tuple(
            re.finditer(
                r"(?im)^[ \t]*" + re.escape(label) + r"[ \t]*:", body
            )
        )
        if len(label_occurrences) != 1:
            return None
        matches = re.findall(
            r"(?m)^[ \t]*" + re.escape(label) + r":[ \t]*([^\r\n]*)[ \t]*$",
            body,
        )
        if len(matches) != 1:
            return None
        value = matches[0].strip()
        if not value:
            return None
        values[key] = value
    if (
        values["form"] != "8-K"
        or _SEC_ACCESSION.fullmatch(values["accession"]) is None
        or _SEC_CIK.fullmatch(values["cik"]) is None
    ):
        return None
    locator_cik, locator_accession = locator_parts
    header_cik = values["cik"]
    path_accession = locator_accession.replace("-", "")
    header_accession = values["accession"].replace("-", "")
    if (
        int(locator_cik) == 0
        or int(locator_cik) != int(header_cik)
        or path_accession != header_accession
    ):
        return None
    return values["registrant"]


def _resolve_sec_occurrence_date(
    claim_index: int,
    claim: dict,
    source: HostSourceBody,
    envelope: dict,
    verified_binding_indices: frozenset,
    context: HostBuildContext,
):
    """Retain the historical v0.1 completed-action occurrence grammar."""
    occurrence = _resolve_sec_occurrence_date_with_verbs(
        claim_index,
        claim,
        source,
        envelope,
        verified_binding_indices,
        context,
        _ACTION_VERB,
    )
    return None if occurrence is None else occurrence[:3]


def _resolve_sec_occurrence_date_v0_2(
    claim_index: int,
    claim: dict,
    source: HostSourceBody,
    envelope: dict,
    verified_binding_indices: frozenset,
    context: HostBuildContext,
):
    """Use the shared SEC guards with v0.2's narrow announced verb addition."""
    return _resolve_sec_occurrence_date_with_verbs(
        claim_index,
        claim,
        source,
        envelope,
        verified_binding_indices,
        context,
        _ACTION_VERB_V0_2,
    )


def _ascii_whitespace_fold(value: str) -> str:
    return _SRO_ASCII_WS_RUN.sub(" ", value).strip(" ")


def _sro_date_token_value(match):
    try:
        if match.group("iso") is not None:
            return datetime.date.fromisoformat(match.group("iso"))
        month = _SRO_MONTH_NUMBERS[match.group("month").rstrip(".").casefold()]
        return datetime.date(int(match.group("year")), month, int(match.group("day")))
    except (KeyError, TypeError, ValueError):
        return None


def _resolve_sec_sro_approval_occurrence_date_v0_3(
    claim_index: int,
    claim: dict,
    source: HostSourceBody,
    envelope: dict,
    verified_binding_indices: frozenset,
    context: HostBuildContext,
):
    """Resolve only the frozen SEC Nasdaq accelerated-approval order grammar."""
    locator = _SRO_LOCATOR.fullmatch(source.final_locator)
    if locator is None:
        return None
    body = source.body
    sec_headings = tuple(_SRO_SEC_HEADING.finditer(body))
    release_files = tuple(_SRO_RELEASE_FILE.finditer(body))
    sro_headings = tuple(_SRO_IDENTITY_HEADING.finditer(body))
    titles = tuple(_SRO_TITLE.finditer(body))
    if not (
        len(sec_headings) == len(release_files) == len(sro_headings) == len(titles) == 1
    ):
        return None

    sec_heading = sec_headings[0]
    release_file = release_files[0]
    sro_heading = sro_headings[0]
    title = titles[0]
    cover_date_match = _SRO_COVER_DATE.match(body, title.end())
    if (
        not sec_heading.start() < release_file.start() < sro_heading.start() < title.start()
        or cover_date_match is None
    ):
        return None
    title_prefix = _ascii_whitespace_fold(body[sro_heading.end():title.start()])
    if title_prefix and _SRO_AMENDMENT_NOTICE_PREFIX.fullmatch(title_prefix) is None:
        return None
    release_no = release_file.group("release")
    file_no = release_file.group("file")
    if (
        release_no != "34-" + locator.group("release")
        or locator.group("year") != cover_date_match.group("year")
    ):
        return None
    try:
        cover_date = datetime.date(
            int(cover_date_match.group("year")),
            _SRO_MONTH_NUMBERS[cover_date_match.group("month").casefold()],
            int(cover_date_match.group("day")),
        )
    except (KeyError, ValueError):
        return None

    cover_start = sec_heading.start()
    cover_end = cover_date_match.end()
    cover_date_span = cover_date_match.span("token")
    if any(
        not (cover_start <= label.start() < cover_end)
        for label in _SRO_DATE_LABEL.finditer(body)
    ):
        return None
    if _SRO_COVER_STATUS_LABEL.search(body[cover_start:cover_end]) is not None:
        return None

    prior_date_spans = []
    previous_end = -1
    cover_token_count = 0
    for date_match in _SRO_DATE_TOKEN.finditer(body):
        token_start, token_end = date_match.span()
        if token_start < previous_end:
            return None
        previous_end = token_end
        parsed_date = _sro_date_token_value(date_match)
        if parsed_date is None:
            return None
        if (token_start, token_end) == cover_date_span:
            cover_token_count += 1
        elif parsed_date >= cover_date:
            return None
        else:
            prior_date_spans.append((token_start, token_end))
    if cover_token_count != 1:
        return None

    paragraphs = tuple(_line_paragraph_spans(body))
    order_starts = tuple(_SRO_ORDER_START.finditer(body))
    approval_ends = tuple(_SRO_APPROVAL_END.finditer(body))
    signatures = tuple(_SRO_SIGNATURE.finditer(body))
    if len(order_starts) != 1 or len(approval_ends) != 1 or len(signatures) != 1:
        return None
    order_start = order_starts[0]
    approval_end = approval_ends[0]
    signature = signatures[0]
    order_paragraph = next(
        (
            span
            for span in paragraphs
            if span[0] <= order_start.start() < span[1]
        ),
        None,
    )
    if order_paragraph is None:
        return None
    paragraph_start, paragraph_end = order_paragraph
    if (
        body[paragraph_start:order_start.start()].strip(" \t\r\n\f\v")
        or not order_start.end() <= approval_end.start() < approval_end.end() <= paragraph_end
        or not approval_end.end() <= signature.start()
        or body[approval_end.end():paragraph_end].strip(" \t\r\n\f\v")
        or body[paragraph_end:signature.start()].strip(" \t\r\n\f\v")
    ):
        return None
    clause_start, clause_end = order_start.start(), approval_end.end()
    clause = body[clause_start:clause_end]
    file_reference = re.compile(
        r"the" + _SRO_ASCII_WS + r"+proposed" + _SRO_ASCII_WS
        + r"+rule" + _SRO_ASCII_WS + r"+change" + _SRO_ASCII_WS
        + r"*\(" + re.escape(file_no) + r"\)"
    )
    if (
        len(tuple(file_reference.finditer(clause))) != 1
        or _SRO_NONOPERATIVE.search(clause) is not None
    ):
        return None

    claim_quote = claim.get("quote")
    claim_text = claim.get("text")
    if type(claim_quote) is not str or not claim_quote or type(claim_text) is not str:
        return None
    claim_start = body.find(claim_quote)
    if (
        claim_start < 0
        or body.find(claim_quote, claim_start + 1) >= 0
        or (claim_start, claim_start + len(claim_quote)) not in paragraphs
        or not (
            claim_start <= clause_start
            and clause_end <= claim_start + len(claim_quote)
        )
    ):
        return None
    canonical_claim = (
        "The Securities and Exchange Commission approved the proposed rule "
        "change ({}) on an accelerated basis.".format(file_no)
    )
    folded_claim = _ascii_whitespace_fold(claim_text)
    if folded_claim not in (
        _ascii_whitespace_fold(clause),
        _ascii_whitespace_fold(canonical_claim),
    ):
        return None

    model_date = claim.get("event_date")
    if (
        type(model_date) is not str
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", model_date) is None
        or model_date != cover_date.isoformat()
        or cover_date > context.observed_at.astimezone(datetime.timezone.utc).date()
    ):
        return None

    field_bindings = envelope.get("field_bindings")
    if type(field_bindings) is not list:
        return None
    field_path = "/claims/{}/event_date".format(claim_index)
    matching = tuple(
        (index, binding)
        for index, binding in enumerate(field_bindings)
        if type(binding) is dict and binding.get("field_path") == field_path
    )
    if len(matching) != 1:
        return None
    binding_index, binding = matching[0]
    binding_start = binding.get("start")
    binding_end = binding.get("end")
    binding_quote = binding.get("quote")
    if (
        binding_index not in verified_binding_indices
        or binding.get("source_id") != claim.get("source_id")
        or binding.get("status") != "supported"
        or binding.get("semantic_role") != "date"
        or type(binding_start) is not int
        or type(binding_end) is not int
        or type(binding_quote) is not str
        or binding_start < 0
        or binding_end <= binding_start
        or binding_end > len(body)
        or body[binding_start:binding_end] != binding_quote
        or (binding_start, binding_end) not in paragraphs
        or body.find(binding_quote) != binding_start
        or body.find(binding_quote, binding_start + 1) >= 0
        or not (binding_start <= cover_date_span[0] < cover_date_span[1] <= binding_end)
    ):
        return None

    return cover_date, {
        "release_no": release_no,
        "file_no": file_no,
        "sro_name": "The Nasdaq Stock Market LLC",
        "event_date": cover_date.isoformat(),
        "cover_date_quote": body[slice(*cover_date_span)],
        "cover_date_start": cover_date_span[0],
        "cover_date_end": cover_date_span[1],
        "prior_date_spans": prior_date_spans,
        "claim_quote": claim_quote,
        "claim_start": claim_start,
        "claim_end": claim_start + len(claim_quote),
        "operative_clause_quote": clause,
        "operative_clause_start": clause_start,
        "operative_clause_end": clause_end,
        "binding_quote": binding_quote,
        "binding_start": binding_start,
        "binding_end": binding_end,
    }


def _resolve_sec_occurrence_date_with_verbs(
    claim_index: int,
    claim: dict,
    source: HostSourceBody,
    envelope: dict,
    verified_binding_indices: frozenset,
    context: HostBuildContext,
    action_verbs: str,
):
    """Resolve a dated SEC sentence only with exact source-bound receipt offsets."""
    locator_parts = _sec_locator_parts(source.final_locator)
    registrant = _sec_submission_header(source.body, locator_parts)
    if registrant is None or not registrant:
        return None
    sentence = claim.get("text")
    if type(sentence) is not str:
        return None
    sentence_pattern = re.compile(
        r"On (?P<month>" + _ENGLISH_MONTHS + r") "
        r"(?P<day>[0-9]{1,2}), (?P<year>[0-9]{4}), "
        + re.escape(registrant)
        + r" (?P<verb>" + action_verbs + r") (?P<act>[^.!?\r\n]+)\."
    )
    match = sentence_pattern.fullmatch(sentence)
    if match is None:
        return None
    start = source.body.find(sentence)
    if start < 0 or source.body.find(sentence, start + 1) >= 0:
        return None
    # Require the entire source body to contain only the candidate's explicit
    # date token; otherwise chronology is ambiguous, regardless of phrasing.
    date_tokens = tuple(_SOURCE_DATE_TOKEN.finditer(source.body))
    candidate_date_span = (
        start + match.start("month"),
        start + match.end("year"),
    )
    if len(date_tokens) != 1 or date_tokens[0].span() != candidate_date_span:
        return None

    act = match.group("act")
    if (
        len(act) > 240
        or _UNCERTAIN_ACTION.search(act) is not None
        or _SOURCE_DATE_TOKEN.search(act) is not None
        or re.search(
            r"\bto\s+(?:enter|complete|close|execute|sign|acquire|purchase|"
            r"sell|deliver|launch|begin|start)\b",
            act,
            re.IGNORECASE,
        )
    ):
        return None
    month = _ENGLISH_MONTH_NUMBERS.get(match.group("month"))
    if month is None:
        return None
    try:
        event_date = datetime.date(
            int(match.group("year")), month, int(match.group("day"))
        )
    except ValueError:
        return None
    model_date = claim.get("event_date")
    if (
        type(model_date) is not str
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", model_date) is None
        or model_date != event_date.isoformat()
        or event_date > context.observed_at.astimezone(datetime.timezone.utc).date()
    ):
        return None

    field_bindings = envelope.get("field_bindings")
    if type(field_bindings) is not list:
        return None
    field_path = "/claims/{}/event_date".format(claim_index)
    matching = [
        (index, binding)
        for index, binding in enumerate(field_bindings)
        if type(binding) is dict and binding.get("field_path") == field_path
    ]
    if len(matching) != 1:
        return None
    binding_index, binding = matching[0]
    end = start + len(sentence)
    binding_quote = binding.get("quote")
    binding_start = binding.get("start")
    binding_end = binding.get("end")
    binding_tail = (
        source.body[end:binding_end]
        if type(binding_end) is int and end <= binding_end <= len(source.body)
        else None
    )
    if (
        binding_index not in verified_binding_indices
        or type(binding.get("source_id")) is not str
        or binding["source_id"] != claim.get("source_id")
        or type(binding_quote) is not str
        or type(binding_start) is not int
        or type(binding_end) is not int
        or binding_start != start
        or binding_end < end
        or binding_quote != source.body[binding_start:binding_end]
        or binding_quote[: len(sentence)] != sentence
        or binding_tail is None
        or binding_tail.strip(" \t\r\n")
        or source.body[start:end] != sentence
        or binding.get("semantic_role") != "date"
        or binding.get("status") != "supported"
    ):
        return None
    return event_date, start, end, match.group("verb")


def _ascii_whitespace_pattern(value: str) -> str:
    return (_SRO_ASCII_WS + "+").join(
        re.escape(part)
        for part in re.split(_SRO_ASCII_WS + "+", value)
    )


_SEC_V04_SLASH_DATE_TOKEN = re.compile(
    r"(?<![A-Za-z0-9-])[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}(?![A-Za-z0-9-])",
    re.ASCII,
)
_SEC_V04_ALLOWED_PERIODIC_OBJECT_TEXT = "U.S. Food and Drug Administration"
_SEC_V04_ALLOWED_PERIODIC_OBJECT_PHRASE = (
    r"(?<![A-Za-z0-9_])"
    + re.escape(_SEC_V04_ALLOWED_PERIODIC_OBJECT_TEXT)
    + r"(?![A-Za-z0-9_])"
)


def _sec_v04_ambiguity_date_tokens(text: str):
    return tuple(
        sorted(
            (
                *_SRO_DATE_TOKEN.finditer(text),
                *_SEC_V04_SLASH_DATE_TOKEN.finditer(text),
            ),
            key=lambda match: match.start(),
        )
    )


def _sec_primary_html_occurrence_pattern(registrant: str):
    whitespace = _SRO_ASCII_WS + "+"
    verbs = (
        "entered into",
        "completed",
        "closed",
        "executed",
        "signed",
        "announced",
        "issued a press release",
    )
    verb_pattern = "|".join(_ascii_whitespace_pattern(verb) for verb in verbs)
    alias_pattern = (
        r"(?:" + whitespace + r"\(" + _ascii_whitespace_pattern("the")
        + whitespace + r"(?:“Company”|\"Company\")\))?"
    )
    object_pattern = (
        r"(?P<object>(?:[^.!?]|"
        + _SEC_V04_ALLOWED_PERIODIC_OBJECT_PHRASE
        + r"){1,240}?)\."
    )
    return re.compile(
        r"(?<![A-Za-z0-9])On" + whitespace
        + r"(?P<month>(?ai:" + _ENGLISH_MONTHS + r"))" + whitespace
        + r"(?P<day>[0-9]{1,2})," + whitespace
        + r"(?P<year>[0-9]{4})," + whitespace
        + _ascii_whitespace_pattern(registrant)
        + alias_pattern + whitespace
        + r"(?P<verb>" + verb_pattern + r")" + whitespace
        + object_pattern
        + r"(?=$|[ \t\r\n\f\v])"
    )


def _sec_primary_html_occurrence_date_v0_4(
    claim_index: int,
    claim: dict,
    source: HostSourceBody,
    envelope: dict,
    verified_binding_indices: frozenset,
    context: HostBuildContext,
    admission: object,
):
    """Resolve one exact occurrence sentence from its authenticated SEC HTML body."""
    if type(admission) is not SourceAdmission:
        return None
    try:
        parsed_size = len(admission.parsed_body.encode("utf-8", errors="strict"))
    except (AttributeError, UnicodeEncodeError):
        return None
    checked_admission = _revalidate_source_admission(
        admission,
        max_raw_bytes=admission.raw_body_bytes,
        max_parsed_bytes=parsed_size,
    )
    if (
        checked_admission is None
        or checked_admission.family != "sec"
        or checked_admission.parser_id != "sec-edgar-cover-layout-v4"
        or checked_admission.parser_version != "4"
        or checked_admission.content_type != "text/html"
        or checked_admission.source_id != claim.get("source_id")
        or checked_admission.source_id != admission.source_id
        or checked_admission.final_locator != source.final_locator
        or checked_admission.parsed_body != source.body
        or checked_admission.parsed_body_sha256 != source.body_sha256
        or checked_admission.retrieved_at != source.retrieved_at
        or hashlib.sha256(source.body.encode("utf-8", errors="strict")).hexdigest()
        != source.body_sha256
    ):
        return None
    initial_parts = _sec_locator_parts(checked_admission.initial_locator)
    locator_parts = _sec_locator_parts(source.final_locator)
    if locator_parts is None or initial_parts != locator_parts:
        return None

    registrant_anchors = tuple(
        anchor
        for anchor in checked_admission.raw_anchors
        if anchor.field == "sec_cover.registrant"
    )
    if len(registrant_anchors) != 1:
        return None
    registrant_anchor = registrant_anchors[0]
    if (
        type(registrant_anchor.parsed_start) is not int
        or type(registrant_anchor.parsed_end) is not int
        or not 0 <= registrant_anchor.parsed_start < registrant_anchor.parsed_end
        <= len(source.body)
    ):
        return None
    registrant = source.body[
        registrant_anchor.parsed_start:registrant_anchor.parsed_end
    ]
    if _sec_cover_layout_v4_fold(registrant) is None:
        return None

    claim_id = claim.get("claim_id")
    quote = claim.get("quote")
    claim_text = claim.get("text")
    if (
        type(claim_id) is not str
        or type(quote) is not str
        or not quote
        or type(claim_text) is not str
    ):
        return None
    paragraph_spans = tuple(_line_paragraph_spans(source.body))
    paragraph_matches = tuple(
        span for span in paragraph_spans if source.body[slice(*span)] == quote
    )
    if len(paragraph_matches) != 1:
        return None
    paragraph_start, paragraph_end = paragraph_matches[0]
    quote_start = source.body.find(quote)
    if quote_start != paragraph_start or source.body.find(quote, quote_start + 1) >= 0:
        return None

    statement_pattern = _sec_primary_html_occurrence_pattern(registrant)
    paragraph_matches = tuple(statement_pattern.finditer(quote))
    if len(paragraph_matches) != 1:
        return None
    statement = paragraph_matches[0]
    prefix = quote[:statement.start()]
    if prefix.strip(" \t\r\n\f\v") and re.search(
        r"[.!?][ \t\r\n\f\v]*\Z", prefix
    ) is None:
        return None
    statement_text = statement.group(0)
    statement_start = paragraph_start + statement.start()
    statement_end = paragraph_start + statement.end()
    date_start = paragraph_start + statement.start("month")
    date_end = paragraph_start + statement.end("year")
    paragraph_date_tokens = _sec_v04_ambiguity_date_tokens(quote)
    if (
        len(paragraph_date_tokens) != 1
        or paragraph_date_tokens[0].span()
        != (statement.start("month"), statement.end("year"))
    ):
        return None
    if any(
        statement_start <= match.start() < statement_end
        and match.span() != (
            date_start,
            date_end,
        )
        for match in _sec_v04_ambiguity_date_tokens(source.body)
    ):
        return None
    if _ascii_whitespace_fold(claim_text) != _ascii_whitespace_fold(statement_text):
        return None

    object_text = statement.group("object").strip(" \t\r\n\f\v")
    # The one permitted periodic phrase contains "and" as part of the agency name.
    uncertainty_object_text = object_text.replace(
        _SEC_V04_ALLOWED_PERIODIC_OBJECT_TEXT, "U.S. Food-Drug Administration"
    )
    negation = re.compile(
        r"\b(?:not|never|neither|nor|no|without|failed\s+to|cannot|can't|"
        r"won't|didn't|doesn't|hasn't|haven't|hadn't)\b",
        re.IGNORECASE | re.ASCII,
    )
    if (
        not object_text
        or len(object_text) > 240
        or _UNCERTAIN_ACTION.search(uncertainty_object_text) is not None
        or negation.search(object_text) is not None
    ):
        return None

    body = source.body
    correction_label = re.compile(
        r"^[ \t]*(?:Correction|Corrected event date|Withdrawal|Retraction):",
        re.IGNORECASE | re.ASCII | re.MULTILINE,
    )
    correction_sentence = re.compile(
        r"(?ai)(?<![A-Za-z0-9])The" + _SRO_ASCII_WS + r"+foregoing"
        + _SRO_ASCII_WS + r"+statement" + _SRO_ASCII_WS + r"+is"
        + _SRO_ASCII_WS
        + r"+(?:incorrect|corrected|withdrawn|retracted)\."
    )
    if correction_label.search(body) is not None or correction_sentence.search(body) is not None:
        return None

    selected_key = (
        _ascii_whitespace_fold(registrant),
        _ascii_whitespace_fold(statement.group("verb")),
        _ascii_whitespace_fold(object_text),
    )
    duplicate_matches = tuple(
        match
        for match in statement_pattern.finditer(body)
        if (
            _ascii_whitespace_fold(registrant),
            _ascii_whitespace_fold(match.group("verb")),
            _ascii_whitespace_fold(
                match.group("object").strip(" \t\r\n\f\v")
            ),
        ) == selected_key
    )
    if len(duplicate_matches) != 1 or (
        duplicate_matches[0].start(), duplicate_matches[0].end()
    ) != (statement_start, statement_end):
        return None

    try:
        event_date = datetime.date(
            int(statement.group("year")),
            _ENGLISH_MONTH_NUMBERS[statement.group("month").title()],
            int(statement.group("day")),
        )
    except (KeyError, ValueError):
        return None
    model_date = claim.get("event_date")
    if (
        type(model_date) is not str
        or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", model_date) is None
        or model_date != event_date.isoformat()
        or event_date > context.observed_at.astimezone(datetime.timezone.utc).date()
    ):
        return None

    field_bindings = envelope.get("field_bindings")
    if type(field_bindings) is not list:
        return None
    field_path = "/claims/{}/event_date".format(claim_index)
    matching_bindings = tuple(
        (index, binding)
        for index, binding in enumerate(field_bindings)
        if type(binding) is dict and binding.get("field_path") == field_path
    )
    if len(matching_bindings) != 1:
        return None
    binding_index, binding = matching_bindings[0]
    binding_start = binding.get("start")
    binding_end = binding.get("end")
    if (
        binding_index not in verified_binding_indices
        or binding.get("source_id") != claim.get("source_id")
        or binding.get("source_id") != checked_admission.source_id
        or type(binding_start) is not int
        or type(binding_end) is not int
        or binding_start != paragraph_start
        or binding_end != paragraph_end
        or binding.get("quote") != quote
        or source.body[binding_start:binding_end] != quote
        or binding.get("semantic_role") != "date"
        or binding.get("status") != "supported"
    ):
        return None

    action_role = (
        "announcement"
        if _ascii_whitespace_fold(statement.group("verb"))
        in ("announced", "issued a press release")
        else "completed_act"
    )
    return event_date, {
        "admission_provenance": checked_admission.provenance(),
        "registrant": registrant,
        "cik": locator_parts[0],
        "accession": locator_parts[1],
        "source_id": checked_admission.source_id,
        "body_sha256": source.body_sha256,
        "locator": source.final_locator,
        "action_role": action_role,
        "action_verb": _ascii_whitespace_fold(statement.group("verb")),
        "matched_statement": statement_text,
        "statement_start": statement_start,
        "statement_end": statement_end,
        "paragraph_start": paragraph_start,
        "paragraph_end": paragraph_end,
        "paragraph_quote": quote,
        "binding_start": binding_start,
        "binding_end": binding_end,
        "date_token_start": date_start,
        "date_token_end": date_end,
        "date_token": body[date_start:date_end],
    }


def _retain_unknown_context_v0_4(
    snapshot: object,
    receipt: object,
    original_context: HostBuildContext,
    prepared_context: HostBuildContext,
    admission_by_id: dict,
) -> HostBuildContext:
    """Apply the frozen authenticated SEC primary-HTML occurrence-date rule."""
    if prepared_context.event_date_range is not None:
        return prepared_context
    selected_id = prepared_context.event_description_binding
    if type(selected_id) is not str:
        return prepared_context
    evidence = _preparation_evidence(snapshot, receipt, original_context)
    if evidence is None:
        return prepared_context
    envelope, verified_claim_ids, verified_binding_indices = evidence
    claims = envelope.get("claims")
    if type(claims) is not list:
        return prepared_context
    selected = tuple(
        (index, claim)
        for index, claim in enumerate(claims)
        if type(claim) is dict and claim.get("claim_id") == selected_id
    )
    if len(selected) != 1:
        return prepared_context
    claim_index, claim = selected[0]
    if (
        claim.get("kind") != "observed_fact"
        or selected_id not in verified_claim_ids
        or type(claim.get("source_id")) is not str
    ):
        return prepared_context
    source_id = claim["source_id"]
    source = original_context.source_bodies.get(source_id)
    admission = admission_by_id.get(source_id)
    if (
        type(source) is not HostSourceBody
        or claim.get("locator") != source.final_locator
        or type(admission) is not SourceAdmission
    ):
        return prepared_context
    occurrence = _sec_primary_html_occurrence_date_v0_4(
        claim_index,
        claim,
        source,
        envelope,
        verified_binding_indices,
        original_context,
        admission,
    )
    if occurrence is None:
        return prepared_context
    event_date, fields = occurrence
    methodology = json.dumps(
        {
            "rule_version": (
                "host-event-source-facts-v0.4/"
                "sec-primary-html-occurrence-date"
            ),
            **fields,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return replace(
        prepared_context,
        event_date_range=MethodologizedDateRange(event_date, event_date, methodology),
    )


def _publication_datetime(value: Optional[str]) -> Optional[datetime.datetime]:
    """Retain only an explicitly timezone-aware publication timestamp."""
    if type(value) is not str:
        return None
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _safe_configuration_snapshot(config: HostEventGrounderConfig) -> bytes:
    """Serialize only the fixed, non-secret run-start configuration allowlist."""
    def model_snapshot(model: ModelRuntimeConfig) -> dict:
        endpoint = urlsplit(model.base_endpoint)
        # ModelRuntimeConfig already rejects userinfo, query, and fragment.
        # Reassemble only the URL components accepted for the public snapshot.
        host = endpoint.hostname
        if host is None:
            raise ValueError("model endpoint is invalid")
        if ":" in host and not host.startswith("["):
            host = "[{}]".format(host)
        port = endpoint.port
        netloc = host if port is None else "{}:{}".format(host, port)
        clean_endpoint = "{}://{}{}".format(
            endpoint.scheme.casefold(), netloc, endpoint.path
        )
        return {
            "schema_version": "host-event-model-snapshot-v0.1",
            "role": model.role,
            "provider": model.provider,
            "model": model.model,
            "base_endpoint": clean_endpoint,
            "capabilities": list(model.capabilities),
            "timeout_seconds": model.timeout_seconds,
            "request_budget": model.request_budget,
            "max_tokens": model.max_tokens,
            "max_input_bytes": model.max_input_bytes,
            "max_output_bytes": model.max_output_bytes,
            "remote_enabled": model.remote_enabled,
            "fee_authorized": model.fee_authorized,
            "json_mode": model.json_mode,
            "thinking_enabled": model.thinking_enabled,
        }

    source = config.source
    snapshot = {
        "models": [
            model_snapshot(config.discovery_model),
            model_snapshot(config.semantic_model),
        ],
        "sources": [
            {
                "schema_version": "host-event-source-snapshot-v0.1",
                "provider": "tavily",
                "paygo_off_confirmed": source.paygo_off_confirmed,
                "request_budget": source.request_budget,
                "credit_budget": source.credit_budget,
                "max_request_bytes": source.max_request_bytes,
                "max_response_bytes": source.max_response_bytes,
                "timeout_seconds": source.timeout_seconds,
                "time_budget_seconds": source.time_budget_seconds,
                "byte_budget": source.byte_budget,
                "max_search_results": source.max_search_results,
                "max_extract_urls": source.max_extract_urls,
                "grounder_limits": {
                    "run_input_bounds": {
                        "max_run_input_bytes": config.run_input_bounds.max_run_input_bytes,
                        "max_string_bytes": config.run_input_bounds.max_string_bytes,
                        "max_array_items": config.run_input_bounds.max_array_items,
                    },
                    "max_json_bytes": config.max_json_bytes,
                    "max_source_body_bytes": config.max_source_body_bytes,
                    "max_catalog_entries": config.max_catalog_entries,
                    "max_catalog_bytes": config.max_catalog_bytes,
                    "max_catalog_paragraphs": config.max_catalog_paragraphs,
                },
                # This closed snapshot persists the admission formula inputs:
                # per-GET raw cap = max_response_bytes; aggregate raw cap =
                # min(5 * that cap, byte_budget - Tavily bytes already spent)
                # when byte_budget is configured, else 5 * that cap. The
                # grounder limit is the separate total parsed-context cap;
                # admission wall time is timeout_seconds * 5 monotonic seconds.
            }
        ],
        "skills": [],
    }
    try:
        encoded = json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError):
        raise ValueError("configuration snapshot is invalid") from None
    if len(encoded) > config.max_json_bytes:
        raise ValueError("configuration snapshot exceeds max_json_bytes")
    return encoded


def create_event_grounder(
    config: HostEventGrounderConfig,
    *,
    repo_root: Union[str, Path],
    source_transport: Optional[Callable[[Any, float], Any]] = None,
    discovery_transport: Optional[Callable[[Any, float], Any]] = None,
    semantic_transport: Optional[Callable[[Any, float], Any]] = None,
    host_context_preparer: Optional[Callable[..., HostBuildContext]] = None,
) -> Callable[..., HostGrounderEvidenceCatalogRuntimeResult]:
    """Return the frozen server callback, creating fresh clients per run.

    Optional transports are the same narrow test seam exposed by the existing
    clients. Production callers omit them and use the configured HTTP clients.
    """
    config = _revalidate_config(config)
    if host_context_preparer is not None and not callable(host_context_preparer):
        raise TypeError("host_context_preparer must be callable or None")
    for name, transport in (
        ("source_transport", source_transport),
        ("discovery_transport", discovery_transport),
        ("semantic_transport", semantic_transport),
    ):
        if transport is not None and not callable(transport):
            raise TypeError("{} must be callable or None".format(name))
    context_preparer = (
        _retain_unknown_context_v0_3
        if host_context_preparer is None
        else host_context_preparer
    )
    # Capture immutable canonical bytes now, before the host can initiate any
    # external call. The accessor below returns a detached JSON-compatible copy.
    snapshot_bytes = _safe_configuration_snapshot(config)

    def configuration_snapshot() -> dict:
        """Return a fresh JSON-safe copy of the fixed non-secret config snapshot.

        Hosts can persist this run-start record before invoking the callback.
        Mutating a returned object cannot alter the captured snapshot.
        """
        return json.loads(snapshot_bytes.decode("utf-8"))

    def _run_grounder(
        raw_input: str,
        *,
        run_id: str,
        bounds: CoreOperationalBounds,
        source_query: str,
    ) -> HostGrounderEvidenceCatalogRuntimeResult:
        if not callable(context_preparer):
            raise HostGrounderRuntimeError("HOST_CONTEXT_PREPARER_INVALID")
        if type(bounds) is not CoreOperationalBounds:
            raise TypeError("bounds must be CoreOperationalBounds")
        try:
            CoreOperationalBounds(
                max_submissions=bounds.max_submissions,
                max_hypotheses=bounds.max_hypotheses,
                max_browser_rows=bounds.max_browser_rows,
                max_cases=bounds.max_cases,
                quote_timeout_seconds=bounds.quote_timeout_seconds,
            )
        except (AttributeError, TypeError, ValueError):
            raise TypeError("bounds must be a valid CoreOperationalBounds") from None
        active_config = _revalidate_config(config)
        user_input = UserEventInput(raw_input)
        subquestion = HostGrounderSubquestion(_SUBQUESTION_ID, raw_input)
        default_recipe = host_context_preparer is None
        subquestions = (
            (
                subquestion,
                HostGrounderSubquestion(
                    _EVENT_FACT_ANCHOR_SUBQUESTION_ID,
                    _EVENT_FACT_ANCHOR_QUESTION,
                ),
            )
            if default_recipe
            else (subquestion,)
        )
        run_input = HostGrounderRunInput(
            run_id,
            user_input,
            subquestions,
            active_config.run_input_bounds,
        )

        source_client = TavilySourceClient(
            active_config.source,
            repo_root=repo_root,
            transport=source_transport,
        )
        discovery_client = ChatCompletionsClient(
            active_config.discovery_model,
            active_config.discovery_credential,
            repo_root=repo_root,
            transport=discovery_transport,
        )
        semantic_client = ChatCompletionsClient(
            active_config.semantic_model,
            active_config.semantic_credential,
            repo_root=repo_root,
            transport=semantic_transport,
        )

        # One Basic Search plus one Basic Extract (at most five URLs, one
        # Extract credit). Fail before the first paid-capable call if the
        # caller's own source budget cannot cover that bounded operation.
        if source_client.remaining_request_budget < 2:
            raise TavilyTransportError("REQUEST_BUDGET_EXHAUSTED")
        if source_client.remaining_credit_budget < 2:
            raise TavilyTransportError("CREDIT_BUDGET_EXHAUSTED")
        if discovery_client.remaining_request_budget < 1:
            raise ModelTransportError("REQUEST_BUDGET_EXHAUSTED")
        if semantic_client.remaining_request_budget < 1:
            raise ModelTransportError("REQUEST_BUDGET_EXHAUSTED")

        max_results = min(
            active_config.source.max_search_results,
            active_config.source.max_extract_urls,
            active_config.run_input_bounds.max_array_items,
        )
        search_result = source_client.search(source_query, max_results=max_results)
        references = search_result.sources
        if not references:
            # No result is a stage failure, not evidence that the full source
            # universe was searched or that the request has complete coverage.
            raise HostGrounderRuntimeError("NO_SEARCH_RESULTS")

        requested_urls = tuple(reference.url for reference in references)
        extracted = source_client.extract(
            requested_urls,
            query=source_query,
            source_refs=references,
        )
        if (
            not extracted.coverage.is_complete
            or extracted.failed_extracts
            or extracted.urls != requested_urls
            or len(extracted.bodies) != len(references)
            or tuple(body.url for body in extracted.bodies) != requested_urls
        ):
            # A partial Extract is a conservative pre-model failure, not a
            # claim that no sources exist or that source coverage is complete.
            # The frozen runtime result has no Tavily receipt slot, so this
            # exact-result interface does not retain a partial receipt.
            raise HostGrounderRuntimeError("EXTRACTION_FAILURE")

        reference_by_url = {reference.url: reference for reference in references}
        retrieved_at = datetime.datetime.now(datetime.timezone.utc)
        source_bodies = {}
        for body in extracted.bodies:
            reference = reference_by_url.get(body.url)
            if (
                reference is None
                or body.source_id != reference.source_id
                or not body.body.strip()
                or body.source_id in source_bodies
            ):
                raise HostGrounderRuntimeError("EXTRACTION_FAILURE")
            encoded_body = body.body.encode("utf-8", errors="strict")
            source_bodies[body.source_id] = HostSourceBody(
                body=body.body,
                body_sha256=hashlib.sha256(encoded_body).hexdigest(),
                final_locator=body.url,
                retrieved_at=retrieved_at,
                title=reference.title,
                published_at=_publication_datetime(body.publication_date),
            )

        # Direct admission is a separate, Host-owned read. A failure for one
        # locator leaves that Tavily record unadmitted and does not claim an
        # origin; it does not turn into an Event-wide source or semantic veto.
        candidate_locators = tuple(body.url for body in extracted.bodies)
        admitted_sources = ()
        admission_raw_response_limit = active_config.source.max_response_bytes
        admission_raw_budget_limit = (
            MAX_SOURCE_ADMISSION_REQUESTS * admission_raw_response_limit
        )
        if active_config.source.byte_budget is not None:
            admission_raw_budget_limit = min(
                admission_raw_budget_limit,
                max(0, active_config.source.byte_budget - source_client.bytes_used),
            )
        tavily_body_bytes = sum(
            len(source.body.encode("utf-8", errors="strict"))
            for source in source_bodies.values()
        )
        pending_source_bodies = {}
        admitted_source_list = []
        admission_client = None
        sec_composite_records = ()
        sec_composite_symbols = ()
        try:
            admission_client = _create_source_admission_client(
                timeout_seconds=active_config.source.timeout_seconds,
                max_response_bytes=admission_raw_response_limit,
                byte_budget=admission_raw_budget_limit,
            )
            admission_batch = admission_client.admit_candidates(candidate_locators)
            if type(admission_batch) is AdmissionBatch:
                admission_batch = AdmissionBatch(
                    tuple(admission_batch.admissions),
                    tuple(admission_batch.failures),
                    admission_batch.request_count,
                    admission_batch.response_bytes,
                )
                if admission_batch.response_bytes > admission_raw_budget_limit:
                    admission_batch = AdmissionBatch((), (), 0, 0)
                candidate_set = frozenset(candidate_locators)
                authorized_supplements = set()
                admitted_ids = set()
                admitted_initials = set()
                registered_bytes = tavily_body_bytes
                for candidate in admission_batch.admissions:
                    admission = _revalidate_source_admission(
                        candidate,
                        max_raw_bytes=admission_raw_response_limit,
                        max_parsed_bytes=active_config.max_source_body_bytes,
                    )
                    if admission is None or admission.source_id in admitted_ids:
                        continue
                    if (
                        admission.initial_locator not in candidate_set
                        and admission.initial_locator not in authorized_supplements
                    ):
                        continue
                    if admission.initial_locator in admitted_initials:
                        continue
                    if admission.source_id in source_bodies or admission.source_id in pending_source_bodies:
                        continue
                    parsed_bytes = len(admission.parsed_body.encode("utf-8", errors="strict"))
                    if (
                        len(source_bodies) + len(pending_source_bodies)
                        >= run_input.bounds.max_array_items
                        or registered_bytes + parsed_bytes > active_config.max_source_body_bytes
                    ):
                        continue
                    pending_source_bodies[admission.source_id] = HostSourceBody(
                        body=admission.parsed_body,
                        body_sha256=admission.parsed_body_sha256,
                        final_locator=admission.final_locator,
                        retrieved_at=admission.retrieved_at,
                    )
                    admitted_source_list.append(admission)
                    admitted_ids.add(admission.source_id)
                    admitted_initials.add(admission.initial_locator)
                    registered_bytes += parsed_bytes
                    if (
                        admission.family == "sec"
                        and admission.initial_locator in candidate_set
                        and admission.parser_id == "sec-edgar-cover-v1"
                        and admission.parser_version == "1"
                    ):
                        symbol = admission.parsed_symbol
                        if symbol is not None:
                            authorized_supplements.add(
                                "https://www.nasdaq.com/market-activity/stocks/{}".format(
                                    symbol.lower()
                                )
                            )
                            authorized_supplements.add(
                                "https://finance.yahoo.com/quote/{}/".format(symbol)
                            )
                cover_candidates = {}
                for admission in admitted_source_list:
                    if (
                        admission.parser_id != "sec-edgar-cover-layout-v4"
                        or admission.parser_version != "4"
                        or admission.source_id not in pending_source_bodies
                        or admission.parsed_symbol is None
                    ):
                        continue
                    path_parts = _sec_locator_parts(admission.final_locator)
                    if path_parts is None:
                        continue
                    cover = _parse_sec_primary_cover(
                        admission.source_id,
                        pending_source_bodies[admission.source_id],
                        admission.parsed_symbol,
                        int(path_parts[0]),
                        admission,
                    )
                    if cover is not None:
                        cover_candidates.setdefault(admission.parsed_symbol, []).append(admission)
                selected_cover_map = {
                    symbol: items[0]
                    for symbol, items in cover_candidates.items()
                    if len(items) == 1
                }
                selected_symbols = tuple(sorted(selected_cover_map))
                if selected_symbols:
                    selected_covers = tuple(
                        selected_cover_map[symbol] for symbol in selected_symbols
                    )
                    try:
                        composite_batch = admission_client._admit_sec_reference_and_yahoo(
                            selected_symbols, selected_covers
                        )
                        composite = admission_client._revalidate_sec_composite(
                            composite_batch.admissions,
                            selected_symbols,
                            max_raw_bytes=admission_raw_response_limit,
                            max_parsed_bytes=active_config.max_source_body_bytes,
                        )
                        if composite is not None:
                            additions = tuple(
                                item for item in composite
                                if item.source_id not in admitted_ids
                            )
                            addition_ids = {item.source_id for item in additions}
                            parsed_total = sum(
                                len(item.parsed_body.encode("utf-8", errors="strict"))
                                for item in additions
                            )
                            if (
                                len(addition_ids) == len(additions)
                                and all(
                                    item.source_id not in source_bodies
                                    and item.initial_locator not in admitted_initials
                                    for item in additions
                                )
                                and len(source_bodies) + len(pending_source_bodies)
                                + len(additions) <= run_input.bounds.max_array_items
                                and registered_bytes + parsed_total
                                <= active_config.max_source_body_bytes
                            ):
                                for item in additions:
                                    pending_source_bodies[item.source_id] = HostSourceBody(
                                        body=item.parsed_body,
                                        body_sha256=item.parsed_body_sha256,
                                        final_locator=item.final_locator,
                                        retrieved_at=item.retrieved_at,
                                    )
                                    admitted_source_list.append(item)
                                    admitted_ids.add(item.source_id)
                                    admitted_initials.add(item.initial_locator)
                                registered_bytes += parsed_total
                                sec_composite_records = composite
                                sec_composite_symbols = selected_symbols
                    except Exception:
                        sec_composite_records = ()
                        sec_composite_symbols = ()
            source_bodies.update(pending_source_bodies)
            admitted_sources = tuple(admitted_source_list)
        except Exception:
            # Keep the origin-admission failure local and closed. In particular,
            # never persist or expose arbitrary transport/parser exception text.
            pending_source_bodies.clear()
            admitted_source_list = []
            admitted_sources = ()

        run_context_preparer = context_preparer
        event_fact_anchor_capture = [] if default_recipe else None
        if host_context_preparer is None:
            run_context_preparer = _make_listing_source_preparer(
                tuple(source.source_id for source in admitted_sources),
                admission_records=admitted_sources,
                sec_composite=(
                    (
                        admission_client,
                        sec_composite_symbols,
                        sec_composite_records,
                        admission_raw_response_limit,
                        active_config.max_source_body_bytes,
                    )
                    if sec_composite_records and admission_client is not None
                    else None
                ),
                _event_fact_anchor_capture=event_fact_anchor_capture,
            )

        context = HostBuildContext(
            raw_input=user_input,
            submission_id=run_id,
            event_id=run_id,
            producer_id=_PRODUCER_ID,
            producer_version=_PRODUCER_VERSION,
            observed_at=retrieved_at,
            source_bodies=source_bodies,
            run_id=run_id,
            canonical_input_hash=run_input.canonical_input_hash,
            # No event-date, hypothesis, listing, or caller-policy evidence is
            # inferred from UserEventInput hints or arbitrary web text.
        )
        audit_holder = HostEvidenceCatalogAuditHolder(
            run_id=run_id,
            canonical_input_hash=run_input.canonical_input_hash,
        )
        result = _run_host_grounder_same_run_evidence_catalog_v0_9(
            run_input,
            context,
            discovery_client=discovery_client,
            semantic_client=semantic_client,
            audit_holder=audit_holder,
            max_json_bytes=active_config.max_json_bytes,
            max_source_body_bytes=active_config.max_source_body_bytes,
            max_catalog_entries=active_config.max_catalog_entries,
            max_catalog_bytes=active_config.max_catalog_bytes,
            max_catalog_paragraphs=active_config.max_catalog_paragraphs,
            host_context_preparer=run_context_preparer,
            semantic_transport_retry_enabled=default_recipe,
        )
        if event_fact_anchor_capture is None:
            return result
        if len(event_fact_anchor_capture) != 1:
            raise HostGrounderRuntimeError("HOST_CONTEXT_PREPARATION_REJECTED")
        return _stamp_event_fact_anchor_outcome(
            result, event_fact_anchor_capture[0]
        )

    def event_grounder(
        raw_input: str,
        *,
        run_id: str,
        bounds: CoreOperationalBounds,
    ) -> HostGrounderEvidenceCatalogRuntimeResult:
        _ = (config, context_preparer)
        return _run_grounder(
            raw_input,
            run_id=run_id,
            bounds=bounds,
            source_query=raw_input,
        )

    def world_source_query_factory(
        source_query: object,
    ) -> Callable[..., HostGrounderEvidenceCatalogRuntimeResult]:
        if (
            type(source_query) is not str
            or not source_query
            or source_query != source_query.strip()
            or len(source_query) > 400
        ):
            raise HostGrounderRuntimeError("SOURCE_QUERY_INVALID")
        try:
            source_query.encode("utf-8", "strict")
        except UnicodeEncodeError:
            raise HostGrounderRuntimeError("SOURCE_QUERY_INVALID") from None

        def query_bound_grounder(
            raw_input: str,
            *,
            run_id: str,
            bounds: CoreOperationalBounds,
        ) -> HostGrounderEvidenceCatalogRuntimeResult:
            return _run_grounder(
                raw_input,
                run_id=run_id,
                bounds=bounds,
                source_query=source_query,
            )

        return query_bound_grounder

    event_grounder.configuration_snapshot = configuration_snapshot
    event_grounder._world_source_query_factory = world_source_query_factory
    return event_grounder
