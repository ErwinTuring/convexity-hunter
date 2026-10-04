"""Synthetic, stdlib-only loopback tests for the bounded Host HTTP shell."""

import contextlib
import datetime
import hashlib
import http.client
import io
import json
import pathlib
import socket
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from urllib.parse import quote
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tests.test_host_direct import _bounds as direct_bounds
from tests.test_host_direct import _bridge_for as direct_bridge_for
from tests.test_host_direct import _payload as direct_input_payload
from convexity_hunter.core_application import (
    CoreCaseSet,
    CoreDirectResult,
    CoreOperationalBounds,
    CoreRunResult,
    CoreUnavailableCase,
    SourceSubmissionBatch,
    run_event_core,
    run_world_core,
)
from convexity_hunter.core_presentation import compact_summary
from convexity_hunter.core_research import CoreDisposition
from convexity_hunter.host_direct import parse_direct_input, run_direct_input
from convexity_hunter.host_profile import (
    STANDARD_RESEARCH_PROFILE,
    create_core_research_policy,
)
from convexity_hunter.host_server import (
    BLOCKED_REASON,
    CSRF_HEADER,
    MAX_REQUEST_BODY_BYTES,
    create_server,
    validate_run_request,
)
from convexity_hunter import host_server as host_server_module
from tests.test_core_application import (
    FakeMarketBridge as BatchFakeMarketBridge,
    make_policy as make_batch_policy,
    make_row as make_batch_row,
    make_submission as make_batch_submission,
)
from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.event_intelligence import DistributionChangeMode
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority


def valid_payload():
    return {
        "mode": "world",
        "input": "research a named event",
        "bounds": {
            "max_submissions": 2,
            "max_hypotheses": 3,
            "max_browser_rows": 20,
            "max_cases": 8,
            "quote_timeout_seconds": 2.5,
        },
    }


def make_world_batch_result(
    raw_input, *, case_id_transform=None, approved_profile=False
):
    rows = (
        make_batch_row(datetime.date(2030, 1, 31), "CALL", "100"),
    )
    batch = SourceSubmissionBatch(
        raw_input,
        (
            make_batch_submission(
                "host-batch",
                ("hyp-b", "hyp-a"),
                mode=DistributionChangeMode.EXTREME_TAIL_UP,
            ),
        ),
    )
    policy = (
        create_core_research_policy(
            evaluation_date=datetime.date(2030, 1, 1),
            maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
            bounds=CoreOperationalBounds(
                max_submissions=2,
                max_hypotheses=3,
                max_browser_rows=20,
                max_cases=8,
                quote_timeout_seconds=2.5,
            ),
        )
        if approved_profile
        else make_batch_policy([])
    )
    result = run_world_core(
        raw_input,
        source_producer=lambda _raw: batch,
        market_bridge=BatchFakeMarketBridge(rows),
        policy=policy,
    )
    if case_id_transform is None:
        return result
    case_set = result.case_set
    transformed = CoreCaseSet(
        case_set.entry_origin,
        case_set.raw_input,
        case_set.submissions,
        tuple(
            replace(case, case_id=case_id_transform(case.case_id))
            for case in case_set.cases
        ),
        tuple(
            replace(case, case_id=case_id_transform(case.case_id))
            for case in case_set.unavailable
        ),
        case_set.reasons,
    )
    return CoreRunResult(transformed, compact_summary(transformed))


def make_event_batch_result(raw_input):
    event_input = UserEventInput(raw_input, provisional_symbols=("ABC",))
    batch = SourceSubmissionBatch(
        event_input,
        (make_batch_submission("host-event", ("event-hyp",)),),
    )
    rows = (
        make_batch_row(datetime.date(2030, 1, 31), "CALL", "100"),
        make_batch_row(datetime.date(2030, 1, 31), "PUT", "100"),
    )
    return run_event_core(
        event_input,
        grounder=lambda _raw: batch,
        market_bridge=BatchFakeMarketBridge(rows),
        policy=make_batch_policy([]),
    )


class MemoryJournal:
    """Narrow test double for the future worker-owned persistence API."""

    def __init__(self):
        self.runs = {}
        self.events = []
        self.batch_results = {}
        self.batch_case_requests = []

    def create_run(self, *, mode, input, bounds, profile_snapshot, metadata):
        run_id = "run-{}".format(len(self.runs) + 1)
        self.events.append("run_start")
        bounds_snapshot = {
            "max_submissions": bounds.max_submissions,
            "max_hypotheses": bounds.max_hypotheses,
            "max_browser_rows": bounds.max_browser_rows,
            "max_cases": bounds.max_cases,
            "quote_timeout_seconds": bounds.quote_timeout_seconds,
        }
        self.runs[run_id] = {
            "run_id": run_id,
            "mode": mode,
            "input": input,
            "bounds": bounds_snapshot,
            "profile": profile_snapshot,
            "metadata": metadata,
            "status": "RUNNING",
            "diagnostics": [],
            "events": [],
            "cases": [],
            "internal_secret": "private-store-sentinel",
            "internal_snapshot": {"unexpected_secret": "private-snapshot-sentinel"},
        }
        return run_id

    def start_stage(self, run_id, stage_name):
        self.assert_run(run_id)
        self.events.append("stage_started")
        self.runs[run_id]["events"].append(
            {
                "stage": stage_name,
                "event": "stage_started",
                "untrusted_internal_field": "private-event-sentinel",
            }
        )
        return "stage-{}".format(len(self.events))

    def finish_stage(self, run_id, stage_id, *, status, outcome, diagnostics):
        self.assert_run(run_id)
        self.events.append("stage_outcome")
        self.runs[run_id]["events"].append(
            {
                "stage_id": stage_id,
                "event": "stage_outcome",
                "status": status,
                "outcome": outcome,
                "user_text": "private-outcome-sentinel",
            }
        )
        self.runs[run_id]["diagnostics"].extend(diagnostics)

    def finish_run(self, run_id, *, status, diagnostics):
        self.assert_run(run_id)
        self.events.append("terminal")
        self.runs[run_id]["status"] = status
        self.runs[run_id]["diagnostics"] = list(diagnostics)

    def save_direct_result(self, run_id, result):
        self.assert_run(run_id)
        case_id = result.kernel_request.case_id
        summary = {
            "case_id": case_id,
            "classification": result.kernel_result.disposition.value,
            "reasons": [],
        }
        self.runs[run_id]["cases"].append(summary)
        self.runs[run_id].setdefault("direct_case_details", {})[case_id] = {
            "schema_version": "host-direct-case-v0.1",
            **summary,
            "report_cache": (
                None
                if not result.full_report
                else {
                    "renderer_version": "test-renderer",
                    "core_sha256": "test-digest",
                    "text": result.full_report,
                }
            ),
            "core_snapshot": {"private": "snapshot-sentinel"},
            "raw_input": "private-input-sentinel",
        }
        return case_id

    def list_direct_cases(self, run_id):
        self.assert_run(run_id)
        return list(self.runs[run_id]["cases"])

    def get_direct_case(self, run_id, case_id):
        if run_id not in self.runs:
            return None
        return self.runs[run_id].get("direct_case_details", {}).get(case_id)

    @staticmethod
    def _batch_status(result):
        case_set = result.case_set
        if "LIMIT_EXCEEDED" in case_set.reasons:
            return "BLOCKED"
        if case_set.submissions is None or not case_set.submissions.submissions:
            return "BLOCKED"
        if case_set.unavailable:
            return "PARTIAL"
        if case_set.cases:
            return "COMPLETED"
        return "BLOCKED"

    @staticmethod
    def _reason_values(values):
        return [getattr(item, "value", item) for item in values]

    @staticmethod
    def _compact_case(case):
        return {
            "case_id": case.case_id,
            "case_key": hashlib.sha256(case.case_id.encode("utf-8")).hexdigest(),
            "disposition": case.disposition,
            "geometry_status": case.geometry_status,
            "ask_basis_per_underlying_unit": (
                None
                if case.ask_basis_per_underlying_unit is None
                else str(case.ask_basis_per_underlying_unit)
            ),
            "reasons": list(case.reasons),
            "structure_kind": case.structure_kind,
            "legs": [
                {
                    "leg_id": leg.leg_id,
                    "underlying": leg.underlying,
                    "option_type": leg.option_type,
                    "expiration": leg.expiration.isoformat(),
                    "strike": str(leg.strike),
                    "quantity": leg.quantity,
                    "contract_multiplier": leg.contract_multiplier,
                }
                for leg in case.legs
            ],
            "budget_status": case.budget_status,
            "single_cost_upper_bound": (
                None if case.single_cost_upper_bound is None else str(case.single_cost_upper_bound)
            ),
            "repeated_cost_upper_bound": (
                None if case.repeated_cost_upper_bound is None else str(case.repeated_cost_upper_bound)
            ),
            "single_loss_fraction": (
                None if case.single_loss_fraction is None else str(case.single_loss_fraction)
            ),
            "repeated_loss_fraction": (
                None if case.repeated_loss_fraction is None else str(case.repeated_loss_fraction)
            ),
        }

    def save_batch_result(self, run_id, result):
        self.assert_run(run_id)
        self.events.append("batch_archive")
        self.batch_results[run_id] = result
        self.runs[run_id]["batch_status"] = self._batch_status(result)
        return None

    def get_batch_summary(self, run_id):
        result = self.batch_results.get(run_id)
        if result is None:
            return None
        compact = compact_summary(result.case_set)
        return {
            "entry_origin": compact.entry_origin,
            "case_count": compact.case_count,
            "unavailable_count": compact.unavailable_count,
            "disposition_counts": dict(compact.disposition_counts),
            "case_ids": list(compact.case_ids),
            "reasons": list(compact.reasons),
            "case_summaries": [
                self._compact_case(item) for item in compact.case_summaries
            ],
            "unavailable_case_ids": list(compact.unavailable_case_ids),
            "unavailable_cases": [
                {
                    "case_id": item.case_id,
                    "case_key": hashlib.sha256(item.case_id.encode("utf-8")).hexdigest(),
                    "reasons": list(item.reasons),
                }
                for item in result.case_set.unavailable
            ],
            "host_status": self.runs[run_id]["batch_status"],
            "internal_core_json": {"private": "batch-core-private-sentinel"},
            "raw_input": "batch-private-input-sentinel",
        }

    def list_batch_cases(self, run_id):
        result = self.batch_results.get(run_id)
        if result is None:
            return []
        rows = []
        for case in result.case_set.cases:
            reasons = self._reason_values(case.kernel_result.reasons) + list(case.reasons)
            rows.append(
                {
                    "case_id": case.case_id,
                    "case_key": hashlib.sha256(case.case_id.encode("utf-8")).hexdigest(),
                    "classification": case.kernel_result.disposition.value,
                    "reasons": list(dict.fromkeys(reasons)),
                }
            )
        for case in result.case_set.unavailable:
            rows.append(
                {
                    "case_id": case.case_id,
                    "case_key": hashlib.sha256(case.case_id.encode("utf-8")).hexdigest(),
                    "classification": "UNAVAILABLE",
                    "reasons": list(case.reasons),
                }
            )
        return rows

    def get_batch_case(self, run_id, case_key):
        self.batch_case_requests.append((run_id, case_key))
        result = self.batch_results.get(run_id)
        if result is None:
            return None
        for case in result.case_set.cases:
            actual_key = hashlib.sha256(case.case_id.encode("utf-8")).hexdigest()
            if actual_key == case_key:
                from convexity_hunter.core_presentation import report

                reasons = self._reason_values(case.kernel_result.reasons) + list(case.reasons)
                return {
                    "case_id": case.case_id,
                    "case_key": actual_key,
                    "classification": case.kernel_result.disposition.value,
                    "reasons": list(dict.fromkeys(reasons)),
                    "report": report(case),
                    "internal_core_json": {"private": "case-core-private-sentinel"},
                }
        for case in result.case_set.unavailable:
            actual_key = hashlib.sha256(case.case_id.encode("utf-8")).hexdigest()
            if actual_key == case_key:
                return {
                    "case_id": case.case_id,
                    "case_key": actual_key,
                    "classification": "UNAVAILABLE",
                    "reasons": list(case.reasons),
                    "report": None,
                }
        return None

    def assert_run(self, run_id):
        if run_id not in self.runs:
            raise AssertionError("run must exist before its stages")

    def list_runs(self):
        return [dict(run) for run in self.runs.values()]

    def get_run(self, run_id):
        return self.runs.get(run_id)


class HostServerTests(unittest.TestCase):
    def setUp(self):
        self.journal = MemoryJournal()
        self.rendered_tokens = []

        def renderer(token):
            self.rendered_tokens.append(token)
            return (
                "<!doctype html><style>body{color:#123}</style>"
                "<script>window.localCsrf='"
                + token
                + "';</script><script src='/static/app.js'></script>"
            )

        self.server = create_server(
            self.journal,
            render_workbench=renderer,
            port=0,
            request_timeout_seconds=0.5,
        )
        self.port = self.server.server_port
        self.thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.01),
            daemon=True,
        )
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, *, headers=None, body=None, port=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.port if port is None else port, timeout=2
        )
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, response.getheaders(), response.read()
        connection.close()
        return result

    def raw_request(self, request_bytes):
        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as sock:
            sock.sendall(request_bytes)
            response = http.client.HTTPResponse(sock)
            response.begin()
            return response.status, response.getheaders(), response.read()

    def post_headers(self, *, csrf=True, origin=None, port=None, token=None):
        request_port = self.port if port is None else port
        result = {
            "Content-Type": "application/json; charset=utf-8",
            "Host": "127.0.0.1:{}".format(request_port),
        }
        if csrf:
            result[CSRF_HEADER] = self.server.csrf_token if token is None else token
        if origin is not None:
            result["Origin"] = origin
        return result

    @staticmethod
    def decoded(response):
        return json.loads(response[2].decode("utf-8"))

    def test_server_binds_ipv4_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_status_profile_and_response_safety_headers(self):
        status = self.request("GET", "/api/status")
        self.assertEqual(status[0], 200)
        payload = self.decoded(status)
        self.assertEqual(payload["host"], "READY")
        self.assertEqual(payload["journal"], "READY")
        self.assertEqual(payload["ui"], "READY")
        self.assertEqual(payload["configuration"], "NOT_INSPECTED")
        self.assertEqual(
            payload["executors"],
            {
                "world": "NOT_CONFIGURED",
                "event": "NOT_CONFIGURED",
                "direct": "NOT_CONFIGURED",
            },
        )
        self.assertNotIn(b"credential", status[2].lower())
        headers = dict((name.lower(), value) for name, value in status[1])
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        self.assertEqual(headers["cache-control"], "no-store")
        self.assertNotIn("access-control-allow-origin", headers)

        profile = self.request("GET", "/api/profile")
        self.assertEqual(profile[0], 200)
        self.assertEqual(self.decoded(profile), STANDARD_RESEARCH_PROFILE.snapshot())

    def test_status_reports_direct_executor_configuration_only(self):
        server = create_server(
            self.journal,
            render_workbench=lambda _token: "",
            direct_executor=lambda _raw_input, *, bounds: None,
            port=0,
        )
        thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.01), daemon=True
        )
        thread.start()
        try:
            host = self.request(
                "GET", "/api/status", port=server.server_port
            )
            self.assertEqual(host[0], 200)
            self.assertEqual(self.decoded(host)["executors"]["direct"], "CONFIGURED")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_workbench_get_receives_csrf_and_uses_nonce_csp(self):
        response = self.request("GET", "/")
        self.assertEqual(response[0], 200)
        self.assertEqual(len(self.rendered_tokens), 1)
        self.assertEqual(self.rendered_tokens[0], self.server.csrf_token)
        markup = response[2].decode("utf-8")
        self.assertIn(self.server.csrf_token, markup)
        headers = dict((name.lower(), value) for name, value in response[1])
        policy = headers["content-security-policy"]
        self.assertIn("script-src 'nonce-", policy)
        self.assertIn("style-src 'nonce-", policy)
        self.assertIn("default-src 'none'", policy)
        self.assertIn("<script nonce=", markup)
        self.assertIn("<style nonce=", markup)
        self.assertIn("<script src='/static/app.js'></script>", markup)

    def test_run_payload_uses_exact_core_bounds_and_preserves_raw_input(self):
        source = valid_payload()
        request = validate_run_request(json.dumps(source).encode("utf-8"))
        self.assertEqual(request.mode, "world")
        self.assertEqual(request.input, source["input"])
        self.assertEqual(
            request.bounds,
            CoreOperationalBounds(
                max_submissions=2,
                max_hypotheses=3,
                max_browser_rows=20,
                max_cases=8,
                quote_timeout_seconds=2.5,
            ),
        )
        for mode in ("world", "event", "direct"):
            candidate = valid_payload()
            candidate["mode"] = mode
            with self.subTest(mode=mode):
                self.assertEqual(
                    validate_run_request(json.dumps(candidate).encode("utf-8")).mode,
                    mode,
                )

    def test_post_creates_honest_blocked_history_and_reopens_it(self):
        request_data = valid_payload()
        request_data["input"] = "<svg/onload=alert(1)>PRIVATE_USER_INPUT_SENTINEL"
        payload = json.dumps(request_data).encode("utf-8")
        headers = self.post_headers(origin="http://127.0.0.1:{}".format(self.port))
        created = self.request("POST", "/api/runs", headers=headers, body=payload)
        self.assertEqual(created[0], 201)
        response_body = self.decoded(created)
        self.assertEqual(response_body["status"], "BLOCKED")
        self.assertEqual(response_body["reason"], BLOCKED_REASON)
        self.assertNotIn("input", response_body)
        self.assertEqual(
            self.journal.events,
            ["run_start", "stage_started", "stage_outcome", "terminal"],
        )

        run_id = response_body["run_id"]
        history = self.request("GET", "/api/runs")
        self.assertEqual(history[0], 200)
        history_body = self.decoded(history)
        self.assertEqual(len(history_body["runs"]), 1)
        self.assertEqual(
            set(history_body["runs"][0]), {"run_id", "mode", "status", "diagnostics", "events"}
        )
        reopened = self.request("GET", "/api/runs/{}".format(run_id))
        self.assertEqual(reopened[0], 200)
        reopened_body = self.decoded(reopened)
        self.assertEqual(
            self.journal.runs[run_id]["input"], request_data["input"]
        )
        self.assertNotIn(request_data["input"], created[2].decode("utf-8"))
        self.assertNotIn(request_data["input"], history[2].decode("utf-8"))
        self.assertNotIn(request_data["input"], reopened[2].decode("utf-8"))
        for field in (
            "input",
            "raw_input",
            "bounds",
            "profile",
            "profile_snapshot",
            "configuration",
            "configuration_snapshot",
            "versions",
            "execution_snapshot",
            "contract_versions",
            "metadata",
            "snapshot",
            "internal_secret",
            "internal_snapshot",
        ):
            self.assertNotIn(field, reopened_body)
        for sentinel in (
            "private-store-sentinel",
            "private-snapshot-sentinel",
            "private-event-sentinel",
            "private-outcome-sentinel",
        ):
            self.assertNotIn(sentinel, reopened[2].decode("utf-8"))
            self.assertNotIn(sentinel, history[2].decode("utf-8"))
        self.assertEqual(reopened_body["status"], "BLOCKED")
        self.assertEqual(len(reopened_body["events"]), 2)
        self.assertEqual(
            self.journal.runs[run_id]["metadata"]["configuration_snapshot"],
            {"models": [], "sources": [], "skills": []},
        )
        self.assertEqual(
            self.journal.runs[run_id]["metadata"]["contract_versions"]["host_shell"],
            "host-server-v0.1",
        )
        self.assertEqual(
            self.journal.runs[run_id]["metadata"]["contract_versions"]["architecture"],
            "standalone-mvp-architecture-v0.1",
        )
        self.assertEqual(
            set(reopened_body["events"][0]), {"event", "stage"}
        )
        self.assertEqual(
            set(reopened_body["events"][1]),
            {"event", "stage_id", "status", "outcome"},
        )
        self.assertEqual(
            set(reopened_body["events"][1]["outcome"]),
            {"executor_status", "reason", "host_shell_version"},
        )
        self.assertEqual(
            reopened_body["events"][1]["outcome"]["executor_status"],
            "NOT_CONFIGURED",
        )
        self.assertEqual(
            reopened_body["events"][1]["outcome"]["reason"], BLOCKED_REASON
        )

    def test_csrf_host_and_origin_are_enforced(self):
        body = json.dumps(valid_payload()).encode("utf-8")
        no_csrf = self.request(
            "POST", "/api/runs", headers=self.post_headers(csrf=False), body=body
        )
        bad_csrf_headers = self.post_headers()
        bad_csrf_headers[CSRF_HEADER] = "not-the-token"
        bad_csrf = self.request(
            "POST", "/api/runs", headers=bad_csrf_headers, body=body
        )
        bad_origin = self.request(
            "POST",
            "/api/runs",
            headers=self.post_headers(origin="http://attacker.invalid"),
            body=body,
        )
        bad_host_headers = self.post_headers()
        bad_host_headers["Host"] = "attacker.invalid:{}".format(self.port)
        bad_host = self.request(
            "POST", "/api/runs", headers=bad_host_headers, body=body
        )
        self.assertEqual((no_csrf[0], bad_csrf[0]), (403, 403))
        self.assertEqual(bad_origin[0], 403)
        self.assertEqual(bad_host[0], 421)
        self.assertEqual(self.journal.runs, {})

    def test_invalid_payload_is_closed_sanitized_and_not_reflected(self):
        cases = (
            b'{"mode":"world","mode":"event","input":"sentinel-secret-text","bounds":{}}',
            b'{"mode":"world","input":"sentinel-secret-text","bounds":{},"extra":"bad"}',
            b'{"mode":"world","input":"sentinel-secret-text","bounds":{},"x":NaN}',
            b'{"mode":"shell","input":"sentinel-secret-text","bounds":{}}',
            b'{"mode":"world","input":"   ","bounds":{}}',
        )
        for body in cases:
            with self.subTest(body=body[:36]):
                result = self.request(
                    "POST", "/api/runs", headers=self.post_headers(), body=body
                )
                self.assertEqual(result[0], 400)
                self.assertNotIn(b"sentinel-secret-text", result[2])
        self.assertEqual(self.journal.runs, {})

    def test_unknown_bounds_keys_and_bool_or_out_of_range_values_are_rejected(self):
        payload = valid_payload()
        payload["bounds"]["path"] = "/tmp/arbitrary"
        with self.assertRaises(ValueError):
            validate_run_request(json.dumps(payload).encode("utf-8"))

        for key, value in (
            ("max_cases", True),
            ("max_cases", -1),
            ("quote_timeout_seconds", 0),
            ("quote_timeout_seconds", 61),
        ):
            invalid = valid_payload()
            invalid["bounds"][key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError):
                    validate_run_request(json.dumps(invalid).encode("utf-8"))

    def test_body_size_transfer_encoding_and_malformed_content_length(self):
        oversized = (
            "POST /api/runs HTTP/1.1\r\n"
            "Host: 127.0.0.1:{}\r\n"
            "X-CH-CSRF: {}\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: {}\r\n\r\n"
        ).format(self.port, self.server.csrf_token, MAX_REQUEST_BODY_BYTES + 1).encode("ascii")
        self.assertEqual(self.raw_request(oversized)[0], 413)

        malformed = (
            "POST /api/runs HTTP/1.1\r\n"
            "Host: 127.0.0.1:{}\r\n"
            "X-CH-CSRF: {}\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: 4oops\r\n\r\n"
        ).format(self.port, self.server.csrf_token).encode("ascii")
        self.assertEqual(self.raw_request(malformed)[0], 400)

        transfer_encoded = (
            "POST /api/runs HTTP/1.1\r\n"
            "Host: 127.0.0.1:{}\r\n"
            "X-CH-CSRF: {}\r\n"
            "Content-Type: application/json\r\n"
            "Transfer-Encoding: chunked\r\n"
            "Content-Length: 0\r\n\r\n"
        ).format(self.port, self.server.csrf_token).encode("ascii")
        self.assertEqual(self.raw_request(transfer_encoded)[0], 400)

        duplicate_lengths = (
            "POST /api/runs HTTP/1.1\r\n"
            "Host: 127.0.0.1:{}\r\n"
            "X-CH-CSRF: {}\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: 0\r\n"
            "Content-Length: 0\r\n\r\n"
        ).format(self.port, self.server.csrf_token).encode("ascii")
        self.assertEqual(self.raw_request(duplicate_lengths)[0], 400)

    def test_unknown_routes_case_details_and_methods_fail_closed(self):
        self.assertEqual(self.request("GET", "/api/secret-config")[0], 404)
        case = self.request("GET", "/api/runs/run-1/cases/case-1")
        self.assertEqual(case[0], 404)
        self.assertEqual(self.decoded(case), {"error": "case not found"})
        method = self.request("OPTIONS", "/api/runs")
        self.assertEqual(method[0], 405)
        self.assertNotIn(
            "access-control-allow-origin",
            dict((name.lower(), value) for name, value in method[1]),
        )

    def test_real_store_survives_reopen_and_http_never_returns_private_snapshot(self):
        from convexity_hunter.host_store import HostStore

        temporary_root = pathlib.Path(tempfile.gettempdir()).resolve()
        with tempfile.TemporaryDirectory(dir=temporary_root) as external_directory:
            db_path = pathlib.Path(external_directory) / "local-host.sqlite3"
            store = HostStore(db_path)
            first_server = create_server(
                store,
                render_workbench=lambda token: "<!doctype html><meta name='csrf-token' content='{}'>".format(token),
                port=0,
                request_timeout_seconds=0.5,
            )
            first_thread = threading.Thread(
                target=lambda: first_server.serve_forever(poll_interval=0.01),
                daemon=True,
            )
            first_thread.start()
            try:
                request_data = valid_payload()
                request_data["input"] = "<svg/onload=alert(1)>REAL_STORE_PRIVATE_INPUT_SENTINEL"
                response = self.request(
                    "POST",
                    "/api/runs",
                    port=first_server.server_port,
                    headers=self.post_headers(
                        port=first_server.server_port,
                        token=first_server.csrf_token,
                        origin="http://127.0.0.1:{}".format(first_server.server_port),
                    ),
                    body=json.dumps(request_data).encode("utf-8"),
                )
                self.assertEqual(response[0], 201)
                run_id = self.decoded(response)["run_id"]
                self.assertEqual(self.decoded(response)["status"], "BLOCKED")
                self.assertEqual(self.decoded(response)["reason"], BLOCKED_REASON)
                private_snapshot = store.get_run(run_id)
                persisted_input = private_snapshot.get(
                    "input", private_snapshot.get("raw_input")
                )
                self.assertEqual(persisted_input, request_data["input"])
                self.assertEqual(private_snapshot["mode"], request_data["mode"])
                self.assertEqual(private_snapshot["bounds"], request_data["bounds"])
                self.assertEqual(
                    private_snapshot["profile_snapshot"],
                    STANDARD_RESEARCH_PROFILE.snapshot(),
                )
                self.assertEqual(
                    set(private_snapshot["metadata"]),
                    {
                        "configuration_snapshot",
                        "execution_snapshot",
                        "contract_versions",
                    },
                )
                self.assertEqual(
                    private_snapshot["metadata"]["configuration_snapshot"],
                    {"models": [], "sources": [], "skills": []},
                )
                self.assertEqual(
                    private_snapshot["metadata"]["execution_snapshot"], {}
                )
                self.assertEqual(
                    private_snapshot["metadata"]["contract_versions"]["host_shell"],
                    "host-server-v0.1",
                )
                self.assertEqual(
                    private_snapshot["metadata"]["contract_versions"],
                    {
                        "architecture": "standalone-mvp-architecture-v0.1",
                        "host_shell": "host-server-v0.1",
                        "standard_research_profile": "{}:{}".format(
                            STANDARD_RESEARCH_PROFILE.snapshot()["profile_id"],
                            STANDARD_RESEARCH_PROFILE.snapshot()["version"],
                        ),
                    },
                )
            finally:
                first_server.shutdown()
                first_server.server_close()
                first_thread.join(timeout=2)
                store.close()

            reopened_store = HostStore(db_path)
            second_server = create_server(
                reopened_store,
                render_workbench=lambda _token: "<!doctype html>",
                port=0,
                request_timeout_seconds=0.5,
            )
            second_thread = threading.Thread(
                target=lambda: second_server.serve_forever(poll_interval=0.01),
                daemon=True,
            )
            second_thread.start()
            try:
                history = self.request(
                    "GET", "/api/runs", port=second_server.server_port
                )
                detail = self.request(
                    "GET",
                    "/api/runs/{}".format(run_id),
                    port=second_server.server_port,
                )
                self.assertEqual(history[0], 200)
                self.assertEqual(detail[0], 200)
                public_history = self.decoded(history)
                public_detail = self.decoded(detail)
                self.assertEqual(public_detail["run_id"], run_id)
                self.assertEqual(public_detail["status"], "BLOCKED")
                self.assertEqual(
                    set(public_history["runs"][0]),
                    {"run_id", "mode", "status", "created_at", "updated_at"},
                )
                self.assertEqual(
                    set(public_detail),
                    {
                        "run_id",
                        "mode",
                        "status",
                        "created_at",
                        "updated_at",
                        "diagnostics",
                        "events",
                        "batch_summary",
                        "cases",
                    },
                )
                self.assertIsNone(public_detail["batch_summary"])
                self.assertEqual(public_detail["cases"], [])
                self.assertEqual(
                    set(public_detail["events"][0]),
                    {"event", "stage", "stage_id", "status", "started_at"},
                )
                self.assertEqual(
                    set(public_detail["events"][1]),
                    {
                        "event",
                        "stage",
                        "stage_id",
                        "status",
                        "started_at",
                        "completed_at",
                        "outcome",
                        "diagnostics",
                    },
                )
                self.assertNotIn(request_data["input"], response[2].decode("utf-8"))
                self.assertNotIn(request_data["input"], history[2].decode("utf-8"))
                self.assertNotIn(request_data["input"], detail[2].decode("utf-8"))
                for public_run in public_history["runs"] + [public_detail]:
                    for field in (
                        "input",
                        "raw_input",
                        "configuration",
                        "configuration_snapshot",
                        "profile_snapshot",
                        "profile",
                        "operational_bounds",
                        "bounds",
                        "versions",
                        "metadata",
                        "snapshot",
                    ):
                        self.assertNotIn(field, public_run)
                self.assertIn(BLOCKED_REASON, public_detail["diagnostics"])
            finally:
                second_server.shutdown()
                second_server.server_close()
                second_thread.join(timeout=2)
                reopened_store.close()


class HostServerGrounderProjectionTests(unittest.TestCase):
    def test_grounder_stage_outcome_is_public_only_through_closed_projection(self):
        from tests.test_host_store import make_grounder_no_submission_result
        from convexity_hunter.host_store import _grounder_stage_outcome

        outcome = _grounder_stage_outcome(
            make_grounder_no_submission_result("grounder-public-run"),
            "grounder-public-run",
            "synthetic fixture event",
        )
        event = host_server_module._public_event({
            "event": "stage_finished",
            "stage": "grounder",
            "stage_id": "stage-1",
            "status": "COMPLETED",
            "outcome": outcome,
            "diagnostics": ["GROUNDING_NO_SUBMISSION"],
            "started_at": "2026-10-04T00:00:00.000Z",
            "completed_at": "2026-10-04T00:00:01.000Z",
        })
        self.assertEqual(event["stage"], "grounder")
        self.assertEqual(event["outcome"]["source_status"], "UNKNOWN")
        self.assertEqual(event["outcome"]["submission_status"], "MISSING")
        self.assertEqual(event["outcome"]["ei_status"], "NOT_RUN")

        leaked = dict(outcome)
        leaked["raw_model_body"] = "must-not-be-projected"
        invalid_event = host_server_module._public_event({
            "event": "stage_finished",
            "stage": "grounder",
            "stage_id": "stage-1",
            "status": "COMPLETED",
            "outcome": leaked,
            "diagnostics": ["GROUNDING_NO_SUBMISSION"],
        })
        self.assertNotIn("outcome", invalid_event)
        self.assertNotIn("raw_model_body", json.dumps(invalid_event))


class HostServerBatchTests(unittest.TestCase):
    def setUp(self):
        self.journal = MemoryJournal()
        self.server = None

    def tearDown(self):
        self._stop_server()

    def _start_server(
        self,
        *,
        world_executor=None,
        event_executor=None,
        event_grounder=None,
        event_core_executor=None,
    ):
        server = create_server(
            self.journal,
            render_workbench=lambda _token: "<!doctype html>",
            world_executor=world_executor,
            event_executor=event_executor,
            event_grounder=event_grounder,
            event_core_executor=event_core_executor,
            port=0,
            request_timeout_seconds=0.5,
        )
        thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.01), daemon=True
        )
        thread.start()
        server._test_thread = thread
        self.server = server
        return server

    def _stop_server(self):
        server = self.server
        if server is None:
            return
        server.shutdown()
        server.server_close()
        server._test_thread.join(timeout=2)
        self.server = None

    def _request(self, method, path, *, body=None, csrf=False):
        port = self.server.server_port
        headers = {"Host": "127.0.0.1:{}".format(port)}
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if csrf:
            headers[CSRF_HEADER] = self.server.csrf_token
            headers["Origin"] = "http://127.0.0.1:{}".format(port)
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        result = response.status, response.getheaders(), response.read()
        connection.close()
        return result

    @staticmethod
    def _decoded(response):
        return json.loads(response[2].decode("utf-8"))

    def _post(self, raw_input, *, mode="world"):
        body = json.dumps(
            {
                "mode": mode,
                "input": raw_input,
                "bounds": {
                    "max_submissions": 2,
                    "max_hypotheses": 3,
                    "max_browser_rows": 20,
                    "max_cases": 8,
                    "quote_timeout_seconds": 2.5,
                },
            }
        ).encode("utf-8")
        return self._request("POST", "/api/runs", body=body, csrf=True)

    def test_batch_reason_projection_accepts_only_core_limit_reason_grammar(self):
        for label in ("submissions", "hypotheses", "browser_rows", "cases"):
            reason = "{}:5>2".format(label)
            self.assertEqual(
                host_server_module._public_batch_reasons([reason]), [reason]
            )
        for reason in (
            "case_id:5>2",
            "cases:-1>2",
            "cases:5>2 exception text",
            "private exception text",
        ):
            with self.subTest(reason=reason):
                with self.assertRaises(ValueError):
                    host_server_module._public_batch_reasons([reason])

    def test_world_callback_snapshot_full_ordered_archive_and_lazy_keyed_restart(self):
        raw_input = "PRIVATE_BATCH_INPUT_SENTINEL"
        long_id_prefix = "/世界/" + ("x" * 270) + "/"
        result = make_world_batch_result(
            raw_input,
            case_id_transform=lambda case_id: long_id_prefix + case_id,
        )
        calls = []

        def executor(actual_input, *, bounds):
            calls.append((actual_input, bounds))
            self.assertEqual(actual_input, raw_input)
            self.assertEqual(
                self.journal.events,
                ["run_start", "stage_started"],
            )
            return result

        self._start_server(world_executor=executor)
        status = self._decoded(self._request("GET", "/api/status"))
        self.assertEqual(status["executors"]["world"], "CONFIGURED")
        self.assertEqual(status["executors"]["event"], "NOT_CONFIGURED")

        created = self._request("POST", "/api/runs", body=json.dumps({
            "mode": "world",
            "input": raw_input,
            "bounds": {
                "max_submissions": 2,
                "max_hypotheses": 3,
                "max_browser_rows": 20,
                "max_cases": 8,
                "quote_timeout_seconds": 2.5,
            },
        }).encode("utf-8"), csrf=True)
        self.assertEqual(created[0], 201)
        created_body = self._decoded(created)
        self.assertEqual(created_body["status"], "COMPLETED")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], raw_input)
        self.assertIsInstance(calls[0][1], CoreOperationalBounds)
        self.assertEqual(
            self.journal.events,
            ["run_start", "stage_started", "batch_archive", "stage_outcome", "terminal"],
        )
        run_id = created_body["run_id"]
        stored_run = self.journal.get_run(run_id)
        self.assertEqual(
            stored_run["metadata"]["execution_snapshot"],
            {
                "world_executor": {
                    "status": "CONFIGURED",
                    "version": "host-batch-executor-v0.1",
                }
            },
        )
        outcome = stored_run["events"][-1]["outcome"]
        self.assertEqual(
            outcome,
            {
                "schema_version": "host-batch-outcome-v0.1",
                "case_count": 2,
                "unavailable_count": 0,
                "status": "COMPLETED",
            },
        )

        detail_path = "/api/runs/{}".format(run_id)
        public_run_response = self._request("GET", detail_path)
        self.assertEqual(public_run_response[0], 200)
        public_run = self._decoded(public_run_response)
        expected_ids = [case.case_id for case in result.case_set.cases]
        summary = public_run["batch_summary"]
        self.assertEqual(
            set(summary),
            {
                "entry_origin",
                "case_count",
                "unavailable_count",
                "disposition_counts",
                "case_ids",
                "reasons",
                "case_summaries",
                "unavailable_case_ids",
                "unavailable_cases",
                "host_status",
            },
        )
        self.assertNotIn("compact", summary)
        self.assertEqual(summary["case_ids"], expected_ids)
        self.assertEqual(summary["unavailable_case_ids"], [])
        self.assertEqual(summary["unavailable_cases"], [])
        self.assertEqual(summary["host_status"], "COMPLETED")
        self.assertEqual([case["case_id"] for case in public_run["cases"]], expected_ids)
        self.assertEqual(
            [case["case_key"] for case in public_run["cases"]],
            [hashlib.sha256(case_id.encode("utf-8")).hexdigest() for case_id in expected_ids],
        )
        self.assertGreater(len(expected_ids[0]), 256)
        self.assertIn("/世界/", expected_ids[0])
        self.assertEqual(len(public_run["batch_summary"]["case_summaries"]), 2)

        first_key = public_run["cases"][0]["case_key"]
        detail_path = "/api/runs/{}/cases/{}".format(run_id, first_key)
        case_response = self._request("GET", detail_path)
        self.assertEqual(case_response[0], 200)
        public_case = self._decoded(case_response)
        self.assertEqual(public_case["case_id"], expected_ids[0])
        self.assertEqual(public_case["case_key"], first_key)
        self.assertTrue(public_case["report"])
        self.assertEqual(
            self._request("GET", "/api/runs/{}/cases/{}".format(run_id, quote(expected_ids[0], safe="")))[0],
            404,
        )
        for response_body in (created[2], public_run_response[2], case_response[2]):
            for private_value in (
                raw_input.encode("utf-8"),
                b"internal_core_json",
                b"batch-core-private-sentinel",
                b"case-core-private-sentinel",
                b"profile_snapshot",
                b"execution_snapshot",
            ):
                self.assertNotIn(private_value, response_body)
        self.assertEqual(len(calls), 1)

        self._stop_server()
        self._start_server()
        reopened = self._request("GET", detail_path)
        self.assertEqual(reopened[0], 200)
        self.assertEqual(self._decoded(reopened)["case_id"], expected_ids[0])
        self.assertEqual(self._decoded(self._request("GET", detail_path.rsplit("/cases/", 1)[0]))["cases"], public_run["cases"])
        self.assertEqual(self._decoded(self._request("GET", "/api/status"))["executors"]["world"], "NOT_CONFIGURED")
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.journal.batch_case_requests[-1], (run_id, first_key))

    def test_event_callback_binds_description_without_http_constructing_event_input(self):
        raw_input = "event-description-bound-to-the-post"
        result = make_event_batch_result(raw_input)
        calls = []

        def executor(actual_input, *, bounds):
            calls.append(actual_input)
            self.assertEqual(actual_input, raw_input)
            self.assertEqual(result.case_set.raw_input.description, raw_input)
            return result

        self._start_server(event_executor=executor)
        created = self._post(raw_input, mode="event")
        self.assertEqual(created[0], 201)
        self.assertEqual(self._decoded(created)["status"], "COMPLETED")
        self.assertEqual(calls, [raw_input])
        run_id = self._decoded(created)["run_id"]
        self.assertEqual(
            self.journal.get_run(run_id)["metadata"]["execution_snapshot"],
            {
                "event_executor": {
                    "status": "CONFIGURED",
                    "version": "host-batch-executor-v0.1",
                }
            },
        )

    def _event_configuration_snapshot_accessor(self):
        from convexity_hunter.host_event import create_event_grounder
        from tests.test_host_event import _config

        return create_event_grounder(_config(), repo_root=ROOT).configuration_snapshot

    def _new_grounder_store(self, filename):
        from convexity_hunter.host_store import HostStore

        temporary_directory = tempfile.TemporaryDirectory(
            dir=pathlib.Path(tempfile.gettempdir()).resolve()
        )
        store = HostStore(pathlib.Path(temporary_directory.name) / filename)
        self.journal = store
        return temporary_directory, store

    def test_staged_event_no_submission_persists_negative_result_after_run_start(self):
        from tests.test_host_store import make_grounder_no_submission_result

        temporary_directory, store = self._new_grounder_store("grounder-negative.sqlite3")
        timeline = []
        result_by_run = {}
        raw_input = "synthetic fixture event"
        original_create_run = store.create_run

        def create_run(**kwargs):
            timeline.append("create_run")
            return original_create_run(**kwargs)

        store.create_run = create_run

        def snapshot():
            timeline.append("configuration_snapshot")
            return self._event_configuration_snapshot_accessor()()

        def grounder(actual_input, *, run_id, bounds):
            timeline.append("grounder")
            self.assertEqual(actual_input, raw_input)
            self.assertIsInstance(bounds, CoreOperationalBounds)
            run = store.get_run(run_id)
            self.assertEqual(run["status"], "RUNNING")
            self.assertEqual(
                [(event["event"], event["stage"]) for event in run["events"]],
                [("stage_started", "grounder")],
            )
            result = make_grounder_no_submission_result(run_id)
            result_by_run[run_id] = result
            return result

        grounder.configuration_snapshot = snapshot

        def core_executor(*_args, **_kwargs):
            self.fail("Core executor must not run without a source batch")

        try:
            self._start_server(
                event_grounder=grounder,
                event_core_executor=core_executor,
            )
            status = self._decoded(self._request("GET", "/api/status"))
            self.assertEqual(status["executors"]["event"], "CONFIGURED")

            response = self._post(raw_input, mode="event")
            self.assertEqual(response[0], 201)
            body = self._decoded(response)
            self.assertEqual(body["status"], "BLOCKED")
            self.assertEqual(body["reason"], "GROUNDING_NO_SUBMISSION")
            run = store.get_run(body["run_id"])
            self.assertEqual(run["status"], "BLOCKED")
            self.assertEqual(
                [event["stage"] for event in run["events"]], ["grounder", "grounder"]
            )
            self.assertEqual(run["events"][1]["status"], "COMPLETED")
            self.assertEqual(
                run["events"][1]["outcome"]["schema_version"],
                "host-grounder-stage-outcome-v0.1",
            )
            self.assertEqual(
                run["metadata"]["configuration_snapshot"],
                self._event_configuration_snapshot_accessor()(),
            )
            self.assertEqual(
                timeline, ["configuration_snapshot", "create_run", "grounder"]
            )
            self.assertEqual(store.get_batch_summary(body["run_id"]), None)
            self.assertIsNotNone(result_by_run[body["run_id"]])
        finally:
            self._stop_server()
            store.close()
            temporary_directory.cleanup()

    def test_staged_event_positive_submission_is_saved_before_exact_batch_core(self):
        from tests.test_host_store import make_grounder_submission_result

        temporary_directory, store = self._new_grounder_store("grounder-positive.sqlite3")
        raw_input = "synthetic fixture event"
        holder = {}
        core_calls = []
        market_bridge = BatchFakeMarketBridge(())

        def grounder(actual_input, *, run_id, bounds):
            self.assertEqual(actual_input, raw_input)
            self.assertIsInstance(bounds, CoreOperationalBounds)
            run = store.get_run(run_id)
            self.assertEqual(run["status"], "RUNNING")
            self.assertEqual(
                [(event["event"], event["stage"]) for event in run["events"]],
                [("stage_started", "grounder")],
            )
            holder["result"] = make_grounder_submission_result(run_id)
            return holder["result"]

        grounder.configuration_snapshot = self._event_configuration_snapshot_accessor()

        def core_executor(actual_input, *, bounds, source_batch):
            core_calls.append((actual_input, bounds, source_batch))
            self.assertEqual(actual_input, raw_input)
            self.assertIs(source_batch, holder["result"].build_result.source_batch)
            self.assertIsInstance(bounds, CoreOperationalBounds)
            run_id = holder["result"].build_result.context.run_id
            run = store.get_run(run_id)
            self.assertEqual(run["status"], "RUNNING")
            self.assertEqual(
                [(event["event"], event["stage"], event["status"])
                 for event in run["events"]],
                [
                    ("stage_started", "grounder", "RUNNING"),
                    ("stage_finished", "grounder", "COMPLETED"),
                    ("stage_started", "executor", "RUNNING"),
                ],
            )
            saved_outcome = run["events"][1]["outcome"]
            self.assertEqual(saved_outcome["source_status"], "UNKNOWN")
            self.assertEqual(saved_outcome["ei_assessment_status"], "incomplete")
            return run_event_core(
                source_batch.raw_input,
                grounder=lambda candidate: (
                    source_batch if candidate is source_batch.raw_input else None
                ),
                market_bridge=market_bridge,
                policy=make_batch_policy([]),
            )

        try:
            self._start_server(
                event_grounder=grounder,
                event_core_executor=core_executor,
            )
            response = self._post(raw_input, mode="event")
            self.assertEqual(response[0], 201)
            body = self._decoded(response)
            self.assertEqual(body["status"], "BLOCKED")
            self.assertEqual(len(core_calls), 1)
            self.assertIs(
                core_calls[0][2], holder["result"].build_result.source_batch
            )
            self.assertEqual(market_bridge.calls, [])

            run_id = body["run_id"]
            summary = store.get_batch_summary(run_id)
            self.assertIsNotNone(summary)
            self.assertEqual(summary["host_status"], "BLOCKED")
            self.assertEqual(summary["case_count"], 0)
            self.assertEqual(summary["unavailable_count"], 1)
            run = store.get_run(run_id)
            grounder_outcome = run["events"][1]["outcome"]
            self.assertNotIn("submission", grounder_outcome)
            self.assertEqual(grounder_outcome["ei_assessment_status"], "incomplete")
            self.assertIsNone(
                host_server_module._public_outcome(
                    dict(grounder_outcome, ei_assessment_status="INCOMPLETE")
                )
            )

            public_response = self._request("GET", "/api/runs/{}".format(run_id))
            self.assertEqual(public_response[0], 200)
            public = self._decoded(public_response)
            public_grounder_outcome = public["events"][1]["outcome"]
            self.assertEqual(
                public_grounder_outcome["ei_assessment_status"], "incomplete"
            )
            self.assertEqual(public_grounder_outcome["source_status"], "UNKNOWN")
            serialized = json.dumps(public, ensure_ascii=False).encode("utf-8")
            for private_value in (
                b"PRIVATE_SUBMISSION_STATEMENT",
                b"PRIVATE_SUBMISSION_UNCERTAINTY",
                b"private.example/source/private-path",
                b"PRIVATE_SOURCE_TITLE",
            ):
                self.assertNotIn(private_value, serialized)
        finally:
            self._stop_server()
            store.close()
            temporary_directory.cleanup()

    def test_staged_event_failures_use_closed_truthful_codes(self):
        from convexity_hunter.host_grounder_runtime import HostGrounderRuntimeError

        temporary_directory, store = self._new_grounder_store("grounder-failures.sqlite3")

        def grounder(raw_input, *, run_id, bounds):
            del run_id, bounds
            if raw_input == "typed source stop":
                raise HostGrounderRuntimeError("NO_SEARCH_RESULTS")
            raise RuntimeError("PRIVATE_EXCEPTION_PATH_SENTINEL")

        grounder.configuration_snapshot = self._event_configuration_snapshot_accessor()

        def core_executor(*_args, **_kwargs):
            self.fail("Core executor must not run after Grounder failure")

        try:
            self._start_server(
                event_grounder=grounder,
                event_core_executor=core_executor,
            )
            typed_response = self._post("typed source stop", mode="event")
            typed_body = self._decoded(typed_response)
            self.assertEqual(typed_body["status"], "BLOCKED")
            self.assertEqual(typed_body["reason"], "NO_SEARCH_RESULTS")
            self.assertEqual(store.get_run(typed_body["run_id"])["status"], "BLOCKED")

            unexpected_response = self._post("unexpected failure", mode="event")
            unexpected_body = self._decoded(unexpected_response)
            self.assertEqual(unexpected_body["status"], "FAILED")
            self.assertEqual(unexpected_body["reason"], "RUN_CONTEXT_INVALID")
            stored = store.get_run(unexpected_body["run_id"])
            self.assertEqual(stored["status"], "FAILED")
            self.assertNotIn(
                "PRIVATE_EXCEPTION_PATH_SENTINEL",
                json.dumps(stored, ensure_ascii=False),
            )
            self.assertNotIn(b"PRIVATE_EXCEPTION_PATH_SENTINEL", unexpected_response[2])
        finally:
            self._stop_server()
            store.close()
            temporary_directory.cleanup()

    def test_semantic_failure_subcause_projection_is_closed_and_stage_bound(self):
        from convexity_hunter.host_grounder_runtime import HostGrounderRuntimeError

        stage_codes = {
            "semantic_wire_parse": "SEMANTIC_FAILURE_STAGE_WIRE_PARSE",
            "semantic_receipt_construction": "SEMANTIC_FAILURE_STAGE_RECEIPT_CONSTRUCTION",
            "semantic_receipt_validation": "SEMANTIC_FAILURE_STAGE_RECEIPT_VALIDATION",
        }
        check_codes = {
            "wire_decode": "SEMANTIC_FAILURE_CHECK_WIRE_DECODE",
            "topshape": "SEMANTIC_FAILURE_CHECK_TOPSHAPE",
            "run_binding": "SEMANTIC_FAILURE_CHECK_RUN_BINDING",
            "catalog_validation": "SEMANTIC_FAILURE_CHECK_CATALOG_VALIDATION",
            "producer_binding_alignment": "SEMANTIC_FAILURE_CHECK_PRODUCER_BINDING_ALIGNMENT",
            "evidence_ref_expansion": "SEMANTIC_FAILURE_CHECK_EVIDENCE_REF_EXPANSION",
            "internal_verdict_validation": "SEMANTIC_FAILURE_CHECK_INTERNAL_VERDICT_VALIDATION",
        }
        project = host_server_module._semantic_failure_diagnostic_codes

        for stage, stage_code in stage_codes.items():
            with self.subTest(stage=stage):
                error = HostGrounderRuntimeError(
                    "SEMANTIC_VERDICT_REJECTED", failure_stage=stage
                )
                self.assertEqual(project(error), (stage_code,))

        for check, check_code in check_codes.items():
            with self.subTest(check=check):
                error = HostGrounderRuntimeError(
                    "SEMANTIC_VERDICT_REJECTED",
                    failure_stage="semantic_wire_parse",
                    failure_check=check,
                )
                self.assertEqual(
                    project(error),
                    (stage_codes["semantic_wire_parse"], check_code),
                )

        unknown_stage = HostGrounderRuntimeError("SEMANTIC_VERDICT_REJECTED")
        unknown_stage.failure_stage = "PRIVATE_STAGE_SENTINEL"
        unknown_stage.failure_check = "wire_decode"
        self.assertEqual(project(unknown_stage), ())

        bypassed_check = HostGrounderRuntimeError("SEMANTIC_VERDICT_REJECTED")
        bypassed_check.failure_stage = "semantic_receipt_validation"
        bypassed_check.failure_check = "wire_decode"
        bypassed_check.private_detail = "PRIVATE_CHECK_SENTINEL"
        self.assertEqual(
            project(bypassed_check),
            (stage_codes["semantic_receipt_validation"],),
        )

        unknown_check = HostGrounderRuntimeError("SEMANTIC_VERDICT_REJECTED")
        unknown_check.failure_stage = "semantic_wire_parse"
        unknown_check.failure_check = "PRIVATE_CHECK_SENTINEL"
        self.assertEqual(
            project(unknown_check), (stage_codes["semantic_wire_parse"],)
        )

        missing_attrs = HostGrounderRuntimeError("SEMANTIC_VERDICT_REJECTED")
        del missing_attrs.failure_stage
        del missing_attrs.failure_check
        self.assertEqual(project(missing_attrs), ())

        missing_check = HostGrounderRuntimeError(
            "SEMANTIC_VERDICT_REJECTED", failure_stage="semantic_wire_parse"
        )
        del missing_check.failure_check
        self.assertEqual(
            project(missing_check), (stage_codes["semantic_wire_parse"],)
        )

        unrelated = HostGrounderRuntimeError("NO_SEARCH_RESULTS")
        unrelated.failure_stage = "semantic_wire_parse"
        unrelated.failure_check = "wire_decode"
        self.assertEqual(project(unrelated), ())

    def test_semantic_failure_subcauses_survive_store_reload_and_http_history(self):
        from convexity_hunter.host_grounder_runtime import HostGrounderRuntimeError
        from convexity_hunter.host_store import HostStore

        temporary_directory = tempfile.TemporaryDirectory(
            dir=pathlib.Path(tempfile.gettempdir()).resolve()
        )
        db_path = pathlib.Path(temporary_directory.name) / "semantic-failure.sqlite3"
        store = HostStore(db_path)
        self.journal = store
        case_names = (
            "valid semantic cause",
            "unknown semantic stage",
            "bypassed semantic check",
            "unknown semantic check",
            "missing semantic failure attributes",
        )
        run_ids = {}
        core_calls = []

        def grounder(raw_input, *, run_id, bounds):
            del run_id, bounds
            if raw_input == case_names[0]:
                raise HostGrounderRuntimeError(
                    "SEMANTIC_VERDICT_REJECTED",
                    failure_stage="semantic_wire_parse",
                    failure_check="evidence_ref_expansion",
                )
            error = HostGrounderRuntimeError("SEMANTIC_VERDICT_REJECTED")
            if raw_input == case_names[1]:
                error.failure_stage = "PRIVATE_STAGE_SENTINEL"
                error.failure_check = "wire_decode"
                error.private_detail = "PRIVATE_ERROR_ATTRIBUTE_SENTINEL"
            elif raw_input == case_names[2]:
                error.failure_stage = "semantic_receipt_validation"
                error.failure_check = "wire_decode"
                error.private_detail = "PRIVATE_ERROR_ATTRIBUTE_SENTINEL"
            elif raw_input == case_names[3]:
                error.failure_stage = "semantic_wire_parse"
                error.failure_check = "PRIVATE_CHECK_SENTINEL"
                error.private_detail = "PRIVATE_ERROR_ATTRIBUTE_SENTINEL"
            else:
                del error.failure_stage
                del error.failure_check
                error.private_detail = "PRIVATE_ERROR_ATTRIBUTE_SENTINEL"
            raise error

        grounder.configuration_snapshot = self._event_configuration_snapshot_accessor()

        def core_executor(*_args, **_kwargs):
            core_calls.append("core")
            self.fail("Core must not run after semantic Grounder failure")

        try:
            self._start_server(
                event_grounder=grounder,
                event_core_executor=core_executor,
            )
            for raw_input in case_names:
                response = self._post(raw_input, mode="event")
                self.assertEqual(response[0], 201)
                body = self._decoded(response)
                self.assertEqual(body["status"], "BLOCKED")
                self.assertEqual(body["reason"], "SEMANTIC_VERDICT_REJECTED")
                run_ids[raw_input] = body["run_id"]
                run = store.get_run(body["run_id"])
                self.assertEqual(run["status"], "BLOCKED")
                self.assertEqual(
                    run["events"][1]["diagnostics"], ["SEMANTIC_VERDICT_REJECTED"]
                )
                self.assertIsNone(store.get_batch_summary(body["run_id"]))
                for secret in (
                    "PRIVATE_STAGE_SENTINEL",
                    "PRIVATE_CHECK_SENTINEL",
                    "PRIVATE_ERROR_ATTRIBUTE_SENTINEL",
                ):
                    self.assertNotIn(secret, response[2].decode("utf-8"))
                    self.assertNotIn(secret, json.dumps(run, ensure_ascii=False))

            valid_codes = [
                "SEMANTIC_VERDICT_REJECTED",
                "SEMANTIC_FAILURE_STAGE_WIRE_PARSE",
                "SEMANTIC_FAILURE_CHECK_EVIDENCE_REF_EXPANSION",
            ]
            self.assertEqual(
                store.get_run(run_ids[case_names[0]])["diagnostics"], valid_codes
            )
            self.assertEqual(
                store.get_run(run_ids[case_names[1]])["diagnostics"],
                ["SEMANTIC_VERDICT_REJECTED"],
            )
            self.assertEqual(
                store.get_run(run_ids[case_names[2]])["diagnostics"],
                [
                    "SEMANTIC_VERDICT_REJECTED",
                    "SEMANTIC_FAILURE_STAGE_RECEIPT_VALIDATION",
                ],
            )
            self.assertEqual(
                store.get_run(run_ids[case_names[3]])["diagnostics"],
                [
                    "SEMANTIC_VERDICT_REJECTED",
                    "SEMANTIC_FAILURE_STAGE_WIRE_PARSE",
                ],
            )
            self.assertEqual(
                store.get_run(run_ids[case_names[4]])["diagnostics"],
                ["SEMANTIC_VERDICT_REJECTED"],
            )
            self.assertEqual(core_calls, [])

            self._stop_server()
            store.close()
            store = HostStore(db_path)
            self.journal = store
            self._start_server()
            for raw_input, run_id in run_ids.items():
                response = self._request("GET", "/api/runs/{}".format(run_id))
                self.assertEqual(response[0], 200)
                public_run = self._decoded(response)
                expected = (
                    valid_codes
                    if raw_input == case_names[0]
                    else store.get_run(run_id)["diagnostics"]
                )
                self.assertEqual(public_run["diagnostics"], expected)
                self.assertEqual(
                    public_run["events"][1]["diagnostics"],
                    ["SEMANTIC_VERDICT_REJECTED"],
                )
                serialized = response[2].decode("utf-8")
                for secret in (
                    "PRIVATE_STAGE_SENTINEL",
                    "PRIVATE_CHECK_SENTINEL",
                    "PRIVATE_ERROR_ATTRIBUTE_SENTINEL",
                ):
                    self.assertNotIn(secret, serialized)
            self.assertEqual(core_calls, [])
        finally:
            self._stop_server()
            store.close()
            temporary_directory.cleanup()

    def test_missing_tavily_credential_blocks_before_transport_or_core_without_leakage(self):
        from convexity_hunter.host_event import create_event_grounder
        from convexity_hunter.host_sources import TavilyTransportError
        from tests.test_host_event import _config

        transport_calls = []
        core_calls = []

        def transport(*_args, **_kwargs):
            transport_calls.append("transport")
            self.fail("missing credentials must be rejected before HTTP transport")

        grounder = create_event_grounder(
            _config(),
            repo_root=ROOT,
            source_transport=transport,
            discovery_transport=transport,
            semantic_transport=transport,
        )

        def core_executor(*_args, **_kwargs):
            core_calls.append("core")
            self.fail("Core must not run after missing source credentials")

        try:
            self._start_server(
                event_grounder=grounder,
                event_core_executor=core_executor,
            )
            with patch.dict("os.environ", {"SYNTHETIC_TAVILY_KEY": ""}):
                response = self._post("synthetic credential failure", mode="event")

            self.assertEqual(response[0], 201)
            body = self._decoded(response)
            self.assertEqual(body["status"], "BLOCKED")
            self.assertEqual(body["reason"], "SOURCE_CREDENTIAL_UNAVAILABLE")
            self.assertEqual(transport_calls, [])
            self.assertEqual(core_calls, [])
            run = self.journal.get_run(body["run_id"])
            self.assertEqual(run["status"], "BLOCKED")
            self.assertEqual(run["diagnostics"], ["SOURCE_CREDENTIAL_UNAVAILABLE"])
            self.assertNotIn(b"INVALID_API_KEY", response[2])
            self.assertNotIn(b"SYNTHETIC_TAVILY_KEY", response[2])
            self.assertNotIn(
                "INVALID_API_KEY", json.dumps(run, ensure_ascii=False)
            )

            from convexity_hunter.host_sources import TavilyCredentialError

            rejected_key = TavilyTransportError("HTTP_ERROR", status=401)
            self.assertEqual(
                host_server_module._grounder_failure_status(rejected_key),
                ("BLOCKED", "SOURCE_CREDENTIAL_UNAVAILABLE"),
            )
            self.assertEqual(
                host_server_module._grounder_failure_status(
                    TavilyCredentialError("PRIVATE_CREDENTIAL_DIAGNOSTIC")
                ),
                ("BLOCKED", "SOURCE_CREDENTIAL_UNAVAILABLE"),
            )
        finally:
            self._stop_server()

    def test_staged_event_configuration_is_validated_by_store_before_callback(self):
        temporary_directory, store = self._new_grounder_store("grounder-invalid-config.sqlite3")
        called = []

        def grounder(*_args, **_kwargs):
            called.append("grounder")
            raise AssertionError("invalid configuration must stop before Grounder")

        grounder.configuration_snapshot = lambda: {
            "models": [], "sources": [], "skills": [], "unapproved": "PRIVATE_CONFIG_SENTINEL"
        }

        try:
            self._start_server(
                event_grounder=grounder,
                event_core_executor=lambda *_args, **_kwargs: None,
            )
            response = self._post("synthetic fixture event", mode="event")
            self.assertEqual(response[0], 500)
            self.assertEqual(self._decoded(response), {"error": "journal unavailable"})
            self.assertEqual(called, [])
            self.assertEqual(store.list_runs(), [])
            self.assertNotIn(b"PRIVATE_CONFIG_SENTINEL", response[2])
        finally:
            self._stop_server()
            store.close()
            temporary_directory.cleanup()

    def test_real_store_batch_archive_reopens_without_callback_reacquisition(self):
        from convexity_hunter.host_store import HostStore

        temporary_directory = tempfile.TemporaryDirectory(
            dir=pathlib.Path(tempfile.gettempdir()).resolve()
        )
        db_path = pathlib.Path(temporary_directory.name) / "batch.sqlite3"
        store = HostStore(db_path)
        self.journal = store
        raw_input = "durable synthetic World input"
        result = make_world_batch_result(raw_input, approved_profile=True)
        callback_calls = []

        def executor(actual_input, *, bounds):
            callback_calls.append(actual_input)
            self.assertEqual(actual_input, raw_input)
            return result

        try:
            self._start_server(world_executor=executor)
            created = self._post(raw_input)
            self.assertEqual(created[0], 201)
            created_body = self._decoded(created)
            self.assertEqual(created_body["status"], "COMPLETED")
            run_id = created_body["run_id"]
            archived_summary = store.get_batch_summary(run_id)
            self.assertEqual(archived_summary["host_status"], "COMPLETED")
            self.assertEqual(
                archived_summary["case_ids"],
                [case.case_id for case in result.case_set.cases],
            )
            self.assertEqual(
                store.get_run(run_id)["events"][-1]["outcome"],
                {
                    "schema_version": "host-batch-outcome-v0.1",
                    "case_count": 2,
                    "unavailable_count": 0,
                    "status": "COMPLETED",
                },
            )

            run_path = "/api/runs/{}".format(run_id)
            public_run_response = self._request("GET", run_path)
            self.assertEqual(public_run_response[0], 200)
            public_run = self._decoded(public_run_response)
            self.assertEqual(
                [case["case_id"] for case in public_run["cases"]],
                archived_summary["case_ids"],
            )
            case_key = public_run["cases"][0]["case_key"]
            case_path = "{}/cases/{}".format(run_path, case_key)
            case_response = self._request("GET", case_path)
            self.assertEqual(case_response[0], 200)
            self.assertEqual(
                self._decoded(case_response)["case_id"],
                archived_summary["case_ids"][0],
            )
            self.assertEqual(callback_calls, [raw_input])

            self._stop_server()
            store.close()
            store = HostStore(db_path)
            self.journal = store
            self._start_server()
            reopened_run_response = self._request("GET", run_path)
            reopened_case_response = self._request("GET", case_path)
            self.assertEqual(reopened_run_response[0], 200)
            self.assertEqual(reopened_case_response[0], 200)
            self.assertEqual(
                self._decoded(reopened_run_response)["batch_summary"],
                public_run["batch_summary"],
            )
            self.assertEqual(
                self._decoded(reopened_case_response), self._decoded(case_response)
            )
            self.assertEqual(callback_calls, [raw_input])
        finally:
            self._stop_server()
            store.close()
            temporary_directory.cleanup()

    def test_real_store_batch_archive_survives_recovery_before_finalization(self):
        from convexity_hunter.host_store import HostStore

        temporary_directory = tempfile.TemporaryDirectory(
            dir=pathlib.Path(tempfile.gettempdir()).resolve()
        )
        db_path = pathlib.Path(temporary_directory.name) / "interrupted-batch.sqlite3"
        store = HostStore(db_path)
        self.journal = store
        raw_input = "durable synthetic World input before finalization"
        bounds = CoreOperationalBounds(
            max_submissions=2,
            max_hypotheses=3,
            max_browser_rows=20,
            max_cases=8,
            quote_timeout_seconds=2.5,
        )
        result = make_world_batch_result(raw_input, approved_profile=True)
        callback_calls = []

        def executor(actual_input, *, bounds):
            callback_calls.append((actual_input, bounds))
            return result

        try:
            run_id = store.create_run(
                mode="world",
                input=raw_input,
                bounds=bounds,
                profile_snapshot=STANDARD_RESEARCH_PROFILE.snapshot(),
                metadata=host_server_module._run_start_metadata(
                    world_configured=True
                ),
            )
            store.start_stage(run_id, "executor")
            store.save_batch_result(run_id, result)
            archive_before_restart = tuple(
                store._conn().execute(
                    "SELECT archive_json,archive_sha256 FROM batch_archives WHERE run_id=?",
                    (run_id,),
                ).fetchone()
            )
            self.assertEqual(store.get_run(run_id)["status"], "RUNNING")

            store.close()
            store = HostStore(db_path)
            self.journal = store
            self.assertEqual(store.get_run(run_id)["status"], "INTERRUPTED")
            archive_after_recovery = tuple(
                store._conn().execute(
                    "SELECT archive_json,archive_sha256 FROM batch_archives WHERE run_id=?",
                    (run_id,),
                ).fetchone()
            )
            self.assertEqual(archive_after_recovery, archive_before_restart)

            self._start_server(world_executor=executor)
            history_response = self._request("GET", "/api/runs")
            self.assertEqual(history_response[0], 200)
            history = self._decoded(history_response)
            history_run = next(
                item for item in history["runs"] if item["run_id"] == run_id
            )
            self.assertEqual(history_run["status"], "INTERRUPTED")

            run_path = "/api/runs/{}".format(run_id)
            detail_response = self._request("GET", run_path)
            self.assertEqual(detail_response[0], 200)
            detail = self._decoded(detail_response)
            self.assertEqual(detail["status"], "INTERRUPTED")
            self.assertEqual(detail["batch_summary"]["host_status"], "COMPLETED")
            expected_ids = [case.case_id for case in result.case_set.cases]
            self.assertEqual(
                [case["case_id"] for case in detail["cases"]], expected_ids
            )
            self.assertEqual(len(detail["cases"]), 2)

            case_key = detail["cases"][0]["case_key"]
            case_path = "{}/cases/{}".format(run_path, case_key)
            case_response = self._request("GET", case_path)
            self.assertEqual(case_response[0], 200)
            case = self._decoded(case_response)
            self.assertEqual(case["case_id"], expected_ids[0])
            self.assertEqual(case["case_key"], case_key)
            self.assertTrue(case["report"])
            self.assertEqual(callback_calls, [])

            archive_after_reads = tuple(
                store._conn().execute(
                    "SELECT archive_json,archive_sha256 FROM batch_archives WHERE run_id=?",
                    (run_id,),
                ).fetchone()
            )
            self.assertEqual(archive_after_reads, archive_before_restart)
        finally:
            self._stop_server()
            store.close()
            temporary_directory.cleanup()

    def test_partial_all_unavailable_empty_and_limit_statuses_come_from_store(self):
        raw_values = ("partial", "all-unavailable", "empty", "limit")
        base = make_world_batch_result("partial")
        original = base.case_set
        unavailable_case_id = "/世界/" + ("u" * 270) + "/unavailable"
        partial_set = CoreCaseSet(
            "WORLD",
            original.raw_input,
            original.submissions,
            original.cases[:1],
            (
                CoreUnavailableCase(
                    unavailable_case_id, ("MARKET_DATA_UNAVAILABLE",)
                ),
            ),
            (),
        )
        partial = CoreRunResult(partial_set, compact_summary(partial_set))

        empty_raw = "empty"
        empty_set = CoreCaseSet("WORLD", empty_raw, None, (), (), ("EMPTY_SUBMISSION",))
        empty = CoreRunResult(empty_set, compact_summary(empty_set))

        limit_raw = "limit"
        limit_batch = SourceSubmissionBatch(
            limit_raw, original.submissions.submissions
        )
        limit_reason = "cases:9>8"
        limit_set = CoreCaseSet(
            "WORLD",
            limit_raw,
            limit_batch,
            (),
            (),
            ("LIMIT_EXCEEDED", limit_reason),
        )
        limited = CoreRunResult(limit_set, compact_summary(limit_set))

        unavailable_raw = "all-unavailable"
        unavailable_batch = SourceSubmissionBatch(
            unavailable_raw, original.submissions.submissions
        )
        unavailable_set = CoreCaseSet(
            "WORLD",
            unavailable_raw,
            unavailable_batch,
            (),
            (CoreUnavailableCase("unavailable-only", ("MARKET_DATA_UNAVAILABLE",)),),
            (),
        )
        all_unavailable = CoreRunResult(
            unavailable_set, compact_summary(unavailable_set)
        )
        results = {
            "partial": partial,
            "all-unavailable": all_unavailable,
            "empty": empty,
            "limit": limited,
        }
        callback_calls = []

        def executor(raw_input, *, bounds):
            callback_calls.append(raw_input)
            return results[raw_input]

        self._start_server(world_executor=executor)
        expected = {
            "partial": ("PARTIAL", 1, 1),
            "all-unavailable": ("PARTIAL", 0, 1),
            "empty": ("BLOCKED", 0, 0),
            "limit": ("BLOCKED", 0, 0),
        }
        for raw_input in raw_values:
            with self.subTest(raw_input=raw_input):
                response = self._post(raw_input)
                self.assertEqual(response[0], 201)
                body = self._decoded(response)
                status, case_count, unavailable_count = expected[raw_input]
                self.assertEqual(body["status"], status)
                run = self.journal.get_run(body["run_id"])
                self.assertEqual(run["status"], status)
                self.assertEqual(
                    run["events"][-1]["outcome"],
                    {
                        "schema_version": "host-batch-outcome-v0.1",
                        "case_count": case_count,
                        "unavailable_count": unavailable_count,
                        "status": status,
                    },
                )
                summary_response = self._request(
                    "GET", "/api/runs/{}".format(body["run_id"])
                )
                self.assertEqual(summary_response[0], 200)
                summary = self._decoded(summary_response)["batch_summary"]
                self.assertEqual(summary["host_status"], status)
                if raw_input == "partial":
                    self.assertEqual(
                        summary["unavailable_case_ids"], [unavailable_case_id]
                    )
                    self.assertEqual(
                        summary["unavailable_cases"],
                        [
                            {
                                "case_id": unavailable_case_id,
                                "case_key": hashlib.sha256(
                                    unavailable_case_id.encode("utf-8")
                                ).hexdigest(),
                                "reasons": ["MARKET_DATA_UNAVAILABLE"],
                            }
                        ],
                    )
                    self.assertEqual(
                        set(summary["unavailable_cases"][0]),
                        {"case_id", "case_key", "reasons"},
                    )
                elif raw_input == "limit":
                    self.assertEqual(summary["reasons"], ["LIMIT_EXCEEDED", limit_reason])
                    self.assertIn(limit_reason.encode("ascii"), summary_response[2])
        self.assertEqual(callback_calls, list(raw_values))

    def test_executor_errors_invalid_result_and_request_binding_are_sanitized(self):
        valid_other_input = make_world_batch_result("different-private-input")
        wrong_mode_input = UserEventInput("wrong-mode-request")
        wrong_mode_set = CoreCaseSet(
            "EVENT", wrong_mode_input, None, (), (), ("EMPTY_SUBMISSION",)
        )
        wrong_mode = CoreRunResult(wrong_mode_set, compact_summary(wrong_mode_set))
        results = {
            "wrong-input": valid_other_input,
            "wrong-mode": wrong_mode,
            "wrong-type": object(),
        }
        calls = []

        def executor(raw_input, *, bounds):
            calls.append(raw_input)
            if raw_input == "raises":
                raise RuntimeError("PRIVATE_EXCEPTION_TEXT_SENTINEL")
            return results[raw_input]

        self._start_server(world_executor=executor)
        for raw_input, expected_reason in (
            ("raises", "HOST_BATCH_EXECUTOR_FAILED"),
            ("wrong-input", "HOST_BATCH_RESULT_INVALID"),
            ("wrong-mode", "HOST_BATCH_RESULT_INVALID"),
            ("wrong-type", "HOST_BATCH_RESULT_INVALID"),
        ):
            with self.subTest(raw_input=raw_input):
                response = self._post(raw_input)
                self.assertEqual(response[0], 201)
                body = self._decoded(response)
                self.assertEqual(body["status"], "FAILED")
                self.assertEqual(body["reason"], expected_reason)
                self.assertNotIn(b"PRIVATE_EXCEPTION_TEXT_SENTINEL", response[2])
                history = self._request("GET", "/api/runs/{}".format(body["run_id"]))
                self.assertNotIn(b"PRIVATE_EXCEPTION_TEXT_SENTINEL", history[2])
                self.assertEqual(self.journal.batch_results.get(body["run_id"]), None)
        self.assertEqual(calls, ["raises", "wrong-input", "wrong-mode", "wrong-type"])


class HostServerDirectStoreIntegrationTests(unittest.TestCase):
    def setUp(self):
        from convexity_hunter.host_store import HostStore

        self.temporary_directory = tempfile.TemporaryDirectory(
            dir=pathlib.Path(tempfile.gettempdir()).resolve()
        )
        self.db_path = pathlib.Path(self.temporary_directory.name) / "direct.sqlite3"
        self.store = HostStore(self.db_path)
        self.direct_payload = direct_input_payload()
        self.bridge, _verifications, _quotes = direct_bridge_for(self.direct_payload)
        self.invocation_states = []
        self.server = self._start_server(self._executor)

    def tearDown(self):
        self._stop_server()
        self.store.close()
        self.temporary_directory.cleanup()

    def _executor(self, raw_input, *, bounds):
        runs = self.store.list_runs()
        latest = self.store.get_run(runs[-1]["run_id"])
        self.invocation_states.append(
            (latest["status"], latest["events"][-1]["event"])
        )
        if raw_input == "SYNTHETIC_PRECORE_BLOCK":
            structure = parse_direct_input(json.dumps(self.direct_payload)).structure
            return CoreDirectResult(
                raw_input=raw_input,
                core_structure=structure,
                exact_verifications=(),
                native_quotes=(),
                provider_references=(),
                kernel_request=None,
                kernel_result=None,
                reasons=("private-core-reason-sentinel",),
                full_report="",
                blocked=True,
            )
        if raw_input == "SYNTHETIC_EXECUTOR_FAILURE":
            raise RuntimeError("PRIVATE_EXCEPTION_TEXT_SENTINEL")
        return run_direct_input(
            raw_input,
            bounds=bounds,
            exact_provider_bridge=self.bridge,
        )

    def _start_server(self, direct_executor):
        server = create_server(
            self.store,
            render_workbench=lambda _token: "<!doctype html>",
            direct_executor=direct_executor,
            port=0,
            request_timeout_seconds=0.5,
        )
        thread = threading.Thread(
            target=lambda: server.serve_forever(poll_interval=0.01), daemon=True
        )
        thread.start()
        server._test_thread = thread
        return server

    def _stop_server(self):
        server = getattr(self, "server", None)
        if server is None:
            return
        server.shutdown()
        server.server_close()
        server._test_thread.join(timeout=2)
        self.server = None

    @staticmethod
    def _bounds(*, max_cases=8):
        return {
            "max_submissions": 2,
            "max_hypotheses": 3,
            "max_browser_rows": 20,
            "max_cases": max_cases,
            "quote_timeout_seconds": 2.5,
        }

    @staticmethod
    def _decoded(response):
        return json.loads(response[2].decode("utf-8"))

    def _request(self, method, path, *, body=None, csrf=False):
        port = self.server.server_port
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        if csrf:
            headers[CSRF_HEADER] = self.server.csrf_token
            headers["Origin"] = "http://127.0.0.1:{}".format(port)
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        result = response.status, response.getheaders(), response.read()
        connection.close()
        return result

    def _post(self, raw_input, *, max_cases=8):
        request_data = {
            "mode": "direct",
            "input": raw_input,
            "bounds": self._bounds(max_cases=max_cases),
        }
        return self._request(
            "POST",
            "/api/runs",
            body=json.dumps(request_data).encode("utf-8"),
            csrf=True,
        )

    def _assert_stage_paired(self, run_id, *, status, diagnostics):
        snapshot = self.store.get_run(run_id)
        self.assertEqual(snapshot["status"], status)
        self.assertEqual(snapshot["diagnostics"], diagnostics)
        self.assertEqual(len(snapshot["events"]), 2)
        self.assertEqual(snapshot["events"][0]["event"], "stage_started")
        self.assertEqual(snapshot["events"][1]["event"], "stage_finished")
        self.assertEqual(snapshot["events"][1]["status"], status)
        self.assertEqual(snapshot["events"][1]["diagnostics"], diagnostics)

    def test_real_store_direct_success_reopens_with_only_public_case_projection(self):
        status = self._request("GET", "/api/status")
        self.assertEqual(self._decoded(status)["executors"]["direct"], "CONFIGURED")

        raw_input = json.dumps(self.direct_payload)
        created = self._post(raw_input)
        self.assertEqual(created[0], 201)
        response = self._decoded(created)
        self.assertEqual(response["status"], "COMPLETED")
        self.assertEqual(response["classification"], CoreDisposition.DATA_INSUFFICIENT_CORE.value)
        run_id = response["run_id"]
        case_id = response["case_id"]
        self.assertIn(":", case_id)
        self.assertEqual(self.invocation_states, [("RUNNING", "stage_started")])

        private_run = self.store.get_run(run_id)
        self.assertEqual(private_run["status"], "COMPLETED")
        self.assertEqual(
            private_run["metadata"]["execution_snapshot"],
            {
                "direct_executor": {
                    "status": "CONFIGURED",
                    "version": "host-direct-input-v0.1",
                }
            },
        )
        self.assertEqual(
            private_run["events"][1]["outcome"],
            {
                "schema_version": "host-direct-outcome-v0.1",
                "case_id": case_id,
                "classification": CoreDisposition.DATA_INSUFFICIENT_CORE.value,
            },
        )
        self.assertEqual(self.store.list_direct_cases(run_id)[0]["case_id"], case_id)
        self.assertTrue(self.store.get_direct_case(run_id, case_id)["report_cache"]["text"])

        public_run = self._decoded(
            self._request("GET", "/api/runs/{}".format(run_id))
        )
        self.assertEqual(
            public_run["events"][1]["outcome"],
            {
                "schema_version": "host-direct-outcome-v0.1",
                "case_id": case_id,
                "classification": CoreDisposition.DATA_INSUFFICIENT_CORE.value,
            },
        )
        self.assertEqual(set(public_run["cases"][0]), {"case_id", "classification", "reasons"})
        self.assertEqual(public_run["cases"][0]["case_id"], case_id)
        detail_path = "/api/runs/{}/cases/{}".format(run_id, quote(case_id, safe=""))
        public_case_response = self._request("GET", detail_path)
        self.assertEqual(public_case_response[0], 200)
        public_case = self._decoded(public_case_response)
        self.assertEqual(set(public_case), {"case_id", "classification", "reasons", "report"})
        self.assertEqual(public_case["case_id"], case_id)
        self.assertEqual(
            public_case["report"],
            self.store.get_direct_case(run_id, case_id)["report_cache"]["text"],
        )
        for response_body in (created[2], json.dumps(public_run).encode(), public_case_response[2]):
            for private_field in (
                b"core_snapshot",
                b"core_sha256",
                b"profile_snapshot",
                b"raw_input",
                b"PRIVATE_EXCEPTION_TEXT_SENTINEL",
            ):
                self.assertNotIn(private_field, response_body)
        self.assertEqual(
            self._request("GET", "/api/runs/{}/cases/%2F".format(run_id))[0], 404
        )

        self._stop_server()
        self.store.close()
        from convexity_hunter.host_store import HostStore

        self.store = HostStore(self.db_path)
        self.server = self._start_server(None)
        reopened_detail = self._request("GET", detail_path)
        self.assertEqual(reopened_detail[0], 200)
        self.assertEqual(self._decoded(reopened_detail), public_case)
        reopened_run = self._decoded(
            self._request("GET", "/api/runs/{}".format(run_id))
        )
        self.assertEqual(reopened_run["cases"], public_run["cases"])
        self.assertEqual(
            self._decoded(self._request("GET", "/api/status"))["executors"]["direct"],
            "NOT_CONFIGURED",
        )

        blocked = self._decoded(self._post(raw_input))
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertEqual(blocked["reason"], BLOCKED_REASON)
        self._assert_stage_paired(
            blocked["run_id"], status="BLOCKED", diagnostics=[BLOCKED_REASON]
        )
        self.assertEqual(
            self.store.get_run(blocked["run_id"])["metadata"]["execution_snapshot"],
            {},
        )

    def test_invalid_bounds_precore_and_executor_failure_are_paired_and_sanitized(self):
        bridge_calls_before = len(self.bridge.calls)

        invalid = self._decoded(self._post("INVALID_DIRECT_INPUT_PRIVATE_SENTINEL"))
        self.assertEqual(invalid["status"], "BLOCKED")
        self.assertEqual(invalid["reason"], "HOST_DIRECT_INPUT_REJECTED")
        self._assert_stage_paired(
            invalid["run_id"],
            status="BLOCKED",
            diagnostics=["HOST_DIRECT_INPUT_REJECTED"],
        )
        self.assertEqual(len(self.bridge.calls), bridge_calls_before)

        zero_cases = self._decoded(self._post(json.dumps(self.direct_payload), max_cases=0))
        self.assertEqual(zero_cases["status"], "BLOCKED")
        self.assertEqual(zero_cases["reason"], "HOST_DIRECT_BOUNDS_REJECTED")
        self._assert_stage_paired(
            zero_cases["run_id"],
            status="BLOCKED",
            diagnostics=["HOST_DIRECT_BOUNDS_REJECTED"],
        )
        self.assertEqual(len(self.bridge.calls), bridge_calls_before)

        precore = self._decoded(self._post("SYNTHETIC_PRECORE_BLOCK"))
        self.assertEqual(precore["status"], "BLOCKED")
        self.assertEqual(precore["reason"], "HOST_DIRECT_CORE_BLOCKED")
        self._assert_stage_paired(
            precore["run_id"],
            status="BLOCKED",
            diagnostics=["HOST_DIRECT_CORE_BLOCKED"],
        )
        self.assertEqual(self.store.list_direct_cases(precore["run_id"]), [])

        failed_response = self._post("SYNTHETIC_EXECUTOR_FAILURE")
        failed = self._decoded(failed_response)
        self.assertEqual(failed["status"], "FAILED")
        self.assertEqual(failed["reason"], "HOST_DIRECT_EXECUTOR_FAILED")
        self._assert_stage_paired(
            failed["run_id"],
            status="FAILED",
            diagnostics=["HOST_DIRECT_EXECUTOR_FAILED"],
        )
        history = self._request("GET", "/api/runs/{}".format(failed["run_id"]))
        self.assertNotIn(b"PRIVATE_EXCEPTION_TEXT_SENTINEL", failed_response[2])
        self.assertNotIn(b"PRIVATE_EXCEPTION_TEXT_SENTINEL", history[2])
        self.assertNotIn(b"private-core-reason-sentinel", history[2])
        self.assertEqual(
            self.store.list_direct_cases(failed["run_id"]), []
        )


class HostServerCliTests(unittest.TestCase):
    def test_direct_cli_requires_explicit_futu_port_and_opt_in(self):
        invalid_arguments = (
            ("--db", "/tmp/unused.sqlite3", "--enable-direct"),
            ("--db", "/tmp/unused.sqlite3", "--futu-port", "12345"),
            (
                "--db",
                "/tmp/unused.sqlite3",
                "--enable-direct",
                "--futu-port",
                "0",
            ),
        )
        for arguments in invalid_arguments:
            with self.subTest(arguments=arguments):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        host_server_module.main(list(arguments))

    def test_enabled_cli_installs_lazy_direct_executor_without_sdk_startup(self):
        class Journal:
            closed = False

            def close(self):
                self.closed = True

        class Server:
            server_port = 8080
            closed = False

            def serve_forever(self):
                raise KeyboardInterrupt

            def server_close(self):
                self.closed = True

        journal = Journal()
        server = Server()
        executor = lambda _raw_input, *, bounds: None
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch.object(host_server_module, "_open_store", return_value=journal)
            )
            stack.enter_context(
                patch.object(
                    host_server_module,
                    "_load_workbench_renderer",
                    return_value=lambda _token: "",
                )
            )
            make_executor = stack.enter_context(
                patch.object(
                    host_server_module,
                    "_make_futu_direct_executor",
                    return_value=executor,
                )
            )
            create = stack.enter_context(
                patch.object(host_server_module, "create_server", return_value=server)
            )
            open_context = stack.enter_context(
                patch(
                    "convexity_hunter.host_server._open_suppressed_futu_quote_context"
                )
            )
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            result = host_server_module.main(
                [
                    "--db",
                    "/tmp/unused.sqlite3",
                    "--enable-direct",
                    "--futu-port",
                    "12345",
                ]
            )
        self.assertEqual(result, 0)
        make_executor.assert_called_once_with(12345)
        self.assertIs(create.call_args.kwargs["direct_executor"], executor)
        open_context.assert_not_called()
        self.assertTrue(journal.closed)
        self.assertTrue(server.closed)

    def test_constructed_futu_direct_executor_does_not_initialize_sdk(self):
        with patch(
            "convexity_hunter.host_server._open_suppressed_futu_quote_context"
        ) as open_context:
            executor = host_server_module._make_futu_direct_executor(12345)
        self.assertTrue(callable(executor))
        open_context.assert_not_called()

    def test_sdk_output_is_suppressed_across_initialization_operation_and_close(self):
        import types

        import convexity_hunter.providers.futu as futu_provider

        bound_output = io.StringIO()

        class FakeLogger:
            def __init__(self):
                self.file_level = 50
                self.console_level = 50
                self.console_enabled = True
                self.bound_stream_closed = False

            def enable_console_log(self, enabled):
                self.console_enabled = enabled

            def emit(self):
                if self.console_enabled and self.console_level <= 50:
                    bound_output.write("PRIVATE_BOUND_LOG_SENTINEL\n")
                if self.file_level <= 50:
                    bound_output.write("PRIVATE_FILE_LOG_SENTINEL\n")

        logger = FakeLogger()
        observed_levels = []

        class Context:
            closed = False

            def close(self):
                print("PRIVATE_SDK_CLOSE_STDOUT_SENTINEL")
                print("PRIVATE_SDK_CLOSE_STDERR_SENTINEL", file=sys.stderr)
                logger.emit()
                self.closed = True

        context = Context()

        class SDK:
            @staticmethod
            def OpenQuoteContext(*, host, port):
                observed_levels.append(
                    (logger.file_level, logger.console_level, logger.console_enabled)
                )
                print("PRIVATE_SDK_INIT_STDOUT_SENTINEL")
                print("PRIVATE_SDK_INIT_STDERR_SENTINEL", file=sys.stderr)
                logger.emit()
                return context

        expected_result = object()

        def synthetic_run(_raw_input, *, bounds, exact_provider_bridge):
            del bounds
            print("PRIVATE_DIRECT_STDOUT_SENTINEL")
            print("PRIVATE_DIRECT_STDERR_SENTINEL", file=sys.stderr)
            exact_provider_bridge.quote_context_factory().close()
            return expected_result

        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch.object(futu_provider, "_load_futu_sdk", return_value=SDK)
            )
            stack.enter_context(
                patch(
                    "importlib.import_module",
                    return_value=types.SimpleNamespace(logger=logger),
                )
            )
            stack.enter_context(
                patch(
                    "convexity_hunter.host_direct.run_direct_input",
                    side_effect=synthetic_run,
                )
            )
            stack.enter_context(contextlib.redirect_stdout(stdout_capture))
            stack.enter_context(contextlib.redirect_stderr(stderr_capture))
            executor = host_server_module._make_futu_direct_executor(12345)
            result = executor("synthetic", bounds=object())

        self.assertIs(result, expected_result)
        self.assertEqual(stdout_capture.getvalue(), "")
        self.assertEqual(stderr_capture.getvalue(), "")
        self.assertEqual(bound_output.getvalue(), "")
        self.assertEqual(observed_levels, [(sys.maxsize, sys.maxsize, False)])
        self.assertTrue(context.closed)
        self.assertFalse(logger.bound_stream_closed)
        self.assertFalse(host_server_module._SDK_OUTPUT_SINK.closed)

    def test_missing_official_logger_controls_fails_closed_before_quote_context(self):
        import types

        import convexity_hunter.providers.futu as futu_provider

        class SDK:
            called = False

            def OpenQuoteContext(self, *, host, port):
                self.called = True
                return (host, port)

        sdk = SDK()
        with contextlib.ExitStack() as stack:
            stack.enter_context(
                patch.object(futu_provider, "_load_futu_sdk", return_value=sdk)
            )
            stack.enter_context(
                patch(
                    "importlib.import_module",
                    return_value=types.SimpleNamespace(logger=object()),
                )
            )
            with self.assertRaisesRegex(
                RuntimeError, "logging suppression is unavailable"
            ):
                host_server_module._open_suppressed_futu_quote_context(12345)
        self.assertFalse(sdk.called)


if __name__ == "__main__":
    unittest.main()
