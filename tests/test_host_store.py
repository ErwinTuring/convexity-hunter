"""Focused tests for the private versioned Host SQLite journal."""

import datetime
import decimal
import hashlib
import contextlib
import io
import json
import logging
import os
import pathlib
import sqlite3
import stat
import sys
import tempfile
import traceback
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter.core_application import CoreDirectResult, CoreOperationalBounds
from convexity_hunter import core_research as core
from convexity_hunter.core_presentation import report
from convexity_hunter.market_data import DataOrigin, SourceQualityFlag, SourceReference
from convexity_hunter.host_profile import STANDARD_RESEARCH_PROFILE
from convexity_hunter.host_store import (
    HostStore,
    HostStoreError,
    SCHEMA_VERSION,
    StoreCorruptionError,
    UnsupportedSchemaVersionError,
)


BOUNDS = CoreOperationalBounds(
    max_submissions=2,
    max_hypotheses=3,
    max_browser_rows=20,
    max_cases=8,
    quote_timeout_seconds=2.5,
)
BLOCKED_REASON = "HOST_EXECUTOR_NOT_CONFIGURED"
HOST_SHELL_VERSION = "host-server-v0.1"


def _run_start_metadata():
    """Frozen legacy fixture, independent of the concurrently edited HTTP shell."""

    return {
        "configuration_snapshot": {"models": [], "sources": [], "skills": []},
        "execution_snapshot": {},
        "contract_versions": {
            "architecture": "standalone-mvp-architecture-v0.1",
            "host_shell": HOST_SHELL_VERSION,
            "standard_research_profile": "standard-research-profile:v0.1",
        },
    }


def _event_configuration_snapshot():
    def model(role):
        return {
            "schema_version": "host-event-model-snapshot-v0.1",
            "provider": "fixture-provider",
            "model": "fixture-model",
            "base_endpoint": "https://models.example.test/v1",
            "role": role,
            "capabilities": ["chat_completions", "json_mode"],
            "timeout_seconds": 2.5,
            "request_budget": 2,
            "max_tokens": 128,
            "max_input_bytes": 8192,
            "max_output_bytes": 4096,
            "remote_enabled": True,
            "fee_authorized": True,
            "json_mode": True,
            "thinking_enabled": False,
        }

    return {
        "models": [model("discovery"), model("semantic")],
        "sources": [{
            "schema_version": "host-event-source-snapshot-v0.1",
            "provider": "tavily",
            "paygo_off_confirmed": True,
            "request_budget": 3,
            "credit_budget": 12,
            "max_request_bytes": 8192,
            "max_response_bytes": 65536,
            "timeout_seconds": 2.5,
            "time_budget_seconds": 20.0,
            "byte_budget": 131072,
            "max_search_results": 5,
            "max_extract_urls": 5,
            "grounder_limits": {
                "run_input_bounds": {
                    "max_run_input_bytes": 8192,
                    "max_string_bytes": 4096,
                    "max_array_items": 20,
                },
                "max_json_bytes": 131072,
                "max_source_body_bytes": 131072,
                "max_catalog_entries": 100,
                "max_catalog_bytes": 262144,
                "max_catalog_paragraphs": 200,
            },
        }],
        "skills": [],
    }


def blocked_outcome():
    return {
        "executor_status": "NOT_CONFIGURED",
        "reason": BLOCKED_REASON,
        "host_shell_version": HOST_SHELL_VERSION,
    }


def make_direct_result(*, cached_report=True, source_uri="https://example.test/quote"):
    observed = datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc)
    source = SourceReference(
        source_id="synthetic-quote", provider_name="synthetic", dataset_name="option-ask",
        provider_record_id="record-1", provider_request_id="request-1", source_symbol="XYZ",
        source_uri=source_uri, observed_at=observed, retrieved_at=observed,
        provider_timezone="UTC", timestamp_methodology="synthetic observation",
        origin=DataOrigin.EXCHANGE_OBSERVED, is_delayed=False, declared_delay_seconds=None,
        payload_sha256="a" * 64, revision_number=1, provider_correction_id=None,
        quality_flags=(SourceQualityFlag.CORRECTED,),
    )
    provenance = core.CoreProvenance(source, "synthetic retained evidence")
    identifier = "US.XYZ270115C100000"
    leg = core.CoreLeg(identifier, "XYZ", "USD", core.CoreOptionType.CALL,
                       decimal.Decimal("100.00"), datetime.date(2027, 1, 15), 1, 100,
                       decimal.Decimal("2.50"), core.CoreAskAuthority.INDICATIVE_ONLY,
                       "synthetic declared leg", provenance)
    structure = core.CoreStructure((leg,), "synthetic declared structure", provenance)
    request = STANDARD_RESEARCH_PROFILE.request_factory(
        case_id="direct:" + identifier, structure=structure, context=None
    )
    result = CoreDirectResult(
        raw_input=object(), core_structure=structure,
        exact_verifications=(SimpleNamespace(provider_identifier=identifier),),
        native_quotes=(object(),), provider_references=(object(),),
        kernel_request=request, kernel_result=core.evaluate_core_research(request),
        reasons=(), full_report="",
    )
    return replace(result, full_report=report(result)) if cached_report else result


def make_grounder_no_submission_result(run_id="grounder-run"):
    """Synthetic typed fixture for the future stage journal API; never a live run."""

    from types import MappingProxyType

    from convexity_hunter.event_entry import UserEventInput
    from convexity_hunter.host_grounder_builder import (
        CoverageSidecar,
        FieldBindingSidecar,
        HostBuildContext,
        HostBuildDiagnostic,
        HostBuildResult,
        HostSourceBody,
        SemanticValidationRecord,
    )
    from convexity_hunter.host_grounder_evidence_catalog import HostEvidenceCatalogAudit
    from convexity_hunter.host_grounder_receipt import ValidatedEnvelopeSnapshot
    from convexity_hunter.host_grounder_runtime import (
        HostGrounderCallSummary,
        HostGrounderEvidenceCatalogRuntimeResult,
    )

    def canonical(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    now = datetime.datetime(2026, 1, 2, tzinfo=datetime.timezone.utc)
    raw_input = UserEventInput("synthetic fixture event")
    body = "synthetic source body; never persisted by the stage projection"
    body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    context = HostBuildContext(
        raw_input=raw_input,
        submission_id="submission-1",
        event_id="event-1",
        producer_id="host-grounder",
        producer_version="0.3",
        observed_at=now,
        source_bodies={
            "source-1": HostSourceBody(body, body_hash, "https://source.example/item", now)
        },
        run_id=run_id,
        canonical_input_hash="a" * 64,
    )
    envelope = {
        "schema_version": "grounder-output-v0.1",
        "stage": "semantic",
        "request_id": run_id,
        "claims": [{"claim_id": "claim-private", "text": "PRIVATE_CLAIM_TEXT"}],
        "hypotheses": [],
        "coverage": [{
            "subquestion_id": "question-1", "status": "unresolved",
            "claim_ids": [], "gap": "PRIVATE_GAP_TEXT",
        }],
        "field_bindings": [{}],
    }
    envelope_bytes = canonical(envelope).encode("utf-8")
    envelope_hash = hashlib.sha256(envelope_bytes).hexdigest()
    receipt = MappingProxyType({
        "schema_version": "semantic-validation-v0.2",
        "run_id": run_id,
        "canonical_input_hash": context.canonical_input_hash,
        "envelope_hash": envelope_hash,
        "source_body_hashes": (("source-1", body_hash),),
        "validator_id": "fixture-validator",
        "validator_version": "host-grounder-semantic-verifier-prompt-v0.7",
        "verified_claim_ids": ("claim-private",),
        "rejected_claims": (),
        "verified_hypothesis_ids": (),
        "rejected_hypotheses": (),
        "verified_binding_indices": (0,),
        "rejected_bindings": (),
        "coverage_outcomes": ((0, "question-1", "unresolved", "PRIVATE_VALIDATOR_RATIONALE"),),
    })
    semantic = SemanticValidationRecord(
        run_id, context.canonical_input_hash, envelope_hash, receipt,
        ValidatedEnvelopeSnapshot(envelope_bytes, envelope_hash),
    )
    source_hashes = [{"source_id": "source-1", "sha256": body_hash}]
    catalog_bytes = b"PRIVATE_CATALOG_BYTES"
    producer_bytes = b"PRIVATE_MODEL_BODY_AND_MODEL_RATIONALE"
    sidecar = {
        "schema_version": "host-grounder-quote-localization-audit-v0.3",
        "run_id": run_id,
        "canonical_input_hash": context.canonical_input_hash,
        "producer_wire_version": "grounder-output-v0.3",
        "producer_prompt_version": "host-grounder-discovery-prompt-v0.6",
        "producer_content_sha256": hashlib.sha256(producer_bytes).hexdigest(),
        "normalized_envelope_sha256": envelope_hash,
        "source_body_hashes": source_hashes,
        "verifier_wire_version": "semantic-verdict-v0.3",
        "validator_version": "host-grounder-semantic-verifier-prompt-v0.7",
        "localizer_version": "host-evidence-catalog-resolver-v0.1",
        "catalog_schema_version": "host-grounder-evidence-catalog-v0.1",
        "catalog_generator_version": "host-evidence-paragraph-generator-v0.1",
        "catalog_sha256": hashlib.sha256(catalog_bytes).hexdigest(),
    }
    sidecar_bytes = canonical(sidecar).encode("utf-8")
    audit = HostEvidenceCatalogAudit(
        catalog_bytes, producer_bytes, envelope_bytes, sidecar_bytes,
        sidecar["catalog_sha256"], sidecar["producer_content_sha256"],
        envelope_hash, hashlib.sha256(sidecar_bytes).hexdigest(),
    )
    build = HostBuildResult(
        context,
        raw_input,
        None,
        None,
        (CoverageSidecar(
            0, "question-1", "unresolved", "unresolved", (),
            "PRIVATE_GAP_TEXT", "PRIVATE_VALIDATOR_RATIONALE",
        ),),
        (FieldBindingSidecar(
            0, "event.description", "source-1", "PRIVATE_QUOTE", 0, 1,
            "description", "supported", "verified", None,
        ),),
        semantic,
        (
            HostBuildDiagnostic("CLAIM_NOT_PROJECTABLE", "claim", "claim-private", "PRIVATE_REASON"),
            HostBuildDiagnostic("NO_PROJECTABLE_HYPOTHESIS", None, None, "PRIVATE_REASON"),
        ),
    )
    return HostGrounderEvidenceCatalogRuntimeResult(
        build,
        HostGrounderCallSummary("discovery", "fixture-provider", "fixture-model", "fixture-model", "unused-id", "stop", 10, 20),
        HostGrounderCallSummary("semantic", "fixture-provider", "fixture-model", "fixture-model", "unused-id", "stop", 10, 20),
        audit,
    )


def make_grounder_retry_result(run_id="grounder-run"):
    from convexity_hunter.host_grounder_evidence_catalog import (
        HostEvidenceCatalogCallAudit,
        HostEvidenceCatalogProducerAttempt,
    )

    result = make_grounder_no_submission_result(run_id)
    malformed = b"STORE_REPAIR_MALFORMED_SENTINEL"

    def call_audit(bytes_received):
        return HostEvidenceCatalogCallAudit(
            provider=result.discovery_call.provider,
            requested_model=result.discovery_call.requested_model,
            returned_model=result.discovery_call.returned_model,
            finish_reason=result.discovery_call.finish_reason,
            bytes_sent=result.discovery_call.bytes_sent,
            bytes_received=bytes_received,
        )

    attempts = (
        HostEvidenceCatalogProducerAttempt(
            index=1,
            status="format_rejected",
            output_sha256=hashlib.sha256(malformed).hexdigest(),
            failure_check="producer_v0_3_json_format",
            failure_code=None,
            call=call_audit(len(malformed)),
        ),
        HostEvidenceCatalogProducerAttempt(
            index=2,
            status="accepted",
            output_sha256=result.audit.producer_content_sha256,
            failure_check=None,
            failure_code=None,
            call=call_audit(result.discovery_call.bytes_received),
        ),
    )
    sidecar = json.loads(result.audit.sidecar_utf8)
    sidecar["schema_version"] = "host-grounder-quote-localization-audit-v0.4"
    sidecar["producer_attempts"] = [attempt.to_json() for attempt in attempts]
    sidecar["producer_repair_prompt_version"] = "host-grounder-discovery-format-repair-v0.1"
    sidecar_wire = json.dumps(
        sidecar, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    audit = replace(
        result.audit,
        sidecar_utf8=sidecar_wire,
        sidecar_sha256=hashlib.sha256(sidecar_wire).hexdigest(),
        producer_attempts=attempts,
    )
    return replace(result, audit=audit), malformed


def make_grounder_submission_result(run_id="grounder-run"):
    from convexity_hunter.core_application import SourceSubmissionBatch
    from convexity_hunter.event_intelligence import (
        EventIntelligenceSubmission,
        EventSourceReference,
        EventStatement,
        EventStatementKind,
        EventUnderlyingHypothesis,
    )

    result = make_grounder_no_submission_result(run_id)
    context = result.build_result.context
    now = context.observed_at
    submission = EventIntelligenceSubmission(
        submission_id="submission-1",
        event_id="event-1",
        producer_id="host-grounder",
        producer_version="0.3",
        observed_at=now,
        event_description=context.raw_input.description,
        event_date_range=None,
        sources=(EventSourceReference(
            "source-1", "https://private.example/source/private-path", "PRIVATE_SOURCE_TITLE", now
        ),),
        statements=(EventStatement(
            "statement-1", EventStatementKind.OBSERVED_FACT,
            "PRIVATE_SUBMISSION_STATEMENT", ("source-1",), (),
        ),),
        hypotheses=(EventUnderlyingHypothesis(
            "hypothesis-1", None, None, None, None, None,
            supporting_statement_ids=("statement-1",),
            uncertainties=("PRIVATE_SUBMISSION_UNCERTAINTY",),
        ),),
    )
    batch = SourceSubmissionBatch(context.raw_input, (submission,))
    build = replace(result.build_result, submission=submission, source_batch=batch)
    return replace(result, build_result=build)


def make_v1_database(path):
    connection = sqlite3.connect(str(path))
    connection.execute("CREATE TABLE runs(run_seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL)")
    connection.execute(
        "CREATE TABLE events(event_seq INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT NOT NULL REFERENCES runs(run_id),"
        "event_type TEXT NOT NULL CHECK(event_type IN ('run_started','stage_started','stage_finished','run_finished')),"
        "stage_id TEXT,stage_name TEXT,status TEXT NOT NULL,payload_json TEXT NOT NULL,occurred_at TEXT NOT NULL,"
        "CHECK((event_type IN ('run_started','run_finished') AND stage_id IS NULL AND stage_name IS NULL) OR "
        "(event_type IN ('stage_started','stage_finished') AND stage_id IS NOT NULL AND stage_name IS NOT NULL)))"
    )
    for table in ("runs", "events"):
        for operation in ("update", "delete"):
            connection.execute("CREATE TRIGGER {}_no_{} BEFORE {} ON {} BEGIN SELECT RAISE(ABORT,'append-only journal'); END".format(table, operation, operation, table))
    snapshot = {
        "mode": "world", "input": "legacy exact input", "input_sha256": hashlib.sha256(b"legacy exact input").hexdigest(),
        "bounds": {name: getattr(BOUNDS, name) for name in BOUNDS.__dataclass_fields__},
        "profile_snapshot": STANDARD_RESEARCH_PROFILE.snapshot(), "metadata": _run_start_metadata(),
    }
    snapshot["metadata"]["execution_snapshot"] = {}
    now = "2026-01-02T00:00:00.000Z"
    connection.execute("INSERT INTO runs(run_id,created_at) VALUES('legacy-run',?)", (now,))
    for event, stage_id, name, status, payload in (
        ("run_started", None, None, "RUNNING", snapshot),
        ("stage_started", "legacy-stage", "executor", "RUNNING", {}),
        ("stage_finished", "legacy-stage", "executor", "BLOCKED", {"outcome": blocked_outcome(), "diagnostics": [BLOCKED_REASON]}),
        ("run_finished", None, None, "BLOCKED", {"diagnostics": [BLOCKED_REASON]}),
    ):
        connection.execute("INSERT INTO events(run_id,event_type,stage_id,stage_name,status,payload_json,occurred_at) VALUES(?,?,?,?,?,?,?)",
                           ("legacy-run", event, stage_id, name, status, json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True), now))
    connection.execute("PRAGMA application_id=1128811057")
    connection.execute("PRAGMA user_version=1")
    connection.commit()
    rows = connection.execute("SELECT * FROM events ORDER BY event_seq").fetchall()
    connection.close()
    return rows


class HostStoreTests(unittest.TestCase):
    def setUp(self):
        canonical_temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
        self.temporary = tempfile.TemporaryDirectory(dir=str(canonical_temp_root))
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.db_path = self.root / "journal.sqlite3"
        self.store = HostStore(self.db_path)
        self.addCleanup(self.store.close)

    def create_run(self, mode="world", raw_input="named event; keep exact spacing\n"):
        return self.store.create_run(
            mode,
            raw_input,
            BOUNDS,
            STANDARD_RESEARCH_PROFILE.snapshot(),
            _run_start_metadata(),
        )

    def test_private_permissions_and_schema_identity(self):
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.db_path.stat().st_mode), 0o600)
        lock_path = self.db_path.with_name(self.db_path.name + ".lock")
        lock_identity = (lock_path.stat().st_dev, lock_path.stat().st_ino)
        self.assertEqual(stat.S_IMODE(lock_path.stat().st_mode), 0o600)
        connection = sqlite3.connect(str(self.db_path))
        try:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], SCHEMA_VERSION)
            self.assertNotEqual(connection.execute("PRAGMA application_id").fetchone()[0], 0)
        finally:
            connection.close()
        self.store.close()
        self.assertTrue(lock_path.is_file())
        reopened = HostStore(self.db_path)
        self.addCleanup(reopened.close)
        self.assertEqual(
            (lock_path.stat().st_dev, lock_path.stat().st_ino), lock_identity
        )

    def test_snapshot_state_history_and_detached_reads(self):
        run_id = self.create_run("event")
        started = self.store.get_run(run_id)
        self.assertEqual(started["status"], "RUNNING")
        self.assertEqual(started["input"], "named event; keep exact spacing\n")
        self.assertEqual(
            set(started["bounds"]),
            {
                "max_submissions",
                "max_hypotheses",
                "max_browser_rows",
                "max_cases",
                "quote_timeout_seconds",
            },
        )
        started["bounds"]["max_cases"] = 999
        self.assertEqual(self.store.get_run(run_id)["bounds"]["max_cases"], 8)

        stage_id = self.store.start_stage(run_id, "executor")
        self.store.finish_stage(
            run_id,
            stage_id,
            "BLOCKED",
            blocked_outcome(),
            (BLOCKED_REASON,),
        )
        self.store.finish_run(run_id, "BLOCKED", (BLOCKED_REASON,))

        run = self.store.get_run(run_id)
        self.assertEqual(run["status"], "BLOCKED")
        self.assertEqual(run["diagnostics"], [BLOCKED_REASON])
        self.assertEqual([event["event"] for event in run["events"]], ["stage_started", "stage_finished"])
        self.assertEqual(run["events"][1]["outcome"], blocked_outcome())
        self.assertEqual(self.store.list_runs()[0]["run_id"], run_id)
        self.assertIsNone(self.store.get_run("missing-run"))

    def test_grounder_missing_submission_commits_sanitized_stage_without_core_archive(self):
        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        result = make_grounder_no_submission_result(run_id)

        self.assertIsNone(self.store.save_grounder_stage_result(run_id, stage_id, result))
        run = self.store.get_run(run_id)
        self.assertEqual(run["status"], "BLOCKED")
        self.assertEqual(run["diagnostics"], ["GROUNDING_NO_SUBMISSION"])
        outcome = run["events"][-1]["outcome"]
        self.assertEqual(outcome["schema_version"], "host-grounder-stage-outcome-v0.1")
        self.assertEqual(
            [outcome[name] for name in (
                "grounder_status", "source_status", "semantic_status", "builder_status",
                "submission_status", "ei_status",
            )],
            ["COMPLETED", "UNKNOWN", "RECEIPT_VALIDATED", "COMPLETED", "MISSING", "NOT_RUN"],
        )
        self.assertEqual(outcome["counts"], {
            "source_body_count": 1,
            "claim_count": 1,
            "hypothesis_count": 0,
            "field_binding_count": 1,
            "coverage_count": 1,
        })
        self.assertEqual(outcome["diagnostic_counts"], [
            {"code": "CLAIM_NOT_PROJECTABLE", "count": 1},
            {"code": "NO_PROJECTABLE_HYPOTHESIS", "count": 1},
        ])
        self.assertEqual(outcome["coverage"], [{
            "index": 0,
            "subquestion_id": "question-1",
            "model_status": "unresolved",
            "validator_status": "unresolved",
            "claim_count": 0,
            "gap_present": True,
        }])
        self.assertEqual(run["events"][1]["stage"], "grounder")
        self.assertEqual(run["events"][1]["status"], "COMPLETED")
        archive_wire = "".join(
            row[0] for row in self.store._conn().execute(
                "SELECT payload_json FROM events WHERE run_id=?", (run_id,)
            ).fetchall()
        )
        for private_value in (
            "PRIVATE_MODEL_BODY_AND_MODEL_RATIONALE", "PRIVATE_CLAIM_TEXT",
            "PRIVATE_GAP_TEXT", "PRIVATE_VALIDATOR_RATIONALE", "PRIVATE_REASON",
            "PRIVATE_CATALOG_BYTES", "PRIVATE_QUOTE", "unused-id",
            "synthetic source body; never persisted",
        ):
            self.assertNotIn(private_value, archive_wire)
        self.assertIsNone(self.store._conn().execute(
            "SELECT 1 FROM direct_cases WHERE run_id=?", (run_id,)
        ).fetchone())
        self.assertIsNone(self.store._conn().execute(
            "SELECT 1 FROM batch_archives WHERE run_id=?", (run_id,)
        ).fetchone())

        self.store.close()
        reopened = HostStore(self.db_path)
        self.addCleanup(reopened.close)
        reopened_run = reopened.get_run(run_id)
        reopened_outcome = reopened_run["events"][1]["outcome"]
        self.assertEqual(reopened_run["status"], "BLOCKED")
        self.assertEqual(
            reopened_outcome["schema_version"], "host-grounder-stage-outcome-v0.1"
        )
        self.assertNotIn("producer_attempts", reopened_outcome["provenance"])

    def test_grounder_retry_success_archive_reopens_both_attempt_receipts(self):
        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        result, malformed = make_grounder_retry_result(run_id)
        malformed_hash = hashlib.sha256(malformed).hexdigest()
        accepted_hash = result.audit.producer_content_sha256

        self.store.save_grounder_stage_result(run_id, stage_id, result)
        outcome = self.store.get_run(run_id)["events"][1]["outcome"]
        self.assertEqual(
            outcome["schema_version"], "host-grounder-stage-outcome-v0.2"
        )
        self.assertEqual(
            [item["output_sha256"] for item in outcome["provenance"]["producer_attempts"]],
            [malformed_hash, accepted_hash],
        )
        self.assertEqual(
            outcome["provenance"]["producer_attempts"][1]["output_sha256"],
            outcome["provenance"]["producer_content_sha256"],
        )
        self.store.close()

        reopened = HostStore(self.db_path)
        self.addCleanup(reopened.close)
        reopened_run = reopened.get_run(run_id)
        reopened_outcome = reopened_run["events"][1]["outcome"]
        self.assertEqual(reopened_run["status"], "BLOCKED")
        self.assertEqual(
            [item["output_sha256"] for item in reopened_outcome["provenance"]["producer_attempts"]],
            [malformed_hash, accepted_hash],
        )
        self.assertTrue(
            all(item["call"] is not None
                for item in reopened_outcome["provenance"]["producer_attempts"])
        )
        self.assertNotIn(malformed.decode("utf-8"), json.dumps(reopened_run))

    def test_grounder_retry_failure_archive_reopens_completed_attempts_without_raw_text(self):
        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        result, malformed = make_grounder_retry_result(run_id)
        first, accepted = result.audit.producer_attempts
        second_rejected = replace(
            accepted,
            status="format_rejected",
            failure_check="producer_v0_3_closed_shape",
        )
        failure_outcome = {
            "schema_version": "host-grounder-producer-failure-audit-v0.1",
            "status": "FAILED",
            "producer_attempts": [first.to_json(), second_rejected.to_json()],
        }

        self.store.finish_stage(
            run_id, stage_id, "FAILED", failure_outcome,
            ("PRODUCER_ENVELOPE_INVALID",),
        )
        self.store.finish_run(run_id, "FAILED", ("PRODUCER_ENVELOPE_INVALID",))
        expected_hashes = [
            item["output_sha256"] for item in failure_outcome["producer_attempts"]
        ]
        self.store.close()

        reopened = HostStore(self.db_path)
        self.addCleanup(reopened.close)
        reopened_run = reopened.get_run(run_id)
        audit = reopened_run["events"][1]["outcome"]
        self.assertEqual(reopened_run["status"], "FAILED")
        self.assertEqual(
            [item["output_sha256"] for item in audit["producer_attempts"]],
            expected_hashes,
        )
        self.assertTrue(all(item["call"] is not None for item in audit["producer_attempts"]))
        self.assertNotIn(malformed.decode("utf-8"), json.dumps(reopened_run))

    def test_grounder_archive_accepts_only_registered_producer_prompt_versions(self):
        from convexity_hunter.host_store import (
            _grounder_stage_outcome,
            _validate_grounder_stage_outcome,
        )

        result = make_grounder_no_submission_result()
        run_id = result.build_result.context.run_id
        outcome = _grounder_stage_outcome(
            result, run_id, "synthetic fixture event"
        )
        sidecar = json.loads(result.audit.sidecar_utf8.decode("utf-8"))
        self.assertEqual(
            outcome["provenance"]["producer_prompt_version"],
            sidecar["producer_prompt_version"],
        )

        unsupported = dict(outcome)
        unsupported["provenance"] = dict(outcome["provenance"])
        unsupported["provenance"]["producer_prompt_version"] = (
            "host-grounder-discovery-prompt-v0.8"
        )
        with self.assertRaisesRegex(ValueError, "producer prompt version is not registered"):
            _validate_grounder_stage_outcome(unsupported)

        sidecar["producer_prompt_version"] = "host-grounder-discovery-prompt-v0.8"
        sidecar_wire = json.dumps(
            sidecar, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        unsupported_audit = replace(
            result.audit,
            sidecar_utf8=sidecar_wire,
            sidecar_sha256=hashlib.sha256(sidecar_wire).hexdigest(),
        )
        with self.assertRaisesRegex(ValueError, "audit versions do not identify"):
            _grounder_stage_outcome(
                replace(result, audit=unsupported_audit),
                run_id,
                "synthetic fixture event",
            )

    def test_grounder_rejects_submission_and_wrong_mode_without_partial_events(self):
        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        result = make_grounder_no_submission_result(run_id)
        submitted = replace(result, build_result=replace(result.build_result, submission=object()))
        with self.assertRaisesRegex(ValueError, "missing EI submission"):
            self.store.save_grounder_stage_result(run_id, stage_id, submitted)
        self.assertEqual(self.store.get_run(run_id)["status"], "RUNNING")
        self.assertEqual(len(self.store.get_run(run_id)["events"]), 1)

        world_run = self.create_run("world", "synthetic fixture event")
        world_stage = self.store.start_stage(world_run, "grounder")
        with self.assertRaisesRegex(ValueError, "restricted to Event runs"):
            self.store.save_grounder_stage_result(
                world_run, world_stage, make_grounder_no_submission_result(world_run)
            )
        self.assertEqual(self.store.get_run(world_run)["status"], "RUNNING")
        self.assertEqual(len(self.store.get_run(world_run)["events"]), 1)

    def test_grounder_submission_stage_persists_assessed_closed_snapshot_and_safe_history(self):
        from convexity_hunter.event_intelligence import assess_event_intelligence_submission

        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        result = make_grounder_submission_result(run_id)
        self.assertIsNone(
            self.store.save_grounder_submission_stage_result(run_id, stage_id, result)
        )

        run = self.store.get_run(run_id)
        self.assertEqual(run["status"], "RUNNING")
        self.assertEqual([event["event"] for event in run["events"]], ["stage_started", "stage_finished"])
        self.assertEqual(run["events"][-1]["status"], "COMPLETED")
        public = run["events"][-1]["outcome"]
        self.assertEqual(public["schema_version"], "host-grounder-submission-stage-outcome-v0.1")
        self.assertEqual(public["submission_status"], "PRESENT")
        self.assertEqual(public["ei_status"], "ASSESSED")
        self.assertEqual(public["source_batch_count"], 1)
        self.assertNotIn("submission", public)

        raw = self.store._conn().execute(
            "SELECT payload_json FROM events WHERE run_id=? AND event_type='stage_finished'",
            (run_id,),
        ).fetchone()["payload_json"]
        stored = json.loads(raw)["outcome"]
        self.assertEqual(set(stored), {
            "schema_version", "grounder_status", "source_status", "semantic_status",
            "builder_status", "submission_status", "ei_status", "counts", "diagnostic_counts",
            "coverage", "provenance", "submission", "submission_sha256", "source_batch_count",
        })
        self.assertEqual(stored["counts"], {
            "source_body_count": 1, "claim_count": 1, "hypothesis_count": 0,
            "field_binding_count": 1, "coverage_count": 1,
        })
        assessment = assess_event_intelligence_submission(result.build_result.submission)
        self.assertEqual(
            stored["submission"]["assessment"]["status"], assessment.status.value
        )
        self.assertEqual(
            stored["submission"]["assessment"]["issues"],
            [{"code": issue.code.value, "subject_id": issue.subject_id} for issue in assessment.issues],
        )
        canonical_submission = json.dumps(
            stored["submission"], ensure_ascii=False, allow_nan=False,
            separators=(",", ":"), sort_keys=True,
        ).encode("utf-8")
        self.assertEqual(stored["submission_sha256"], hashlib.sha256(canonical_submission).hexdigest())
        self.assertEqual(public["ei_assessment_status"], assessment.status.value)
        self.assertEqual(public["submission_sha256"], stored["submission_sha256"])
        public_wire = json.dumps(run["events"], ensure_ascii=False, sort_keys=True)
        for private_value in (
            "https://private.example/source/private-path", "PRIVATE_SOURCE_TITLE",
            "PRIVATE_SUBMISSION_STATEMENT", "PRIVATE_SUBMISSION_UNCERTAINTY",
        ):
            self.assertNotIn(private_value, public_wire)
        self.assertIsNone(self.store._conn().execute(
            "SELECT 1 FROM direct_cases WHERE run_id=? UNION ALL "
            "SELECT 1 FROM batch_archives WHERE run_id=? LIMIT 1", (run_id, run_id)
        ).fetchone())

    def test_grounder_submission_rejects_wrong_batch_binding_type_and_input(self):
        from convexity_hunter.core_application import SourceSubmissionBatch

        for label in ("wrong raw input object", "wrong sole submission", "wrong batch type", "multiple submissions"):
            with self.subTest(label=label):
                run_id = self.create_run("event", "synthetic fixture event")
                stage_id = self.store.start_stage(run_id, "grounder")
                result = make_grounder_submission_result(run_id)
                build = result.build_result
                if label == "wrong raw input object":
                    invalid_build = replace(
                        build, source_batch=replace(build.source_batch, raw_input=object())
                    )
                    message = "exact Host raw input"
                elif label == "wrong sole submission":
                    other = replace(build.submission, submission_id="other-submission")
                    invalid_build = replace(
                        build, source_batch=SourceSubmissionBatch(build.raw_input, (other,))
                    )
                    message = "exact built submission"
                elif label == "wrong batch type":
                    invalid_build = replace(build, source_batch=object())
                    message = "exact SourceSubmissionBatch"
                else:
                    second = replace(build.submission, submission_id="second-submission")
                    invalid_build = replace(
                        build,
                        source_batch=SourceSubmissionBatch(
                            build.raw_input, (build.submission, second)
                        ),
                    )
                    message = "exactly one submission"
                invalid = replace(result, build_result=invalid_build)
                with self.assertRaisesRegex((TypeError, ValueError), message):
                    self.store.save_grounder_submission_stage_result(run_id, stage_id, invalid)
                self.assertEqual([event["event"] for event in self.store.get_run(run_id)["events"]], ["stage_started"])

        run_id = self.create_run("event", "different Host input")
        stage_id = self.store.start_stage(run_id, "grounder")
        with self.assertRaisesRegex(ValueError, "does not match the immutable Host run input"):
            self.store.save_grounder_submission_stage_result(
                run_id, stage_id, make_grounder_submission_result(run_id)
            )
        self.assertEqual([event["event"] for event in self.store.get_run(run_id)["events"]], ["stage_started"])

        run_id = self.create_run("world", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        with self.assertRaisesRegex(ValueError, "restricted to Event runs"):
            self.store.save_grounder_submission_stage_result(
                run_id, stage_id, make_grounder_submission_result(run_id)
            )

        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        with self.assertRaisesRegex(TypeError, "exact v0.7 evidence-catalog runtime result"):
            self.store.save_grounder_submission_stage_result(run_id, stage_id, object())

    def test_grounder_submission_reuses_receipt_audit_hash_and_finish_reason_guards(self):
        from types import MappingProxyType

        invalid_cases = ("receipt", "audit_hash", "finish_reason")
        for invalid_case in invalid_cases:
            with self.subTest(invalid_case=invalid_case):
                run_id = self.create_run("event", "synthetic fixture event")
                stage_id = self.store.start_stage(run_id, "grounder")
                result = make_grounder_submission_result(run_id)
                if invalid_case == "receipt":
                    receipt = dict(result.build_result.semantic_validation.receipt)
                    receipt["validator_version"] = "fixture-validator-v0.1"
                    semantic = replace(
                        result.build_result.semantic_validation,
                        receipt=MappingProxyType(receipt),
                    )
                    result = replace(
                        result,
                        build_result=replace(result.build_result, semantic_validation=semantic),
                    )
                    message = "receipt version or identity disagrees"
                elif invalid_case == "audit_hash":
                    result = replace(
                        result, audit=replace(result.audit, catalog_sha256="f" * 64)
                    )
                    message = "catalog digest does not match its bytes"
                else:
                    result = replace(
                        result,
                        discovery_call=replace(result.discovery_call, finish_reason="length"),
                    )
                    message = "model-call metadata is malformed"
                with self.assertRaisesRegex(ValueError, message):
                    self.store.save_grounder_submission_stage_result(run_id, stage_id, result)
                self.assertEqual(
                    [event["event"] for event in self.store.get_run(run_id)["events"]],
                    ["stage_started"],
                )

    def test_grounder_submission_waits_for_other_stages_and_cannot_use_generic_finish(self):
        from convexity_hunter.host_store import _grounder_stage_outcome

        run_id = self.create_run("event", "synthetic fixture event")
        grounder_id = self.store.start_stage(run_id, "grounder")
        executor_id = self.store.start_stage(run_id, "executor")
        result = make_grounder_submission_result(run_id)
        with self.assertRaisesRegex(ValueError, "all other Host stages must finish"):
            self.store.save_grounder_submission_stage_result(run_id, grounder_id, result)
        outcome = _grounder_stage_outcome(
            result, run_id, "synthetic fixture event", require_submission=True
        )
        with self.assertRaisesRegex(ValueError, "requires save_grounder_stage_result"):
            self.store.finish_stage(run_id, grounder_id, "COMPLETED", outcome, ())
        with self.assertRaisesRegex(ValueError, "requires save_grounder_stage_result"):
            self.store.finish_stage(run_id, executor_id, "COMPLETED", outcome, ())
        self.assertEqual(len(self.store.get_run(run_id)["events"]), 2)

        self.store.finish_stage(run_id, executor_id, "COMPLETED", "COMPLETED", ())
        self.store.save_grounder_submission_stage_result(run_id, grounder_id, result)
        self.assertEqual(self.store.get_run(run_id)["status"], "RUNNING")
        self.assertEqual(self.store.get_run(run_id)["events"][-1]["outcome"]["source_batch_count"], 1)

    def test_grounder_submission_history_survives_restart_without_replay(self):
        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        self.store.save_grounder_submission_stage_result(
            run_id, stage_id, make_grounder_submission_result(run_id)
        )
        self.store.close()

        recovered = HostStore(self.db_path)
        self.addCleanup(recovered.close)
        run = recovered.get_run(run_id)
        self.assertEqual(run["status"], "INTERRUPTED")
        self.assertEqual(run["diagnostics"], ["PROCESS_RESTART"])
        self.assertEqual(run["events"][-1]["event"], "stage_finished")
        self.assertEqual(run["events"][-1]["stage_id"], stage_id)
        self.assertEqual(run["events"][-1]["outcome"]["schema_version"], "host-grounder-submission-stage-outcome-v0.1")
        self.assertNotIn("submission", run["events"][-1]["outcome"])
        self.assertEqual(recovered._conn().execute(
            "SELECT COUNT(*) FROM events WHERE run_id=? AND event_type='stage_started'", (run_id,)
        ).fetchone()[0], 1)
        self.assertEqual(recovered._conn().execute(
            "SELECT COUNT(*) FROM events WHERE run_id=? AND event_type='stage_finished'", (run_id,)
        ).fetchone()[0], 1)
        self.assertIsNotNone(recovered._conn().execute(
            "SELECT payload_json FROM events WHERE run_id=? AND event_type='stage_finished'", (run_id,)
        ).fetchone())
        self.assertIsNone(recovered._conn().execute(
            "SELECT 1 FROM batch_archives WHERE run_id=?", (run_id,)
        ).fetchone())

    def test_grounder_submission_read_rejects_tampered_codec_assessment_and_digest(self):
        for tamper in ("assessment", "digest", "closed_field"):
            with self.subTest(tamper=tamper):
                run_id = self.create_run("event", "synthetic fixture event")
                stage_id = self.store.start_stage(run_id, "grounder")
                self.store.save_grounder_submission_stage_result(
                    run_id, stage_id, make_grounder_submission_result(run_id)
                )
                finish = self.store._conn().execute(
                    "SELECT event_seq,payload_json FROM events WHERE run_id=? AND event_type='stage_finished'",
                    (run_id,),
                ).fetchone()
                payload = json.loads(finish["payload_json"])
                if tamper == "assessment":
                    payload["outcome"]["submission"]["assessment"]["assessment_version"] = "forged-v0.1"
                elif tamper == "digest":
                    payload["outcome"]["submission_sha256"] = "f" * 64
                else:
                    payload["outcome"]["unknown"] = "not closed"
                payload_json = json.dumps(
                    payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
                )
                with self.store._transaction() as connection:
                    if connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='events_no_update'"
                    ).fetchone() is not None:
                        connection.execute("DROP TRIGGER events_no_update")
                    connection.execute(
                        "UPDATE events SET payload_json=? WHERE event_seq=?",
                        (payload_json, finish["event_seq"]),
                    )
                with self.assertRaisesRegex(StoreCorruptionError, "stage result payload violates"):
                    self.store.get_run(run_id)

    def test_grounder_submission_read_rejects_tampered_original_input_binding(self):
        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        self.store.save_grounder_submission_stage_result(
            run_id, stage_id, make_grounder_submission_result(run_id)
        )
        finish = self.store._conn().execute(
            "SELECT event_seq,payload_json FROM events WHERE run_id=? AND event_type='stage_finished'",
            (run_id,),
        ).fetchone()
        payload = json.loads(finish["payload_json"])
        payload["outcome"]["provenance"]["host_raw_input_sha256"] = "f" * 64
        payload_json = json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
        )
        with self.store._transaction() as connection:
            connection.execute("DROP TRIGGER events_no_update")
            connection.execute(
                "UPDATE events SET payload_json=? WHERE event_seq=?",
                (payload_json, finish["event_seq"]),
            )
        with self.assertRaisesRegex(StoreCorruptionError, "not bound to the immutable Host raw input"):
            self.store.get_run(run_id)

    def test_grounder_receipt_validator_version_must_match_audit_before_write(self):
        from types import MappingProxyType

        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        result = make_grounder_no_submission_result(run_id)
        receipt = dict(result.build_result.semantic_validation.receipt)
        receipt["validator_version"] = "fixture-validator-v0.1"
        semantic = replace(
            result.build_result.semantic_validation,
            receipt=MappingProxyType(receipt),
        )
        build = replace(result.build_result, semantic_validation=semantic)
        result = replace(result, build_result=build)

        with self.assertRaisesRegex(ValueError, "receipt version or identity disagrees"):
            self.store.save_grounder_stage_result(run_id, stage_id, result)
        run = self.store.get_run(run_id)
        self.assertEqual(run["status"], "RUNNING")
        self.assertEqual([event["event"] for event in run["events"]], ["stage_started"])

    def test_grounder_call_summary_rejects_truncated_completion_on_write_and_read(self):
        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        result = make_grounder_no_submission_result(run_id)
        truncated = replace(
            result,
            discovery_call=replace(result.discovery_call, finish_reason="length"),
        )
        with self.assertRaisesRegex(ValueError, "model-call metadata is malformed"):
            self.store.save_grounder_stage_result(run_id, stage_id, truncated)
        self.assertEqual([event["event"] for event in self.store.get_run(run_id)["events"]], ["stage_started"])

        self.store.save_grounder_stage_result(run_id, stage_id, result)
        finish = self.store._conn().execute(
            "SELECT event_seq,payload_json FROM events WHERE run_id=? AND event_type='stage_finished'",
            (run_id,),
        ).fetchone()
        payload = json.loads(finish["payload_json"])
        payload["outcome"]["provenance"]["model_calls"][0]["finish_reason"] = "length"
        payload_json = json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
        )
        with self.store._transaction() as connection:
            connection.execute("DROP TRIGGER events_no_update")
            connection.execute(
                "UPDATE events SET payload_json=? WHERE event_seq=?",
                (payload_json, finish["event_seq"]),
            )
        with self.assertRaisesRegex(StoreCorruptionError, "stage result payload violates"):
            self.store.get_run(run_id)

    def test_grounder_generic_finish_stage_only_allows_restart_interruption(self):
        from convexity_hunter.host_store import _grounder_stage_outcome

        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        result = make_grounder_no_submission_result(run_id)
        outcome = _grounder_stage_outcome(result, run_id, "synthetic fixture event")
        with self.assertRaisesRegex(ValueError, "requires save_grounder_stage_result"):
            self.store.finish_stage(
                run_id, stage_id, "COMPLETED", outcome, ("GROUNDING_NO_SUBMISSION",)
            )
        with self.assertRaisesRegex(ValueError, "requires save_grounder_stage_result"):
            self.store.finish_stage(run_id, stage_id, "COMPLETED", "COMPLETED", ())
        self.assertEqual([event["event"] for event in self.store.get_run(run_id)["events"]], ["stage_started"])

        self.store.finish_stage(
            run_id, stage_id, "INTERRUPTED", "INTERRUPTED", ("PROCESS_RESTART",)
        )
        with self.assertRaisesRegex(ValueError, "requires the matching restart terminal"):
            self.store.finish_run(run_id, "COMPLETED", ())
        self.assertEqual(self.store.get_run(run_id)["status"], "RUNNING")
        self.store.finish_run(run_id, "INTERRUPTED", ("PROCESS_RESTART",))
        run = self.store.get_run(run_id)
        self.assertEqual(run["status"], "INTERRUPTED")
        self.assertEqual(run["events"][-1]["event"], "stage_finished")
        self.assertEqual(run["events"][-1]["status"], "INTERRUPTED")
        self.assertEqual(run["events"][-1]["outcome"], "INTERRUPTED")

    def test_generic_finish_stage_rejects_grounder_dto_for_executor_without_event(self):
        from convexity_hunter.host_store import _grounder_stage_outcome

        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "executor")
        outcome = _grounder_stage_outcome(
            make_grounder_no_submission_result(run_id), run_id, "synthetic fixture event"
        )
        with self.assertRaisesRegex(ValueError, "Grounder typed outcome requires"):
            self.store.finish_stage(
                run_id, stage_id, "COMPLETED", outcome, ("GROUNDING_NO_SUBMISSION",)
            )
        run = self.store.get_run(run_id)
        self.assertEqual(run["status"], "RUNNING")
        self.assertEqual([event["event"] for event in run["events"]], ["stage_started"])

    def test_grounder_failed_and_blocked_generic_terminals_are_closed_and_noncomplete(self):
        for status, diagnostic in (
            ("FAILED", "SEMANTIC_CALL_FAILED"),
            ("BLOCKED", "MODEL_REQUEST_TOO_LARGE"),
            ("FAILED", "NO_SEARCH_RESULTS"),
            ("FAILED", "EXTRACTION_FAILURE"),
            ("FAILED", "SOURCE_CREDENTIAL_UNAVAILABLE"),
            ("FAILED", "SOURCE_TRANSPORT_FAILURE"),
            ("BLOCKED", "OPERATIONAL_LIMIT"),
        ):
            with self.subTest(status=status):
                run_id = self.create_run("event", "grounder terminal case")
                stage_id = self.store.start_stage(run_id, "grounder")
                with self.assertRaisesRegex(ValueError, "Grounder generic finish permits"):
                    self.store.finish_stage(
                        run_id, stage_id, status, "FAILED" if status == "BLOCKED" else "BLOCKED",
                        (diagnostic,),
                    )
                with self.assertRaisesRegex(ValueError, "Grounder generic finish permits"):
                    self.store.finish_stage(
                        run_id, stage_id, status, status, ("UNKNOWN_GROUNDER_ERROR",)
                    )
                self.assertEqual(
                    [event["event"] for event in self.store.get_run(run_id)["events"]],
                    ["stage_started"],
                )

                self.store.finish_stage(run_id, stage_id, status, status, (diagnostic,))
                run = self.store.get_run(run_id)
                self.assertEqual(run["status"], "RUNNING")
                self.assertEqual(run["events"][-1]["status"], status)
                self.assertEqual(run["events"][-1]["outcome"], status)
                self.assertEqual(run["events"][-1]["diagnostics"], [diagnostic])
                with self.assertRaisesRegex(ValueError, "cannot terminate as a complete run"):
                    self.store.finish_run(run_id, "COMPLETED", ())
                self.assertEqual(self.store.get_run(run_id)["status"], "RUNNING")
                self.store.finish_run(run_id, status, (diagnostic,))
                terminal = self.store.get_run(run_id)
                self.assertEqual(terminal["status"], status)
                self.assertEqual(terminal["events"][-1]["outcome"], status)

    def test_recovered_grounder_stage_is_interrupted_without_semantic_result(self):
        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        self.store.close()

        recovered = HostStore(self.db_path)
        self.addCleanup(recovered.close)
        run = recovered.get_run(run_id)
        self.assertEqual(run["status"], "INTERRUPTED")
        self.assertEqual(len(run["events"]), 2)
        stage_event = run["events"][-1]
        self.assertEqual(stage_event["event"], "stage_finished")
        self.assertEqual(stage_event["stage_id"], stage_id)
        self.assertEqual(stage_event["status"], "INTERRUPTED")
        self.assertEqual(stage_event["outcome"], "INTERRUPTED")
        self.assertEqual(stage_event["diagnostics"], ["PROCESS_RESTART"])
        self.assertEqual(run["diagnostics"], ["PROCESS_RESTART"])

    def test_grounder_rejects_same_run_id_with_different_host_query(self):
        run_id = self.create_run("event", "a different Host query")
        stage_id = self.store.start_stage(run_id, "grounder")
        result = make_grounder_no_submission_result(run_id)
        with self.assertRaisesRegex(ValueError, "does not match the immutable Host run input"):
            self.store.save_grounder_stage_result(run_id, stage_id, result)
        run = self.store.get_run(run_id)
        self.assertEqual(run["status"], "RUNNING")
        self.assertEqual([event["event"] for event in run["events"]], ["stage_started"])

    def test_grounder_accepts_exact_string_raw_input_shape(self):
        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        result = make_grounder_no_submission_result(run_id)
        context = replace(result.build_result.context, raw_input="synthetic fixture event")
        build = replace(result.build_result, context=context, raw_input=context.raw_input)
        result = replace(result, build_result=build)

        self.store.save_grounder_stage_result(run_id, stage_id, result)
        self.assertEqual(self.store.get_run(run_id)["status"], "BLOCKED")

    def test_grounder_read_rejects_tampered_host_raw_input_digest(self):
        run_id = self.create_run("event", "synthetic fixture event")
        stage_id = self.store.start_stage(run_id, "grounder")
        self.store.save_grounder_stage_result(
            run_id, stage_id, make_grounder_no_submission_result(run_id)
        )
        finish = self.store._conn().execute(
            "SELECT event_seq,payload_json FROM events WHERE run_id=? AND event_type='stage_finished'",
            (run_id,),
        ).fetchone()
        payload = json.loads(finish["payload_json"])
        payload["outcome"]["provenance"]["host_raw_input_sha256"] = "f" * 64
        payload_json = json.dumps(
            payload, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True
        )
        with self.store._transaction() as connection:
            connection.execute("DROP TRIGGER events_no_update")
            connection.execute(
                "UPDATE events SET payload_json=? WHERE event_seq=?",
                (payload_json, finish["event_seq"]),
            )
        with self.assertRaisesRegex(StoreCorruptionError, "not bound to the immutable Host raw input"):
            self.store.get_run(run_id)

    def test_unfinished_stages_must_pair_and_terminal_runs_are_immutable(self):
        run_id = self.create_run()
        stage_id = self.store.start_stage(run_id, "executor")
        with self.assertRaises(ValueError):
            self.store.finish_run(run_id, "BLOCKED", ())
        self.store.finish_stage(run_id, stage_id, "BLOCKED", "BLOCKED", ())
        with self.assertRaises(ValueError):
            self.store.finish_stage(run_id, stage_id, "BLOCKED", "BLOCKED", ())
        self.store.finish_run(run_id, "BLOCKED", ())
        with self.assertRaises(ValueError):
            self.store.start_stage(run_id, "executor")
        with self.assertRaises(ValueError):
            self.store.finish_run(run_id, "BLOCKED", ())

    def test_running_run_recovers_without_replaying_work(self):
        run_id = self.create_run("direct", '{"exact": "raw input"}')
        stage_id = self.store.start_stage(run_id, "executor")
        with self.assertRaises(HostStoreError) as raised:
            HostStore(self.db_path)
        self.assertEqual(
            str(raised.exception),
            "could not acquire exclusive HostStore database lock",
        )
        self.assertNotIn(str(self.db_path), str(raised.exception))

        self.store.close()

        # A genuine close/reopen releases the inode lock and recovers exactly
        # once instead of allowing a concurrent constructor to interrupt it.
        recovered = HostStore(self.db_path)
        self.addCleanup(recovered.close)
        run = recovered.get_run(run_id)
        self.assertEqual(run["status"], "INTERRUPTED")
        self.assertEqual(run["events"][-1]["status"], "INTERRUPTED")
        self.assertEqual(run["events"][-1]["stage_id"], stage_id)
        self.assertEqual(run["diagnostics"], ["PROCESS_RESTART"])

    def test_append_only_triggers_reject_updates_and_deletes(self):
        run_id = self.create_run()
        connection = sqlite3.connect(str(self.db_path))
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE runs SET created_at='changed' WHERE run_id=?", (run_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM events WHERE run_id=?", (run_id,))
        finally:
            connection.close()

    def test_closed_metadata_bounds_and_outcome_reject_unapproved_payloads(self):
        metadata = _run_start_metadata()
        metadata["configuration_snapshot"]["models"].append({"name": "unapproved"})
        with self.assertRaises(ValueError):
            self.store.create_run("world", "input", BOUNDS, STANDARD_RESEARCH_PROFILE.snapshot(), metadata)
        with self.assertRaises((TypeError, ValueError)):
            CoreOperationalBounds(0, 0, 0, -1, 1.0)
        self.assertEqual(self.store.list_runs(), [])

        run_id = self.create_run()
        stage_id = self.store.start_stage(run_id, "executor")
        with self.assertRaises(ValueError):
            self.store.finish_stage(
                run_id,
                stage_id,
                "BLOCKED",
                {"response_body": "unredacted provider payload"},
                (),
            )
        with self.assertRaises(ValueError):
            self.store.finish_stage(run_id, stage_id, "BLOCKED", blocked_outcome(), ("not a code",))
        self.assertEqual(self.store.get_run(run_id)["status"], "RUNNING")

    def test_event_configuration_snapshot_is_closed_typed_and_never_resolves_credentials(self):
        from convexity_hunter.host_sources import TavilyCredentialRef

        metadata = _run_start_metadata()
        metadata["configuration_snapshot"] = _event_configuration_snapshot()
        with patch.object(
            TavilyCredentialRef, "resolve", side_effect=AssertionError("must not resolve credentials")
        ):
            run_id = self.store.create_run(
                "event", "synthetic fixture event", BOUNDS,
                STANDARD_RESEARCH_PROFILE.snapshot(), metadata,
            )
        self.assertEqual(
            self.store.get_run(run_id)["metadata"]["configuration_snapshot"],
            _event_configuration_snapshot(),
        )
        self.assertEqual(SCHEMA_VERSION, 3)
        legacy_id = self.create_run("world", "legacy empty shell snapshot")
        self.assertEqual(
            self.store.get_run(legacy_id)["metadata"]["configuration_snapshot"],
            {"models": [], "sources": [], "skills": []},
        )

    def test_event_configuration_snapshot_rejects_unknown_and_unapproved_values(self):
        invalid_snapshots = []

        snapshot = _event_configuration_snapshot()
        snapshot["models"][0]["credential_ref"] = {"env_name": "PRIVATE_ENV_NAME"}
        invalid_snapshots.append(("model credential field", snapshot))

        snapshot = _event_configuration_snapshot()
        snapshot["models"][0]["base_endpoint"] = "http://127.0.0.1:9000/v1"
        invalid_snapshots.append(("local model endpoint", snapshot))

        snapshot = _event_configuration_snapshot()
        snapshot["models"][0]["role"], snapshot["models"][1]["role"] = "semantic", "discovery"
        invalid_snapshots.append(("model role order", snapshot))

        snapshot = _event_configuration_snapshot()
        snapshot["sources"][0]["provider"] = "other"
        invalid_snapshots.append(("source provider", snapshot))

        snapshot = _event_configuration_snapshot()
        snapshot["sources"][0]["credential_path"] = "/private/credential"
        invalid_snapshots.append(("source credential field", snapshot))

        snapshot = _event_configuration_snapshot()
        snapshot["sources"][0]["grounder_limits"]["unknown_limit"] = 1
        invalid_snapshots.append(("unknown Grounder limit", snapshot))

        snapshot = _event_configuration_snapshot()
        snapshot["skills"].append({"name": "unapproved-skill"})
        invalid_snapshots.append(("skill entry", snapshot))

        for label, snapshot in invalid_snapshots:
            with self.subTest(label=label):
                metadata = _run_start_metadata()
                metadata["configuration_snapshot"] = snapshot
                with self.assertRaises((TypeError, ValueError)):
                    self.store.create_run(
                        "event", "input", BOUNDS,
                        STANDARD_RESEARCH_PROFILE.snapshot(), metadata,
                    )
        self.assertEqual(self.store.list_runs(), [])

    def test_nonprivate_existing_parent_is_rejected_without_chmod(self):
        shared = self.root / "existing-shared"
        shared.mkdir(mode=0o755)
        os.chmod(str(shared), 0o755)
        with self.assertRaises(ValueError):
            HostStore(shared / "journal.sqlite3")
        self.assertEqual(stat.S_IMODE(shared.stat().st_mode), 0o755)

    def test_v1_migration_preserves_old_snapshot_and_stage_history(self):
        path = self.root / "legacy.sqlite3"
        before = make_v1_database(path)
        migrated = HostStore(path)
        self.addCleanup(migrated.close)
        self.assertEqual([tuple(row) for row in migrated._conn().execute("SELECT * FROM events ORDER BY event_seq")], before)
        self.assertEqual(migrated._conn().execute("PRAGMA user_version").fetchone()[0], 3)
        run = migrated.get_run("legacy-run")
        self.assertEqual(run["input"], "legacy exact input")
        self.assertEqual(run["status"], "BLOCKED")
        self.assertEqual(run["metadata"]["execution_snapshot"], {})
        self.assertEqual(run["events"][-1]["outcome"], blocked_outcome())
        self.assertEqual(migrated.list_direct_cases("legacy-run"), [])

    def test_direct_archive_identity_profile_provenance_and_detached_reads(self):
        run_id = self.create_run("direct")
        result = make_direct_result()
        case_id = self.store.save_direct_result(run_id, result)
        self.assertEqual(case_id, result.kernel_request.case_id)
        archive = self.store.get_direct_case(run_id, case_id)
        self.assertEqual(archive["schema_version"], "host-direct-case-v0.1")
        self.assertEqual(archive["profile_snapshot"], STANDARD_RESEARCH_PROFILE.snapshot())
        self.assertEqual(archive["disclosures"], {
            "maturity_authority": "neutral_structural_research",
            "hypothesis_maturity_alignment": "not_established",
            "quote_reference_temporal_alignment": "not_established",
            "cross_structure_quote_synchronicity": "not_established",
        })
        self.assertEqual(archive["report_cache"]["text"], result.full_report)
        self.assertEqual(archive["report_cache"]["core_sha256"], archive["core_sha256"])
        restored = self.store.load_core_result(run_id, case_id)
        self.assertEqual(restored, result.kernel_result)
        self.assertEqual(restored.request.provenance.source_reference, result.kernel_request.provenance.source_reference)
        self.assertEqual(restored.request.risk_policy.portfolio_value, STANDARD_RESEARCH_PROFILE.portfolio_value)
        self.assertIsNone(restored.request.cost_ledger)
        self.assertIsNone(restored.request.sensitivity)
        summary = self.store.list_direct_cases(run_id)[0]
        self.assertEqual(set(summary), {"case_id", "classification", "reasons"})
        self.assertEqual(summary["classification"], "DATA_INSUFFICIENT_CORE")
        archive["core_snapshot"]["version"] = "mutated"
        summary["reasons"].clear()
        self.assertEqual(self.store.load_core_result(run_id, case_id), restored)
        self.assertTrue(self.store.list_direct_cases(run_id)[0]["reasons"])
        self.assertIsNone(self.store.get_direct_case(run_id, "missing"))
        self.assertIsNone(self.store.load_core_result(run_id, "missing"))
        with self.assertRaises(ValueError):
            self.store.save_direct_result(run_id, result)
        for sql in ("UPDATE direct_cases SET archive_json='{}'", "DELETE FROM direct_cases"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.store._conn().execute(sql)

    def test_direct_pointer_requires_committed_case_and_core_done_is_completed(self):
        run_id = self.create_run("direct")
        result = make_direct_result(cached_report=False)
        stage_id = self.store.start_stage(run_id, "direct")
        outcome = {"schema_version": "host-direct-outcome-v0.1",
                   "case_id": result.kernel_request.case_id, "classification": "DATA_INSUFFICIENT_CORE"}
        with self.assertRaises(ValueError):
            self.store.finish_stage(run_id, stage_id, "COMPLETED", outcome, ())
        case_id = self.store.save_direct_result(run_id, result)
        self.assertIsNone(self.store.get_direct_case(run_id, case_id)["report_cache"])
        self.store.finish_stage(run_id, stage_id, "COMPLETED", outcome, ())
        with self.assertRaises(ValueError):
            self.store.finish_run(run_id, "BLOCKED", ())
        self.store.finish_run(run_id, "COMPLETED", ())
        self.assertEqual(self.store.get_run(run_id)["status"], "COMPLETED")
        with self.assertRaises(ValueError):
            self.store.save_direct_result(run_id, result)
        self.store.close()
        reopened = HostStore(self.db_path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get_run(run_id)["status"], "COMPLETED")
        self.assertEqual(reopened.load_core_result(run_id, case_id), result.kernel_result)

    def test_direct_rejects_report_profile_disclosure_and_identity_mismatch(self):
        run_id = self.create_run("direct")
        result = make_direct_result()
        with self.assertRaises(ValueError):
            self.store.save_direct_result(self.create_run("world"), result)
        with self.assertRaises(ValueError):
            self.store.save_direct_result(run_id, replace(result, full_report="invented report"))
        risk = replace(result.kernel_request.risk_policy, portfolio_value=decimal.Decimal("200000"))
        request = replace(result.kernel_request, risk_policy=risk)
        different_profile = replace(result, kernel_request=request,
                                    kernel_result=core.evaluate_core_research(request), full_report="")
        with self.assertRaises(ValueError):
            self.store.save_direct_result(run_id, different_profile)
        from convexity_hunter.option_chain_discovery import OptionMaturityAuthority
        with self.assertRaises(ValueError):
            self.store.save_direct_result(run_id, replace(result, full_report="", maturity_authority=OptionMaturityAuthority.HYPOTHESIS_ALIGNED))
        with self.assertRaises(TypeError):
            self.store.save_direct_result(run_id, replace(result, kernel_request=None, kernel_result=None, full_report=""))
        invalid_identity = replace(result)
        object.__setattr__(invalid_identity, "kernel_request", replace(result.kernel_request, description="other request"))
        with self.assertRaises(ValueError):
            self.store.save_direct_result(run_id, invalid_identity)
        self.assertEqual(self.store.list_direct_cases(run_id), [])

    def test_direct_load_rejects_digests_and_unknown_envelope_fields(self):
        run_id = self.create_run("direct")
        case_id = self.store.save_direct_result(run_id, make_direct_result())
        connection = self.store._conn()
        original = connection.execute("SELECT archive_json FROM direct_cases").fetchone()[0]
        connection.execute("DROP TRIGGER direct_cases_no_update")
        for mutation in ("archive_digest", "core_digest", "unknown_field", "classification"):
            with self.subTest(mutation=mutation):
                archive = json.loads(original)
                if mutation == "core_digest":
                    archive["core_sha256"] = "0" * 64
                elif mutation == "unknown_field":
                    archive["extra"] = "not allowed"
                elif mutation == "classification":
                    archive["classification"] = "RESEARCHABLE_CONVEXITY"
                wire = json.dumps(archive, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
                digest = "0" * 64 if mutation == "archive_digest" else hashlib.sha256(wire.encode()).hexdigest()
                connection.execute("UPDATE direct_cases SET archive_json=?,archive_sha256=?", (wire, digest))
                with self.assertRaises(StoreCorruptionError):
                    self.store.load_core_result(run_id, case_id)

    def test_source_uri_credentials_rejected_before_write_without_disclosure(self):
        run_id = self.create_run("direct")
        uris = (
            "https://user:PASSWORD_SENTINEL@example.test/quotes?symbol=XYZ",
            "https://example.test/quotes?%41pI%5FkEy=APIKEY_SENTINEL&symbol=XYZ",
            "https://example.test/quotes#access%5Ftoken=APIKEY_SENTINEL",
        )
        result = make_direct_result(cached_report=False)
        leg = result.kernel_request.structure.legs[0]
        bad_source = replace(leg.provenance.source_reference, source_uri=uris[1])
        bad_leg = replace(leg, provenance=replace(leg.provenance, source_reference=bad_source))
        structure = replace(result.core_structure, legs=(bad_leg,))
        request = replace(result.kernel_request, structure=structure)
        nested_only = replace(result, core_structure=structure, kernel_request=request,
                              kernel_result=core.evaluate_core_research(request))
        captured = io.StringIO()
        handler = logging.StreamHandler(captured)
        logging.getLogger().addHandler(handler)
        errors = []
        try:
            with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                for index, candidate in enumerate(
                    [make_direct_result(cached_report=False, source_uri=uri) for uri in uris] + [nested_only]
                ):
                    with self.subTest(index=index), self.assertRaises(ValueError) as raised:
                        self.store.save_direct_result(run_id, candidate)
                    errors.extend(traceback.format_exception(type(raised.exception), raised.exception, raised.exception.__traceback__))
        finally:
            logging.getLogger().removeHandler(handler)
        self.assertEqual(self.store.list_direct_cases(run_id), [])
        for sentinel in ("PASSWORD_SENTINEL", "APIKEY_SENTINEL"):
            self.assertFalse(sentinel.encode() in self.db_path.read_bytes(), "rejected URI material reached the database")
            self.assertFalse(sentinel in captured.getvalue() + "".join(errors), "URI material appeared in output or errors")

    def test_source_uri_public_queries_preserved_exactly(self):
        uri = "https://example.test/quotes?symbol=XYZ&note=api_key%3Dpublic-doc&sort=asc#quote-section"
        run_id = self.create_run("direct")
        result = make_direct_result(source_uri=uri)
        case_id = self.store.save_direct_result(run_id, result)
        restored = self.store.load_core_result(run_id, case_id)
        self.assertEqual(restored.request.provenance.source_reference.source_uri, uri)
        self.assertEqual(restored.request.structure.legs[0].provenance.source_reference.source_uri, uri)
        self.assertEqual(restored, result.kernel_result)

    def test_source_uri_load_rejects_nested_credentials_even_with_valid_digests(self):
        run_id = self.create_run("direct")
        case_id = self.store.save_direct_result(run_id, make_direct_result(cached_report=False))
        connection = self.store._conn()
        original = connection.execute("SELECT archive_json FROM direct_cases").fetchone()[0]
        connection.execute("DROP TRIGGER direct_cases_no_update")
        captured = io.StringIO()
        errors = []
        handler = logging.StreamHandler(captured)
        logging.getLogger().addHandler(handler)
        try:
            for index, uri in enumerate((
                "https://user:PASSWORD_SENTINEL@example.test/quote",
                "https://example.test/quote?api%5Fkey=APIKEY_SENTINEL",
            )):
                archive = json.loads(original)
                source = archive["core_snapshot"]["request"]["structure"]["legs"]["$tuple"][0]["provenance"]["source_reference"]
                self.assertEqual(source["$type"], "market_data.SourceReference")
                source["source_uri"] = uri
                core_wire = json.dumps(archive["core_snapshot"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                archive["core_sha256"] = hashlib.sha256(core_wire.encode()).hexdigest()
                wire = json.dumps(archive, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                connection.execute("UPDATE direct_cases SET archive_json=?,archive_sha256=?", (wire, hashlib.sha256(wire.encode()).hexdigest()))
                with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
                    for reader in (self.store.get_direct_case, self.store.load_core_result):
                        with self.subTest(index=index), self.assertRaises(StoreCorruptionError) as raised:
                            reader(run_id, case_id)
                        self.assertIn("authentication material", str(raised.exception.__cause__))
                        errors.extend(traceback.format_exception(type(raised.exception), raised.exception, raised.exception.__traceback__))
        finally:
            logging.getLogger().removeHandler(handler)
            connection.execute("UPDATE direct_cases SET archive_json=?,archive_sha256=?", (original, hashlib.sha256(original.encode()).hexdigest()))
            connection.execute("CREATE TRIGGER direct_cases_no_update BEFORE UPDATE ON direct_cases BEGIN SELECT RAISE(ABORT,'append-only journal'); END")
        self.assertFalse(any(sentinel in captured.getvalue() + "".join(errors)
                             for sentinel in ("PASSWORD_SENTINEL", "APIKEY_SENTINEL")), "URI material appeared in output or errors")

    def test_direct_execution_metadata_is_closed_and_corrupt_v2_table_rejected(self):
        metadata = _run_start_metadata()
        metadata["execution_snapshot"] = {"direct_executor": {"status": "CONFIGURED", "version": "host-direct-input-v0.1"}}
        run_id = self.store.create_run("direct", "input", BOUNDS, STANDARD_RESEARCH_PROFILE.snapshot(), metadata)
        self.assertEqual(self.store.get_run(run_id)["metadata"]["execution_snapshot"], metadata["execution_snapshot"])
        metadata["execution_snapshot"]["direct_executor"]["private_path"] = "/not-accepted"
        with self.assertRaises(ValueError):
            self.store.create_run("direct", "input", BOUNDS, STANDARD_RESEARCH_PROFILE.snapshot(), metadata)
        self.store.close()
        connection = sqlite3.connect(str(self.db_path))
        connection.execute("ALTER TABLE direct_cases ADD COLUMN unexpected TEXT")
        connection.close()
        with self.assertRaises(StoreCorruptionError):
            HostStore(self.db_path)

    def test_world_event_executor_metadata_is_optional_and_composable(self):
        metadata = _run_start_metadata()
        metadata["execution_snapshot"] = {
            "direct_executor": {
                "status": "CONFIGURED",
                "version": "host-direct-input-v0.1",
            },
            "world_executor": {
                "status": "CONFIGURED",
                "version": "host-batch-executor-v0.1",
            },
            "event_executor": {
                "status": "CONFIGURED",
                "version": "host-batch-executor-v0.1",
            },
        }
        run_id = self.store.create_run(
            "world", "input", BOUNDS, STANDARD_RESEARCH_PROFILE.snapshot(), metadata
        )
        self.assertEqual(
            self.store.get_run(run_id)["metadata"]["execution_snapshot"],
            metadata["execution_snapshot"],
        )
        invalid = _run_start_metadata()
        invalid["execution_snapshot"] = {
            "world_executor": {"status": "CONFIGURED", "version": "host-batch-executor-v0.2"}
        }
        with self.assertRaises(ValueError):
            self.store.create_run(
                "world", "input", BOUNDS, STANDARD_RESEARCH_PROFILE.snapshot(), invalid
            )

    def test_v2_to_v3_migration_preserves_direct_archive(self):
        run_id = self.create_run("direct")
        result = make_direct_result()
        case_id = self.store.save_direct_result(run_id, result)
        expected = self.store.get_direct_case(run_id, case_id)
        self.store.close()

        connection = sqlite3.connect(str(self.db_path))
        connection.execute("DROP TABLE batch_archives")
        connection.execute("PRAGMA user_version=2")
        connection.commit()
        connection.close()

        migrated = HostStore(self.db_path)
        self.addCleanup(migrated.close)
        self.assertEqual(migrated._conn().execute("PRAGMA user_version").fetchone()[0], 3)
        self.assertEqual(migrated.get_direct_case(run_id, case_id), expected)
        self.assertEqual(migrated.load_core_result(run_id, case_id), result.kernel_result)

    def test_symlink_git_and_unsupported_or_corrupt_databases_are_rejected(self):
        link = self.root / "linked-parent"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            HostStore(link / "journal.sqlite3")
        with self.assertRaises(ValueError):
            HostStore(ROOT / ".host-store-test.sqlite3")

        symlink_db = self.root / "symlink-lock-db.sqlite3"
        lock_target = self.root / "lock-target"
        lock_target.write_bytes(b"not used as a lock")
        os.chmod(str(lock_target), 0o600)
        symlink_db.with_name(symlink_db.name + ".lock").symlink_to(lock_target)
        with self.assertRaises(HostStoreError) as raised:
            HostStore(symlink_db)
        self.assertNotIn(str(symlink_db), str(raised.exception))

        future_path = self.root / "future.sqlite3"
        connection = sqlite3.connect(str(future_path))
        connection.execute("PRAGMA user_version=4")
        connection.commit()
        connection.close()
        with self.assertRaises(UnsupportedSchemaVersionError):
            HostStore(future_path)

        corrupt_path = self.root / "corrupt.sqlite3"
        corrupt_path.write_bytes(b"not a SQLite database")
        with self.assertRaises(StoreCorruptionError):
            HostStore(corrupt_path)


if __name__ == "__main__":
    unittest.main()
