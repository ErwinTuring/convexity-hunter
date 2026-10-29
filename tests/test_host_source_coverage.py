import copy
import hashlib
import unittest
from dataclasses import FrozenInstanceError, replace

from convexity_hunter.host_source_coverage import HostSourceCoverageAudit


def _source_id(url):
    return "url:" + hashlib.sha256(url.encode("utf-8")).hexdigest()


def _payload(status="PARTIAL"):
    first = "https://example.org/a"
    second = "https://example.org/b"
    entries = [
        {
            "source_id": _source_id(first),
            "locator": first,
            "status": "BODY_AVAILABLE",
            "body_sha256": hashlib.sha256(b"body A").hexdigest(),
        },
        {
            "source_id": _source_id(second),
            "locator": second,
            "status": "FAILED",
            "reason_code": "PROVIDER_REPORTED_FAILURE",
        },
    ]
    if status == "COMPLETE":
        entries.pop()
    elif status == "EMPTY":
        entries[0] = {
            "source_id": _source_id(first),
            "locator": first,
            "status": "FAILED",
            "reason_code": "PROVIDER_REPORTED_FAILURE",
        }
    return {
        "schema_version": "host-source-coverage-v0.1",
        "host_run_id": "outer-run-1",
        "unit_id": "unit-1",
        "run_id": "grounder-run-1",
        "canonical_input_hash": "a" * 64,
        "status": status,
        "entries": entries,
    }


class HostSourceCoverageAuditTests(unittest.TestCase):
    def test_partial_payload_is_immutable_canonical_and_detached(self):
        payload = _payload()
        audit = HostSourceCoverageAudit.from_dict(payload)

        source_a = _source_id("https://example.org/a")
        source_b = _source_id("https://example.org/b")
        body_hash = hashlib.sha256(b"body A").hexdigest()
        expected = (
            '{"canonical_input_hash":"' + "a" * 64
            + '","entries":[{"body_sha256":"' + body_hash
            + '","locator":"https://example.org/a","source_id":"' + source_a
            + '","status":"BODY_AVAILABLE"},{"locator":"https://example.org/b","reason_code":"PROVIDER_REPORTED_FAILURE","source_id":"' + source_b
            + '","status":"FAILED"}],"host_run_id":"outer-run-1","run_id":"grounder-run-1","schema_version":"host-source-coverage-v0.1","status":"PARTIAL","unit_id":"unit-1"}'
        ).encode("utf-8")
        self.assertEqual(audit.canonical_utf8, expected)
        self.assertEqual(audit.sha256, hashlib.sha256(expected).hexdigest())
        self.assertEqual(audit.to_dict(), payload)

        payload["entries"][0]["body_sha256"] = "f" * 64
        exported = audit.to_dict()
        exported["entries"].clear()
        self.assertEqual(audit.to_dict()["entries"][0]["body_sha256"], body_hash)
        self.assertEqual(len(audit.to_dict()["entries"]), 2)
        with self.assertRaises(FrozenInstanceError):
            audit.status = "COMPLETE"

    def test_constructor_and_boundary_roundtrip_reject_status_subclasses(self):
        class StatusSubclass(str):
            pass

        audit = HostSourceCoverageAudit.from_dict(_payload())
        with self.assertRaises(ValueError):
            replace(audit, status=StatusSubclass("PARTIAL"))
        self.assertEqual(
            HostSourceCoverageAudit.from_dict(audit.to_dict()).canonical_utf8,
            audit.canonical_utf8,
        )

    def test_complete_partial_and_empty_statuses_are_derived_from_rows(self):
        complete = HostSourceCoverageAudit.from_dict(_payload("COMPLETE"))
        partial = HostSourceCoverageAudit.from_dict(_payload("PARTIAL"))
        empty = HostSourceCoverageAudit.from_dict(_payload("EMPTY"))
        self.assertEqual((complete.status, len(complete.entries)), ("COMPLETE", 1))
        self.assertEqual((partial.status, len(partial.entries)), ("PARTIAL", 2))
        self.assertEqual((empty.status, len(empty.entries)), ("EMPTY", 2))

    def test_closed_shape_partition_and_url_identity_fail_closed(self):
        mutations = []

        missing_root = _payload()
        missing_root.pop("host_run_id")
        mutations.append(missing_root)

        extra_root = _payload()
        extra_root["provider_text"] = "must not survive"
        mutations.append(extra_root)

        wrong_status = _payload()
        wrong_status["status"] = "COMPLETE"
        mutations.append(wrong_status)

        overlap = _payload()
        overlap["entries"][1]["locator"] = overlap["entries"][0]["locator"]
        overlap["entries"][1]["source_id"] = overlap["entries"][0]["source_id"]
        mutations.append(overlap)

        wrong_id = _payload()
        wrong_id["entries"][0]["source_id"] = "url:" + "0" * 64
        mutations.append(wrong_id)

        wrong_variant = _payload()
        wrong_variant["entries"][1]["body_sha256"] = "b" * 64
        mutations.append(wrong_variant)

        wrong_body_digest = _payload()
        wrong_body_digest["entries"][0]["body_sha256"] = "B" * 64
        mutations.append(wrong_body_digest)

        wrong_failure_reason = _payload()
        wrong_failure_reason["entries"][1]["reason_code"] = "TIMEOUT: raw details"
        mutations.append(wrong_failure_reason)

        private_url = _payload()
        private_url["entries"][0]["locator"] = "http://127.0.0.1/private"
        private_url["entries"][0]["source_id"] = _source_id(private_url["entries"][0]["locator"])
        mutations.append(private_url)

        too_many = _payload()
        too_many["entries"] = [copy.deepcopy(too_many["entries"][0]) for _ in range(6)]
        mutations.append(too_many)

        for candidate in mutations:
            with self.subTest(candidate=candidate):
                with self.assertRaises((TypeError, ValueError)):
                    HostSourceCoverageAudit.from_dict(candidate)

        with self.assertRaises(ValueError):
            HostSourceCoverageAudit.from_dict({})


if __name__ == "__main__":
    unittest.main()
