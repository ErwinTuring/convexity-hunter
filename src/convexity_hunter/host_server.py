"""Bounded loopback HTTP/CLI shell for the standalone Host.

This module deliberately does not execute World, Event, Direct, provider, model,
or market-data work. Submitted runs are durably represented as blocked until a
trusted executor is explicitly installed.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import secrets
import socket
import sys
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple
from urllib.parse import urlsplit

from .core_application import CoreOperationalBounds
from .host_profile import PROFILE_ID, PROFILE_VERSION, STANDARD_RESEARCH_PROFILE


LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
REQUEST_TIMEOUT_SECONDS = 5.0
MAX_REQUEST_BODY_BYTES = 64 * 1024
CSRF_HEADER = "X-CH-CSRF"
BLOCKED_REASON = "HOST_EXECUTOR_NOT_CONFIGURED"
HOST_SHELL_VERSION = "host-server-v0.1"
ARCHITECTURE_VERSION = "standalone-mvp-architecture-v0.1"
_MODES = frozenset(("world", "event", "direct"))
_BOUNDS_FIELDS = frozenset(
    (
        "max_submissions",
        "max_hypotheses",
        "max_browser_rows",
        "max_cases",
        "quote_timeout_seconds",
    )
)
_RUN_ID_RE = re.compile(r"[A-Za-z0-9._~-]{1,128}\Z", re.ASCII)
_CONTENT_LENGTH_RE = re.compile(r"[0-9]+\Z", re.ASCII)
_INLINE_TAG_RE = re.compile(r"<(script|style)\b([^>]*)>", re.IGNORECASE)
_DIAGNOSTIC_CODE_RE = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z", re.ASCII)
_TIMESTAMP_RE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.+-]+(?:Z|[+-][0-9]{2}:[0-9]{2})\Z",
    re.ASCII,
)
_RUN_STATUSES = frozenset(
    ("QUEUED", "RUNNING", "COMPLETED", "PARTIAL", "BLOCKED", "FAILED", "INTERRUPTED")
)
_STAGE_EVENTS = frozenset(
    ("stage_started", "stage_outcome", "stage_finished", "stage_succeeded", "stage_failed")
)
_STAGE_NAMES = frozenset(("executor",))


class RequestPayloadError(ValueError):
    """An untrusted request failed the closed local API schema."""


@dataclass(frozen=True)
class ValidatedRunRequest:
    mode: str
    input: str
    bounds: CoreOperationalBounds

    def bounds_snapshot(self) -> Dict[str, Any]:
        return {
            "max_submissions": self.bounds.max_submissions,
            "max_hypotheses": self.bounds.max_hypotheses,
            "max_browser_rows": self.bounds.max_browser_rows,
            "max_cases": self.bounds.max_cases,
            "quote_timeout_seconds": self.bounds.quote_timeout_seconds,
        }


def _reject_json_constant(_value: str) -> None:
    raise RequestPayloadError("non-finite JSON number")


def _unique_object_pairs(pairs: list[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RequestPayloadError("duplicate JSON key")
        result[key] = value
    return result


def _strict_json_loads(body: bytes) -> Any:
    try:
        decoded = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise RequestPayloadError("request body is not UTF-8") from error
    try:
        return json.loads(
            decoded,
            object_pairs_hook=_unique_object_pairs,
            parse_constant=_reject_json_constant,
        )
    except RequestPayloadError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        raise RequestPayloadError("malformed JSON") from error


def validate_run_request(body: bytes) -> ValidatedRunRequest:
    """Parse the exact POST /api/runs shape without retaining or echoing input."""

    value = _strict_json_loads(body)
    if type(value) is not dict or set(value) != {"mode", "input", "bounds"}:
        raise RequestPayloadError("request fields do not match the run schema")

    mode = value["mode"]
    if type(mode) is not str or mode not in _MODES:
        raise RequestPayloadError("mode is invalid")

    raw_input = value["input"]
    if type(raw_input) is not str or not raw_input.strip():
        raise RequestPayloadError("input must be a non-empty string")

    raw_bounds = value["bounds"]
    if type(raw_bounds) is not dict or set(raw_bounds) != _BOUNDS_FIELDS:
        raise RequestPayloadError("bounds fields do not match the operational schema")
    for name in (
        "max_submissions",
        "max_hypotheses",
        "max_browser_rows",
        "max_cases",
    ):
        if type(raw_bounds[name]) is not int:
            raise RequestPayloadError("operational integer bound is invalid")
    timeout = raw_bounds["quote_timeout_seconds"]
    try:
        timeout_is_finite = type(timeout) in (int, float) and math.isfinite(timeout)
    except (OverflowError, TypeError, ValueError):
        timeout_is_finite = False
    if not timeout_is_finite:
        raise RequestPayloadError("operational timeout is invalid")
    try:
        bounds = CoreOperationalBounds(
            max_submissions=raw_bounds["max_submissions"],
            max_hypotheses=raw_bounds["max_hypotheses"],
            max_browser_rows=raw_bounds["max_browser_rows"],
            max_cases=raw_bounds["max_cases"],
            quote_timeout_seconds=timeout,
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise RequestPayloadError("operational bounds are invalid") from error
    return ValidatedRunRequest(mode=mode, input=raw_input, bounds=bounds)


def _origin_for_port(port: int) -> str:
    if port == 80:
        return "http://127.0.0.1"
    return "http://127.0.0.1:{}".format(port)


def _configuration_snapshot() -> Dict[str, Any]:
    """Required frozen Store payload, not a claim that host config was inspected."""

    return {"models": [], "sources": [], "skills": []}


def _version_snapshot() -> Dict[str, str]:
    """Real contract versions known to this shell, never guessed from config."""

    return {
        "architecture": ARCHITECTURE_VERSION,
        "host_shell": HOST_SHELL_VERSION,
        "standard_research_profile": "{}:{}".format(PROFILE_ID, PROFILE_VERSION),
    }


def _run_start_metadata() -> Dict[str, Any]:
    return {
        "configuration_snapshot": _configuration_snapshot(),
        "execution_snapshot": {},
        "contract_versions": _version_snapshot(),
    }


def _public_diagnostics(value: Any) -> list[str]:
    if type(value) is not list:
        raise ValueError("stored diagnostics are malformed")
    if any(
        type(item) is not str or _DIAGNOSTIC_CODE_RE.fullmatch(item) is None
        for item in value
    ):
        raise ValueError("stored diagnostics are malformed")
    return list(value)


def _public_outcome(value: Any) -> Optional[Dict[str, str]]:
    if type(value) is str:
        return {"status": value} if value in _RUN_STATUSES else None
    if type(value) is not dict:
        return None
    allowed_values = {
        "executor_status": frozenset(("NOT_CONFIGURED",)),
        "reason": frozenset((BLOCKED_REASON,)),
        "host_shell_version": frozenset((HOST_SHELL_VERSION,)),
    }
    projected = {
        key: item
        for key, item in value.items()
        if key in allowed_values
        and type(item) is str
        and item in allowed_values[key]
    }
    return projected or None


def _public_event(value: Any) -> Optional[Dict[str, Any]]:
    if type(value) is not dict:
        return None
    event_name = value.get("event")
    if type(event_name) is not str or event_name not in _STAGE_EVENTS:
        return None
    projected: Dict[str, Any] = {"event": event_name}
    stage = value.get("stage")
    if type(stage) is str and stage in _STAGE_NAMES:
        projected["stage"] = stage
    stage_id = value.get("stage_id")
    if type(stage_id) is str and _RUN_ID_RE.fullmatch(stage_id) is not None:
        projected["stage_id"] = stage_id
    status = value.get("status")
    if type(status) is str and status in _RUN_STATUSES:
        projected["status"] = status
    outcome = _public_outcome(value.get("outcome"))
    if outcome is not None:
        projected["outcome"] = outcome
    if "diagnostics" in value:
        projected["diagnostics"] = _public_diagnostics(value["diagnostics"])
    for field in ("started_at", "completed_at"):
        timestamp = value.get(field)
        if type(timestamp) is str and _TIMESTAMP_RE.fullmatch(timestamp) is not None:
            projected[field] = timestamp
    return projected


def _public_run(value: Any) -> Dict[str, Any]:
    """Project an internal Store snapshot onto the deliberately small HTTP view."""

    if type(value) is not dict:
        raise ValueError("stored run is malformed")
    run_id = value.get("run_id")
    mode = value.get("mode")
    status = value.get("status")
    if (
        type(run_id) is not str
        or _RUN_ID_RE.fullmatch(run_id) is None
        or type(mode) is not str
        or mode not in _MODES
        or type(status) is not str
        or status not in _RUN_STATUSES
    ):
        raise ValueError("stored run identity or status is malformed")
    projected: Dict[str, Any] = {"run_id": run_id, "mode": mode, "status": status}
    for field in ("created_at", "updated_at"):
        timestamp = value.get(field)
        if type(timestamp) is str and _TIMESTAMP_RE.fullmatch(timestamp) is not None:
            projected[field] = timestamp
    if "diagnostics" in value:
        projected["diagnostics"] = _public_diagnostics(value["diagnostics"])
    if "events" in value:
        events = value["events"]
        if type(events) not in (list, tuple):
            raise ValueError("stored run events are malformed")
        projected["events"] = [
            safe_event
            for item in events
            if (safe_event := _public_event(item)) is not None
        ]
    return projected


def _constant_time_text_match(actual: str, expected: str) -> bool:
    return secrets.compare_digest(actual.encode("utf-8"), expected.encode("utf-8"))


def _host_matches(value: str, port: int) -> bool:
    """Accept only the numeric loopback authority for this listener."""

    try:
        parsed = urlsplit("//" + value)
        return (
            parsed.hostname == LOOPBACK_HOST
            and parsed.port == port
            and parsed.username is None
            and parsed.password is None
            and parsed.path == ""
            and parsed.query == ""
            and parsed.fragment == ""
        )
    except ValueError:
        return False


def _request_route(path: str) -> Tuple[str, ...]:
    """Return a closed route tuple; reject absolute-form and query-string URLs."""

    if not path.startswith("/") or path.startswith("//"):
        return ()
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return ()
    return tuple(parsed.path.split("/"))


def _read_json_body(handler: BaseHTTPRequestHandler) -> bytes:
    transfer_encodings = handler.headers.get_all("Transfer-Encoding", [])
    if transfer_encodings:
        raise RequestPayloadError("transfer encoding is unsupported")
    content_encodings = handler.headers.get_all("Content-Encoding", [])
    if content_encodings and (
        len(content_encodings) != 1
        or content_encodings[0].strip().lower() != "identity"
    ):
        raise RequestPayloadError("content encoding is unsupported")

    lengths = handler.headers.get_all("Content-Length", [])
    if len(lengths) != 1 or _CONTENT_LENGTH_RE.fullmatch(lengths[0].strip()) is None:
        raise RequestPayloadError("content length is invalid")
    try:
        length = int(lengths[0].strip(), 10)
    except (ValueError, OverflowError) as error:
        raise RequestPayloadError("content length is invalid") from error
    if length > MAX_REQUEST_BODY_BYTES:
        raise OverflowError("request body exceeds the configured transport limit")

    content_types = handler.headers.get_all("Content-Type", [])
    if len(content_types) != 1:
        raise RequestPayloadError("content type is invalid")
    media_type, separator, parameters = content_types[0].partition(";")
    if media_type.strip().lower() != "application/json":
        raise RequestPayloadError("content type is invalid")
    if separator and parameters.strip().lower() not in (
        "charset=utf-8",
        "charset=\"utf-8\"",
    ):
        raise RequestPayloadError("content type is invalid")

    try:
        body = handler.rfile.read(length)
    except (OSError, socket.timeout) as error:
        raise TimeoutError("request body read timed out") from error
    if len(body) != length:
        raise RequestPayloadError("request body is incomplete")
    return body


def _content_security_policy(nonce: str) -> str:
    return "; ".join(
        (
            "default-src 'none'",
            "script-src 'nonce-{}'".format(nonce),
            "style-src 'nonce-{}'".format(nonce),
            "connect-src 'self'",
            "img-src 'self'",
            "font-src 'self'",
            "base-uri 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
            "object-src 'none'",
        )
    )


def _nonce_inline_assets(markup: str, nonce: str) -> str:
    """Nonce trusted renderer inline blocks so CSP does not permit inline JS."""

    def add_nonce(match: re.Match[str]) -> str:
        tag_name = match.group(1).lower()
        attributes = match.group(2)
        if tag_name == "script" and re.search(r"(?:^|\s)src\s*=", attributes, re.IGNORECASE):
            return match.group(0)
        if re.search(r"(?:^|\s)nonce\s*=", attributes, re.IGNORECASE):
            attributes = re.sub(
                r"(?:^|\s)nonce\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",
                "",
                attributes,
                count=1,
                flags=re.IGNORECASE,
            )
        return '<{} nonce="{}"{}>'.format(tag_name, nonce, attributes)

    return _INLINE_TAG_RE.sub(add_nonce, markup)


class HostRequestHandler(BaseHTTPRequestHandler):
    """HTTP API; dependencies are attached by ``create_server``."""

    protocol_version = "HTTP/1.1"
    server_version = "ConvexityHunterLocal"
    sys_version = ""

    journal: Any
    render_workbench: Callable[[str], str]

    def log_message(self, _format: str, *args: Any) -> None:
        # Request targets and headers are attacker-controlled and are never logged.
        return

    def send_error(self, code: int, message: Optional[str] = None, explain: Optional[str] = None) -> None:
        del message, explain
        self.close_connection = True
        status = code if code in (400, 404, 405, 408, 413, 415, 417, 421, 431, 500, 501) else 400
        self._send_json(status, {"error": _ERROR_TEXT.get(status, "request rejected")})

    def handle_expect_100(self) -> bool:
        self.send_error(417)
        return False

    def do_GET(self) -> None:
        if not self._validate_local_authority():
            return
        route = _request_route(self.path)
        if route == ("", ""):
            self._serve_workbench()
            return
        if route == ("", "api", "status"):
            self._send_json(
                200,
                {
                    "host": "READY",
                    "journal": "READY",
                    "ui": "READY",
                    "configuration": "NOT_INSPECTED",
                    "executors": {
                        "world": "NOT_CONFIGURED",
                        "event": "NOT_CONFIGURED",
                        "direct": "NOT_CONFIGURED",
                    },
                },
            )
            return
        if route == ("", "api", "profile"):
            self._send_json(200, STANDARD_RESEARCH_PROFILE.snapshot())
            return
        if route == ("", "api", "runs"):
            self._get_runs()
            return
        if len(route) == 4 and route[:2] == ("", "api") and route[2] == "runs":
            if _RUN_ID_RE.fullmatch(route[3]) is None:
                self._send_json(404, {"error": "run not found"})
                return
            self._get_run(route[3])
            return
        if (
            len(route) == 6
            and route[:2] == ("", "api")
            and route[2] == "runs"
            and route[4] == "cases"
        ):
            self._send_json(404, {"error": "case detail unavailable"})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._validate_local_authority():
            return
        if _request_route(self.path) != ("", "api", "runs"):
            self._send_json(404, {"error": "not found"})
            return
        csrf_values = self.headers.get_all(CSRF_HEADER, [])
        if (
            len(csrf_values) != 1
            or not _constant_time_text_match(csrf_values[0], self.server.csrf_token)
        ):
            self._send_json(403, {"error": "request rejected"})
            return
        try:
            body = _read_json_body(self)
        except OverflowError:
            self._send_json(413, {"error": "request body too large"})
            return
        except TimeoutError:
            self._send_json(408, {"error": "request timed out"})
            return
        except RequestPayloadError:
            self._send_json(400, {"error": "invalid request"})
            return
        try:
            request = validate_run_request(body)
        except RequestPayloadError:
            self._send_json(400, {"error": "invalid request"})
            return
        self._post_run(request)

    def do_HEAD(self) -> None:
        self._method_not_allowed()

    def do_OPTIONS(self) -> None:
        self._method_not_allowed()

    def do_PUT(self) -> None:
        self._method_not_allowed()

    def do_PATCH(self) -> None:
        self._method_not_allowed()

    def do_DELETE(self) -> None:
        self._method_not_allowed()

    def _method_not_allowed(self) -> None:
        if not self._validate_local_authority():
            return
        self.send_response(405)
        self.send_header("Allow", "GET, POST")
        body = b'{"error":"method not allowed"}'
        self._write_common_headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _validate_local_authority(self) -> bool:
        self.close_connection = True
        host_values = self.headers.get_all("Host", [])
        if len(host_values) != 1 or not _host_matches(
            host_values[0].strip(), self.server.server_port
        ):
            self._send_json(421, {"error": "request rejected"})
            return False
        origin_values = self.headers.get_all("Origin", [])
        if len(origin_values) > 1 or (
            origin_values
            and not _constant_time_text_match(
                origin_values[0], _origin_for_port(self.server.server_port)
            )
        ):
            self._send_json(403, {"error": "request rejected"})
            return False
        return True

    def _serve_workbench(self) -> None:
        try:
            markup = self.server.render_workbench(self.server.csrf_token)
            if type(markup) is not str:
                raise TypeError("renderer returned non-text")
        except Exception:
            self._send_json(500, {"error": "workbench unavailable"})
            return
        nonce = secrets.token_urlsafe(18)
        markup = _nonce_inline_assets(markup, nonce)
        self.send_response(200)
        self.send_header("Content-Security-Policy", _content_security_policy(nonce))
        self._write_common_headers("text/html; charset=utf-8", len(markup.encode("utf-8")))
        self.end_headers()
        self.wfile.write(markup.encode("utf-8"))

    def _get_runs(self) -> None:
        try:
            result = self.server.journal.list_runs()
            if type(result) is not list:
                raise ValueError("journal returned malformed run list")
            public_runs = [_public_run(item) for item in result]
        except Exception:
            self._send_json(500, {"error": "journal unavailable"})
            return
        self._send_json(200, {"runs": public_runs})

    def _get_run(self, run_id: str) -> None:
        try:
            result = self.server.journal.get_run(run_id)
            public_run = None if result is None else _public_run(result)
        except Exception:
            self._send_json(500, {"error": "journal unavailable"})
            return
        if public_run is None:
            self._send_json(404, {"error": "run not found"})
            return
        self._send_json(200, public_run)

    def _post_run(self, request: ValidatedRunRequest) -> None:
        try:
            # Persist each append-only boundary explicitly. No research callable
            # is reachable from this slice.
            run_id = self.server.journal.create_run(
                mode=request.mode,
                input=request.input,
                bounds=request.bounds,
                profile_snapshot=STANDARD_RESEARCH_PROFILE.snapshot(),
                metadata=_run_start_metadata(),
            )
            if type(run_id) is not str or _RUN_ID_RE.fullmatch(run_id) is None:
                raise ValueError("journal returned an invalid run identifier")
            stage_id = self.server.journal.start_stage(run_id, "executor")
            self.server.journal.finish_stage(
                run_id,
                stage_id,
                status="BLOCKED",
                outcome={
                    "executor_status": "NOT_CONFIGURED",
                    "reason": BLOCKED_REASON,
                    "host_shell_version": HOST_SHELL_VERSION,
                },
                diagnostics=(BLOCKED_REASON,),
            )
            self.server.journal.finish_run(
                run_id,
                status="BLOCKED",
                diagnostics=(BLOCKED_REASON,),
            )
        except Exception:
            self._send_json(500, {"error": "journal unavailable"})
            return
        # Do not reflect raw input or persistence internals in the POST response.
        self._send_json(
            201,
            {
                "run_id": run_id,
                "status": "BLOCKED",
                "reason": BLOCKED_REASON,
            },
        )

    def _send_json(self, status: int, payload: Mapping[str, Any]) -> None:
        try:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError):
            status = 500
            body = b'{"error":"response unavailable"}'
        self.send_response(status)
        self._write_common_headers("application/json; charset=utf-8", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _write_common_headers(self, content_type: str, content_length: int) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(content_length))
        self.send_header("Connection", "close")


_ERROR_TEXT = {
    400: "invalid request",
    404: "not found",
    405: "method not allowed",
    408: "request timed out",
    413: "request body too large",
    415: "unsupported media type",
    417: "expectation failed",
    421: "request rejected",
    431: "request headers too large",
    500: "internal error",
}


def create_server(
    journal: Any,
    *,
    render_workbench: Callable[[str], str],
    port: int = DEFAULT_PORT,
    request_timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
) -> HTTPServer:
    """Create an HTTP server bound exclusively to numeric IPv4 loopback."""

    if type(port) is not int or isinstance(port, bool) or not 0 <= port <= 65535:
        raise ValueError("port must be an integer in the TCP port range")
    if (
        type(request_timeout_seconds) not in (int, float)
        or not math.isfinite(request_timeout_seconds)
        or request_timeout_seconds <= 0
    ):
        raise ValueError("request timeout must be a finite positive number")

    class _LoopbackHTTPServer(HTTPServer):
        allow_reuse_address = False

        def handle_error(self, _request: Any, _client_address: Any) -> None:
            # Never print tracebacks that may include request-adjacent data.
            return

        def get_request(self) -> Tuple[socket.socket, Any]:
            request, client_address = super().get_request()
            request.settimeout(float(request_timeout_seconds))
            return request, client_address

    server = _LoopbackHTTPServer(
        (LOOPBACK_HOST, port),
        HostRequestHandler,
        bind_and_activate=True,
    )
    server.journal = journal
    server.render_workbench = render_workbench
    server.csrf_token = secrets.token_urlsafe(32)
    return server


def _open_store(db_path: Path) -> Any:
    """Open the worker-owned Store, which enforces the external-path boundary."""

    from .host_store import HostStore  # Imported lazily to keep CLI imports inert.

    return HostStore(db_path)


def _load_workbench_renderer() -> Callable[[str], str]:
    from .host_workbench import render_workbench

    return render_workbench


def _positive_cli_port(value: str) -> int:
    try:
        port = int(value, 10)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Convexity Hunter local Host.")
    parser.add_argument("--db", required=True, type=Path, help="external SQLite journal path")
    parser.add_argument(
        "--port",
        type=_positive_cli_port,
        default=DEFAULT_PORT,
        help="loopback TCP port (default: 8080)",
    )
    args = parser.parse_args(argv)

    journal = None
    server = None
    try:
        journal = _open_store(args.db)
        server = create_server(
            journal,
            render_workbench=_load_workbench_renderer(),
            port=args.port,
        )
        print("Convexity Hunter local Host: http://127.0.0.1:{}".format(server.server_port))
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except Exception:
        # Do not expose the database path or low-level filesystem exception.
        print("local Host could not start", file=sys.stderr)
        return 2
    finally:
        if server is not None:
            server.server_close()
        if journal is not None:
            close = getattr(journal, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
