"""Bounded stdlib chat-completions transport for the M1a Host boundary.

This module owns configuration, explicit credential resolution, and transport
envelope validation only.  The assistant content is returned as opaque text;
semantic JSON validation is deliberately an injected later boundary.
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
import re
import socket
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence, Tuple, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


__all__ = (
    "ChatCompletionsClient",
    "ModelCredential",
    "ModelCredentialError",
    "ModelConfigurationError",
    "ModelRuntimeConfig",
    "ModelTransportError",
    "ModelTransportReceipt",
)


_ROLE_VALUES = ("discovery", "semantic")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DEEPSEEK_BLOCK_HEADER = re.compile(
    r"^deepseek[ \t]*:?[ \t]*\{$",
    re.IGNORECASE | re.ASCII,
)
_LOOPBACK_NAMES = frozenset(("localhost", "localhost.localdomain"))


class ModelConfigurationError(ValueError):
    """A rejected, non-secret runtime configuration."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"ModelConfigurationError(code={self.code!r})"


class ModelCredentialError(ValueError):
    """A rejected or unavailable explicit credential source."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"ModelCredentialError(code={self.code!r})"


class ModelTransportError(RuntimeError):
    """A sanitized typed transport or transport-envelope failure."""

    def __init__(self, code: str, *, status: Optional[int] = None) -> None:
        self.code = code
        self.status = status
        message = code if status is None else f"{code} status={status}"
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"ModelTransportError(code={self.code!r}, status={self.status!r})"
        )


def _require_text(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ModelConfigurationError(f"INVALID_{name.upper()}")
    return value


def _require_positive_int(name: str, value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ModelConfigurationError(f"INVALID_{name.upper()}")
    return value


def _is_loopback_host(hostname: str) -> bool:
    normalized = hostname.lower().rstrip(".")
    if normalized in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _validate_base_endpoint(endpoint: str) -> None:
    if any(character in endpoint for character in ("\x00", "\r", "\n")):
        raise ModelConfigurationError("INVALID_BASE_ENDPOINT")
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        raise ModelConfigurationError("INVALID_BASE_ENDPOINT") from None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ModelConfigurationError("INVALID_BASE_ENDPOINT")
    if parsed.username is not None or parsed.password is not None:
        raise ModelConfigurationError("ENDPOINT_USERINFO_FORBIDDEN")
    if parsed.query or parsed.fragment or port is not None and port <= 0:
        raise ModelConfigurationError("ENDPOINT_QUERY_OR_FRAGMENT_FORBIDDEN")
    if parsed.hostname is None:
        raise ModelConfigurationError("INVALID_BASE_ENDPOINT")
    if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
        raise ModelConfigurationError("NON_LOOPBACK_HTTP_FORBIDDEN")


@dataclass(frozen=True)
class ModelRuntimeConfig:
    """Explicit, bounded runtime configuration for one model role."""

    provider: str
    model: str
    base_endpoint: str
    role: str
    capabilities: Tuple[str, ...]
    timeout_seconds: float
    request_budget: int
    max_tokens: int
    max_input_bytes: int
    max_output_bytes: int
    remote_enabled: bool
    fee_authorized: bool
    json_mode: bool
    thinking_enabled: bool

    def __post_init__(self) -> None:
        _require_text("provider", self.provider)
        _require_text("model", self.model)
        _require_text("base_endpoint", self.base_endpoint)
        _require_text("role", self.role)
        if self.role not in _ROLE_VALUES:
            raise ModelConfigurationError("INVALID_ROLE")
        if type(self.capabilities) is not tuple or any(
            type(capability) is not str
            or not capability
            or capability.strip() != capability
            for capability in self.capabilities
        ):
            raise ModelConfigurationError("INVALID_CAPABILITIES")
        if len(set(self.capabilities)) != len(self.capabilities):
            raise ModelConfigurationError("DUPLICATE_CAPABILITY")
        if (
            type(self.timeout_seconds) not in (int, float)
            or isinstance(self.timeout_seconds, bool)
            or not math.isfinite(float(self.timeout_seconds))
            or self.timeout_seconds <= 0
        ):
            raise ModelConfigurationError("INVALID_TIMEOUT_SECONDS")
        _require_positive_int("request_budget", self.request_budget)
        _require_positive_int("max_tokens", self.max_tokens)
        _require_positive_int("max_input_bytes", self.max_input_bytes)
        _require_positive_int("max_output_bytes", self.max_output_bytes)
        if type(self.remote_enabled) is not bool:
            raise ModelConfigurationError("INVALID_REMOTE_ENABLED")
        if type(self.fee_authorized) is not bool:
            raise ModelConfigurationError("INVALID_FEE_AUTHORIZED")
        if type(self.json_mode) is not bool:
            raise ModelConfigurationError("INVALID_JSON_MODE")
        if type(self.thinking_enabled) is not bool:
            raise ModelConfigurationError("INVALID_THINKING_ENABLED")
        if self.json_mode and "json_mode" not in self.capabilities:
            raise ModelConfigurationError("JSON_MODE_NOT_DECLARED")
        if self.thinking_enabled and "thinking" not in self.capabilities:
            raise ModelConfigurationError("THINKING_NOT_DECLARED")

        _validate_base_endpoint(self.base_endpoint)
        hostname = urlsplit(self.base_endpoint).hostname
        assert hostname is not None
        if not _is_loopback_host(hostname):
            if not self.remote_enabled:
                raise ModelConfigurationError("REMOTE_NOT_ENABLED")
            if not self.fee_authorized:
                raise ModelConfigurationError("REMOTE_FEE_NOT_AUTHORIZED")


@dataclass(frozen=True, repr=False)
class ModelCredential:
    """One explicit external credential source; no discovery is performed."""

    properties_path: Optional[Union[str, os.PathLike[str]]] = None
    env_name: Optional[str] = None

    def __post_init__(self) -> None:
        has_path = self.properties_path is not None
        has_env = self.env_name is not None
        if has_path == has_env:
            raise ModelCredentialError("EXACTLY_ONE_CREDENTIAL_SOURCE_REQUIRED")
        if has_env:
            if type(self.env_name) is not str or not _ENV_NAME.fullmatch(self.env_name):
                raise ModelCredentialError("INVALID_ENVIRONMENT_NAME")
        else:
            try:
                path = Path(self.properties_path)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                raise ModelCredentialError("INVALID_PROPERTIES_PATH") from None
            if not path.is_absolute():
                raise ModelCredentialError("PROPERTIES_PATH_MUST_BE_ABSOLUTE")
            object.__setattr__(self, "properties_path", path)

    def __repr__(self) -> str:
        source = "environment" if self.env_name is not None else "properties_file"
        return f"ModelCredential(source={source!r})"

    def resolve(self, *, repo_root: Union[str, os.PathLike[str]]) -> str:
        """Resolve only this explicit source, returning the key in memory."""

        if self.env_name is not None:
            value = os.environ.get(self.env_name)
            if value is None:
                raise ModelCredentialError("CREDENTIAL_UNAVAILABLE")
            return _validate_api_key(value)

        try:
            root = Path(repo_root).resolve(strict=True)
            candidate = Path(self.properties_path).resolve(strict=True)  # type: ignore[arg-type]
        except (OSError, RuntimeError, TypeError, ValueError):
            raise ModelCredentialError("CREDENTIAL_UNAVAILABLE") from None
        if not root.is_dir() or not candidate.is_file():
            raise ModelCredentialError("CREDENTIAL_UNAVAILABLE")
        try:
            candidate.relative_to(root)
        except ValueError:
            pass
        else:
            raise ModelCredentialError("CREDENTIAL_PATH_INSIDE_REPOSITORY")

        try:
            text = candidate.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise ModelCredentialError("CREDENTIAL_UNAVAILABLE") from None
        api_key: Optional[str] = None
        in_deepseek_block = False
        saw_deepseek_block = False
        block_has_api_key = False
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if in_deepseek_block:
                if line == "}":
                    if not block_has_api_key:
                        raise ModelCredentialError("INVALID_PROPERTIES_FILE")
                    in_deepseek_block = False
                    continue
                if "{" in line or "}" in line:
                    raise ModelCredentialError("INVALID_PROPERTIES_FILE")
                key, separator, value = line.partition("=")
                if separator != "=" or key.strip() != "api_key":
                    raise ModelCredentialError("INVALID_PROPERTIES_FILE")
                if api_key is not None:
                    raise ModelCredentialError("DUPLICATE_API_KEY")
                api_key = value.strip()
                block_has_api_key = True
                continue

            if _DEEPSEEK_BLOCK_HEADER.fullmatch(line):
                if saw_deepseek_block:
                    raise ModelCredentialError("INVALID_PROPERTIES_FILE")
                saw_deepseek_block = True
                in_deepseek_block = True
                block_has_api_key = False
                continue
            if line == "}" or "{" in line or "}" in line:
                raise ModelCredentialError("INVALID_PROPERTIES_FILE")

            key, separator, value = line.partition("=")
            if separator != "=" or key.strip() != "api_key":
                raise ModelCredentialError("INVALID_PROPERTIES_FILE")
            if api_key is not None:
                raise ModelCredentialError("DUPLICATE_API_KEY")
            api_key = value.strip()
        if in_deepseek_block:
            raise ModelCredentialError("INVALID_PROPERTIES_FILE")
        if api_key is None:
            raise ModelCredentialError("CREDENTIAL_UNAVAILABLE")
        return _validate_api_key(api_key)


def _validate_api_key(value: object) -> str:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ModelCredentialError("INVALID_API_KEY")
    return value


@dataclass(frozen=True, repr=False)
class ModelTransportReceipt:
    """Typed result; ``content`` remains opaque to this transport layer."""

    provider: str
    requested_model: str
    returned_model: Optional[str]
    request_id: Optional[str]
    content: str
    reasoning_content: Optional[str]
    finish_reason: str
    bytes_sent: int
    bytes_received: int
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    cached_tokens: Optional[int]
    prompt_cache_hit_tokens: Optional[int]
    prompt_cache_miss_tokens: Optional[int]

    def __repr__(self) -> str:
        return (
            "ModelTransportReceipt("
            f"provider={self.provider!r}, requested_model={self.requested_model!r}, "
            f"returned_model={self.returned_model!r}, "
            f"request_id={self.request_id!r}, finish_reason={self.finish_reason!r}, "
            f"bytes_sent={self.bytes_sent}, bytes_received={self.bytes_received}, "
            f"prompt_tokens={self.prompt_tokens!r}, "
            f"completion_tokens={self.completion_tokens!r}, "
            f"total_tokens={self.total_tokens!r})"
        )


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _default_transport(request: Request, timeout_seconds: float) -> Any:
    opener = build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout_seconds)


def _response_status(response: Any) -> int:
    status = getattr(response, "status", None)
    if status is None:
        getcode = getattr(response, "getcode", None)
        status = getcode() if callable(getcode) else 200
    if type(status) is not int:
        raise ModelTransportError("INVALID_RESPONSE_STATUS")
    return status


def _response_header(response: Any, name: str) -> Optional[str]:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    getter = getattr(headers, "get", None)
    value = getter(name) if callable(getter) else None
    if value is None:
        return None
    if type(value) is not str:
        raise ModelTransportError("INVALID_RESPONSE_HEADER")
    return value


def _read_bounded(response: Any, maximum: int) -> bytes:
    content_length = _response_header(response, "Content-Length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            raise ModelTransportError("INVALID_CONTENT_LENGTH") from None
        if declared < 0:
            raise ModelTransportError("INVALID_CONTENT_LENGTH")
        if declared > maximum:
            raise ModelTransportError("RESPONSE_TOO_LARGE")
    try:
        body = response.read(maximum + 1)
    except (socket.timeout, TimeoutError):
        raise ModelTransportError("TIMEOUT") from None
    except Exception:
        raise ModelTransportError("RESPONSE_READ_FAILED") from None
    if type(body) is not bytes:
        raise ModelTransportError("INVALID_RESPONSE_BODY")
    if len(body) > maximum:
        raise ModelTransportError("RESPONSE_TOO_LARGE")
    return body


def _expect_object(value: object, code: str = "MALFORMED_RESPONSE") -> Mapping[str, Any]:
    if type(value) is not dict:
        raise ModelTransportError(code)
    return value


def _check_keys(
    value: Mapping[str, Any],
    allowed: Tuple[str, ...],
    required: Tuple[str, ...] = (),
) -> None:
    if any(type(key) is not str for key in value):
        raise ModelTransportError("UNKNOWN_TRANSPORT_FIELD")
    unknown = set(value) - set(allowed)
    if unknown:
        raise ModelTransportError("UNKNOWN_TRANSPORT_FIELD")
    if any(key not in value for key in required):
        raise ModelTransportError("MALFORMED_RESPONSE")


def _strict_object_pairs(pairs: Sequence[Tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError("NONFINITE_JSON")


def _parse_transport_json(body: bytes) -> Mapping[str, Any]:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise ModelTransportError("MALFORMED_JSON") from None
    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_strict_object_pairs,
            parse_constant=_reject_nonfinite,
        )
    except ValueError as error:
        code = str(error)
        if code not in ("DUPLICATE_JSON_KEY", "NONFINITE_JSON"):
            code = "MALFORMED_JSON"
        raise ModelTransportError(code) from None
    return _expect_object(parsed, "TRANSPORT_ROOT_NOT_OBJECT")


def _parse_usage(
    usage: object, max_tokens: int
) -> Tuple[
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
]:
    if usage is None:
        return None, None, None, None, None, None
    usage_object = _expect_object(usage)
    _check_keys(
        usage_object,
        (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_tokens_details",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        ),
    )
    values = []
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage_object.get(name)
        if value is not None and (type(value) is not int or value < 0):
            raise ModelTransportError("INVALID_USAGE")
        values.append(value)
    prompt_tokens, completion_tokens, total_tokens = values
    if completion_tokens is not None and completion_tokens > max_tokens:
        raise ModelTransportError("TOKEN_BUDGET_EXCEEDED")
    details = usage_object.get("prompt_tokens_details")
    cached_tokens = None
    if details is not None:
        details_object = _expect_object(details)
        _check_keys(details_object, ("cached_tokens",))
        cached_tokens = details_object.get("cached_tokens")
        if cached_tokens is not None and (
            type(cached_tokens) is not int or cached_tokens < 0
        ):
            raise ModelTransportError("INVALID_USAGE")
    prompt_cache_hit_tokens = usage_object.get("prompt_cache_hit_tokens")
    prompt_cache_miss_tokens = usage_object.get("prompt_cache_miss_tokens")
    for value in (prompt_cache_hit_tokens, prompt_cache_miss_tokens):
        if value is not None and (type(value) is not int or value < 0):
            raise ModelTransportError("INVALID_USAGE")
    return (
        prompt_tokens,
        completion_tokens,
        total_tokens,
        cached_tokens,
        prompt_cache_hit_tokens,
        prompt_cache_miss_tokens,
    )


def _parse_completion_response(
    body: bytes, max_tokens: int
) -> Tuple[
    Optional[str],
    Optional[str],
    str,
    Optional[str],
    str,
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
]:
    root = _parse_transport_json(body)
    _check_keys(
        root,
        (
            "id",
            "object",
            "created",
            "model",
            "choices",
            "usage",
            "system_fingerprint",
            "service_tier",
        ),
        ("choices",),
    )
    request_id = root.get("id")
    if request_id is not None and (type(request_id) is not str or not request_id):
        raise ModelTransportError("MALFORMED_RESPONSE")
    returned_model = root.get("model")
    if returned_model is not None and (
        type(returned_model) is not str or not returned_model
    ):
        raise ModelTransportError("MALFORMED_RESPONSE")
    choices = root["choices"]
    if type(choices) is not list or len(choices) != 1:
        raise ModelTransportError("MALFORMED_RESPONSE")
    choice = _expect_object(choices[0])
    _check_keys(choice, ("index", "message", "finish_reason", "logprobs"), ("message", "finish_reason"))
    finish_reason = choice["finish_reason"]
    if finish_reason == "length":
        raise ModelTransportError("TRUNCATED_RESPONSE")
    if finish_reason != "stop":
        raise ModelTransportError("UNSUPPORTED_FINISH_REASON")
    message = _expect_object(choice["message"])
    _check_keys(
        message,
        (
            "role",
            "content",
            "refusal",
            "tool_calls",
            "function_call",
            "reasoning_content",
        ),
        ("role", "content"),
    )
    if "tool_calls" in message or "function_call" in message:
        raise ModelTransportError("TOOL_CALLS_REJECTED")
    refusal = message.get("refusal")
    if refusal is not None:
        if type(refusal) is not str:
            raise ModelTransportError("MALFORMED_RESPONSE")
        raise ModelTransportError("REFUSAL_REJECTED")
    if message["role"] != "assistant" or type(message["content"]) is not str:
        raise ModelTransportError("MALFORMED_RESPONSE")
    if not message["content"]:
        raise ModelTransportError("EMPTY_RESPONSE")
    reasoning_content = message.get("reasoning_content")
    if reasoning_content is not None and type(reasoning_content) is not str:
        raise ModelTransportError("MALFORMED_RESPONSE")
    (
        prompt_tokens,
        completion_tokens,
        total_tokens,
        cached_tokens,
        prompt_cache_hit_tokens,
        prompt_cache_miss_tokens,
    ) = _parse_usage(root.get("usage"), max_tokens)
    return (
        request_id,
        returned_model,
        message["content"],
        reasoning_content,
        finish_reason,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        cached_tokens,
        prompt_cache_hit_tokens,
        prompt_cache_miss_tokens,
    )


class ChatCompletionsClient:
    """One bounded, no-retry chat-completions client."""

    def __init__(
        self,
        config: ModelRuntimeConfig,
        credential: ModelCredential,
        *,
        repo_root: Union[str, os.PathLike[str]],
        transport: Optional[Callable[[Request, float], Any]] = None,
    ) -> None:
        if type(config) is not ModelRuntimeConfig:
            raise TypeError("config must have exact type ModelRuntimeConfig")
        if type(credential) is not ModelCredential:
            raise TypeError("credential must have exact type ModelCredential")
        try:
            root = Path(repo_root).resolve(strict=True)
        except (OSError, RuntimeError, TypeError, ValueError):
            raise ModelConfigurationError("INVALID_REPO_ROOT") from None
        if not root.is_dir():
            raise ModelConfigurationError("INVALID_REPO_ROOT")
        if transport is not None and not callable(transport):
            raise TypeError("transport must be callable or None")
        self.config = config
        self.credential = credential
        self.repo_root = root
        self._transport = transport or _default_transport
        self._remaining_request_budget = config.request_budget
        self._budget_lock = threading.Lock()

    @property
    def remaining_request_budget(self) -> int:
        with self._budget_lock:
            return self._remaining_request_budget

    def _reserve_request(self) -> None:
        with self._budget_lock:
            if self._remaining_request_budget <= 0:
                raise ModelTransportError("REQUEST_BUDGET_EXHAUSTED")
            self._remaining_request_budget -= 1

    def complete(
        self, system_prompt: str, source_prompt: str
    ) -> ModelTransportReceipt:
        """Send explicit system/source messages and return opaque content.

        The transport envelope is validated here.  ``content`` is not parsed
        as semantic JSON and is intentionally left for a later validator.
        """

        if type(system_prompt) is not str or not system_prompt:
            raise ModelTransportError("INVALID_SYSTEM_PROMPT")
        if type(source_prompt) is not str or not source_prompt:
            raise ModelTransportError("INVALID_SOURCE_PROMPT")
        messages = (
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": source_prompt},
        )
        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
        }
        if self.config.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if "thinking" in self.config.capabilities:
            payload["thinking"] = {
                "type": "enabled" if self.config.thinking_enabled else "disabled"
            }
        try:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError):
            raise ModelTransportError("REQUEST_SERIALIZATION_FAILED") from None
        if len(body) > self.config.max_input_bytes:
            raise ModelTransportError("REQUEST_TOO_LARGE")

        self._reserve_request()
        api_key = self.credential.resolve(repo_root=self.repo_root)
        endpoint = self.config.base_endpoint.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint += "/chat/completions"
        request = Request(
            endpoint,
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
                "Content-Length": str(len(body)),
                "Content-Type": "application/json",
            },
            method="POST",
        )

        response = None
        try:
            try:
                response = self._transport(request, self.config.timeout_seconds)
            except HTTPError as error:
                status = error.code if type(error.code) is int else None
                if status == 401:
                    raise ModelTransportError("AUTHENTICATION_FAILED", status=status) from None
                if status is not None and 300 <= status < 400:
                    raise ModelTransportError("REDIRECT_REJECTED", status=status) from None
                raise ModelTransportError("HTTP_ERROR", status=status) from None
            except (socket.timeout, TimeoutError):
                raise ModelTransportError("TIMEOUT") from None
            except URLError:
                raise ModelTransportError("NETWORK_ERROR") from None
            except ModelTransportError:
                raise
            except Exception:
                raise ModelTransportError("TRANSPORT_FAILED") from None

            status = _response_status(response)
            if 300 <= status < 400:
                raise ModelTransportError("REDIRECT_REJECTED", status=status)
            if status == 401:
                raise ModelTransportError("AUTHENTICATION_FAILED", status=status)
            if status < 200 or status >= 300:
                raise ModelTransportError("HTTP_ERROR", status=status)
            body_received = _read_bounded(response, self.config.max_output_bytes)
            (
                request_id,
                returned_model,
                content,
                reasoning_content,
                finish_reason,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                cached_tokens,
                prompt_cache_hit_tokens,
                prompt_cache_miss_tokens,
            ) = _parse_completion_response(body_received, self.config.max_tokens)
            return ModelTransportReceipt(
                provider=self.config.provider,
                requested_model=self.config.model,
                returned_model=returned_model,
                request_id=request_id,
                content=content,
                reasoning_content=reasoning_content,
                finish_reason=finish_reason,
                bytes_sent=len(body),
                bytes_received=len(body_received),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cached_tokens=cached_tokens,
                prompt_cache_hit_tokens=prompt_cache_hit_tokens,
                prompt_cache_miss_tokens=prompt_cache_miss_tokens,
            )
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
