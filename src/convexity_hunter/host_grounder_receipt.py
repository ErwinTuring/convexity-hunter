"""Structural and identity validation for Host semantic-validation receipts.

This module checks receipt provenance and lexical localization only. It does
not evaluate source entailment, attribution, semantic truth, or EI acceptance.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Mapping, Tuple

from .host_grounder_schema import parse_model_output_envelope


_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "run_id",
        "canonical_input_hash",
        "envelope_hash",
        "source_body_hashes",
        "validator_id",
        "validator_version",
        "verified_claim_ids",
        "rejected_claims",
        "verified_hypothesis_ids",
        "rejected_hypotheses",
        "verified_binding_indices",
        "rejected_bindings",
        "coverage_outcomes",
    }
)
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_COVERAGE_OUTCOMES = frozenset({"supported", "unresolved", "contradicted"})


@dataclass(frozen=True)
class ValidatedEnvelopeSnapshot:
    """Immutable canonical envelope bytes bound to the validated receipt hash."""

    canonical_bytes: bytes
    envelope_hash: str


def _nonempty_utf8(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(f"{label} must be a nonempty string")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} is not valid UTF-8 text") from exc
    return value


def _sha256_text(value: object, label: str) -> str:
    text = _nonempty_utf8(value, label)
    if _SHA256_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
    return text


def _canonical_envelope_bytes(envelope: Mapping[str, object]) -> bytes:
    try:
        canonical_json = json.dumps(
            envelope,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return canonical_json.encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise ValueError("envelope cannot be encoded as canonical UTF-8 JSON") from exc


def _require_tuple(value: object, label: str) -> tuple:
    if type(value) is not tuple:
        raise ValueError(f"{label} must be a tuple")
    return value


def _validate_string_partition(
    all_ids: Tuple[str, ...],
    verified_ids: object,
    rejected_entries: object,
    label: str,
) -> None:
    verified = _require_tuple(verified_ids, f"verified_{label}_ids")
    rejected = _require_tuple(rejected_entries, f"rejected {label} entries")

    verified_set = set()
    for value in verified:
        item = _nonempty_utf8(value, f"verified {label} ID")
        if item in verified_set:
            raise ValueError(f"duplicate verified {label} ID: {item}")
        verified_set.add(item)

    rejected_set = set()
    for entry in rejected:
        pair = _require_tuple(entry, f"rejected {label} entry")
        if len(pair) != 2:
            raise ValueError(f"rejected {label} entry must contain an ID and reason")
        item = _nonempty_utf8(pair[0], f"rejected {label} ID")
        _nonempty_utf8(pair[1], f"rejected {label} reason")
        if item in rejected_set:
            raise ValueError(f"duplicate rejected {label} ID: {item}")
        rejected_set.add(item)

    if verified_set & rejected_set:
        raise ValueError(f"verified and rejected {label} partitions overlap")
    if verified_set | rejected_set != set(all_ids):
        raise ValueError(f"verified and rejected {label} partitions do not match envelope")


def _unique_occurrence(body: str, quote: str) -> bool:
    first = body.find(quote)
    return first >= 0 and body.find(quote, first + 1) < 0


def validate_semantic_validation_receipt(
    envelope: Mapping[str, object],
    receipt: Mapping[str, object],
    *,
    run_id: str,
    canonical_input_hash: str,
    request_subquestion_ids: Tuple[str, ...],
    source_bodies: Mapping[str, str],
    max_input_bytes: int,
    max_string_bytes: int,
    max_array_items: int,
) -> ValidatedEnvelopeSnapshot:
    """Validate a receipt and return its immutable canonical envelope snapshot.

    ``envelope`` is the result of ``parse_model_output_envelope``. The caller
    supplies the immutable run identity, original request's ordered coverage
    IDs, and exact source-body registry. Lexical checks apply to verified claims
    and bindings; passing this validator says nothing about whether any source
    semantically supports a claim or hypothesis. The three required limits
    must match those used for the initial parse and are reapplied to the
    canonical serialization; builders must consume the returned snapshot rather
    than the mutable input mapping.
    """

    if type(envelope) is not dict:
        raise ValueError("envelope must be the parsed ModelOutputEnvelope dictionary")
    canonical_bytes = _canonical_envelope_bytes(envelope)
    envelope = parse_model_output_envelope(
        canonical_bytes.decode("utf-8", errors="strict"),
        max_input_bytes,
        max_string_bytes=max_string_bytes,
        max_array_items=max_array_items,
    )
    if not isinstance(receipt, Mapping) or set(receipt) != _RECEIPT_KEYS:
        raise ValueError("receipt must have the exact closed v0.1 field set")

    run_id = _nonempty_utf8(run_id, "expected run_id")
    canonical_input_hash = _sha256_text(
        canonical_input_hash, "expected canonical_input_hash"
    )
    if (
        type(receipt["schema_version"]) is not str
        or receipt["schema_version"] != "semantic-validation-v0.1"
    ):
        raise ValueError("receipt schema_version must be semantic-validation-v0.1")
    if _nonempty_utf8(receipt["run_id"], "receipt run_id") != run_id:
        raise ValueError("receipt run_id does not match the Host run")
    if _sha256_text(receipt["canonical_input_hash"], "receipt canonical_input_hash") != (
        canonical_input_hash
    ):
        raise ValueError("receipt canonical_input_hash does not match the Host run")
    _nonempty_utf8(receipt["validator_id"], "validator_id")
    _nonempty_utf8(receipt["validator_version"], "validator_version")

    expected_envelope_hash = hashlib.sha256(canonical_bytes).hexdigest()
    envelope_hash = _sha256_text(receipt["envelope_hash"], "receipt envelope_hash")
    if envelope_hash != expected_envelope_hash:
        raise ValueError("receipt envelope_hash does not match the parsed envelope")

    claims = envelope["claims"]
    hypotheses = envelope["hypotheses"]
    coverage = envelope["coverage"]
    bindings = envelope["field_bindings"]
    if any(type(items) is not list for items in (claims, hypotheses, coverage, bindings)):
        raise ValueError("parsed envelope collections must be lists")

    claim_ids = []
    claims_by_id = {}
    for claim in claims:
        if type(claim) is not dict:
            raise ValueError("parsed claims must be objects")
        claim_id = _nonempty_utf8(claim.get("claim_id"), "claim_id")
        if claim_id in claims_by_id:
            raise ValueError(f"duplicate envelope claim ID: {claim_id}")
        _nonempty_utf8(claim.get("source_id"), f"claim {claim_id} source_id")
        _nonempty_utf8(claim.get("quote"), f"claim {claim_id} quote")
        claims_by_id[claim_id] = claim
        claim_ids.append(claim_id)
    _validate_string_partition(
        tuple(claim_ids), receipt["verified_claim_ids"], receipt["rejected_claims"], "claim"
    )

    hypothesis_ids = []
    seen_hypotheses = set()
    for hypothesis in hypotheses:
        if type(hypothesis) is not dict:
            raise ValueError("parsed hypotheses must be objects")
        hypothesis_id = _nonempty_utf8(hypothesis.get("hypothesis_id"), "hypothesis_id")
        if hypothesis_id in seen_hypotheses:
            raise ValueError(f"duplicate envelope hypothesis ID: {hypothesis_id}")
        seen_hypotheses.add(hypothesis_id)
        hypothesis_ids.append(hypothesis_id)
    _validate_string_partition(
        tuple(hypothesis_ids),
        receipt["verified_hypothesis_ids"],
        receipt["rejected_hypotheses"],
        "hypothesis",
    )

    request_ids = _require_tuple(request_subquestion_ids, "request_subquestion_ids")
    request_id_set = set()
    for subquestion_id in request_ids:
        value = _nonempty_utf8(subquestion_id, "request subquestion_id")
        if value in request_id_set:
            raise ValueError(f"duplicate original request subquestion_id: {value}")
        request_id_set.add(value)

    coverage_ids = []
    for item in coverage:
        if type(item) is not dict:
            raise ValueError("parsed coverage entries must be objects")
        coverage_ids.append(_nonempty_utf8(item.get("subquestion_id"), "subquestion_id"))
    if tuple(coverage_ids) != request_ids:
        raise ValueError("envelope coverage IDs do not match the original request")

    source_hashes = []
    source_bodies_by_id = {}
    if not isinstance(source_bodies, Mapping):
        raise ValueError("source_bodies must be a source ID to body mapping")
    for source_id, body in source_bodies.items():
        source_id = _nonempty_utf8(source_id, "source body source_id")
        if type(body) is not str:
            raise ValueError(f"source body for {source_id} must be a string")
        try:
            body_bytes = body.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError(f"source body for {source_id} is not valid UTF-8 text") from exc
        source_bodies_by_id[source_id] = body
        source_hashes.append((source_id, hashlib.sha256(body_bytes).hexdigest()))
    source_hashes.sort(key=lambda item: item[0])

    receipt_source_hashes = _require_tuple(
        receipt["source_body_hashes"], "source_body_hashes"
    )
    parsed_source_hashes = []
    for entry in receipt_source_hashes:
        pair = _require_tuple(entry, "source_body_hashes entry")
        if len(pair) != 2:
            raise ValueError("source_body_hashes entries must contain source_id and hash")
        source_id = _nonempty_utf8(pair[0], "receipt source_body_hashes source_id")
        body_hash = _sha256_text(pair[1], f"source body hash for {source_id}")
        parsed_source_hashes.append((source_id, body_hash))
    if any(
        parsed_source_hashes[index - 1][0] >= parsed_source_hashes[index][0]
        for index in range(1, len(parsed_source_hashes))
    ):
        raise ValueError("source_body_hashes must be sorted by unique source_id")
    if tuple(parsed_source_hashes) != tuple(source_hashes):
        raise ValueError("receipt source_body_hashes do not match the exact body registry")

    verified_claims = _require_tuple(receipt["verified_claim_ids"], "verified_claim_ids")
    for claim_id in verified_claims:
        claim = claims_by_id[claim_id]
        source_id = claim["source_id"]
        body = source_bodies_by_id.get(source_id)
        if body is None or not _unique_occurrence(body, claim["quote"]):
            raise ValueError(
                f"verified claim {claim_id} quote is not unique in its registered source body"
            )

    verified_bindings = _require_tuple(
        receipt["verified_binding_indices"], "verified_binding_indices"
    )
    rejected_bindings = _require_tuple(receipt["rejected_bindings"], "rejected_bindings")
    verified_binding_set = set()
    for value in verified_bindings:
        if type(value) is not int or value < 0:
            raise ValueError("verified binding indices must be nonnegative integers")
        if value in verified_binding_set:
            raise ValueError(f"duplicate verified binding index: {value}")
        verified_binding_set.add(value)

    rejected_binding_set = set()
    for entry in rejected_bindings:
        pair = _require_tuple(entry, "rejected binding entry")
        if len(pair) != 2:
            raise ValueError("rejected binding entry must contain an index and reason")
        index, reason = pair
        if type(index) is not int or index < 0:
            raise ValueError("rejected binding indices must be nonnegative integers")
        _nonempty_utf8(reason, "rejected binding reason")
        if index in rejected_binding_set:
            raise ValueError(f"duplicate rejected binding index: {index}")
        rejected_binding_set.add(index)
    if verified_binding_set & rejected_binding_set:
        raise ValueError("verified and rejected binding partitions overlap")
    if verified_binding_set | rejected_binding_set != set(range(len(bindings))):
        raise ValueError("verified and rejected binding partitions do not match envelope")

    for index in sorted(verified_binding_set):
        binding = bindings[index]
        if type(binding) is not dict:
            raise ValueError("parsed field bindings must be objects")
        source_id = _nonempty_utf8(binding.get("source_id"), f"binding {index} source_id")
        quote = _nonempty_utf8(binding.get("quote"), f"binding {index} quote")
        start = binding.get("start")
        end = binding.get("end")
        if type(start) is not int or type(end) is not int or start < 0 or end <= start:
            raise ValueError(f"verified binding {index} has an invalid half-open span")
        body = source_bodies_by_id.get(source_id)
        if body is None or end > len(body) or body[start:end] != quote:
            raise ValueError(
                f"verified binding {index} span does not match its registered source body"
            )

    coverage_outcomes = _require_tuple(receipt["coverage_outcomes"], "coverage_outcomes")
    outcomes_by_index = {}
    for entry in coverage_outcomes:
        outcome = _require_tuple(entry, "coverage outcome")
        if len(outcome) != 4:
            raise ValueError("coverage outcomes must contain index, ID, outcome, and rationale")
        index, subquestion_id, status, rationale = outcome
        if type(index) is not int or index < 0 or index >= len(coverage_ids):
            raise ValueError("coverage outcome index is outside envelope coverage")
        subquestion_id = _nonempty_utf8(subquestion_id, "coverage outcome subquestion_id")
        if subquestion_id != coverage_ids[index]:
            raise ValueError("coverage outcome ID does not match its envelope index")
        if type(status) is not str or status not in _COVERAGE_OUTCOMES:
            raise ValueError("coverage outcome status is invalid")
        _nonempty_utf8(rationale, "coverage outcome rationale")
        if index in outcomes_by_index:
            raise ValueError(f"duplicate coverage outcome index: {index}")
        outcomes_by_index[index] = subquestion_id
    if set(outcomes_by_index) != set(range(len(coverage_ids))):
        raise ValueError("coverage outcomes do not partition envelope coverage exactly")

    return ValidatedEnvelopeSnapshot(
        canonical_bytes=canonical_bytes,
        envelope_hash=envelope_hash,
    )
