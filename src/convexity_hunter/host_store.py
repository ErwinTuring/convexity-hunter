"""Private append-only SQLite journal for the minimal Host shell.

This store persists run events and closed Direct artifacts through the typed
Core snapshot codec. It does not call providers or read configuration files.
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
from urllib.parse import parse_qsl, urlsplit

from .core_application import CoreOperationalBounds
from .host_profile import STANDARD_RESEARCH_PROFILE, StandardResearchProfile


SCHEMA_VERSION = 3
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
_AUTH_URI_KEYS = _SENSITIVE_KEYS | {
    "apikey", "auth", "auth_token", "authtoken", "accesstoken", "client_secret",
    "clientsecret", "bearer", "credential", "credentials", "signature", "sig",
    "x_amz_credential", "x_amz_signature", "x_amz_security_token",
}
_DIAGNOSTIC_RE = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z", re.ASCII)
_ID_RE = re.compile(r"[A-Za-z0-9._~-]{1,128}\Z", re.ASCII)
_CASE_ID_RE = re.compile(r"[A-Za-z0-9._:~-]{1,256}\Z", re.ASCII)
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
_DIRECT_CASE_TABLE_SQL = (
    "CREATE TABLE direct_cases (run_id TEXT NOT NULL REFERENCES runs(run_id),"
    "case_id TEXT NOT NULL,archive_json TEXT NOT NULL,archive_sha256 TEXT NOT NULL,"
    "PRIMARY KEY(run_id,case_id))"
)
_DIRECT_SCHEMA_OBJECTS = _SCHEMA_OBJECTS | {
    "direct_cases", "direct_cases_no_update", "direct_cases_no_delete"
}
_BATCH_ARCHIVE_TABLE_SQL = (
    "CREATE TABLE batch_archives (run_id TEXT PRIMARY KEY NOT NULL REFERENCES runs(run_id),"
    "archive_json TEXT NOT NULL,archive_sha256 TEXT NOT NULL)"
)
_BATCH_SCHEMA_OBJECTS = _DIRECT_SCHEMA_OBJECTS | {
    "batch_archives", "batch_archives_no_update", "batch_archives_no_delete"
}
_DIRECT_REPORT_VERSION = "core-presentation-direct-v0.1"


class HostStoreError(RuntimeError):
    """Base exception for a rejected or unavailable Host journal."""


class UnsupportedSchemaVersionError(HostStoreError):
    """The database schema is newer than this implementation supports."""


class StoreCorruptionError(HostStoreError):
    """The database is not a valid versioned Host journal."""


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


def _validate_uri_credentials(uri: Any, label: str) -> None:
    """Reject URI authentication material without rewriting retained locators."""

    if type(uri) is not str:
        raise ValueError("{} must be text".format(label))
    try:
        parts = urlsplit(uri)
        if parts.username is not None or parts.password is not None:
            raise ValueError()
        fragment = parts.fragment.partition("?")[2] if "?" in parts.fragment else parts.fragment
        for parameters in (parts.query, fragment.lstrip("?")):
            if any(
                key.casefold().replace("-", "_") in _AUTH_URI_KEYS
                for key, _ in parse_qsl(parameters, keep_blank_values=True)
            ):
                raise ValueError()
    except ValueError:
        raise ValueError("{} contains invalid or prohibited authentication material".format(label)) from None


def _validate_event_source_locator(value: Any) -> None:
    """Guard URL-like EI/Event locators while allowing provider-neutral labels."""

    if value is None:
        return
    if type(value) is not str:
        raise ValueError("source locator must be text or None")
    try:
        parts = urlsplit(value)
    except ValueError:
        raise ValueError("source locator contains invalid or prohibited authentication material") from None
    if parts.scheme or parts.netloc or "://" in value or value.startswith("//"):
        _validate_uri_credentials(value, "source locator")


def _validate_source_reference_uris(value: Any) -> None:
    """Check only URI fields of known codec SourceReference nodes, without rewriting."""

    if type(value) is dict:
        if value.get("$type") == "market_data.SourceReference":
            uri = value.get("source_uri")
            if uri is not None:
                _validate_uri_credentials(uri, "SourceReference URI")
        for item in value.values():
            _validate_source_reference_uris(item)
    elif type(value) is list:
        for item in value:
            _validate_source_reference_uris(item)


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
    if type(execution) is not dict:
        raise ValueError("execution_snapshot must contain only closed configured executor records")
    allowed_executors = {
        "direct_executor": "host-direct-input-v0.1",
        "world_executor": "host-batch-executor-v0.1",
        "event_executor": "host-batch-executor-v0.1",
    }
    if set(execution) - set(allowed_executors):
        raise ValueError("execution_snapshot contains an unknown executor")
    for name, version in allowed_executors.items():
        if name in execution and execution[name] != {"status": "CONFIGURED", "version": version}:
            raise ValueError("execution_snapshot contains an invalid executor record")
    versions = value["contract_versions"]
    if type(versions) is not dict or set(versions) != _CONTRACT_VERSION_FIELDS:
        raise ValueError("contract_versions must contain exactly the frozen shell version fields")
    for version in versions.values():
        if type(version) is not str or _SAFE_VERSION_RE.fullmatch(version) is None:
            raise ValueError("contract version values must be short non-secret identifiers")
    snapshot = {
        "configuration_snapshot": {"models": [], "sources": [], "skills": []},
        "execution_snapshot": dict(execution),
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
    batch_fields = {"schema_version", "case_count", "unavailable_count", "status"}
    if type(value) is dict and set(value) == batch_fields:
        if (
            type(value["schema_version"]) is not str
            or value["schema_version"] != "host-batch-outcome-v0.1"
        ):
            raise ValueError("invalid closed batch outcome version")
        for name in ("case_count", "unavailable_count"):
            if type(value[name]) is not int or value[name] < 0:
                raise ValueError("invalid closed batch outcome count")
        if type(value["status"]) is not str or value["status"] not in (
            "COMPLETED", "PARTIAL", "BLOCKED"
        ):
            raise ValueError("invalid closed batch outcome status")
        return dict(value)
    if type(value) is dict and set(value) == {"schema_version", "case_id", "classification"}:
        from .core_research import CoreDisposition
        if (value["schema_version"] != "host-direct-outcome-v0.1"
                or type(value["case_id"]) is not str
                or _CASE_ID_RE.fullmatch(value["case_id"]) is None
                or type(value["classification"]) is not str
                or value["classification"] not in {item.value for item in CoreDisposition}):
            raise ValueError("invalid closed Direct outcome")
        return dict(value)
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
    """Append-only schema-v3 local journal with crash recovery."""

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
            raise UnsupportedSchemaVersionError("database schema is newer than schema v3")
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
            version = 1
            objects = _SCHEMA_OBJECTS
            application_id = _APPLICATION_ID
        if version not in (1, 2, 3) or application_id != _APPLICATION_ID:
            raise StoreCorruptionError("database identity or schema version is invalid")
        expected_objects = (
            _SCHEMA_OBJECTS if version == 1
            else _DIRECT_SCHEMA_OBJECTS if version == 2
            else _BATCH_SCHEMA_OBJECTS
        )
        if objects != expected_objects:
            raise StoreCorruptionError("database objects do not match the journal schema")
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
        if version == 1:
            with self._transaction() as transaction:
                transaction.execute(_DIRECT_CASE_TABLE_SQL)
                for operation in ("update", "delete"):
                    transaction.execute(
                        "CREATE TRIGGER direct_cases_no_{} BEFORE {} ON direct_cases "
                        "BEGIN SELECT RAISE(ABORT,'append-only journal'); END".format(operation, operation)
                    )
                transaction.execute("PRAGMA user_version=2")
            version = 2
        if version == 2:
            expected_direct = {"direct_cases": _DIRECT_CASE_TABLE_SQL}
            for operation in ("update", "delete"):
                expected_direct["direct_cases_no_" + operation] = (
                    "CREATE TRIGGER direct_cases_no_{} BEFORE {} ON direct_cases "
                    "BEGIN SELECT RAISE(ABORT,'append-only journal'); END".format(
                        operation, operation
                    )
                )
            actual_direct = dict(connection.execute(
                "SELECT name,sql FROM sqlite_master WHERE name IN "
                "('direct_cases','direct_cases_no_update','direct_cases_no_delete')"
            ).fetchall())
            if (
                any(
                    " ".join(actual_direct.get(name, "").lower().split())
                    != " ".join(sql.lower().split())
                    for name, sql in expected_direct.items()
                )
                or tuple(
                    row["name"] for row in connection.execute("PRAGMA table_info(direct_cases)")
                ) != ("run_id", "case_id", "archive_json", "archive_sha256")
            ):
                raise StoreCorruptionError("Direct schema v2 is invalid; batch migration was not applied")
            with self._transaction() as transaction:
                transaction.execute(_BATCH_ARCHIVE_TABLE_SQL)
                for operation in ("update", "delete"):
                    transaction.execute(
                        "CREATE TRIGGER batch_archives_no_{} BEFORE {} ON batch_archives "
                        "BEGIN SELECT RAISE(ABORT,'append-only journal'); END".format(operation, operation)
                    )
                transaction.execute("PRAGMA user_version=3")

        expected = {
            "direct_cases": _DIRECT_CASE_TABLE_SQL,
            "batch_archives": _BATCH_ARCHIVE_TABLE_SQL,
        }
        for table in ("direct_cases", "batch_archives"):
            for operation in ("update", "delete"):
                expected[table + "_no_" + operation] = (
                    "CREATE TRIGGER {}_no_{} BEFORE {} ON {} "
                    "BEGIN SELECT RAISE(ABORT,'append-only journal'); END".format(
                        table, operation, operation, table
                    )
                )
        actual = dict(connection.execute(
            "SELECT name,sql FROM sqlite_master WHERE name IN "
            "('direct_cases','direct_cases_no_update','direct_cases_no_delete',"
            "'batch_archives','batch_archives_no_update','batch_archives_no_delete')"
        ).fetchall())
        if any(" ".join(actual.get(name, "").lower().split()) != " ".join(sql.lower().split())
               for name, sql in expected.items()):
            raise StoreCorruptionError("immutable case archive tables or triggers do not match schema v3")
        if tuple(row["name"] for row in connection.execute("PRAGMA table_info(direct_cases)")) != (
            "run_id", "case_id", "archive_json", "archive_sha256"
        ):
            raise StoreCorruptionError("Direct table does not match schema v2")
        if tuple(row["name"] for row in connection.execute("PRAGMA table_info(batch_archives)")) != (
            "run_id", "archive_json", "archive_sha256"
        ):
            raise StoreCorruptionError("batch archive table does not match schema v3")

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
                if type(payload["outcome"]) is dict and "case_id" in payload["outcome"]:
                    archive = self.get_direct_case(run_id, payload["outcome"]["case_id"])
                    if (archive is None or event["status"] != "COMPLETED"
                            or archive["classification"] != payload["outcome"]["classification"]):
                        raise StoreCorruptionError("Direct stage has no matching committed archive")
                elif (
                    type(payload["outcome"]) is dict
                    and payload["outcome"].get("schema_version") == "host-batch-outcome-v0.1"
                ):
                    archive, _decoded = self._read_batch_archive(run_id)
                    if (
                        archive is None
                        or archive["outcome"] != payload["outcome"]
                        or event["status"] != payload["outcome"]["status"]
                    ):
                        raise StoreCorruptionError("batch stage has no matching committed archive")
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
            batch_rows = connection.execute(
                "SELECT run_id FROM batch_archives WHERE run_id=?", (run_id,)
            ).fetchall()
            for _batch_row in batch_rows:
                archive, _decoded = self._read_batch_archive(run_id)
                if archive is None:
                    raise StoreCorruptionError("batch archive disappeared during validation")

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
            if type(normalized_outcome) is dict and "case_id" in normalized_outcome:
                archive = self.get_direct_case(run_id, normalized_outcome["case_id"])
                if (archive is None or status != "COMPLETED"
                        or archive["classification"] != normalized_outcome["classification"]):
                    raise ValueError("Direct outcome requires its committed case and COMPLETED stage")
            elif (
                type(normalized_outcome) is dict
                and normalized_outcome.get("schema_version") == "host-batch-outcome-v0.1"
            ):
                archive, _decoded = self._read_batch_archive(run_id)
                if (
                    archive is None
                    or archive["outcome"] != normalized_outcome
                    or status != normalized_outcome["status"]
                ):
                    raise ValueError("batch outcome requires its matching committed archive and status")
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
            if status == "BLOCKED" and connection.execute(
                "SELECT 1 FROM direct_cases WHERE run_id=?", (run_id,)
            ).fetchone() is not None:
                raise ValueError("completed Core evaluation cannot be Host BLOCKED")
            batch_archive, _decoded = self._read_batch_archive(run_id)
            if batch_archive is not None and status in ("COMPLETED", "PARTIAL", "BLOCKED"):
                if status != batch_archive["outcome"]["status"]:
                    raise ValueError("run status must match the validated batch Host outcome")
            self._append_event(
                connection, run_id, "run_finished", None, None, status, payload, now
            )

    def save_direct_result(self, run_id: str, result: Any) -> str:
        from .core_application import CoreDirectResult
        from .core_presentation import report
        from .host_core_snapshot import encode_core_result

        self._validate_run_id(run_id)
        if type(result) is not CoreDirectResult or result.kernel_result is None:
            raise TypeError("save requires an evaluated exact CoreDirectResult")
        result.__post_init__()  # Existing request/result/structure identity validation.
        case_id = result.kernel_request.case_id
        self._validate_case_id(case_id)
        with self._lock, self._transaction() as connection:
            run = self.get_run(run_id)
            if run is None:
                raise KeyError(run_id)
            if run["mode"] != "direct" or run["status"] != "RUNNING":
                raise ValueError("Direct archive requires a RUNNING Direct run")
            core_snapshot = encode_core_result(result.kernel_result)
            _validate_source_reference_uris(core_snapshot)
            core_digest = hashlib.sha256(_canonical_json(core_snapshot, "Core snapshot").encode("utf-8")).hexdigest()
            if result.full_report and report(result) != result.full_report:
                raise ValueError("Direct report cache differs from the current renderer")
            archive = {
                "schema_version": "host-direct-case-v0.1", "run_id": run_id, "case_id": case_id,
                "classification": result.kernel_result.disposition.value,
                "direct_reasons": list(result.reasons),
                "reasons": list(dict.fromkeys(result.reasons + tuple(item.value for item in result.kernel_result.reasons))),
                "profile_snapshot": run["profile_snapshot"], "core_snapshot": core_snapshot,
                "core_sha256": core_digest,
                "disclosures": {
                    "maturity_authority": result.maturity_authority.value,
                    "hypothesis_maturity_alignment": result.hypothesis_maturity_alignment.value,
                    "quote_reference_temporal_alignment": result.quote_reference_temporal_alignment,
                    "cross_structure_quote_synchronicity": result.cross_structure_quote_synchronicity,
                },
                "report_cache": None if not result.full_report else {
                    "renderer_version": _DIRECT_REPORT_VERSION,
                    "core_sha256": core_digest, "text": result.full_report,
                },
            }
            self._validate_direct_archive(archive, run_id, case_id)
            wire = _canonical_json(archive, "Direct archive")
            try:
                connection.execute("INSERT INTO direct_cases VALUES(?,?,?,?)", (
                    run_id, case_id, wire, hashlib.sha256(wire.encode("utf-8")).hexdigest()
                ))
            except sqlite3.IntegrityError:
                raise ValueError("Direct case already archived") from None
        return case_id

    def _validate_direct_archive(self, archive: Any, run_id: str, case_id: str) -> Any:
        from .host_core_snapshot import decode_core_result

        fields = {"schema_version", "run_id", "case_id", "classification", "direct_reasons",
                  "reasons", "profile_snapshot", "core_snapshot", "core_sha256", "disclosures", "report_cache"}
        if type(archive) is not dict or set(archive) != fields:
            raise ValueError("unknown or missing Direct archive fields")
        if (archive["schema_version"] != "host-direct-case-v0.1"
                or archive["run_id"] != run_id or archive["case_id"] != case_id):
            raise ValueError("Direct archive version or identity mismatch")
        _validate_source_reference_uris(archive["core_snapshot"])
        digest = hashlib.sha256(_canonical_json(archive["core_snapshot"], "Core snapshot").encode("utf-8")).hexdigest()
        if archive["core_sha256"] != digest:
            raise ValueError("Core snapshot digest mismatch")
        core = decode_core_result(archive["core_snapshot"])
        risk = core.request.risk_policy
        approved = STANDARD_RESEARCH_PROFILE.to_core_risk_policy(core.request.structure)
        risk_fields = ("portfolio_value", "maximum_single_loss_fraction",
                       "maximum_repeated_loss_fraction", "repeat_count", "currency")
        if risk is None or any(getattr(risk, name) != getattr(approved, name) for name in risk_fields):
            raise ValueError("Core risk inputs differ from the approved run profile")
        direct_reasons = archive["direct_reasons"]
        if (type(direct_reasons) is not list
                or any(type(item) is not str or item != "missing_direct_quote_evidence" for item in direct_reasons)
                or core.request.case_id != case_id or archive["classification"] != core.disposition.value
                or archive["reasons"] != list(dict.fromkeys(direct_reasons + [item.value for item in core.reasons]))):
            raise ValueError("Direct classification or reasons mismatch")
        start = _decode_canonical_json(self._events_for(run_id)[0]["payload_json"])
        if start["mode"] != "direct" or archive["profile_snapshot"] != start["profile_snapshot"]:
            raise ValueError("Direct archive differs from its immutable run mode or profile")
        disclosure = archive["disclosures"]
        if type(disclosure) is not dict or disclosure != {
                "maturity_authority": "neutral_structural_research",
                "hypothesis_maturity_alignment": "not_established",
                "quote_reference_temporal_alignment": "not_established",
                "cross_structure_quote_synchronicity": "not_established"}:
            raise ValueError("invalid Direct authority or temporal disclosures")
        cache = archive["report_cache"]
        if cache is not None and (type(cache) is not dict
                or set(cache) != {"renderer_version", "core_sha256", "text"}
                or cache["renderer_version"] != _DIRECT_REPORT_VERSION
                or cache["core_sha256"] != digest or type(cache["text"]) is not str or not cache["text"]):
            raise ValueError("invalid digest-bound Direct report cache")
        return core

    def save_batch_result(self, run_id: str, result: Any) -> None:
        """Atomically archive one complete, bounded World/Event Core batch."""

        from .core_application import CoreRunResult
        from .host_batch_snapshot import build_batch_archive, validate_batch_archive

        self._validate_run_id(run_id)
        if type(result) is not CoreRunResult:
            raise TypeError("save_batch_result requires exact CoreRunResult")
        result.__post_init__()
        with self._lock, self._transaction() as connection:
            run = self.get_run(run_id)
            if run is None:
                raise KeyError(run_id)
            if run["mode"] not in ("world", "event") or run["status"] != "RUNNING":
                raise ValueError("batch archive requires a RUNNING World or Event run")
            archive = build_batch_archive(
                run_id=run_id,
                mode=run["mode"],
                run_input=run["input"],
                input_sha256=run["input_sha256"],
                bounds=run["bounds"],
                profile_snapshot=run["profile_snapshot"],
                metadata=run["metadata"],
                result=result,
                canonical_json=_canonical_json,
                validate_locator=_validate_event_source_locator,
                validate_source_uris=_validate_source_reference_uris,
            )
            validated_summary, _decoded_cases = validate_batch_archive(
                archive,
                run_id=run_id,
                mode=run["mode"],
                run_input=run["input"],
                input_sha256=run["input_sha256"],
                bounds=run["bounds"],
                profile_snapshot=run["profile_snapshot"],
                metadata=run["metadata"],
                canonical_json=_canonical_json,
                validate_locator=_validate_event_source_locator,
                validate_source_uris=_validate_source_reference_uris,
            )
            if validated_summary != archive["summary"]:
                raise ValueError("batch summary validation mismatch")
            wire = _canonical_json(archive, "Host batch archive")
            digest = hashlib.sha256(wire.encode("utf-8")).hexdigest()
            try:
                connection.execute(
                    "INSERT INTO batch_archives(run_id,archive_json,archive_sha256) VALUES(?,?,?)",
                    (run_id, wire, digest),
                )
            except sqlite3.IntegrityError:
                raise ValueError("World/Event batch already archived") from None
        return None

    def _read_batch_archive(
        self, run_id: str
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        from .host_batch_snapshot import validate_batch_archive

        self._validate_run_id(run_id)
        row = self._conn().execute(
            "SELECT archive_json,archive_sha256 FROM batch_archives WHERE run_id=?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None, {}
        wire, stored_digest = row["archive_json"], row["archive_sha256"]
        if type(wire) is not str or type(stored_digest) is not str:
            raise StoreCorruptionError("batch archive encoding is malformed")
        if hashlib.sha256(wire.encode("utf-8")).hexdigest() != stored_digest:
            raise StoreCorruptionError("batch archive digest mismatch")
        archive = _decode_canonical_json(wire)
        events = self._events_for(run_id)
        if not events or events[0]["event_type"] != "run_started":
            raise StoreCorruptionError("batch archive has no immutable run-start snapshot")
        snapshot = _decode_canonical_json(events[0]["payload_json"])
        try:
            summary, decoded_cases = validate_batch_archive(
                archive,
                run_id=run_id,
                mode=snapshot["mode"],
                run_input=snapshot["input"],
                input_sha256=snapshot["input_sha256"],
                bounds=snapshot["bounds"],
                profile_snapshot=snapshot["profile_snapshot"],
                metadata=snapshot["metadata"],
                canonical_json=_canonical_json,
                validate_locator=_validate_event_source_locator,
                validate_source_uris=_validate_source_reference_uris,
            )
            if summary != archive["summary"]:
                raise ValueError("batch summary validation mismatch")
            return archive, decoded_cases
        except (TypeError, ValueError, KeyError, IndexError, AttributeError) as error:
            raise StoreCorruptionError(
                "batch archive violates its closed snapshot contract"
            ) from error

    def get_batch_summary(self, run_id: str) -> Optional[Dict[str, Any]]:
        from .host_batch_snapshot import public_summary

        with self._lock:
            archive, _decoded = self._read_batch_archive(run_id)
            return None if archive is None else public_summary(archive)

    def list_batch_cases(self, run_id: str) -> List[Dict[str, Any]]:
        from .host_batch_snapshot import public_cases

        with self._lock:
            archive, _decoded = self._read_batch_archive(run_id)
            return [] if archive is None else public_cases(archive)

    def get_batch_case(self, run_id: str, case_key: str) -> Optional[Dict[str, Any]]:
        from .host_batch_snapshot import public_case, validate_case_key

        self._validate_run_id(run_id)
        validate_case_key(case_key)
        with self._lock:
            archive, decoded_cases = self._read_batch_archive(run_id)
            return None if archive is None else public_case(archive, case_key, decoded_cases)

    def _read_direct_case(self, run_id: str, case_id: str) -> Tuple[Any, Any]:
        self._validate_run_id(run_id)
        self._validate_case_id(case_id)
        row = self._conn().execute(
            "SELECT archive_json,archive_sha256 FROM direct_cases WHERE run_id=? AND case_id=?",
            (run_id, case_id),
        ).fetchone()
        if row is None:
            return None, None
        if type(row["archive_json"]) is not str or type(row["archive_sha256"]) is not str:
            raise StoreCorruptionError("Direct archive encoding is malformed")
        if hashlib.sha256(row["archive_json"].encode("utf-8")).hexdigest() != row["archive_sha256"]:
            raise StoreCorruptionError("Direct archive digest mismatch")
        archive = _decode_canonical_json(row["archive_json"])
        try:
            return archive, self._validate_direct_archive(archive, run_id, case_id)
        except (TypeError, ValueError, KeyError, IndexError) as error:
            raise StoreCorruptionError("Direct archive violates its closed snapshot contract") from error

    def get_direct_case(self, run_id: str, case_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._read_direct_case(run_id, case_id)[0]

    def load_core_result(self, run_id: str, case_id: str) -> Any:
        with self._lock:
            return self._read_direct_case(run_id, case_id)[1]

    def list_direct_cases(self, run_id: str) -> List[Dict[str, Any]]:
        self._validate_run_id(run_id)
        with self._lock:
            rows = self._conn().execute("SELECT case_id FROM direct_cases WHERE run_id=? ORDER BY case_id", (run_id,)).fetchall()
            return [{key: archive[key] for key in ("case_id", "classification", "reasons")}
                    for archive in (self.get_direct_case(run_id, row[0]) for row in rows)]

    @staticmethod
    def _validate_case_id(case_id: Any) -> None:
        if type(case_id) is not str or _CASE_ID_RE.fullmatch(case_id) is None:
            raise ValueError("invalid Direct case_id")

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
