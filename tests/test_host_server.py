"""Synthetic, stdlib-only loopback tests for the bounded Host HTTP shell."""

import http.client
import json
import pathlib
import socket
import sys
import tempfile
import threading
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter.core_application import CoreOperationalBounds
from convexity_hunter.host_profile import STANDARD_RESEARCH_PROFILE
from convexity_hunter.host_server import (
    BLOCKED_REASON,
    CSRF_HEADER,
    MAX_REQUEST_BODY_BYTES,
    create_server,
    validate_run_request,
)


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


class MemoryJournal:
    """Narrow test double for the future worker-owned persistence API."""

    def __init__(self):
        self.runs = {}
        self.events = []

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
        self.assertEqual(self.decoded(case), {"error": "case detail unavailable"})
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
                    },
                )
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


if __name__ == "__main__":
    unittest.main()
