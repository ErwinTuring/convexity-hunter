import copy
import hashlib
import json
import unittest
from types import MappingProxyType

from convexity_hunter.host_grounder_receipt import (
    ValidatedEnvelopeSnapshot,
    validate_semantic_validation_receipt,
)
from convexity_hunter.host_grounder_schema import parse_model_output_envelope


_RUN_ID = "run-42"
_INPUT_HASH = "a" * 64


def _claim(**updates):
    claim = {
        "claim_id": "claim-1",
        "kind": "observed_fact",
        "source_id": "source-z",
        "locator": "page 1",
        "quote": "Acme",
        "text": "Acme did not file.",
        "entity_refs": [],
        "event_date": None,
        "published_at": None,
        "dependency_claim_ids": [],
        "uncertainty": [],
        "falsification_conditions": [],
    }
    claim.update(updates)
    return claim


def _hypothesis(**updates):
    hypothesis = {
        "hypothesis_id": "hypothesis-1",
        "underlying_symbol": "ACME",
        "impact_path": None,
        "distribution_mode": None,
        "distribution_hypothesis": None,
        "expected_window": None,
        "reassessment": None,
        "supporting_claim_ids": ["claim-1"],
        "contradicting_claim_ids": [],
        "contradiction_review": None,
        "uncertainties": [],
        "falsification_conditions": [],
    }
    hypothesis.update(updates)
    return hypothesis


def _binding(**updates):
    binding = {
        "field_path": "/hypotheses/0/underlying_symbol",
        "source_id": "source-z",
        "quote": "ACME",
        "start": 2,
        "end": 6,
        "semantic_role": "entity",
        "status": "supported",
    }
    binding.update(updates)
    return binding


def _envelope(**updates):
    envelope = {
        "schema_version": "grounder-output-v0.1",
        "stage": "discovery",
        "request_id": "request-1",
        "claims": [_claim()],
        "hypotheses": [_hypothesis()],
        "coverage": [
            {
                "subquestion_id": "question-1",
                "status": "contradicted",
                "claim_ids": ["claim-1"],
                "gap": None,
            }
        ],
        "field_bindings": [_binding()],
    }
    envelope.update(updates)
    raw_json = json.dumps(envelope, ensure_ascii=False, separators=(",", ":"))
    return parse_model_output_envelope(
        raw_json,
        max_input_bytes=100_000,
        max_string_bytes=10_000,
        max_array_items=100,
    )


def _canonical_hash_for_test(envelope):
    """Independent fixture serializer; the golden test below pins exact bytes."""
    encoded = json.dumps(
        envelope,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _body_hashes(source_bodies):
    return tuple(
        (source_id, hashlib.sha256(body.encode("utf-8")).hexdigest())
        for source_id, body in sorted(source_bodies.items())
    )


def _case():
    envelope = _envelope()
    source_bodies = {
        "source-z": "😀 ACME report: Acme filed.",
        "source-a": "Additional registered source body.",
    }
    receipt = {
        "schema_version": "semantic-validation-v0.1",
        "run_id": _RUN_ID,
        "canonical_input_hash": _INPUT_HASH,
        "envelope_hash": _canonical_hash_for_test(envelope),
        "source_body_hashes": _body_hashes(source_bodies),
        "validator_id": "host-validator",
        "validator_version": "0.1",
        "verified_claim_ids": ("claim-1",),
        "rejected_claims": (),
        "verified_hypothesis_ids": ("hypothesis-1",),
        "rejected_hypotheses": (),
        "verified_binding_indices": (0,),
        "rejected_bindings": (),
        "coverage_outcomes": ((0, "question-1", "supported", "Host rationale."),),
    }
    return envelope, receipt, source_bodies


def _rebind(envelope, receipt, source_bodies):
    receipt["envelope_hash"] = _canonical_hash_for_test(envelope)
    receipt["source_body_hashes"] = _body_hashes(source_bodies)


def _validate(
    envelope,
    receipt,
    source_bodies,
    request_ids=("question-1",),
    *,
    max_input_bytes=100_000,
    max_string_bytes=10_000,
    max_array_items=100,
    expected_schema_version="semantic-validation-v0.1",
):
    return validate_semantic_validation_receipt(
        envelope,
        receipt,
        run_id=_RUN_ID,
        canonical_input_hash=_INPUT_HASH,
        request_subquestion_ids=request_ids,
        source_bodies=source_bodies,
        max_input_bytes=max_input_bytes,
        max_string_bytes=max_string_bytes,
        max_array_items=max_array_items,
        expected_schema_version=expected_schema_version,
    )


class HostGrounderReceiptTests(unittest.TestCase):
    def test_accepts_exact_receipt_and_does_not_assert_semantic_truth(self):
        envelope, receipt, source_bodies = _case()

        snapshot = _validate(envelope, receipt, source_bodies)
        self.assertIsInstance(snapshot, ValidatedEnvelopeSnapshot)
        self.assertEqual(snapshot.envelope_hash, receipt["envelope_hash"])
        self.assertEqual(
            hashlib.sha256(snapshot.canonical_bytes).hexdigest(),
            snapshot.envelope_hash,
        )

    def test_v02_receipt_and_explicit_version_mismatch(self):
        envelope, receipt, source_bodies = _case()
        receipt["schema_version"] = "semantic-validation-v0.2"

        with self.assertRaisesRegex(ValueError, "does not match expected_schema_version"):
            _validate(envelope, receipt, source_bodies)
        self.assertIsInstance(
            _validate(
                envelope, receipt, source_bodies,
                expected_schema_version="semantic-validation-v0.2",
            ),
            ValidatedEnvelopeSnapshot,
        )
        with self.assertRaisesRegex(ValueError, "does not match expected_schema_version"):
            _validate(
                envelope, dict(receipt, schema_version="semantic-validation-v0.1"),
                source_bodies, expected_schema_version="semantic-validation-v0.2",
            )
        with self.assertRaisesRegex(ValueError, "expected_schema_version is unsupported"):
            _validate(
                envelope, receipt, source_bodies,
                expected_schema_version="semantic-validation-v0.3",
            )

        receipt["schema_version"] = "semantic-validation-v0.3"
        with self.assertRaisesRegex(ValueError, "receipt schema_version is unsupported"):
            _validate(envelope, receipt, source_bodies)

    def test_canonical_envelope_encoding_has_independent_golden_bytes_and_hash(self):
        envelope = _envelope(
            request_id="请求-1",
            claims=[],
            hypotheses=[],
            coverage=[],
            field_bindings=[],
        )
        expected_bytes = (
            '{"claims":[],"coverage":[],"field_bindings":[],"hypotheses":[],'
            '"request_id":"请求-1","schema_version":"grounder-output-v0.1",'
            '"stage":"discovery"}'
        ).encode("utf-8")
        self.assertEqual(
            json.dumps(
                envelope,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8"),
            expected_bytes,
        )
        self.assertEqual(
            hashlib.sha256(expected_bytes).hexdigest(),
            "91ff7f2770875b051fa7f3ecdd2c25891d407d8cdfdb7574df6c2001233adb90",
        )

    def test_rejects_open_or_incomplete_receipt_shape(self):
        envelope, receipt, source_bodies = _case()
        self.assertIsInstance(
            _validate(envelope, MappingProxyType(receipt), source_bodies),
            ValidatedEnvelopeSnapshot,
        )

        with_extra = dict(receipt, unexpected="value")
        with_missing = dict(receipt)
        del with_missing["validator_version"]

        for candidate in (with_extra, with_missing):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, "closed"):
                    _validate(envelope, candidate, source_bodies)

        with_list = dict(receipt, verified_claim_ids=["claim-1"])
        with self.assertRaisesRegex(ValueError, "tuple"):
            _validate(envelope, with_list, source_bodies)

    def test_claim_partition_rejects_duplicate_overlap_missing_and_foreign_ids(self):
        envelope, receipt, source_bodies = _case()
        invalid_values = (
            (("claim-1", "claim-1"), ()),
            (("claim-1",), (("claim-1", "also rejected"),)),
            ((), ()),
            (("foreign-claim",), ()),
        )
        for verified, rejected in invalid_values:
            with self.subTest(verified=verified, rejected=rejected):
                candidate = dict(
                    receipt,
                    verified_claim_ids=verified,
                    rejected_claims=rejected,
                )
                with self.assertRaises(ValueError):
                    _validate(envelope, candidate, source_bodies)

    def test_hypothesis_partition_rejects_duplicate_overlap_missing_and_foreign_ids(self):
        envelope, receipt, source_bodies = _case()
        invalid_values = (
            (("hypothesis-1", "hypothesis-1"), ()),
            (("hypothesis-1",), (("hypothesis-1", "reason"),)),
            ((), ()),
            (("foreign-hypothesis",), ()),
            ((), (("hypothesis-1", ""),)),
        )
        for verified, rejected in invalid_values:
            with self.subTest(verified=verified, rejected=rejected):
                candidate = dict(
                    receipt,
                    verified_hypothesis_ids=verified,
                    rejected_hypotheses=rejected,
                )
                with self.assertRaises(ValueError):
                    _validate(envelope, candidate, source_bodies)

    def test_duplicate_ids_in_the_envelope_are_rejected(self):
        envelope, receipt, source_bodies = _case()
        duplicate_claim = copy.deepcopy(envelope)
        duplicate_claim["claims"].append(copy.deepcopy(duplicate_claim["claims"][0]))
        _rebind(duplicate_claim, receipt, source_bodies)
        with self.assertRaisesRegex(ValueError, "duplicate envelope claim"):
            _validate(duplicate_claim, receipt, source_bodies)

        duplicate_hypothesis = copy.deepcopy(envelope)
        duplicate_hypothesis["hypotheses"].append(
            copy.deepcopy(duplicate_hypothesis["hypotheses"][0])
        )
        _rebind(duplicate_hypothesis, receipt, source_bodies)
        with self.assertRaisesRegex(ValueError, "duplicate envelope hypothesis"):
            _validate(duplicate_hypothesis, receipt, source_bodies)

    def test_binding_partition_rejects_duplicate_overlap_missing_foreign_and_bool(self):
        envelope, receipt, source_bodies = _case()
        invalid_values = (
            ((0, 0), ()),
            ((0,), ((0, "reason"),)),
            ((), ()),
            ((7,), ()),
            ((True,), ()),
            ((), ((0, ""),)),
        )
        for verified, rejected in invalid_values:
            with self.subTest(verified=verified, rejected=rejected):
                candidate = dict(
                    receipt,
                    verified_binding_indices=verified,
                    rejected_bindings=rejected,
                )
                with self.assertRaises(ValueError):
                    _validate(envelope, candidate, source_bodies)

    def test_coverage_outcomes_are_an_exact_index_id_partition(self):
        envelope, receipt, source_bodies = _case()
        invalid_outcomes = (
            ((0, "question-1", "supported", "ok"),) * 2,
            (),
            ((1, "question-1", "supported", "ok"),),
            ((0, "foreign-question", "supported", "ok"),),
            ((0, "question-1", "unsupported", "ok"),),
            ((0, "question-1", "supported", ""),),
            ((False, "question-1", "supported", "ok"),),
        )
        for outcomes in invalid_outcomes:
            with self.subTest(outcomes=outcomes):
                candidate = dict(receipt, coverage_outcomes=outcomes)
                with self.assertRaises(ValueError):
                    _validate(envelope, candidate, source_bodies)

        with_list_entry = dict(
            receipt,
            coverage_outcomes=([0, "question-1", "supported", "ok"],),
        )
        with self.assertRaisesRegex(ValueError, "tuple"):
            _validate(envelope, with_list_entry, source_bodies)

    def test_coverage_must_match_original_request_in_order_without_duplicates(self):
        envelope, receipt, source_bodies = _case()
        for request_ids in ((), ("foreign-question",), ("question-1", "question-1")):
            with self.subTest(request_ids=request_ids):
                with self.assertRaises(ValueError):
                    _validate(envelope, receipt, source_bodies, request_ids)

        two_coverage = copy.deepcopy(envelope)
        two_coverage["coverage"].append(
            {
                "subquestion_id": "question-2",
                "status": "unresolved",
                "claim_ids": [],
                "gap": "not evaluated",
            }
        )
        two_receipt = dict(
            receipt,
            coverage_outcomes=(
                (0, "question-1", "supported", "ok"),
                (1, "question-2", "unresolved", "gap"),
            ),
        )
        _rebind(two_coverage, two_receipt, source_bodies)
        self.assertIsInstance(
            _validate(
                two_coverage,
                two_receipt,
                source_bodies,
                ("question-1", "question-2"),
            ),
            ValidatedEnvelopeSnapshot,
        )

    def test_run_input_and_envelope_hashes_must_match_exactly(self):
        envelope, receipt, source_bodies = _case()
        with self.assertRaisesRegex(ValueError, "run_id"):
            validate_semantic_validation_receipt(
                envelope,
                dict(receipt, run_id="other-run"),
                run_id=_RUN_ID,
                canonical_input_hash=_INPUT_HASH,
                request_subquestion_ids=("question-1",),
                source_bodies=source_bodies,
                max_input_bytes=100_000,
                max_string_bytes=10_000,
                max_array_items=100,
            )
        with self.assertRaisesRegex(ValueError, "canonical_input_hash"):
            _validate(envelope, dict(receipt, canonical_input_hash="b" * 64), source_bodies)
        with self.assertRaisesRegex(ValueError, "envelope_hash"):
            _validate(envelope, dict(receipt, envelope_hash="0" * 64), source_bodies)
        with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
            _validate(envelope, dict(receipt, envelope_hash="A" * 64), source_bodies)

        changed_envelope = copy.deepcopy(envelope)
        changed_envelope["request_id"] = "different-request"
        with self.assertRaisesRegex(ValueError, "envelope_hash"):
            _validate(changed_envelope, receipt, source_bodies)

    def test_revalidates_mutated_nested_schema_even_when_receipt_is_rehashed(self):
        mutations = (
            ("kind", lambda value: value["claims"][0].update(kind="unsupported")),
            (
                "dependencies",
                lambda value: value["claims"][0].update(dependency_claim_ids=["ok", 7]),
            ),
            (
                "binding path",
                lambda value: value["field_bindings"][0].update(field_path="/unlisted/path"),
            ),
            (
                "binding status",
                lambda value: value["field_bindings"][0].update(status="accepted"),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                envelope, receipt, source_bodies = _case()
                mutate(envelope)
                _rebind(envelope, receipt, source_bodies)
                self.assertEqual(receipt["envelope_hash"], _canonical_hash_for_test(envelope))
                with self.assertRaises(ValueError):
                    _validate(envelope, receipt, source_bodies)

    def test_revalidation_reapplies_explicit_parser_bounds(self):
        envelope, receipt, source_bodies = _case()
        with self.assertRaisesRegex(ValueError, "max_input_bytes"):
            _validate(envelope, receipt, source_bodies, max_input_bytes=1)
        with self.assertRaisesRegex(ValueError, "max_string_bytes"):
            _validate(envelope, receipt, source_bodies, max_string_bytes=5)

        too_many_dependencies = copy.deepcopy(envelope)
        too_many_dependencies["claims"][0]["dependency_claim_ids"] = ["one", "two"]
        changed_receipt = dict(receipt)
        _rebind(too_many_dependencies, changed_receipt, source_bodies)
        with self.assertRaisesRegex(ValueError, "max_array_items"):
            _validate(
                too_many_dependencies,
                changed_receipt,
                source_bodies,
                max_array_items=1,
            )

    def test_post_validation_mutation_cannot_change_returned_snapshot(self):
        envelope, receipt, source_bodies = _case()
        original_envelope = copy.deepcopy(envelope)
        snapshot = _validate(envelope, receipt, source_bodies)
        original_bytes = snapshot.canonical_bytes

        envelope["claims"][0]["kind"] = "interpretation"
        envelope["field_bindings"][0]["status"] = "unresolved"
        self.assertEqual(snapshot.canonical_bytes, original_bytes)
        self.assertEqual(snapshot.envelope_hash, receipt["envelope_hash"])
        self.assertEqual(
            parse_model_output_envelope(
                snapshot.canonical_bytes.decode("utf-8"),
                max_input_bytes=100_000,
                max_string_bytes=10_000,
                max_array_items=100,
            ),
            original_envelope,
        )

        with self.assertRaises(AttributeError):
            snapshot.canonical_bytes = b"changed"

    def test_source_hash_registry_is_exact_sorted_and_utf8_bound(self):
        envelope, receipt, source_bodies = _case()
        valid_hashes = receipt["source_body_hashes"]
        bad_registries = (
            (),
            valid_hashes[:-1],
            valid_hashes + (("foreign-source", "b" * 64),),
            (valid_hashes[1], valid_hashes[0]),
            (("source-a", "0" * 64), valid_hashes[1]),
        )
        for hashes in bad_registries:
            with self.subTest(hashes=hashes):
                with self.assertRaises(ValueError):
                    _validate(envelope, dict(receipt, source_body_hashes=hashes), source_bodies)

        changed_body = dict(source_bodies)
        changed_body["source-a"] += " Changed after validation."
        with self.assertRaisesRegex(ValueError, "exact body registry"):
            _validate(envelope, receipt, changed_body)

        with self.assertRaisesRegex(ValueError, "valid UTF-8"):
            _validate(envelope, receipt, {"source-z": "\ud800"})

    def test_verified_claim_quotes_must_occur_exactly_once_in_the_bound_body(self):
        envelope, receipt, source_bodies = _case()
        for body in (
            "😀 ACME report: no relevant quote.",
            "😀 ACME report: Acme filed, Acme repeated.",
        ):
            with self.subTest(body=body):
                candidate_bodies = dict(source_bodies, **{"source-z": body})
                candidate_receipt = dict(receipt)
                _rebind(envelope, candidate_receipt, candidate_bodies)
                with self.assertRaisesRegex(ValueError, "claim claim-1 quote is not unique"):
                    _validate(envelope, candidate_receipt, candidate_bodies)

        overlap_envelope = copy.deepcopy(envelope)
        overlap_envelope["claims"][0]["quote"] = "aaa"
        overlap_bodies = dict(source_bodies, **{"source-z": "aaaa"})
        overlap_receipt = dict(receipt)
        _rebind(overlap_envelope, overlap_receipt, overlap_bodies)
        with self.assertRaisesRegex(ValueError, "claim claim-1 quote is not unique"):
            _validate(overlap_envelope, overlap_receipt, overlap_bodies)

        rejected_receipt = dict(
            receipt,
            verified_claim_ids=(),
            rejected_claims=(("claim-1", "lexical location unresolved"),),
        )
        repeated_bodies = dict(
            source_bodies,
            **{"source-z": "😀 ACME report: Acme filed, Acme repeated."},
        )
        _rebind(envelope, rejected_receipt, repeated_bodies)
        self.assertIsInstance(
            _validate(envelope, rejected_receipt, repeated_bodies),
            ValidatedEnvelopeSnapshot,
        )

    def test_verified_field_binding_span_uses_codepoints_and_exact_body_text(self):
        envelope, receipt, source_bodies = _case()
        self.assertIsInstance(
            _validate(envelope, receipt, source_bodies), ValidatedEnvelopeSnapshot
        )

        invalid_binding = copy.deepcopy(envelope)
        invalid_binding["field_bindings"][0]["start"] = 5  # UTF-8 byte offset, not codepoint.
        invalid_receipt = dict(receipt)
        _rebind(invalid_binding, invalid_receipt, source_bodies)
        with self.assertRaisesRegex(ValueError, "span does not match"):
            _validate(invalid_binding, invalid_receipt, source_bodies)

        beyond_body = copy.deepcopy(envelope)
        beyond_body["field_bindings"][0]["end"] = 10_000
        beyond_receipt = dict(receipt)
        _rebind(beyond_body, beyond_receipt, source_bodies)
        with self.assertRaisesRegex(ValueError, "span does not match"):
            _validate(beyond_body, beyond_receipt, source_bodies)

        missing_source = copy.deepcopy(envelope)
        missing_source["field_bindings"][0]["source_id"] = "missing-source"
        missing_receipt = dict(receipt)
        _rebind(missing_source, missing_receipt, source_bodies)
        with self.assertRaisesRegex(ValueError, "span does not match"):
            _validate(missing_source, missing_receipt, source_bodies)


if __name__ == "__main__":
    unittest.main()
