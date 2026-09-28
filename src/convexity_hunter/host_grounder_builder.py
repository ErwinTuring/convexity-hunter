"""Deterministic projection from a validated Host envelope into Event Intelligence."""

import datetime
import hashlib
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from .core_application import SourceSubmissionBatch
from .event_intelligence import (
    DistributionChangeMode,
    EventIntelligenceSubmission,
    EventSourceReference,
    EventStatement,
    EventStatementKind,
    EventUnderlyingHypothesis,
    HypothesisReassessment,
    MethodologizedDateRange,
    ReassessmentBasisKind,
    _validate_reassessment_provenance,
)
from .host_gate import validate_source_batch
from .host_grounder_receipt import (
    ValidatedEnvelopeSnapshot,
    validate_semantic_validation_receipt,
)
from .host_grounder_schema import parse_model_output_envelope
from .market_data import UnderlyingKey


__all__ = (
    "HostSourceBody",
    "CallerPolicyProvenance",
    "HostBuildContext",
    "CoverageSidecar",
    "FieldBindingSidecar",
    "HostBuildDiagnostic",
    "SemanticValidationRecord",
    "HostBuildResult",
    "build_host_grounder",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_RFC3339 = re.compile(
    r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})[Tt]"
    r"(?P<clock>(?:[01][0-9]|2[0-3]):[0-5][0-9]:(?P<second>[0-5][0-9]|60))"
    r"(?:\.(?P<fraction>[0-9]+))?"
    r"(?P<offset>[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)


def _exact_string(value: object, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError("{} must be a canonical nonempty string".format(label))
    value.encode("utf-8", errors="strict")
    return value


def _aware(value: object, label: str) -> None:
    if not isinstance(value, datetime.datetime):
        raise TypeError("{} must be a datetime".format(label))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("{} must be timezone-aware".format(label))


@dataclass(frozen=True)
class HostSourceBody:
    """Fetched body and exact Host-owned source metadata."""

    body: str
    body_sha256: str
    final_locator: str
    retrieved_at: datetime.datetime
    title: Optional[str] = None
    published_at: Optional[datetime.datetime] = None

    def __post_init__(self) -> None:
        if type(self.body) is not str:
            raise TypeError("body must have exact type str")
        body_hash = hashlib.sha256(self.body.encode("utf-8", errors="strict")).hexdigest()
        if type(self.body_sha256) is not str or _SHA256.fullmatch(self.body_sha256) is None:
            raise ValueError("body_sha256 must be a lowercase SHA-256 digest")
        if self.body_sha256 != body_hash:
            raise ValueError("body_sha256 does not match the exact UTF-8 body")
        _exact_string(self.final_locator, "final_locator")
        _aware(self.retrieved_at, "retrieved_at")
        if self.title is not None:
            _exact_string(self.title, "title")
        if self.published_at is not None:
            _aware(self.published_at, "published_at")


@dataclass(frozen=True)
class CallerPolicyProvenance:
    """Explicit caller authorization bound to one run/input and reassessment."""

    run_id: str
    canonical_input_hash: str
    reassessment_by: datetime.date
    rationale: str
    authorization_source: str

    def __post_init__(self) -> None:
        _exact_string(self.run_id, "caller policy run_id")
        if type(self.canonical_input_hash) is not str or _SHA256.fullmatch(
            self.canonical_input_hash
        ) is None:
            raise ValueError("caller policy input hash must be lowercase SHA-256")
        if type(self.reassessment_by) is not datetime.date:
            raise TypeError("caller policy reassessment_by must have exact type date")
        _exact_string(self.rationale, "caller policy rationale")
        _exact_string(self.authorization_source, "caller policy authorization_source")


@dataclass(frozen=True)
class HostBuildContext:
    """Immutable Host-owned context for one event build."""

    raw_input: object
    submission_id: str
    event_id: str
    producer_id: str
    producer_version: str
    observed_at: datetime.datetime
    source_bodies: Mapping[str, HostSourceBody]
    run_id: str
    canonical_input_hash: str
    event_description_binding: Optional[str] = None
    event_date_range: Optional[MethodologizedDateRange] = None
    underlying_bindings: Optional[Mapping[Tuple[str, str], Tuple[UnderlyingKey, object]]] = None
    caller_policy_provenance: Optional[CallerPolicyProvenance] = None

    def __post_init__(self) -> None:
        for field in (
            "submission_id", "event_id", "producer_id", "producer_version", "run_id"
        ):
            _exact_string(getattr(self, field), field)
        if type(self.canonical_input_hash) is not str or _SHA256.fullmatch(
            self.canonical_input_hash
        ) is None:
            raise ValueError("canonical_input_hash must be lowercase SHA-256")
        _aware(self.observed_at, "observed_at")
        if self.event_description_binding is not None:
            _exact_string(self.event_description_binding, "event_description_binding")
        if self.event_date_range is not None:
            if type(self.event_date_range) is not MethodologizedDateRange:
                raise TypeError("event_date_range must be MethodologizedDateRange")
            if MethodologizedDateRange(
                self.event_date_range.start_date,
                self.event_date_range.end_date,
                self.event_date_range.methodology,
            ) != self.event_date_range:
                raise ValueError("event_date_range is not intrinsically valid")

        if not isinstance(self.source_bodies, Mapping):
            raise TypeError("source_bodies must be a mapping")
        sources = {}
        for source_id, source in self.source_bodies.items():
            _exact_string(source_id, "source_id")
            if type(source) is not HostSourceBody:
                raise TypeError("source body values must be HostSourceBody records")
            HostSourceBody(
                source.body, source.body_sha256, source.final_locator,
                source.retrieved_at, source.title, source.published_at
            )
            sources[source_id] = source
        object.__setattr__(self, "source_bodies", MappingProxyType(sources))

        bindings = {} if self.underlying_bindings is None else self.underlying_bindings
        if not isinstance(bindings, Mapping):
            raise TypeError("underlying_bindings must be a mapping")
        exact_bindings = {}
        for pair, value in bindings.items():
            if (
                type(pair) is not tuple
                or len(pair) != 2
                or type(value) is not tuple
                or len(value) != 2
            ):
                raise ValueError(
                    "underlying bindings need exact pairs and (UnderlyingKey, reference) values"
                )
            hypothesis_id = _exact_string(pair[0], "underlying hypothesis_id")
            symbol = _exact_string(pair[1], "underlying symbol")
            key, reference = value
            if type(key) is not UnderlyingKey or reference is None:
                raise ValueError("underlying binding needs an exact key and evidence reference")
            if UnderlyingKey(
                key.symbol, key.listing_mic, key.security_type, key.currency
            ) != key:
                raise ValueError("underlying binding key is not intrinsically valid")
            if type(reference) is str and not reference.strip():
                raise ValueError("underlying evidence reference must be nonempty")
            exact_bindings[(hypothesis_id, symbol)] = (key, reference)
        object.__setattr__(self, "underlying_bindings", MappingProxyType(exact_bindings))
        if self.caller_policy_provenance is not None and type(
            self.caller_policy_provenance
        ) is not CallerPolicyProvenance:
            raise TypeError("caller_policy_provenance must be CallerPolicyProvenance or None")
        if self.caller_policy_provenance is not None:
            policy = self.caller_policy_provenance
            CallerPolicyProvenance(
                policy.run_id, policy.canonical_input_hash, policy.reassessment_by,
                policy.rationale, policy.authorization_source
            )


@dataclass(frozen=True)
class CoverageSidecar:
    index: int
    subquestion_id: str
    model_status: str
    validator_status: str
    claim_ids: Tuple[str, ...]
    gap: Optional[str]
    validator_rationale: str

    @property
    def status(self) -> str:
        return self.validator_status


@dataclass(frozen=True)
class FieldBindingSidecar:
    index: int
    field_path: str
    source_id: str
    quote: str
    start: int
    end: int
    semantic_role: str
    model_status: str
    validator_status: str
    validator_reason: Optional[str]


@dataclass(frozen=True)
class HostBuildDiagnostic:
    code: str
    subject_type: Optional[str]
    subject_id: Optional[str]
    reason: str


@dataclass(frozen=True)
class SemanticValidationRecord:
    run_id: str
    canonical_input_hash: str
    envelope_hash: str
    receipt: Mapping[str, object]
    snapshot: ValidatedEnvelopeSnapshot


@dataclass(frozen=True)
class HostBuildResult:
    context: HostBuildContext
    raw_input: object
    submission: Optional[EventIntelligenceSubmission]
    source_batch: Optional[SourceSubmissionBatch]
    coverage: Tuple[CoverageSidecar, ...]
    field_bindings: Tuple[FieldBindingSidecar, ...]
    semantic_validation: SemanticValidationRecord
    diagnostics: Tuple[HostBuildDiagnostic, ...]


def _published_at_matches(value: str, registered: Optional[datetime.datetime]) -> bool:
    if registered is None:
        return False
    match = _RFC3339.fullmatch(value)
    if match is None or match.group("second") == "60":
        return False
    fraction = match.group("fraction") or ""
    if len(fraction) > 6 and any(char != "0" for char in fraction[6:]):
        return False
    clock = match.group("clock")
    if fraction:
        clock += "." + fraction[:6]
    offset = match.group("offset")
    text = match.group("date") + "T" + clock
    text += "+00:00" if offset.lower() == "z" else offset
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return False
    return parsed.astimezone(datetime.timezone.utc) == registered.astimezone(
        datetime.timezone.utc
    )


def build_host_grounder(
    envelope: Mapping[str, object],
    receipt: Mapping[str, object],
    *,
    context: HostBuildContext,
    request_subquestion_ids: Tuple[str, ...],
    max_input_bytes: int,
    max_string_bytes: int,
    max_array_items: int,
) -> HostBuildResult:
    """Project verified closures into one batch.

    Requires a receipt from a trusted Host semantic validator; this projection
    cannot authenticate its issuer or establish factual truth.
    """
    if type(context) is not HostBuildContext:
        raise TypeError("context must be HostBuildContext")
    observed_at_utc_date = context.observed_at.astimezone(datetime.timezone.utc).date()
    if not isinstance(receipt, Mapping):
        raise TypeError("receipt must be a mapping")
    receipt = MappingProxyType(dict(receipt))
    bodies = MappingProxyType(
        {source_id: source.body for source_id, source in context.source_bodies.items()}
    )
    snapshot = validate_semantic_validation_receipt(
        envelope,
        receipt,
        run_id=context.run_id,
        canonical_input_hash=context.canonical_input_hash,
        request_subquestion_ids=request_subquestion_ids,
        source_bodies=bodies,
        max_input_bytes=max_input_bytes,
        max_string_bytes=max_string_bytes,
        max_array_items=max_array_items,
    )
    # The caller's parsed mapping is mutable. Only the validated snapshot feeds projection.
    data = parse_model_output_envelope(
        snapshot.canonical_bytes.decode("utf-8"),
        max_input_bytes,
        max_string_bytes=max_string_bytes,
        max_array_items=max_array_items,
    )
    semantic = SemanticValidationRecord(
        context.run_id, context.canonical_input_hash, snapshot.envelope_hash, receipt, snapshot
    )
    outcomes = {entry[0]: entry for entry in receipt["coverage_outcomes"]}
    coverage = tuple(
        CoverageSidecar(
            i, item["subquestion_id"], item["status"], outcomes[i][2],
            tuple(item["claim_ids"]), item["gap"], outcomes[i][3]
        )
        for i, item in enumerate(data["coverage"])
    )
    verified_bindings = set(receipt["verified_binding_indices"])
    rejected_bindings = dict(receipt["rejected_bindings"])
    field_sidecars = tuple(
        FieldBindingSidecar(
            i, item["field_path"], item["source_id"], item["quote"],
            item["start"], item["end"], item["semantic_role"], item["status"],
            "verified" if i in verified_bindings else "rejected", rejected_bindings.get(i)
        )
        for i, item in enumerate(data["field_bindings"])
    )
    verified_claims = set(receipt["verified_claim_ids"])
    rejected_claims = dict(receipt["rejected_claims"])
    verified_hypotheses = set(receipt["verified_hypothesis_ids"])
    rejected_hypotheses = dict(receipt["rejected_hypotheses"])
    bindings_by_path = {}
    for i, item in enumerate(data["field_bindings"]):
        bindings_by_path.setdefault(item["field_path"], []).append(i)
    diagnostics = []

    def has_verified_binding(path: str, subject: str, subject_id: str) -> bool:
        indexes = bindings_by_path.get(path, ())
        if indexes and all(i in verified_bindings for i in indexes):
            return True
        reasons = tuple(rejected_bindings[i] for i in indexes if i in rejected_bindings)
        diagnostics.append(
            HostBuildDiagnostic(
                "FIELD_BINDING_NOT_VERIFIED" if indexes else "FIELD_BINDING_MISSING",
                subject,
                subject_id,
                "{}: {}".format(path, reasons or "no verified binding"),
            )
        )
        return False

    readable_sources = {
        source_id for source_id, source in context.source_bodies.items() if source.body.strip()
    }
    if not readable_sources:
        diagnostics.append(
            HostBuildDiagnostic(
                "NO_READABLE_SOURCE_BODY", None, None,
                "Host source registry is empty of readable bodies"
            )
        )

    claims = data["claims"]
    claims_by_id = {claim["claim_id"]: claim for claim in claims}
    claim_errors = {}

    def claim_error(claim_id: str, reason: str) -> None:
        claim_errors.setdefault(claim_id, []).append(reason)

    for index, claim in enumerate(claims):
        claim_id = claim["claim_id"]
        if claim_id not in verified_claims:
            reason = rejected_claims[claim_id]
            claim_error(claim_id, reason)
            diagnostics.append(
                HostBuildDiagnostic(
                    "CLAIM_REJECTED_BY_VALIDATOR", "claim", claim_id, reason
                )
            )
        source = context.source_bodies.get(claim["source_id"])
        if source is None or claim["source_id"] not in readable_sources:
            claim_error(claim_id, "claim has no readable Host-registered source body")
        if not claim_id or claim_id != claim_id.strip():
            claim_error(claim_id, "EI normalization would alter claim_id")
        if not claim["text"].strip() or claim["text"] != claim["text"].strip():
            claim_error(claim_id, "EI normalization would alter or reject claim text")
        deps = claim["dependency_claim_ids"]
        if len(set(deps)) != len(deps):
            claim_error(claim_id, "duplicate dependency IDs cannot be projected")
        if claim["kind"] == "observed_fact" and deps:
            claim_error(claim_id, "EI observed facts cannot declare dependencies")
        if claim["published_at"] is not None and (
            source is None or not _published_at_matches(claim["published_at"], source.published_at)
        ):
            claim_error(claim_id, "DTO publication time conflicts with Host source metadata")
        paths = []
        if claim["event_date"] is not None:
            paths.append("/claims/{}/event_date".format(index))
        paths.extend(
            "/claims/{}/entity_refs/{}".format(index, j)
            for j, _value in enumerate(claim["entity_refs"])
        )
        for path in paths:
            if not has_verified_binding(path, "claim", claim_id):
                claim_error(claim_id, "non-null claim field lacks fully verified binding: " + path)

    for claim_id, reasons in claim_errors.items():
        if claim_id in verified_claims:
            diagnostics.append(
                HostBuildDiagnostic("CLAIM_NOT_PROJECTABLE", "claim", claim_id, "; ".join(reasons))
            )

    closure_cache = {}

    def claim_closure(root: str):
        if root in closure_cache:
            return closure_cache[root]
        found, visiting = set(), set()
        failure = None

        def visit(claim_id: str) -> bool:
            nonlocal failure
            if claim_id in visiting:
                failure = "claim dependency cycle"
                return False
            if claim_id in found:
                return True
            claim = claims_by_id.get(claim_id)
            if claim is None:
                failure = "claim/dependency ID is absent from envelope"
                return False
            if claim_id in claim_errors:
                failure = "; ".join(claim_errors[claim_id])
                return False
            visiting.add(claim_id)
            for dependency in claim["dependency_claim_ids"]:
                if not visit(dependency):
                    return False
            visiting.remove(claim_id)
            found.add(claim_id)
            return True

        valid = visit(root)
        result = (valid, frozenset(found), failure)
        closure_cache[root] = result
        return result

    kept_hypotheses = []
    kept_claim_ids = set()
    for index, item in enumerate(data["hypotheses"]):
        hypothesis_id = item["hypothesis_id"]
        if hypothesis_id not in verified_hypotheses:
            diagnostics.append(
                HostBuildDiagnostic(
                    "HYPOTHESIS_REJECTED_BY_VALIDATOR", "hypothesis", hypothesis_id,
                    rejected_hypotheses[hypothesis_id]
                )
            )
            continue
        failures = []
        if not hypothesis_id or hypothesis_id != hypothesis_id.strip():
            failures.append("EI normalization would alter hypothesis_id")
        for key in ("impact_path", "distribution_hypothesis", "contradiction_review"):
            value = item[key]
            if value is not None and value != value.strip():
                failures.append("EI normalization would alter " + key)
        for key in ("uncertainties", "falsification_conditions"):
            values = item[key]
            if (
                any(not value or value != value.strip() for value in values)
                or len(set(values)) != len(values)
            ):
                failures.append(key + " contains text EI would alter or reject")

        support = item["supporting_claim_ids"]
        contradiction = item["contradicting_claim_ids"]
        reassessment_data = item["reassessment"]
        basis = [] if reassessment_data is None else reassessment_data["basis_claim_ids"]
        if not support:
            failures.append("hypothesis has no supporting claim closure")
        if len(set(support)) != len(support) or len(set(contradiction)) != len(contradiction):
            failures.append("supporting or contradicting IDs contain duplicates")
        if set(support) & set(contradiction):
            failures.append("supporting and contradicting IDs overlap")
        if len(set(basis)) != len(basis):
            failures.append("reassessment basis IDs contain duplicates")

        for key in ("impact_path", "distribution_mode", "distribution_hypothesis"):
            if item[key] is not None and not has_verified_binding(
                "/hypotheses/{}/{}".format(index, key), "hypothesis", hypothesis_id
            ):
                failures.append(key + " lacks fully verified field bindings")
        window_data = item["expected_window"]
        if window_data is not None:
            for key in ("start_date", "end_date"):
                if not has_verified_binding(
                    "/hypotheses/{}/expected_window/{}".format(index, key),
                    "hypothesis", hypothesis_id
                ):
                    failures.append("expected_window date lacks verified binding")
            if window_data["methodology"] != window_data["methodology"].strip():
                failures.append("EI normalization would alter window methodology")
            start = datetime.date.fromisoformat(window_data["start_date"])
            end = datetime.date.fromisoformat(window_data["end_date"])
            if start > end:
                failures.append("expected_window start_date is after end_date")

        reassessment_date = basis_kind = methodology = None
        caller_authorized = False
        if reassessment_data is not None:
            date_path = "/hypotheses/{}/reassessment/reassessment_by".format(index)
            if not has_verified_binding(date_path, "hypothesis", hypothesis_id):
                failures.append("reassessment date lacks verified binding")
            reassessment_date = datetime.date.fromisoformat(reassessment_data["reassessment_by"])
            basis_kind = ReassessmentBasisKind(reassessment_data["basis_kind"])
            methodology = reassessment_data["methodology"]
            if methodology != methodology.strip():
                failures.append("EI normalization would alter reassessment methodology")
            if basis_kind is ReassessmentBasisKind.SOURCE_BACKED_MILESTONE:
                expected = "source-backed-milestone:{}:{}".format(
                    basis[0] if len(basis) == 1 else "", reassessment_date.isoformat()
                )
                if len(basis) != 1 or methodology != expected:
                    failures.append(
                        "source-backed reassessment methodology or basis is invalid"
                    )
            else:
                prefix = "caller-research-policy-assumption:{}:".format(
                    reassessment_date.isoformat()
                )
                if not methodology.startswith(prefix):
                    failures.append("caller-policy methodology is invalid")
                else:
                    policy = context.caller_policy_provenance
                    rationale = methodology[len(prefix):]
                    caller_authorized = policy is not None and (
                        policy.run_id == context.run_id
                        and policy.canonical_input_hash == context.canonical_input_hash
                        and policy.reassessment_by == reassessment_date
                        and policy.rationale == rationale
                    )
                    if not caller_authorized:
                        diagnostics.append(
                            HostBuildDiagnostic(
                                "CALLER_POLICY_PROVENANCE_MISMATCH", "hypothesis", hypothesis_id,
                                "DTO reassessment retained in sidecar and omitted from EI"
                            )
                        )
                    elif not basis:
                        failures.append("authorized caller-policy reassessment needs basis claims")

        roots = tuple(support) + tuple(contradiction) + tuple(basis)
        all_closure, support_closure = set(), set()
        for root in roots:
            valid, closure, reason = claim_closure(root)
            if not valid:
                failures.append("claim {} closure is not projectable: {}".format(root, reason))
            else:
                all_closure.update(closure)
                if root in support:
                    support_closure.update(closure)
        if support and not support_closure:
            failures.append("hypothesis has no source-backed supporting closure")

        if (
            reassessment_data is not None
            and (
                basis_kind is ReassessmentBasisKind.SOURCE_BACKED_MILESTONE
                or caller_authorized
            )
            and reassessment_date < observed_at_utc_date
        ):
            failures.append(
                "reassessment_by precedes observed_at UTC calendar date"
            )

        reassessment = None
        if (
            reassessment_data is not None
            and not failures
            and (basis_kind is ReassessmentBasisKind.SOURCE_BACKED_MILESTONE or caller_authorized)
        ):
            try:
                reassessment = HypothesisReassessment(
                    reassessment_date, methodology, basis_kind, tuple(basis)
                )
            except (TypeError, ValueError) as exc:
                failures.append("invalid EI reassessment: {}".format(exc))

        if failures:
            diagnostics.append(
                HostBuildDiagnostic(
                    "HYPOTHESIS_NOT_PROJECTED", "hypothesis", hypothesis_id,
                    "; ".join(dict.fromkeys(failures))
                )
            )
            continue

        symbol = item["underlying_symbol"]
        underlying_key = None
        if symbol is not None:
            verified = has_verified_binding(
                "/hypotheses/{}/underlying_symbol".format(index), "hypothesis", hypothesis_id
            )
            candidate = context.underlying_bindings.get((hypothesis_id, symbol))
            if verified and candidate is not None and candidate[0].symbol == symbol:
                underlying_key = candidate[0]
            else:
                diagnostics.append(
                    HostBuildDiagnostic(
                        "UNDERLYING_UNRESOLVED", "hypothesis", hypothesis_id,
                        "no exact verified Host binding for the asserted symbol"
                    )
                )
        expected_window = None
        if window_data is not None:
            expected_window = MethodologizedDateRange(
                datetime.date.fromisoformat(window_data["start_date"]),
                datetime.date.fromisoformat(window_data["end_date"]),
                window_data["methodology"],
            )
        try:
            projected = EventUnderlyingHypothesis(
                hypothesis_id=hypothesis_id,
                underlying_key=underlying_key,
                impact_path=item["impact_path"],
                distribution_mode=(
                    None
                    if item["distribution_mode"] is None
                    else DistributionChangeMode(item["distribution_mode"])
                ),
                distribution_hypothesis=item["distribution_hypothesis"],
                expected_window=expected_window,
                reassessment=reassessment,
                supporting_statement_ids=tuple(support),
                contradicting_statement_ids=tuple(contradiction),
                contradiction_review=item["contradiction_review"],
                uncertainties=tuple(item["uncertainties"]),
                falsification_conditions=tuple(item["falsification_conditions"]),
            )
        except (TypeError, ValueError) as exc:
            diagnostics.append(
                HostBuildDiagnostic(
                    "HYPOTHESIS_NOT_PROJECTED", "hypothesis", hypothesis_id,
                    str(exc)
                )
            )
            continue
        if reassessment is not None:
            # Reuse EI's own provenance rule; this adapter does not copy its
            # source-backed/caller-policy closure semantics or assess acceptance.
            statement_map = {
                claim_id: EventStatement(
                    claim_id,
                    EventStatementKind.OBSERVED_FACT
                    if claims_by_id[claim_id]["kind"] == "observed_fact"
                    else EventStatementKind.INTERPRETATION,
                    claims_by_id[claim_id]["text"],
                    (claims_by_id[claim_id]["source_id"],),
                    tuple(claims_by_id[claim_id]["dependency_claim_ids"]),
                )
                for claim_id in all_closure
            }
            try:
                _validate_reassessment_provenance(projected, statement_map)
            except ValueError as exc:
                diagnostics.append(
                    HostBuildDiagnostic(
                        "HYPOTHESIS_NOT_PROJECTED", "hypothesis", hypothesis_id,
                        "EI reassessment provenance rejected: {}".format(exc)
                    )
                )
                continue
        kept_hypotheses.append(projected)
        kept_claim_ids.update(all_closure)

    if not readable_sources or not kept_hypotheses:
        if readable_sources:
            diagnostics.append(
                HostBuildDiagnostic(
                    "NO_PROJECTABLE_HYPOTHESIS", None, None,
                    "no verified hypothesis has a source-backed claim closure"
                )
            )
        return HostBuildResult(
            context, context.raw_input, None, None, coverage, field_sidecars, semantic,
            tuple(diagnostics)
        )

    statements = []
    used_sources = set()
    for claim in claims:
        if claim["claim_id"] not in kept_claim_ids:
            continue
        used_sources.add(claim["source_id"])
        statements.append(
            EventStatement(
                claim["claim_id"],
                (
                    EventStatementKind.OBSERVED_FACT
                    if claim["kind"] == "observed_fact"
                    else EventStatementKind.INTERPRETATION
                ),
                claim["text"],
                (claim["source_id"],),
                tuple(claim["dependency_claim_ids"]),
            )
        )
    sources = tuple(
        EventSourceReference(
            source_id,
            context.source_bodies[source_id].final_locator,
            context.source_bodies[source_id].title,
            context.source_bodies[source_id].published_at,
        )
        for source_id in sorted(used_sources)
    )
    statement_by_id = {statement.statement_id: statement for statement in statements}
    description = None
    if context.event_description_binding is not None:
        statement = statement_by_id.get(context.event_description_binding)
        if (
            statement is not None
            and statement.kind is EventStatementKind.OBSERVED_FACT
            and statement.source_ids
        ):
            description = statement.text
        else:
            diagnostics.append(
                HostBuildDiagnostic(
                    "EVENT_DESCRIPTION_BINDING_UNAVAILABLE", "claim",
                    context.event_description_binding,
                    "description binding is not a surviving source-backed observed fact"
                )
            )
    try:
        submission = EventIntelligenceSubmission(
            context.submission_id, context.event_id, context.producer_id,
            context.producer_version, context.observed_at, description,
            context.event_date_range, sources, tuple(statements), tuple(kept_hypotheses)
        )
        batch = SourceSubmissionBatch(context.raw_input, (submission,))
    except (TypeError, ValueError) as exc:
        diagnostics.append(
            HostBuildDiagnostic(
                "SUBMISSION_CONSTRUCTION_FAILED", None, None, str(exc)
            )
        )
        return HostBuildResult(
            context, context.raw_input, None, None, coverage, field_sidecars, semantic,
            tuple(diagnostics)
        )
    gate = validate_source_batch(context.raw_input, batch)
    if not gate.allowed:
        diagnostics.append(
            HostBuildDiagnostic("SOURCE_BATCH_REJECTED", None, None, ",".join(gate.reason_codes))
        )
        return HostBuildResult(
            context, context.raw_input, None, None, coverage, field_sidecars, semantic,
            tuple(diagnostics)
        )
    return HostBuildResult(
        context, context.raw_input, submission, batch, coverage, field_sidecars, semantic,
        tuple(diagnostics)
    )
