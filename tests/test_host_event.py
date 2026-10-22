"""Synthetic transport tests for the bounded pre-Core Event Grounder driver."""

import datetime
import hashlib
import inspect
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from urllib.error import HTTPError, URLError
from unittest.mock import patch

from convexity_hunter.core_application import CoreOperationalBounds
from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.event_intelligence import MethodologizedDateRange
from convexity_hunter.host_event import (
    _EVENT_FACT_ANCHOR_QUESTION,
    _EVENT_FACT_ANCHOR_SUBQUESTION_ID,
    HostEventGrounderConfig,
    _make_listing_source_preparer,
    _event_fact_anchor_claim_id,
    _retain_unknown_context_v0_5,
    _resolve_sec_occurrence_date,
    _retain_unknown_context,
    _retain_unknown_context_v0_2,
    _retain_unknown_context_v0_3,
    _publication_datetime,
    create_event_grounder,
)
from convexity_hunter.host_grounder_builder import (
    CallerPolicyProvenance,
    HostBuildContext,
    HostSourceBody,
)
from convexity_hunter.host_grounder_evidence_catalog import (
    _line_paragraph_spans,
    build_host_evidence_catalog,
    parse_grounder_output_v0_3,
)
from convexity_hunter.host_grounder_run_input import (
    HostGrounderRunInput,
    HostGrounderRunInputBounds,
    HostGrounderSubquestion,
)
from convexity_hunter.host_grounder_runtime import (
    HostGrounderEvidenceCatalogRuntimeResult,
    HostGrounderRuntimeError,
)
from convexity_hunter.host_grounder_receipt import ValidatedEnvelopeSnapshot
from convexity_hunter.host_model import (
    ModelCredential,
    ModelRuntimeConfig,
)
from convexity_hunter.host_sources import TavilyCredentialRef, TavilySourceConfig
from convexity_hunter.host_source_admission import (
    AdmissionBatch,
    _Reply,
    _SourceAdmissionClient,
    _nasdaq_html,
    _sec_html,
    _source_id_for_locator,
    _yahoo_html,
)
from convexity_hunter.market_data import UnderlyingKey, UnderlyingSecurityType


_ROOT = Path(__file__).resolve().parents[1]
_RAW_INPUT = "Assess the reported ACME filing."
_RUN_ID = "synthetic-event-run"
_NOW = datetime.datetime(2026, 10, 4, 8, 0, tzinfo=datetime.timezone.utc)
_BODY_BY_URL = {
    "https://source.example/z": "ACME filed a report.\n",
    "https://source.example/a": "The filing describes a possible capacity change.\n",
}
_SEARCH_ORDER = (
    ("source-z", "https://source.example/z"),
    ("source-a", "https://source.example/a"),
)
_SEC_LOCATOR = (
    "https://www.sec.gov/Archives/edgar/data/320193/"
    "000032019326000123/example.htm"
)
_SEC_SENTENCE = (
    "On October 3, 2026, ACME HOLDINGS, INC. completed its acquisition of Example Corp."
)
_V04_SEC_SENTENCE = (
    "On September 21, 2026, Example Holdings, Inc. (the “Company”) announced "
    "its agreement with Example Corp."
)
_SEC_HEADER = (
    "CONFORMED SUBMISSION TYPE: 8-K\n"
    "ACCESSION NUMBER: 0000320193-26-000123\n"
    "COMPANY CONFORMED NAME: ACME HOLDINGS, INC.\n"
    "CENTRAL INDEX KEY: 0000320193\n\n"
)
_SRO_ORDER_LOCATOR = "https://www.sec.gov/files/rules/sro/nasdaq/2026/34-105199.pdf"
_SRO_ORDER_BODY = (
    "SECURITIES AND EXCHANGE COMMISSION\n"
    "[Release No. 34-105199; File No. SR-Nasdaq-2025-109]\n"
    "Self-Regulatory Organizations; The Nasdaq Stock Market LLC;\n"
    "Order Granting Accelerated Approval of a Proposed Rule Change\n"
    "April 10, 2026.\n\n"
    "Earlier materials include March 2, 2026, Apr. 1, 2026, and 2026-03-20.\n\n"
    "IT IS THEREFORE ORDERED, pursuant to Section 19(b)(2) of the Act, that the proposed rule change "
    "(SR-Nasdaq-2025-109), as modified by Amendment No. 1, be, and is hereby, "
    "approved on an accelerated basis.\n\n"
    "For the Commission\nSynthetic Signatory\n"
)
_SRO_CLAIM_TEXT = (
    "The Securities and Exchange Commission approved the proposed rule change "
    "(SR-Nasdaq-2025-109) on an accelerated basis."
)
_SRO_OPERATIVE_CLAUSE = (
    "IT IS THEREFORE ORDERED, pursuant to Section 19(b)(2) of the Act, that the proposed rule change "
    "(SR-Nasdaq-2025-109), as modified by Amendment No. 1, be, and is hereby, "
    "approved on an accelerated basis."
)


class _SyntheticResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        self.status = 200
        self.headers = {}
        self.closed = False

    def read(self, _size=-1):
        return self.body

    def close(self):
        self.closed = True


class _NoNetworkAdmissionClient:
    def admit_candidates(self, _locators):
        return AdmissionBatch((), (), 0, 0)


class _SyntheticSourceTransport:
    def __init__(self, *, search_order=_SEARCH_ORDER, failed_urls=(), body_overrides=None):
        self.search_order = tuple(search_order)
        self.failed_urls = frozenset(failed_urls)
        self.body_overrides = dict(body_overrides or {})
        self.calls = []
        self.extract_url_orders = []

    def __call__(self, request, _timeout):
        payload = json.loads(request.data.decode("utf-8"))
        self.calls.append((request.full_url, payload))
        if request.full_url.endswith("/search"):
            results = [
                {
                    "id": source_id,
                    "url": url,
                    "title": "Unverified source title",
                    "content": "SEARCH_SNIPPET_MUST_NOT_REACH_MODELS_{}".format(source_id),
                    "published_date": "2026-10-03",
                }
                for source_id, url in self.search_order
            ]
            return _SyntheticResponse(
                {"results": results, "request_id": "synthetic-search"}
            )
        if request.full_url.endswith("/extract"):
            urls = tuple(payload["urls"])
            self.extract_url_orders.append(urls)
            results = [
                {
                    "url": url,
                    "raw_content": self.body_overrides.get(
                        url, _BODY_BY_URL.get(url, "Fetched source body.\n")
                    ),
                }
                for url in urls
                if url not in self.failed_urls
            ]
            failed = [{"url": url, "error": "synthetic failure"} for url in urls if url in self.failed_urls]
            return _SyntheticResponse(
                {
                    "results": results,
                    "failed_results": failed,
                    "request_id": "synthetic-extract",
                }
            )
        raise AssertionError("unexpected synthetic source endpoint")


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _context_and_run_input(
    run_id, raw_input, source_order, bodies_by_url, bounds, *, normal_recipe=True
):
    user_input = UserEventInput(raw_input)
    subquestions = (HostGrounderSubquestion("user_event_input", raw_input),)
    if normal_recipe:
        subquestions += (HostGrounderSubquestion(
            _EVENT_FACT_ANCHOR_SUBQUESTION_ID, _EVENT_FACT_ANCHOR_QUESTION
        ),)
    run_input = HostGrounderRunInput(
        run_id,
        user_input,
        subquestions,
        bounds,
    )
    source_bodies = {
        source_id: HostSourceBody(
            bodies_by_url[url],
            _digest(bodies_by_url[url]),
            url,
            _NOW,
            "Unverified source title",
            None,
        )
        for source_id, url in source_order
    }
    context = HostBuildContext(
        raw_input=user_input,
        submission_id=run_id,
        event_id=run_id,
        producer_id="convexity-hunter-event-grounder",
        producer_version="v0.1",
        observed_at=_NOW,
        source_bodies=source_bodies,
        run_id=run_id,
        canonical_input_hash=run_input.canonical_input_hash,
    )
    return run_input, context


def _model_outputs(
    run_id,
    raw_input,
    source_order,
    bodies_by_url,
    config,
    *,
    fact_text=None,
    event_date=None,
    additional_fact_texts=(),
    fact_evidence_markers=None,
    date_binding_marker=None,
    coverage_supported=False,
    covered_claim_ids=None,
    anchor_supported=None,
    research_coverage_supported=None,
    normal_recipe=True,
):
    run_input, context = _context_and_run_input(
        run_id,
        raw_input,
        source_order,
        bodies_by_url,
        config.run_input_bounds,
        normal_recipe=normal_recipe,
    )


    catalog = build_host_evidence_catalog(
        run_id,
        run_input.canonical_input_hash,
        context.source_bodies,
        max_catalog_entries=config.max_catalog_entries,
        max_catalog_bytes=config.max_catalog_bytes,
        max_catalog_paragraphs=config.max_catalog_paragraphs,
        max_string_bytes=run_input.bounds.max_string_bytes,
        max_array_items=run_input.bounds.max_array_items,
    )
    producer_claims = []
    producer_bindings = []
    verdict_claims = []
    verdict_bindings = []
    coverage_claim_ids = []
    claim_evidence_refs = {}
    fact_texts = () if fact_text is None else (fact_text,) + tuple(additional_fact_texts)
    evidence_markers = (
        None if fact_evidence_markers is None else tuple(fact_evidence_markers)
    )
    if evidence_markers is not None and len(evidence_markers) != len(fact_texts):
        raise ValueError("synthetic claim evidence markers must match emitted claims")
    for claim_index, claim_text in enumerate(fact_texts):
        marker = None if evidence_markers is None else evidence_markers[claim_index]
        matching_entries = tuple(
            entry
            for entry in catalog.entries
            if (
                marker in entry.quote
                if type(marker) is str
                else entry.quote.rstrip("\r\n") == claim_text
            )
        )
        if len(matching_entries) != 1:
            raise ValueError("synthetic claim evidence must identify one catalog paragraph")
        entry = matching_entries[0]
        evidence_ref = {"evidence_id": entry.evidence_id}
        claim_id = "fact-{}".format(claim_index + 1)
        claim_evidence_refs[claim_id] = evidence_ref
        claim_event_date = event_date if claim_index == 0 else None
        producer_claims.append(
            {
                "claim_id": claim_id,
                "kind": "observed_fact",
                "evidence_id": entry.evidence_id,
                "text": claim_text,
                "entity_refs": [],
                "event_date": claim_event_date,
                "published_at": None,
                "dependency_claim_ids": [],
                "uncertainty": [],
                "falsification_conditions": [],
            }
        )
        verdict_claims.append(
            {
                "claim_id": claim_id,
                "outcome": "supported",
                "rationale": "Synthetic source sentence supports the fact.",
                "evidence_refs": [evidence_ref],
            }
        )
        if claim_event_date is not None:
            binding_entries = tuple(
                candidate
                for candidate in catalog.entries
                if (
                    date_binding_marker in candidate.quote
                    if type(date_binding_marker) is str
                    else candidate.evidence_id == entry.evidence_id
                )
            )
            if len(binding_entries) != 1:
                raise ValueError("synthetic date evidence must identify one catalog paragraph")
            binding_ref = {"evidence_id": binding_entries[0].evidence_id}
            producer_bindings.append(
                {
                    "field_path": "/claims/{}/event_date".format(claim_index),
                    "evidence_id": binding_ref["evidence_id"],
                    "semantic_role": "date",
                    "status": "supported",
                }
            )
            verdict_bindings.append(
                {
                    "index": len(producer_bindings) - 1,
                    "outcome": "supported",
                    "rationale": "Synthetic source sentence localizes the date field.",
                    "evidence_refs": [binding_ref],
                }
            )
        coverage_claim_ids.append(claim_id)
    selected_coverage_ids = (
        coverage_claim_ids
        if covered_claim_ids is None
        else list(covered_claim_ids)
    )
    if any(claim_id not in claim_evidence_refs for claim_id in selected_coverage_ids):
        raise ValueError("synthetic coverage must reference an emitted claim")
    research_supported = (
        coverage_supported
        if research_coverage_supported is None
        else research_coverage_supported
    )
    if anchor_supported is None:
        anchor_supported = bool(fact_text) or coverage_supported
    anchor_claim_id = next(iter(selected_coverage_ids), None)
    coverage_rows = [{
        "subquestion_id": "user_event_input",
        "status": "supported" if research_supported else "unresolved",
        "claim_ids": selected_coverage_ids if research_supported else [],
        "gap": None if research_supported else "Synthetic fixture supplies no supported hypothesis.",
    }]
    if normal_recipe:
        coverage_rows.append({
            "subquestion_id": _EVENT_FACT_ANCHOR_SUBQUESTION_ID,
            "status": "supported" if anchor_supported and anchor_claim_id else "unresolved",
            "claim_ids": [anchor_claim_id] if anchor_supported and anchor_claim_id else [],
            "gap": None if anchor_supported and anchor_claim_id else "Synthetic fixture has no unique event anchor.",
        })
    producer = {
        "schema_version": "grounder-output-v0.3",
        "stage": "semantic",
        "request_id": run_id,
        "claims": producer_claims,
        "hypotheses": [],
        "coverage": coverage_rows,
        "field_bindings": producer_bindings,
    }
    normalized, normalized_bytes = parse_grounder_output_v0_3(
        json.dumps(producer, sort_keys=True, separators=(",", ":")),
        config.max_json_bytes,
        max_string_bytes=run_input.bounds.max_string_bytes,
        max_array_items=run_input.bounds.max_array_items,
        run_id=run_id,
        canonical_input_hash=run_input.canonical_input_hash,
        source_bodies=context.source_bodies,
        catalog=catalog,
    )
    verdict = {
        "schema_version": "semantic-verdict-v0.3",
        "run_id": run_id,
        "envelope_hash": _digest(normalized_bytes.decode("utf-8")),
        "source_body_hashes": [
            {"source_id": source_id, "sha256": source.body_sha256}
            for source_id, source in sorted(context.source_bodies.items())
        ],
        "claims": verdict_claims,
        "hypotheses": [],
        "field_bindings": verdict_bindings,
        "coverage": [
            {
                "index": 0,
                "subquestion_id": "user_event_input",
                "outcome": "supported" if research_supported else "unresolved",
                "rationale": "Synthetic verifier supports the covered event fact." if research_supported else "The synthetic fixture does not establish an answer.",
                "evidence_refs": [claim_evidence_refs[claim_id] for claim_id in selected_coverage_ids] if research_supported else [],
            }
        ] + ([{
            "index": 1,
            "subquestion_id": _EVENT_FACT_ANCHOR_SUBQUESTION_ID,
            "outcome": "supported" if anchor_supported and anchor_claim_id else "unresolved",
            "rationale": "Synthetic verifier supports the unique event anchor." if anchor_supported and anchor_claim_id else "The synthetic fixture has no unique event anchor.",
            "evidence_refs": [claim_evidence_refs[anchor_claim_id]] if anchor_supported and anchor_claim_id else [],
        }] if normal_recipe else []),
    }
    return (
        json.dumps(producer, sort_keys=True, separators=(",", ":")),
        json.dumps(verdict, sort_keys=True, separators=(",", ":")),
        normalized,
    )


def _source_fact_case(
    *,
    sentence=_SEC_SENTENCE,
    body=None,
    locator=_SEC_LOCATOR,
    model_date="2026-10-03",
    observed_at=_NOW,
    verified_claim=True,
    verified_binding=True,
    receipt_body_hash=None,
    binding_offset_delta=0,
    extra_claim=False,
    extra_interpretation=False,
    coverage_items=None,
    coverage_outcomes=None,
    claim_order=None,
    description=None,
    date_range=None,
):
    if body is None:
        body = _SEC_HEADER + sentence + "\n"
    source_id = "sec-fact"
    source = HostSourceBody(
        body, _digest(body), locator, _NOW, "Synthetic SEC filing", None
    )
    claims = [
        {
            "claim_id": "fact-1",
            "kind": "observed_fact",
            "source_id": source_id,
            "locator": locator,
            "quote": sentence,
            "text": sentence,
            "event_date": model_date,
        }
    ]
    if extra_claim:
        claims.append(
            {
                "claim_id": "fact-2",
                "kind": "observed_fact",
                "source_id": source_id,
                "locator": locator,
                "quote": "Additional source-backed fact.",
                "text": "Additional source-backed fact.",
                "event_date": None,
            }
        )
        body += "Additional source-backed fact.\n"
        source = HostSourceBody(
            body, _digest(body), locator, _NOW, "Synthetic SEC filing", None
        )
    if extra_interpretation:
        interpretation = "The filing suggests broader strategic effects."
        claims.append(
            {
                "claim_id": "interpretation-1",
                "kind": "interpretation",
                "source_id": source_id,
                "locator": locator,
                "quote": interpretation,
                "text": interpretation,
                "event_date": None,
            }
        )
        body += interpretation + "\n"
        source = HostSourceBody(
            body, _digest(body), locator, _NOW, "Synthetic SEC filing", None
        )
    start = body.find(sentence)
    envelope = {
        "schema_version": "grounder-output-v0.1",
        "stage": "semantic",
        "request_id": _RUN_ID,
        "claims": claims,
        "hypotheses": [],
        "coverage": [
            {
                "subquestion_id": "user_event_input",
                "status": "unresolved",
                "claim_ids": [],
                "gap": "Synthetic fixture.",
            }
        ],
        "field_bindings": [
            {
                "field_path": "/claims/0/event_date",
                "source_id": source_id,
                "quote": sentence,
                "start": start + binding_offset_delta,
                "end": start + len(sentence) + binding_offset_delta,
                "semantic_role": "date",
                "status": "supported",
            }
        ],
    }
    if claim_order is not None:
        claims_by_id = {claim["claim_id"]: claim for claim in claims}
        new_indexes = {claim_id: index for index, claim_id in enumerate(claim_order)}
        envelope["claims"] = [claims_by_id[claim_id] for claim_id in claim_order]
        for binding in envelope["field_bindings"]:
            parts = binding["field_path"].split("/")
            if len(parts) > 3 and parts[1] == "claims":
                claim_id = claims[int(parts[2])]["claim_id"]
                parts[2] = str(new_indexes[claim_id])
                binding["field_path"] = "/".join(parts)
    if coverage_items is not None:
        envelope["coverage"] = coverage_items
    canonical_bytes = json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    envelope_hash = _digest(canonical_bytes.decode("utf-8"))
    context = HostBuildContext(
        raw_input=UserEventInput(_RAW_INPUT),
        submission_id=_RUN_ID,
        event_id=_RUN_ID,
        producer_id="convexity-hunter-event-grounder",
        producer_version="v0.1",
        observed_at=observed_at,
        source_bodies={source_id: source},
        run_id=_RUN_ID,
        canonical_input_hash="a" * 64,
        event_description_binding=description,
        event_date_range=date_range,
    )
    receipt_values = {
        "schema_version": "semantic-validation-v0.2",
        "run_id": _RUN_ID,
        "canonical_input_hash": context.canonical_input_hash,
        "envelope_hash": envelope_hash,
        "source_body_hashes": (
            (source_id, receipt_body_hash or source.body_sha256),
        ),
        "verified_claim_ids": (
            tuple(claim["claim_id"] for claim in claims) if verified_claim else ()
        ),
        "verified_binding_indices": (0,) if verified_binding else (),
    }
    if coverage_outcomes is not None:
        receipt_values["coverage_outcomes"] = coverage_outcomes
    receipt = MappingProxyType(receipt_values)
    return ValidatedEnvelopeSnapshot(canonical_bytes, envelope_hash), receipt, context


def _sro_direct_case(
    *,
    body=_SRO_ORDER_BODY,
    locator=_SRO_ORDER_LOCATOR,
    claim_text=_SRO_CLAIM_TEXT,
    claim_quote_override=None,
    model_date="2026-04-10",
    binding_count=1,
    binding_paragraph="cover",
    binding_start_delta=0,
    binding_end_delta=0,
    binding_quote_override=None,
    binding_start_override=None,
    binding_end_override=None,
    verified_binding_indices=None,
    binding_status="supported",
    binding_role="date",
    binding_source_id=None,
    verified_claim_ids=("fact-1",),
    claim_id_override="fact-1",
    receipt_body_hash=None,
):
    source_id = "sro-order"
    source = HostSourceBody(body, _digest(body), locator, _NOW, "Synthetic SEC order", None)
    paragraph_spans = tuple(_line_paragraph_spans(body))
    clause_start = body.find("IT IS THEREFORE ORDERED")
    claim_span = next(
        (
            span
            for span in paragraph_spans
            if clause_start >= 0 and span[0] <= clause_start < span[1]
        ),
        paragraph_spans[0],
    )
    cover_token_start = next(
        start
        for start, end in paragraph_spans
        if body[start:end].startswith("SECURITIES AND EXCHANGE COMMISSION")
    )
    binding_span = next(
        span
        for span in paragraph_spans
        if span[0] <= cover_token_start < span[1]
    )
    if binding_paragraph == "claim":
        binding_span = claim_span
    binding_start, binding_end = binding_span
    binding_quote = body[binding_start:binding_end]
    if binding_quote_override is not None:
        binding_quote = binding_quote_override
    bindings = [
        {
            "field_path": "/claims/0/event_date",
            "source_id": source_id if binding_source_id is None else binding_source_id,
            "quote": binding_quote,
            "start": (
                binding_start + binding_start_delta
                if binding_start_override is None
                else binding_start_override
            ),
            "end": (
                binding_end + binding_end_delta
                if binding_end_override is None
                else binding_end_override
            ),
            "semantic_role": binding_role,
            "status": binding_status,
        }
        for _ in range(binding_count)
    ]
    envelope = {
        "schema_version": "grounder-output-v0.1",
        "stage": "semantic",
        "request_id": _RUN_ID,
        "claims": [
            {
                "claim_id": claim_id_override,
                "kind": "observed_fact",
                "source_id": source_id,
                "locator": locator,
                "quote": (
                    body[slice(*claim_span)]
                    if claim_quote_override is None
                    else claim_quote_override
                ),
                "text": claim_text,
                "event_date": model_date,
            }
        ],
        "hypotheses": [],
        "coverage": [],
        "field_bindings": bindings,
    }
    canonical_bytes = json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    envelope_hash = _digest(canonical_bytes.decode("utf-8"))
    context = HostBuildContext(
        raw_input=UserEventInput(_RAW_INPUT),
        submission_id=_RUN_ID,
        event_id=_RUN_ID,
        producer_id="convexity-hunter-event-grounder",
        producer_version="v0.1",
        observed_at=_NOW,
        source_bodies=MappingProxyType({source_id: source}),
        run_id=_RUN_ID,
        canonical_input_hash="a" * 64,
    )
    verified_indices = (
        tuple(range(binding_count))
        if verified_binding_indices is None
        else verified_binding_indices
    )
    receipt = MappingProxyType(
        {
            "schema_version": "semantic-validation-v0.2",
            "run_id": _RUN_ID,
            "canonical_input_hash": context.canonical_input_hash,
            "envelope_hash": envelope_hash,
            "source_body_hashes": (
                (source_id, source.body_sha256 if receipt_body_hash is None else receipt_body_hash),
            ),
            "verified_claim_ids": verified_claim_ids,
            "verified_binding_indices": verified_indices,
        }
    )
    return ValidatedEnvelopeSnapshot(canonical_bytes, envelope_hash), receipt, context


def _listing_source_material(
    run_id,
    symbol,
    *,
    locator_overrides=None,
    body_overrides=None,
    source_id_overrides=None,
):
    source_ids = {
        "sec": "{}-trusted-sec".format(run_id),
        "nasdaq": "{}-trusted-nasdaq".format(run_id),
        "yahoo": "{}-trusted-yahoo".format(run_id),
    }
    locators = {
        "sec": (
            "https://www.sec.gov/Archives/edgar/data/1234567890/"
            "123456789012345678/cover.htm"
        ),
        "nasdaq": "https://www.nasdaq.com/market-activity/stocks/{}/analyst-research".format(
            symbol.lower()
        ),
        "yahoo": "https://finance.yahoo.com/quote/{}/".format(symbol),
    }
    bodies = {
        "sec": (
            "Example Holdings, Inc.\r\n"
            "(Exact name of registrant as specified in its charter)\r\n"
            "\r\n"
            "| Title of each class | Trading Symbol(s) | "
            "Name of each exchange on which registered |\r\n"
            "| --- | --- | --- |\r\n"
            "| Ordinary shares, no par value | {} | "
            "The Nasdaq Stock Market LLC |\r\n"
            "\r\n"
            "A synthetic event was reported.\r\n"
        ).format(symbol),
        "nasdaq": "# Example Holdings, Inc. Ordinary Shares ({})\n".format(symbol),
        "yahoo": "NasdaqGS - Delayed Quote•USD\r\n\r\n# Example Holdings, Inc. ({})\r\n".format(
            symbol
        ),
    }
    for role, locator in (locator_overrides or {}).items():
        locators[role] = locator
    for role, body in (body_overrides or {}).items():
        bodies[role] = body
    for role, source_id in (source_id_overrides or {}).items():
        source_ids[role] = source_id
    source_order = tuple(
        (source_ids[role], locators[role]) for role in ("sec", "nasdaq", "yahoo")
    )
    bodies_by_url = {locators[role]: bodies[role] for role in ("sec", "nasdaq", "yahoo")}
    return source_ids, source_order, bodies, bodies_by_url


def _listing_identity_case(
    run_id="listing-preparer-run",
    symbol="Z7QX",
    *,
    locator_overrides=None,
    body_overrides=None,
    source_id_overrides=None,
    verified_hypothesis_ids=None,
    verified_binding_indices=(0,),
    duplicate_entity_binding=False,
):
    source_ids, source_order, bodies, bodies_by_url = _listing_source_material(
        run_id,
        symbol,
        locator_overrides=locator_overrides,
        body_overrides=body_overrides,
        source_id_overrides=source_id_overrides,
    )
    run_input, context = _context_and_run_input(
        run_id,
        "Assess a synthetic listing event.",
        source_order,
        bodies_by_url,
        HostGrounderRunInputBounds(20_000, 10_000, 20),
    )
    hypothesis_id = "hypothesis-generated-{}".format(run_id)
    field_bindings = [
        {
            "field_path": "/hypotheses/0/underlying_symbol",
            "semantic_role": "entity",
        }
    ]
    if duplicate_entity_binding:
        field_bindings.append(dict(field_bindings[0]))
    envelope = {
        "schema_version": "grounder-output-v0.1",
        "stage": "semantic",
        "request_id": run_id,
        "claims": [],
        "hypotheses": [
            {"hypothesis_id": hypothesis_id, "underlying_symbol": symbol}
        ],
        "coverage": [],
        "field_bindings": field_bindings,
    }
    canonical_bytes = json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    envelope_hash = hashlib.sha256(canonical_bytes).hexdigest()
    receipt = MappingProxyType(
        {
            "schema_version": "semantic-validation-v0.2",
            "run_id": run_id,
            "canonical_input_hash": run_input.canonical_input_hash,
            "envelope_hash": envelope_hash,
            "source_body_hashes": tuple(
                (source_id, context.source_bodies[source_id].body_sha256)
                for source_id in sorted(context.source_bodies)
            ),
            "verified_claim_ids": (),
            "verified_hypothesis_ids": (
                (hypothesis_id,)
                if verified_hypothesis_ids is None
                else verified_hypothesis_ids
            ),
            "verified_binding_indices": verified_binding_indices,
        }
    )
    return (
        ValidatedEnvelopeSnapshot(canonical_bytes, envelope_hash),
        receipt,
        context,
        source_ids,
        source_order,
        bodies,
        bodies_by_url,
        hypothesis_id,
        run_input,
    )


def _sec_primary_raw_cover_html(symbol="ACME", share_class="Common Stock"):
    return (
        "<html><body><p>Example Holdings, Inc.</p>"
        "<p>(Exact name of registrant as specified in its charter)</p>"
        "<table><tr><th>Title of each class</th><th></th>"
        "<th>Trading Symbol(s)</th><th></th>"
        "<th>Name of each exchange on which registered</th></tr>"
        "<tr><td>" + share_class + "</td><td></td><td>" + symbol + "</td><td></td>"
        "<td>The Nasdaq&#13;Capital Market</td></tr></table></body></html>"
    ).encode("utf-8")


def _sec_v04_admission(
    paragraphs, *, registrant="Example Holdings, Inc.", admit=True
):
    cover = _sec_primary_raw_cover_html().replace(
        b"Example Holdings, Inc.", registrant.encode("utf-8")
    )
    addition = "".join("<p>{}</p>".format(value) for value in paragraphs).encode("utf-8")
    raw_html = cover.replace(b"</body></html>", addition + b"</body></html>")

    def transport(locator, _address, _timeout, _max_bytes):
        if locator == _SEC_LOCATOR:
            return _Reply(
                200, {"Content-Type": "text/html; charset=UTF-8"}, raw_html
            )
        return _Reply(404, {"Content-Type": "text/plain"}, b"synthetic absent")

    client = _SourceAdmissionClient(
        timeout_seconds=2.0,
        max_response_bytes=200_000,
        byte_budget=1_000_000,
        _transport=transport,
        _resolver=lambda _host, _port: ("93.184.216.34",),
        _clock=lambda: _NOW,
    )
    if not admit:
        return client, None
    batch = client.admit_candidates((_SEC_LOCATOR,))
    if len(batch.admissions) != 1:
        raise AssertionError("synthetic v0.4 SEC HTML admission did not succeed")
    return client, batch.admissions[0]


def _sec_v04_fact_case(
    *,
    paragraph=_V04_SEC_SENTENCE,
    extra_paragraphs=(),
    claim_text=None,
    model_date="2026-09-21",
    binding_role="date",
    binding_status="supported",
    binding_start_override=None,
    binding_end_override=None,
    verified_claim=True,
    verified_binding=True,
    include_admission=True,
    admission_override=None,
    return_inputs=False,
):
    _client, authentic_admission = _sec_v04_admission(
        (paragraph,) + tuple(extra_paragraphs)
    )
    body = authentic_admission.parsed_body
    source_id = authentic_admission.source_id
    source = HostSourceBody(
        body=body,
        body_sha256=authentic_admission.parsed_body_sha256,
        final_locator=authentic_admission.final_locator,
        retrieved_at=authentic_admission.retrieved_at,
    )
    paragraph_span = next(
        span
        for span in _line_paragraph_spans(body)
        if paragraph in body[slice(*span)]
    )
    quote = body[slice(*paragraph_span)]
    selected_text = paragraph if claim_text is None else claim_text
    binding = {
        "field_path": "/claims/0/event_date",
        "source_id": source_id,
        "quote": quote,
        "start": paragraph_span[0],
        "end": paragraph_span[1],
        "semantic_role": binding_role,
        "status": binding_status,
    }
    if binding_start_override is not None:
        binding["start"] = binding_start_override
    if binding_end_override is not None:
        binding["end"] = binding_end_override
    envelope = {
        "schema_version": "grounder-output-v0.1",
        "stage": "semantic",
        "request_id": "v04-sec-html-case",
        "claims": [
            {
                "claim_id": "fact-1",
                "kind": "observed_fact",
                "source_id": source_id,
                "locator": source.final_locator,
                "quote": quote,
                "text": selected_text,
                "event_date": model_date,
            }
        ],
        "hypotheses": [],
        "coverage": [],
        "field_bindings": [binding],
    }
    canonical_bytes = json.dumps(
        envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    envelope_hash = _digest(canonical_bytes.decode("utf-8"))
    context = HostBuildContext(
        raw_input=UserEventInput(_RAW_INPUT),
        submission_id="v04-sec-html-case",
        event_id="v04-sec-html-case",
        producer_id="convexity-hunter-event-grounder",
        producer_version="v0.1",
        observed_at=_NOW,
        source_bodies=MappingProxyType({source_id: source}),
        run_id="v04-sec-html-case",
        canonical_input_hash="b" * 64,
    )
    receipt = MappingProxyType(
        {
            "schema_version": "semantic-validation-v0.2",
            "run_id": context.run_id,
            "canonical_input_hash": context.canonical_input_hash,
            "envelope_hash": envelope_hash,
            "source_body_hashes": ((source_id, source.body_sha256),),
            "verified_claim_ids": ("fact-1",) if verified_claim else (),
            "verified_binding_indices": (0,) if verified_binding else (),
        }
    )
    snapshot = ValidatedEnvelopeSnapshot(canonical_bytes, envelope_hash)
    records = (
        authentic_admission if admission_override is None else admission_override,
    ) if include_admission else ()
    preparer = _make_listing_source_preparer(
        (source_id,), admission_records=records
    )
    prepared = preparer(snapshot, receipt, context)
    if return_inputs:
        return prepared, context, authentic_admission, snapshot, receipt, records
    return prepared, context, authentic_admission


def _sec_primary_composite_records(
    symbol="ACME", *, yahoo_override=None, share_class="Common Stock",
    cover_html_override=None,
):
    cover_html = cover_html_override or _sec_primary_raw_cover_html(symbol, share_class)
    reference_locator = "https://www.sec.gov/files/company_tickers_exchange.json"
    reference_body = json.dumps(
        {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[320193, "Reference Unicode — Name", symbol, "Nasdaq"]],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    yahoo_locator = "https://finance.yahoo.com/quote/{}/".format(symbol)
    yahoo_body = (yahoo_override or (
        "<html><body><div>NasdaqCM - Nasdaq Real Time Price USD</div>"
        "<h1>Example Holdings, Inc. (" + symbol + ")</h1></body></html>"
    )).encode("utf-8")
    responses = {
        _SEC_LOCATOR: _Reply(200, {"Content-Type": "text/html; charset=UTF-8"}, cover_html),
        reference_locator: _Reply(200, {"Content-Type": "application/json"}, reference_body),
        yahoo_locator: _Reply(200, {"Content-Type": "text/html; charset=UTF-8"}, yahoo_body),
    }
    calls = []

    def transport(locator, _address, _timeout, _max_bytes):
        calls.append(locator)
        return responses[locator]

    client = _SourceAdmissionClient(
        timeout_seconds=2.0,
        max_response_bytes=1_500_000,
        byte_budget=2_500_000,
        _transport=transport,
        _resolver=lambda _host, _port: ("93.184.216.34",),
        _clock=lambda: _NOW,
    )
    initial = client.admit_candidates((_SEC_LOCATOR,))
    composite = client._admit_sec_reference_and_yahoo((symbol,), initial.admissions)
    checked = client._revalidate_sec_composite(
        composite.admissions,
        (symbol,),
        max_raw_bytes=1_500_000,
        max_parsed_bytes=1_500_000,
    )
    return client, checked, calls


def _sec_primary_listing_case(
    run_id="sec-primary-listing-run",
    *,
    yahoo_override=None,
    share_class="Common Stock",
    cover_html_override=None,
    **identity_options
):
    base = _listing_identity_case(run_id=run_id, symbol="ACME", **identity_options)
    snapshot, receipt, context, _ids, _order, _bodies, _by_url, hypothesis_id, run_input = base
    client, records, calls = _sec_primary_composite_records(
        "ACME", yahoo_override=yahoo_override, share_class=share_class,
        cover_html_override=cover_html_override,
    )
    if records is None:
        raise AssertionError("synthetic SEC-primary composite did not issue")
    source_bodies = {
        record.source_id: HostSourceBody(
            body=record.parsed_body,
            body_sha256=record.parsed_body_sha256,
            final_locator=record.final_locator,
            retrieved_at=record.retrieved_at,
        )
        for record in records
    }
    context = replace(context, source_bodies=source_bodies)
    receipt_values = dict(receipt)
    receipt_values["source_body_hashes"] = tuple(
        (source_id, source_bodies[source_id].body_sha256)
        for source_id in sorted(source_bodies)
    )
    receipt = MappingProxyType(receipt_values)
    return snapshot, receipt, context, client, records, calls, hypothesis_id, run_input


def _listing_runtime_wires(
    run_id, symbol, source_order, bodies_by_url, config, *, normal_recipe=True
):
    run_input, context = _context_and_run_input(
        run_id,
        "Assess a synthetic listing event.",
        source_order,
        bodies_by_url,
        config.run_input_bounds,
        normal_recipe=normal_recipe,
    )
    catalog = build_host_evidence_catalog(
        run_id,
        run_input.canonical_input_hash,
        context.source_bodies,
        max_catalog_entries=config.max_catalog_entries,
        max_catalog_bytes=config.max_catalog_bytes,
        max_catalog_paragraphs=config.max_catalog_paragraphs,
        max_string_bytes=run_input.bounds.max_string_bytes,
        max_array_items=run_input.bounds.max_array_items,
    )
    claim_id = "claim-generated-{}".format(run_id)
    hypothesis_id = "hypothesis-generated-{}".format(run_id)
    claim_quote = "A synthetic event was reported."
    sec_source_id = source_order[0][0]
    claim_entry = next(
        entry
        for entry in catalog.entries
        if entry.quote.rstrip("\r\n") == claim_quote
    )
    symbol_entry = next(
        entry
        for entry in catalog.entries
        if entry.source_id == sec_source_id and symbol in entry.quote
    )
    coverage = [{
        "subquestion_id": "user_event_input",
        "status": "supported",
        "claim_ids": [claim_id],
        "gap": None,
    }]
    if normal_recipe:
        coverage.append({
            "subquestion_id": _EVENT_FACT_ANCHOR_SUBQUESTION_ID,
            "status": "supported",
            "claim_ids": [claim_id],
            "gap": None,
        })
    producer = {
        "schema_version": "grounder-output-v0.3",
        "stage": "semantic",
        "request_id": run_id,
        "claims": [
            {
                "claim_id": claim_id,
                "kind": "observed_fact",
                "evidence_id": claim_entry.evidence_id,
                "text": claim_quote,
                "entity_refs": [],
                "event_date": None,
                "published_at": None,
                "dependency_claim_ids": [],
                "uncertainty": [],
                "falsification_conditions": [],
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": hypothesis_id,
                "underlying_symbol": symbol,
                "impact_path": None,
                "distribution_mode": None,
                "distribution_hypothesis": None,
                "expected_window": None,
                "reassessment": None,
                "supporting_claim_ids": [claim_id],
                "contradicting_claim_ids": [],
                "contradiction_review": None,
                "uncertainties": [],
                "falsification_conditions": [],
            }
        ],
        "coverage": coverage,
        "field_bindings": [
            {
                "field_path": "/hypotheses/0/underlying_symbol",
                "evidence_id": symbol_entry.evidence_id,
                "semantic_role": "entity",
                "status": "supported",
            }
        ],
    }
    normalized, normalized_bytes = parse_grounder_output_v0_3(
        json.dumps(producer, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        config.max_json_bytes,
        max_string_bytes=run_input.bounds.max_string_bytes,
        max_array_items=run_input.bounds.max_array_items,
        run_id=run_id,
        canonical_input_hash=run_input.canonical_input_hash,
        source_bodies=context.source_bodies,
        catalog=catalog,
    )
    event_ref = {"evidence_id": claim_entry.evidence_id}
    symbol_ref = {"evidence_id": symbol_entry.evidence_id}
    semantic = {
        "schema_version": "semantic-verdict-v0.3",
        "run_id": run_id,
        "envelope_hash": hashlib.sha256(normalized_bytes).hexdigest(),
        "source_body_hashes": [
            {"source_id": source_id, "sha256": source.body_sha256}
            for source_id, source in sorted(context.source_bodies.items())
        ],
        "claims": [
            {
                "claim_id": claim_id,
                "outcome": "supported",
                "rationale": "Synthetic registered text supports the event claim.",
                "evidence_refs": [event_ref],
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": hypothesis_id,
                "outcome": "supported",
                "rationale": "Synthetic validator confirms the hypothesis record.",
                "evidence_refs": [event_ref],
            }
        ],
        "field_bindings": [
            {
                "index": 0,
                "outcome": "supported",
                "rationale": "Synthetic validator confirms the exact symbol binding.",
                "evidence_refs": [symbol_ref],
            }
        ],
        "coverage": [
            {
                "index": 0,
                "subquestion_id": "user_event_input",
                "outcome": "supported",
                "rationale": "Synthetic registered text addresses the prompt.",
                "evidence_refs": [event_ref],
            }
        ] + ([{
            "index": 1,
            "subquestion_id": _EVENT_FACT_ANCHOR_SUBQUESTION_ID,
            "outcome": "supported",
            "rationale": "Synthetic registered text uniquely identifies the event fact.",
            "evidence_refs": [event_ref],
        }] if normal_recipe else []),
    }
    return (
        json.dumps(producer, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        json.dumps(semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        normalized,
    )


class _SyntheticModelTransport:
    def __init__(self, discovery_content, semantic_content):
        self.contents = {
            "fixture-discovery": discovery_content,
            "fixture-semantic": semantic_content,
        }
        self.calls = []

    def __call__(self, request, _timeout):
        payload = json.loads(request.data.decode("utf-8"))
        self.calls.append(payload)
        model = payload["model"]
        content = self.contents[model]
        if type(content) is list:
            if not content:
                raise AssertionError("synthetic model output sequence was exhausted")
            content = content.pop(0)
        return _SyntheticResponse(
            {
                "id": "synthetic-" + model,
                "model": model,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
            }
        )


def _config(*, max_source_body_bytes=20_000, source_order=_SEARCH_ORDER):
    return HostEventGrounderConfig(
        source=TavilySourceConfig(
            credential_ref=TavilyCredentialRef(env_name="SYNTHETIC_TAVILY_KEY"),
            paygo_off_confirmed=True,
            request_budget=2,
            credit_budget=2,
            max_request_bytes=20_000,
            max_response_bytes=200_000,
            timeout_seconds=2.0,
            max_search_results=len(source_order),
            max_extract_urls=len(source_order),
        ),
        discovery_model=ModelRuntimeConfig(
            provider="deepseek",
            model="fixture-discovery",
            base_endpoint="https://api.deepseek.com",
            role="discovery",
            capabilities=("json_mode",),
            timeout_seconds=2.0,
            request_budget=1,
            max_tokens=2_000,
            max_input_bytes=500_000,
            max_output_bytes=200_000,
            remote_enabled=True,
            fee_authorized=True,
            json_mode=True,
            thinking_enabled=False,
        ),
        discovery_credential=ModelCredential(env_name="SYNTHETIC_DISCOVERY_KEY"),
        semantic_model=ModelRuntimeConfig(
            provider="deepseek",
            model="fixture-semantic",
            base_endpoint="https://api.deepseek.com",
            role="semantic",
            capabilities=("json_mode",),
            timeout_seconds=2.0,
            request_budget=1,
            max_tokens=2_000,
            max_input_bytes=500_000,
            max_output_bytes=200_000,
            remote_enabled=True,
            fee_authorized=True,
            json_mode=True,
            thinking_enabled=False,
        ),
        semantic_credential=ModelCredential(env_name="SYNTHETIC_SEMANTIC_KEY"),
        run_input_bounds=HostGrounderRunInputBounds(20_000, 10_000, 10),
        max_json_bytes=100_000,
        max_source_body_bytes=max_source_body_bytes,
        max_catalog_entries=64,
        max_catalog_bytes=32_768,
        max_catalog_paragraphs=128,
    )


class HostEventGrounderTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "SYNTHETIC_TAVILY_KEY": "synthetic-only-key",
                "SYNTHETIC_DISCOVERY_KEY": "synthetic-only-key",
                "SYNTHETIC_SEMANTIC_KEY": "synthetic-only-key",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.admission_factory = patch(
            "convexity_hunter.host_event._create_source_admission_client",
            side_effect=lambda **_kwargs: _NoNetworkAdmissionClient(),
        )
        self.admission_factory.start()
        self.addCleanup(self.admission_factory.stop)

    def test_factory_returns_frozen_callback_signature_and_redacts_config(self):
        config = _config()
        callback = create_event_grounder(config, repo_root=_ROOT)
        self.assertIs(
            inspect.getclosurevars(callback).nonlocals["context_preparer"],
            _retain_unknown_context_v0_3,
        )
        self.assertEqual(
            tuple(inspect.signature(callback).parameters),
            ("raw_input", "run_id", "bounds"),
        )
        self.assertEqual(
            str(inspect.signature(HostGrounderEvidenceCatalogRuntimeResult)),
            "(build_result: 'HostBuildResult', discovery_call: 'HostGrounderCallSummary', "
            "semantic_call: 'HostGrounderCallSummary', audit: 'HostEvidenceCatalogAudit') -> None",
        )
        self.assertNotIn("SYNTHETIC", repr(config))
        with self.assertRaisesRegex(TypeError, "host_context_preparer"):
            create_event_grounder(config, repo_root=_ROOT, host_context_preparer=object())

    def test_default_event_semantic_transport_retries_same_body_once(self):
        run_id = "semantic-transport-retry-event"
        config = _config()
        config = replace(
            config,
            semantic_model=replace(config.semantic_model, request_budget=2),
        )
        discovery, semantic, _normalized = _model_outputs(
            run_id, _RAW_INPUT, _SEARCH_ORDER, _BODY_BY_URL, config
        )

        class ScriptedTransport:
            def __init__(self):
                self.calls = []
                self.semantic_calls = 0

            def __call__(self, request, timeout):
                payload = json.loads(request.data.decode("utf-8"))
                model = payload["model"]
                self.calls.append((model, request.data, timeout))
                if model == "fixture-semantic":
                    self.semantic_calls += 1
                    if self.semantic_calls == 1:
                        raise URLError("private synthetic network detail")
                    content = semantic
                else:
                    content = discovery
                return _SyntheticResponse({
                    "id": "synthetic-" + model,
                    "model": model,
                    "choices": [{
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 20,
                        "total_tokens": 30,
                    },
                })

        model_transport = ScriptedTransport()
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=_SyntheticSourceTransport(),
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        result = callback(
            _RAW_INPUT,
            run_id=run_id,
            bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
        )

        semantic_calls = [call for call in model_transport.calls if call[0] == "fixture-semantic"]
        self.assertEqual(len(model_transport.calls), 3)
        self.assertEqual(len(semantic_calls), 2)
        self.assertEqual(semantic_calls[0][1], semantic_calls[1][1])
        self.assertEqual(
            hashlib.sha256(semantic_calls[0][1]).hexdigest(),
            result._semantic_transport["request_body_sha256"],
        )
        self.assertTrue(all(0 < call[2] <= config.semantic_model.timeout_seconds for call in semantic_calls))
        audit = result._semantic_transport
        self.assertEqual(audit["attempt_limit"], 2)
        self.assertEqual(
            [row["transport_code"] for row in audit["attempts"]],
            ["NETWORK_ERROR", None],
        )
        self.assertEqual(
            [row["outcome"] for row in audit["attempts"]],
            ["transport_failed", "response_received"],
        )
        self.assertEqual(
            audit["output_reservation_limit_tokens"],
            2 * config.semantic_model.max_tokens,
        )
        self.assertEqual(audit["attempts"][1]["usage"]["total_tokens"], 30)
        self.assertIsNotNone(result._event_fact_anchor_outcome)

    def test_default_event_semantic_http_failure_is_not_retried(self):
        run_id = "semantic-transport-http-no-retry"
        config = _config()
        config = replace(
            config,
            semantic_model=replace(config.semantic_model, request_budget=2),
        )
        discovery, _semantic, _normalized = _model_outputs(
            run_id, _RAW_INPUT, _SEARCH_ORDER, _BODY_BY_URL, config
        )

        class HttpFailureTransport:
            def __init__(self):
                self.semantic_calls = 0

            def __call__(self, request, _timeout):
                payload = json.loads(request.data.decode("utf-8"))
                if payload["model"] == "fixture-semantic":
                    self.semantic_calls += 1
                    raise HTTPError(request.full_url, 503, "synthetic", {}, None)
                return _SyntheticResponse({
                    "id": "synthetic-discovery",
                    "model": "fixture-discovery",
                    "choices": [{
                        "message": {"role": "assistant", "content": discovery},
                        "finish_reason": "stop",
                    }],
                })

        model_transport = HttpFailureTransport()
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=_SyntheticSourceTransport(),
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            callback(
                _RAW_INPUT,
                run_id=run_id,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )

        self.assertEqual(raised.exception.code, "SEMANTIC_CALL_FAILED")
        self.assertEqual(model_transport.semantic_calls, 1)
        audit = raised.exception.semantic_transport
        self.assertEqual(len(audit["attempts"]), 1)
        self.assertEqual(audit["attempts"][0]["transport_code"], "HTTP_ERROR")
        self.assertEqual(audit["attempts"][0]["http_status"], 503)

    def test_custom_context_preparer_keeps_semantic_call_single_attempt(self):
        run_id = "semantic-transport-custom-route-no-retry"
        config = _config()
        config = replace(
            config,
            semantic_model=replace(config.semantic_model, request_budget=2),
        )
        discovery, _semantic, _normalized = _model_outputs(
            run_id,
            _RAW_INPUT,
            _SEARCH_ORDER,
            _BODY_BY_URL,
            config,
            normal_recipe=False,
        )

        class CustomRouteTransport:
            def __init__(self):
                self.semantic_calls = 0

            def __call__(self, request, _timeout):
                payload = json.loads(request.data.decode("utf-8"))
                if payload["model"] == "fixture-semantic":
                    self.semantic_calls += 1
                    raise URLError("private custom-route network detail")
                return _SyntheticResponse({
                    "id": "synthetic-discovery",
                    "model": "fixture-discovery",
                    "choices": [{
                        "message": {"role": "assistant", "content": discovery},
                        "finish_reason": "stop",
                    }],
                })

        model_transport = CustomRouteTransport()
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=_SyntheticSourceTransport(),
            discovery_transport=model_transport,
            semantic_transport=model_transport,
            host_context_preparer=_retain_unknown_context_v0_3,
        )

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            callback(
                _RAW_INPUT,
                run_id=run_id,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )

        self.assertEqual(model_transport.semantic_calls, 1)
        self.assertEqual(raised.exception.code, "SEMANTIC_CALL_FAILED")
        self.assertIsNone(raised.exception.semantic_transport)

    def test_independent_anchor_gate_selects_only_its_supported_fact_row(self):
        coverage = [
            {
                "subquestion_id": "user_event_input",
                "status": "unresolved",
                "claim_ids": [],
                "gap": "Economic materiality remains unresolved.",
            },
            {
                "subquestion_id": _EVENT_FACT_ANCHOR_SUBQUESTION_ID,
                "status": "supported",
                "claim_ids": ["fact-1"],
                "gap": None,
            },
        ]
        outcomes = (
            (0, "user_event_input", "unresolved", "Research question remains incomplete."),
            (1, _EVENT_FACT_ANCHOR_SUBQUESTION_ID, "supported", "Unique source-backed event fact."),
        )
        snapshot, receipt, context = _source_fact_case(
            extra_claim=True,
            coverage_items=coverage,
            coverage_outcomes=outcomes,
        )

        self.assertEqual(
            _event_fact_anchor_claim_id(snapshot, receipt, context), "fact-1"
        )
        prepared, selected = _retain_unknown_context_v0_5(
            snapshot, receipt, context, {}
        )
        self.assertEqual(selected, "fact-1")
        self.assertEqual(prepared.event_description_binding, "fact-1")
        self.assertIsNone(prepared.event_date_range)
        self.assertIs(prepared.source_bodies["sec-fact"], context.source_bodies["sec-fact"])
        bad_index_receipt = dict(receipt)
        bad_index_receipt["coverage_outcomes"] = (
            outcomes[0],
            (True, _EVENT_FACT_ANCHOR_SUBQUESTION_ID, "supported", "Unique source-backed event fact."),
        )
        self.assertIsNone(
            _event_fact_anchor_claim_id(
                snapshot, MappingProxyType(bad_index_receipt), context
            )
        )

    def test_independent_anchor_gate_does_not_use_singleton_or_research_fallback(self):
        coverage = [
            {
                "subquestion_id": "user_event_input",
                "status": "supported",
                "claim_ids": ["fact-1"],
                "gap": None,
            },
            {
                "subquestion_id": _EVENT_FACT_ANCHOR_SUBQUESTION_ID,
                "status": "unresolved",
                "claim_ids": [],
                "gap": "No unique event anchor.",
            },
        ]
        outcomes = (
            (0, "user_event_input", "supported", "Research coverage supports the fact."),
            (1, _EVENT_FACT_ANCHOR_SUBQUESTION_ID, "unresolved", "No unique event anchor."),
        )
        snapshot, receipt, context = _source_fact_case(
            coverage_items=coverage,
            coverage_outcomes=outcomes,
        )
        prepared, selected = _retain_unknown_context_v0_5(
            snapshot, receipt, context, {}
        )
        self.assertIsNone(selected)
        self.assertIsNone(prepared.event_description_binding)
        self.assertIsNone(_event_fact_anchor_claim_id(snapshot, receipt, context))

    def test_independent_anchor_gate_preserves_preexisting_binding_without_audit_selection(self):
        coverage = [
            {"subquestion_id": "user_event_input", "status": "unresolved", "claim_ids": [], "gap": "gap"},
            {"subquestion_id": _EVENT_FACT_ANCHOR_SUBQUESTION_ID, "status": "supported", "claim_ids": ["fact-1"], "gap": None},
        ]
        outcomes = (
            (0, "user_event_input", "unresolved", "gap"),
            (1, _EVENT_FACT_ANCHOR_SUBQUESTION_ID, "supported", "supported"),
        )
        snapshot, receipt, context = _source_fact_case(
            description="caller-owned-description",
            coverage_items=coverage,
            coverage_outcomes=outcomes,
        )
        prepared, selected = _retain_unknown_context_v0_5(
            snapshot, receipt, context, {}
        )
        self.assertIsNone(selected)
        self.assertEqual(prepared.event_description_binding, "caller-owned-description")

    def test_private_world_query_factory_preserves_full_context_and_isolates_runs(self):
        config = _config()
        queries = ("q" * 400, "Assess the second ACME filing.")
        self.assertEqual(len(queries[0]), 400)
        contexts = tuple(
            query + "\n\nprovisional lead context:\n" + ("lead-context-" * 45)
            for query in queries
        )
        self.assertTrue(all(len(context) > 400 for context in contexts))
        bodies = dict(_BODY_BY_URL)
        discovery_outputs = []
        semantic_outputs = []
        run_ids = ("world-query-run-one", "world-query-run-two")
        for run_id, full_context in zip(run_ids, contexts):
            discovery, semantic, _normalized = _model_outputs(
                run_id,
                full_context,
                _SEARCH_ORDER,
                bodies,
                config,
            )
            discovery_outputs.append(discovery)
            semantic_outputs.append(semantic)
        source_transport = _SyntheticSourceTransport(body_overrides=bodies)
        model_transport = _SyntheticModelTransport(
            discovery_outputs, semantic_outputs
        )
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )
        self.assertEqual(
            tuple(inspect.signature(callback).parameters),
            ("raw_input", "run_id", "bounds"),
        )
        query_factory = callback._world_source_query_factory
        bound_callbacks = tuple(query_factory(query) for query in queries)
        self.assertTrue(
            all(
                tuple(inspect.signature(bound).parameters)
                == ("raw_input", "run_id", "bounds")
                for bound in bound_callbacks
            )
        )

        results = tuple(
            bound(
                full_context,
                run_id=run_id,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
            for bound, full_context, run_id in zip(
                bound_callbacks, contexts, run_ids
            )
        )

        self.assertEqual(
            [payload["query"] for _url, payload in source_transport.calls],
            [queries[0], queries[0], queries[1], queries[1]],
        )
        self.assertEqual(len(source_transport.calls), 4)
        self.assertEqual(len(model_transport.calls), 4)
        def contains_full_context(value, full_context):
            if type(value) is str:
                if full_context in value:
                    return True
                try:
                    decoded = json.loads(value)
                except (TypeError, ValueError):
                    return False
                return contains_full_context(decoded, full_context)
            if type(value) is dict:
                return any(
                    contains_full_context(item, full_context)
                    for item in value.values()
                )
            if type(value) in (list, tuple):
                return any(
                    contains_full_context(item, full_context) for item in value
                )
            return False

        for query, full_context, run_id, result in zip(
            queries, contexts, run_ids, results
        ):
            with self.subTest(run_id=run_id):
                self.assertTrue(
                    any(
                        contains_full_context(call, full_context)
                        for call in model_transport.calls
                    )
                )
                self.assertEqual(
                    result.build_result.context.raw_input.description,
                    full_context,
                )
                expected_hash = HostGrounderRunInput(
                    run_id,
                    UserEventInput(full_context),
                    (
                        HostGrounderSubquestion("user_event_input", full_context),
                        HostGrounderSubquestion(
                            _EVENT_FACT_ANCHOR_SUBQUESTION_ID,
                            _EVENT_FACT_ANCHOR_QUESTION,
                        ),
                    ),
                    config.run_input_bounds,
                ).canonical_input_hash
                self.assertEqual(
                    result.build_result.context.canonical_input_hash,
                    expected_hash,
                )
                self.assertEqual(
                    result.build_result.semantic_validation.receipt[
                        "canonical_input_hash"
                    ],
                    expected_hash,
                )

    def test_private_world_query_factory_rejects_invalid_bound_queries_before_calls(self):
        source_transport = _SyntheticSourceTransport()
        model_transport = _SyntheticModelTransport("{}", "{}")
        callback = create_event_grounder(
            _config(),
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )
        for query in ("q" * 401, " q", "q ", "", None, "\ud800"):
            with self.subTest(query=repr(query)):
                with self.assertRaises(HostGrounderRuntimeError) as raised:
                    callback._world_source_query_factory(query)
                self.assertEqual(raised.exception.code, "SOURCE_QUERY_INVALID")
        self.assertEqual(source_transport.calls, [])
        self.assertEqual(model_transport.calls, [])

    def test_default_event_callback_keeps_the_original_input_as_source_query(self):
        query = "Assess the reported ACME filing."
        config = _config()
        bodies = dict(_BODY_BY_URL)
        discovery, semantic, _normalized = _model_outputs(
            "default-event-query-run",
            query,
            _SEARCH_ORDER,
            bodies,
            config,
        )
        source_transport = _SyntheticSourceTransport(body_overrides=bodies)
        model_transport = _SyntheticModelTransport(discovery, semantic)
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        callback(
            query,
            run_id="default-event-query-run",
            bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
        )

        self.assertEqual(
            [payload["query"] for _url, payload in source_transport.calls],
            [query, query],
        )

    def test_default_context_preparer_binds_unique_sec_fact_and_exact_date_evidence(self):
        snapshot, receipt, context = _source_fact_case()
        source = context.source_bodies["sec-fact"]
        prepared = _retain_unknown_context(snapshot, receipt, context)

        self.assertIsNot(prepared, context)
        self.assertEqual(prepared.event_description_binding, "fact-1")
        self.assertIs(prepared.raw_input, context.raw_input)
        self.assertIs(prepared.source_bodies["sec-fact"], source)
        self.assertEqual(prepared.underlying_bindings, {})
        self.assertEqual(prepared.event_date_range.start_date, datetime.date(2026, 10, 3))
        self.assertEqual(prepared.event_date_range.end_date, datetime.date(2026, 10, 3))
        methodology = json.loads(prepared.event_date_range.methodology)
        self.assertEqual(
            methodology["rule_version"],
            "host-event-source-facts-v0.1/sec-8-k-occurrence-date",
        )
        self.assertEqual(methodology["source_id"], "sec-fact")
        self.assertEqual(methodology["body_sha256"], source.body_sha256)
        self.assertEqual(methodology["locator"], _SEC_LOCATOR)
        self.assertEqual(
            source.body[methodology["start"]:methodology["end"]], _SEC_SENTENCE
        )

    def test_v02_coverage_selects_one_fact_independent_of_claim_and_id_order(self):
        coverage = [
            {
                "subquestion_id": "user_event_input",
                "status": "supported",
                "claim_ids": ["interpretation-1", "fact-1"],
                "gap": None,
            }
        ]
        outcomes = ((0, "user_event_input", "supported", "Verified event coverage."),)
        first_case = _source_fact_case(
            extra_claim=True,
            extra_interpretation=True,
            coverage_items=coverage,
            coverage_outcomes=outcomes,
        )
        snapshot, receipt, context = first_case
        reordered = _source_fact_case(
            extra_claim=True,
            extra_interpretation=True,
            coverage_items=[dict(coverage[0], claim_ids=["fact-1", "interpretation-1"])],
            coverage_outcomes=outcomes,
            claim_order=("interpretation-1", "fact-2", "fact-1"),
        )

        prepared = _retain_unknown_context_v0_2(*first_case)
        reordered_prepared = _retain_unknown_context_v0_2(*reordered)
        for result in (prepared, reordered_prepared):
            self.assertEqual(result.event_description_binding, "fact-1")
            self.assertEqual(result.event_date_range.start_date, datetime.date(2026, 10, 3))
            self.assertEqual(result.event_date_range.end_date, datetime.date(2026, 10, 3))
        self.assertEqual(
            prepared.event_date_range.methodology,
            reordered_prepared.event_date_range.methodology,
        )
        self.assertEqual(
            json.loads(prepared.event_date_range.methodology)["rule_version"],
            "host-event-source-facts-v0.2/sec-8-k-occurrence-date",
        )

        # A caller-supplied description is already the anchor; another fact
        # cannot lend it a date, and the supplied string object is retained.
        supplied = "".join(("fact", "-2"))
        supplied_context = replace(context, event_description_binding=supplied)
        supplied_result = _retain_unknown_context_v0_2(
            snapshot, receipt, supplied_context
        )
        self.assertIs(supplied_result.event_description_binding, supplied)
        self.assertIsNone(supplied_result.event_date_range)

    def test_v02_covered_multi_fact_selection_fails_closed_on_bad_roots(self):
        good = {
            "subquestion_id": "user_event_input",
            "status": "supported",
            "claim_ids": ["fact-1"],
            "gap": None,
        }
        supported = ((0, "user_event_input", "supported", "Verified event coverage."),)
        cases = (
            ("unresolved-envelope", [dict(good, status="unresolved")], supported),
            ("non-null-gap", [dict(good, gap="still open")], supported),
            ("duplicate-claim-id", [dict(good, claim_ids=["fact-1", "fact-1"])], supported),
            ("malformed-claim-id", [dict(good, claim_ids=["fact-1", 7])], supported),
            ("unverified-claim-id", [dict(good, claim_ids=["missing"])], supported),
            ("ambiguous-facts", [dict(good, claim_ids=["fact-1", "fact-2"])], supported),
            ("rejected-receipt", [good], ((0, "user_event_input", "unresolved", "Not supported."),)),
            ("missing-outcome", [good], ()),
            ("mismatched-outcome-id", [good], ((0, "other-question", "supported", "Mismatch."),)),
            ("malformed-outcome", [good], ((False, "user_event_input", "supported", "Bad index."),)),
            ("duplicate-outcome", [good], (supported[0], supported[0])),
            (
                "duplicate-coverage-root",
                [good, dict(good)],
                (supported[0], (1, "user_event_input", "supported", "Duplicate root.")),
            ),
        )
        for label, coverage, outcomes in cases:
            with self.subTest(case=label):
                case = _source_fact_case(
                    extra_claim=True,
                    coverage_items=coverage,
                    coverage_outcomes=outcomes,
                )
                self.assertIs(_retain_unknown_context_v0_2(*case), case[2])

    def test_v02_announced_occurrence_is_narrow_and_keeps_v01_rejection(self):
        announced = (
            "On October 3, 2026, ACME HOLDINGS, INC. announced its acquisition "
            "of Example Corp."
        )
        snapshot, receipt, context = _source_fact_case(sentence=announced)
        envelope = json.loads(snapshot.canonical_bytes.decode("utf-8"))
        self.assertIsNone(
            _resolve_sec_occurrence_date(
                0,
                envelope["claims"][0],
                context.source_bodies["sec-fact"],
                envelope,
                frozenset((0,)),
                context,
            )
        )
        self.assertIsNone(_retain_unknown_context(snapshot, receipt, context).event_date_range)

        prepared = _retain_unknown_context_v0_2(snapshot, receipt, context)
        methodology = json.loads(prepared.event_date_range.methodology)
        self.assertEqual(prepared.event_date_range.start_date, datetime.date(2026, 10, 3))
        self.assertEqual(
            methodology["rule_version"],
            "host-event-source-facts-v0.2/sec-8-k-occurrence-date",
        )
        self.assertEqual(methodology["verb"], "announced")
        self.assertEqual(
            context.source_bodies["sec-fact"].body[methodology["start"]:methodology["end"]],
            announced,
        )

        unsafe_cases = (
            {
                "sentence": "ACME HOLDINGS, INC. announced its acquisition of Example Corp.",
                "body": _SEC_HEADER + "Filing date: October 3, 2026\n" + "ACME HOLDINGS, INC. announced its acquisition of Example Corp.\n",
            },
            {
                "sentence": "On October 3, 2026, ACME HOLDINGS, INC. announced that it will complete its acquisition of Example Corp."
            },
            {
                "sentence": announced.replace("ACME HOLDINGS, INC.", "OTHER CORPORATION, INC.")
            },
            {"sentence": announced, "model_date": "2026-10-02"},
            {"sentence": announced, "binding_offset_delta": 1},
            {"sentence": announced, "receipt_body_hash": "f" * 64},
        )
        for options in unsafe_cases:
            with self.subTest(options=options):
                unsafe_snapshot, unsafe_receipt, unsafe_context = _source_fact_case(**options)
                result = _retain_unknown_context_v0_2(
                    unsafe_snapshot, unsafe_receipt, unsafe_context
                )
                self.assertIsNone(result.event_date_range)

    def test_listing_preparer_requires_explicit_exact_authorized_source_tuple(self):
        case = _listing_identity_case()
        snapshot, receipt, context, source_ids = case[:4]
        with self.assertRaises(TypeError):
            _make_listing_source_preparer(list(source_ids.values()))
        with self.assertRaises(ValueError):
            _make_listing_source_preparer((source_ids["sec"], source_ids["sec"]))

        prepared_empty = _make_listing_source_preparer(())(snapshot, receipt, context)
        prepared_unselected = _make_listing_source_preparer(("not-authorized",))(
            snapshot, receipt, context
        )
        self.assertEqual(prepared_empty.underlying_bindings, {})
        self.assertEqual(prepared_unselected.underlying_bindings, {})
        self.assertIs(prepared_empty.raw_input, context.raw_input)
        self.assertIs(prepared_unselected, context)

    def test_listing_preparer_requires_verified_hypothesis_and_unique_verified_entity_binding(self):
        cases = (
            {"verified_hypothesis_ids": ()},
            {"verified_binding_indices": ()},
            {"duplicate_entity_binding": True},
        )
        for options in cases:
            with self.subTest(options=options):
                case = _listing_identity_case(**options)
                snapshot, receipt, context, source_ids = case[:4]
                prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
                    snapshot, receipt, context
                )
                self.assertEqual(prepared.underlying_bindings, {})

    def test_sec_primary_composite_binds_only_from_same_client_receipt(self):
        snapshot, receipt, context, client, records, calls, hypothesis_id, _run_input = (
            _sec_primary_listing_case()
        )
        source_ids = tuple(record.source_id for record in records)
        preparer = _make_listing_source_preparer(
            source_ids,
            admission_records=records,
            sec_composite=(client, ("ACME",), records, 1_500_000, 1_500_000),
        )
        prepared = preparer(snapshot, receipt, context)
        pair = (hypothesis_id, "ACME")
        self.assertIn(pair, prepared.underlying_bindings)
        key, reference_text = prepared.underlying_bindings[pair]
        self.assertEqual(
            key,
            UnderlyingKey("ACME", None, UnderlyingSecurityType.EQUITY, "USD"),
        )
        reference = json.loads(reference_text)
        self.assertEqual(
            reference["rule_version"], "host-listing-source-composite-v0.2"
        )
        self.assertEqual(
            [source["role"] for source in reference["sources"]],
            ["sec_issuer_reference", "sec_cover_security_class", "yahoo_quote_denomination"],
        )
        self.assertEqual(reference["sources"][0]["issuer_name"], "Reference Unicode — Name")
        self.assertEqual(reference["sources"][1]["share_class"], "Common Stock")
        self.assertEqual(
            reference["sources"][1]["registered_exchange"],
            "The Nasdaq Capital Market",
        )
        self.assertEqual(reference["sources"][2]["currency_basis"],
                         "yahoo_provider_reported_quote_denomination")
        for item in reference["sources"]:
            self.assertIn("source_admission", item)
            self.assertTrue(item["excerpts"])
        self.assertEqual(len(calls), 3)

    def test_sec_primary_cover_uses_v4_marker_span_for_wrapped_marker(self):
        raw_cover = _sec_primary_raw_cover_html().replace(
            b"(Exact name of registrant as specified in its charter)",
            b"(Exact name of registrant as \nspecified in its charter)",
        )
        snapshot, receipt, context, client, records, _calls, hypothesis_id, _run_input = (
            _sec_primary_listing_case(
                run_id="sec-primary-wrapped-marker-run",
                cover_html_override=raw_cover,
            )
        )
        cover_record = records[0]
        self.assertEqual(cover_record.parser_id, "sec-edgar-cover-layout-v4")
        marker_anchors = tuple(
            anchor for anchor in cover_record.raw_anchors
            if anchor.field == "sec_cover.registrant_marker"
        )
        self.assertEqual(len(marker_anchors), 1)
        marker_anchor = marker_anchors[0]
        self.assertIn(
            "\n",
            cover_record.parsed_body[marker_anchor.parsed_start:marker_anchor.parsed_end],
        )
        preparer = _make_listing_source_preparer(
            tuple(record.source_id for record in records),
            admission_records=records,
            sec_composite=(client, ("ACME",), records, 1_500_000, 1_500_000),
        )
        prepared = preparer(snapshot, receipt, context)
        self.assertIn((hypothesis_id, "ACME"), prepared.underlying_bindings)

    def test_sec_primary_composite_fails_closed_on_unissued_tamper_and_unverified_hypothesis(self):
        snapshot, receipt, context, client, records, _calls, hypothesis_id, _run_input = (
            _sec_primary_listing_case()
        )
        source_ids = tuple(record.source_id for record in records)
        tampered = replace(
            records[-1],
            parsed_body=records[-1].parsed_body + "tamper",
            parsed_body_sha256=_digest(records[-1].parsed_body + "tamper"),
        )
        for label, selected_records, selected_client in (
            ("record-tamper", records[:-1] + (tampered,), client),
            ("wrong-order", tuple(reversed(records)), client),
            ("foreign-client", records, _SourceAdmissionClient(
                timeout_seconds=1.0,
                max_response_bytes=100_000,
                byte_budget=100_000,
            )),
        ):
            with self.subTest(case=label):
                preparer = _make_listing_source_preparer(
                    source_ids,
                    admission_records=records,
                    sec_composite=(
                        selected_client, ("ACME",), selected_records,
                        1_500_000, 1_500_000,
                    ),
                )
                prepared = preparer(snapshot, receipt, context)
                self.assertEqual(prepared.underlying_bindings, {})

        unverified = _sec_primary_listing_case(
            run_id="sec-primary-unverified-run", verified_hypothesis_ids=()
        )
        snap, rec, ctx, source_client, source_records, _calls, _hypothesis_id, _ri = unverified
        preparer = _make_listing_source_preparer(
            tuple(record.source_id for record in source_records),
            admission_records=source_records,
            sec_composite=(source_client, ("ACME",), source_records, 1_500_000, 1_500_000),
        )
        self.assertEqual(preparer(snap, rec, ctx).underlying_bindings, {})

    def test_sec_primary_composite_requires_issued_exact_client_validator(self):
        snapshot, receipt, context, client, records, _calls, _hypothesis_id, _run_input = (
            _sec_primary_listing_case()
        )
        source_ids = tuple(record.source_id for record in records)

        class _FakeAdmissionClient:
            def _revalidate_sec_composite(self, *_args, **_kwargs):
                return records

        with self.assertRaises(ValueError):
            _make_listing_source_preparer(
                source_ids,
                admission_records=records,
                sec_composite=(
                    _FakeAdmissionClient(), ("ACME",), records,
                    1_500_000, 1_500_000,
                ),
            )

        tampered = records[:-1] + (
            replace(records[-1], raw_body_sha256="0" * 64),
        )
        for shadow_validator in (False, True):
            with self.subTest(shadow_validator=shadow_validator):
                if shadow_validator:
                    client._revalidate_sec_composite = (
                        lambda *_args, **_kwargs: records
                    )
                preparer = _make_listing_source_preparer(
                    source_ids,
                    admission_records=records,
                    sec_composite=(
                        client, ("ACME",), tampered, 1_500_000, 1_500_000,
                    ),
                )
                prepared = preparer(snapshot, receipt, context)
                self.assertEqual(prepared.underlying_bindings, {})

    def test_sec_primary_composite_rejects_nonmatching_issuer_and_wrong_cover_class(self):
        cases = (
            ("different issuer", "<html><body><div>NasdaqCM - Nasdaq Real Time Price USD</div>"
             "<h1>Different Holdings, Inc. (ACME)</h1></body></html>", "Common Stock"),
            ("wrong class", None, "Preferred Stock"),
        )
        for label, yahoo_override, share_class in cases:
            with self.subTest(case=label):
                snapshot, receipt, context, client, records, _calls, _hypothesis_id, _ri = (
                    _sec_primary_listing_case(
                        run_id="sec-primary-reject-{}".format(label.replace(" ", "-")),
                        yahoo_override=yahoo_override,
                        share_class=share_class,
                    )
                )
                preparer = _make_listing_source_preparer(
                    tuple(record.source_id for record in records),
                    admission_records=records,
                    sec_composite=(client, ("ACME",), records, 1_500_000, 1_500_000),
                )
                self.assertEqual(
                    preparer(snapshot, receipt, context).underlying_bindings, {}
                )

    def test_listing_preparer_fails_closed_on_url_ambiguity(self):
        cases = (
            ("spoof", "https://finance.yahoo.com.attacker.invalid/quote/Z7QX/"),
            ("userinfo", "https://user@finance.yahoo.com/quote/Z7QX/"),
            ("port", "https://finance.yahoo.com:8443/quote/Z7QX/"),
            ("query", "https://finance.yahoo.com/quote/Z7QX/?"),
            ("encoded-path", "https://finance.yahoo.com/quote/Z7QX/%2e%2e"),
        )
        for label, locator in cases:
            with self.subTest(locator=label):
                case = _listing_identity_case(
                    locator_overrides={"yahoo": locator}
                )
                snapshot, receipt, context, source_ids = case[:4]
                prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
                    snapshot, receipt, context
                )
                self.assertEqual(prepared.underlying_bindings, {})

    def test_listing_preparer_fails_closed_on_duplicate_or_conflicting_body_fields(self):
        valid = _listing_source_material("listing-conflict-run", "Z7QX")
        _source_ids, _order, bodies, _by_url = valid
        duplicate_sec = bodies["sec"].replace(
            "| Ordinary shares, no par value | Z7QX | The Nasdaq Stock Market LLC |\r\n\r\n",
            "| Ordinary shares, no par value | Z7QX | The Nasdaq Stock Market LLC |\r\n"
            "| Ordinary shares, no par value | Z7QX | The Nasdaq Stock Market LLC |\r\n\r\n",
        )
        cases = (
            ("duplicate-row", {"sec": duplicate_sec}),
            (
                "wrong-denomination",
                {"yahoo": bodies["yahoo"].replace("•USD", "•EUR")},
            ),
            (
                "issuer-conflict",
                {"yahoo": bodies["yahoo"].replace("Example Holdings, Inc.", "Different Holdings")},
            ),
        )
        for label, body_overrides in cases:
            with self.subTest(body=label):
                case = _listing_identity_case(body_overrides=body_overrides)
                snapshot, receipt, context, source_ids = case[:4]
                prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
                    snapshot, receipt, context
                )
                self.assertEqual(prepared.underlying_bindings, {})

    def test_listing_preparer_rejects_sec_text_v2_common_stock_capital_market(self):
        _source_ids, _source_order, bodies, _bodies_by_url = _listing_source_material(
            "listing-sec-text-v2-run", "Z7QX"
        )
        sec_text_v2 = bodies["sec"].replace(
            "Ordinary shares, no par value", "Common Stock"
        ).replace("The Nasdaq Stock Market LLC", "Nasdaq Capital Market")
        case = _listing_identity_case(
            run_id="listing-sec-text-v2-run",
            symbol="Z7QX",
            body_overrides={"sec": sec_text_v2},
        )
        snapshot, receipt, context, source_ids = case[:4]
        prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
            snapshot, receipt, context
        )
        self.assertEqual(prepared.underlying_bindings, {})

    def test_listing_preparer_excludes_v3_and_v4_even_when_body_matches_v1(self):
        raw_html = (
            "<html><body><p>Example Holdings, Inc.</p>"
            "<p>(Exact name of registrant as specified in its charter)</p>"
            "<table><tr><th>Title of each class</th><th></th>"
            "<th>Trading Symbol(s)</th><th></th>"
            "<th>Name of each exchange on which registered</th></tr>"
            "<tr><td>Ordinary shares, no par value</td><td></td>"
            "<td>Z7QX</td><td></td>"
            "<td>The Nasdaq Stock Market LLC</td></tr></table></body></html>"
        ).encode("utf-8")
        calls = []

        def transport(locator, _address, _timeout, _max_bytes):
            calls.append(locator)
            return _Reply(200, {"Content-Type": "text/html; charset=UTF-8"}, raw_html)

        admitted = _SourceAdmissionClient(
            timeout_seconds=1.0,
            max_response_bytes=100_000,
            byte_budget=100_000,
            _transport=transport,
            _resolver=lambda _host, _port: ("93.184.216.34",),
            _clock=lambda: _NOW,
        ).admit_candidates((_SEC_LOCATOR,))
        self.assertEqual(calls, [_SEC_LOCATOR])
        self.assertEqual(admitted.request_count, 1)
        self.assertEqual(len(admitted.admissions), 1)
        sec_record = admitted.admissions[0]
        self.assertEqual(sec_record.parser_id, "sec-edgar-cover-layout-v3")
        self.assertEqual(sec_record.parsed_body.splitlines()[-1],
                         "| Ordinary shares, no par value | Z7QX | The Nasdaq Stock Market LLC |")

        case = _listing_identity_case(
            run_id="listing-sec-layout-v3-run",
            symbol="Z7QX",
            locator_overrides={"sec": _SEC_LOCATOR},
            body_overrides={"sec": sec_record.parsed_body},
            source_id_overrides={"sec": sec_record.source_id},
        )
        snapshot, receipt, context, source_ids = case[:4]
        legacy_prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
            snapshot, receipt, context
        )
        self.assertIn(
            ("hypothesis-generated-listing-sec-layout-v3-run", "Z7QX"),
            legacy_prepared.underlying_bindings,
        )
        for parser_id, version in (
            ("sec-edgar-cover-layout-v3", "3"),
            ("sec-edgar-cover-layout-v4", "4"),
        ):
            with self.subTest(parser_id=parser_id):
                guarded_record = replace(
                    sec_record, parser_id=parser_id, parser_version=version
                )
                guarded_prepared = _make_listing_source_preparer(
                    tuple(source_ids.values()), admission_records=(guarded_record,)
                )(snapshot, receipt, context)
                self.assertEqual(guarded_prepared.underlying_bindings, {})

    def test_listing_preparer_accepts_ascii_tab_whitespace_but_rejects_other_controls(self):
        valid = _listing_source_material("listing-tab-run", "Z7QX")
        _source_ids, _order, bodies, _by_url = valid
        tab_bodies = {
            "sec": (
                bodies["sec"]
                .replace("Example Holdings, Inc.", "Example\tHoldings, Inc.")
                .replace("Ordinary shares, no par value", "Ordinary\tshares, no par value")
                .replace("The Nasdaq Stock Market LLC", "The Nasdaq\tStock Market LLC")
            ),
            "nasdaq": bodies["nasdaq"].replace(
                "Example Holdings, Inc.", "Example\tHoldings, Inc."
            ),
            "yahoo": bodies["yahoo"].replace(
                "Example Holdings, Inc.", "Example\tHoldings, Inc."
            ),
        }
        case = _listing_identity_case(body_overrides=tab_bodies)
        snapshot, receipt, context, source_ids = case[:4]
        prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
            snapshot, receipt, context
        )
        pair = ("hypothesis-generated-listing-preparer-run", "Z7QX")
        self.assertIn(pair, prepared.underlying_bindings)
        provenance = json.loads(prepared.underlying_bindings[pair][1])
        sec_excerpts = provenance["sources"][0]["excerpts"]
        self.assertTrue(any("Ordinary\tshares" in item["text"] for item in sec_excerpts))

        control_bodies = dict(bodies)
        control_bodies["sec"] = bodies["sec"].replace(
            "Example Holdings, Inc.", "Example\vHoldings, Inc."
        )
        case = _listing_identity_case(body_overrides=control_bodies)
        snapshot, receipt, context, source_ids = case[:4]
        prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
            snapshot, receipt, context
        )
        self.assertEqual(prepared.underlying_bindings, {})

    def test_listing_preparer_rejects_nonempty_yahoo_heading_suffix(self):
        case = _listing_identity_case(
            body_overrides={
                "yahoo": (
                    "NasdaqGS - Delayed Quote•USD\r\n\r\n"
                    "# Example Holdings, Inc. (Z7QX) trailing text\r\n"
                )
            }
        )
        snapshot, receipt, context, source_ids = case[:4]
        prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
            snapshot, receipt, context
        )
        self.assertEqual(prepared.underlying_bindings, {})

    def test_listing_preparer_rejects_competing_case_variant_yahoo_quote_header(self):
        case = _listing_identity_case(
            body_overrides={
                "yahoo": (
                    "NYSE - delayed quote•EUR\r\n"
                    "NasdaqGS - Delayed Quote•USD\r\n\r\n"
                    "# Example Holdings, Inc. (Z7QX)\r\n"
                )
            }
        )
        snapshot, receipt, context, source_ids = case[:4]
        prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
            snapshot, receipt, context
        )
        self.assertEqual(prepared.underlying_bindings, {})

    def test_listing_preparer_rejects_single_case_variant_yahoo_quote_header(self):
        case = _listing_identity_case(
            body_overrides={
                "yahoo": (
                    "nasdaqgs - delayed quote•usd\r\n\r\n"
                    "# Example Holdings, Inc. (Z7QX)\r\n"
                )
            }
        )
        snapshot, receipt, context, source_ids = case[:4]
        prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
            snapshot, receipt, context
        )
        self.assertEqual(prepared.underlying_bindings, {})

    def test_listing_preparer_revalidates_constructor_bypassed_source_body(self):
        case = _listing_identity_case()
        snapshot, receipt, context, source_ids = case[:4]
        sec_source = context.source_bodies[source_ids["sec"]]
        object.__setattr__(sec_source, "body_sha256", "0" * 64)

        prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
            snapshot, receipt, context
        )
        self.assertEqual(prepared.underlying_bindings, {})
        self.assertIs(prepared.source_bodies[source_ids["sec"]], sec_source)

    def test_listing_preparer_preserves_existing_context_and_binding_objects(self):
        case = _listing_identity_case()
        snapshot, receipt, context, source_ids = case[:4]
        preserved_key = UnderlyingKey("OTHER", "XNAS", UnderlyingSecurityType.EQUITY, "USD")
        preserved_reference = object()
        policy = CallerPolicyProvenance(
            context.run_id,
            context.canonical_input_hash,
            datetime.date(2026, 10, 10),
            "synthetic retained policy",
            "synthetic caller",
        )
        date_range = MethodologizedDateRange(
            datetime.date(2026, 10, 1),
            datetime.date(2026, 10, 2),
            "synthetic retained range",
        )
        preserved_context = replace(
            context,
            event_description_binding="caller-description",
            event_date_range=date_range,
            underlying_bindings={
                ("caller-hypothesis", "OTHER"): (preserved_key, preserved_reference)
            },
            caller_policy_provenance=policy,
        )
        prepared = _make_listing_source_preparer(tuple(source_ids.values()))(
            snapshot, receipt, preserved_context
        )

        self.assertIsNot(prepared, preserved_context)
        self.assertIs(prepared.raw_input, preserved_context.raw_input)
        self.assertIs(prepared.event_date_range, date_range)
        self.assertEqual(prepared.event_description_binding, "caller-description")
        self.assertIs(prepared.caller_policy_provenance, policy)
        for source_id in source_ids.values():
            self.assertIs(
                prepared.source_bodies[source_id], preserved_context.source_bodies[source_id]
            )
        preserved = prepared.underlying_bindings[("caller-hypothesis", "OTHER")]
        self.assertIs(preserved[0], preserved_key)
        self.assertIs(preserved[1], preserved_reference)
        self.assertIn(
            ("hypothesis-generated-listing-preparer-run", "Z7QX"),
            prepared.underlying_bindings,
        )

    def test_opt_in_listing_preparer_passes_dynamic_identity_through_runtime_guard(self):
        run_id = "runtime-listing-composite-51"
        symbol = "Z7QX"
        source_ids, source_order, _bodies, bodies_by_url = _listing_source_material(
            run_id, symbol
        )
        config = _config(source_order=source_order)
        discovery, semantic, _normalized = _listing_runtime_wires(
            run_id, symbol, source_order, bodies_by_url, config,
            normal_recipe=False,
        )
        source_transport = _SyntheticSourceTransport(
            search_order=source_order,
            body_overrides=bodies_by_url,
        )
        model_transport = _SyntheticModelTransport(discovery, semantic)
        preparer = _make_listing_source_preparer(tuple(source_ids.values()))
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
            host_context_preparer=preparer,
        )

        result = callback(
            "Assess a synthetic listing event.",
            run_id=run_id,
            bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
        )

        prepared = result.build_result.context
        pair = ("hypothesis-generated-{}".format(run_id), symbol)
        key, reference = prepared.underlying_bindings[pair]
        self.assertEqual(key, UnderlyingKey(symbol, None, UnderlyingSecurityType.EQUITY, "USD"))
        self.assertEqual(prepared.event_description_binding, "claim-generated-{}".format(run_id))
        provenance = json.loads(reference)
        self.assertEqual(provenance["rule_version"], "host-listing-source-composite-v0.1")
        self.assertEqual(
            provenance["currency_basis"], "yahoo_provider_reported_quote_denomination"
        )
        self.assertEqual(
            [source["role"] for source in provenance["sources"]],
            ["sec_listing_class", "nasdaq_instrument_heading", "yahoo_quote_denomination"],
        )
        for source_record in provenance["sources"]:
            registered = prepared.source_bodies[source_record["source_id"]]
            self.assertEqual(
                source_record["body_sha256"], _digest(registered.body)
            )
            for excerpt in source_record["excerpts"]:
                self.assertEqual(
                    registered.body[excerpt["start"]:excerpt["end"]], excerpt["text"]
                )
                self.assertEqual(excerpt["sha256"], _digest(excerpt["text"]))
        self.assertEqual(len(source_transport.calls), 2)
        self.assertEqual(len(model_transport.calls), 2)

    def test_default_host_route_registers_sec_primary_three_source_composite(self):
        run_id = "default-sec-primary-composite-run"
        note_locator = "https://source.example/a"
        candidate_order = (
            ("source-sec", _SEC_LOCATOR),
            ("source-note", note_locator),
        )
        cover_html = _sec_primary_raw_cover_html().replace(
            b"</p><table>", b"</p><p>A synthetic event was reported.</p><table>"
        )
        reference_locator = "https://www.sec.gov/files/company_tickers_exchange.json"
        yahoo_locator = "https://finance.yahoo.com/quote/ACME/"
        reference_body = json.dumps(
            {
                "fields": ["cik", "name", "ticker", "exchange"],
                "data": [[320193, "Reference Unicode — Name", "ACME", "Nasdaq"]],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        yahoo_body = (
            b"<html><body><div>NasdaqCM - Nasdaq Real Time Price USD</div>"
            b"<h1>Example Holdings, Inc. (ACME)</h1></body></html>"
        )
        replies = {
            _SEC_LOCATOR: _Reply(
                200, {"Content-Type": "text/html; charset=UTF-8"}, cover_html
            ),
            reference_locator: _Reply(
                200, {"Content-Type": "application/json"}, reference_body
            ),
            yahoo_locator: _Reply(
                200, {"Content-Type": "text/html; charset=UTF-8"}, yahoo_body
            ),
        }

        def make_client(calls):
            def transport(locator, _address, _timeout, _max_bytes):
                calls.append(locator)
                return replies[locator]

            return _SourceAdmissionClient(
                timeout_seconds=2.0,
                max_response_bytes=1_500_000,
                byte_budget=2_500_000,
                _transport=transport,
                _resolver=lambda _host, _port: ("93.184.216.34",),
                _clock=lambda: _NOW,
            )

        fixture_client = make_client([])
        fixture_candidates = fixture_client.admit_candidates((_SEC_LOCATOR,))
        fixture_composite = fixture_client._admit_sec_reference_and_yahoo(
            ("ACME",), fixture_candidates.admissions
        )
        self.assertEqual(len(fixture_composite.admissions), 3)
        source_order = candidate_order + tuple(
            (record.source_id, record.initial_locator)
            for record in fixture_composite.admissions
        )
        bodies_by_url = {
            record.initial_locator: record.parsed_body
            for record in fixture_composite.admissions
        }
        bodies_by_url[note_locator] = "A synthetic event was reported.\n"
        config = _config(source_order=candidate_order)
        discovery, semantic, _normalized = _listing_runtime_wires(
            run_id, "ACME", source_order, bodies_by_url, config
        )
        source_transport = _SyntheticSourceTransport(
            search_order=candidate_order, body_overrides=bodies_by_url
        )
        model_transport = _SyntheticModelTransport(discovery, semantic)
        admission_calls = []
        admission_client = make_client(admission_calls)
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )
        with patch(
            "convexity_hunter.host_event._create_source_admission_client",
            return_value=admission_client,
        ):
            result = callback(
                "Assess a synthetic listing event.",
                run_id=run_id,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )

        prepared = result.build_result.context
        pair = ("hypothesis-generated-{}".format(run_id), "ACME")
        self.assertIn(pair, prepared.underlying_bindings)
        provenance = json.loads(prepared.underlying_bindings[pair][1])
        self.assertEqual(
            provenance["rule_version"], "host-listing-source-composite-v0.2"
        )
        self.assertEqual(
            [item["role"] for item in provenance["sources"]],
            ["sec_issuer_reference", "sec_cover_security_class", "yahoo_quote_denomination"],
        )
        self.assertEqual(
            admission_calls, [_SEC_LOCATOR, reference_locator, yahoo_locator]
        )

    def test_sec_v2_v3_and_v4_supplement_authority_is_candidate_only(self):
        nasdaq_url = "https://www.nasdaq.com/market-activity/stocks/acme"
        yahoo_url = "https://finance.yahoo.com/quote/ACME/"
        sec_html = (
            b"<!doctype html><html><body>"
            b"<p>ACME HOLDINGS, INC.</p>"
            b"<p>(Exact name of registrant as specified in its charter)</p>"
            b"<p>A synthetic event was reported.</p>"
            b"<p>On October 3, 2026, ACME HOLDINGS, INC. completed its acquisition of Example Corp.</p>"
            b"<table><tr><th>Title of each class</th><th>Trading Symbol(s)</th>"
            b"<th>Name of each exchange on which registered</th></tr>"
            b"<tr><td>Common Stock</td><td>ACME</td>"
            b"<td>Nasdaq Capital Market</td></tr></table></body></html>"
        )
        nasdaq_html = (
            b"<!doctype html><html><body>"
            b"<h1>ACME HOLDINGS, INC. Ordinary Shares (ACME)</h1>"
            b"</body></html>"
        )
        yahoo_html = (
            b"<!doctype html><html><body><div>NasdaqGS - Delayed Quote&#8226;USD</div>"
            b"<h1>ACME HOLDINGS, INC. (ACME)</h1></body></html>"
        )
        def make_batch(sec_body, candidate_urls=(_SEC_LOCATOR, nasdaq_url, yahoo_url)):
            replies = {
                _SEC_LOCATOR: _Reply(200, {"Content-Type": "text/html"}, sec_body),
                nasdaq_url: _Reply(200, {"Content-Type": "text/html"}, nasdaq_html),
                yahoo_url: _Reply(200, {"Content-Type": "text/html"}, yahoo_html),
            }

            class _AdmissionTransport:
                def __call__(self, locator, _address, _timeout, _max_bytes):
                    return replies[locator]

            batch_client = _SourceAdmissionClient(
                timeout_seconds=2.0,
                max_response_bytes=100_000,
                byte_budget=500_000,
                _transport=_AdmissionTransport(),
                _resolver=lambda _host, _port: ("93.184.216.34",),
                _clock=lambda: _NOW,
            )
            return batch_client.admit_candidates(candidate_urls)

        v2_batch = make_batch(sec_html)
        self.assertEqual(
            [record.parser_id for record in v2_batch.admissions],
            [
                "sec-edgar-cover-text-v2",
                "nasdaq-instrument-v1",
                "yahoo-quote-header-v1",
            ],
        )
        class _PreloadedAdmissionClient:
            def __init__(self, batch):
                self.locators = None
                self.batch = batch

            def admit_candidates(self, locators):
                self.locators = tuple(locators)
                return self.batch

        def run_case(run_id, candidate_urls, batch):
            candidate_ids = {
                _SEC_LOCATOR: "tavily-sec",
                nasdaq_url: "tavily-nasdaq",
                yahoo_url: "tavily-yahoo",
            }
            expected_records = tuple(
                record
                for record in batch.admissions
                if record.initial_locator in candidate_urls
            )
            candidate_source_order = tuple(
                (candidate_ids[url], url) for url in candidate_urls
            )
            source_order = candidate_source_order + tuple(
                (record.source_id, record.initial_locator)
                for record in expected_records
            )
            bodies_by_url = {
                record.initial_locator: record.parsed_body
                for record in batch.admissions
            }
            config = _config(source_order=candidate_source_order)
            discovery, semantic, _normalized = _model_outputs(
                run_id,
                "Assess the reported ACME filing.",
                source_order,
                bodies_by_url,
                config,
            )
            source_transport = _SyntheticSourceTransport(
                search_order=tuple(
                    (candidate_ids[url], url) for url in candidate_urls
                ),
                body_overrides=bodies_by_url,
            )
            model_transport = _SyntheticModelTransport(discovery, semantic)
            admission_client = _PreloadedAdmissionClient(batch)
            callback = create_event_grounder(
                config,
                repo_root=_ROOT,
                source_transport=source_transport,
                discovery_transport=model_transport,
                semantic_transport=model_transport,
            )
            with patch(
                "convexity_hunter.host_event._create_source_admission_client",
                return_value=admission_client,
            ):
                result = callback(
                    "Assess the reported ACME filing.",
                    run_id=run_id,
                    bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
                )
            registered = set(result.build_result.context.source_bodies)
            registered_admissions = {
                record.source_id
                for record in batch.admissions
                if record.source_id in registered
            }
            expected_admissions = {record.source_id for record in expected_records}
            self.assertEqual(admission_client.locators, candidate_urls)
            self.assertEqual(registered_admissions, expected_admissions)

        run_case("sec-v2-unsolicited-supplements", (_SEC_LOCATOR,), v2_batch)
        run_case("sec-v2-explicit-nasdaq", (_SEC_LOCATOR, nasdaq_url), v2_batch)

        v3_sec_html = (
            b"<!doctype html><html><body>"
            b"<p>ACME HOLDINGS, INC.</p>"
            b"<p>(Exact name of registrant as specified in its charter)</p>"
            b"<p>A synthetic event was reported.</p>"
            b"<p>On October 3, 2026, ACME HOLDINGS, INC. completed its acquisition of Example Corp.</p>"
            b"<table><tr><th>Title of each class</th><th>&nbsp;</th>"
            b"<th>Trading Symbol(s)</th><th>&nbsp;</th>"
            b"<th>Name of each exchange on which registered</th></tr>"
            b"<tr><td>Common Stock</td><td>&nbsp;</td><td>ACME</td>"
            b"<td>&nbsp;</td><td>Nasdaq Capital Market</td></tr></table></body></html>"
        )
        v3_single = make_batch(v3_sec_html, (_SEC_LOCATOR,))
        self.assertEqual(v3_single.request_count, 1)
        self.assertEqual(len(v3_single.admissions), 1)
        self.assertEqual(v3_single.admissions[0].parser_id, "sec-edgar-cover-layout-v3")
        v3_batch = make_batch(v3_sec_html)
        self.assertEqual(
            [record.parser_id for record in v3_batch.admissions],
            [
                "sec-edgar-cover-layout-v3",
                "nasdaq-instrument-v1",
                "yahoo-quote-header-v1",
            ],
        )
        run_case("sec-v3-unsolicited-supplements", (_SEC_LOCATOR,), v3_batch)
        run_case(
            "sec-v3-explicit-nasdaq",
            (_SEC_LOCATOR, nasdaq_url),
            v3_batch,
        )

        v4_sec_html = (
            b"<!doctype html><html><body>"
            b"<p>ACME HOLDINGS, INC.</p>"
            b"<p>(Exact&#10;name of registrant as specified in its charter)</p>"
            b"<p>A synthetic event was reported.</p>"
            b"<p>On October 3, 2026, ACME HOLDINGS, INC. completed its acquisition of Example Corp.</p>"
            b"<table><tr><th>Title of each class</th><th>&nbsp;</th>"
            b"<th>Trading Symbol(s)</th><th>&nbsp;</th>"
            b"<th>Name of each exchange on which registered</th></tr>"
            b"<tr><td>Common Stock</td><td>&nbsp;</td><td>ACME</td>"
            b"<td>&nbsp;</td><td>Nasdaq Capital Market</td></tr></table></body></html>"
        )
        v4_single = make_batch(v4_sec_html, (_SEC_LOCATOR,))
        self.assertEqual(v4_single.request_count, 1)
        self.assertEqual(len(v4_single.admissions), 1)
        self.assertEqual(v4_single.admissions[0].parser_id, "sec-edgar-cover-layout-v4")
        v4_batch = make_batch(v4_sec_html)
        self.assertEqual(
            [record.parser_id for record in v4_batch.admissions],
            [
                "sec-edgar-cover-layout-v4",
                "nasdaq-instrument-v1",
                "yahoo-quote-header-v1",
            ],
        )
        run_case("sec-v4-unsolicited-supplements", (_SEC_LOCATOR,), v4_batch)
        run_case(
            "sec-v4-explicit-nasdaq",
            (_SEC_LOCATOR, nasdaq_url),
            v4_batch,
        )

    def test_default_event_path_admits_html_before_models_and_preserves_lineage(self):
        run_id = "default-admission-listing-run"
        initial_sec = _SEC_LOCATOR
        final_sec = initial_sec.replace("www.sec.gov", "sec.gov")
        symbol = "ACME"
        nasdaq_url = "https://www.nasdaq.com/market-activity/stocks/acme"
        yahoo_url = "https://finance.yahoo.com/quote/ACME/"
        sec_html = (
            "<!doctype html><html><body>"
            "<p>ACME HOLDINGS, INC.</p>"
            "<p>(Exact name of registrant as specified in its charter)</p>"
            "<p>A synthetic event was reported.</p>"
            "<p>On October 3, 2026, ACME HOLDINGS, INC. completed its acquisition of Example Corp.</p>"
            "<table>"
            "<tr><th>Title of each class</th><th>Trading Symbol(s)</th>"
            "<th>Name of each exchange on which registered</th></tr>"
            "<tr><td>Ordinary shares, no par value</td><td>ACME</td>"
            "<td>The Nasdaq Stock Market LLC</td></tr>"
            "</table></body></html>"
        ).encode("utf-8")
        # The ignored HTML envelope is intentionally larger than the parsed
        # context ceiling; HTTP and parsed-evidence limits must stay separate.
        sec_html = sec_html.replace(
            b"<body>", b"<body><!--" + (b"x" * 25_000) + b"-->"
        )
        nasdaq_html = (
            b"<!doctype html><html><body>"
            b"<h1>ACME HOLDINGS, INC. Ordinary Shares (ACME)</h1>"
            b"</body></html>"
        )
        yahoo_html = (
            "<!doctype html><html><body><div>NasdaqGS - Delayed Quote&#8226;USD</div>"
            "<h1>ACME HOLDINGS, INC. (ACME)</h1></body></html>"
        ).encode("utf-8")

        source_ids = (
            _source_id_for_locator(initial_sec),
            _source_id_for_locator(nasdaq_url),
            _source_id_for_locator(yahoo_url),
        )
        sec_parsed = _sec_html(sec_html.decode("utf-8"))
        nasdaq_parsed = _nasdaq_html(nasdaq_html.decode("utf-8"), symbol)
        yahoo_parsed = _yahoo_html(yahoo_html.decode("utf-8"), symbol)
        self.assertIsNotNone(sec_parsed)
        self.assertIsNotNone(nasdaq_parsed)
        self.assertIsNotNone(yahoo_parsed)
        source_order = (
            (source_ids[0], final_sec),
            (source_ids[1], nasdaq_url),
            (source_ids[2], yahoo_url),
            ("tavily-sec", initial_sec),
        )
        bodies_by_url = {
            final_sec: sec_parsed.body,
            nasdaq_url: nasdaq_parsed.body,
            yahoo_url: yahoo_parsed.body,
            initial_sec: "Tavily retained text is not admitted listing evidence.\n",
        }
        config = _config(
            source_order=(("tavily-sec", initial_sec),),
            max_source_body_bytes=20_000,
        )
        config = replace(
            config,
            source=replace(config.source, max_response_bytes=100_000),
        )
        discovery, semantic, _normalized = _listing_runtime_wires(
            run_id, symbol, source_order, bodies_by_url, config
        )
        source_transport = _SyntheticSourceTransport(
            search_order=(("tavily-sec", initial_sec),),
            body_overrides={initial_sec: bodies_by_url[initial_sec]},
        )
        model_transport = _SyntheticModelTransport(discovery, semantic)

        class _AdmissionTransport:
            def __init__(self):
                self.calls = []
                self.replies = {
                    initial_sec: [_Reply(302, {"Location": final_sec}, b"")],
                    final_sec: [_Reply(200, {"Content-Type": "text/html; charset=utf-8"}, sec_html)],
                    nasdaq_url: [_Reply(200, {"Content-Type": "text/html; charset=utf-8"}, nasdaq_html)],
                    yahoo_url: [_Reply(200, {"Content-Type": "text/html; charset=utf-8"}, yahoo_html)],
                }

            def __call__(self, locator, address, timeout, max_bytes):
                self.calls.append((locator, address, timeout, max_bytes))
                reply = self.replies[locator].pop(0)
                if len(reply.body) > max_bytes:
                    return _Reply(reply.status, reply.headers, reply.body[: max_bytes + 1])
                return reply

        admission_transport = _AdmissionTransport()
        admission_client = _SourceAdmissionClient(
            timeout_seconds=config.source.timeout_seconds,
            max_response_bytes=config.source.max_response_bytes,
            byte_budget=5 * config.source.max_response_bytes,
            _transport=admission_transport,
            _resolver=lambda _host, _port: ("93.184.216.34",),
            _clock=lambda: _NOW,
        )
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        with patch(
            "convexity_hunter.host_event._create_source_admission_client",
            return_value=admission_client,
        ) as client_factory:
            result = callback(
                "Assess a synthetic listing event.",
                run_id=run_id,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )

        prepared = result.build_result.context
        pair = ("hypothesis-generated-{}".format(run_id), symbol)
        key, reference = prepared.underlying_bindings[pair]
        self.assertEqual(key, UnderlyingKey(symbol, None, UnderlyingSecurityType.EQUITY, "USD"))
        self.assertIsNone(prepared.event_date_range)
        self.assertGreater(len(sec_html), config.max_source_body_bytes)
        self.assertLessEqual(len(prepared.source_bodies[source_ids[0]].body.encode("utf-8")), 20_000)
        self.assertEqual(len(admission_transport.calls), 4)
        self.assertEqual(len(source_transport.calls), 2)
        self.assertEqual(len(model_transport.calls), 2)
        client_factory.assert_called_once_with(
            timeout_seconds=2.0,
            max_response_bytes=100_000,
            byte_budget=500_000,
        )
        safe_snapshot_source = callback.configuration_snapshot()["sources"][0]
        self.assertEqual(safe_snapshot_source["max_response_bytes"], 100_000)
        self.assertEqual(
            safe_snapshot_source["grounder_limits"]["max_source_body_bytes"],
            20_000,
        )
        model_payloads = json.dumps(model_transport.calls, ensure_ascii=False)
        self.assertIn(source_ids[0], model_payloads)
        self.assertIn("A synthetic event was reported.", model_payloads)
        self.assertIn("| Ordinary shares, no par value | ACME |", model_payloads)
        self.assertNotIn("<table>", model_payloads)
        self.assertNotIn("x" * 100, model_payloads)
        provenance = json.loads(reference)
        self.assertEqual(
            [source["role"] for source in provenance["sources"]],
            ["sec_listing_class", "nasdaq_instrument_heading", "yahoo_quote_denomination"],
        )
        for source in provenance["sources"]:
            admission = source["source_admission"]
            self.assertEqual(admission["parsed_body_sha256"], source["body_sha256"])
            self.assertNotEqual(admission["raw_body_sha256"], admission["parsed_body_sha256"])
            self.assertIn("initial_locator", admission)
            self.assertIn("final_locator", admission)
            self.assertIn("origin", admission)
            self.assertIn("parser_id", admission)
            self.assertIn("raw_anchors", admission)
        self.assertEqual(provenance["sources"][0]["source_admission"]["initial_locator"], initial_sec)
        self.assertEqual(provenance["sources"][0]["source_admission"]["final_locator"], final_sec)

    def test_occurrence_month_mapping_does_not_depend_on_datetime_strptime(self):
        snapshot, receipt, context = _source_fact_case()
        datetime_without_parser = SimpleNamespace(
            date=datetime.date,
            timezone=datetime.timezone,
        )
        with patch(
            "convexity_hunter.host_event.datetime", datetime_without_parser
        ):
            prepared = _retain_unknown_context(snapshot, receipt, context)
        self.assertEqual(
            prepared.event_date_range.start_date, datetime.date(2026, 10, 3)
        )

    def test_extra_explicit_dates_anywhere_in_sec_body_leave_date_unknown(self):
        extra_dates = (
            "The acquisition was completed on October 4, 2026.",
            "Supplemental filing date: 2026-10-04.",
            "Supplemental filing date: 10/4/2026.",
        )
        for extra_date in extra_dates:
            with self.subTest(extra_date=extra_date):
                body = _SEC_HEADER + _SEC_SENTENCE + "\n" + extra_date + "\n"
                snapshot, receipt, context = _source_fact_case(body=body)
                prepared = _retain_unknown_context(snapshot, receipt, context)

                self.assertEqual(prepared.event_description_binding, "fact-1")
                self.assertIsNone(prepared.event_date_range)
                self.assertIs(
                    prepared.source_bodies["sec-fact"],
                    context.source_bodies["sec-fact"],
                )
                self.assertEqual(prepared.source_bodies["sec-fact"].body, body)
                self.assertEqual(
                    prepared.source_bodies["sec-fact"].title,
                    "Synthetic SEC filing",
                )

    def test_default_host_route_resolves_v04_from_admitted_primary_html(self):
        run_id = "default-v04-sec-html-run"
        _fixture_client, admission = _sec_v04_admission(
            (
                "Earlier filing: March 2, 2026.",
                _V04_SEC_SENTENCE,
                "Filing date: October 1, 2026.",
                "Response deadline: December 31, 2026.",
            )
        )
        untrusted_locator = "https://source.example/unverified-extract"
        model_sources = (
            ("source-sec", untrusted_locator),
            (admission.source_id, _SEC_LOCATOR),
        )
        model_bodies = {
            untrusted_locator: "Tavily text is not admitted SEC evidence.\n",
            _SEC_LOCATOR: admission.parsed_body,
        }
        config = _config(source_order=(("source-sec", _SEC_LOCATOR),))
        discovery, semantic, _normalized = _model_outputs(
            run_id,
            _RAW_INPUT,
            model_sources,
            model_bodies,
            config,
            fact_text=_V04_SEC_SENTENCE,
            event_date="2026-09-21",
            date_binding_marker="September 21, 2026",
        )
        source_transport = _SyntheticSourceTransport(
            search_order=(("source-sec", _SEC_LOCATOR),),
            body_overrides={
                _SEC_LOCATOR: "Tavily text is not admitted SEC evidence.\n"
            },
        )
        model_transport = _SyntheticModelTransport(discovery, semantic)
        route_client, _route_admission = _sec_v04_admission(
            (
                "Earlier filing: March 2, 2026.",
                _V04_SEC_SENTENCE,
                "Filing date: October 1, 2026.",
                "Response deadline: December 31, 2026.",
            ),
            admit=False,
        )
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )
        with patch(
            "convexity_hunter.host_event._create_source_admission_client",
            return_value=route_client,
        ):
            result = callback(
                _RAW_INPUT,
                run_id=run_id,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )

        prepared = result.build_result.context
        self.assertEqual(prepared.event_description_binding, "fact-1")
        self.assertEqual(
            prepared.event_date_range.start_date, datetime.date(2026, 9, 21)
        )
        self.assertEqual(
            prepared.event_date_range.end_date, datetime.date(2026, 9, 21)
        )
        methodology = json.loads(prepared.event_date_range.methodology)
        source = prepared.source_bodies[admission.source_id]
        self.assertNotIn("CONFORMED SUBMISSION TYPE", source.body)
        self.assertEqual(
            methodology["rule_version"],
            "host-event-source-facts-v0.4/sec-primary-html-occurrence-date",
        )
        self.assertEqual(methodology["action_role"], "announcement")
        self.assertEqual(methodology["registrant"], "Example Holdings, Inc.")
        self.assertEqual(methodology["cik"], "320193")
        self.assertEqual(methodology["accession"], "000032019326000123")
        self.assertEqual(methodology["admission_provenance"]["parser_id"], "sec-edgar-cover-layout-v4")
        self.assertEqual(
            source.body[
                methodology["paragraph_start"]:methodology["paragraph_end"]
            ],
            methodology["paragraph_quote"],
        )
        self.assertEqual(
            source.body[
                methodology["statement_start"]:methodology["statement_end"]
            ],
            _V04_SEC_SENTENCE,
        )
        self.assertEqual(
            source.body[
                methodology["date_token_start"]:methodology["date_token_end"]
            ],
            "September 21, 2026",
        )
        self.assertEqual(len(source_transport.calls), 2)
        self.assertEqual(len(model_transport.calls), 2)

    def test_v05_prebound_description_does_not_trigger_v04_date_derivation(self):
        from convexity_hunter.host_event import _retain_unknown_context_v0_4

        _resolved, original_context, admission, snapshot, receipt, _records = (
            _sec_v04_fact_case(return_inputs=True)
        )
        prebound_context = replace(
            original_context, event_description_binding="fact-1"
        )
        admission_by_id = {admission.source_id: admission}
        legal_v04_control = _retain_unknown_context_v0_4(
            snapshot,
            receipt,
            prebound_context,
            prebound_context,
            admission_by_id,
        )
        self.assertEqual(
            legal_v04_control.event_date_range.start_date,
            datetime.date(2026, 9, 21),
        )

        with patch(
            "convexity_hunter.host_event._retain_unknown_context_v0_4",
            wraps=_retain_unknown_context_v0_4,
        ) as date_helper:
            prepared, selected_claim_id = _retain_unknown_context_v0_5(
                snapshot, receipt, prebound_context, admission_by_id
            )

        self.assertIsNone(selected_claim_id)
        self.assertEqual(prepared.event_description_binding, "fact-1")
        self.assertIsNone(prepared.event_date_range)
        date_helper.assert_not_called()

    def test_v04_rejects_frozen_occurrence_and_provenance_counterexamples(self):
        duplicate = _V04_SEC_SENTENCE.replace(
            "September 21", "September 22"
        )
        cases = (
            ("url only", {"include_admission": False}),
            ("unverified fact", {"verified_claim": False}),
            ("unverified date binding", {"verified_binding": False}),
            ("wrong date role", {"binding_role": "published_at"}),
            ("wrong binding status", {"binding_status": "unresolved"}),
            ("string offset", {"binding_start_override": "0"}),
            ("boolean offset", {"binding_end_override": True}),
            ("paraphrased claim", {"claim_text": "The company announced an agreement."}),
            ("inconsistent model date", {"model_date": "2026-09-20"}),
            (
                "modal act",
                {
                    "paragraph": _V04_SEC_SENTENCE.replace(
                        "its agreement", "it will complete its agreement"
                    )
                },
            ),
            (
                "negated act",
                {
                    "paragraph": _V04_SEC_SENTENCE.replace(
                        "its agreement", "it did not complete its agreement"
                    )
                },
            ),
            (
                "future event",
                {
                    "paragraph": _V04_SEC_SENTENCE.replace(
                        "September 21, 2026", "September 21, 2027"
                    ),
                    "model_date": "2027-09-21",
                },
            ),
            (
                "second date in selected paragraph",
                {
                    "paragraph": _V04_SEC_SENTENCE + " Filing date: October 1, 2026.",
                    "claim_text": _V04_SEC_SENTENCE,
                },
            ),
            (
                "inner act date",
                {
                    "paragraph": _V04_SEC_SENTENCE.replace(
                        "its agreement with Example Corp.",
                        "it completed an agreement dated October 1, 2026",
                    ),
                },
            ),
            (
                "inner abbreviated date with period",
                {
                    "paragraph": _V04_SEC_SENTENCE.replace(
                        "its agreement with Example Corp.",
                        "the review was dated Sep. 18, 2026",
                    ),
                },
            ),
            (
                "inner abbreviated date without period",
                {
                    "paragraph": _V04_SEC_SENTENCE.replace(
                        "its agreement with Example Corp.",
                        "the review was dated Sep 18, 2026",
                    ),
                },
            ),
            (
                "duplicate same act elsewhere",
                {"extra_paragraphs": (duplicate,)},
            ),
            (
                "correction label",
                {"extra_paragraphs": ("Corrected event date: September 22, 2026.",)},
            ),
            (
                "correction sentence",
                {"extra_paragraphs": ("The foregoing statement is corrected.",)},
            ),
            (
                "embedded denial prefix",
                {
                    "paragraph": "It is not true that " + _V04_SEC_SENTENCE,
                    "claim_text": _V04_SEC_SENTENCE,
                },
            ),
            (
                "publication-only date",
                {
                    "paragraph": "This filing was published on September 21, 2026.",
                    "claim_text": "This filing was published on September 21, 2026.",
                },
            ),
        )
        for label, options in cases:
            with self.subTest(case=label):
                prepared, _context, _admission = _sec_v04_fact_case(**options)
                self.assertIsNone(prepared.event_date_range)

        _client, wrong_cover = _sec_v04_admission(
            (_V04_SEC_SENTENCE,), registrant="Different Holdings, Inc."
        )
        mismatched, _context, _admission = _sec_v04_fact_case(
            admission_override=wrong_cover
        )
        self.assertIsNone(mismatched.event_date_range)

        press_release = (
            "On September 21, 2026, Example Holdings, Inc. issued a press release "
            "describing its agreement with Example Corp."
        )
        accepted, _context, _admission = _sec_v04_fact_case(
            paragraph=press_release, model_date="2026-09-21"
        )
        self.assertEqual(
            accepted.event_date_range.start_date, datetime.date(2026, 9, 21)
        )
        self.assertEqual(
            json.loads(accepted.event_date_range.methodology)["action_role"],
            "announcement",
        )

    def test_casevariant_duplicate_sec_headers_are_rejected(self):
        duplicate_fields = (
            ("form", "CONFORMED SUBMISSION TYPE", "8-K", "10-K"),
            (
                "accession",
                "ACCESSION NUMBER",
                "0000320193-26-000123",
                "0000320193-26-000124",
            ),
            (
                "registrant",
                "COMPANY CONFORMED NAME",
                "ACME HOLDINGS, INC.",
                "OTHER CORPORATION, INC.",
            ),
            ("cik", "CENTRAL INDEX KEY", "0000320193", "0000320194"),
        )
        for key, label, canonical_value, conflicting_value in duplicate_fields:
            for variant, repeated_value in (
                ("same", canonical_value),
                ("conflicting", conflicting_value),
            ):
                with self.subTest(field=key, variant=variant):
                    body = (
                        _SEC_HEADER
                        + "{}: {}\n".format(label.lower(), repeated_value)
                        + _SEC_SENTENCE
                        + "\n"
                    )
                    snapshot, receipt, context = _source_fact_case(body=body)
                    prepared = _retain_unknown_context(snapshot, receipt, context)

                    self.assertEqual(prepared.event_description_binding, "fact-1")
                    self.assertIsNone(prepared.event_date_range)
                    self.assertIs(
                        prepared.source_bodies["sec-fact"],
                        context.source_bodies["sec-fact"],
                    )
                    self.assertEqual(prepared.source_bodies["sec-fact"].body, body)

    def test_create_event_grounder_default_preparer_fills_from_validated_runtime_snapshot(self):
        source_order = (("sec-fact", _SEC_LOCATOR),)
        secondary_fact = "The filing describes a separate source-backed fact."
        source_bodies = {
            _SEC_LOCATOR: _SEC_HEADER + _SEC_SENTENCE + "\n\n" + secondary_fact + "\n"
        }
        config = _config(source_order=source_order)
        discovery, semantic, _normalized = _model_outputs(
            _RUN_ID,
            _RAW_INPUT,
            source_order,
            source_bodies,
            config,
            fact_text=_SEC_SENTENCE,
            event_date="2026-10-03",
            additional_fact_texts=(secondary_fact,),
            coverage_supported=True,
            covered_claim_ids=("fact-1",),
        )
        source_transport = _SyntheticSourceTransport(
            search_order=source_order,
            body_overrides=source_bodies,
        )
        model_transport = _SyntheticModelTransport(discovery, semantic)
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        result = callback(
            _RAW_INPUT,
            run_id=_RUN_ID,
            bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
        )

        prepared = result.build_result.context
        self.assertEqual(prepared.event_description_binding, "fact-1")
        self.assertIsNone(prepared.event_date_range)
        self.assertEqual(
            result._event_fact_anchor_outcome.selected_claim_id, "fact-1"
        )
        from convexity_hunter.host_store import (
            _grounder_stage_outcome,
            _validate_grounder_stage_outcome,
        )

        archived = _grounder_stage_outcome(result, _RUN_ID, _RAW_INPUT)
        self.assertEqual(
            archived["schema_version"], "host-grounder-stage-outcome-v0.4"
        )
        self.assertEqual(
            archived["event_fact_anchor"],
            {
                "subquestion_id": _EVENT_FACT_ANCHOR_SUBQUESTION_ID,
                "selected_claim_id": "fact-1",
            },
        )
        forged = json.loads(json.dumps(archived))
        forged["event_fact_anchor"]["subquestion_id"] = "wrong-question"
        with self.assertRaises(ValueError):
            _validate_grounder_stage_outcome(forged)
        from convexity_hunter.core_application import SourceSubmissionBatch
        from convexity_hunter.event_intelligence import (
            EventIntelligenceSubmission,
            EventSourceReference,
            EventStatement,
            EventStatementKind,
            EventUnderlyingHypothesis,
        )
        from convexity_hunter.host_grounder_runtime import _stamp_event_fact_anchor_outcome
        from convexity_hunter.host_store import _grounder_public_stage_outcome

        now = prepared.observed_at
        submission = EventIntelligenceSubmission(
            submission_id="anchor-submission",
            event_id=prepared.event_id,
            producer_id=prepared.producer_id,
            producer_version=prepared.producer_version,
            observed_at=now,
            event_description=prepared.raw_input.description,
            event_date_range=None,
            sources=(EventSourceReference(
                "source-1", "https://source.example/private-path", "fixture", now
            ),),
            statements=(EventStatement(
                "statement-1", EventStatementKind.OBSERVED_FACT,
                "fixture statement", ("source-1",), (),
            ),),
            hypotheses=(EventUnderlyingHypothesis(
                "hypothesis-1", None, None, None, None, None,
                supporting_statement_ids=("statement-1",),
                uncertainties=("fixture uncertainty",),
            ),),
        )
        batch = SourceSubmissionBatch(prepared.raw_input, (submission,))
        submission_result = _stamp_event_fact_anchor_outcome(
            replace(
                result,
                build_result=replace(
                    result.build_result, submission=submission, source_batch=batch
                ),
            ),
            result._event_fact_anchor_outcome,
        )
        submission_archived = _grounder_stage_outcome(
            submission_result, _RUN_ID, _RAW_INPUT, require_submission=True
        )
        self.assertEqual(
            submission_archived["schema_version"],
            "host-grounder-submission-stage-outcome-v0.3",
        )
        public_submission = _grounder_public_stage_outcome(submission_archived)
        self.assertEqual(
            public_submission["event_fact_anchor"]["selected_claim_id"], "fact-1"
        )
        self.assertNotIn("submission", public_submission)
        self.assertEqual(prepared.underlying_bindings, {})
        self.assertEqual(len(source_transport.calls), 2)
        self.assertEqual(len(model_transport.calls), 2)

    def test_custom_preparer_preserves_sro_date_from_catalog_paragraph_binding(self):
        source_order = (("sro-order", _SRO_ORDER_LOCATOR),)
        source_bodies = {_SRO_ORDER_LOCATOR: _SRO_ORDER_BODY}
        config = _config(source_order=source_order)
        discovery, semantic, _normalized = _model_outputs(
            _RUN_ID,
            _RAW_INPUT,
            source_order,
            source_bodies,
            config,
            fact_text=_SRO_CLAIM_TEXT,
            event_date="2026-04-10",
            fact_evidence_markers=("IT IS THEREFORE ORDERED",),
            date_binding_marker="April 10, 2026",
            coverage_supported=True,
            covered_claim_ids=("fact-1",),
            normal_recipe=False,
        )
        source_transport = _SyntheticSourceTransport(
            search_order=source_order,
            body_overrides=source_bodies,
        )
        model_transport = _SyntheticModelTransport(discovery, semantic)
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
            host_context_preparer=_retain_unknown_context_v0_3,
        )
        result = callback(
            _RAW_INPUT,
            run_id=_RUN_ID,
            bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
        )

        prepared = result.build_result.context
        self.assertEqual(prepared.event_description_binding, "fact-1")
        self.assertEqual(prepared.event_date_range.start_date, datetime.date(2026, 4, 10))
        self.assertEqual(prepared.event_date_range.end_date, datetime.date(2026, 4, 10))
        methodology = json.loads(prepared.event_date_range.methodology)
        self.assertEqual(
            methodology["rule_version"],
            "host-event-source-facts-v0.3/sec-sro-accelerated-approval-occurrence-date",
        )
        body = prepared.source_bodies["sro-order"].body
        expected_body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        self.assertEqual(methodology["body_sha256"], expected_body_hash)
        self.assertEqual(methodology["release_no"], "34-105199")
        self.assertEqual(methodology["file_no"], "SR-Nasdaq-2025-109")
        self.assertEqual(methodology["sro_name"], "The Nasdaq Stock Market LLC")
        cover_start = body.index("SECURITIES AND EXCHANGE COMMISSION")
        cover_end = body.index("\n\n", cover_start)
        cover_paragraph = body[cover_start : cover_end + 1]
        date_start = body.index("April 10, 2026")
        clause_start = body.index(_SRO_OPERATIVE_CLAUSE)
        clause_end = clause_start + len(_SRO_OPERATIVE_CLAUSE)
        order_start = body.rfind("\n\n", 0, clause_start) + 2
        order_end = body.index("\n\n", clause_start)
        order_paragraph = body[order_start : order_end + 1]
        self.assertEqual(methodology["cover_date_quote"], "April 10, 2026")
        self.assertEqual(methodology["cover_date_start"], date_start)
        self.assertEqual(methodology["cover_date_end"], date_start + len("April 10, 2026"))
        self.assertEqual(body[methodology["cover_date_start"] : methodology["cover_date_end"]], "April 10, 2026")
        self.assertEqual(methodology["binding_quote"], cover_paragraph)
        self.assertEqual(body[methodology["binding_start"] : methodology["binding_end"]], cover_paragraph)
        self.assertEqual(methodology["claim_quote"], order_paragraph)
        self.assertEqual(body[methodology["claim_start"] : methodology["claim_end"]], order_paragraph)
        self.assertEqual(methodology["operative_clause_quote"], _SRO_OPERATIVE_CLAUSE)
        self.assertEqual(methodology["operative_clause_start"], clause_start)
        self.assertEqual(methodology["operative_clause_end"], clause_end)
        self.assertEqual(body[clause_start:clause_end], _SRO_OPERATIVE_CLAUSE)
        expected_prior_tokens = ("March 2, 2026", "Apr. 1, 2026", "2026-03-20")
        expected_prior_spans = tuple(
            (body.index(token), body.index(token) + len(token))
            for token in expected_prior_tokens
        )
        self.assertEqual(
            tuple(tuple(span) for span in methodology["prior_date_spans"]),
            expected_prior_spans,
        )
        self.assertEqual(
            tuple(body[start:end] for start, end in expected_prior_spans),
            expected_prior_tokens,
        )
        prior_dates = (
            datetime.date(2026, 3, 2),
            datetime.date(2026, 4, 1),
            datetime.date(2026, 3, 20),
        )
        self.assertTrue(all(value < datetime.date(2026, 4, 10) for value in prior_dates))

        semantic_validation = result.build_result.semantic_validation
        self.assertEqual(semantic_validation.receipt["verified_binding_indices"], (0,))
        self.assertEqual(
            semantic_validation.receipt["source_body_hashes"],
            (("sro-order", expected_body_hash),),
        )
        self.assertEqual(
            semantic_validation.receipt["envelope_hash"],
            hashlib.sha256(semantic_validation.snapshot.canonical_bytes).hexdigest(),
        )
        normalized_envelope = json.loads(semantic_validation.snapshot.canonical_bytes)
        claim = normalized_envelope["claims"][0]
        binding = normalized_envelope["field_bindings"][0]
        self.assertEqual(claim["quote"], methodology["claim_quote"])
        self.assertEqual(binding["quote"], methodology["binding_quote"])
        self.assertEqual(binding["start"], methodology["binding_start"])
        self.assertEqual(binding["end"], methodology["binding_end"])
        self.assertEqual(len(source_transport.calls), 2)
        self.assertEqual(len(model_transport.calls), 2)

    def test_sro_source_fact_grammar_fails_closed_on_mismatch_and_ambiguity(self):
        same_date_body = _SRO_ORDER_BODY.replace(
            "Apr. 1, 2026", "April 10, 2026"
        )
        later_date_body = _SRO_ORDER_BODY.replace(
            "Apr. 1, 2026", "April 11, 2026"
        )
        invalid_date_body = _SRO_ORDER_BODY.replace(
            "March 2, 2026", "Feb. 30, 2026"
        )
        labeled_body = _SRO_ORDER_BODY.replace(
            "Earlier materials include", "Dated: April 1, 2026.\nEarlier materials include"
        )
        cases = (
            ("claim-text-mismatch", {"claim_text": "The Commission conditionally approved it."}),
            ("partial-claim-paragraph", {"claim_quote_override": _SRO_OPERATIVE_CLAUSE}),
            ("unverified-claim", {"verified_claim_ids": ()}),
            ("wrong-claim-id", {"claim_id_override": "fact-2"}),
            ("zero-bindings", {"binding_count": 0}),
            ("duplicate-binding", {"binding_count": 2}),
            ("bool-offset", {"binding_start_override": True}),
            ("partial-paragraph", {"binding_start_delta": 1}),
            ("quote-span-mismatch", {"binding_quote_override": "April 10, 2026"}),
            ("wrong-binding-role", {"binding_role": "publication"}),
            ("wrong-binding-source", {"binding_source_id": "different-source"}),
            ("unverified-binding", {"verified_binding_indices": ()}),
            ("binding-paragraph-misses-cover", {"binding_paragraph": "claim"}),
            ("body-hash-mismatch", {"receipt_body_hash": "0" * 64}),
            ("same-day-reference", {"body": same_date_body}),
            ("later-date-reference", {"body": later_date_body}),
            ("invalid-recognized-date", {"body": invalid_date_body}),
            ("line-start-date-label", {"body": labeled_body}),
            ("wrong-release-url", {"locator": _SRO_ORDER_LOCATOR.replace("105199", "105198")}),
            ("url-query", {"locator": _SRO_ORDER_LOCATOR + "?download=1"}),
            ("url-userinfo", {"locator": _SRO_ORDER_LOCATOR.replace("https://www.sec.gov", "https://sec.gov@www.sec.gov")}),
            ("url-year-mismatch", {"locator": _SRO_ORDER_LOCATOR.replace("/2026/", "/2025/")}),
            ("duplicate-cover-heading", {"body": _SRO_ORDER_BODY + "\nSECURITIES AND EXCHANGE COMMISSION\n"}),
            ("wrong-sro-identity", {"body": _SRO_ORDER_BODY.replace("The Nasdaq Stock Market LLC", "The New York Stock Exchange LLC")}),
            ("wrong-order-title", {"body": _SRO_ORDER_BODY.replace("Order Granting Accelerated Approval", "Order Proposing Accelerated Approval")}),
            ("wrong-operative-file", {"body": _SRO_ORDER_BODY.replace("(SR-Nasdaq-2025-109), as modified", "(SR-Nasdaq-2025-110), as modified")}),
            ("conflicting-disposition", {"body": _SRO_ORDER_BODY.replace("approved on an accelerated basis.", "denied, but approved on an accelerated basis.")}),
            ("title-only-truncation", {"body": _SRO_ORDER_BODY[:_SRO_ORDER_BODY.index("IT IS THEREFORE ORDERED")]}),
            ("missing-signatory", {"body": _SRO_ORDER_BODY[:_SRO_ORDER_BODY.index("For the Commission")]}),
            ("conditional-order", {"body": _SRO_ORDER_BODY.replace("is hereby, approved", "is hereby, conditionally approved")}),
            ("claim-date-mismatch", {"model_date": "2026-04-09"}),
            ("future-cover-date", {"model_date": "2026-10-05", "body": _SRO_ORDER_BODY.replace("April 10, 2026", "October 5, 2026", 1)}),
        )
        for label, options in cases:
            with self.subTest(case=label):
                snapshot, receipt, context = _sro_direct_case(**options)
                prepared = _retain_unknown_context_v0_3(snapshot, receipt, context)
                self.assertIsNone(prepared.event_date_range)

    def test_sro_title_accepts_only_empty_or_official_amendment_notice_prefix(self):
        official_prefix = "Notice of Filing of Amendment Nos. 2 and 3 and "
        official_body = _SRO_ORDER_BODY.replace(
            "Order Granting Accelerated Approval",
            official_prefix + "Order Granting Accelerated Approval",
        )
        snapshot, receipt, context = _sro_direct_case(body=official_body)
        prepared = _retain_unknown_context_v0_3(snapshot, receipt, context)
        self.assertEqual(prepared.event_date_range.start_date, datetime.date(2026, 4, 10))

        rejected_bodies = (
            (
                "draft-title-prefix",
                _SRO_ORDER_BODY.replace(
                    "Order Granting Accelerated Approval",
                    "DRAFT Order Granting Accelerated Approval",
                ),
            ),
            (
                "unknown-title-prefix",
                _SRO_ORDER_BODY.replace(
                    "Order Granting Accelerated Approval",
                    "Notice of Filing of Amendment Nos. 2 and 3 or "
                    "Order Granting Accelerated Approval",
                ),
            ),
            (
                "cover-status-label",
                _SRO_ORDER_BODY.replace(
                    "SECURITIES AND EXCHANGE COMMISSION\n",
                    "SECURITIES AND EXCHANGE COMMISSION\nPRELIMINARY\n",
                ),
            ),
        )
        for label, body in rejected_bodies:
            with self.subTest(case=label):
                snapshot, receipt, context = _sro_direct_case(body=body)
                prepared = _retain_unknown_context_v0_3(snapshot, receipt, context)
                self.assertIsNone(prepared.event_date_range)

    def test_existing_description_mismatch_does_not_receive_candidate_date(self):
        snapshot, receipt, context = _source_fact_case(description="fact-2")
        prepared = _retain_unknown_context(snapshot, receipt, context)
        self.assertIs(prepared, context)
        self.assertEqual(prepared.event_description_binding, "fact-2")
        self.assertIsNone(prepared.event_date_range)

    def test_default_context_preparer_rejects_unbound_or_ambiguous_inputs(self):
        cases = (
            (
                "url-spoof",
                {"locator": _SEC_LOCATOR.replace("www.sec.gov", "www.sec.gov.attacker.invalid")},
                "fact-1",
                None,
            ),
            (
                "url-userinfo",
                {"locator": _SEC_LOCATOR.replace("https://www.sec.gov", "https://sec.gov@www.sec.gov")},
                "fact-1",
                None,
            ),
            (
                "url-nondefault-port",
                {"locator": _SEC_LOCATOR.replace("www.sec.gov", "www.sec.gov:8443")},
                "fact-1",
                None,
            ),
            (
                "url-empty-query",
                {"locator": _SEC_LOCATOR + "?"},
                "fact-1",
                None,
            ),
            (
                "url-encoded-separator",
                {"locator": _SEC_LOCATOR.replace("example.htm", "example%2fother.htm")},
                "fact-1",
                None,
            ),
            (
                "url-extra-path-segment",
                {"locator": _SEC_LOCATOR.replace("example.htm", "extra/example.htm")},
                "fact-1",
                None,
            ),
            (
                "url-locator-cik-mismatch",
                {"locator": _SEC_LOCATOR.replace("/data/320193/", "/data/320194/")},
                "fact-1",
                None,
            ),
            (
                "header-form-mismatch",
                {"body": _SEC_HEADER.replace("8-K", "10-K") + _SEC_SENTENCE + "\n"},
                "fact-1",
                None,
            ),
            (
                "header-accession-mismatch",
                {"body": _SEC_HEADER.replace("000123", "000124") + _SEC_SENTENCE + "\n"},
                "fact-1",
                None,
            ),
            (
                "header-cik-mismatch",
                {"body": _SEC_HEADER.replace("0000320193", "0000320194") + _SEC_SENTENCE + "\n"},
                "fact-1",
                None,
            ),
            (
                "duplicate-header-metadata",
                {"body": _SEC_HEADER + "COMPANY CONFORMED NAME: OTHER CORP\n" + _SEC_SENTENCE + "\n"},
                "fact-1",
                None,
            ),
            (
                "receipt-source-hash-mismatch",
                {"receipt_body_hash": "f" * 64},
                None,
                None,
            ),
            (
                "unverified-fact",
                {"verified_claim": False},
                None,
                None,
            ),
            (
                "unverified-date-binding",
                {"verified_binding": False},
                "fact-1",
                None,
            ),
            (
                "wrong-date-binding-offset",
                {"binding_offset_delta": 1},
                "fact-1",
                None,
            ),
            (
                "model-source-date-disagreement",
                {"model_date": "2026-10-02"},
                "fact-1",
                None,
            ),
            (
                "future-occurrence-date",
                {
                    "sentence": _SEC_SENTENCE.replace("October 3", "October 5"),
                    "model_date": "2026-10-05",
                },
                "fact-1",
                None,
            ),
            (
                "invalid-calendar-date",
                {
                    "sentence": _SEC_SENTENCE.replace("October 3", "February 30"),
                    "model_date": "2026-02-30",
                },
                "fact-1",
                None,
            ),
            (
                "conditional-action",
                {
                    "sentence": (
                        "On October 3, 2026, ACME HOLDINGS, INC. signed a conditional "
                        "agreement to acquire Example Corp."
                    )
                },
                "fact-1",
                None,
            ),
            (
                "multiple-verified-facts",
                {"extra_claim": True},
                None,
                None,
            ),
            (
                "multiple-occurrence-sentences",
                {
                    "body": (
                        _SEC_HEADER
                        + _SEC_SENTENCE
                        + "\nOn October 2, 2026, ACME HOLDINGS, INC. signed another agreement.\n"
                    )
                },
                "fact-1",
                None,
            ),
        )
        for label, options, expected_description, expected_date in cases:
            for preparer in (_retain_unknown_context, _retain_unknown_context_v0_2):
                with self.subTest(case=label, route=preparer.__name__):
                    snapshot, receipt, context = _source_fact_case(**options)
                    prepared = preparer(snapshot, receipt, context)
                    self.assertEqual(
                        prepared.event_description_binding, expected_description
                    )
                    actual_date = (
                        None
                        if prepared.event_date_range is None
                        else prepared.event_date_range.start_date
                    )
                    self.assertEqual(actual_date, expected_date)
                    self.assertEqual(prepared.underlying_bindings, {})

    def test_default_context_preparer_preserves_caller_supplied_fields_by_identity(self):
        supplied_range = MethodologizedDateRange(
            datetime.date(2026, 9, 1),
            datetime.date(2026, 9, 2),
            "caller-supplied methodology",
        )
        supplied_description = "".join(("fact", "-1"))
        snapshot, receipt, context = _source_fact_case(
            extra_claim=True,
            description=supplied_description,
            date_range=supplied_range,
        )
        for preparer in (_retain_unknown_context, _retain_unknown_context_v0_2):
            with self.subTest(route=preparer.__name__):
                prepared = preparer(snapshot, receipt, context)
                self.assertIs(prepared, context)
                self.assertIs(prepared.event_date_range, supplied_range)
                self.assertIs(prepared.event_description_binding, supplied_description)

    def test_run_start_configuration_snapshot_is_exact_safe_and_detached(self):
        callback = create_event_grounder(_config(), repo_root=_ROOT)
        snapshot = callback.configuration_snapshot()
        self.assertEqual(set(snapshot), {"models", "sources", "skills"})
        self.assertEqual(snapshot["skills"], [])
        self.assertEqual(len(snapshot["models"]), 2)
        self.assertEqual(
            [model["role"] for model in snapshot["models"]],
            ["discovery", "semantic"],
        )
        model_fields = {
            "schema_version",
            "provider",
            "model",
            "base_endpoint",
            "role",
            "capabilities",
            "timeout_seconds",
            "request_budget",
            "max_tokens",
            "max_input_bytes",
            "max_output_bytes",
            "remote_enabled",
            "fee_authorized",
            "json_mode",
            "thinking_enabled",
        }
        for model in snapshot["models"]:
            self.assertEqual(set(model), model_fields)
            self.assertEqual(model["schema_version"], "host-event-model-snapshot-v0.1")
            self.assertEqual(model["provider"], "deepseek")
            self.assertEqual(model["base_endpoint"], "https://api.deepseek.com")
        self.assertEqual(len(snapshot["sources"]), 1)
        source = snapshot["sources"][0]
        self.assertEqual(
            set(source),
            {
                "schema_version",
                "provider",
                "paygo_off_confirmed",
                "request_budget",
                "credit_budget",
                "max_request_bytes",
                "max_response_bytes",
                "timeout_seconds",
                "time_budget_seconds",
                "byte_budget",
                "max_search_results",
                "max_extract_urls",
                "grounder_limits",
            },
        )
        self.assertEqual(source["schema_version"], "host-event-source-snapshot-v0.1")
        self.assertEqual(source["provider"], "tavily")
        self.assertEqual(source["grounder_limits"]["run_input_bounds"], {
            "max_run_input_bytes": 20_000,
            "max_string_bytes": 10_000,
            "max_array_items": 10,
        })
        encoded = json.dumps(snapshot, sort_keys=True)
        for forbidden in (
            "SYNTHETIC_TAVILY_KEY",
            "SYNTHETIC_DISCOVERY_KEY",
            "SYNTHETIC_SEMANTIC_KEY",
            "synthetic-only-key",
            "credential_ref",
            "properties_path",
            "env_name",
            "headers",
        ):
            self.assertNotIn(forbidden, encoded)
        self.assertLessEqual(len(encoded.encode("utf-8")), _config().max_json_bytes)

        snapshot["models"][0]["model"] = "caller-mutated-copy"
        fresh_snapshot = callback.configuration_snapshot()
        self.assertEqual(fresh_snapshot["models"][0]["model"], "fixture-discovery")

    def test_factory_revalidates_constructor_bypassed_model_role_and_source_budget(self):
        wrong_role = _config()
        object.__setattr__(wrong_role.discovery_model, "role", "semantic")
        with self.assertRaisesRegex(ValueError, "wrong role"):
            create_event_grounder(wrong_role, repo_root=_ROOT)

        invalid_budget = _config()
        object.__setattr__(invalid_budget.source, "request_budget", 0)
        with self.assertRaisesRegex(ValueError, "INVALID_REQUEST_BUDGET"):
            create_event_grounder(invalid_budget, repo_root=_ROOT)

    def test_factory_rejects_nonapproved_provider_and_endpoint_before_snapshot(self):
        for model_name in ("discovery_model", "semantic_model"):
            for field, value in (
                ("provider", "deepseek-compatible"),
                ("base_endpoint", "https://api.deepseek.com/v1"),
                ("base_endpoint", "https://api.deepseek.com.attacker.invalid"),
            ):
                with self.subTest(model=model_name, field=field, value=value):
                    config = _config()
                    model = getattr(config, model_name)
                    object.__setattr__(model, field, value)
                    source_transport = _SyntheticSourceTransport()
                    model_transport = _SyntheticModelTransport("{}", "{}")
                    with self.assertRaisesRegex(
                        ValueError, "UNAPPROVED_MODEL_CONFIGURATION"
                    ):
                        create_event_grounder(
                            config,
                            repo_root=_ROOT,
                            source_transport=source_transport,
                            discovery_transport=model_transport,
                            semantic_transport=model_transport,
                        )
                    self.assertEqual(source_transport.calls, [])
                    self.assertEqual(model_transport.calls, [])

    def test_resolved_futu_credential_symlink_is_rejected_without_reading_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "futu_api_config.properties"
            target.touch()
            alias = Path(directory) / "external-model.properties"
            alias.symlink_to(target)
            config = _config()
            object.__setattr__(
                config,
                "semantic_credential",
                ModelCredential(properties_path=alias),
            )

            def forbidden_read(*_args, **_kwargs):
                raise AssertionError("credential file contents must not be read")

            with patch.object(Path, "read_text", forbidden_read):
                with self.assertRaisesRegex(ValueError, "futu credential files"):
                    create_event_grounder(config, repo_root=_ROOT)

    def test_constructor_bypassed_core_bounds_fail_before_any_source_call(self):
        config = _config()
        source_transport = _SyntheticSourceTransport()
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
        )
        invalid_bounds = object.__new__(CoreOperationalBounds)
        object.__setattr__(invalid_bounds, "max_submissions", -1)
        object.__setattr__(invalid_bounds, "max_hypotheses", 1)
        object.__setattr__(invalid_bounds, "max_browser_rows", 1)
        object.__setattr__(invalid_bounds, "max_cases", 1)
        object.__setattr__(invalid_bounds, "quote_timeout_seconds", 1.0)

        with self.assertRaisesRegex(TypeError, "valid CoreOperationalBounds"):
            callback(_RAW_INPUT, run_id=_RUN_ID, bounds=invalid_bounds)
        self.assertEqual(source_transport.calls, [])

    def test_factory_config_is_revalidated_again_at_each_call(self):
        source_transport = _SyntheticSourceTransport()
        callback = create_event_grounder(
            _config(),
            repo_root=_ROOT,
            source_transport=source_transport,
        )
        captured_config = inspect.getclosurevars(callback).nonlocals["config"]
        object.__setattr__(captured_config.source, "credit_budget", 0)

        with self.assertRaisesRegex(ValueError, "INVALID_CREDIT_BUDGET"):
            callback(
                _RAW_INPUT,
                run_id=_RUN_ID,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
        self.assertEqual(source_transport.calls, [])

    def test_call_revalidates_model_allowlist_before_transport(self):
        source_transport = _SyntheticSourceTransport()
        callback = create_event_grounder(
            _config(),
            repo_root=_ROOT,
            source_transport=source_transport,
        )
        captured_config = inspect.getclosurevars(callback).nonlocals["config"]
        object.__setattr__(captured_config.semantic_model, "base_endpoint", "https://evil.invalid")

        with self.assertRaisesRegex(ValueError, "UNAPPROVED_MODEL_CONFIGURATION"):
            callback(
                _RAW_INPUT,
                run_id=_RUN_ID,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
        self.assertEqual(source_transport.calls, [])

    def test_synthetic_transport_wiring_returns_exact_runtime_and_fresh_budgets(self):
        config = _config()
        discovery_content, semantic_content, _normalized = _model_outputs(
            _RUN_ID, _RAW_INPUT, _SEARCH_ORDER, _BODY_BY_URL, config,
            normal_recipe=False,
        )
        source_transport = _SyntheticSourceTransport()
        model_transport = _SyntheticModelTransport(discovery_content, semantic_content)
        preparation_calls = []

        def independent_preparer(snapshot, receipt, original_context):
            preparation_calls.append((snapshot, receipt, original_context))
            return original_context

        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
            host_context_preparer=independent_preparer,
        )

        first = callback(
            _RAW_INPUT,
            run_id=_RUN_ID,
            bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
        )
        second = callback(
            _RAW_INPUT,
            run_id=_RUN_ID,
            bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
        )

        self.assertIs(type(first), HostGrounderEvidenceCatalogRuntimeResult)
        self.assertIs(type(second), HostGrounderEvidenceCatalogRuntimeResult)
        self.assertIsNone(first.build_result.submission)
        self.assertIsNone(second.build_result.submission)
        self.assertEqual(len(preparation_calls), 2)
        for snapshot, receipt, context in preparation_calls:
            self.assertTrue(snapshot.envelope_hash)
            self.assertEqual(receipt["schema_version"], "semantic-validation-v0.2")
            self.assertEqual(context.raw_input.description, _RAW_INPUT)
            self.assertIsNone(context.event_description_binding)
            self.assertIsNone(context.event_date_range)
            self.assertEqual(context.underlying_bindings, {})
            self.assertEqual(tuple(context.source_bodies), ("source-z", "source-a"))
            self.assertTrue(
                all(source.published_at is None for source in context.source_bodies.values())
            )

        self.assertEqual(
            source_transport.extract_url_orders,
            [tuple(url for _source_id, url in _SEARCH_ORDER)] * 2,
        )
        self.assertEqual(len(source_transport.calls), 4)
        self.assertEqual(len(model_transport.calls), 4)
        model_user_content = [
            message["content"]
            for call in model_transport.calls
            for message in call["messages"]
            if message["role"] == "user"
        ]
        self.assertTrue(
            all(
                "SEARCH_SNIPPET_MUST_NOT_REACH_MODELS" not in content
                for content in model_user_content
            )
        )
        self.assertTrue(any("ACME filed a report." in content for content in model_user_content))
        system_prompts = [call["messages"][0]["content"] for call in model_transport.calls]
        self.assertTrue(
            any("host-grounder-discovery-prompt-v0.9" in prompt for prompt in system_prompts)
        )
        self.assertTrue(
            any("host-grounder-semantic-verifier-prompt-v0.8" in prompt for prompt in system_prompts)
        )

    def test_event_v06_explicit_budget_two_repairs_format_on_same_source_snapshot(self):
        config = _config()
        config = replace(
            config,
            discovery_model=replace(config.discovery_model, request_budget=2),
        )
        discovery_content, semantic_content, _normalized = _model_outputs(
            _RUN_ID, _RAW_INPUT, _SEARCH_ORDER, _BODY_BY_URL, config,
            normal_recipe=False,
        )
        malformed = "EVENT_REPAIR_SENTINEL_MUST_NOT_BE_ECHOED"
        source_transport = _SyntheticSourceTransport()
        model_transport = _SyntheticModelTransport(
            [malformed, discovery_content], semantic_content
        )
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
            host_context_preparer=lambda _snapshot, _receipt, context: context,
        )

        result = callback(
            _RAW_INPUT,
            run_id=_RUN_ID,
            bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
        )

        self.assertIs(type(result), HostGrounderEvidenceCatalogRuntimeResult)
        self.assertEqual(
            [call["model"] for call in model_transport.calls],
            ["fixture-discovery", "fixture-discovery", "fixture-semantic"],
        )
        self.assertEqual(len(source_transport.calls), 2)
        self.assertEqual(
            source_transport.extract_url_orders,
            [tuple(url for _source_id, url in _SEARCH_ORDER)],
        )
        user_prompts = [
            message["content"]
            for request in model_transport.calls
            for message in request["messages"]
            if message["role"] == "user"
        ]
        self.assertNotIn(malformed, user_prompts[1])
        notice = "\n\nOne bounded format correction"
        self.assertTrue(user_prompts[1].startswith(user_prompts[0] + notice))
        self.assertEqual(
            json.loads(user_prompts[0])["evidence_catalog_json"],
            json.loads(user_prompts[1].split(notice, 1)[0])["evidence_catalog_json"],
        )
        sidecar = json.loads(result.audit.sidecar_utf8)
        self.assertEqual(
            [item["status"] for item in sidecar["producer_attempts"]],
            ["format_rejected", "accepted"],
        )
        self.assertEqual(
            sidecar["producer_attempts"][1]["output_sha256"],
            result.audit.producer_content_sha256,
        )
        self.assertEqual(
            result.audit.producer_content_utf8, discovery_content.encode("utf-8")
        )
        self.assertEqual(
            json.loads(result.audit.normalized_envelope_utf8)["request_id"], _RUN_ID
        )

    def test_partial_extract_is_explicit_failure_and_never_runs_models(self):
        config = _config()
        discovery, semantic, _normalized = _model_outputs(
            _RUN_ID, _RAW_INPUT, _SEARCH_ORDER, _BODY_BY_URL, config
        )
        source_transport = _SyntheticSourceTransport(
            failed_urls={_SEARCH_ORDER[1][1]}
        )
        model_transport = _SyntheticModelTransport(discovery, semantic)
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            callback(
                _RAW_INPUT,
                run_id=_RUN_ID,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
        self.assertEqual(raised.exception.code, "EXTRACTION_FAILURE")
        self.assertEqual(str(raised.exception), "EXTRACTION_FAILURE")
        self.assertEqual(len(source_transport.calls), 2)
        self.assertEqual(model_transport.calls, [])

    def test_empty_extracted_body_is_not_forwarded_to_a_model(self):
        config = _config(source_order=_SEARCH_ORDER[:1])
        discovery, semantic, _normalized = _model_outputs(
            _RUN_ID,
            _RAW_INPUT,
            _SEARCH_ORDER[:1],
            _BODY_BY_URL,
            config,
        )
        source_transport = _SyntheticSourceTransport(
            search_order=_SEARCH_ORDER[:1], body_overrides={_SEARCH_ORDER[0][1]: ""}
        )
        model_transport = _SyntheticModelTransport(discovery, semantic)
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            callback(
                _RAW_INPUT,
                run_id=_RUN_ID,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
        self.assertEqual(raised.exception.code, "EXTRACTION_FAILURE")
        self.assertEqual(model_transport.calls, [])

    def test_source_body_limit_rejects_without_truncation_or_model_calls(self):
        config = _config(max_source_body_bytes=4, source_order=_SEARCH_ORDER[:1])
        discovery, semantic, _normalized = _model_outputs(
            _RUN_ID, _RAW_INPUT, _SEARCH_ORDER[:1], _BODY_BY_URL, config
        )
        source_transport = _SyntheticSourceTransport(search_order=_SEARCH_ORDER[:1])
        model_transport = _SyntheticModelTransport(discovery, semantic)
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            callback(
                _RAW_INPUT,
                run_id=_RUN_ID,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
        self.assertEqual(raised.exception.code, "SOURCE_BODY_LIMIT_EXCEEDED")
        self.assertEqual(model_transport.calls, [])

    def test_date_only_publication_is_not_promoted_to_an_aware_timestamp(self):
        self.assertIsNone(_publication_datetime("2026-10-03"))
        self.assertEqual(
            _publication_datetime("2026-10-03T09:30:00Z"),
            datetime.datetime(2026, 10, 3, 9, 30, tzinfo=datetime.timezone.utc),
        )
