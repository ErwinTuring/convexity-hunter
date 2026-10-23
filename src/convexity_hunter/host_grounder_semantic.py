"""Low-level deterministic parsing and conversion of a bounded verifier verdict.

This module makes no model/network calls. Caller-provided verdicts and
``validator_id`` values are not authenticated here; do not expose this
conversion as product runtime or treat those values as authenticated claims.
Passing its gates is fallible evidence assessment, not proof of semantic or
real-world truth.
"""

import hashlib
import json
import logging
import re
from collections import deque
from typing import Mapping, Tuple

from .host_grounder_receipt import validate_semantic_validation_receipt
from .host_grounder_schema import parse_model_output_envelope


__all__ = ("parse_semantic_verdict",)

_HEX = re.compile(r"[0-9a-f]{64}")
_TOP = frozenset(("schema_version", "run_id", "envelope_hash", "source_body_hashes", "claims", "hypotheses", "field_bindings", "coverage"))
_BASE = frozenset(("outcome", "rationale", "evidence_refs"))
_REF = frozenset(("source_id", "body_sha256", "start", "end", "quote"))
_OUTCOMES = frozenset(("supported", "contradicted", "unresolved"))
_RECEIPT_SCHEMA_VERSIONS = frozenset(
    ("semantic-validation-v0.1", "semantic-validation-v0.2")
)
_RECEIPT_FAILURE_CHECKS = frozenset(
    (
        "RUN_BINDING",
        "ENVELOPE_HASH",
        "SOURCE_REGISTRY",
        "SOURCE_HASHES",
        "REQUEST_IDS",
        "CLAIM_IDS",
        "HYPOTHESIS_IDS",
        "BINDING_IDS",
        "COVERAGE_IDS",
        "EVIDENCE_SOURCE_HASH",
        "EVIDENCE_SPAN",
        "UNKNOWN",
    )
)
_LOGGER = logging.getLogger(__name__)
_REJECTION_CHECKS = frozenset(
    (
        "dependency_closure",
        "dependency_cycle",
        "hypothesis_roots",
        "hypothesis_support_source",
        "missing_exact_reference",
        "required_field_binding",
        "unknown",
        "verifier_contradicted",
        "verifier_unresolved",
    )
)


def _receipt_failure(message: str, check: str) -> ValueError:
    """Attach one fixed private category without changing ValueError text."""
    error = ValueError(message)
    if type(check) is not str or check not in _RECEIPT_FAILURE_CHECKS:
        check = "UNKNOWN"
    error._receipt_failure_check = check
    return error


def _record_rejection_check(checks: dict, category: object) -> None:
    """Count only closed check names; never coerce caller-controlled values."""
    if type(checks) is not dict:
        return
    if type(category) is not str or category not in _REJECTION_CHECKS:
        category = "unknown"
    count = checks.get(category, 0)
    if type(count) is not int or count < 0:
        count = 0
    checks[category] = count + 1


def _record_verifier_rejection(checks: dict, outcome: object) -> None:
    if type(outcome) is str and outcome == "contradicted":
        _record_rejection_check(checks, "verifier_contradicted")
    elif type(outcome) is str and outcome == "unresolved":
        _record_rejection_check(checks, "verifier_unresolved")
    else:
        _record_rejection_check(checks, "unknown")


def _emit_rejection_checks(checks: object) -> None:
    """Emit counts from the closed check vocabulary, swallowing logger failures."""
    try:
        if type(checks) is not dict:
            return
        safe_counts = {}
        for category, count in checks.items():
            if (
                type(category) is str
                and category in _REJECTION_CHECKS
                and type(count) is int
                and count > 0
            ):
                safe_counts[category] = count
        if not safe_counts:
            return
        fields = " ".join(
            "{}={}".format(category, safe_counts[category])
            for category in sorted(safe_counts)
        )
        _LOGGER.warning("semantic_validation_rejection_checks %s", fields)
    except Exception:
        # Observability must never alter receipt construction or rejection policy.
        return


def _limit(value: object, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("{} must be a positive integer".format(name))
    return value


def _string(value: object, name: str, limit: int) -> str:
    if type(value) is not str or not value:
        raise ValueError("{} must be a nonempty string".format(name))
    try:
        size = len(value.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as exc:
        raise ValueError("{} is not valid UTF-8".format(name)) from exc
    if size > limit:
        raise ValueError("{} exceeds max_string_bytes".format(name))
    return value


def _digest(value: object, name: str, limit: int) -> str:
    value = _string(value, name, limit)
    if _HEX.fullmatch(value) is None:
        raise ValueError("{} must be lowercase SHA-256 hex".format(name))
    return value


def _object(value: object, keys: frozenset, name: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ValueError("{} must have the exact closed field set".format(name))
    return value


def _array(value: object, name: str, limit: int) -> list:
    if type(value) is not list or len(value) > limit:
        raise ValueError("{} must be an array within max_array_items".format(name))
    return value


def _reject_duplicate_keys(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: {}".format(key))
        result[key] = value
    return result


def _reject_constant(token: str) -> None:
    raise ValueError("non-finite JSON number is not permitted: {}".format(token))


def parse_semantic_verdict(
    raw_json: str,
    max_input_bytes: int,
    *,
    max_string_bytes: int,
    max_array_items: int,
) -> dict:
    """Strictly parse the closed semantic-verdict-v0.1 JSON DTO."""
    max_input_bytes = _limit(max_input_bytes, "max_input_bytes")
    max_string_bytes = _limit(max_string_bytes, "max_string_bytes")
    max_array_items = _limit(max_array_items, "max_array_items")
    if type(raw_json) is not str:
        raise ValueError("raw_json must be a string")
    try:
        if len(raw_json.encode("utf-8", errors="strict")) > max_input_bytes:
            raise ValueError("raw_json exceeds max_input_bytes")
        verdict = json.loads(
            raw_json,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except (UnicodeEncodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("raw_json is not valid bounded UTF-8 JSON") from exc

    def strings_and_arrays(value: object, name: str) -> None:
        if type(value) is str:
            _string(value, name, max_string_bytes)
        elif type(value) is list:
            _array(value, name, max_array_items)
            for index, item in enumerate(value):
                strings_and_arrays(item, "{}[{}]".format(name, index))
        elif type(value) is dict:
            for key, item in value.items():
                _string(key, "{} key".format(name), max_string_bytes)
                strings_and_arrays(item, "{}.{}".format(name, key))

    try:
        strings_and_arrays(verdict, "verdict")
    except RecursionError as exc:
        raise ValueError("verdict nesting is too deep") from exc

    verdict = _object(verdict, _TOP, "verdict")
    if verdict["schema_version"] != "semantic-verdict-v0.1":
        raise ValueError("schema_version must be semantic-verdict-v0.1")
    _string(verdict["run_id"], "run_id", max_string_bytes)
    _digest(verdict["envelope_hash"], "envelope_hash", max_string_bytes)

    previous = None
    for raw in _array(verdict["source_body_hashes"], "source_body_hashes", max_array_items):
        item = _object(raw, frozenset(("source_id", "sha256")), "source body hash")
        source_id = _string(item["source_id"], "source_id", max_string_bytes)
        _digest(item["sha256"], "source sha256", max_string_bytes)
        if previous is not None and source_id <= previous:
            raise ValueError("source_body_hashes must be sorted with unique IDs")
        previous = source_id

    specs = (
        ("claims", "claim_id", frozenset(("claim_id",)) | _BASE),
        ("hypotheses", "hypothesis_id", frozenset(("hypothesis_id",)) | _BASE),
        ("field_bindings", "index", frozenset(("index",)) | _BASE),
        ("coverage", "index", frozenset(("index", "subquestion_id")) | _BASE),
    )
    for name, id_key, keys in specs:
        seen = set()
        for raw in _array(verdict[name], name, max_array_items):
            item = _object(raw, keys, name + " item")
            identity = item[id_key]
            if id_key == "index":
                if type(identity) is not int or identity < 0:
                    raise ValueError(name + " index must be a nonnegative integer")
            else:
                _string(identity, name + " ID", max_string_bytes)
            if identity in seen:
                raise ValueError("duplicate {} verdict identity".format(name))
            seen.add(identity)
            if name == "coverage":
                _string(item["subquestion_id"], "subquestion_id", max_string_bytes)
            if type(item["outcome"]) is not str or item["outcome"] not in _OUTCOMES:
                raise ValueError(name + " outcome is invalid")
            _string(item["rationale"], name + " rationale", max_string_bytes)
            refs = _array(item["evidence_refs"], name + " evidence_refs", max_array_items)
            if item["outcome"] != "unresolved" and not refs:
                raise ValueError("supported or contradicted verdict needs evidence_refs")
            for raw_ref in refs:
                ref = _object(raw_ref, _REF, "evidence ref")
                _string(ref["source_id"], "evidence source_id", max_string_bytes)
                _digest(ref["body_sha256"], "evidence body_sha256", max_string_bytes)
                if type(ref["start"]) is not int or ref["start"] < 0:
                    raise ValueError("evidence start must be a nonnegative integer")
                if type(ref["end"]) is not int or ref["end"] <= ref["start"]:
                    raise ValueError("evidence end must be greater than start")
                _string(ref["quote"], "evidence quote", max_string_bytes)
    return verdict


def _paths_for_claim(claim: dict, index: int) -> tuple:
    paths = []
    if claim["event_date"] is not None:
        paths.append("/claims/{}/event_date".format(index))
    paths.extend("/claims/{}/entity_refs/{}".format(index, j) for j in range(len(claim["entity_refs"])))
    return tuple(paths)


def _paths_for_hypothesis(hypothesis: dict, index: int) -> tuple:
    paths = [
        "/hypotheses/{}/{}".format(index, key)
        for key in ("underlying_symbol", "impact_path", "distribution_mode", "distribution_hypothesis")
        if hypothesis[key] is not None
    ]
    if hypothesis["expected_window"] is not None:
        paths.extend("/hypotheses/{}/expected_window/{}".format(index, key) for key in ("start_date", "end_date"))
    if hypothesis["reassessment"] is not None:
        paths.append("/hypotheses/{}/reassessment/reassessment_by".format(index))
    return tuple(paths)


def build_semantic_validation_receipt(
    envelope: Mapping[str, object],
    raw_verdict_json: str,
    *,
    run_id: str,
    canonical_input_hash: str,
    request_subquestion_ids: Tuple[str, ...],
    source_bodies: Mapping[str, str],
    validator_id: str,
    validator_version: str,
    max_input_bytes: int,
    max_string_bytes: int,
    max_array_items: int,
    max_source_body_bytes: int,
    receipt_schema_version: str = "semantic-validation-v0.1",
) -> dict:
    """Build a version-selected closed receipt; v0.1 remains the default."""
    if (
        type(receipt_schema_version) is not str
        or receipt_schema_version not in _RECEIPT_SCHEMA_VERSIONS
    ):
        raise ValueError("receipt_schema_version is unsupported")
    max_input_bytes = _limit(max_input_bytes, "max_input_bytes")
    max_string_bytes = _limit(max_string_bytes, "max_string_bytes")
    max_array_items = _limit(max_array_items, "max_array_items")
    max_source_body_bytes = _limit(max_source_body_bytes, "max_source_body_bytes")
    run_id = _string(run_id, "run_id", max_string_bytes)
    canonical_input_hash = _digest(canonical_input_hash, "canonical_input_hash", max_string_bytes)
    validator_id = _string(validator_id, "validator_id", max_string_bytes)
    validator_version = _string(validator_version, "validator_version", max_string_bytes)
    if type(envelope) is not dict:
        raise ValueError("envelope must be a parsed model-output dictionary")
    try:
        envelope_bytes = json.dumps(
            envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError, RecursionError) as exc:
        raise ValueError("envelope cannot be canonically encoded") from exc
    parsed = parse_model_output_envelope(
        envelope_bytes.decode("utf-8"), max_input_bytes,
        max_string_bytes=max_string_bytes, max_array_items=max_array_items,
    )
    envelope_hash = hashlib.sha256(envelope_bytes).hexdigest()
    verdict = parse_semantic_verdict(
        raw_verdict_json, max_input_bytes,
        max_string_bytes=max_string_bytes, max_array_items=max_array_items,
    )
    if verdict["run_id"] != run_id:
        raise _receipt_failure("verdict run_id does not match Host run", "RUN_BINDING")
    if verdict["envelope_hash"] != envelope_hash:
        raise _receipt_failure(
            "verdict envelope_hash does not match canonical envelope", "ENVELOPE_HASH"
        )
    if not isinstance(source_bodies, Mapping) or len(source_bodies) > max_array_items:
        raise _receipt_failure("source_bodies must be a bounded mapping", "SOURCE_REGISTRY")
    body_hashes = {}
    body_bytes_total = 0
    for source_id, body in source_bodies.items():
        _string(source_id, "source_id", max_string_bytes)
        if type(body) is not str:
            raise _receipt_failure("source body must be a string", "SOURCE_REGISTRY")
        try:
            body_bytes = body.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise _receipt_failure("source body is not valid UTF-8", "SOURCE_REGISTRY") from exc
        body_bytes_total += len(body_bytes)
        if body_bytes_total > max_source_body_bytes:
            raise _receipt_failure(
                "source body registry exceeds max_source_body_bytes", "SOURCE_REGISTRY"
            )
        body_hashes[source_id] = hashlib.sha256(body_bytes).hexdigest()
    expected_hashes = tuple(sorted(body_hashes.items()))
    reported_hashes = tuple((x["source_id"], x["sha256"]) for x in verdict["source_body_hashes"])
    if reported_hashes != expected_hashes:
        raise _receipt_failure(
            "verdict source_body_hashes do not match exact registry", "SOURCE_HASHES"
        )

    if type(request_subquestion_ids) is not tuple:
        raise _receipt_failure("request_subquestion_ids must be a tuple", "REQUEST_IDS")
    request_ids = tuple(_string(x, "request subquestion_id", max_string_bytes) for x in request_subquestion_ids)
    if len(set(request_ids)) != len(request_ids):
        raise _receipt_failure("duplicate request subquestion_id", "REQUEST_IDS")
    claims, hypotheses = parsed["claims"], parsed["hypotheses"]
    bindings, coverage = parsed["field_bindings"], parsed["coverage"]
    claim_ids = tuple(x["claim_id"] for x in claims)
    hypothesis_ids = tuple(x["hypothesis_id"] for x in hypotheses)
    if len(set(claim_ids)) != len(claim_ids):
        raise _receipt_failure("duplicate envelope claim or hypothesis ID", "CLAIM_IDS")
    if len(set(hypothesis_ids)) != len(hypothesis_ids):
        raise _receipt_failure("duplicate envelope claim or hypothesis ID", "HYPOTHESIS_IDS")
    if tuple(x["subquestion_id"] for x in coverage) != request_ids:
        raise _receipt_failure(
            "envelope coverage IDs do not match ordered request", "COVERAGE_IDS"
        )

    def keyed(name: str, id_key: str, expected: set, check: str) -> dict:
        records = verdict[name]
        result = {item[id_key]: item for item in records}
        if len(result) != len(records):
            raise _receipt_failure("duplicate {} verdict identity".format(name), check)
        if set(result) != expected:
            raise _receipt_failure(
                "{} verdict IDs/indices do not match envelope".format(name), check
            )
        return result

    cv = keyed("claims", "claim_id", set(claim_ids), "CLAIM_IDS")
    hv = keyed("hypotheses", "hypothesis_id", set(hypothesis_ids), "HYPOTHESIS_IDS")
    bv = keyed("field_bindings", "index", set(range(len(bindings))), "BINDING_IDS")
    vv = verdict["coverage"]
    if len(vv) != len(request_ids) or any(
        item["index"] != i or item["subquestion_id"] != request_ids[i]
        for i, item in enumerate(vv)
    ):
        raise _receipt_failure("coverage verdicts do not match ordered request", "COVERAGE_IDS")

    def refs(record: dict) -> tuple:
        result = []
        for ref in record["evidence_refs"]:
            body = source_bodies.get(ref["source_id"])
            if body is None or body_hashes.get(ref["source_id"]) != ref["body_sha256"]:
                raise _receipt_failure("evidence ref source/hash mismatch", "EVIDENCE_SOURCE_HASH")
            if ref["end"] > len(body) or body[ref["start"]:ref["end"]] != ref["quote"]:
                raise _receipt_failure(
                    "evidence ref span does not match exact body", "EVIDENCE_SPAN"
                )
            result.append(ref)
        return tuple(result)

    cr = {key: refs(item) for key, item in cv.items()}
    hr = {key: refs(item) for key, item in hv.items()}
    br = {key: refs(item) for key, item in bv.items()}
    vr = {i: refs(item) for i, item in enumerate(vv)}
    paths = {}
    for i, binding in enumerate(bindings):
        paths.setdefault(binding["field_path"], []).append(i)

    rejection_checks = {}
    verified_bindings, rejected_bindings = set(), {}
    for i, binding in enumerate(bindings):
        exact = any(
            r["source_id"] == binding["source_id"] and r["quote"] == binding["quote"]
            and r["start"] == binding["start"] and r["end"] == binding["end"]
            for r in br[i]
        )
        if bv[i]["outcome"] == "supported" and exact:
            verified_bindings.add(i)
        else:
            if bv[i]["outcome"] != "supported":
                _record_verifier_rejection(rejection_checks, bv[i]["outcome"])
            else:
                _record_rejection_check(rejection_checks, "missing_exact_reference")
            rejected_bindings[i] = (
                "verifier_{}: {}".format(bv[i]["outcome"], bv[i]["rationale"])
                if bv[i]["outcome"] != "supported"
                else "supported verdict lacks exact field binding reference"
            )

    claim_map = {x["claim_id"]: (i, x) for i, x in enumerate(claims)}
    claim_failures = {}
    for claim_id in claim_ids:
        i, claim = claim_map[claim_id]
        record, failures = cv[claim_id], []
        if record["outcome"] != "supported":
            _record_verifier_rejection(rejection_checks, record["outcome"])
            failures.append("verifier_{}: {}".format(record["outcome"], record["rationale"]))
        else:
            body = source_bodies.get(claim["source_id"])
            located = body is not None and body.strip() and body.count(claim["quote"]) == 1
            exact = located and any(
                r["source_id"] == claim["source_id"] and r["quote"] == claim["quote"]
                and r["start"] == body.find(claim["quote"])
                and r["end"] == r["start"] + len(claim["quote"])
                for r in cr[claim_id]
            )
            if not exact:
                _record_rejection_check(rejection_checks, "missing_exact_reference")
                failures.append("supported verdict lacks unique exact claim quote reference")
        for path in _paths_for_claim(claim, i):
            indexes = paths.get(path, ())
            if not indexes or not all(j in verified_bindings for j in indexes):
                _record_rejection_check(rejection_checks, "required_field_binding")
                failures.append("required field binding is not supported: {}".format(path))
        claim_failures[claim_id] = failures

    # Remove failed/missing dependency closures, then reject residual cycles.
    eligible = {cid for cid in claim_ids if not claim_failures[cid]}
    changed = True
    while changed:
        changed = False
        for cid in tuple(eligible):
            deps = claim_map[cid][1]["dependency_claim_ids"]
            if len(set(deps)) != len(deps) or any(dep not in eligible for dep in deps):
                eligible.remove(cid)
                _record_rejection_check(rejection_checks, "dependency_closure")
                claim_failures[cid].append("dependency closure contains duplicate or unverified IDs")
                changed = True
    dependants = {cid: [] for cid in eligible}
    remaining_deps = {cid: 0 for cid in eligible}
    for cid in eligible:
        for dep in claim_map[cid][1]["dependency_claim_ids"]:
            remaining_deps[cid] += 1
            dependants[dep].append(cid)
    queue = deque(cid for cid in claim_ids if cid in eligible and remaining_deps[cid] == 0)
    verified_claim_set = set()
    while queue:
        cid = queue.popleft()
        verified_claim_set.add(cid)
        for parent in dependants[cid]:
            remaining_deps[parent] -= 1
            if remaining_deps[parent] == 0:
                queue.append(parent)
    for cid in eligible - verified_claim_set:
        _record_rejection_check(rejection_checks, "dependency_cycle")
        claim_failures[cid].append("claim dependency cycle or incomplete closure")
    verified_claim_ids = tuple(cid for cid in claim_ids if cid in verified_claim_set)
    rejected_claims = tuple(
        (cid, "; ".join(claim_failures[cid]))
        for cid in claim_ids if cid not in verified_claim_set
    )

    def closure(roots: list) -> set:
        found, pending = set(), list(roots)
        while pending:
            cid = pending.pop()
            if cid in found:
                continue
            found.add(cid)
            if cid in claim_map:
                pending.extend(claim_map[cid][1]["dependency_claim_ids"])
        return found

    verified_hypotheses, rejected_hypotheses = [], []
    for i, hypothesis in enumerate(hypotheses):
        hid, record, failures = hypothesis["hypothesis_id"], hv[hypothesis["hypothesis_id"]], []
        if record["outcome"] != "supported":
            _record_verifier_rejection(rejection_checks, record["outcome"])
            failures.append("verifier_{}: {}".format(record["outcome"], record["rationale"]))
        support, contradiction = hypothesis["supporting_claim_ids"], hypothesis["contradicting_claim_ids"]
        reassessment = hypothesis["reassessment"]
        basis = [] if reassessment is None else reassessment["basis_claim_ids"]
        roots = support + contradiction + basis
        if (
            not support
            or len(set(support)) != len(support)
            or len(set(contradiction)) != len(contradiction)
            or len(set(basis)) != len(basis)
            or set(support) & set(contradiction)
        ):
            _record_rejection_check(rejection_checks, "hypothesis_roots")
            failures.append("hypothesis claim roots are empty, duplicated, or overlapping")
        if any(root not in verified_claim_set for root in roots):
            _record_rejection_check(rejection_checks, "hypothesis_roots")
            failures.append("hypothesis claim dependency closure is incomplete")
        support_closure = closure(support) if support else set()
        support_sources = {
            claim_map[cid][1]["source_id"] for cid in support_closure if cid in claim_map
        }
        if not support_sources.intersection(r["source_id"] for r in hr[hid]):
            _record_rejection_check(rejection_checks, "hypothesis_support_source")
            failures.append("hypothesis refs do not cite a supporting-closure source")
        for path in _paths_for_hypothesis(hypothesis, i):
            indexes = paths.get(path, ())
            if not indexes or not all(j in verified_bindings for j in indexes):
                _record_rejection_check(rejection_checks, "required_field_binding")
                failures.append("required field binding is not supported: {}".format(path))
        if failures:
            rejected_hypotheses.append((hid, "; ".join(dict.fromkeys(failures))))
        else:
            verified_hypotheses.append(hid)

    coverage_outcomes = []
    for i, item in enumerate(coverage):
        record, failures = vv[i], []
        if record["outcome"] != "supported":
            failures.append("verifier_{}: {}".format(record["outcome"], record["rationale"]))
        claim_roots = item["claim_ids"]
        if not claim_roots or any(cid not in verified_claim_set for cid in claim_roots):
            failures.append("coverage has no complete verified claim closure")
        used_sources = {
            claim_map[cid][1]["source_id"]
            for cid in closure(claim_roots) if cid in claim_map
        }
        if not used_sources.intersection(r["source_id"] for r in vr[i]):
            failures.append("coverage refs do not cite a verified claim source")
        if failures:
            status = "unresolved"
            rationale = "Host gate: " + "; ".join(dict.fromkeys(failures))
        else:
            status = "supported"
            rationale = "verifier_supported: " + record["rationale"]
        if len(rationale.encode("utf-8")) > max_string_bytes:
            raise ValueError("coverage rationale exceeds max_string_bytes")
        coverage_outcomes.append((i, item["subquestion_id"], status, rationale))

    receipt = {
        "schema_version": receipt_schema_version,
        "run_id": run_id,
        "canonical_input_hash": canonical_input_hash,
        "envelope_hash": envelope_hash,
        "source_body_hashes": expected_hashes,
        "validator_id": validator_id,
        "validator_version": validator_version,
        "verified_claim_ids": verified_claim_ids,
        "rejected_claims": rejected_claims,
        "verified_hypothesis_ids": tuple(verified_hypotheses),
        "rejected_hypotheses": tuple(rejected_hypotheses),
        "verified_binding_indices": tuple(sorted(verified_bindings)),
        "rejected_bindings": tuple(sorted(rejected_bindings.items())),
        "coverage_outcomes": tuple(coverage_outcomes),
    }
    validate_semantic_validation_receipt(
        parsed, receipt, run_id=run_id, canonical_input_hash=canonical_input_hash,
        request_subquestion_ids=request_ids, source_bodies=source_bodies,
        max_input_bytes=max_input_bytes, max_string_bytes=max_string_bytes,
        max_array_items=max_array_items,
        expected_schema_version=receipt_schema_version,
    )
    _emit_rejection_checks(rejection_checks)
    return receipt
