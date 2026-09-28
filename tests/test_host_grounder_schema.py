import json
import unittest

from convexity_hunter.event_intelligence import (
    DistributionChangeMode,
    ReassessmentBasisKind,
)
from convexity_hunter.host_grounder_schema import parse_model_output_envelope


def _envelope():
    return {
        "schema_version": "grounder-output-v0.1",
        "stage": "discovery",
        "request_id": "request-1",
        "claims": [],
        "hypotheses": [],
        "coverage": [],
        "field_bindings": [],
    }


def _parse(value, max_string_bytes=10_000):
    raw_json = value if isinstance(value, str) else json.dumps(value)
    return parse_model_output_envelope(
        raw_json,
        max_input_bytes=100_000,
        max_string_bytes=max_string_bytes,
        max_array_items=100,
    )


def _claim(**updates):
    claim = {
        "claim_id": "claim-1",
        "kind": "observed_fact",
        "source_id": "source-1",
        "locator": "p. 1",
        "quote": "quoted text",
        "text": "claim text",
        "entity_refs": ["ENTITY"],
        "event_date": None,
        "published_at": None,
        "dependency_claim_ids": [],
        "uncertainty": [],
        "falsification_conditions": [],
    }
    claim.update(updates)
    return claim


def _hypothesis():
    return {
        "hypothesis_id": "hypothesis-1",
        "underlying_symbol": "ENTITY",
        "impact_path": None,
        "distribution_mode": None,
        "distribution_hypothesis": None,
        "expected_window": None,
        "reassessment": None,
        "supporting_claim_ids": [],
        "contradicting_claim_ids": [],
        "contradiction_review": None,
        "uncertainties": [],
        "falsification_conditions": [],
    }


def _binding(field_path="/hypotheses/0/underlying_symbol", semantic_role="entity"):
    return {
        "field_path": field_path,
        "source_id": "source-1",
        "quote": "E",
        "start": 0,
        "end": 1,
        "semantic_role": semantic_role,
        "status": "supported",
    }


class HostGrounderSchemaTests(unittest.TestCase):
    def test_valid_minimal_envelope(self):
        envelope = _envelope()
        self.assertEqual(_parse(envelope), envelope)

        with_empty_entity_refs = _envelope()
        with_empty_entity_refs["claims"] = [_claim(entity_refs=[])]
        self.assertEqual(_parse(with_empty_entity_refs), with_empty_entity_refs)

        with_enum_mode = _envelope()
        hypothesis = _hypothesis()
        hypothesis["distribution_mode"] = DistributionChangeMode.EXTREME_TAIL_UP.value
        with_enum_mode["hypotheses"] = [hypothesis]
        self.assertEqual(_parse(with_enum_mode), with_enum_mode)

        with_arbitrary_mode = _envelope()
        hypothesis = _hypothesis()
        hypothesis["distribution_mode"] = "normal"
        with_arbitrary_mode["hypotheses"] = [hypothesis]
        with self.assertRaisesRegex(ValueError, "allowed EI mode"):
            _parse(with_arbitrary_mode)

    def test_enforces_string_limit_for_all_values_and_object_keys(self):
        with self.assertRaisesRegex(ValueError, "max_string_bytes"):
            _parse(_envelope(), max_string_bytes=15)

        envelope = _envelope()
        envelope["k" * 22] = "short"
        with self.assertRaisesRegex(ValueError, "max_string_bytes"):
            _parse(envelope, max_string_bytes=21)

    def test_reassessment_basis_kind_uses_closed_ei_enum(self):
        envelope = _envelope()
        hypothesis = _hypothesis()
        hypothesis["reassessment"] = {
            "reassessment_by": "2026-12-31",
            "methodology": "source-backed-milestone:claim-1:2026-12-31",
            "basis_kind": ReassessmentBasisKind.SOURCE_BACKED_MILESTONE.value,
            "basis_claim_ids": ["claim-1"],
        }
        envelope["hypotheses"] = [hypothesis]
        self.assertEqual(_parse(envelope), envelope)

        hypothesis["reassessment"]["basis_kind"] = "model_guess"
        with self.assertRaisesRegex(ValueError, "basis_kind is invalid"):
            _parse(envelope)

    def test_rejects_duplicate_key(self):
        raw_json = (
            '{"schema_version":"grounder-output-v0.1",'
            '"schema_version":"grounder-output-v0.1"}'
        )

        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            _parse(raw_json)

    def test_rejects_unknown_field(self):
        envelope = _envelope()
        envelope["unexpected"] = "nope"

        with self.assertRaisesRegex(ValueError, "unknown fields"):
            _parse(envelope)

    def test_rejects_invalid_field_path_or_role(self):
        cases = (
            ("/hypotheses/00/underlying_symbol", "entity"),
            ("/hypotheses/1/underlying_symbol", "entity"),
            ("/hypotheses/0/underlying_symbol", "hypothesis"),
        )
        for path, role in cases:
            with self.subTest(path=path, role=role):
                envelope = _envelope()
                envelope["hypotheses"] = [_hypothesis()]
                envelope["field_bindings"] = [_binding(path, role)]
                with self.assertRaises(ValueError):
                    _parse(envelope)

    def test_rejects_invalid_date_time_or_nonfinite_number(self):
        cases = (
            json.dumps({**_envelope(), "claims": [_claim(event_date="2026-02-30")]}),
            json.dumps(
                {
                    **_envelope(),
                    "claims": [_claim(published_at="2026-09-28T12:30:00")],
                }
            ),
            json.dumps(
                {
                    **_envelope(),
                    "claims": [_claim(published_at="2026-09-28T12:30:00+24:00")],
                }
            ),
            json.dumps(
                {
                    **_envelope(),
                    "claims": [_claim(published_at="2026-09-28T12:30:00+01:60")],
                }
            ),
            json.dumps(
                {
                    **_envelope(),
                    "claims": [_claim(published_at="2026-09-28T23:59:60Z")],
                }
            ),
            json.dumps(
                {
                    **_envelope(),
                    "claims": [_claim(published_at="2014-06-30T23:59:60Z")],
                }
            ),
            '{"schema_version":"grounder-output-v0.1","stage":"discovery",'
            '"request_id":"request-1","claims":[],"hypotheses":[],"coverage":[],'
            '"field_bindings":[],"unexpected":NaN}',
        )
        for raw_json in cases:
            with self.subTest(raw_json=raw_json):
                with self.assertRaises(ValueError):
                    _parse(raw_json)

    def test_accepts_case_insensitive_rfc3339_and_leap_second_text(self):
        timestamps = (
            "2026-09-28t12:30:00z",
            "2026-09-28T12:30:00.5Z",
            "2026-09-28T12:30:00.500000Z",
            "2026-09-28T12:30:00." + ("1234567890" * 10) + "Z",
            "2026-09-28t12:30:00.5z",
            "2016-12-31T23:59:60Z",
            "2016-12-31t23:59:60z",
            "2017-01-01T00:59:60+01:00",
        )
        for timestamp in timestamps:
            with self.subTest(timestamp=timestamp):
                envelope = _envelope()
                envelope["claims"] = [_claim(published_at=timestamp)]
                parsed = _parse(envelope)
                self.assertEqual(parsed["claims"][0]["published_at"], timestamp)


if __name__ == "__main__":
    unittest.main()
