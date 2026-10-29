"""Immutable Host-owned audit of a bounded source extraction partition.

This DTO contains only URL identities, exact body digests, and one fixed
provider-failure code.  It is deliberately independent of Core, World, and
Store types.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from typing import Tuple
from urllib.parse import parse_qsl, unquote, urlsplit


_SCHEMA_VERSION = "host-source-coverage-v0.1"
_MAX_REQUESTED_URLS = 5
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SENSITIVE_QUERY_NAMES = frozenset(
    {
        "api_key", "apikey", "authorization", "auth", "client_secret",
        "cookie", "credential", "jwt", "password", "passwd",
        "private_key", "refresh_token", "secret", "session", "signature",
        "sig", "token", "access_token",
    }
)
_LOCAL_HOST_NAMES = frozenset(
    {"localhost", "localhost.localdomain", "metadata", "metadata.google.internal"}
)
_ROOT_KEYS = frozenset(
    {
        "schema_version", "host_run_id", "unit_id", "run_id",
        "canonical_input_hash", "status", "entries",
    }
)
_BODY_ENTRY_KEYS = frozenset(
    {"source_id", "locator", "status", "body_sha256"}
)
_FAILED_ENTRY_KEYS = frozenset(
    {"source_id", "locator", "status", "reason_code"}
)


def _bounded_text(value: object, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError("{} must be a canonical nonempty string".format(label))
    value.encode("utf-8", errors="strict")
    return value


def _is_private_host(hostname: str) -> bool:
    normalized = hostname.casefold().rstrip(".")
    if normalized in _LOCAL_HOST_NAMES or normalized.endswith(
        (".localhost", ".local", ".internal")
    ):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _public_locator(value: object) -> str:
    locator = _bounded_text(value, "locator")
    if any(ord(character) < 32 or ord(character) == 127 for character in locator):
        raise ValueError("locator contains a control character")
    if "\\" in locator:
        raise ValueError("locator contains a backslash")
    try:
        parsed = urlsplit(locator)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("locator is not a public URL") from exc
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValueError("locator is not a public URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("locator must not contain user information")
    if hostname is None or not hostname or _is_private_host(hostname):
        raise ValueError("locator must identify a public host")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("locator has an invalid port")
    if parsed.fragment:
        raise ValueError("locator must not contain a fragment")
    try:
        query_pairs = parse_qsl(
            unquote(parsed.query), keep_blank_values=True, strict_parsing=False
        )
    except ValueError as exc:
        raise ValueError("locator has an invalid query") from exc
    for key, _ in query_pairs:
        if key.casefold().replace("-", "_") in _SENSITIVE_QUERY_NAMES:
            raise ValueError("locator contains a sensitive query parameter")
    return locator


def _url_source_id(locator: str) -> str:
    return "url:" + hashlib.sha256(locator.encode("utf-8", errors="strict")).hexdigest()


@dataclass(frozen=True)
class _CoverageEntry:
    source_id: str
    locator: str
    status: str
    digest_or_reason: str

    def to_dict(self) -> dict:
        if self.status == "BODY_AVAILABLE":
            return {
                "source_id": self.source_id,
                "locator": self.locator,
                "status": self.status,
                "body_sha256": self.digest_or_reason,
            }
        return {
            "source_id": self.source_id,
            "locator": self.locator,
            "status": self.status,
            "reason_code": self.digest_or_reason,
        }


@dataclass(frozen=True)
class HostSourceCoverageAudit:
    """A complete, immutable and canonical extraction-outcome partition."""

    schema_version: str
    host_run_id: str
    unit_id: str
    run_id: str
    canonical_input_hash: str
    status: str
    entries: Tuple[_CoverageEntry, ...]

    def __post_init__(self) -> None:
        if type(self.schema_version) is not str or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("unsupported source coverage schema_version")
        _bounded_text(self.host_run_id, "host_run_id")
        _bounded_text(self.unit_id, "unit_id")
        _bounded_text(self.run_id, "run_id")
        if type(self.canonical_input_hash) is not str or _SHA256.fullmatch(
            self.canonical_input_hash
        ) is None:
            raise ValueError("canonical_input_hash must be lowercase SHA-256")
        if type(self.entries) is not tuple or not 1 <= len(self.entries) <= _MAX_REQUESTED_URLS:
            raise ValueError("entries must be a tuple of one to five outcomes")

        seen_ids = set()
        seen_locators = set()
        success_count = 0
        failed_count = 0
        for entry in self.entries:
            if type(entry) is not _CoverageEntry:
                raise TypeError("entries must contain immutable coverage rows")
            if type(entry.status) is not str:
                raise TypeError("coverage row status must have exact type str")
            locator = _public_locator(entry.locator)
            if type(entry.source_id) is not str or entry.source_id != _url_source_id(locator):
                raise ValueError("source_id must match the exact URL-derived identity")
            if entry.source_id in seen_ids or locator in seen_locators:
                raise ValueError("coverage rows must have unique requested URLs")
            seen_ids.add(entry.source_id)
            seen_locators.add(locator)
            if entry.status == "BODY_AVAILABLE":
                if type(entry.digest_or_reason) is not str or _SHA256.fullmatch(
                    entry.digest_or_reason
                ) is None:
                    raise ValueError("body_sha256 must be lowercase SHA-256")
                success_count += 1
            elif entry.status == "FAILED":
                if (
                    type(entry.digest_or_reason) is not str
                    or entry.digest_or_reason != "PROVIDER_REPORTED_FAILURE"
                ):
                    raise ValueError("failed rows require the fixed provider reason code")
                failed_count += 1
            else:
                raise ValueError("coverage row status is unsupported")

        expected_status = (
            "EMPTY" if success_count == 0
            else "COMPLETE" if failed_count == 0
            else "PARTIAL"
        )
        if type(self.status) is not str or self.status != expected_status:
            raise ValueError("status does not match the complete outcome partition")

    @classmethod
    def from_dict(cls, payload: object) -> "HostSourceCoverageAudit":
        """Validate the exact frozen payload shape and return an immutable DTO."""
        if type(payload) is not dict or frozenset(payload) != _ROOT_KEYS:
            raise ValueError("source coverage payload has an invalid root shape")
        if (
            type(payload["schema_version"]) is not str
            or payload["schema_version"] != _SCHEMA_VERSION
        ):
            raise ValueError("unsupported source coverage schema_version")
        raw_entries = payload["entries"]
        if type(raw_entries) is not list or not 1 <= len(raw_entries) <= _MAX_REQUESTED_URLS:
            raise ValueError("entries must contain one to five outcomes")
        entries = []
        for row in raw_entries:
            if type(row) is not dict:
                raise ValueError("coverage entry must be an object")
            status = row.get("status")
            if type(status) is not str:
                raise ValueError("coverage entry status must have exact type str")
            expected_keys = (
                _BODY_ENTRY_KEYS if status == "BODY_AVAILABLE"
                else _FAILED_ENTRY_KEYS if status == "FAILED"
                else frozenset()
            )
            if not expected_keys or frozenset(row) != expected_keys:
                raise ValueError("coverage entry has an invalid variant shape")
            locator = _public_locator(row["locator"])
            source_id = row["source_id"]
            if type(source_id) is not str or source_id != _url_source_id(locator):
                raise ValueError("source_id must match the exact URL-derived identity")
            detail = row["body_sha256"] if status == "BODY_AVAILABLE" else row["reason_code"]
            if type(detail) is not str:
                raise ValueError("coverage row value must have exact type str")
            entries.append(_CoverageEntry(source_id, locator, status, detail))
        return cls(
            schema_version=payload["schema_version"],
            host_run_id=payload["host_run_id"],
            unit_id=payload["unit_id"],
            run_id=payload["run_id"],
            canonical_input_hash=payload["canonical_input_hash"],
            status=payload["status"],
            entries=tuple(entries),
        )

    def to_dict(self) -> dict:
        """Return a detached JSON-compatible representation."""
        return {
            "schema_version": self.schema_version,
            "host_run_id": self.host_run_id,
            "unit_id": self.unit_id,
            "run_id": self.run_id,
            "canonical_input_hash": self.canonical_input_hash,
            "status": self.status,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    @property
    def canonical_utf8(self) -> bytes:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_utf8).hexdigest()


__all__ = ("HostSourceCoverageAudit",)
