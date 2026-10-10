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
from unittest.mock import patch

from convexity_hunter.core_application import CoreOperationalBounds
from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.event_intelligence import MethodologizedDateRange
from convexity_hunter.host_event import (
    HostEventGrounderConfig,
    _make_listing_source_preparer,
    _retain_unknown_context,
    _publication_datetime,
    create_event_grounder,
)
from convexity_hunter.host_grounder_builder import (
    CallerPolicyProvenance,
    HostBuildContext,
    HostSourceBody,
)
from convexity_hunter.host_grounder_evidence_catalog import (
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
_SEC_HEADER = (
    "CONFORMED SUBMISSION TYPE: 8-K\n"
    "ACCESSION NUMBER: 0000320193-26-000123\n"
    "COMPANY CONFORMED NAME: ACME HOLDINGS, INC.\n"
    "CENTRAL INDEX KEY: 0000320193\n\n"
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


def _context_and_run_input(run_id, raw_input, source_order, bodies_by_url, bounds):
    user_input = UserEventInput(raw_input)
    run_input = HostGrounderRunInput(
        run_id,
        user_input,
        (HostGrounderSubquestion("user_event_input", raw_input),),
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
):
    run_input, context = _context_and_run_input(
        run_id,
        raw_input,
        source_order,
        bodies_by_url,
        config.run_input_bounds,
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
    if fact_text is not None:
        entry = next(
            entry
            for entry in catalog.entries
            if entry.quote.rstrip("\r\n") == fact_text
        )
        evidence_ref = {"evidence_id": entry.evidence_id}
        producer_claims.append(
            {
                "claim_id": "fact-1",
                "kind": "observed_fact",
                "evidence_id": entry.evidence_id,
                "text": fact_text,
                "entity_refs": [],
                "event_date": event_date,
                "published_at": None,
                "dependency_claim_ids": [],
                "uncertainty": [],
                "falsification_conditions": [],
            }
        )
        producer_bindings.append(
            {
                "field_path": "/claims/0/event_date",
                "evidence_id": entry.evidence_id,
                "semantic_role": "date",
                "status": "supported",
            }
        )
        verdict_claims.append(
            {
                "claim_id": "fact-1",
                "outcome": "supported",
                "rationale": "Synthetic source sentence supports the fact.",
                "evidence_refs": [evidence_ref],
            }
        )
        verdict_bindings.append(
            {
                "index": 0,
                "outcome": "supported",
                "rationale": "Synthetic source sentence localizes the date field.",
                "evidence_refs": [evidence_ref],
            }
        )
        coverage_claim_ids.append("fact-1")
    producer = {
        "schema_version": "grounder-output-v0.3",
        "stage": "semantic",
        "request_id": run_id,
        "claims": producer_claims,
        "hypotheses": [],
        "coverage": [
            {
                "subquestion_id": "user_event_input",
                "status": "unresolved",
                "claim_ids": coverage_claim_ids,
                "gap": "Synthetic fixture supplies no supported hypothesis.",
            }
        ],
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
                "outcome": "unresolved",
                "rationale": "The synthetic fixture does not establish an answer.",
                "evidence_refs": [],
            }
        ],
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
    receipt = MappingProxyType(
        {
            "schema_version": "semantic-validation-v0.2",
            "run_id": _RUN_ID,
            "canonical_input_hash": context.canonical_input_hash,
            "envelope_hash": envelope_hash,
            "source_body_hashes": (
                (source_id, receipt_body_hash or source.body_sha256),
            ),
            "verified_claim_ids": (
                ("fact-1", "fact-2") if extra_claim else ("fact-1",)
            ) if verified_claim else (),
            "verified_binding_indices": (0,) if verified_binding else (),
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


def _listing_runtime_wires(run_id, symbol, source_order, bodies_by_url, config):
    run_input, context = _context_and_run_input(
        run_id,
        "Assess a synthetic listing event.",
        source_order,
        bodies_by_url,
        config.run_input_bounds,
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
        "coverage": [
            {
                "subquestion_id": "user_event_input",
                "status": "supported",
                "claim_ids": [claim_id],
                "gap": None,
            }
        ],
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
        ],
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
            _retain_unknown_context,
        )
        self.assertEqual(
            tuple(inspect.signature(callback).parameters),
            ("raw_input", "run_id", "bounds"),
        )
        self.assertNotIn("SYNTHETIC", repr(config))
        with self.assertRaisesRegex(TypeError, "host_context_preparer"):
            create_event_grounder(config, repo_root=_ROOT, host_context_preparer=object())

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
            run_id, symbol, source_order, bodies_by_url, config
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
        source_bodies = {_SEC_LOCATOR: _SEC_HEADER + _SEC_SENTENCE + "\n"}
        config = _config(source_order=source_order)
        discovery, semantic, _normalized = _model_outputs(
            _RUN_ID,
            _RAW_INPUT,
            source_order,
            source_bodies,
            config,
            fact_text=_SEC_SENTENCE,
            event_date="2026-10-03",
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
        self.assertEqual(prepared.event_date_range.start_date, datetime.date(2026, 10, 3))
        self.assertEqual(prepared.event_date_range.end_date, datetime.date(2026, 10, 3))
        self.assertEqual(prepared.underlying_bindings, {})
        self.assertEqual(len(source_transport.calls), 2)
        self.assertEqual(len(model_transport.calls), 2)

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
            with self.subTest(case=label):
                snapshot, receipt, context = _source_fact_case(**options)
                prepared = _retain_unknown_context(snapshot, receipt, context)
                self.assertEqual(prepared.event_description_binding, expected_description)
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
        snapshot, receipt, context = _source_fact_case(
            description="caller-supplied description", date_range=supplied_range
        )
        prepared = _retain_unknown_context(snapshot, receipt, context)
        self.assertIs(prepared, context)
        self.assertIs(prepared.event_date_range, supplied_range)
        self.assertEqual(prepared.event_description_binding, "caller-supplied description")

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
            _RUN_ID, _RAW_INPUT, _SEARCH_ORDER, _BODY_BY_URL, config
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
            any("host-grounder-discovery-prompt-v0.7" in prompt for prompt in system_prompts)
        )
        self.assertTrue(
            any("host-grounder-semantic-verifier-prompt-v0.7" in prompt for prompt in system_prompts)
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
