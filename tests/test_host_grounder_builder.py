import copy
import datetime
import hashlib
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

import convexity_hunter.host_grounder_builder as builder_module
from convexity_hunter.core_application import SourceSubmissionBatch
from convexity_hunter.event_intelligence import (
    MethodologizedDateRange,
    ReassessmentBasisKind,
)
from convexity_hunter.host_grounder_builder import (
    CallerPolicyProvenance,
    HostBuildContext,
    HostSourceBody,
    build_host_grounder,
)
from convexity_hunter.host_grounder_schema import parse_model_output_envelope
from convexity_hunter.market_data import UnderlyingKey, UnderlyingSecurityType


_RUN_ID = "run-42"
_INPUT_HASH = "a" * 64
_NOW = datetime.datetime(2026, 9, 28, 9, 30, tzinfo=datetime.timezone.utc)
_LIMITS = {
    "max_input_bytes": 100_000,
    "max_string_bytes": 10_000,
    "max_array_items": 100,
}


def _claim(claim_id, *, kind="observed_fact", **updates):
    value = {
        "claim_id": claim_id,
        "kind": kind,
        "source_id": "source-1",
        "locator": "model locator is not EI provenance",
        "quote": "quote-{}".format(claim_id),
        "text": "Text for {}.".format(claim_id),
        "entity_refs": [],
        "event_date": None,
        "published_at": None,
        "dependency_claim_ids": [],
        "uncertainty": [],
        "falsification_conditions": [],
    }
    value.update(updates)
    return value


def _hypothesis(hypothesis_id="hyp-1", *, symbol="ACME", **updates):
    value = {
        "hypothesis_id": hypothesis_id,
        "underlying_symbol": symbol,
        "impact_path": None,
        "distribution_mode": None,
        "distribution_hypothesis": "A possible distribution shift",
        "expected_window": None,
        "reassessment": None,
        "supporting_claim_ids": ["claim-2"],
        "contradicting_claim_ids": [],
        "contradiction_review": None,
        "uncertainties": [],
        "falsification_conditions": [],
    }
    value.update(updates)
    return value


def _base_body(claims, hypotheses):
    values = [claim["quote"] for claim in claims]
    for hypothesis in hypotheses:
        for key in (
            "underlying_symbol",
            "impact_path",
            "distribution_mode",
            "distribution_hypothesis",
        ):
            if hypothesis[key] is not None:
                values.append(hypothesis[key])
        window = hypothesis["expected_window"]
        if window is not None:
            values.extend((window["start_date"], window["end_date"]))
        reassessment = hypothesis["reassessment"]
        if reassessment is not None:
            values.append(reassessment["reassessment_by"])
    for claim in claims:
        if claim["event_date"] is not None:
            values.append(claim["event_date"])
        values.extend(claim["entity_refs"])
    # Preserve first occurrence only; field-binding spans need exact slices,
    # not unique quotes (claim quote uniqueness is separately checked).
    return " | ".join(dict.fromkeys(values))


def _binding(path, quote, body, *, status="supported", source_id="source-1"):
    start = body.find(quote)
    if start < 0:
        raise AssertionError("binding quote missing from synthetic source body")
    return {
        "field_path": path,
        "source_id": source_id,
        "quote": quote,
        "start": start,
        "end": start + len(quote),
        "semantic_role": (
            "hypothesis"
            if path.startswith("/hypotheses/")
            and any(
                path.endswith("/" + field)
                for field in ("impact_path", "distribution_mode", "distribution_hypothesis")
            )
            else "date"
            if path.endswith("/event_date")
            or "/expected_window/" in path
            or path.endswith("/reassessment/reassessment_by")
            else "entity"
        ),
        "status": status,
    }


def _default_bindings(hypotheses, claims, body):
    result = []
    for index, hypothesis in enumerate(hypotheses):
        for key in (
            "impact_path",
            "distribution_mode",
            "distribution_hypothesis",
        ):
            if hypothesis[key] is not None:
                result.append(
                    _binding(
                        "/hypotheses/{}/{}".format(index, key),
                        hypothesis[key],
                        body,
                    )
                )
        symbol = hypothesis["underlying_symbol"]
        if symbol is not None:
            result.append(
                _binding(
                    "/hypotheses/{}/underlying_symbol".format(index),
                    symbol,
                    body,
                )
            )
        window = hypothesis["expected_window"]
        if window is not None:
            for key in ("start_date", "end_date"):
                result.append(
                    _binding(
                        "/hypotheses/{}/expected_window/{}".format(index, key),
                        window[key],
                        body,
                    )
                )
        reassessment = hypothesis["reassessment"]
        if reassessment is not None:
            result.append(
                _binding(
                    "/hypotheses/{}/reassessment/reassessment_by".format(index),
                    reassessment["reassessment_by"],
                    body,
                )
            )
    for index, claim in enumerate(claims):
        if claim["event_date"] is not None:
            result.append(
                _binding(
                    "/claims/{}/event_date".format(index),
                    claim["event_date"],
                    body,
                )
            )
        for entity_index, entity in enumerate(claim["entity_refs"]):
            result.append(
                _binding(
                    "/claims/{}/entity_refs/{}".format(index, entity_index),
                    entity,
                    body,
                )
            )
    return result


def _source(body, *, published_at=None):
    return HostSourceBody(
        body=body,
        body_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        final_locator="https://publisher.example/final",
        retrieved_at=_NOW,
        title="Host title",
        published_at=published_at,
    )


def _canonical_hash(envelope):
    encoded = json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _case(
    *,
    claims=None,
    hypotheses=None,
    field_bindings=None,
    source_body=None,
    verified_claim_ids=None,
    rejected_claims=(),
    verified_hypothesis_ids=None,
    rejected_hypotheses=(),
    verified_binding_indices=None,
    rejected_bindings=(),
    event_description_binding="claim-1",
    underlying_bindings=None,
    caller_policy_provenance=None,
    event_date_range=None,
    coverage_status="contradicted",
    validator_coverage_status="supported",
    source_published_at=None,
):
    if claims is None:
        claims = [
            _claim("claim-1", text="A source-reported event occurred."),
            _claim(
                "claim-2",
                kind="interpretation",
                text="The event may alter future outcomes.",
                dependency_claim_ids=["claim-1"],
            ),
        ]
    if hypotheses is None:
        hypotheses = [_hypothesis()]
    claims = copy.deepcopy(claims)
    hypotheses = copy.deepcopy(hypotheses)
    if source_body is None:
        source_body = _base_body(claims, hypotheses)
    if field_bindings is None:
        field_bindings = _default_bindings(hypotheses, claims, source_body)
    else:
        field_bindings = copy.deepcopy(field_bindings)

    coverage = [
        {
            "subquestion_id": "question-1",
            "status": coverage_status,
            "claim_ids": ["claim-1"],
            "gap": "model gap text",
        }
    ]
    envelope_dict = {
        "schema_version": "grounder-output-v0.1",
        "stage": "semantic",
        "request_id": "request-1",
        "claims": claims,
        "hypotheses": hypotheses,
        "coverage": coverage,
        "field_bindings": field_bindings,
    }
    parsed = parse_model_output_envelope(
        json.dumps(envelope_dict, ensure_ascii=False, separators=(",", ":")),
        **_LIMITS,
    )

    body_hash = hashlib.sha256(source_body.encode("utf-8")).hexdigest()
    all_claim_ids = tuple(claim["claim_id"] for claim in claims)
    all_hypothesis_ids = tuple(hypothesis["hypothesis_id"] for hypothesis in hypotheses)
    all_binding_indices = tuple(range(len(field_bindings)))
    if verified_claim_ids is None:
        verified_claim_ids = all_claim_ids
    if verified_hypothesis_ids is None:
        verified_hypothesis_ids = all_hypothesis_ids
    if verified_binding_indices is None:
        rejected_indices = {entry[0] for entry in rejected_bindings}
        verified_binding_indices = tuple(
            index for index in all_binding_indices if index not in rejected_indices
        )
    if isinstance(rejected_claims, dict):
        rejected_claims = tuple(rejected_claims.items())
    if isinstance(rejected_hypotheses, dict):
        rejected_hypotheses = tuple(rejected_hypotheses.items())
    receipt = {
        "schema_version": "semantic-validation-v0.1",
        "run_id": _RUN_ID,
        "canonical_input_hash": _INPUT_HASH,
        "envelope_hash": _canonical_hash(parsed),
        "source_body_hashes": (("source-1", body_hash),),
        "validator_id": "synthetic-independent-validator",
        "validator_version": "test-v0.1",
        "verified_claim_ids": tuple(verified_claim_ids),
        "rejected_claims": tuple(rejected_claims),
        "verified_hypothesis_ids": tuple(verified_hypothesis_ids),
        "rejected_hypotheses": tuple(rejected_hypotheses),
        "verified_binding_indices": tuple(verified_binding_indices),
        "rejected_bindings": tuple(rejected_bindings),
        "coverage_outcomes": (
            (0, "question-1", validator_coverage_status, "validator rationale"),
        ),
    }
    raw_input = object()
    if underlying_bindings is None:
        underlying_bindings = {
            (hypothesis["hypothesis_id"], hypothesis["underlying_symbol"]): (
                UnderlyingKey(
                    symbol=hypothesis["underlying_symbol"],
                    listing_mic="XNAS",
                    security_type=UnderlyingSecurityType.EQUITY,
                    currency="USD",
                ),
                "verified listing reference",
            )
            for hypothesis in hypotheses
            if hypothesis["underlying_symbol"] is not None
        }
    context = HostBuildContext(
        raw_input=raw_input,
        submission_id="submission-1",
        event_id="event-1",
        producer_id="host-grounder",
        producer_version="0.1",
        observed_at=_NOW,
        source_bodies={
            "source-1": _source(
                source_body, published_at=source_published_at
            )
        },
        run_id=_RUN_ID,
        canonical_input_hash=_INPUT_HASH,
        event_description_binding=event_description_binding,
        event_date_range=event_date_range,
        underlying_bindings=underlying_bindings,
        caller_policy_provenance=caller_policy_provenance,
    )
    return parsed, receipt, context


def _build(case, **updates):
    envelope, receipt, context = case
    return build_host_grounder(
        envelope,
        receipt,
        context=context,
        request_subquestion_ids=("question-1",),
        **_LIMITS,
        **updates
    )


class HostGrounderBuilderTests(unittest.TestCase):
    def test_projects_transitive_claim_closure_and_exact_host_source_metadata(self):
        claims = [
            _claim("claim-1", text="A source-reported event occurred."),
            _claim(
                "claim-2",
                kind="interpretation",
                text="A first interpretation.",
                dependency_claim_ids=["claim-1"],
            ),
            _claim(
                "claim-3",
                kind="interpretation",
                text="A second interpretation.",
                dependency_claim_ids=["claim-2"],
            ),
        ]
        case = _case(claims=claims, hypotheses=[_hypothesis(supporting_claim_ids=["claim-3"])])

        result = _build(case)

        self.assertIsNotNone(result.submission)
        self.assertEqual(
            {statement.statement_id for statement in result.submission.statements},
            {"claim-1", "claim-2", "claim-3"},
        )
        statement = next(
            item for item in result.submission.statements
            if item.statement_id == "claim-3"
        )
        self.assertEqual(statement.dependency_statement_ids, ("claim-2",))
        source, = result.submission.sources
        self.assertEqual(source.locator, "https://publisher.example/final")
        self.assertEqual(source.title, "Host title")
        self.assertIsNone(source.published_at)
        self.assertEqual(result.submission.event_description, "A source-reported event occurred.")
        self.assertIs(type(result.source_batch), SourceSubmissionBatch)
        self.assertIs(result.source_batch.raw_input, case[2].raw_input)
        self.assertIs(result.raw_input, case[2].raw_input)

    def test_keeps_unrelated_verified_hypothesis_when_another_is_rejected(self):
        claims = [
            _claim("claim-1", text="The supported event occurred."),
            _claim(
                "claim-2",
                kind="interpretation",
                text="The supported event may matter.",
                dependency_claim_ids=["claim-1"],
            ),
            _claim("claim-3", text="A different event occurred."),
        ]
        hypotheses = [
            _hypothesis("hyp-good", symbol="GOOD", supporting_claim_ids=["claim-2"]),
            _hypothesis("hyp-rejected", symbol="BAD", supporting_claim_ids=["claim-3"]),
        ]
        case = _case(
            claims=claims,
            hypotheses=hypotheses,
            verified_hypothesis_ids=("hyp-good",),
            rejected_hypotheses=(("hyp-rejected", "counterevidence unresolved"),),
        )

        result = _build(case)

        self.assertEqual(
            tuple(item.hypothesis_id for item in result.submission.hypotheses),
            ("hyp-good",),
        )
        self.assertEqual(
            {statement.statement_id for statement in result.submission.statements},
            {"claim-1", "claim-2"},
        )
        self.assertIn(
            "counterevidence unresolved",
            tuple(item.reason for item in result.diagnostics),
        )

    def test_coverage_displays_validator_outcome_and_retains_model_status(self):
        result = _build(_case())

        self.assertEqual(result.coverage[0].status, "supported")
        self.assertEqual(result.coverage[0].model_status, "contradicted")
        self.assertEqual(result.coverage[0].validator_rationale, "validator rationale")

    def test_false_claim_date_binding_excludes_its_dependency_closure(self):
        claims = [
            _claim(
                "claim-1",
                text="A source-reported event occurred on 2026-09-10.",
                event_date="2026-09-10",
            ),
            _claim(
                "claim-2",
                kind="interpretation",
                text="The event may matter.",
                dependency_claim_ids=["claim-1"],
            ),
        ]
        body = _base_body(claims, [_hypothesis()])
        bindings = _default_bindings([_hypothesis()], claims, body)
        rejected_index = len(bindings)
        bindings.append(
            _binding("/claims/0/event_date", "2026-09-10", body)
        )
        case = _case(
            claims=claims,
            field_bindings=bindings,
            source_body=body,
            verified_binding_indices=tuple(range(rejected_index)),
            rejected_bindings=((rejected_index, "date role was not supported"),),
        )

        result = _build(case)

        self.assertIsNone(result.submission)
        self.assertIsNone(result.source_batch)
        self.assertTrue(
            any(item.code == "FIELD_BINDING_NOT_VERIFIED" for item in result.diagnostics)
        )
        self.assertTrue(
            any(item.code == "NO_PROJECTABLE_HYPOTHESIS" for item in result.diagnostics)
        )

    def test_similar_but_nonmatching_underlying_binding_stays_unresolved(self):
        similar = UnderlyingKey(
            symbol="ACME",
            listing_mic="XNYS",
            security_type=UnderlyingSecurityType.EQUITY,
            currency="USD",
        )
        case = _case(
            underlying_bindings={
                ("another-hypothesis", "ACME"): (similar, "unrelated listing proof"),
                ("hyp-1", "ACME INC"): (similar, "similar-name proof"),
            }
        )

        result = _build(case)

        self.assertIsNotNone(result.submission)
        self.assertIsNone(result.submission.hypotheses[0].underlying_key)
        self.assertTrue(
            any(item.code == "UNDERLYING_UNRESOLVED" for item in result.diagnostics)
        )

    def test_matching_caller_policy_provenance_constructs_atomic_reassessment(self):
        date_text = "2026-11-15"
        claims = [
            _claim("claim-1", text="A source-reported milestone occurred."),
            _claim(
                "claim-2",
                kind="interpretation",
                text="The milestone may affect the distribution.",
                dependency_claim_ids=["claim-1"],
            ),
        ]
        hypothesis = _hypothesis(
            supporting_claim_ids=["claim-2"],
            reassessment={
                "reassessment_by": date_text,
                "methodology": "caller-research-policy-assumption:{}:Review next filing".format(
                    date_text
                ),
                "basis_kind": "caller_research_policy_assumption",
                "basis_claim_ids": ["claim-1", "claim-2"],
            },
        )
        provenance = CallerPolicyProvenance(
            run_id=_RUN_ID,
            canonical_input_hash=_INPUT_HASH,
            reassessment_by=datetime.date.fromisoformat(date_text),
            rationale="Review next filing",
            authorization_source="caller decision record 7",
        )
        case = _case(
            claims=claims,
            hypotheses=[hypothesis],
            caller_policy_provenance=provenance,
        )

        result = _build(case)

        reassessment = result.submission.hypotheses[0].reassessment
        self.assertIsNotNone(reassessment)
        self.assertEqual(reassessment.reassessment_by, datetime.date(2026, 11, 15))
        self.assertEqual(
            reassessment.basis_kind,
            ReassessmentBasisKind.CALLER_RESEARCH_POLICY_ASSUMPTION,
        )
        self.assertEqual(
            reassessment.basis_statement_ids, ("claim-1", "claim-2")
        )

    def test_source_milestone_uses_verified_support_closure_and_host_event_range(self):
        date_text = "2026-11-15"
        claims = [
            _claim("claim-1", text="Milestone reported on {}.".format(date_text)),
            _claim(
                "claim-2",
                kind="interpretation",
                text="The milestone may affect the distribution.",
                dependency_claim_ids=["claim-1"],
            ),
        ]
        hypothesis = _hypothesis(
            supporting_claim_ids=["claim-2"],
            reassessment={
                "reassessment_by": date_text,
                "methodology": "source-backed-milestone:claim-1:{}".format(date_text),
                "basis_kind": "source_backed_milestone",
                "basis_claim_ids": ["claim-1"],
            },
        )
        event_range = MethodologizedDateRange(
            datetime.date(2026, 9, 1), None, "independent Host chronology"
        )
        case = _case(
            claims=claims,
            hypotheses=[hypothesis],
            event_date_range=event_range,
        )

        result = _build(case)

        self.assertIsNotNone(result.submission)
        self.assertEqual(
            result.submission.hypotheses[0].reassessment.reassessment_by,
            datetime.date(2026, 11, 15),
        )
        self.assertIs(result.submission.event_date_range, event_range)

    def test_stale_reassessment_excludes_only_its_hypothesis_using_utc_date(self):
        stale_date = "2026-09-27"
        claims = [
            _claim(
                "claim-stale-fact",
                text="Milestone scheduled for {}.".format(stale_date),
            ),
            _claim(
                "claim-stale-interpretation",
                kind="interpretation",
                text="The stale milestone may affect outcomes.",
                dependency_claim_ids=["claim-stale-fact"],
            ),
            _claim("claim-valid-fact", text="A separate event was reported."),
            _claim(
                "claim-valid-interpretation",
                kind="interpretation",
                text="The separate event may affect outcomes.",
                dependency_claim_ids=["claim-valid-fact"],
            ),
        ]
        hypotheses = [
            _hypothesis(
                "hyp-stale",
                symbol="STALE",
                supporting_claim_ids=["claim-stale-interpretation"],
                reassessment={
                    "reassessment_by": stale_date,
                    "methodology": "source-backed-milestone:claim-stale-fact:{}".format(
                        stale_date
                    ),
                    "basis_kind": "source_backed_milestone",
                    "basis_claim_ids": ["claim-stale-fact"],
                },
            ),
            _hypothesis(
                "hyp-valid",
                symbol="VALID",
                supporting_claim_ids=["claim-valid-interpretation"],
            ),
        ]
        case = _case(claims=claims, hypotheses=hypotheses)
        # Local date is Sep 27, but Host submission date is Sep 28 in UTC.
        context = replace(
            case[2],
            observed_at=datetime.datetime(
                2026,
                9,
                27,
                22,
                30,
                tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
            ),
        )

        result = _build((case[0], case[1], context))

        self.assertIsNotNone(result.submission)
        self.assertEqual(
            tuple(item.hypothesis_id for item in result.submission.hypotheses),
            ("hyp-valid",),
        )
        self.assertEqual(
            {statement.statement_id for statement in result.submission.statements},
            {"claim-valid-fact", "claim-valid-interpretation"},
        )
        stale_diagnostic, = tuple(
            item for item in result.diagnostics
            if item.subject_id == "hyp-stale"
            and "reassessment_by precedes observed_at UTC calendar date" in item.reason
        )
        self.assertEqual(stale_diagnostic.code, "HYPOTHESIS_NOT_PROJECTED")

    def test_mismatched_caller_policy_is_retained_in_sidecar_but_not_projected(self):
        date_text = "2026-11-15"
        claims = [
            _claim("claim-1", text="A source-reported milestone occurred."),
            _claim(
                "claim-2",
                kind="interpretation",
                text="The milestone may affect the distribution.",
                dependency_claim_ids=["claim-1"],
            ),
        ]
        hypothesis = _hypothesis(
            supporting_claim_ids=["claim-2"],
            reassessment={
                "reassessment_by": date_text,
                "methodology": "caller-research-policy-assumption:{}:Review next filing".format(
                    date_text
                ),
                "basis_kind": "caller_research_policy_assumption",
                "basis_claim_ids": ["claim-1", "claim-2"],
            },
        )
        stale_policy = CallerPolicyProvenance(
            run_id="another-run",
            canonical_input_hash=_INPUT_HASH,
            reassessment_by=datetime.date.fromisoformat(date_text),
            rationale="Review next filing",
            authorization_source="stale caller record",
        )
        case = _case(
            claims=claims,
            hypotheses=[hypothesis],
            caller_policy_provenance=stale_policy,
        )

        result = _build(case)

        self.assertIsNotNone(result.submission)
        self.assertIsNone(result.submission.hypotheses[0].reassessment)
        self.assertTrue(
            any(
                item.code == "CALLER_POLICY_PROVENANCE_MISMATCH"
                for item in result.diagnostics
            )
        )
        self.assertEqual(
            result.semantic_validation.snapshot.envelope_hash,
            result.semantic_validation.receipt["envelope_hash"],
        )

    def test_source_body_hash_mismatch_is_rejected_before_projection(self):
        body = "body"
        with self.assertRaisesRegex(ValueError, "does not match"):
            HostSourceBody(
                body=body,
                body_sha256="0" * 64,
                final_locator="https://publisher.example/final",
                retrieved_at=_NOW,
            )

    def test_no_readable_body_or_no_supporting_hypothesis_emits_no_batch(self):
        empty_case = _case(
            claims=[],
            hypotheses=[],
            field_bindings=[],
            source_body="   ",
            verified_claim_ids=(),
            verified_hypothesis_ids=(),
            verified_binding_indices=(),
        )
        empty_result = _build(empty_case)
        self.assertIsNone(empty_result.submission)
        self.assertIsNone(empty_result.source_batch)
        self.assertTrue(
            any(item.code == "NO_READABLE_SOURCE_BODY" for item in empty_result.diagnostics)
        )

        no_hypothesis_case = _case(
            claims=[_claim("claim-1")],
            hypotheses=[],
            field_bindings=[],
            event_description_binding=None,
        )
        no_hypothesis_result = _build(no_hypothesis_case)
        self.assertIsNone(no_hypothesis_result.submission)
        self.assertIsNone(no_hypothesis_result.source_batch)

    def test_receipt_run_or_envelope_mismatch_fails_closed(self):
        case = _case()
        envelope, receipt, context = case
        wrong_run = dict(receipt, run_id="other-run")
        with self.assertRaisesRegex(ValueError, "run_id"):
            build_host_grounder(
                envelope,
                wrong_run,
                context=context,
                request_subquestion_ids=("question-1",),
                **_LIMITS
            )

        changed_envelope = copy.deepcopy(envelope)
        changed_envelope["claims"][0]["text"] = "Changed after receipt creation."
        with self.assertRaisesRegex(ValueError, "envelope_hash"):
            build_host_grounder(
                changed_envelope,
                receipt,
                context=context,
                request_subquestion_ids=("question-1",),
                **_LIMITS
            )

    def test_projection_uses_validated_snapshot_not_mutable_input_mapping(self):
        case = _case()
        envelope, receipt, context = case
        original_text = envelope["claims"][0]["text"]
        validate = builder_module.validate_semantic_validation_receipt

        def validate_then_mutate(*args, **kwargs):
            snapshot = validate(*args, **kwargs)
            envelope["claims"][0]["text"] = "mutated after receipt validation"
            return snapshot

        with patch.object(
            builder_module,
            "validate_semantic_validation_receipt",
            side_effect=validate_then_mutate,
        ):
            result = build_host_grounder(
                envelope,
                receipt,
                context=context,
                request_subquestion_ids=("question-1",),
                **_LIMITS
            )

        projected_claim = next(
            item for item in result.submission.statements
            if item.statement_id == "claim-1"
        )
        self.assertEqual(projected_claim.text, original_text)


if __name__ == "__main__":
    unittest.main()
