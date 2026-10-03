"""Private append-only SQLite journal for the minimal Host shell.

This store persists only the frozen M6 run snapshot and stage/run events. It
does not call providers, read configuration files, or serialize source/Core
objects.
"""

from __future__ import annotations

import contextlib
import datetime as _datetime
import fcntl
import hashlib
import json
import math
import os
import re
import sqlite3
import stat
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

from .core_application import CoreOperationalBounds
from .host_profile import STANDARD_RESEARCH_PROFILE, StandardResearchProfile


SCHEMA_VERSION = 1
_APPLICATION_ID = 0x43484A31  # ASCII "CHJ1"
_MODES = frozenset(("world", "event", "direct"))
_RUN_STATUSES = frozenset(
    ("QUEUED", "RUNNING", "COMPLETED", "PARTIAL", "BLOCKED", "FAILED", "INTERRUPTED")
)
_TERMINAL_STATUSES = frozenset(
    ("COMPLETED", "PARTIAL", "BLOCKED", "FAILED", "INTERRUPTED")
)
_BOUND_FIELDS = (
    "max_submissions",
    "max_hypotheses",
    "max_browser_rows",
    "max_cases",
    "quote_timeout_seconds",
)
_METADATA_FIELDS = frozenset(
    ("configuration_snapshot", "execution_snapshot", "contract_versions")
)
_CONFIGURATION_FIELDS = frozenset(("models", "sources", "skills"))
_CONTRACT_VERSION_FIELDS = frozenset(
    ("architecture", "host_shell", "standard_research_profile")
)
_SENSITIVE_KEYS = frozenset(
    (
        "access_token",
        "api_key",
        "api_token",
        "authorization",
        "authorization_header",
        "cookie",
        "credential_path",
        "password",
        "raw_config",
        "raw_configuration",
        "refresh_token",
        "secret",
        "token",
    )
)
_DIAGNOSTIC_RE = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z", re.ASCII)
_ID_RE = re.compile(r"[A-Za-z0-9._~-]{1,128}\Z", re.ASCII)
_SAFE_VERSION_RE = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z", re.ASCII)
_SCHEMA_OBJECTS = frozenset(
    (
        "runs",
        "events",
        "runs_no_update",
        "runs_no_delete",
        "events_no_update",
        "events_no_delete",
    )
)
_RUN_COLUMNS = ("run_seq", "run_id", "created_at")
_EVENT_COLUMNS = (
    "event_seq",
    "run_id",
    "event_type",
    "stage_id",
    "stage_name",
    "status",
    "payload_json",
    "occurred_at",
)


class HostStoreError(RuntimeError):
    """Base exception for a rejected or unavailable Host journal."""


class UnsupportedSchemaVersionError(HostStoreError):
    """The database schema is newer than this implementation supports."""


class StoreCorruptionError(HostStoreError):
    """The database is not a valid schema-v1 Host journal."""


def _canonical_value(value: Any, label: str, depth: int = 0) -> Any:
    if depth > 64:
        raise ValueError("{} exceeds the JSON nesting limit".format(label))
    value_type = type(value)
    if value is None or value_type in (bool, int):
        return value
    if value_type is float:
        if not math.isfinite(value):
            raise ValueError("{} contains a non-finite number".format(label))
        return value
    if value_type is str:
        try:
            value.encode("utf-8", "strict")
        except UnicodeError as error:
            raise ValueError("{} contains invalid Unicode".format(label)) from error
        return value
    if value_type in (list, tuple):
        return [_canonical_value(item, label, depth + 1) for item in value]
    if value_type is dict:
        result: Dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("{} object keys must be strings".format(label))
            normalized_key = key.lower().replace("-", "_")
            if normalized_key in _SENSITIVE_KEYS:
                raise ValueError("{} contains a prohibited sensitive field".format(label))
            result[key] = _canonical_value(item, label, depth + 1)
        return result
    raise TypeError("{} contains a value outside the closed JSON types".format(label))


def _canonical_json(value: Any, label: str) -> str:
    normalized = _canonical_value(value, label)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON constant {}".format(value))


def _unique_object(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _decode_canonical_json(value: str) -> Any:
    try:
        decoded = json.loads(
            value,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        if _canonical_json(decoded, "stored snapshot") != value:
            raise ValueError("stored JSON is not canonical")
        return decoded
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise StoreCorruptionError("journal contains invalid canonical JSON") from error


def _timestamp() -> str:
    return (
        _datetime.datetime.now(_datetime.timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _validated_bounds(value: Any) -> Dict[str, Any]:
    if type(value) is CoreOperationalBounds:
        bounds = value
    elif type(value) is dict and set(value) == set(_BOUND_FIELDS):
        bounds = CoreOperationalBounds(**value)
    else:
        raise TypeError("bounds must be CoreOperationalBounds or its exact closed field mapping")
    return {name: getattr(bounds, name) for name in _BOUND_FIELDS}


def _validated_profile(value: Any) -> Dict[str, Any]:
    if type(value) is StandardResearchProfile:
        snapshot = value.snapshot()
    elif type(value) is dict:
        snapshot = value
    else:
        raise TypeError("profile_snapshot must be the approved profile or its snapshot")
    approved = STANDARD_RESEARCH_PROFILE.snapshot()
    if snapshot != approved:
        raise ValueError("profile_snapshot is not the approved Standard Research Profile")
    _canonical_json(snapshot, "profile_snapshot")
    return snapshot


def _validated_metadata(value: Any) -> Dict[str, Any]:
    if type(value) is not dict or set(value) != _METADATA_FIELDS:
        raise ValueError("metadata must contain exactly the three frozen snapshot fields")
    configuration = value["configuration_snapshot"]
    if (
        type(configuration) is not dict
        or set(configuration) != _CONFIGURATION_FIELDS
        or any(type(configuration[field]) is not list or configuration[field] for field in _CONFIGURATION_FIELDS)
    ):
        raise ValueError("configuration_snapshot must be the empty in-slice shell snapshot")
    execution = value["execution_snapshot"]
    if type(execution) is not dict or execution:
        raise ValueError("execution_snapshot must be empty when no executor is configured")
    versions = value["contract_versions"]
    if type(versions) is not dict or set(versions) != _CONTRACT_VERSION_FIELDS:
        raise ValueError("contract_versions must contain exactly the frozen shell version fields")
    for version in versions.values():
        if type(version) is not str or _SAFE_VERSION_RE.fullmatch(version) is None:
            raise ValueError("contract version values must be short non-secret identifiers")
    snapshot = {
        "configuration_snapshot": {"models": [], "sources": [], "skills": []},
        "execution_snapshot": {},
        "contract_versions": dict(versions),
    }
    _canonical_json(snapshot, "metadata")
    return snapshot


def _validated_diagnostics(value: Any) -> List[str]:
    if type(value) not in (list, tuple):
        raise TypeError("diagnostics must be a list or tuple of closed diagnostic codes")
    result = list(value)
    if any(type(item) is not str or _DIAGNOSTIC_RE.fullmatch(item) is None for item in result):
        raise ValueError("diagnostics must contain only uppercase diagnostic codes")
    return result


def _validate_shell_outcome(value: Any) -> Any:
    """Accept only terminal status tags or this slice's fixed blocked shell DTO."""

    if type(value) is str and value in _TERMINAL_STATUSES:
        return value
    expected_fields = {"executor_status", "reason", "host_shell_version"}
    if type(value) is not dict or set(value) != expected_fields:
        raise ValueError("stage outcome is outside the closed shell result contract")
    if value["executor_status"] != "NOT_CONFIGURED":
        raise ValueError("unsupported executor result")
    if value["reason"] != "HOST_EXECUTOR_NOT_CONFIGURED":
        raise ValueError("unsupported blocked reason")
    if (
        type(value["host_shell_version"]) is not str
        or _SAFE_VERSION_RE.fullmatch(value["host_shell_version"]) is None
    ):
        raise ValueError("host shell version is not a safe version identifier")
    return dict(value)


def _effective_uid() -> int:
    getter = getattr(os, "geteuid", None)
    if getter is None:
        raise HostStoreError("private SQLite storage requires POSIX file ownership support")
    return getter()


def _absolute_path(db_path: Any) -> Path:
    try:
        raw_path = os.fspath(db_path)
    except TypeError as error:
        raise TypeError("db_path must be path-like") from error
    if type(raw_path) is not str or not raw_path:
        raise ValueError("db_path must be a non-empty text path")
    expanded = Path(raw_path).expanduser()
    if ".." in expanded.parts:
        raise ValueError("db_path must not contain parent traversal")
    path = Path(os.path.abspath(str(expanded)))
    if path.name in ("", "."):
        raise ValueError("db_path must name a database file")
    return path


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current = current / component
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise ValueError("symlink paths are not allowed for the private journal")


def _reject_git_path(path: Path) -> None:
    for directory in (path.parent, *path.parent.parents):
        if os.path.lexists(str(directory / ".git")):
            raise ValueError("SQLite journal must be outside every Git working tree")


def _prepare_parent(path: Path) -> None:
    parent = path.parent
    missing: List[Path] = []
    created: set = set()
    current = parent
    while not current.exists():
        missing.append(current)
        if current.parent == current:
            raise ValueError("cannot find an existing parent directory")
        current = current.parent
    _reject_symlink_components(current)
    if not current.is_dir():
        raise ValueError("database parent must be a directory")
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            pass
        else:
            created.add(directory)
        _reject_symlink_components(directory)
        if not directory.is_dir():
            raise ValueError("database parent path is not a directory")
        if directory in created:
            os.chmod(str(directory), 0o700)

    _reject_symlink_components(parent)
    parent_stat = parent.lstat()
    if not stat.S_ISDIR(parent_stat.st_mode):
        raise ValueError("database parent must be a regular directory")
    if parent_stat.st_uid != _effective_uid():
        raise ValueError("database parent must be owned by the current user")
    if stat.S_IMODE(parent_stat.st_mode) != 0o700:
        if parent not in created:
            raise ValueError("existing database parent must already have mode 0700")
        os.chmod(str(parent), 0o700)
    if stat.S_IMODE(parent.lstat().st_mode) != 0o700:
        raise HostStoreError("database parent permissions are not private")


def _prepare_database_file(path: Path) -> None:
    _reject_symlink_components(path)
    try:
        file_stat = path.lstat()
    except FileNotFoundError:
        flags = os.O_CREAT | os.O_EXCL | os.O_RDWR
        flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(str(path), flags, 0o600)
        except FileExistsError:
            file_stat = path.lstat()
        else:
            try:
                os.fchmod(descriptor, 0o600)
            finally:
                os.close(descriptor)
            file_stat = path.lstat()
    if not stat.S_ISREG(file_stat.st_mode):
        raise ValueError("database path must be a regular file, not a link or special file")
    if file_stat.st_uid != _effective_uid():
        raise ValueError("database file must be owned by the current user")
    if file_stat.st_nlink != 1:
        raise ValueError("database file must not have additional hard links")
    os.chmod(str(path), 0o600)
    if stat.S_IMODE(path.lstat().st_mode) != 0o600:
        raise HostStoreError("database file permissions are not private")


def _acquire_database_lock(path: Path) -> int:
    """Hold an exclusive non-blocking lock on a persistent private sidecar."""

    descriptor: Optional[int] = None
    try:
        lock_path = path.with_name(path.name + ".lock")
        _reject_symlink_components(lock_path)
        nofollow = getattr(os, "O_NOFOLLOW", None)
        if nofollow is None:
            raise OSError("no no-follow open support")
        descriptor = os.open(
            str(lock_path), os.O_CREAT | os.O_RDWR | nofollow, 0o600
        )
        file_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_uid != _effective_uid()
            or file_stat.st_nlink != 1
        ):
            raise OSError("lock file failed private ownership checks")
        os.fchmod(descriptor, 0o600)
        if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o600:
            raise OSError("lock file permissions are not private")
        path_stat = lock_path.lstat()
        if (path_stat.st_dev, path_stat.st_ino) != (file_stat.st_dev, file_stat.st_ino):
            raise OSError("lock path changed during acquisition")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return descriptor
    except (OSError, ValueError):
        if descriptor is not None:
            os.close(descriptor)
        raise HostStoreError("could not acquire exclusive HostStore database lock") from None


def _release_database_lock(descriptor: int) -> None:
    """Release the sidecar lock; the inode itself deliberately persists."""

    try:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


class HostStore:
    """Append-only schema-v1 local journal with crash recovery."""

    def __init__(self, db_path: Any) -> None:
        self.db_path = _absolute_path(db_path)
        _reject_symlink_components(self.db_path)
        _reject_git_path(self.db_path)
        _prepare_parent(self.db_path)
        _prepare_database_file(self.db_path)
        self._lock = threading.RLock()
        self._closed = False
        self._connection: Optional[sqlite3.Connection] = None
        self._lock_fd: Optional[int] = None
        try:
            self._lock_fd = _acquire_database_lock(self.db_path)
            self._connection = sqlite3.connect(
                str(self.db_path), timeout=5.0, isolation_level=None, check_same_thread=False
            )
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA busy_timeout=5000")
            self._connection.execute("PRAGMA journal_mode=DELETE")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._initialize_schema()
            self._validate_history()
            self._recover_running_runs()
        except UnsupportedSchemaVersionError:
            self._close_failed_connection()
            raise
        except StoreCorruptionError:
            self._close_failed_connection()
            raise
        except sqlite3.DatabaseError as error:
            self._close_failed_connection()
            raise StoreCorruptionError("database is corrupt or is not a Host journal") from error
        except Exception:
            self._close_failed_connection()
            raise

    def _close_failed_connection(self) -> None:
        try:
            if self._connection is not None:
                self._connection.close()
        finally:
            self._connection = None
            if self._lock_fd is not None:
                _release_database_lock(self._lock_fd)
                self._lock_fd = None
            self._closed = True

    def _conn(self) -> sqlite3.Connection:
        if self._closed or self._connection is None:
            raise HostStoreError("HostStore is closed")
        return self._connection

    @contextlib.contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._conn()
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()

    def _initialize_schema(self) -> None:
        connection = self._conn()
        check = connection.execute("PRAGMA quick_check").fetchone()
        if check is None or check[0] != "ok":
            raise StoreCorruptionError("SQLite quick_check rejected the database")
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError("database schema is newer than schema v1")
        if version < 0:
            raise StoreCorruptionError("database schema version is invalid")
        application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
        objects = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type IN ('table','index','trigger','view') AND name NOT LIKE 'sqlite_%'"
            )
        }
        if version == 0:
            if objects or application_id != 0:
                raise StoreCorruptionError("unversioned non-empty database is not migratable")
            with self._transaction() as transaction:
                transaction.execute(
                    "CREATE TABLE runs ("
                    "run_seq INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "run_id TEXT NOT NULL UNIQUE,"
                    "created_at TEXT NOT NULL"
                    ")"
                )
                transaction.execute(
                    "CREATE TABLE events ("
                    "event_seq INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "run_id TEXT NOT NULL REFERENCES runs(run_id),"
                    "event_type TEXT NOT NULL CHECK(event_type IN "
                    "('run_started','stage_started','stage_finished','run_finished')),"
                    "stage_id TEXT, stage_name TEXT, status TEXT NOT NULL,"
                    "payload_json TEXT NOT NULL, occurred_at TEXT NOT NULL,"
                    "CHECK ((event_type IN ('run_started','run_finished') AND stage_id IS NULL AND stage_name IS NULL) "
                    "OR (event_type IN ('stage_started','stage_finished') AND stage_id IS NOT NULL AND stage_name IS NOT NULL))"
                    ")"
                )
                transaction.execute(
                    "CREATE TRIGGER runs_no_update BEFORE UPDATE ON runs "
                    "BEGIN SELECT RAISE(ABORT,'append-only journal'); END"
                )
                transaction.execute(
                    "CREATE TRIGGER runs_no_delete BEFORE DELETE ON runs "
                    "BEGIN SELECT RAISE(ABORT,'append-only journal'); END"
                )
                transaction.execute(
                    "CREATE TRIGGER events_no_update BEFORE UPDATE ON events "
                    "BEGIN SELECT RAISE(ABORT,'append-only journal'); END"
                )
                transaction.execute(
                    "CREATE TRIGGER events_no_delete BEFORE DELETE ON events "
                    "BEGIN SELECT RAISE(ABORT,'append-only journal'); END"
                )
                transaction.execute("PRAGMA application_id={}".format(_APPLICATION_ID))
                transaction.execute("PRAGMA user_version=1")
            version = SCHEMA_VERSION
            objects = _SCHEMA_OBJECTS
            application_id = _APPLICATION_ID
        if version != SCHEMA_VERSION or application_id != _APPLICATION_ID:
            raise StoreCorruptionError("database identity or schema version is invalid")
        if objects != _SCHEMA_OBJECTS:
            raise StoreCorruptionError("database objects do not match the frozen schema-v1 journal")
        if tuple(row["name"] for row in connection.execute("PRAGMA table_info(runs)")) != _RUN_COLUMNS:
            raise StoreCorruptionError("runs table does not match schema v1")
        if tuple(row["name"] for row in connection.execute("PRAGMA table_info(events)")) != _EVENT_COLUMNS:
            raise StoreCorruptionError("events table does not match schema v1")
        trigger_rows = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
        trigger_sql = {row["name"]: " ".join(row["sql"].lower().split()) for row in trigger_rows}
        for name, table, operation in (
            ("runs_no_update", "runs", "update"),
            ("runs_no_delete", "runs", "delete"),
            ("events_no_update", "events", "update"),
            ("events_no_delete", "events", "delete"),
        ):
            sql = trigger_sql.get(name, "")
            if "before {} on {}".format(operation, table) not in sql or "raise(abort" not in sql:
                raise StoreCorruptionError("append-only trigger definition is invalid")
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise StoreCorruptionError("journal foreign-key check failed")

    def _append_event(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        event_type: str,
        stage_id: Optional[str],
        stage_name: Optional[str],
        status: str,
        payload: Any,
        occurred_at: str,
    ) -> None:
        connection.execute(
            "INSERT INTO events(run_id,event_type,stage_id,stage_name,status,payload_json,occurred_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (
                run_id,
                event_type,
                stage_id,
                stage_name,
                status,
                _canonical_json(payload, "event payload"),
                occurred_at,
            ),
        )

    def _events_for(self, run_id: str) -> List[sqlite3.Row]:
        return self._conn().execute(
            "SELECT event_seq,run_id,event_type,stage_id,stage_name,status,payload_json,occurred_at "
            "FROM events WHERE run_id=? ORDER BY event_seq",
            (run_id,),
        ).fetchall()

    def _status_and_stages(self, run_id: str) -> Tuple[str, Dict[str, sqlite3.Row], set]:
        events = self._events_for(run_id)
        if not events or events[0]["event_type"] != "run_started":
            raise StoreCorruptionError("run is missing its initial snapshot event")
        status = "RUNNING"
        started: Dict[str, sqlite3.Row] = {}
        finished = set()
        terminal_seen = False
        for event_index, event in enumerate(events):
            event_type = event["event_type"]
            if terminal_seen:
                raise StoreCorruptionError("journal contains events after run termination")
            if event_type == "run_started":
                if event_index != 0:
                    raise StoreCorruptionError("run contains duplicate start events")
                continue
            if event_type == "stage_started":
                stage_id = event["stage_id"]
                if not stage_id or stage_id in started or event["status"] != "RUNNING":
                    raise StoreCorruptionError("stage start event is invalid")
                started[stage_id] = event
            elif event_type == "stage_finished":
                stage_id = event["stage_id"]
                if stage_id not in started or stage_id in finished:
                    raise StoreCorruptionError("stage completion is unpaired or duplicated")
                if started[stage_id]["stage_name"] != event["stage_name"]:
                    raise StoreCorruptionError("stage name changed between paired events")
                if event["status"] not in _TERMINAL_STATUSES:
                    raise StoreCorruptionError("stage terminal status is invalid")
                finished.add(stage_id)
            elif event_type == "run_finished":
                if event["status"] not in _TERMINAL_STATUSES:
                    raise StoreCorruptionError("run terminal status is invalid")
                if set(started) != finished:
                    raise StoreCorruptionError("run terminated with an unfinished stage")
                status = event["status"]
                terminal_seen = True
            else:
                raise StoreCorruptionError("journal contains an unknown event type")
            payload = _decode_canonical_json(event["payload_json"])
            if event_type == "stage_finished":
                if type(payload) is not dict or set(payload) != {"outcome", "diagnostics"}:
                    raise StoreCorruptionError("stage result payload is malformed")
                try:
                    _validate_shell_outcome(payload["outcome"])
                    _validated_diagnostics(payload["diagnostics"])
                except (TypeError, ValueError) as error:
                    raise StoreCorruptionError("stage result payload violates the shell contract") from error
            elif event_type == "run_finished":
                if type(payload) is not dict or set(payload) != {"diagnostics"}:
                    raise StoreCorruptionError("run result payload is malformed")
                try:
                    _validated_diagnostics(payload["diagnostics"])
                except (TypeError, ValueError) as error:
                    raise StoreCorruptionError("run diagnostics violate the shell contract") from error
        return status, started, finished

    def _validate_history(self) -> None:
        connection = self._conn()
        rows = connection.execute("SELECT run_id FROM runs ORDER BY run_seq").fetchall()
        for row in rows:
            run_id = row["run_id"]
            events = self._events_for(run_id)
            if not events:
                raise StoreCorruptionError("run row has no immutable start event")
            start = events[0]
            if start["event_type"] != "run_started" or start["status"] != "RUNNING":
                raise StoreCorruptionError("run start event is malformed")
            snapshot = _decode_canonical_json(start["payload_json"])
            if type(snapshot) is not dict or set(snapshot) != {
                "mode", "input", "input_sha256", "bounds", "profile_snapshot", "metadata"
            }:
                raise StoreCorruptionError("run snapshot fields do not match schema v1")
            if (
                type(snapshot["mode"]) is not str
                or snapshot["mode"] not in _MODES
                or type(snapshot["input"]) is not str
                or type(snapshot["input_sha256"]) is not str
            ):
                raise StoreCorruptionError("run snapshot mode or input is malformed")
            expected_hash = hashlib.sha256(snapshot["input"].encode("utf-8")).hexdigest()
            if snapshot["input_sha256"] != expected_hash:
                raise StoreCorruptionError("run input hash does not match its immutable input")
            try:
                _validated_bounds(snapshot["bounds"])
                _validated_profile(snapshot["profile_snapshot"])
                _validated_metadata(snapshot["metadata"])
            except (TypeError, ValueError) as error:
                raise StoreCorruptionError("run snapshot violates its frozen field contract") from error
            self._status_and_stages(run_id)

    def _recover_running_runs(self) -> None:
        connection = self._conn()
        with self._transaction() as transaction:
            run_rows = transaction.execute("SELECT run_id FROM runs ORDER BY run_seq").fetchall()
            for row in run_rows:
                run_id = row["run_id"]
                status, started, finished = self._status_and_stages(run_id)
                if status != "RUNNING":
                    continue
                now = _timestamp()
                for stage_id, stage_event in started.items():
                    if stage_id in finished:
                        continue
                    self._append_event(
                        transaction,
                        run_id,
                        "stage_finished",
                        stage_id,
                        stage_event["stage_name"],
                        "INTERRUPTED",
                        {"outcome": "INTERRUPTED", "diagnostics": ["PROCESS_RESTART"]},
                        now,
                    )
                self._append_event(
                    transaction,
                    run_id,
                    "run_finished",
                    None,
                    None,
                    "INTERRUPTED",
                    {"diagnostics": ["PROCESS_RESTART"]},
                    now,
                )

    def create_run(
        self,
        mode: str,
        input: str,
        bounds: Any,
        profile_snapshot: Any,
        metadata: Any,
    ) -> str:
        if type(mode) is not str or mode not in _MODES:
            raise ValueError("mode must be world, event, or direct")
        if type(input) is not str or not input.strip():
            raise ValueError("input must be a non-empty raw string")
        input.encode("utf-8", "strict")
        bounds_snapshot = _validated_bounds(bounds)
        profile = _validated_profile(profile_snapshot)
        metadata_snapshot = _validated_metadata(metadata)
        snapshot = {
            "mode": mode,
            "input": input,
            "input_sha256": hashlib.sha256(input.encode("utf-8")).hexdigest(),
            "bounds": bounds_snapshot,
            "profile_snapshot": profile,
            "metadata": metadata_snapshot,
        }
        payload_json = _canonical_json(snapshot, "run snapshot")
        run_id = str(uuid.uuid4())
        now = _timestamp()
        with self._lock, self._transaction() as connection:
            connection.execute(
                "INSERT INTO runs(run_id,created_at) VALUES(?,?)", (run_id, now)
            )
            connection.execute(
                "INSERT INTO events(run_id,event_type,stage_id,stage_name,status,payload_json,occurred_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (run_id, "run_started", None, None, "RUNNING", payload_json, now),
            )
        return run_id

    def start_stage(self, run_id: str, name: str) -> str:
        self._validate_run_id(run_id)
        if type(name) is not str or not name or len(name) > 128 or not name.isprintable():
            raise ValueError("stage name must be a short printable string")
        stage_id = str(uuid.uuid4())
        now = _timestamp()
        with self._lock, self._transaction() as connection:
            self._require_run(connection, run_id)
            status, _started, _finished = self._status_and_stages(run_id)
            if status != "RUNNING":
                raise ValueError("cannot start a stage after the run is terminal")
            self._append_event(
                connection, run_id, "stage_started", stage_id, name, "RUNNING", {}, now
            )
        return stage_id

    def finish_stage(
        self,
        run_id: str,
        stage_id: str,
        status: str,
        outcome: Any,
        diagnostics: Any,
    ) -> None:
        self._validate_run_id(run_id)
        self._validate_stage_id(stage_id)
        if type(status) is not str or status not in _TERMINAL_STATUSES:
            raise ValueError("stage status must be a terminal Host status")
        normalized_diagnostics = _validated_diagnostics(diagnostics)
        normalized_outcome = _validate_shell_outcome(outcome)
        payload = {"outcome": normalized_outcome, "diagnostics": normalized_diagnostics}
        now = _timestamp()
        with self._lock, self._transaction() as connection:
            self._require_run(connection, run_id)
            run_status, started, finished = self._status_and_stages(run_id)
            if run_status != "RUNNING":
                raise ValueError("cannot finish a stage after the run is terminal")
            if stage_id not in started or stage_id in finished:
                raise ValueError("stage must have exactly one prior unmatched start")
            stage_event = started[stage_id]
            self._append_event(
                connection,
                run_id,
                "stage_finished",
                stage_id,
                stage_event["stage_name"],
                status,
                payload,
                now,
            )

    def finish_run(self, run_id: str, status: str, diagnostics: Any) -> None:
        self._validate_run_id(run_id)
        if type(status) is not str or status not in _TERMINAL_STATUSES:
            raise ValueError("run status must be a terminal Host status")
        normalized_diagnostics = _validated_diagnostics(diagnostics)
        payload = {"diagnostics": normalized_diagnostics}
        now = _timestamp()
        with self._lock, self._transaction() as connection:
            self._require_run(connection, run_id)
            current_status, started, finished = self._status_and_stages(run_id)
            if current_status != "RUNNING":
                raise ValueError("run already has a terminal state")
            if set(started) != finished:
                raise ValueError("all started stages must finish before the run")
            self._append_event(
                connection, run_id, "run_finished", None, None, status, payload, now
            )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        self._validate_run_id(run_id)
        with self._lock:
            row = self._conn().execute(
                "SELECT run_seq,run_id,created_at FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None:
                return None
            events = self._events_for(run_id)
            start_snapshot = _decode_canonical_json(events[0]["payload_json"])
            status, started, finished = self._status_and_stages(run_id)
            run_finish = next((event for event in reversed(events) if event["event_type"] == "run_finished"), None)
            result: Dict[str, Any] = {
                "run_id": run_id,
                "mode": start_snapshot["mode"],
                "input": start_snapshot["input"],
                "input_sha256": start_snapshot["input_sha256"],
                "bounds": start_snapshot["bounds"],
                "profile_snapshot": start_snapshot["profile_snapshot"],
                "metadata": start_snapshot["metadata"],
                "status": status,
                "created_at": row["created_at"],
                "updated_at": events[-1]["occurred_at"],
            }
            if run_finish is not None:
                result["diagnostics"] = _decode_canonical_json(run_finish["payload_json"])["diagnostics"]
            stage_events: List[Dict[str, Any]] = []
            for event in events:
                if event["event_type"] not in ("stage_started", "stage_finished"):
                    continue
                stage_id = event["stage_id"]
                start_event = started[stage_id]
                public_event: Dict[str, Any] = {
                    "event": event["event_type"],
                    "stage": event["stage_name"],
                    "stage_id": stage_id,
                    "status": event["status"],
                    "started_at": start_event["occurred_at"],
                }
                if event["event_type"] == "stage_finished":
                    finish_payload = _decode_canonical_json(event["payload_json"])
                    public_event["outcome"] = finish_payload["outcome"]
                    public_event["diagnostics"] = finish_payload["diagnostics"]
                    public_event["completed_at"] = event["occurred_at"]
                stage_events.append(public_event)
            result["events"] = stage_events
            return result

    def list_runs(self) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn().execute(
                "SELECT run_id FROM runs ORDER BY run_seq ASC"
            ).fetchall()
            results: List[Dict[str, Any]] = []
            for row in rows:
                run = self.get_run(row["run_id"])
                if run is None:
                    raise StoreCorruptionError("run disappeared from the append-only journal")
                results.append(
                    {
                        key: run[key]
                        for key in ("run_id", "mode", "status", "created_at", "updated_at")
                    }
                )
            return results

    def _require_run(self, connection: sqlite3.Connection, run_id: str) -> None:
        if connection.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone() is None:
            raise KeyError(run_id)

    @staticmethod
    def _validate_run_id(run_id: Any) -> None:
        if type(run_id) is not str or _ID_RE.fullmatch(run_id) is None:
            raise ValueError("run_id is invalid")

    @staticmethod
    def _validate_stage_id(stage_id: Any) -> None:
        if type(stage_id) is not str or _ID_RE.fullmatch(stage_id) is None:
            raise ValueError("stage_id is invalid")

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                if self._connection is not None:
                    self._connection.close()
            finally:
                self._connection = None
                if self._lock_fd is not None:
                    _release_database_lock(self._lock_fd)
                    self._lock_fd = None
                self._closed = True
