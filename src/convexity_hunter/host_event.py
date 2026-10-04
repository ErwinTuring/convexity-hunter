"""Bounded Event Grounder composition over the existing Host adapters.

This module performs source acquisition and the pre-Core Grounder run only. It
does not assess EI, invoke market data, persist records, or fabricate Event
dates/listing evidence. Its default context preparer retains unknown date,
description, and listing bindings; this is not a complete product Grounder.
Credentials remain external references and are resolved only by the existing
clients when a request is made.
"""

from __future__ import annotations

import datetime
import hashlib
import ipaddress
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Union
from urllib.parse import urlsplit

from .core_application import CoreOperationalBounds
from .event_entry import UserEventInput
from .host_grounder_builder import HostBuildContext, HostSourceBody
from .host_grounder_evidence_catalog import HostEvidenceCatalogAuditHolder
from .host_grounder_run_input import (
    HostGrounderRunInput,
    HostGrounderRunInputBounds,
    HostGrounderSubquestion,
)
from .host_grounder_runtime import (
    HostGrounderEvidenceCatalogRuntimeResult,
    HostGrounderRuntimeError,
    run_host_grounder_same_run_evidence_catalog_v0_5,
)
from .host_model import (
    ChatCompletionsClient,
    ModelCredential,
    ModelRuntimeConfig,
    ModelTransportError,
)
from .host_sources import (
    TavilyCredentialRef,
    TavilySourceClient,
    TavilySourceConfig,
    TavilyTransportError,
)


__all__ = ("HostEventGrounderConfig", "create_event_grounder")


_PRODUCER_ID = "convexity-hunter-event-grounder"
_PRODUCER_VERSION = "v0.1"
_SUBQUESTION_ID = "user_event_input"
_FORBIDDEN_CREDENTIAL_BASENAME = "futu_api_config.properties"
_APPROVED_MODEL_PROVIDER = "deepseek"
_APPROVED_MODEL_BASE_ENDPOINT = "https://api.deepseek.com"


def _positive_int(name: str, value: object) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError("{} must be a positive integer".format(name))


def _is_loopback_endpoint(endpoint: str) -> bool:
    hostname = urlsplit(endpoint).hostname
    if hostname is None:
        return True
    normalized = hostname.rstrip(".").casefold()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _reject_futu_credential_path(credential: object) -> None:
    path = getattr(credential, "properties_path", None)
    if path is None:
        return
    try:
        supplied = Path(path)
        resolved = supplied.resolve(strict=False)
    except (OSError, RuntimeError, TypeError, ValueError):
        raise ValueError("credential reference is invalid") from None
    if any(
        candidate.name.casefold() == _FORBIDDEN_CREDENTIAL_BASENAME
        for candidate in (supplied, resolved)
    ):
        raise ValueError("futu credential files are not valid Grounder credentials")


@dataclass(frozen=True, repr=False)
class HostEventGrounderConfig:
    """All non-economic budgets and external client settings for Event Grounder.

    A strict external loader can construct this record from the following
    existing typed components: ``TavilySourceConfig``, two role-specific
    ``ModelRuntimeConfig``/``ModelCredential`` pairs, and
    ``HostGrounderRunInputBounds``. The five Grounder limits are mandatory;
    this layer introduces no numeric defaults.
    """

    source: TavilySourceConfig
    discovery_model: ModelRuntimeConfig
    discovery_credential: ModelCredential
    semantic_model: ModelRuntimeConfig
    semantic_credential: ModelCredential
    run_input_bounds: HostGrounderRunInputBounds
    max_json_bytes: int
    max_source_body_bytes: int
    max_catalog_entries: int
    max_catalog_bytes: int
    max_catalog_paragraphs: int

    def __post_init__(self) -> None:
        if type(self.source) is not TavilySourceConfig:
            raise TypeError("source must be TavilySourceConfig")
        for name, config, credential, role in (
            ("discovery", self.discovery_model, self.discovery_credential, "discovery"),
            ("semantic", self.semantic_model, self.semantic_credential, "semantic"),
        ):
            if type(config) is not ModelRuntimeConfig:
                raise TypeError("{}_model must be ModelRuntimeConfig".format(name))
            if config.role != role:
                raise ValueError("{}_model has the wrong role".format(name))
            if type(credential) is not ModelCredential:
                raise TypeError("{}_credential must be ModelCredential".format(name))
            if not config.remote_enabled or not config.fee_authorized:
                raise ValueError("{} model must be explicitly remote and fee-authorized".format(name))
            if _is_loopback_endpoint(config.base_endpoint):
                raise ValueError("local model endpoints are not supported")
            _reject_futu_credential_path(credential)
        _reject_futu_credential_path(self.source.credential_ref)
        if type(self.run_input_bounds) is not HostGrounderRunInputBounds:
            raise TypeError("run_input_bounds must be HostGrounderRunInputBounds")
        for name in (
            "max_json_bytes",
            "max_source_body_bytes",
            "max_catalog_entries",
            "max_catalog_bytes",
            "max_catalog_paragraphs",
        ):
            _positive_int(name, getattr(self, name))

    def __repr__(self) -> str:
        return "HostEventGrounderConfig(<redacted>)"


def _revalidate_config(config: object) -> HostEventGrounderConfig:
    """Re-run every nested constructor, including after frozen-object bypasses."""
    if type(config) is not HostEventGrounderConfig:
        raise TypeError("config must be HostEventGrounderConfig")
    source_config = config.source
    if type(source_config) is not TavilySourceConfig:
        raise TypeError("source must be TavilySourceConfig")
    source_credential_ref = source_config.credential_ref
    if type(source_credential_ref) is not TavilyCredentialRef:
        raise TypeError("source credential reference is invalid")
    source_credential_ref = TavilyCredentialRef(
        properties_path=source_credential_ref.properties_path,
        env_name=source_credential_ref.env_name,
    )
    source = TavilySourceConfig(
        credential_ref=source_credential_ref,
        paygo_off_confirmed=source_config.paygo_off_confirmed,
        request_budget=source_config.request_budget,
        credit_budget=source_config.credit_budget,
        max_request_bytes=source_config.max_request_bytes,
        max_response_bytes=source_config.max_response_bytes,
        timeout_seconds=source_config.timeout_seconds,
        time_budget_seconds=source_config.time_budget_seconds,
        byte_budget=source_config.byte_budget,
        max_search_results=source_config.max_search_results,
        max_extract_urls=source_config.max_extract_urls,
    )

    def checked_model(
        model_config: object, credential: object, role: str
    ) -> tuple:
        if type(model_config) is not ModelRuntimeConfig:
            raise TypeError("{}_model must be ModelRuntimeConfig".format(role))
        if type(credential) is not ModelCredential:
            raise TypeError("{}_credential must be ModelCredential".format(role))
        if (
            model_config.provider != _APPROVED_MODEL_PROVIDER
            or model_config.base_endpoint != _APPROVED_MODEL_BASE_ENDPOINT
        ):
            raise ValueError("UNAPPROVED_MODEL_CONFIGURATION")
        checked_config = ModelRuntimeConfig(
            provider=model_config.provider,
            model=model_config.model,
            base_endpoint=model_config.base_endpoint,
            role=model_config.role,
            capabilities=model_config.capabilities,
            timeout_seconds=model_config.timeout_seconds,
            request_budget=model_config.request_budget,
            max_tokens=model_config.max_tokens,
            max_input_bytes=model_config.max_input_bytes,
            max_output_bytes=model_config.max_output_bytes,
            remote_enabled=model_config.remote_enabled,
            fee_authorized=model_config.fee_authorized,
            json_mode=model_config.json_mode,
            thinking_enabled=model_config.thinking_enabled,
        )
        checked_credential = ModelCredential(
            properties_path=credential.properties_path,
            env_name=credential.env_name,
        )
        return checked_config, checked_credential

    discovery_model, discovery_credential = checked_model(
        config.discovery_model, config.discovery_credential, "discovery"
    )
    semantic_model, semantic_credential = checked_model(
        config.semantic_model, config.semantic_credential, "semantic"
    )
    input_bounds = config.run_input_bounds
    if type(input_bounds) is not HostGrounderRunInputBounds:
        raise TypeError("run_input_bounds must be HostGrounderRunInputBounds")
    checked_input_bounds = HostGrounderRunInputBounds(
        max_run_input_bytes=input_bounds.max_run_input_bytes,
        max_string_bytes=input_bounds.max_string_bytes,
        max_array_items=input_bounds.max_array_items,
    )
    return HostEventGrounderConfig(
        source=source,
        discovery_model=discovery_model,
        discovery_credential=discovery_credential,
        semantic_model=semantic_model,
        semantic_credential=semantic_credential,
        run_input_bounds=checked_input_bounds,
        max_json_bytes=config.max_json_bytes,
        max_source_body_bytes=config.max_source_body_bytes,
        max_catalog_entries=config.max_catalog_entries,
        max_catalog_bytes=config.max_catalog_bytes,
        max_catalog_paragraphs=config.max_catalog_paragraphs,
    )


def _retain_unknown_context(
    _snapshot: object,
    _receipt: object,
    original_context: HostBuildContext,
) -> HostBuildContext:
    """Retain unknown fields; does not resolve description/date/listing evidence."""
    return original_context


def _publication_datetime(value: Optional[str]) -> Optional[datetime.datetime]:
    """Retain only an explicitly timezone-aware publication timestamp."""
    if type(value) is not str:
        return None
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _safe_configuration_snapshot(config: HostEventGrounderConfig) -> bytes:
    """Serialize only the fixed, non-secret run-start configuration allowlist."""
    def model_snapshot(model: ModelRuntimeConfig) -> dict:
        endpoint = urlsplit(model.base_endpoint)
        # ModelRuntimeConfig already rejects userinfo, query, and fragment.
        # Reassemble only the URL components accepted for the public snapshot.
        host = endpoint.hostname
        if host is None:
            raise ValueError("model endpoint is invalid")
        if ":" in host and not host.startswith("["):
            host = "[{}]".format(host)
        port = endpoint.port
        netloc = host if port is None else "{}:{}".format(host, port)
        clean_endpoint = "{}://{}{}".format(
            endpoint.scheme.casefold(), netloc, endpoint.path
        )
        return {
            "schema_version": "host-event-model-snapshot-v0.1",
            "role": model.role,
            "provider": model.provider,
            "model": model.model,
            "base_endpoint": clean_endpoint,
            "capabilities": list(model.capabilities),
            "timeout_seconds": model.timeout_seconds,
            "request_budget": model.request_budget,
            "max_tokens": model.max_tokens,
            "max_input_bytes": model.max_input_bytes,
            "max_output_bytes": model.max_output_bytes,
            "remote_enabled": model.remote_enabled,
            "fee_authorized": model.fee_authorized,
            "json_mode": model.json_mode,
            "thinking_enabled": model.thinking_enabled,
        }

    source = config.source
    snapshot = {
        "models": [
            model_snapshot(config.discovery_model),
            model_snapshot(config.semantic_model),
        ],
        "sources": [
            {
                "schema_version": "host-event-source-snapshot-v0.1",
                "provider": "tavily",
                "paygo_off_confirmed": source.paygo_off_confirmed,
                "request_budget": source.request_budget,
                "credit_budget": source.credit_budget,
                "max_request_bytes": source.max_request_bytes,
                "max_response_bytes": source.max_response_bytes,
                "timeout_seconds": source.timeout_seconds,
                "time_budget_seconds": source.time_budget_seconds,
                "byte_budget": source.byte_budget,
                "max_search_results": source.max_search_results,
                "max_extract_urls": source.max_extract_urls,
                "grounder_limits": {
                    "run_input_bounds": {
                        "max_run_input_bytes": config.run_input_bounds.max_run_input_bytes,
                        "max_string_bytes": config.run_input_bounds.max_string_bytes,
                        "max_array_items": config.run_input_bounds.max_array_items,
                    },
                    "max_json_bytes": config.max_json_bytes,
                    "max_source_body_bytes": config.max_source_body_bytes,
                    "max_catalog_entries": config.max_catalog_entries,
                    "max_catalog_bytes": config.max_catalog_bytes,
                    "max_catalog_paragraphs": config.max_catalog_paragraphs,
                },
            }
        ],
        "skills": [],
    }
    try:
        encoded = json.dumps(
            snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8", errors="strict")
    except (TypeError, ValueError, UnicodeEncodeError):
        raise ValueError("configuration snapshot is invalid") from None
    if len(encoded) > config.max_json_bytes:
        raise ValueError("configuration snapshot exceeds max_json_bytes")
    return encoded


def create_event_grounder(
    config: HostEventGrounderConfig,
    *,
    repo_root: Union[str, Path],
    source_transport: Optional[Callable[[Any, float], Any]] = None,
    discovery_transport: Optional[Callable[[Any, float], Any]] = None,
    semantic_transport: Optional[Callable[[Any, float], Any]] = None,
    host_context_preparer: Optional[Callable[..., HostBuildContext]] = None,
) -> Callable[..., HostGrounderEvidenceCatalogRuntimeResult]:
    """Return the frozen server callback, creating fresh clients per run.

    Optional transports are the same narrow test seam exposed by the existing
    clients. Production callers omit them and use the configured HTTP clients.
    """
    config = _revalidate_config(config)
    if host_context_preparer is not None and not callable(host_context_preparer):
        raise TypeError("host_context_preparer must be callable or None")
    for name, transport in (
        ("source_transport", source_transport),
        ("discovery_transport", discovery_transport),
        ("semantic_transport", semantic_transport),
    ):
        if transport is not None and not callable(transport):
            raise TypeError("{} must be callable or None".format(name))
    context_preparer = (
        _retain_unknown_context
        if host_context_preparer is None
        else host_context_preparer
    )
    # Capture immutable canonical bytes now, before the host can initiate any
    # external call. The accessor below returns a detached JSON-compatible copy.
    snapshot_bytes = _safe_configuration_snapshot(config)

    def configuration_snapshot() -> dict:
        """Return a fresh JSON-safe copy of the fixed non-secret config snapshot.

        Hosts can persist this run-start record before invoking the callback.
        Mutating a returned object cannot alter the captured snapshot.
        """
        return json.loads(snapshot_bytes.decode("utf-8"))

    def event_grounder(
        raw_input: str,
        *,
        run_id: str,
        bounds: CoreOperationalBounds,
    ) -> HostGrounderEvidenceCatalogRuntimeResult:
        if not callable(context_preparer):
            raise HostGrounderRuntimeError("HOST_CONTEXT_PREPARER_INVALID")
        if type(bounds) is not CoreOperationalBounds:
            raise TypeError("bounds must be CoreOperationalBounds")
        try:
            CoreOperationalBounds(
                max_submissions=bounds.max_submissions,
                max_hypotheses=bounds.max_hypotheses,
                max_browser_rows=bounds.max_browser_rows,
                max_cases=bounds.max_cases,
                quote_timeout_seconds=bounds.quote_timeout_seconds,
            )
        except (AttributeError, TypeError, ValueError):
            raise TypeError("bounds must be a valid CoreOperationalBounds") from None
        active_config = _revalidate_config(config)
        user_input = UserEventInput(raw_input)
        subquestion = HostGrounderSubquestion(_SUBQUESTION_ID, raw_input)
        run_input = HostGrounderRunInput(
            run_id,
            user_input,
            (subquestion,),
            active_config.run_input_bounds,
        )

        source_client = TavilySourceClient(
            active_config.source,
            repo_root=repo_root,
            transport=source_transport,
        )
        discovery_client = ChatCompletionsClient(
            active_config.discovery_model,
            active_config.discovery_credential,
            repo_root=repo_root,
            transport=discovery_transport,
        )
        semantic_client = ChatCompletionsClient(
            active_config.semantic_model,
            active_config.semantic_credential,
            repo_root=repo_root,
            transport=semantic_transport,
        )

        # One Basic Search plus one Basic Extract (at most five URLs, one
        # Extract credit). Fail before the first paid-capable call if the
        # caller's own source budget cannot cover that bounded operation.
        if source_client.remaining_request_budget < 2:
            raise TavilyTransportError("REQUEST_BUDGET_EXHAUSTED")
        if source_client.remaining_credit_budget < 2:
            raise TavilyTransportError("CREDIT_BUDGET_EXHAUSTED")
        if discovery_client.remaining_request_budget < 1:
            raise ModelTransportError("REQUEST_BUDGET_EXHAUSTED")
        if semantic_client.remaining_request_budget < 1:
            raise ModelTransportError("REQUEST_BUDGET_EXHAUSTED")

        max_results = min(
            active_config.source.max_search_results,
            active_config.source.max_extract_urls,
            active_config.run_input_bounds.max_array_items,
        )
        search_result = source_client.search(raw_input, max_results=max_results)
        references = search_result.sources
        if not references:
            # No result is a stage failure, not evidence that the full source
            # universe was searched or that the request has complete coverage.
            raise HostGrounderRuntimeError("NO_SEARCH_RESULTS")

        requested_urls = tuple(reference.url for reference in references)
        extracted = source_client.extract(
            requested_urls,
            query=raw_input,
            source_refs=references,
        )
        if (
            not extracted.coverage.is_complete
            or extracted.failed_extracts
            or extracted.urls != requested_urls
            or len(extracted.bodies) != len(references)
            or tuple(body.url for body in extracted.bodies) != requested_urls
        ):
            # A partial Extract is a conservative pre-model failure, not a
            # claim that no sources exist or that source coverage is complete.
            # The frozen runtime result has no Tavily receipt slot, so this
            # exact-result interface does not retain a partial receipt.
            raise HostGrounderRuntimeError("EXTRACTION_FAILURE")

        reference_by_url = {reference.url: reference for reference in references}
        retrieved_at = datetime.datetime.now(datetime.timezone.utc)
        source_bodies = {}
        for body in extracted.bodies:
            reference = reference_by_url.get(body.url)
            if (
                reference is None
                or body.source_id != reference.source_id
                or not body.body.strip()
                or body.source_id in source_bodies
            ):
                raise HostGrounderRuntimeError("EXTRACTION_FAILURE")
            encoded_body = body.body.encode("utf-8", errors="strict")
            source_bodies[body.source_id] = HostSourceBody(
                body=body.body,
                body_sha256=hashlib.sha256(encoded_body).hexdigest(),
                final_locator=body.url,
                retrieved_at=retrieved_at,
                title=reference.title,
                published_at=_publication_datetime(body.publication_date),
            )

        context = HostBuildContext(
            raw_input=user_input,
            submission_id=run_id,
            event_id=run_id,
            producer_id=_PRODUCER_ID,
            producer_version=_PRODUCER_VERSION,
            observed_at=retrieved_at,
            source_bodies=source_bodies,
            run_id=run_id,
            canonical_input_hash=run_input.canonical_input_hash,
            # No event-date, hypothesis, listing, or caller-policy evidence is
            # inferred from UserEventInput hints or arbitrary web text.
        )
        audit_holder = HostEvidenceCatalogAuditHolder(
            run_id=run_id,
            canonical_input_hash=run_input.canonical_input_hash,
        )
        return run_host_grounder_same_run_evidence_catalog_v0_5(
            run_input,
            context,
            discovery_client=discovery_client,
            semantic_client=semantic_client,
            audit_holder=audit_holder,
            max_json_bytes=active_config.max_json_bytes,
            max_source_body_bytes=active_config.max_source_body_bytes,
            max_catalog_entries=active_config.max_catalog_entries,
            max_catalog_bytes=active_config.max_catalog_bytes,
            max_catalog_paragraphs=active_config.max_catalog_paragraphs,
            host_context_preparer=context_preparer,
        )

    event_grounder.configuration_snapshot = configuration_snapshot
    return event_grounder
