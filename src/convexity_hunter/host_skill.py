"""Thin native last30days host controller.

This adapter owns only the pinned three-leg handoff, bounded subprocess
launching, and the injected editorial callback.  It does not turn topics into
Convexity Hunter/EI records, rank them, or execute any source text.
"""

from __future__ import annotations

import datetime as _datetime
import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple, Union

from ._host_skill_launcher import (
    ALLOWED_SOURCE_ENV_NAMES,
    HostSkillLaunchError,
    StageExecution,
    StageRequest,
    build_child_environment,
    run_stage,
)


__all__ = (
    "AngleInput",
    "HostSkillConfig",
    "HostSkillError",
    "HostSkillResult",
    "Judgment",
    "Last30DaysSkillPin",
    "NominationInput",
    "ProviderNativeOutput",
    "SkillPin",
    "StageReceipt",
    "compute_skill_content_sha256",
    "run_last30days_discovery",
)


_VERSION_LINE = re.compile(r"^version:\s*(?:\"([^\"]+)\"|'([^']+)'|(\S+))\s*$")
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# This is the explicitly pinned executable/protocol set, not a claim that an
# arbitrary installed skill directory is a hermetic package.  Python modules
# and the vendored Node module/data files reachable from this script live under
# scripts/.  Setup helpers, maps, caches, fixtures, output and secret-shaped
# files are intentionally outside the set and are never invoked by the fixed
# three-leg argv below.
_PINNED_SCRIPT_SUFFIXES = frozenset((".py", ".mjs", ".js", ".json"))
_PIN_EXCLUDED_DIRS = frozenset(
    ("__pycache__", ".pytest_cache", "cache", "caches", "output", "outputs", "fixtures")
)
_PIN_EXCLUDED_NAME_PARTS = frozenset(("secret", "secrets", "credential", "credentials"))
_PIN_REQUIRED_FILES = (
    "SKILL.md",
    "scripts/last30days.py",
    "scripts/lib/discovery_handoff.py",
    "scripts/lib/env.py",
)
_DISCOVERY_SOURCES = frozenset(("reddit", "hackernews", "digg", "x"))
_SOURCE_ENV_BY_DISCOVERY_SOURCE = {
    # This is an explicit historical source grant, not ambient credential
    # discovery and not a general paid-provider allowlist.
    "reddit": frozenset(("SCRAPECREATORS_API_KEY",)),
    "hackernews": frozenset(),
    "digg": frozenset(),
    # Explicit X cookie headers are source credentials.  Paid X/web/model
    # provider keys are intentionally not permitted by this controller.
    "x": frozenset(("AUTH_TOKEN", "CT0")),
}
_BUNDLE_FILENAME = "discover-nominations.json"
_PENDING_FILENAME = "discover-pending.json"
_JUDGMENTS_FILENAME = "host-judgments.json"
_ANGLES_FILENAME = "host-angles.json"
_FINAL_NATIVE_FILENAME = "discover-final.json"
_MAX_NAME_CHARS = 96
_MAX_ANGLE_CHARS = 200

# Pinned to the installed last30days 3.21.1 discovery_handoff/schema
# envelope.  These are protocol constants, not a synthetic adapter schema.
_NATIVE_NOMINATIONS_SCHEMA_VERSION = "1.0"
_NATIVE_NOMINATIONS_KIND = "discovery-nominations"
_NATIVE_PENDING_SCHEMA_VERSION = "1.0"
_NATIVE_PENDING_KIND = "discovery-pending"


class HostSkillError(RuntimeError):
    """Sanitized controller failure; child/model text is never included."""

    def __init__(
        self,
        code: str,
        *,
        phase: Optional[str] = None,
        exit_code: Optional[int] = None,
    ) -> None:
        self.code = code
        self.phase = phase
        self.exit_code = exit_code
        super().__init__(code)

    def __repr__(self) -> str:
        return "HostSkillError(code={!r}, phase={!r}, exit_code={!r})".format(
            self.code, self.phase, self.exit_code
        )


def _require_text(value: object, code: str, *, max_chars: Optional[int] = None) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise HostSkillError(code)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise HostSkillError(code)
    if max_chars is not None and len(value) > max_chars:
        raise HostSkillError(code)
    return value


def _as_absolute_path(value: object, code: str) -> Path:
    try:
        path = Path(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise HostSkillError(code) from None
    if not path.is_absolute():
        raise HostSkillError(code)
    return path


@dataclass(frozen=True, repr=False)
class Last30DaysSkillPin:
    """Explicit installed skill path/version/code fingerprint."""

    path: Union[str, os.PathLike]
    version: str
    content_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _as_absolute_path(self.path, "INVALID_SKILL_PIN_PATH"))
        _require_text(self.version, "INVALID_SKILL_PIN_VERSION")
        if type(self.content_sha256) is not str or not _HEX_SHA256.fullmatch(
            self.content_sha256
        ):
            raise HostSkillError("INVALID_SKILL_PIN_HASH")

    def __repr__(self) -> str:
        return "Last30DaysSkillPin(path={!r}, version={!r}, content_sha256=<redacted>)".format(
            str(self.path), self.version
        )


SkillPin = Last30DaysSkillPin


@dataclass(frozen=True, repr=False)
class HostSkillConfig:
    """Fixed M1b runtime policy; no interpreter or budget defaults."""

    skill_pin: Last30DaysSkillPin
    python_executable: Union[str, os.PathLike]
    source_allowlist: Tuple[str, ...]
    permitted_source_envs: Tuple[str, ...]
    stage_timeout_seconds: float
    request_stage_budget: int
    max_stdout_bytes: int
    max_stderr_bytes: int
    days: int = 7
    current_only: bool = True
    no_as_of: bool = True
    handoff_ttl_seconds: int = 3600
    max_handoff_bytes: int = 2_000_000
    final_output_path: Optional[Union[str, os.PathLike]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.skill_pin, Last30DaysSkillPin):
            raise HostSkillError("INVALID_SKILL_PIN")
        object.__setattr__(
            self,
            "python_executable",
            _as_absolute_path(self.python_executable, "INVALID_PYTHON_EXECUTABLE"),
        )
        if type(self.source_allowlist) is not tuple or not self.source_allowlist:
            raise HostSkillError("INVALID_SOURCE_ALLOWLIST")
        if len(set(self.source_allowlist)) != len(self.source_allowlist):
            raise HostSkillError("DUPLICATE_SOURCE")
        if any(
            type(source) is not str or source not in _DISCOVERY_SOURCES
            for source in self.source_allowlist
        ):
            raise HostSkillError("SOURCE_NOT_DISCOVERY_CAPABLE")
        if type(self.permitted_source_envs) is not tuple:
            raise HostSkillError("INVALID_SOURCE_ENV_ALLOWLIST")
        if len(set(self.permitted_source_envs)) != len(self.permitted_source_envs):
            raise HostSkillError("DUPLICATE_SOURCE_ENV_NAME")
        if any(
            type(name) is not str or name not in ALLOWED_SOURCE_ENV_NAMES
            for name in self.permitted_source_envs
        ):
            raise HostSkillError("SOURCE_ENV_NOT_PERMITTED")
        permitted_for_sources = frozenset().union(
            *(
                _SOURCE_ENV_BY_DISCOVERY_SOURCE[source]
                for source in self.source_allowlist
            )
        )
        if any(name not in permitted_for_sources for name in self.permitted_source_envs):
            raise HostSkillError("SOURCE_ENV_NOT_AUTHORIZED")
        if (
            type(self.stage_timeout_seconds) not in (int, float)
            or isinstance(self.stage_timeout_seconds, bool)
            or not math.isfinite(float(self.stage_timeout_seconds))
            or self.stage_timeout_seconds <= 0
        ):
            raise HostSkillError("INVALID_STAGE_TIMEOUT")
        for field_name in (
            "request_stage_budget",
            "max_stdout_bytes",
            "max_stderr_bytes",
            "max_handoff_bytes",
        ):
            value = getattr(self, field_name)
            if type(value) is not int or value <= 0:
                raise HostSkillError("INVALID_" + field_name.upper())
        if self.request_stage_budget < 3:
            raise HostSkillError("REQUEST_STAGE_BUDGET_TOO_SMALL")
        if self.days != 7 or type(self.days) is not int:
            raise HostSkillError("DAYS_MUST_BE_SEVEN")
        if self.current_only is not True or self.no_as_of is not True:
            raise HostSkillError("CURRENT_ONLY_POLICY_REQUIRED")
        if self.handoff_ttl_seconds != 3600 or type(self.handoff_ttl_seconds) is not int:
            raise HostSkillError("HANDOFF_TTL_MUST_BE_3600")
        if self.final_output_path is not None:
            final_output = _as_absolute_path(
                self.final_output_path, "INVALID_FINAL_OUTPUT_PATH"
            )
            if final_output.exists() and not final_output.is_file():
                raise HostSkillError("INVALID_FINAL_OUTPUT_PATH")
            object.__setattr__(self, "final_output_path", final_output)


@dataclass(frozen=True)
class NominationInput:
    """One complete native nomination row passed to the injected model."""

    id: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class AngleInput:
    """One complete native pending angle-input row passed to the model."""

    id: str
    payload: Mapping[str, str]


@dataclass(frozen=True)
class Judgment:
    """The only editorial fields accepted from the injected model."""

    id: str
    name: str
    junk: bool
    worthiness: int


@dataclass(frozen=True)
class StageReceipt:
    phase: str
    returncode: int
    stdout_bytes: int
    stderr_bytes: int
    stdout_sha256: str
    stderr_sha256: str


@dataclass(frozen=True)
class HostSkillResult:
    status: str
    bundle_id: Optional[str]
    nominations: Tuple[NominationInput, ...]
    survivor_ids: Tuple[str, ...]
    stages: Tuple[StageReceipt, ...]
    remaining_request_budget: int
    provider_native: Optional["ProviderNativeOutput"] = None


@dataclass(frozen=True, repr=False)
class ProviderNativeOutput:
    """Opaque bounded raw native DiscoveryReport output.

    ``raw_json`` is the installed skill's own ``schema.to_dict(report)``
    payload.  It retains native source/status/evidence and publication-angle
    fields without translating them into Event Intelligence or Hunter types.
    Native editorial fields are explicitly provisional for downstream use.
    """

    raw_json: bytes
    persisted_path: Optional[Path]
    native_editorial_provisional: bool = True

    def __post_init__(self) -> None:
        if type(self.raw_json) is not bytes or not self.raw_json:
            raise HostSkillError("FINAL_OUTPUT_MALFORMED")
        if self.persisted_path is not None:
            if not isinstance(self.persisted_path, Path) or not self.persisted_path.is_absolute():
                raise HostSkillError("INVALID_FINAL_OUTPUT_PATH")
        if self.native_editorial_provisional is not True:
            raise HostSkillError("NATIVE_EDITORIAL_MUST_BE_PROVISIONAL")

    def __repr__(self) -> str:
        return (
            "ProviderNativeOutput(bytes=<redacted>, persisted_path={!r}, "
            "native_editorial_provisional=True)"
        ).format(str(self.persisted_path) if self.persisted_path is not None else None)


ModelCallback = Callable[[str, Tuple[Any, ...]], Any]
StageRunner = Callable[[StageRequest], StageExecution]


def compute_skill_content_sha256(skill_path: Union[str, os.PathLike]) -> str:
    """Hash the fixed Skill protocol/executable set in deterministic order."""

    root = _as_absolute_path(skill_path, "INVALID_SKILL_PIN_PATH")
    try:
        candidates = [root / "SKILL.md"]
        scripts_root = root / "scripts"
        for file_path in scripts_root.rglob("*"):
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(root)
            parts = {part.lower() for part in relative.parts}
            lower_name = file_path.name.lower()
            if parts.intersection(_PIN_EXCLUDED_DIRS):
                continue
            if any(part in lower_name for part in _PIN_EXCLUDED_NAME_PARTS):
                continue
            if file_path.suffix.lower() in _PINNED_SCRIPT_SUFFIXES:
                candidates.append(file_path)
    except (OSError, RuntimeError, ValueError):
        raise HostSkillError("SKILL_PIN_UNAVAILABLE") from None

    relative_files = sorted(
        {file_path.relative_to(root).as_posix(): file_path for file_path in candidates}.items()
    )
    if not relative_files:
        raise HostSkillError("SKILL_PIN_UNAVAILABLE")
    digest = hashlib.sha256()
    for relative_name, file_path in relative_files:
        try:
            with file_path.open("rb") as stream:
                digest.update(relative_name.encode("utf-8"))
                digest.update(b"\0")
                while True:
                    chunk = stream.read(1024 * 64)
                    if not chunk:
                        break
                    digest.update(chunk)
        except (OSError, ValueError):
            raise HostSkillError("SKILL_PIN_UNAVAILABLE") from None
    return digest.hexdigest()


def _verify_skill_pin(pin: Last30DaysSkillPin) -> Path:
    try:
        root = pin.path.resolve(strict=True)
        skill_file = root / "SKILL.md"
        script_file = root / "scripts" / "last30days.py"
        handoff_file = root / "scripts" / "lib" / "discovery_handoff.py"
        env_file = root / "scripts" / "lib" / "env.py"
        if not root.is_dir() or not all(
            (root / relative_name).is_file() for relative_name in _PIN_REQUIRED_FILES
        ):
            raise OSError
        version = None
        for line in skill_file.read_text(encoding="utf-8").splitlines():
            match = _VERSION_LINE.fullmatch(line)
            if match:
                version = next(value for value in match.groups() if value is not None)
                break
        if version != pin.version:
            raise HostSkillError("SKILL_VERSION_MISMATCH")
        if compute_skill_content_sha256(root) != pin.content_sha256:
            raise HostSkillError("SKILL_CONTENT_MISMATCH")
    except HostSkillError:
        raise
    except (OSError, UnicodeError, StopIteration):
        raise HostSkillError("SKILL_PIN_UNAVAILABLE") from None
    return root


def _utc_now() -> _datetime.datetime:
    return _datetime.datetime.now(_datetime.timezone.utc)


def _timestamp_is_fresh(value: object, now: _datetime.datetime, ttl: int) -> bool:
    if type(value) is not str or not value:
        return False
    try:
        timestamp = _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=_datetime.timezone.utc)
    return (now - timestamp.astimezone(_datetime.timezone.utc)).total_seconds() <= ttl


def _read_json(path: Path, max_bytes: int, code: str) -> Mapping[str, Any]:
    try:
        with path.open("rb") as stream:
            raw = stream.read(max_bytes + 1)
    except (OSError, UnicodeError):
        raise HostSkillError(code) from None
    if len(raw) > max_bytes:
        raise HostSkillError("HANDOFF_TOO_LARGE")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, TypeError):
        raise HostSkillError("HANDOFF_MALFORMED") from None
    if not isinstance(payload, dict):
        raise HostSkillError("HANDOFF_MALFORMED")
    return payload


def _require_native_report_shape(payload: Mapping[str, Any], code: str) -> None:
    """Check the closed native DiscoveryReport shape without interpreting it."""

    required = {
        "domain",
        "range_from",
        "range_to",
        "generated_at",
        "plan",
        "topics",
        "source_status",
        "warnings",
        "outcome",
    }
    if not required.issubset(payload) or set(payload) - required - {"weak_signal"}:
        raise HostSkillError(code)
    if any(type(payload.get(name)) is not str for name in (
        "domain", "range_from", "range_to", "generated_at", "outcome"
    )):
        raise HostSkillError(code)
    plan = payload.get("plan")
    if (
        type(plan) is not dict
        or type(plan.get("domain")) is not str
        or type(plan.get("subreddits")) is not list
        or type(plan.get("sources")) is not list
        or any(type(value) is not str for value in plan["subreddits"])
        or any(type(value) is not str for value in plan["sources"])
        or set(plan) - {"domain", "category", "subreddits", "sources"}
    ):
        raise HostSkillError(code)
    topics = payload.get("topics")
    if type(topics) is not list:
        raise HostSkillError(code)
    topic_required = {
        "rank",
        "name",
        "why_spiking",
        "momentum",
        "velocity_score",
        "sources",
        "engagement_by_source",
        "command",
        "evidence_urls",
        "corroboration_count",
    }
    for topic in topics:
        if (
            type(topic) is not dict
            or not topic_required.issubset(topic)
            or set(topic) - topic_required - {
                "top_comment", "podcast_angle", "x_article_angle",
                "previously_surfaced_count", "last_surfaced", "covered",
            }
            or type(topic.get("rank")) is not int
            or type(topic.get("name")) is not str
            or type(topic.get("sources")) is not list
            or type(topic.get("evidence_urls")) is not list
            or type(topic.get("engagement_by_source")) is not dict
            or any(type(value) is not str for value in topic["sources"] + topic["evidence_urls"])
            or any(type(topic.get(key)) is not str for key in (
                "why_spiking", "momentum", "command"
            ))
            or type(topic.get("velocity_score")) not in (int, float)
            or not math.isfinite(topic["velocity_score"])
            or type(topic.get("corroboration_count")) is not int
        ):
            raise HostSkillError(code)
    if type(payload.get("source_status")) is not dict or type(payload.get("warnings")) is not list:
        raise HostSkillError(code)


def _validate_native_bundle(payload: Mapping[str, Any]) -> None:
    if (
        payload.get("schema_version") != _NATIVE_NOMINATIONS_SCHEMA_VERSION
        or payload.get("kind") != _NATIVE_NOMINATIONS_KIND
        or type(payload.get("bundle_id")) is not str
        or not payload["bundle_id"].strip()
        or type(payload.get("generated_at")) is not str
        or type(payload.get("from_date")) is not str
        or type(payload.get("to_date")) is not str
        or type(payload.get("domain")) is not str
        or type(payload.get("tier")) is not str
        or type(payload.get("context")) is not dict
        or type(payload.get("nominations")) is not list
    ):
        raise HostSkillError("BUNDLE_MALFORMED")
    context = payload["context"]
    if (
        not {"enrichment_source_boundary", "requested_sources", "lookback_days"}.issubset(context)
        or type(context.get("lookback_days")) is not int
        or context["lookback_days"] < 0
        or (
            context.get("enrichment_source_boundary") is not None
            and type(context.get("enrichment_source_boundary")) is not list
        )
        or (
            context.get("requested_sources") is not None
            and type(context.get("requested_sources")) is not list
        )
    ):
        raise HostSkillError("BUNDLE_MALFORMED")
    if type(payload.get("mock", False)) is not bool:
        raise HostSkillError("BUNDLE_MALFORMED")
    if type(payload.get("source_status", {})) is not dict:
        raise HostSkillError("BUNDLE_MALFORMED")
    for row in payload["nominations"]:
        if type(row) is not dict or not {
            "id", "cluster_id", "heuristic_name", "heuristic_junk", "sources",
            "engagement_by_source", "nomination",
        }.issubset(row):
            raise HostSkillError("BUNDLE_MALFORMED")
        nomination = row["nomination"]
        if (
            type(row["id"]) is not str
            or not row["id"].strip()
            or type(row["cluster_id"]) is not str
            or type(row["heuristic_name"]) is not str
            or type(row["heuristic_junk"]) is not bool
            or type(row["sources"]) is not list
            or any(type(source) is not str for source in row["sources"])
            or type(row["engagement_by_source"]) is not dict
            or type(nomination) is not dict
            or not {"name", "seed_score", "summary", "junk_shape", "items"}.issubset(nomination)
            or type(nomination["name"]) is not str
            or type(nomination["summary"]) is not str
            or type(nomination["junk_shape"]) is not bool
            or type(nomination["items"]) is not list
        ):
            raise HostSkillError("BUNDLE_MALFORMED")
        for item in nomination["items"]:
            if (
                type(item) is not dict
                or not {"item_id", "source", "title"}.issubset(item)
                or type(item["item_id"]) is not str
                or type(item["source"]) is not str
                or type(item["title"]) is not str
            ):
                raise HostSkillError("BUNDLE_MALFORMED")


def _validate_native_pending(payload: Mapping[str, Any]) -> None:
    if (
        payload.get("schema_version") != _NATIVE_PENDING_SCHEMA_VERSION
        or payload.get("kind") != _NATIVE_PENDING_KIND
        or type(payload.get("bundle_id")) is not str
        or not payload["bundle_id"].strip()
        or type(payload.get("generated_at")) is not str
        or type(payload.get("run_ref")) is not str
        or not payload["run_ref"].strip()
        or type(payload.get("report")) is not dict
        or type(payload.get("angle_inputs")) is not dict
        or type(payload.get("mock", False)) is not bool
    ):
        raise HostSkillError("PENDING_MALFORMED")
    _require_native_report_shape(payload["report"], "PENDING_MALFORMED")
    for nomination_id, value in payload["angle_inputs"].items():
        if type(nomination_id) is not str or not nomination_id.strip() or type(value) is not dict:
            raise HostSkillError("PENDING_MALFORMED")
        if any(type(key) is not str or type(item) is not str for key, item in value.items()):
            raise HostSkillError("PENDING_MALFORMED")


def _parse_bundle(
    path: Path,
    config: HostSkillConfig,
    now: _datetime.datetime,
) -> Tuple[Optional[str], Tuple[NominationInput, ...]]:
    payload = _read_json(path, config.max_handoff_bytes, "BUNDLE_UNREADABLE")
    _validate_native_bundle(payload)
    bundle_id = payload.get("bundle_id")
    generated_at = payload.get("generated_at")
    rows = payload.get("nominations")
    if not _timestamp_is_fresh(generated_at, now, config.handoff_ttl_seconds):
        raise HostSkillError("BUNDLE_STALE", phase="nominate")
    if not rows:
        # Native leg 1 omits the bundle entirely when the sweep is empty.
        raise HostSkillError("BUNDLE_MALFORMED")
    nominations = []
    seen = set()
    for row in rows:
        row_id = row["id"]
        if row_id in seen:
            raise HostSkillError("BUNDLE_DUPLICATE_ID")
        seen.add(row_id)
        nominations.append(NominationInput(id=row_id, payload=dict(row)))
    return bundle_id, tuple(nominations)


def _parse_pending(
    path: Path,
    config: HostSkillConfig,
    now: _datetime.datetime,
    bundle_id: str,
    nomination_ids: Sequence[str],
) -> Tuple[AngleInput, ...]:
    payload = _read_json(path, config.max_handoff_bytes, "PENDING_UNREADABLE")
    _validate_native_pending(payload)
    if payload.get("bundle_id") != bundle_id:
        raise HostSkillError("PENDING_BUNDLE_MISMATCH", phase="resume")
    if not _timestamp_is_fresh(
        payload.get("generated_at"), now, config.handoff_ttl_seconds
    ):
        raise HostSkillError("PENDING_MALFORMED_OR_STALE", phase="resume")
    known = set(nomination_ids)
    inputs = []
    for row_id, value in payload["angle_inputs"].items():
        if row_id not in known:
            raise HostSkillError("PENDING_MALFORMED")
        inputs.append(AngleInput(id=row_id, payload=dict(value)))
    return tuple(inputs)


def _read_final_native(path: Path, config: HostSkillConfig) -> bytes:
    try:
        with path.open("rb") as stream:
            raw = stream.read(config.max_handoff_bytes + 1)
    except (OSError, UnicodeError):
        raise HostSkillError("FINAL_OUTPUT_UNREADABLE", phase="finalize") from None
    if len(raw) > config.max_handoff_bytes:
        raise HostSkillError("FINAL_OUTPUT_TOO_LARGE", phase="finalize")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, TypeError):
        raise HostSkillError("FINAL_OUTPUT_MALFORMED", phase="finalize") from None
    if not isinstance(payload, dict):
        raise HostSkillError("FINAL_OUTPUT_MALFORMED", phase="finalize")
    _require_native_report_shape(payload, "FINAL_OUTPUT_MALFORMED")
    return raw


def _model_rows(output: Any, key: str) -> Sequence[Any]:
    if isinstance(output, Mapping):
        rows = output.get(key)
    else:
        rows = output
    if not isinstance(rows, (list, tuple)):
        raise HostSkillError("MODEL_OUTPUT_INVALID")
    return rows


def _parse_judgment(row: Any) -> Judgment:
    if isinstance(row, Judgment):
        value = row
    elif isinstance(row, Mapping):
        if set(row) != {"id", "name", "junk", "worthiness"}:
            raise HostSkillError("MODEL_OUTPUT_INVALID")
        value = Judgment(
            id=row.get("id"),
            name=row.get("name"),
            junk=row.get("junk"),
            worthiness=row.get("worthiness"),
        )
    else:
        raise HostSkillError("MODEL_OUTPUT_INVALID")
    _require_text(value.id, "MODEL_OUTPUT_INVALID")
    _require_text(value.name, "MODEL_OUTPUT_INVALID", max_chars=_MAX_NAME_CHARS)
    if type(value.junk) is not bool or type(value.worthiness) is not int:
        raise HostSkillError("MODEL_OUTPUT_INVALID")
    if not 0 <= value.worthiness <= 100:
        raise HostSkillError("MODEL_OUTPUT_INVALID")
    return value


def _parse_angles(row: Any) -> Mapping[str, str]:
    if not isinstance(row, Mapping) or set(row) != {"id", "podcast", "x_article"}:
        raise HostSkillError("MODEL_OUTPUT_INVALID")
    row_id = row.get("id")
    podcast = row.get("podcast")
    x_article = row.get("x_article")
    _require_text(row_id, "MODEL_OUTPUT_INVALID")
    for value in (podcast, x_article):
        if type(value) is not str or value != value.strip():
            raise HostSkillError("MODEL_OUTPUT_INVALID")
        if len(value) > _MAX_ANGLE_CHARS or any(
            ord(character) < 32 or ord(character) == 127 for character in value
        ):
            raise HostSkillError("MODEL_OUTPUT_INVALID")
    if not podcast and not x_article:
        raise HostSkillError("MODEL_OUTPUT_INVALID")
    return {"id": row_id, "podcast": podcast, "x_article": x_article}


def _validated_judgments(
    output: Any,
    nomination_ids: Sequence[str],
) -> Tuple[Judgment, ...]:
    rows = _model_rows(output, "judgments")
    expected = set(nomination_ids)
    parsed = [_parse_judgment(row) for row in rows]
    ids = [row.id for row in parsed]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise HostSkillError("MODEL_JUDGMENT_COVERAGE")
    by_id = {row.id: row for row in parsed}
    return tuple(by_id[row_id] for row_id in nomination_ids)


def _validated_angles(
    output: Any,
    survivor_ids: Sequence[str],
) -> Tuple[Mapping[str, str], ...]:
    rows = _model_rows(output, "angles")
    expected = set(survivor_ids)
    parsed = [_parse_angles(row) for row in rows]
    ids = [row["id"] for row in parsed]
    if len(ids) != len(set(ids)) or set(ids) != expected:
        raise HostSkillError("MODEL_ANGLE_COVERAGE")
    by_id = {row["id"]: row for row in parsed}
    return tuple(by_id[row_id] for row_id in survivor_ids)


def _write_json(path: Path, payload: Mapping[str, Any], max_bytes: int) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > max_bytes:
        raise HostSkillError("HANDOFF_TOO_LARGE")
    try:
        path.write_bytes(raw)
    except OSError:
        raise HostSkillError("HANDOFF_WRITE_FAILED") from None


def _stage_argv(
    phase: str,
    config: HostSkillConfig,
    skill_script: Path,
    state_dir: Path,
    domain: Optional[str],
    handoff_file: Optional[Path],
    output_file: Optional[Path] = None,
) -> Tuple[str, ...]:
    common = (
        "--days",
        "7",
        "--search",
        ",".join(config.source_allowlist),
        "--save-dir",
        str(state_dir),
    )
    if phase == "nominate":
        args = ["--discover"]
        if domain is not None:
            args.append(domain)
        args.append("--nominate-only")
        args.extend(common)
    elif phase == "resume":
        assert handoff_file is not None
        args = ["--discover", "--judgments", str(handoff_file)]
        args.extend(common)
    elif phase == "finalize":
        if handoff_file is None or output_file is None:
            raise HostSkillError("INVALID_STAGE")
        args = [
            "--discover",
            "--finalize",
            "--angles",
            str(handoff_file),
            "--emit",
            "json",
            "--json-profile",
            "raw",
            "--output",
            str(output_file),
        ]
        args.extend(common)
    else:
        raise HostSkillError("INVALID_STAGE")
    if "--as-of" in args or "--lookback-days" in args:
        raise HostSkillError("CURRENT_ONLY_POLICY_VIOLATION")
    return tuple([str(skill_script)] + args)


def _receipt(phase: str, execution: StageExecution) -> StageReceipt:
    return StageReceipt(
        phase=phase,
        returncode=execution.returncode,
        stdout_bytes=execution.stdout_bytes,
        stderr_bytes=execution.stderr_bytes,
        stdout_sha256=execution.stdout_sha256,
        stderr_sha256=execution.stderr_sha256,
    )


def run_last30days_discovery(
    config: HostSkillConfig,
    domain: Optional[str],
    model_callback: ModelCallback,
    *,
    stage_runner: Optional[StageRunner] = None,
    clock: Optional[Callable[[], _datetime.datetime]] = None,
) -> HostSkillResult:
    """Run the bounded three-leg native protocol with synthetic seams."""

    if not callable(model_callback):
        raise HostSkillError("MODEL_CALLBACK_REQUIRED")
    if domain is not None:
        _require_text(domain, "INVALID_DOMAIN", max_chars=256)
        if domain.startswith("-"):
            raise HostSkillError("INVALID_DOMAIN")
    root = _verify_skill_pin(config.skill_pin)
    skill_script = root / "scripts" / "last30days.py"
    runner = stage_runner or run_stage
    now_fn = clock or _utc_now
    remaining_budget = config.request_stage_budget
    receipts = []

    with tempfile.TemporaryDirectory(prefix="convexity-hunter-last30days-") as raw_dir:
        state_dir = Path(raw_dir).resolve()
        # Rebuild with the actual isolated directory, never the model/domain.
        try:
            child_environment = build_child_environment(
                config.permitted_source_envs, state_dir
            )
        except HostSkillLaunchError as exc:
            raise HostSkillError(exc.code) from None

        def run_one(phase: str, argv: Tuple[str, ...]) -> StageReceipt:
            nonlocal remaining_budget
            if remaining_budget <= 0:
                raise HostSkillError("REQUEST_STAGE_BUDGET_EXHAUSTED", phase=phase)
            # Reservation happens before the runner and is intentionally not
            # refunded on any launcher/skill/model failure.
            remaining_budget -= 1
            request = StageRequest(
                phase=phase,
                argv=argv,
                skill_path=skill_script,
                python_executable=Path(config.python_executable),
                cwd=state_dir,
                environment=child_environment,
                timeout_seconds=float(config.stage_timeout_seconds),
                max_stdout_bytes=config.max_stdout_bytes,
                max_stderr_bytes=config.max_stderr_bytes,
            )
            try:
                execution = runner(request)
            except HostSkillLaunchError as exc:
                raise HostSkillError(exc.code, phase=phase) from None
            except Exception:
                raise HostSkillError("STAGE_RUNNER_FAILED", phase=phase) from None
            if not isinstance(execution, StageExecution):
                raise HostSkillError("STAGE_RUNNER_INVALID", phase=phase)
            receipt = _receipt(phase, execution)
            receipts.append(receipt)
            if execution.returncode != 0:
                code = "SKILL_CONTRACT_FAILED" if execution.returncode == 2 else "SKILL_STAGE_FAILED"
                raise HostSkillError(code, phase=phase, exit_code=execution.returncode)
            return receipt

        bundle_path = state_dir / _BUNDLE_FILENAME
        run_one(
            "nominate",
            _stage_argv("nominate", config, skill_script, state_dir, domain, None),
        )
        if not bundle_path.exists():
            return HostSkillResult(
                status="empty",
                bundle_id=None,
                nominations=(),
                survivor_ids=(),
                stages=tuple(receipts),
                remaining_request_budget=remaining_budget,
            )

        bundle_id, nominations = _parse_bundle(bundle_path, config, now_fn())
        assert bundle_id is not None
        if not nominations:
            return HostSkillResult(
                status="empty",
                bundle_id=bundle_id,
                nominations=(),
                survivor_ids=(),
                stages=tuple(receipts),
                remaining_request_budget=remaining_budget,
            )

        try:
            judgments_output = model_callback("judgments", nominations)
        except HostSkillError:
            raise
        except Exception:
            raise HostSkillError("MODEL_CALLBACK_FAILED", phase="judgments") from None
        judgments = _validated_judgments(
            judgments_output, tuple(nomination.id for nomination in nominations)
        )
        judgments_path = state_dir / _JUDGMENTS_FILENAME
        _write_json(
            judgments_path,
            {
                "bundle_id": bundle_id,
                "judgments": [
                    {
                        "id": judgment.id,
                        "name": judgment.name,
                        "junk": judgment.junk,
                        "worthiness": judgment.worthiness,
                    }
                    for judgment in judgments
                ],
            },
            config.max_handoff_bytes,
        )

        pending_path = state_dir / _PENDING_FILENAME
        run_one(
            "resume",
            _stage_argv("resume", config, skill_script, state_dir, None, judgments_path),
        )
        if not pending_path.exists():
            raise HostSkillError("PENDING_MISSING", phase="resume")
        angle_inputs = _parse_pending(
            pending_path,
            config,
            now_fn(),
            bundle_id,
            tuple(nomination.id for nomination in nominations),
        )
        survivor_ids = tuple(item.id for item in angle_inputs)
        if not survivor_ids:
            return HostSkillResult(
                status="empty",
                bundle_id=bundle_id,
                nominations=nominations,
                survivor_ids=(),
                stages=tuple(receipts),
                remaining_request_budget=remaining_budget,
            )

        try:
            angles_output = model_callback("angles", angle_inputs)
        except HostSkillError:
            raise
        except Exception:
            raise HostSkillError("MODEL_CALLBACK_FAILED", phase="angles") from None
        angles = _validated_angles(angles_output, survivor_ids)
        angles_path = state_dir / _ANGLES_FILENAME
        _write_json(
            angles_path,
            {"bundle_id": bundle_id, "angles": list(angles)},
            config.max_handoff_bytes,
        )
        # Native writes only inside this run's isolated directory. Persistence
        # occurs after validation, exclusively, so an existing file is safe.
        final_output_path = state_dir / _FINAL_NATIVE_FILENAME
        run_one(
            "finalize",
            _stage_argv(
                "finalize",
                config,
                skill_script,
                state_dir,
                None,
                angles_path,
                final_output_path,
            ),
        )
        native_raw = _read_final_native(final_output_path, config)
        if config.final_output_path is not None:
            try:
                with Path(config.final_output_path).open("xb") as stream:
                    stream.write(native_raw)
            except OSError:
                raise HostSkillError("FINAL_OUTPUT_PERSIST_FAILED", phase="finalize") from None
        return HostSkillResult(
            status="complete",
            bundle_id=bundle_id,
            nominations=nominations,
            survivor_ids=survivor_ids,
            stages=tuple(receipts),
            remaining_request_budget=remaining_budget,
            provider_native=ProviderNativeOutput(
                raw_json=native_raw,
                persisted_path=(
                    Path(config.final_output_path)
                    if config.final_output_path is not None
                    else None
                ),
            ),
        )
