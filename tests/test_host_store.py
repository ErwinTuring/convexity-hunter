"""Focused tests for the private schema-v1 Host SQLite journal."""

import os
import pathlib
import sqlite3
import stat
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter.core_application import CoreOperationalBounds
from convexity_hunter.host_profile import STANDARD_RESEARCH_PROFILE
from convexity_hunter.host_server import BLOCKED_REASON, HOST_SHELL_VERSION, _run_start_metadata
from convexity_hunter.host_store import (
    HostStore,
    HostStoreError,
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


def blocked_outcome():
    return {
        "executor_status": "NOT_CONFIGURED",
        "reason": BLOCKED_REASON,
        "host_shell_version": HOST_SHELL_VERSION,
    }


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
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 1)
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
        connection.execute("PRAGMA user_version=2")
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
