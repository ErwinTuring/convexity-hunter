"""Strict loader for an external, non-secret Event Grounder configuration."""

from __future__ import annotations

import json
import math
import os
import unicodedata
from pathlib import Path
from typing import Any, NoReturn, Union

from .host_event import HostEventGrounderConfig
from .host_grounder_run_input import HostGrounderRunInputBounds
from .host_model import ModelCredential, ModelRuntimeConfig
from .host_sources import TavilyCredentialRef, TavilySourceConfig


HOST_EVENT_CONFIG_SCHEMA_VERSION = "host-event-config-v0.1"
__all__ = (
    "HOST_EVENT_CONFIG_SCHEMA_VERSION",
    "HostEventConfigurationError",
    "load_event_grounder_config",
)

_MAX_CONFIG_BYTES = 64 * 1024
_ERROR_CODES = frozenset(
    (
        "CONFIG_PATH_INVALID",
        "CONFIG_NOT_EXTERNAL",
        "CONFIG_TOO_LARGE",
        "CONFIG_READ_FAILED",
        "INVALID_UTF8",
        "INVALID_JSON",
        "INVALID_UNICODE",
        "DUPLICATE_KEY",
        "NONFINITE_NUMBER",
        "FORBIDDEN_CREDENTIAL_FIELD",
        "UNKNOWN_FIELD",
        "MISSING_FIELD",
        "UNSUPPORTED_SCHEMA_VERSION",
        "INVALID_CREDENTIAL_REFERENCE",
        "INVALID_CONFIGURATION",
    )
)

_ROOT_FIELDS = frozenset(
    (
        "schema_version",
        "source",
        "discovery_model",
        "discovery_credential",
        "semantic_model",
        "semantic_credential",
        "run_input_bounds",
        "max_json_bytes",
        "max_source_body_bytes",
        "max_catalog_entries",
        "max_catalog_bytes",
        "max_catalog_paragraphs",
    )
)
_SOURCE_FIELDS = frozenset(
    (
        "credential_ref",
        "paygo_off_confirmed",
        "request_budget",
        "credit_budget",
        "max_request_bytes",
        "max_response_bytes",
        "timeout_seconds",
        "time_budget_seconds",
        "byte_budget",
        "max_search_results",
        "max_extract_urls",
    )
)
_MODEL_FIELDS = frozenset(
    (
        "provider",
        "model",
        "base_endpoint",
        "role",
        "capabilities",
        "timeout_seconds",
        "request_budget",
        "max_tokens",
        "max_input_bytes",
        "max_output_bytes",
        "remote_enabled",
        "fee_authorized",
        "json_mode",
        "thinking_enabled",
    )
)
_INPUT_BOUNDS_FIELDS = frozenset(
    ("max_run_input_bytes", "max_string_bytes", "max_array_items")
)
_CREDENTIAL_REFERENCE_FIELDS = frozenset(("properties_path", "env_name"))
_RAW_CREDENTIAL_KEY_PARTS = (
    "apikey",
    "privatekey",
    "token",
    "secret",
    "password",
    "passwd",
    "authorization",
    "bearer",
    "accesskey",
)


class HostEventConfigurationError(ValueError):
    """Sanitized loader failure carrying only one closed, stable error code."""

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if type(code) is str and code in _ERROR_CODES
            else "INVALID_CONFIGURATION"
        )
        super().__init__(self.code)

    def __repr__(self) -> str:
        return "HostEventConfigurationError(code={!r})".format(self.code)


def _fail(code: str) -> NoReturn:
    raise HostEventConfigurationError(code) from None


def _is_within(candidate: Path, root: Path) -> bool:
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _read_external_config(
    config_path: Union[str, os.PathLike], repo_root: Union[str, os.PathLike]
) -> bytes:
    try:
        config_lexical = Path(os.path.abspath(os.fspath(config_path)))
        repo_lexical = Path(os.path.abspath(os.fspath(repo_root)))
        repo_resolved = repo_lexical.resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        _fail("CONFIG_PATH_INVALID")

    if not repo_resolved.is_dir():
        _fail("CONFIG_PATH_INVALID")
    if any(
        _is_within(candidate, root)
        for candidate, root in (
            (config_lexical, repo_lexical),
            (config_lexical, repo_resolved),
        )
    ):
        _fail("CONFIG_NOT_EXTERNAL")

    try:
        config_resolved = config_lexical.resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        _fail("CONFIG_PATH_INVALID")
    if any(
        _is_within(config_resolved, root)
        for root in (repo_lexical, repo_resolved)
    ):
        _fail("CONFIG_NOT_EXTERNAL")
    if not config_resolved.is_file():
        _fail("CONFIG_PATH_INVALID")

    try:
        if config_resolved.stat().st_size > _MAX_CONFIG_BYTES:
            _fail("CONFIG_TOO_LARGE")
        with config_resolved.open("rb") as stream:
            contents = stream.read(_MAX_CONFIG_BYTES + 1)
    except HostEventConfigurationError:
        raise
    except (OSError, RuntimeError, ValueError):
        _fail("CONFIG_READ_FAILED")
    if len(contents) > _MAX_CONFIG_BYTES:
        _fail("CONFIG_TOO_LARGE")
    return contents


def _object_pairs_no_duplicates(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_KEY")
        result[key] = value
    return result


def _parse_finite_float(value: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        _fail("NONFINITE_NUMBER")
    return result


def _reject_nonfinite_constant(_value: str) -> NoReturn:
    _fail("NONFINITE_NUMBER")


def _parse_json(contents: bytes) -> Any:
    try:
        text = contents.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        _fail("INVALID_UTF8")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_pairs_no_duplicates,
            parse_float=_parse_finite_float,
            parse_constant=_reject_nonfinite_constant,
        )
    except HostEventConfigurationError:
        raise
    except (ValueError, RecursionError, OverflowError):
        _fail("INVALID_JSON")
    _validate_json_strings_and_keys(value)
    return value


def _normalized_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _validate_json_strings_and_keys(value: Any) -> None:
    pending = [value]
    while pending:
        current = pending.pop()
        if type(current) is str:
            try:
                current.encode("utf-8", errors="strict")
            except UnicodeEncodeError:
                _fail("INVALID_UNICODE")
        elif type(current) is list:
            pending.extend(current)
        elif type(current) is dict:
            for key, child in current.items():
                try:
                    key.encode("utf-8", errors="strict")
                except UnicodeEncodeError:
                    _fail("INVALID_UNICODE")
                normalized = _normalized_key(key)
                if normalized != "maxtokens" and any(
                    fragment in normalized for fragment in _RAW_CREDENTIAL_KEY_PARTS
                ):
                    _fail("FORBIDDEN_CREDENTIAL_FIELD")
                pending.append(child)


def _require_object(value: Any, fields: frozenset) -> dict:
    if type(value) is not dict:
        _fail("INVALID_CONFIGURATION")
    present = set(value)
    if present - fields:
        _fail("UNKNOWN_FIELD")
    if fields - present:
        _fail("MISSING_FIELD")
    return value


def _credential_reference(value: Any, credential_type: type) -> Any:
    if type(value) is not dict:
        _fail("INVALID_CREDENTIAL_REFERENCE")
    keys = set(value)
    if keys - _CREDENTIAL_REFERENCE_FIELDS:
        _fail("UNKNOWN_FIELD")
    if len(keys) != 1:
        _fail("INVALID_CREDENTIAL_REFERENCE")
    name = next(iter(keys))
    reference = value[name]
    if type(reference) is not str or not reference:
        _fail("INVALID_CREDENTIAL_REFERENCE")
    return _construct(credential_type, **{name: reference})


def _construct(constructor: type, **values: Any) -> Any:
    try:
        return constructor(**values)
    except Exception:
        _fail("INVALID_CONFIGURATION")


def _model_config(value: Any) -> ModelRuntimeConfig:
    values = dict(_require_object(value, _MODEL_FIELDS))
    capabilities = values["capabilities"]
    if type(capabilities) is not list or any(
        type(capability) is not str for capability in capabilities
    ):
        _fail("INVALID_CONFIGURATION")
    values["capabilities"] = tuple(capabilities)
    return _construct(ModelRuntimeConfig, **values)


def _build_config(value: Any) -> HostEventGrounderConfig:
    root = _require_object(value, _ROOT_FIELDS)
    if (
        type(root["schema_version"]) is not str
        or root["schema_version"] != HOST_EVENT_CONFIG_SCHEMA_VERSION
    ):
        _fail("UNSUPPORTED_SCHEMA_VERSION")

    source_values = dict(_require_object(root["source"], _SOURCE_FIELDS))
    source_values["credential_ref"] = _credential_reference(
        source_values["credential_ref"], TavilyCredentialRef
    )
    time_budget = source_values["time_budget_seconds"]
    if (
        type(time_budget) not in (int, float)
        or isinstance(time_budget, bool)
        or not math.isfinite(float(time_budget))
        or time_budget <= 0
    ):
        _fail("INVALID_CONFIGURATION")
    byte_budget = source_values["byte_budget"]
    if type(byte_budget) is not int or byte_budget <= 0:
        _fail("INVALID_CONFIGURATION")
    source = _construct(TavilySourceConfig, **source_values)

    discovery_model = _model_config(root["discovery_model"])
    discovery_credential = _credential_reference(
        root["discovery_credential"], ModelCredential
    )
    semantic_model = _model_config(root["semantic_model"])
    semantic_credential = _credential_reference(
        root["semantic_credential"], ModelCredential
    )

    input_bounds = _require_object(root["run_input_bounds"], _INPUT_BOUNDS_FIELDS)
    run_input_bounds = _construct(HostGrounderRunInputBounds, **input_bounds)
    catalog_limits = {
        name: root[name]
        for name in (
            "max_json_bytes",
            "max_source_body_bytes",
            "max_catalog_entries",
            "max_catalog_bytes",
            "max_catalog_paragraphs",
        )
    }
    return _construct(
        HostEventGrounderConfig,
        source=source,
        discovery_model=discovery_model,
        discovery_credential=discovery_credential,
        semantic_model=semantic_model,
        semantic_credential=semantic_credential,
        run_input_bounds=run_input_bounds,
        **catalog_limits
    )


def load_event_grounder_config(
    config_path: Union[str, os.PathLike], *, repo_root: Union[str, os.PathLike]
) -> HostEventGrounderConfig:
    """Load a complete external JSON config without resolving credentials."""

    contents = _read_external_config(config_path, repo_root)
    value = _parse_json(contents)
    try:
        return _build_config(value)
    except HostEventConfigurationError:
        raise
    except Exception:
        _fail("INVALID_CONFIGURATION")
