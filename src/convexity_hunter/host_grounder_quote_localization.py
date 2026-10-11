"""Strict v0.2 quote-only wire localization for the explicit Host route."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from typing import Mapping, Tuple

from .host_grounder_schema import (
    ProducerClosedShapeError,
    ProducerJsonFormatError,
    parse_model_output_envelope,
)
from .host_grounder_semantic import parse_semantic_verdict


_OUTPUT_TOP = frozenset(
    ("schema_version", "stage", "request_id", "claims", "hypotheses", "coverage", "field_bindings")
)
_OUTPUT_BINDING = frozenset(
    ("field_path", "source_id", "quote", "semantic_role", "status")
)
_VERDICT_TOP = frozenset(
    ("schema_version", "run_id", "envelope_hash", "source_body_hashes", "claims", "hypotheses", "field_bindings", "coverage")
)
_VERDICT_SECTIONS = ("claims", "hypotheses", "field_bindings", "coverage")
_WIRE_REF = frozenset(("source_id", "body_sha256", "quote"))


def _limit(value: object, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("{} must be a positive integer".format(name))
    return value


def _decode(raw: str, max_input_bytes: int) -> dict:
    if type(raw) is not str:
        raise ProducerJsonFormatError("producer JSON text is invalid")
    try:
        if len(raw.encode("utf-8", errors="strict")) > max_input_bytes:
            raise ValueError("wire content exceeds max_input_bytes")

        def pairs(items: list) -> dict:
            result = {}
            for key, value in items:
                if key in result:
                    raise ProducerJsonFormatError("producer JSON has duplicate keys")
                result[key] = value
            return result

        def reject_constant(token: str) -> None:
            raise ProducerJsonFormatError("producer JSON constant is invalid")

        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject_constant)
    except (UnicodeEncodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ProducerJsonFormatError("producer JSON syntax is invalid") from exc
    if type(value) is not dict:
        raise ProducerClosedShapeError("producer JSON root shape is invalid")
    return value


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8", errors="strict")


def _wire_string(value: object, label: str, max_string_bytes: int) -> str:
    if type(value) is not str or not value:
        raise ValueError("{} must be a nonempty string".format(label))
    if len(value.encode("utf-8", errors="strict")) > max_string_bytes:
        raise ValueError("{} exceeds max_string_bytes".format(label))
    return value


def _registered_body(source_bodies: Mapping[str, object], source_id: object, body_sha256: object, max_string_bytes: int) -> str:
    source_id = _wire_string(source_id, "source_id", max_string_bytes)
    source = source_bodies.get(source_id)
    body = getattr(source, "body", None)
    registered_hash = getattr(source, "body_sha256", None)
    if type(body) is not str or type(registered_hash) is not str:
        raise ValueError("source is not registered")
    body_bytes = body.encode("utf-8", errors="strict")
    if hashlib.sha256(body_bytes).hexdigest() != registered_hash:
        raise ValueError("source body hash mismatch")
    if body_sha256 is not None and body_sha256 != registered_hash:
        raise ValueError("source body hash mismatch")
    return body


def _unique_location(body: str, quote: object, max_string_bytes: int) -> Tuple[int, int]:
    quote = _wire_string(quote, "quote", max_string_bytes)
    positions = []
    start = 0
    while True:
        found = body.find(quote, start)
        if found < 0:
            break
        positions.append(found)
        if len(positions) > 1:
            raise ValueError("quote is ambiguous")
        start = found + 1  # Count overlapping occurrences.
    if not positions:
        raise ValueError("quote is missing")
    begin = positions[0]
    return begin, begin + len(quote)


def parse_grounder_output_v0_2(
    raw_json: str,
    max_input_bytes: int,
    *,
    max_string_bytes: int,
    max_array_items: int,
    source_bodies: Mapping[str, object],
) -> tuple:
    """Localize quote-only v0.2 bindings, then strictly parse internal v0.1."""
    max_input_bytes = _limit(max_input_bytes, "max_input_bytes")
    max_string_bytes = _limit(max_string_bytes, "max_string_bytes")
    max_array_items = _limit(max_array_items, "max_array_items")
    wire = _decode(raw_json, max_input_bytes)
    if set(wire) != _OUTPUT_TOP or wire.get("schema_version") != "grounder-output-v0.2":
        raise ValueError("producer wire DTO has an invalid closed shape or version")
    bindings = wire.get("field_bindings")
    if type(bindings) is not list or len(bindings) > max_array_items:
        raise ValueError("field_bindings must be a bounded array")

    internal = dict(wire)
    internal["schema_version"] = "grounder-output-v0.1"
    localized = []
    for raw_binding in bindings:
        if type(raw_binding) is not dict or set(raw_binding) != _OUTPUT_BINDING:
            raise ValueError("producer binding has an invalid closed wire shape")
        binding = dict(raw_binding)
        body = _registered_body(
            source_bodies, binding["source_id"], None, max_string_bytes
        )
        start, end = _unique_location(body, binding["quote"], max_string_bytes)
        binding["start"], binding["end"] = start, end
        localized.append(binding)
    internal["field_bindings"] = localized
    normalized = _canonical_bytes(internal)
    if len(normalized) > max_input_bytes:
        raise ValueError("normalized envelope exceeds max_input_bytes")
    parsed = parse_model_output_envelope(
        normalized.decode("utf-8"),
        max_input_bytes,
        max_string_bytes=max_string_bytes,
        max_array_items=max_array_items,
    )
    normalized = _canonical_bytes(parsed)
    if len(normalized) > max_input_bytes:
        raise ValueError("normalized envelope exceeds max_input_bytes")
    return parsed, normalized


def parse_semantic_verdict_v0_2(
    raw_json: str,
    max_input_bytes: int,
    *,
    max_string_bytes: int,
    max_array_items: int,
    source_bodies: Mapping[str, object],
) -> bytes:
    """Localize quote-only verifier refs, then strictly parse internal v0.1."""
    max_input_bytes = _limit(max_input_bytes, "max_input_bytes")
    max_string_bytes = _limit(max_string_bytes, "max_string_bytes")
    max_array_items = _limit(max_array_items, "max_array_items")
    wire = _decode(raw_json, max_input_bytes)
    if set(wire) != _VERDICT_TOP or wire.get("schema_version") != "semantic-verdict-v0.2":
        raise ValueError("verifier wire DTO has an invalid closed shape or version")

    internal = dict(wire)
    internal["schema_version"] = "semantic-verdict-v0.1"
    for section in _VERDICT_SECTIONS:
        records = internal[section]
        if type(records) is not list or len(records) > max_array_items:
            raise ValueError("{} must be a bounded array".format(section))
        for record in records:
            if type(record) is not dict or type(record.get("evidence_refs")) is not list:
                raise ValueError("verdict evidence_refs must be an array")
            refs = record["evidence_refs"]
            if len(refs) > max_array_items:
                raise ValueError("evidence_refs exceeds max_array_items")
            localized_refs = []
            for raw_ref in refs:
                if type(raw_ref) is not dict or set(raw_ref) != _WIRE_REF:
                    raise ValueError("verifier evidence ref has an invalid closed wire shape")
                ref = dict(raw_ref)
                body = _registered_body(
                    source_bodies,
                    ref["source_id"],
                    ref["body_sha256"],
                    max_string_bytes,
                )
                ref["start"], ref["end"] = _unique_location(
                    body, ref["quote"], max_string_bytes
                )
                localized_refs.append(ref)
            record["evidence_refs"] = localized_refs

    normalized = _canonical_bytes(internal)
    if len(normalized) > max_input_bytes:
        raise ValueError("normalized verdict exceeds max_input_bytes")
    parsed = parse_semantic_verdict(
        normalized.decode("utf-8"),
        max_input_bytes,
        max_string_bytes=max_string_bytes,
        max_array_items=max_array_items,
    )
    return _canonical_bytes(parsed)


@dataclass(frozen=True, repr=False)
class QuoteLocalizationAudit:
    """Immutable in-memory retention; payload bytes are never repr-logged."""

    producer_content_utf8: bytes = field(repr=False)
    normalized_envelope_utf8: bytes = field(repr=False)
    sidecar_utf8: bytes = field(repr=False)
    sidecar_sha256: str

    def __repr__(self) -> str:
        return "QuoteLocalizationAudit(sidecar_sha256={!r})".format(self.sidecar_sha256)


class QuoteLocalizationAuditHolder:
    """Caller-owned, single-run write-once retention for the explicit route."""

    __slots__ = (
        "_run_id", "_canonical_input_hash", "_state", "_producer_content_utf8",
        "_producer_content_sha256", "_audit", "_lock",
    )

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("audit holder fields are write-once")
        object.__setattr__(self, name, value)

    def __init__(self, *, run_id: str, canonical_input_hash: str) -> None:
        if type(run_id) is not str or not run_id:
            raise ValueError("run_id must be a nonempty string")
        if (
            type(canonical_input_hash) is not str
            or len(canonical_input_hash) != 64
            or any(character not in "0123456789abcdef" for character in canonical_input_hash)
        ):
            raise ValueError("canonical_input_hash must be lowercase SHA-256 hex")
        run_id.encode("utf-8", errors="strict")
        self._run_id = run_id
        self._canonical_input_hash = canonical_input_hash
        self._state = "new"
        self._producer_content_utf8 = None
        self._producer_content_sha256 = None
        self._audit = None
        self._lock = threading.Lock()

    @property
    def producer_content_utf8(self) -> bytes | None:
        return self._producer_content_utf8

    @property
    def producer_content_sha256(self) -> str | None:
        return self._producer_content_sha256

    @property
    def audit(self) -> QuoteLocalizationAudit | None:
        return self._audit

    @property
    def finalized(self) -> bool:
        return self._state == "finalized"

    def __repr__(self) -> str:
        return "QuoteLocalizationAuditHolder(state={!r})".format(self._state)

    def _begin(self, run_id: str, canonical_input_hash: str) -> None:
        with self._lock:
            if (
                self._state != "new"
                or run_id != self._run_id
                or canonical_input_hash != self._canonical_input_hash
            ):
                raise ValueError("audit holder is not fresh for this run")
            object.__setattr__(self, "_state", "started")

    def _capture_producer_content(self, content_utf8: bytes) -> None:
        with self._lock:
            if self._state != "started" or type(content_utf8) is not bytes:
                raise ValueError("audit holder cannot retain producer content")
            object.__setattr__(self, "_producer_content_utf8", content_utf8)
            object.__setattr__(
                self, "_producer_content_sha256", hashlib.sha256(content_utf8).hexdigest()
            )
            object.__setattr__(self, "_state", "producer_retained")

    def _finalize(
        self,
        normalized_envelope_utf8: bytes,
        source_bodies: Mapping[str, object],
        *,
        audit_schema_version: str,
        producer_prompt_version: str,
        validator_version: str,
    ) -> QuoteLocalizationAudit:
        with self._lock:
            if self._state != "producer_retained" or type(normalized_envelope_utf8) is not bytes:
                raise ValueError("audit holder cannot be finalized")
            audit = make_quote_localization_audit(
                run_id=self._run_id,
                canonical_input_hash=self._canonical_input_hash,
                source_bodies=source_bodies,
                producer_content_utf8=self._producer_content_utf8,
                normalized_envelope_utf8=normalized_envelope_utf8,
                audit_schema_version=audit_schema_version,
                producer_prompt_version=producer_prompt_version,
                validator_version=validator_version,
            )
            object.__setattr__(self, "_audit", audit)
            object.__setattr__(self, "_state", "finalized")
            return audit


def make_quote_localization_audit(
    *,
    run_id: str,
    canonical_input_hash: str,
    source_bodies: Mapping[str, object],
    producer_content_utf8: bytes,
    normalized_envelope_utf8: bytes,
    audit_schema_version: str = "host-grounder-quote-localization-audit-v0.1",
    producer_prompt_version: str = "host-grounder-discovery-prompt-v0.2",
    validator_version: str = "host-grounder-semantic-verifier-prompt-v0.3",
) -> QuoteLocalizationAudit:
    source_hashes = []
    for source_id in sorted(source_bodies):
        source = source_bodies[source_id]
        body = getattr(source, "body", None)
        body_sha256 = getattr(source, "body_sha256", None)
        if type(source_id) is not str or type(body) is not str or type(body_sha256) is not str:
            raise ValueError("source registry cannot be retained")
        if hashlib.sha256(body.encode("utf-8", errors="strict")).hexdigest() != body_sha256:
            raise ValueError("source registry hash mismatch")
        source_hashes.append({"source_id": source_id, "sha256": body_sha256})
    sidecar = {
        "schema_version": audit_schema_version,
        "run_id": run_id,
        "canonical_input_hash": canonical_input_hash,
        "producer_wire_version": "grounder-output-v0.2",
        "producer_prompt_version": producer_prompt_version,
        "producer_content_sha256": hashlib.sha256(producer_content_utf8).hexdigest(),
        "normalized_envelope_sha256": hashlib.sha256(normalized_envelope_utf8).hexdigest(),
        "source_body_hashes": source_hashes,
        "verifier_wire_version": "semantic-verdict-v0.2",
        "validator_version": validator_version,
        "localizer_version": "host-grounder-quote-localizer-v0.1",
    }
    sidecar_bytes = _canonical_bytes(sidecar)
    return QuoteLocalizationAudit(
        producer_content_utf8=producer_content_utf8,
        normalized_envelope_utf8=normalized_envelope_utf8,
        sidecar_utf8=sidecar_bytes,
        sidecar_sha256=hashlib.sha256(sidecar_bytes).hexdigest(),
    )
