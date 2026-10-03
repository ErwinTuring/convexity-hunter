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
