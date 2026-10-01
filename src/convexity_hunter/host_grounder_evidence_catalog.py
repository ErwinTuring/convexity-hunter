"""Bounded v0.3 evidence-catalog wire localization for Host Grounder."""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Tuple

from .host_grounder_builder import HostSourceBody
from .host_grounder_quote_localization import _canonical_bytes, _decode, _limit, _wire_string
from .host_grounder_schema import parse_model_output_envelope
from .host_grounder_semantic import parse_semantic_verdict


__all__ = (
    "EVIDENCE_CATALOG_SCHEMA_VERSION",
    "EVIDENCE_CATALOG_GENERATOR_VERSION",
    "HostEvidenceCatalogEntry",
    "HostEvidenceCatalog",
    "HostEvidenceCatalogAudit",
    "HostEvidenceCatalogAuditHolder",
    "build_host_evidence_catalog",
    "parse_grounder_output_v0_3",
    "parse_semantic_verdict_v0_3",
)


EVIDENCE_CATALOG_SCHEMA_VERSION = "host-grounder-evidence-catalog-v0.1"
EVIDENCE_CATALOG_GENERATOR_VERSION = "host-evidence-paragraph-generator-v0.1"
_AUDIT_SCHEMA_VERSION = "host-grounder-quote-localization-audit-v0.3"
_PRODUCER_WIRE_VERSION = "grounder-output-v0.3"
_PRODUCER_PROMPT_VERSION = "host-grounder-discovery-prompt-v0.4"
_VERIFIER_WIRE_VERSION = "semantic-verdict-v0.3"
_VERIFIER_PROMPT_VERSION = "host-grounder-semantic-verifier-prompt-v0.5"
_RESOLVER_VERSION = "host-evidence-catalog-resolver-v0.1"
_SHA256 = frozenset("0123456789abcdef")
_OUTPUT_TOP = frozenset(
    ("schema_version", "stage", "request_id", "claims", "hypotheses", "coverage", "field_bindings")
)
_CLAIM_KEYS = frozenset(
    (
        "claim_id", "kind", "evidence_id", "text", "entity_refs", "event_date",
        "published_at", "dependency_claim_ids", "uncertainty", "falsification_conditions",
    )
)
_BINDING_KEYS = frozenset(("field_path", "evidence_id", "semantic_role", "status"))
_VERDICT_TOP = frozenset(
    (
        "schema_version", "run_id", "envelope_hash", "source_body_hashes",
        "claims", "hypotheses", "field_bindings", "coverage",
    )
)
_VERDICT_SECTIONS = ("claims", "hypotheses", "field_bindings", "coverage")
_VERDICT_ID_KEYS = {
    "claims": "claim_id",
    "hypotheses": "hypothesis_id",
    "field_bindings": "index",
    "coverage": "index",
}


def _sha256_text(value: object, label: str, max_string_bytes: int) -> str:
    text = _wire_string(value, label, max_string_bytes)
    if len(text) != 64 or any(character not in _SHA256 for character in text):
        raise ValueError("{} must be lowercase SHA-256 hex".format(label))
    return text


def _line_paragraph_spans(body: str):
    """Yield maximal nonblank line runs; only LF and CRLF delimit lines."""
    line_start = 0
    paragraph_start = None
    paragraph_end = None
    while line_start < len(body):
        newline = body.find("\n", line_start)
        line_end = len(body) if newline < 0 else newline + 1
        content_end = line_end - 1 if newline >= 0 else line_end
        if newline >= 0 and content_end > line_start and body[content_end - 1] == "\r":
            content_end -= 1
        content = body[line_start:content_end]
        blank = not content or all(character in " \t" for character in content)
        if blank:
            if paragraph_start is not None:
                yield paragraph_start, paragraph_end
                paragraph_start = None
                paragraph_end = None
        else:
            if paragraph_start is None:
                paragraph_start = line_start
            paragraph_end = line_end
        line_start = line_end
    if paragraph_start is not None:
        yield paragraph_start, paragraph_end


def _overlap_aware_occurrence_count(body: str, quote: str) -> int:
    count = 0
    start = 0
    while True:
        found = body.find(quote, start)
        if found < 0:
            return count
        count += 1
        start = found + 1


@dataclass(frozen=True, repr=False)
class HostEvidenceCatalogEntry:
    evidence_id: str
    source_id: str
    body_sha256: str
    start: int
    end: int
    quote: str = field(repr=False)

    def __repr__(self) -> str:
        return "HostEvidenceCatalogEntry(evidence_id={!r}, source_id={!r}, start={!r}, end={!r})".format(
            self.evidence_id, self.source_id, self.start, self.end
        )


@dataclass(frozen=True, repr=False)
class HostEvidenceCatalog:
    run_id: str
    canonical_input_hash: str
    entries: Tuple[HostEvidenceCatalogEntry, ...]
    source_body_hashes: Tuple[Tuple[str, str], ...]
    canonical_utf8: bytes = field(repr=False)
    catalog_sha256: str
    _entries_by_id: Mapping[str, HostEvidenceCatalogEntry] = field(repr=False)

    def __repr__(self) -> str:
        return "HostEvidenceCatalog(entries={!r}, catalog_sha256={!r})".format(
            len(self.entries), self.catalog_sha256
        )

    def validate_sources(
        self,
        source_bodies: Mapping[str, HostSourceBody],
        *,
        run_id: str,
        canonical_input_hash: str,
        max_string_bytes: int,
    ) -> None:
        if run_id != self.run_id or canonical_input_hash != self.canonical_input_hash:
            raise ValueError("catalog run/input identity mismatch")
        if not isinstance(source_bodies, Mapping) or len(source_bodies) != len(self.source_body_hashes):
            raise ValueError("catalog source registry changed")
        observed = []
        for source_id in sorted(source_bodies):
            source = source_bodies[source_id]
            _wire_string(source_id, "source_id", max_string_bytes)
            if type(source) is not HostSourceBody:
                raise ValueError("catalog source is not a HostSourceBody")
            body_bytes = source.body.encode("utf-8", errors="strict")
            body_hash = hashlib.sha256(body_bytes).hexdigest()
            if source.body_sha256 != body_hash:
                raise ValueError("catalog source body hash changed")
            observed.append((source_id, body_hash))
        if tuple(observed) != self.source_body_hashes:
            raise ValueError("catalog source registry/hash changed")
        for entry in self.entries:
            source = source_bodies.get(entry.source_id)
            if (
                source is None
                or source.body_sha256 != entry.body_sha256
                or entry.end > len(source.body)
                or source.body[entry.start:entry.end] != entry.quote
            ):
                raise ValueError("catalog entry no longer matches its registered source")

    def resolve(
        self,
        evidence_id: object,
        source_bodies: Mapping[str, HostSourceBody],
        *,
        run_id: str,
        canonical_input_hash: str,
        max_string_bytes: int,
    ) -> Tuple[HostEvidenceCatalogEntry, HostSourceBody]:
        self.validate_sources(
            source_bodies,
            run_id=run_id,
            canonical_input_hash=canonical_input_hash,
            max_string_bytes=max_string_bytes,
        )
        evidence_id = _wire_string(evidence_id, "evidence_id", max_string_bytes)
        entry = self._entries_by_id.get(evidence_id)
        if entry is None:
            raise ValueError("evidence_id is not in this run catalog")
        return entry, source_bodies[entry.source_id]


def build_host_evidence_catalog(
    run_id: str,
    canonical_input_hash: str,
    source_bodies: Mapping[str, HostSourceBody],
    *,
    max_catalog_entries: int,
    max_catalog_bytes: int,
    max_catalog_paragraphs: int,
    max_string_bytes: int,
    max_array_items: int,
) -> HostEvidenceCatalog:
    """Build the complete deterministic catalog or fail without truncation."""
    max_catalog_entries = _limit(max_catalog_entries, "max_catalog_entries")
    max_catalog_bytes = _limit(max_catalog_bytes, "max_catalog_bytes")
    max_catalog_paragraphs = _limit(max_catalog_paragraphs, "max_catalog_paragraphs")
    max_string_bytes = _limit(max_string_bytes, "max_string_bytes")
    max_array_items = _limit(max_array_items, "max_array_items")
    run_id = _wire_string(run_id, "run_id", max_string_bytes)
    canonical_input_hash = _sha256_text(
        canonical_input_hash, "canonical_input_hash", max_string_bytes
    )
    if not isinstance(source_bodies, Mapping) or not source_bodies:
        raise ValueError("source registry must be nonempty")
    if len(source_bodies) > max_array_items:
        raise ValueError("source registry exceeds max_array_items")

    source_hash_items = []
    ordered_sources = []
    for source_id in source_bodies:
        _wire_string(source_id, "source_id", max_string_bytes)
    for source_id in sorted(source_bodies):
        source = source_bodies[source_id]
        if type(source) is not HostSourceBody:
            raise ValueError("source registry must contain HostSourceBody records")
        _wire_string(source.final_locator, "final_locator", max_string_bytes)
        if source.title is not None:
            _wire_string(source.title, "title", max_string_bytes)
        body_bytes = source.body.encode("utf-8", errors="strict")
        body_sha256 = hashlib.sha256(body_bytes).hexdigest()
        if source.body_sha256 != body_sha256:
            raise ValueError("source body hash mismatch")
        _sha256_text(body_sha256, "source body sha256", max_string_bytes)
        source_hash_items.append({"source_id": source_id, "sha256": body_sha256})
        ordered_sources.append((source_id, source))

    candidates = []
    exclusions = []
    candidate_count = 0
    for source_id, source in ordered_sources:
        nonunique = 0
        overlong = 0
        for start, end in _line_paragraph_spans(source.body):
            candidate_count += 1
            if candidate_count > max_catalog_paragraphs:
                raise ValueError("catalog exceeds max_catalog_paragraphs")
            quote = source.body[start:end]
            quote_size = len(quote.encode("utf-8", errors="strict"))
            unique = _overlap_aware_occurrence_count(source.body, quote) == 1
            within_string_bound = quote_size <= max_string_bytes
            if not unique:
                nonunique += 1
            if not within_string_bound:
                overlong += 1
            if unique and within_string_bound:
                candidates.append(
                    {
                        "source_id": source_id,
                        "body_sha256": source.body_sha256,
                        "start": start,
                        "end": end,
                        "quote": quote,
                    }
                )
                if len(candidates) > max_catalog_entries or len(candidates) > max_array_items:
                    raise ValueError("catalog exceeds entry bound")
        exclusions.append(
            {
                "source_id": source_id,
                "nonunique_paragraphs": nonunique,
                "overlong_paragraphs": overlong,
            }
        )
    if not candidates:
        raise ValueError("catalog has no eligible entries")
    if len(candidates) > max_catalog_entries or len(exclusions) > max_array_items:
        raise ValueError("catalog exceeds array or entry bound")

    seed = hashlib.sha256(
        _canonical_bytes(
            {
                "run_id": run_id,
                "canonical_input_hash": canonical_input_hash,
                "source_body_hashes": source_hash_items,
                "generator_version": EVIDENCE_CATALOG_GENERATOR_VERSION,
            }
        )
    ).hexdigest()
    entries = []
    seen_ids = set()
    for ordinal, candidate in enumerate(candidates):
        evidence_id = "evidence-{}-{}".format(seed, ordinal)
        _wire_string(evidence_id, "evidence_id", max_string_bytes)
        if evidence_id in seen_ids:
            raise ValueError("duplicate catalog evidence_id")
        seen_ids.add(evidence_id)
        entries.append(
            {
                "evidence_id": evidence_id,
                "source_id": candidate["source_id"],
                "body_sha256": candidate["body_sha256"],
                "start": candidate["start"],
                "end": candidate["end"],
                "quote": candidate["quote"],
            }
        )

    catalog_object = {
        "schema_version": EVIDENCE_CATALOG_SCHEMA_VERSION,
        "run_id": run_id,
        "canonical_input_hash": canonical_input_hash,
        "generator_version": EVIDENCE_CATALOG_GENERATOR_VERSION,
        "source_body_hashes": source_hash_items,
        "entries": entries,
        "exclusions": exclusions,
    }
    catalog_utf8 = _canonical_bytes(catalog_object)
    if len(catalog_utf8) > max_catalog_bytes:
        raise ValueError("catalog exceeds max_catalog_bytes")
    digest = hashlib.sha256(catalog_utf8).hexdigest()
    entry_records = tuple(
        HostEvidenceCatalogEntry(**item) for item in entries
    )
    return HostEvidenceCatalog(
        run_id=run_id,
        canonical_input_hash=canonical_input_hash,
        entries=entry_records,
        source_body_hashes=tuple((item["source_id"], item["sha256"]) for item in source_hash_items),
        canonical_utf8=bytes(catalog_utf8),
        catalog_sha256=digest,
        _entries_by_id=MappingProxyType(
            {entry.evidence_id: entry for entry in entry_records}
        ),
    )


def _normalized_bytes(value: object, max_input_bytes: int, label: str) -> bytes:
    normalized = _canonical_bytes(value)
    if len(normalized) > max_input_bytes:
        raise ValueError("{} exceeds max_input_bytes".format(label))
    return normalized


def parse_grounder_output_v0_3(
    raw_json: str,
    max_input_bytes: int,
    *,
    max_string_bytes: int,
    max_array_items: int,
    run_id: str,
    canonical_input_hash: str,
    source_bodies: Mapping[str, HostSourceBody],
    catalog: HostEvidenceCatalog,
) -> tuple:
    """Expand exact catalog IDs, then apply the unchanged internal v0.1 parser."""
    max_input_bytes = _limit(max_input_bytes, "max_input_bytes")
    max_string_bytes = _limit(max_string_bytes, "max_string_bytes")
    max_array_items = _limit(max_array_items, "max_array_items")
    wire = _decode(raw_json, max_input_bytes)
    if set(wire) != _OUTPUT_TOP or wire.get("schema_version") != "grounder-output-v0.3":
        raise ValueError("producer wire DTO has an invalid closed shape or version")
    catalog.validate_sources(
        source_bodies,
        run_id=run_id,
        canonical_input_hash=canonical_input_hash,
        max_string_bytes=max_string_bytes,
    )

    internal = dict(wire)
    internal["schema_version"] = "grounder-output-v0.1"
    claims = wire.get("claims")
    if type(claims) is not list or len(claims) > max_array_items:
        raise ValueError("claims must be a bounded array")
    expanded_claims = []
    for raw_claim in claims:
        if type(raw_claim) is not dict or set(raw_claim) != _CLAIM_KEYS:
            raise ValueError("producer claim has an invalid closed wire shape")
        claim = dict(raw_claim)
        evidence_id = _wire_string(claim.pop("evidence_id"), "evidence_id", max_string_bytes)
        entry = catalog._entries_by_id.get(evidence_id)
        if entry is None:
            raise ValueError("claim evidence_id is not in this run catalog")
        source = source_bodies[entry.source_id]
        claim["source_id"] = entry.source_id
        claim["locator"] = _wire_string(source.final_locator, "final_locator", max_string_bytes)
        claim["quote"] = entry.quote
        expanded_claims.append(claim)
    internal["claims"] = expanded_claims

    bindings = wire.get("field_bindings")
    if type(bindings) is not list or len(bindings) > max_array_items:
        raise ValueError("field_bindings must be a bounded array")
    expanded_bindings = []
    for raw_binding in bindings:
        if type(raw_binding) is not dict or set(raw_binding) != _BINDING_KEYS:
            raise ValueError("producer binding has an invalid closed wire shape")
        binding = dict(raw_binding)
        evidence_id = _wire_string(binding.pop("evidence_id"), "evidence_id", max_string_bytes)
        entry = catalog._entries_by_id.get(evidence_id)
        if entry is None:
            raise ValueError("binding evidence_id is not in this run catalog")
        binding["source_id"] = entry.source_id
        binding["quote"] = entry.quote
        binding["start"] = entry.start
        binding["end"] = entry.end
        expanded_bindings.append(binding)
    internal["field_bindings"] = expanded_bindings

    normalized = _normalized_bytes(internal, max_input_bytes, "normalized envelope")
    parsed = parse_model_output_envelope(
        normalized.decode("utf-8", errors="strict"),
        max_input_bytes,
        max_string_bytes=max_string_bytes,
        max_array_items=max_array_items,
    )
    normalized = _normalized_bytes(parsed, max_input_bytes, "normalized envelope")
    return parsed, normalized


def parse_semantic_verdict_v0_3(
    raw_json: str,
    max_input_bytes: int,
    *,
    max_string_bytes: int,
    max_array_items: int,
    run_id: str,
    canonical_input_hash: str,
    source_bodies: Mapping[str, HostSourceBody],
    catalog: HostEvidenceCatalog,
    producer_binding_evidence_ids: tuple,
) -> bytes:
    """Expand verifier catalog IDs and strictly parse internal verdict v0.1."""
    max_input_bytes = _limit(max_input_bytes, "max_input_bytes")
    max_string_bytes = _limit(max_string_bytes, "max_string_bytes")
    max_array_items = _limit(max_array_items, "max_array_items")
    wire = _decode(raw_json, max_input_bytes)
    if set(wire) != _VERDICT_TOP or wire.get("schema_version") != "semantic-verdict-v0.3":
        raise ValueError("verifier wire DTO has an invalid closed shape or version")
    if wire.get("run_id") != run_id:
        raise ValueError("verifier run_id does not match Host run")
    catalog.validate_sources(
        source_bodies,
        run_id=run_id,
        canonical_input_hash=canonical_input_hash,
        max_string_bytes=max_string_bytes,
    )
    if type(producer_binding_evidence_ids) is not tuple:
        raise ValueError("producer binding evidence IDs must be an exact tuple")
    producer_binding_evidence_ids = tuple(
        _wire_string(value, "producer binding evidence_id", max_string_bytes)
        for value in producer_binding_evidence_ids
    )
    if any(value not in catalog._entries_by_id for value in producer_binding_evidence_ids):
        raise ValueError("producer binding evidence_id is not in this run catalog")
    wire_bindings = wire.get("field_bindings")
    if type(wire_bindings) is not list or len(wire_bindings) != len(producer_binding_evidence_ids):
        raise ValueError("verifier field binding identities do not match producer")
    for record in wire_bindings:
        if type(record) is not dict or type(record.get("index")) is not int:
            raise ValueError("verifier field binding identity is invalid")
        index = record["index"]
        if index < 0 or index >= len(producer_binding_evidence_ids):
            raise ValueError("verifier field binding index is outside producer")
        if record.get("outcome") == "supported":
            refs = record.get("evidence_refs")
            if type(refs) is not list or not any(
                type(ref) is dict
                and ref.get("evidence_id") == producer_binding_evidence_ids[index]
                for ref in refs
            ):
                raise ValueError("supported binding does not reuse producer evidence_id")

    internal = dict(wire)
    internal["schema_version"] = "semantic-verdict-v0.1"
    for section in _VERDICT_SECTIONS:
        records = internal[section]
        if type(records) is not list or len(records) > max_array_items:
            raise ValueError("{} must be a bounded array".format(section))
        expanded_records = []
        for raw_record in records:
            if type(raw_record) is not dict or type(raw_record.get("evidence_refs")) is not list:
                raise ValueError("verdict record evidence_refs must be an array")
            refs = raw_record["evidence_refs"]
            if len(refs) > max_array_items:
                raise ValueError("evidence_refs exceeds max_array_items")
            record = dict(raw_record)
            expanded_refs = []
            seen_refs = set()
            for raw_ref in refs:
                if type(raw_ref) is not dict or set(raw_ref) != frozenset(("evidence_id",)):
                    raise ValueError("verifier evidence ref has an invalid closed wire shape")
                evidence_id = _wire_string(raw_ref["evidence_id"], "evidence_id", max_string_bytes)
                if evidence_id in seen_refs:
                    raise ValueError("duplicate evidence_id within verifier record")
                seen_refs.add(evidence_id)
                entry = catalog._entries_by_id.get(evidence_id)
                if entry is None:
                    raise ValueError("verifier evidence_id is not in this run catalog")
                expanded_refs.append(
                    {
                        "source_id": entry.source_id,
                        "body_sha256": entry.body_sha256,
                        "start": entry.start,
                        "end": entry.end,
                        "quote": entry.quote,
                    }
                )
            record["evidence_refs"] = expanded_refs
            expanded_records.append(record)
        internal[section] = expanded_records

    normalized = _normalized_bytes(internal, max_input_bytes, "normalized verdict")
    parsed = parse_semantic_verdict(
        normalized.decode("utf-8", errors="strict"),
        max_input_bytes,
        max_string_bytes=max_string_bytes,
        max_array_items=max_array_items,
    )
    return _normalized_bytes(parsed, max_input_bytes, "normalized verdict")


@dataclass(frozen=True, repr=False)
class HostEvidenceCatalogAudit:
    catalog_utf8: bytes = field(repr=False)
    producer_content_utf8: bytes = field(repr=False)
    normalized_envelope_utf8: bytes = field(repr=False)
    sidecar_utf8: bytes = field(repr=False)
    catalog_sha256: str
    producer_content_sha256: str
    normalized_envelope_sha256: str
    sidecar_sha256: str

    def __repr__(self) -> str:
        return "HostEvidenceCatalogAudit(sidecar_sha256={!r})".format(self.sidecar_sha256)


class HostEvidenceCatalogAuditHolder:
    """Caller-owned, repr-hidden, write-once audit retention for one run."""

    __slots__ = (
        "_run_id", "_canonical_input_hash", "_state", "_catalog_utf8",
        "_catalog_sha256", "_producer_content_utf8", "_producer_content_sha256",
        "_audit", "_lock",
    )

    def __setattr__(self, name: str, value: object) -> None:
        if hasattr(self, name):
            raise AttributeError("audit holder fields are write-once")
        object.__setattr__(self, name, value)

    def __init__(self, *, run_id: str, canonical_input_hash: str) -> None:
        if type(run_id) is not str or not run_id:
            raise ValueError("run_id must be a nonempty string")
        run_id.encode("utf-8", errors="strict")
        if (
            type(canonical_input_hash) is not str
            or len(canonical_input_hash) != 64
            or any(character not in _SHA256 for character in canonical_input_hash)
        ):
            raise ValueError("canonical_input_hash must be lowercase SHA-256 hex")
        self._run_id = run_id
        self._canonical_input_hash = canonical_input_hash
        self._state = "new"
        self._catalog_utf8 = None
        self._catalog_sha256 = None
        self._producer_content_utf8 = None
        self._producer_content_sha256 = None
        self._audit = None
        self._lock = threading.Lock()

    @property
    def catalog_utf8(self) -> bytes | None:
        return self._catalog_utf8

    @property
    def catalog_sha256(self) -> str | None:
        return self._catalog_sha256

    @property
    def producer_content_utf8(self) -> bytes | None:
        return self._producer_content_utf8

    @property
    def producer_content_sha256(self) -> str | None:
        return self._producer_content_sha256

    @property
    def audit(self) -> HostEvidenceCatalogAudit | None:
        return self._audit

    @property
    def finalized(self) -> bool:
        return self._state == "finalized"

    def __repr__(self) -> str:
        return "HostEvidenceCatalogAuditHolder(state={!r})".format(self._state)

    def _begin(
        self,
        run_id: str,
        canonical_input_hash: str,
        catalog_utf8: bytes,
        catalog_sha256: str,
    ) -> None:
        with self._lock:
            if (
                self._state != "new"
                or run_id != self._run_id
                or canonical_input_hash != self._canonical_input_hash
                or type(catalog_utf8) is not bytes
                or hashlib.sha256(catalog_utf8).hexdigest() != catalog_sha256
            ):
                raise ValueError("audit holder is not fresh for this run/catalog")
            object.__setattr__(self, "_catalog_utf8", bytes(catalog_utf8))
            object.__setattr__(self, "_catalog_sha256", catalog_sha256)
            object.__setattr__(self, "_state", "catalog_retained")

    def _capture_producer_content(self, content_utf8: bytes) -> None:
        with self._lock:
            if self._state != "catalog_retained" or type(content_utf8) is not bytes:
                raise ValueError("audit holder cannot retain producer content")
            content_copy = bytes(content_utf8)
            object.__setattr__(self, "_producer_content_utf8", content_copy)
            object.__setattr__(
                self, "_producer_content_sha256", hashlib.sha256(content_copy).hexdigest()
            )
            object.__setattr__(self, "_state", "producer_retained")

    def _finalize(
        self,
        normalized_envelope_utf8: bytes,
        *,
        catalog: HostEvidenceCatalog,
    ) -> HostEvidenceCatalogAudit:
        with self._lock:
            if (
                self._state != "producer_retained"
                or type(normalized_envelope_utf8) is not bytes
                or catalog.canonical_utf8 != self._catalog_utf8
                or catalog.catalog_sha256 != self._catalog_sha256
            ):
                raise ValueError("audit holder cannot be finalized")
            normalized_copy = bytes(normalized_envelope_utf8)
            sidecar = {
                "schema_version": _AUDIT_SCHEMA_VERSION,
                "run_id": self._run_id,
                "canonical_input_hash": self._canonical_input_hash,
                "producer_wire_version": _PRODUCER_WIRE_VERSION,
                "producer_prompt_version": _PRODUCER_PROMPT_VERSION,
                "producer_content_sha256": self._producer_content_sha256,
                "normalized_envelope_sha256": hashlib.sha256(normalized_copy).hexdigest(),
                "source_body_hashes": [
                    {"source_id": source_id, "sha256": body_sha256}
                    for source_id, body_sha256 in catalog.source_body_hashes
                ],
                "verifier_wire_version": _VERIFIER_WIRE_VERSION,
                "validator_version": _VERIFIER_PROMPT_VERSION,
                "localizer_version": _RESOLVER_VERSION,
                "catalog_schema_version": EVIDENCE_CATALOG_SCHEMA_VERSION,
                "catalog_generator_version": EVIDENCE_CATALOG_GENERATOR_VERSION,
                "catalog_sha256": catalog.catalog_sha256,
            }
            sidecar_utf8 = _canonical_bytes(sidecar)
            audit = HostEvidenceCatalogAudit(
                catalog_utf8=bytes(self._catalog_utf8),
                producer_content_utf8=bytes(self._producer_content_utf8),
                normalized_envelope_utf8=normalized_copy,
                sidecar_utf8=bytes(sidecar_utf8),
                catalog_sha256=self._catalog_sha256,
                producer_content_sha256=self._producer_content_sha256,
                normalized_envelope_sha256=sidecar["normalized_envelope_sha256"],
                sidecar_sha256=hashlib.sha256(sidecar_utf8).hexdigest(),
            )
            object.__setattr__(self, "_audit", audit)
            object.__setattr__(self, "_state", "finalized")
            return audit
