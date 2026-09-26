"""Bounded, free-only Tavily Search/Extract transport.

This module is deliberately only a source transport.  It does not interpret
source text, construct Event Intelligence records, or call Core.  Returned
source text is untrusted transient grounding material.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
import socket
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


__all__ = (
    "TavilyCredentialError",
    "TavilyCredentialRef",
    "TavilyConfigurationError",
    "TavilyCoverage",
    "TavilyExtractResult",
    "TavilyFailedExtract",
    "TavilyReceipt",
    "TavilySearchResult",
    "TavilySourceBody",
    "TavilySourceClient",
    "TavilySourceConfig",
    "TavilySourceReference",
    "TavilyTransportError",
)


_SEARCH_ENDPOINT = "https://api.tavily.com/search"
_EXTRACT_ENDPOINT = "https://api.tavily.com/extract"
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CREDENTIAL_PROPERTY_KEYS = frozenset(("api_key", "TAVILY_API_KEY"))
_SENSITIVE_QUERY_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "auth",
        "client_secret",
        "cookie",
        "credential",
        "jwt",
        "password",
        "passwd",
        "private_key",
        "refresh_token",
        "secret",
        "session",
        "signature",
        "sig",
        "token",
        "access_token",
    }
)
_LOCAL_HOST_NAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata",
        "metadata.google.internal",
    }
)


class TavilyConfigurationError(ValueError):
    """A rejected non-secret source configuration."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"TavilyConfigurationError(code={self.code!r})"


class TavilyCredentialError(ValueError):
    """A rejected or unavailable explicitly referenced credential."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"TavilyCredentialError(code={self.code!r})"


class TavilyTransportError(RuntimeError):
    """A sanitized source transport or response-envelope failure."""

    def __init__(self, code: str, *, status: Optional[int] = None) -> None:
        self.code = code
        self.status = status
        message = code if status is None else f"{code} status={status}"
        super().__init__(message)

    def __repr__(self) -> str:
        return f"TavilyTransportError(code={self.code!r}, status={self.status!r})"


def _require_text(name: str, value: object, *, nonempty: bool = True) -> str:
    if type(value) is not str:
        raise TavilyConfigurationError(f"INVALID_{name.upper()}")
    if value != value.strip() or any(
        ord(character) < 32 or ord(character) == 127 for character in value
    ):
        raise TavilyConfigurationError(f"INVALID_{name.upper()}")
    if nonempty and not value:
        raise TavilyConfigurationError(f"INVALID_{name.upper()}")
    return value


def _positive_int(name: str, value: object) -> int:
    if type(value) is not int or value <= 0:
        raise TavilyConfigurationError(f"INVALID_{name.upper()}")
    return value


def _positive_float(name: str, value: object) -> float:
    if (
        type(value) not in (int, float)
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or value <= 0
    ):
        raise TavilyConfigurationError(f"INVALID_{name.upper()}")
    return float(value)


def _validate_api_key(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value != value.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise TavilyCredentialError("INVALID_API_KEY")
    return value


@dataclass(frozen=True, repr=False)
class TavilyCredentialRef:
    """One explicit environment or external-properties-file reference.

    No ambient discovery is performed.  In particular this type never looks
    for a default environment variable, dotenv file, keychain, or config file.
    """

    properties_path: Optional[Union[str, os.PathLike[str]]] = None
    env_name: Optional[str] = None

    def __post_init__(self) -> None:
        has_path = self.properties_path is not None
        has_env = self.env_name is not None
        if has_path == has_env:
            raise TavilyCredentialError("EXACTLY_ONE_CREDENTIAL_SOURCE_REQUIRED")
        if has_env:
            if type(self.env_name) is not str or not _ENV_NAME.fullmatch(self.env_name):
                raise TavilyCredentialError("INVALID_ENVIRONMENT_NAME")
            return
        try:
            path = Path(self.properties_path)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise TavilyCredentialError("INVALID_PROPERTIES_PATH") from None
        if not path.is_absolute():
            raise TavilyCredentialError("PROPERTIES_PATH_MUST_BE_ABSOLUTE")
        object.__setattr__(self, "properties_path", path)

    def __repr__(self) -> str:
        source = "environment" if self.env_name is not None else "properties_file"
        return f"TavilyCredentialRef(source={source!r})"

    def resolve(self, *, repo_root: Union[str, os.PathLike[str]]) -> str:
        """Read only this explicitly selected source and return its key."""

        if self.env_name is not None:
            value = os.environ.get(self.env_name)
            if value is None:
                raise TavilyCredentialError("CREDENTIAL_UNAVAILABLE")
            return _validate_api_key(value)

        try:
            root = Path(repo_root).resolve(strict=True)
            candidate = Path(self.properties_path).resolve(strict=True)  # type: ignore[arg-type]
        except (OSError, RuntimeError, TypeError, ValueError):
            raise TavilyCredentialError("CREDENTIAL_UNAVAILABLE") from None
        if not root.is_dir() or not candidate.is_file():
            raise TavilyCredentialError("CREDENTIAL_UNAVAILABLE")
        try:
            candidate.relative_to(root)
        except ValueError:
            pass
        else:
            raise TavilyCredentialError("CREDENTIAL_PATH_INSIDE_REPOSITORY")

        try:
            text = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise TavilyCredentialError("CREDENTIAL_UNAVAILABLE") from None
        found: Optional[str] = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if (
                separator != "="
                or key.strip() not in _CREDENTIAL_PROPERTY_KEYS
                or found is not None
            ):
                raise TavilyCredentialError("INVALID_PROPERTIES_FILE")
            found = value.strip()
        if found is None:
            raise TavilyCredentialError("CREDENTIAL_UNAVAILABLE")
        return _validate_api_key(found)


@dataclass(frozen=True, repr=False)
class TavilySourceConfig:
    """Explicit, bounded free-only transport configuration."""

    credential_ref: TavilyCredentialRef
    paygo_off_confirmed: bool
    request_budget: int
    credit_budget: int
    max_request_bytes: int
    max_response_bytes: int
    timeout_seconds: float
    time_budget_seconds: Optional[float] = None
    byte_budget: Optional[int] = None
    max_search_results: int = 5
    max_extract_urls: int = 5

    def __post_init__(self) -> None:
        if type(self.credential_ref) is not TavilyCredentialRef:
            raise TavilyConfigurationError("INVALID_CREDENTIAL_REF")
        if type(self.paygo_off_confirmed) is not bool:
            raise TavilyConfigurationError("INVALID_PAYGO_OFF_CONFIRMED")
        if not self.paygo_off_confirmed:
            raise TavilyConfigurationError("PAYGO_OFF_NOT_CONFIRMED")
        _positive_int("request_budget", self.request_budget)
        _positive_int("credit_budget", self.credit_budget)
        _positive_int("max_request_bytes", self.max_request_bytes)
        _positive_int("max_response_bytes", self.max_response_bytes)
        _positive_float("timeout_seconds", self.timeout_seconds)
        if self.time_budget_seconds is not None:
            _positive_float("time_budget_seconds", self.time_budget_seconds)
        if self.byte_budget is not None:
            _positive_int("byte_budget", self.byte_budget)
        if type(self.max_search_results) is not int or not 1 <= self.max_search_results <= 20:
            raise TavilyConfigurationError("INVALID_MAX_SEARCH_RESULTS")
        if type(self.max_extract_urls) is not int or not 1 <= self.max_extract_urls <= 5:
            raise TavilyConfigurationError("INVALID_MAX_EXTRACT_URLS")

    def __repr__(self) -> str:
        return (
            "TavilySourceConfig("
            f"paygo_off_confirmed={self.paygo_off_confirmed!r}, "
            f"request_budget={self.request_budget}, credit_budget={self.credit_budget}, "
            f"max_request_bytes={self.max_request_bytes}, "
            f"max_response_bytes={self.max_response_bytes}, "
            f"timeout_seconds={self.timeout_seconds!r})"
        )


@dataclass(frozen=True, repr=False)
class TavilySourceReference:
    """One ordered Search result; publication is not an event date."""

    source_id: str
    url: str
    title: str
    snippet: str
    publication_date: Optional[str]
    provider_result_id: Optional[str]
    native_score: Optional[float]
    verified: bool = False

    @property
    def content(self) -> str:
        return self.snippet

    @property
    def published_at(self) -> Optional[str]:
        return self.publication_date

    def __repr__(self) -> str:
        return (
            "TavilySourceReference("
            f"source_id={self.source_id!r}, url={self.url!r}, "
            f"publication_date={self.publication_date!r}, verified={self.verified!r})"
        )


@dataclass(frozen=True, repr=False)
class TavilySourceBody:
    """Transient, untrusted Extract body; no semantic verification is implied."""

    source_id: str
    url: str
    body: str
    publication_date: Optional[str]
    provider_result_id: Optional[str]
    verified: bool = False

    @property
    def content(self) -> str:
        return self.body

    def __repr__(self) -> str:
        return (
            "TavilySourceBody("
            f"source_id={self.source_id!r}, url={self.url!r}, "
            f"body_bytes={len(self.body.encode('utf-8'))}, verified={self.verified!r})"
        )


@dataclass(frozen=True, repr=False)
class TavilyFailedExtract:
    """A failed URL with a sanitized reason and stable source identity."""

    source_id: str
    url: str
    reason_code: str

    def __repr__(self) -> str:
        return (
            "TavilyFailedExtract("
            f"source_id={self.source_id!r}, url={self.url!r}, "
            f"reason_code={self.reason_code!r})"
        )


@dataclass(frozen=True, repr=False)
class TavilyCoverage:
    """Counts and ordered identities; this is not a Core completion status."""

    requested_count: int
    returned_count: int
    failed_count: int
    source_ids: Tuple[str, ...]
    failed_source_ids: Tuple[str, ...]
    status: str

    @property
    def is_complete(self) -> bool:
        return self.status == "COMPLETE"

    def __repr__(self) -> str:
        return (
            "TavilyCoverage("
            f"requested_count={self.requested_count}, returned_count={self.returned_count}, "
            f"failed_count={self.failed_count}, status={self.status!r})"
        )


@dataclass(frozen=True, repr=False)
class TavilyReceipt:
    """Sanitized per-call receipt; provider usage is observational only."""

    operation: str
    endpoint: str
    request_id: str
    reserved_requests: int
    reserved_credits: int
    reported_credits: Optional[int]
    request_bytes: int
    response_bytes: int
    elapsed_seconds: float
    source_ids: Tuple[str, ...]
    returned_count: int
    failed_count: int

    @property
    def credits_reserved(self) -> int:
        return self.reserved_credits

    @property
    def credits_reported(self) -> Optional[int]:
        return self.reported_credits

    @property
    def bytes_sent(self) -> int:
        return self.request_bytes

    @property
    def bytes_received(self) -> int:
        return self.response_bytes

    def __repr__(self) -> str:
        return (
            "TavilyReceipt("
            f"operation={self.operation!r}, request_id={self.request_id!r}, "
            f"reserved_credits={self.reserved_credits}, "
            f"reported_credits={self.reported_credits!r}, "
            f"request_bytes={self.request_bytes}, response_bytes={self.response_bytes}, "
            f"returned_count={self.returned_count}, failed_count={self.failed_count})"
        )


@dataclass(frozen=True, repr=False)
class TavilySearchResult:
    query: str
    sources: Tuple[TavilySourceReference, ...]
    receipt: TavilyReceipt
    coverage: TavilyCoverage

    def __repr__(self) -> str:
        return (
            "TavilySearchResult("
            f"source_count={len(self.sources)}, coverage={self.coverage!r}, "
            f"receipt={self.receipt!r})"
        )


@dataclass(frozen=True, repr=False)
class TavilyExtractResult:
    urls: Tuple[str, ...]
    bodies: Tuple[TavilySourceBody, ...]
    failed_extracts: Tuple[TavilyFailedExtract, ...]
    receipt: TavilyReceipt
    coverage: TavilyCoverage
    query: Optional[str] = None

    @property
    def sources(self) -> Tuple[TavilySourceBody, ...]:
        return self.bodies

    def __repr__(self) -> str:
        return (
            "TavilyExtractResult("
            f"body_count={len(self.bodies)}, failed_count={len(self.failed_extracts)}, "
            f"coverage={self.coverage!r}, receipt={self.receipt!r})"
        )


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _default_transport(request: Request, timeout_seconds: float) -> Any:
    return build_opener(_NoRedirectHandler()).open(request, timeout=timeout_seconds)


def _safe_error(code: str, *, status: Optional[int] = None) -> TavilyTransportError:
    return TavilyTransportError(code, status=status)


def _is_private_host(hostname: str) -> bool:
    normalized = hostname.lower().rstrip(".")
    if normalized in _LOCAL_HOST_NAMES or normalized.endswith((".localhost", ".local", ".internal")):
        return True
    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _validate_public_url(value: object, *, error_code: str = "UNSAFE_SOURCE_URL") -> str:
    if type(value) is not str or not value or value != value.strip():
        raise TavilyTransportError(error_code)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise TavilyTransportError(error_code)
    if "\\" in value:
        raise TavilyTransportError(error_code)
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise TavilyTransportError(error_code) from None
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise TavilyTransportError(error_code)
    if parsed.username is not None or parsed.password is not None:
        raise TavilyTransportError(error_code)
    if hostname is None or not hostname or _is_private_host(hostname):
        raise TavilyTransportError(error_code)
    if port is not None and not 1 <= port <= 65535:
        raise TavilyTransportError(error_code)
    if parsed.fragment:
        raise TavilyTransportError(error_code)
    try:
        pairs = parse_qsl(unquote(parsed.query), keep_blank_values=True, strict_parsing=False)
    except ValueError:
        raise TavilyTransportError(error_code) from None
    for key, _ in pairs:
        normalized_key = key.lower().replace("-", "_")
        if normalized_key in _SENSITIVE_QUERY_NAMES:
            raise TavilyTransportError(error_code)
    return value


def _url_source_id(url: str) -> str:
    return "url:" + hashlib.sha256(url.encode("utf-8")).hexdigest()


def _validate_provider_id(value: object) -> Optional[str]:
    if value is None:
        return None
    if type(value) is not str or not value or value != value.strip() or len(value) > 256:
        raise TavilyTransportError("MALFORMED_RESPONSE")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise TavilyTransportError("MALFORMED_RESPONSE")
    return value


def _validate_publication(value: object) -> Optional[str]:
    if value is None:
        return None
    if type(value) is not str or not value or value != value.strip() or len(value) > 256:
        raise TavilyTransportError("MALFORMED_RESPONSE")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise TavilyTransportError("MALFORMED_RESPONSE")
    return value


def _strict_pairs(pairs: Sequence[Tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError("NONFINITE_JSON")


def _parse_json(body: bytes) -> Mapping[str, Any]:
    try:
        text = body.decode("utf-8")
        parsed = json.loads(
            text,
            object_pairs_hook=_strict_pairs,
            parse_constant=_reject_nonfinite,
        )
    except UnicodeDecodeError:
        raise _safe_error("MALFORMED_JSON") from None
    except ValueError as error:
        code = str(error)
        if code not in ("DUPLICATE_JSON_KEY", "NONFINITE_JSON"):
            code = "MALFORMED_JSON"
        raise _safe_error(code) from None
    if type(parsed) is not dict:
        raise _safe_error("TRANSPORT_ROOT_NOT_OBJECT")
    return parsed


def _check_keys(value: Mapping[str, Any], allowed: Tuple[str, ...], required: Tuple[str, ...]) -> None:
    if any(type(key) is not str for key in value):
        raise _safe_error("UNKNOWN_RESPONSE_FIELD")
    if set(value) - set(allowed):
        raise _safe_error("UNKNOWN_RESPONSE_FIELD")
    if any(key not in value for key in required):
        raise _safe_error("MALFORMED_RESPONSE")


def _response_id(root: Mapping[str, Any]) -> str:
    value = root.get("request_id")
    if type(value) is not str or not value or value != value.strip() or len(value) > 256:
        raise _safe_error("MALFORMED_RESPONSE")
    return value


def _reported_credits(root: Mapping[str, Any]) -> Optional[int]:
    usage = root.get("usage")
    if usage is None:
        return None
    if type(usage) is not dict:
        raise _safe_error("MALFORMED_RESPONSE")
    _check_keys(usage, ("credits",), ("credits",))
    credits = usage["credits"]
    if type(credits) is not int or credits < 0:
        raise _safe_error("MALFORMED_RESPONSE")
    return credits


def _validate_response_time(root: Mapping[str, Any]) -> None:
    if "response_time" not in root:
        return
    value = root["response_time"]
    if type(value) in (int, float) and not isinstance(value, bool):
        if math.isfinite(float(value)) and value >= 0:
            return
    if type(value) is str:
        try:
            parsed = float(value)
        except ValueError:
            parsed = -1.0
        if math.isfinite(parsed) and parsed >= 0:
            return
    raise _safe_error("MALFORMED_RESPONSE")


def _validate_optional_string(value: object, *, allow_none: bool = True) -> Optional[str]:
    if value is None and allow_none:
        return None
    if type(value) is not str or value != value.strip():
        raise _safe_error("MALFORMED_RESPONSE")
    return value


def _parse_native_score(value: object) -> Optional[float]:
    if value is None:
        return None
    if type(value) not in (int, float) or isinstance(value, bool):
        raise _safe_error("MALFORMED_RESPONSE")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise _safe_error("MALFORMED_RESPONSE")
    return numeric


def _read_bounded(response: Any, maximum: int) -> bytes:
    headers = getattr(response, "headers", None)
    content_length = headers.get("Content-Length") if headers is not None else None
    if content_length is not None:
        try:
            declared = int(content_length)
        except (TypeError, ValueError):
            raise _safe_error("INVALID_CONTENT_LENGTH") from None
        if declared < 0:
            raise _safe_error("INVALID_CONTENT_LENGTH")
        if declared > maximum:
            raise _safe_error("RESPONSE_TOO_LARGE")
    try:
        body = response.read(maximum + 1)
    except (socket.timeout, TimeoutError):
        raise _safe_error("TIMEOUT") from None
    except Exception:
        raise _safe_error("RESPONSE_READ_FAILED") from None
    if type(body) is not bytes:
        raise _safe_error("INVALID_RESPONSE_BODY")
    if len(body) > maximum:
        raise _safe_error("RESPONSE_TOO_LARGE")
    return body


def _response_status(response: Any) -> int:
    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        status = getcode() if callable(getcode) else 200
    if type(status) is not int:
        raise _safe_error("INVALID_RESPONSE_STATUS")
    return status


class TavilySourceClient:
    """One bounded, no-retry Tavily Basic Search/Extract client."""

    def __init__(
        self,
        config: TavilySourceConfig,
        *,
        repo_root: Optional[Union[str, os.PathLike[str]]] = None,
        transport: Optional[Callable[[Request, float], Any]] = None,
        credential_resolver: Optional[Callable[[TavilyCredentialRef], str]] = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if type(config) is not TavilySourceConfig:
            raise TypeError("config must have exact type TavilySourceConfig")
        try:
            root = Path.cwd() if repo_root is None else Path(repo_root)
            root = root.resolve(strict=True)
        except (OSError, RuntimeError, TypeError, ValueError):
            raise TavilyConfigurationError("INVALID_REPO_ROOT") from None
        if not root.is_dir():
            raise TavilyConfigurationError("INVALID_REPO_ROOT")
        if transport is not None and not callable(transport):
            raise TypeError("transport must be callable or None")
        if credential_resolver is not None and not callable(credential_resolver):
            raise TypeError("credential_resolver must be callable or None")
        if not callable(clock):
            raise TypeError("clock must be callable")
        if config.credential_ref.properties_path is not None:
            try:
                candidate = Path(config.credential_ref.properties_path).resolve()
                candidate.relative_to(root)
            except ValueError:
                pass
            except (OSError, RuntimeError):
                raise TavilyConfigurationError("INVALID_CREDENTIAL_REF") from None
            else:
                raise TavilyConfigurationError("CREDENTIAL_PATH_INSIDE_REPOSITORY")
        self.config = config
        self.repo_root = root
        self._transport = transport or _default_transport
        self._credential_resolver = credential_resolver
        self._clock = clock
        self._remaining_requests = config.request_budget
        self._remaining_credits = config.credit_budget
        self._bytes_used = 0
        self._started_at: Optional[float] = None
        self._budget_lock = threading.Lock()

    @property
    def remaining_request_budget(self) -> int:
        with self._budget_lock:
            return self._remaining_requests

    @property
    def remaining_credit_budget(self) -> int:
        with self._budget_lock:
            return self._remaining_credits

    @property
    def bytes_used(self) -> int:
        with self._budget_lock:
            return self._bytes_used

    def _reserve(self, request_bytes: int, credits: int) -> float:
        now = float(self._clock())
        with self._budget_lock:
            if self._remaining_requests < 1:
                raise _safe_error("REQUEST_BUDGET_EXHAUSTED")
            if self._remaining_credits < credits:
                raise _safe_error("CREDIT_BUDGET_EXHAUSTED")
            if self.config.byte_budget is not None:
                if self._bytes_used + request_bytes > self.config.byte_budget:
                    raise _safe_error("BYTE_BUDGET_EXHAUSTED")
            if self._started_at is None:
                self._started_at = now
            elif self.config.time_budget_seconds is not None:
                if now - self._started_at >= self.config.time_budget_seconds:
                    raise _safe_error("TIME_BUDGET_EXHAUSTED")
            self._remaining_requests -= 1
            self._remaining_credits -= credits
            self._bytes_used += request_bytes
            if self.config.time_budget_seconds is None:
                return self.config.timeout_seconds
            remaining = self.config.time_budget_seconds - (now - self._started_at)
            if remaining <= 0:
                raise _safe_error("TIME_BUDGET_EXHAUSTED")
            return min(self.config.timeout_seconds, remaining)

    def _resolve_key(self) -> str:
        try:
            if self._credential_resolver is None:
                return self.config.credential_ref.resolve(repo_root=self.repo_root)
            return _validate_api_key(self._credential_resolver(self.config.credential_ref))
        except TavilyCredentialError:
            raise
        except Exception:
            raise TavilyCredentialError("CREDENTIAL_UNAVAILABLE") from None

    def _call(
        self,
        operation: str,
        endpoint: str,
        payload: Mapping[str, Any],
        credits: int,
    ) -> Tuple[Mapping[str, Any], int, int, float]:
        try:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError):
            raise _safe_error("REQUEST_SERIALIZATION_FAILED") from None
        if len(body) > self.config.max_request_bytes:
            raise _safe_error("REQUEST_TOO_LARGE")
        timeout = self._reserve(len(body), credits)
        api_key = self._resolve_key()
        request = Request(
            endpoint,
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
                "Content-Length": str(len(body)),
                "Content-Type": "application/json",
                "User-Agent": "ConvexityHunter/0.1",
            },
            method="POST",
        )
        response = None
        started = float(self._clock())
        try:
            try:
                response = self._transport(request, timeout)
            except HTTPError as error:
                status = error.code if type(error.code) is int else None
                if status is not None and 300 <= status < 400:
                    raise _safe_error("REDIRECT_REJECTED", status=status) from None
                raise _safe_error("HTTP_ERROR", status=status) from None
            except (socket.timeout, TimeoutError):
                raise _safe_error("TIMEOUT") from None
            except URLError:
                raise _safe_error("NETWORK_ERROR") from None
            except TavilyTransportError:
                raise
            except Exception:
                raise _safe_error("TRANSPORT_FAILED") from None

            geturl = getattr(response, "geturl", None)
            final_url = geturl() if callable(geturl) else None
            if final_url is not None and final_url != endpoint:
                raise _safe_error("REDIRECT_REJECTED")
            status = _response_status(response)
            if 300 <= status < 400:
                raise _safe_error("REDIRECT_REJECTED", status=status)
            if status < 200 or status >= 300:
                raise _safe_error("HTTP_ERROR", status=status)
            maximum = self.config.max_response_bytes
            if self.config.byte_budget is not None:
                with self._budget_lock:
                    remaining_bytes = self.config.byte_budget - self._bytes_used
                if remaining_bytes <= 0:
                    raise _safe_error("BYTE_BUDGET_EXHAUSTED")
                maximum = min(maximum, remaining_bytes)
            body_received = _read_bounded(response, maximum)
            with self._budget_lock:
                self._bytes_used += len(body_received)
            elapsed = max(0.0, float(self._clock()) - started)
            if (
                self.config.time_budget_seconds is not None
                and self._started_at is not None
                and float(self._clock()) - self._started_at > self.config.time_budget_seconds
            ):
                raise _safe_error("TIME_BUDGET_EXCEEDED")
            return _parse_json(body_received), len(body), len(body_received), elapsed
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass

    def search(self, query: str, *, max_results: Optional[int] = None) -> TavilySearchResult:
        """Run one Basic Search.  An empty result is valid source evidence state."""

        if type(query) is not str or not query or query != query.strip():
            raise TavilyConfigurationError("INVALID_QUERY")
        count = self.config.max_search_results if max_results is None else max_results
        if type(count) is not int or not 1 <= count <= self.config.max_search_results:
            raise TavilyConfigurationError("INVALID_MAX_RESULTS")
        payload = {
            "query": query,
            "search_depth": "basic",
            "max_results": count,
            "topic": "general",
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "include_image_descriptions": False,
            "include_favicon": False,
            "include_published_date": True,
            "auto_parameters": False,
            "include_usage": True,
        }
        root, request_bytes, response_bytes, elapsed = self._call(
            "search", _SEARCH_ENDPOINT, payload, 1
        )
        _check_keys(
            root,
            (
                "query",
                "answer",
                "images",
                "follow_up_questions",
                "results",
                "response_time",
                "auto_parameters",
                "usage",
                "request_id",
            ),
            ("results", "request_id"),
        )
        if root.get("follow_up_questions") is not None:
            raise _safe_error("MALFORMED_RESPONSE")
        _validate_response_time(root)
        request_id = _response_id(root)
        reported_credits = _reported_credits(root)
        provider_query = root.get("query")
        if provider_query is not None and type(provider_query) is not str:
            raise _safe_error("MALFORMED_RESPONSE")
        results = root["results"]
        if type(results) is not list or len(results) > count:
            raise _safe_error("MALFORMED_RESPONSE")
        sources = []
        for item in results:
            if type(item) is not dict:
                raise _safe_error("MALFORMED_RESPONSE")
            _check_keys(
                item,
                (
                    "title",
                    "url",
                    "content",
                    "score",
                    "raw_content",
                    "published_date",
                    "favicon",
                    "images",
                    "id",
                ),
                ("title", "url", "content"),
            )
            title = item["title"]
            snippet = item["content"]
            if type(title) is not str or not title or type(snippet) is not str:
                raise _safe_error("MALFORMED_RESPONSE")
            url = _validate_public_url(item["url"])
            publication_date = _validate_publication(item.get("published_date"))
            provider_id = _validate_provider_id(item.get("id"))
            native_score = _parse_native_score(item.get("score"))
            sources.append(
                TavilySourceReference(
                    source_id=provider_id or _url_source_id(url),
                    url=url,
                    title=title,
                    snippet=snippet,
                    publication_date=publication_date,
                    provider_result_id=provider_id,
                    native_score=native_score,
                )
            )
        source_tuple = tuple(sources)
        coverage = TavilyCoverage(
            requested_count=len(source_tuple),
            returned_count=len(source_tuple),
            failed_count=0,
            source_ids=tuple(source.source_id for source in source_tuple),
            failed_source_ids=(),
            status="EMPTY" if not source_tuple else "COMPLETE",
        )
        receipt = TavilyReceipt(
            operation="search",
            endpoint=_SEARCH_ENDPOINT,
            request_id=request_id,
            reserved_requests=1,
            reserved_credits=1,
            reported_credits=reported_credits,
            request_bytes=request_bytes,
            response_bytes=response_bytes,
            elapsed_seconds=elapsed,
            source_ids=coverage.source_ids,
            returned_count=len(source_tuple),
            failed_count=0,
        )
        return TavilySearchResult(query=query, sources=source_tuple, receipt=receipt, coverage=coverage)

    def extract(
        self,
        urls: Sequence[str],
        *,
        query: Optional[str] = None,
        source_refs: Optional[Sequence[TavilySourceReference]] = None,
    ) -> TavilyExtractResult:
        """Run one Basic Extract without fetching source URLs locally."""

        if type(urls) is str:
            raise TavilyConfigurationError("INVALID_URLS")
        try:
            requested_urls = tuple(urls)
        except TypeError:
            raise TavilyConfigurationError("INVALID_URLS") from None
        if not 1 <= len(requested_urls) <= self.config.max_extract_urls:
            raise TavilyConfigurationError("INVALID_URL_COUNT")
        try:
            validated_urls = tuple(_validate_public_url(url) for url in requested_urls)
        except TavilyTransportError:
            raise TavilyConfigurationError("UNSAFE_SOURCE_URL") from None
        if len(set(validated_urls)) != len(validated_urls):
            raise TavilyConfigurationError("DUPLICATE_URL")
        if query is not None and (type(query) is not str or not query or query != query.strip()):
            raise TavilyConfigurationError("INVALID_QUERY")
        refs_by_url = {}
        if source_refs is not None:
            for source in source_refs:
                if type(source) is not TavilySourceReference:
                    raise TavilyConfigurationError("INVALID_SOURCE_REF")
                if source.url in refs_by_url:
                    raise TavilyConfigurationError("DUPLICATE_SOURCE_REF")
                refs_by_url[source.url] = source
            if set(refs_by_url) != set(validated_urls):
                raise TavilyConfigurationError("SOURCE_REF_URL_MISMATCH")
        payload = {
            "urls": list(validated_urls),
            "extract_depth": "basic",
            "format": "markdown",
            "include_images": False,
            "include_favicon": False,
            "include_usage": True,
        }
        if query is not None:
            payload["query"] = query
        credits = (len(validated_urls) + 4) // 5
        root, request_bytes, response_bytes, elapsed = self._call(
            "extract", _EXTRACT_ENDPOINT, payload, credits
        )
        _check_keys(
            root,
            ("results", "failed_results", "response_time", "usage", "request_id"),
            ("results", "failed_results", "request_id"),
        )
        _validate_response_time(root)
        request_id = _response_id(root)
        reported_credits = _reported_credits(root)
        results = root["results"]
        failed_results = root["failed_results"]
        if type(results) is not list or type(failed_results) is not list:
            raise _safe_error("MALFORMED_RESPONSE")
        successes = {}
        failures = {}
        for item in results:
            if type(item) is not dict:
                raise _safe_error("MALFORMED_RESPONSE")
            _check_keys(
                item,
                ("url", "raw_content", "images", "favicon", "title"),
                ("url", "raw_content"),
            )
            url = _validate_public_url(item["url"])
            if url not in validated_urls or url in successes or url in failures:
                raise _safe_error("MALFORMED_RESPONSE")
            if type(item["raw_content"]) is not str:
                raise _safe_error("MALFORMED_RESPONSE")
            if "title" in item and type(item["title"]) is not str:
                raise _safe_error("MALFORMED_RESPONSE")
            successes[url] = item["raw_content"]
        for item in failed_results:
            if type(item) is not dict:
                raise _safe_error("MALFORMED_RESPONSE")
            _check_keys(item, ("url", "error"), ("url",))
            url = _validate_public_url(item["url"])
            if url not in validated_urls or url in successes or url in failures:
                raise _safe_error("MALFORMED_RESPONSE")
            if "error" in item and item["error"] is not None and type(item["error"]) is not str:
                raise _safe_error("MALFORMED_RESPONSE")
            failures[url] = "PROVIDER_REPORTED_FAILURE"
        if set(successes) | set(failures) != set(validated_urls):
            raise _safe_error("MALFORMED_RESPONSE")
        bodies = []
        failed = []
        for url in validated_urls:
            reference = refs_by_url.get(url)
            source_id = reference.source_id if reference is not None else _url_source_id(url)
            if url in successes:
                bodies.append(
                    TavilySourceBody(
                        source_id=source_id,
                        url=url,
                        body=successes[url],
                        publication_date=reference.publication_date if reference else None,
                        provider_result_id=reference.provider_result_id if reference else None,
                    )
                )
            else:
                failed.append(
                    TavilyFailedExtract(
                        source_id=source_id,
                        url=url,
                        reason_code=failures[url],
                    )
                )
        body_tuple = tuple(bodies)
        failed_tuple = tuple(failed)
        source_ids = tuple(
            (refs_by_url[url].source_id if url in refs_by_url else _url_source_id(url))
            for url in validated_urls
        )
        failed_ids = tuple(item.source_id for item in failed_tuple)
        status = "COMPLETE" if not failed_tuple else ("EMPTY" if not body_tuple else "PARTIAL")
        coverage = TavilyCoverage(
            requested_count=len(validated_urls),
            returned_count=len(body_tuple),
            failed_count=len(failed_tuple),
            source_ids=source_ids,
            failed_source_ids=failed_ids,
            status=status,
        )
        receipt = TavilyReceipt(
            operation="extract",
            endpoint=_EXTRACT_ENDPOINT,
            request_id=request_id,
            reserved_requests=1,
            reserved_credits=credits,
            reported_credits=reported_credits,
            request_bytes=request_bytes,
            response_bytes=response_bytes,
            elapsed_seconds=elapsed,
            source_ids=source_ids,
            returned_count=len(body_tuple),
            failed_count=len(failed_tuple),
        )
        return TavilyExtractResult(
            urls=validated_urls,
            bodies=body_tuple,
            failed_extracts=failed_tuple,
            receipt=receipt,
            coverage=coverage,
            query=query,
        )
