"""Synthetic transport tests for the bounded pre-Core Event Grounder driver."""

import datetime
import hashlib
import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from convexity_hunter.core_application import CoreOperationalBounds
from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.host_event import (
    HostEventGrounderConfig,
    _publication_datetime,
    create_event_grounder,
)
from convexity_hunter.host_grounder_builder import HostBuildContext, HostSourceBody
from convexity_hunter.host_grounder_evidence_catalog import (
    build_host_evidence_catalog,
    parse_grounder_output_v0_3,
)
from convexity_hunter.host_grounder_run_input import (
    HostGrounderRunInput,
    HostGrounderRunInputBounds,
    HostGrounderSubquestion,
)
from convexity_hunter.host_grounder_runtime import (
    HostGrounderEvidenceCatalogRuntimeResult,
    HostGrounderRuntimeError,
)
from convexity_hunter.host_model import (
    ModelCredential,
    ModelRuntimeConfig,
)
from convexity_hunter.host_sources import TavilyCredentialRef, TavilySourceConfig


_ROOT = Path(__file__).resolve().parents[1]
_RAW_INPUT = "Assess the reported ACME filing."
_RUN_ID = "synthetic-event-run"
_NOW = datetime.datetime(2026, 10, 4, 8, 0, tzinfo=datetime.timezone.utc)
_BODY_BY_URL = {
    "https://source.example/z": "ACME filed a report.\n",
    "https://source.example/a": "The filing describes a possible capacity change.\n",
}
_SEARCH_ORDER = (
    ("source-z", "https://source.example/z"),
    ("source-a", "https://source.example/a"),
)


class _SyntheticResponse:
    def __init__(self, payload):
        self.body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        self.status = 200
        self.headers = {}
        self.closed = False

    def read(self, _size=-1):
        return self.body

    def close(self):
        self.closed = True


class _SyntheticSourceTransport:
    def __init__(self, *, search_order=_SEARCH_ORDER, failed_urls=(), body_overrides=None):
        self.search_order = tuple(search_order)
        self.failed_urls = frozenset(failed_urls)
        self.body_overrides = dict(body_overrides or {})
        self.calls = []
        self.extract_url_orders = []

    def __call__(self, request, _timeout):
        payload = json.loads(request.data.decode("utf-8"))
        self.calls.append((request.full_url, payload))
        if request.full_url.endswith("/search"):
            results = [
                {
                    "id": source_id,
                    "url": url,
                    "title": "Unverified source title",
                    "content": "SEARCH_SNIPPET_MUST_NOT_REACH_MODELS_{}".format(source_id),
                    "published_date": "2026-10-03",
                }
                for source_id, url in self.search_order
            ]
            return _SyntheticResponse(
                {"results": results, "request_id": "synthetic-search"}
            )
        if request.full_url.endswith("/extract"):
            urls = tuple(payload["urls"])
            self.extract_url_orders.append(urls)
            results = [
                {
                    "url": url,
                    "raw_content": self.body_overrides.get(
                        url, _BODY_BY_URL.get(url, "Fetched source body.\n")
                    ),
                }
                for url in urls
                if url not in self.failed_urls
            ]
            failed = [{"url": url, "error": "synthetic failure"} for url in urls if url in self.failed_urls]
            return _SyntheticResponse(
                {
                    "results": results,
                    "failed_results": failed,
                    "request_id": "synthetic-extract",
                }
            )
        raise AssertionError("unexpected synthetic source endpoint")


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _context_and_run_input(run_id, raw_input, source_order, bodies_by_url, bounds):
    user_input = UserEventInput(raw_input)
    run_input = HostGrounderRunInput(
        run_id,
        user_input,
        (HostGrounderSubquestion("user_event_input", raw_input),),
        bounds,
    )
    source_bodies = {
        source_id: HostSourceBody(
            bodies_by_url[url],
            _digest(bodies_by_url[url]),
            url,
            _NOW,
            "Unverified source title",
            None,
        )
        for source_id, url in source_order
    }
    context = HostBuildContext(
        raw_input=user_input,
        submission_id=run_id,
        event_id=run_id,
        producer_id="convexity-hunter-event-grounder",
        producer_version="v0.1",
        observed_at=_NOW,
        source_bodies=source_bodies,
        run_id=run_id,
        canonical_input_hash=run_input.canonical_input_hash,
    )
    return run_input, context


def _model_outputs(run_id, raw_input, source_order, bodies_by_url, config):
    run_input, context = _context_and_run_input(
        run_id,
        raw_input,
        source_order,
        bodies_by_url,
        config.run_input_bounds,
    )
    catalog = build_host_evidence_catalog(
        run_id,
        run_input.canonical_input_hash,
        context.source_bodies,
        max_catalog_entries=config.max_catalog_entries,
        max_catalog_bytes=config.max_catalog_bytes,
        max_catalog_paragraphs=config.max_catalog_paragraphs,
        max_string_bytes=run_input.bounds.max_string_bytes,
        max_array_items=run_input.bounds.max_array_items,
    )
    producer = {
        "schema_version": "grounder-output-v0.3",
        "stage": "semantic",
        "request_id": run_id,
        "claims": [],
        "hypotheses": [],
        "coverage": [
            {
                "subquestion_id": "user_event_input",
                "status": "unresolved",
                "claim_ids": [],
                "gap": "Synthetic fixture supplies no supported hypothesis.",
            }
        ],
        "field_bindings": [],
    }
    normalized, normalized_bytes = parse_grounder_output_v0_3(
        json.dumps(producer, sort_keys=True, separators=(",", ":")),
        config.max_json_bytes,
        max_string_bytes=run_input.bounds.max_string_bytes,
        max_array_items=run_input.bounds.max_array_items,
        run_id=run_id,
        canonical_input_hash=run_input.canonical_input_hash,
        source_bodies=context.source_bodies,
        catalog=catalog,
    )
    verdict = {
        "schema_version": "semantic-verdict-v0.3",
        "run_id": run_id,
        "envelope_hash": _digest(normalized_bytes.decode("utf-8")),
        "source_body_hashes": [
            {"source_id": source_id, "sha256": source.body_sha256}
            for source_id, source in sorted(context.source_bodies.items())
        ],
        "claims": [],
        "hypotheses": [],
        "field_bindings": [],
        "coverage": [
            {
                "index": 0,
                "subquestion_id": "user_event_input",
                "outcome": "unresolved",
                "rationale": "The synthetic fixture does not establish an answer.",
                "evidence_refs": [],
            }
        ],
    }
    return (
        json.dumps(producer, sort_keys=True, separators=(",", ":")),
        json.dumps(verdict, sort_keys=True, separators=(",", ":")),
        normalized,
    )


class _SyntheticModelTransport:
    def __init__(self, discovery_content, semantic_content):
        self.contents = {
            "fixture-discovery": discovery_content,
            "fixture-semantic": semantic_content,
        }
        self.calls = []

    def __call__(self, request, _timeout):
        payload = json.loads(request.data.decode("utf-8"))
        self.calls.append(payload)
        model = payload["model"]
        content = self.contents[model]
        return _SyntheticResponse(
            {
                "id": "synthetic-" + model,
                "model": model,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
            }
        )


def _config(*, max_source_body_bytes=20_000, source_order=_SEARCH_ORDER):
    return HostEventGrounderConfig(
        source=TavilySourceConfig(
            credential_ref=TavilyCredentialRef(env_name="SYNTHETIC_TAVILY_KEY"),
            paygo_off_confirmed=True,
            request_budget=2,
            credit_budget=2,
            max_request_bytes=20_000,
            max_response_bytes=200_000,
            timeout_seconds=2.0,
            max_search_results=len(source_order),
            max_extract_urls=len(source_order),
        ),
        discovery_model=ModelRuntimeConfig(
            provider="deepseek",
            model="fixture-discovery",
            base_endpoint="https://api.deepseek.com",
            role="discovery",
            capabilities=("json_mode",),
            timeout_seconds=2.0,
            request_budget=1,
            max_tokens=2_000,
            max_input_bytes=500_000,
            max_output_bytes=200_000,
            remote_enabled=True,
            fee_authorized=True,
            json_mode=True,
            thinking_enabled=False,
        ),
        discovery_credential=ModelCredential(env_name="SYNTHETIC_DISCOVERY_KEY"),
        semantic_model=ModelRuntimeConfig(
            provider="deepseek",
            model="fixture-semantic",
            base_endpoint="https://api.deepseek.com",
            role="semantic",
            capabilities=("json_mode",),
            timeout_seconds=2.0,
            request_budget=1,
            max_tokens=2_000,
            max_input_bytes=500_000,
            max_output_bytes=200_000,
            remote_enabled=True,
            fee_authorized=True,
            json_mode=True,
            thinking_enabled=False,
        ),
        semantic_credential=ModelCredential(env_name="SYNTHETIC_SEMANTIC_KEY"),
        run_input_bounds=HostGrounderRunInputBounds(20_000, 10_000, 10),
        max_json_bytes=100_000,
        max_source_body_bytes=max_source_body_bytes,
        max_catalog_entries=64,
        max_catalog_bytes=32_768,
        max_catalog_paragraphs=128,
    )


class HostEventGrounderTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "SYNTHETIC_TAVILY_KEY": "synthetic-only-key",
                "SYNTHETIC_DISCOVERY_KEY": "synthetic-only-key",
                "SYNTHETIC_SEMANTIC_KEY": "synthetic-only-key",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_factory_returns_frozen_callback_signature_and_redacts_config(self):
        config = _config()
        callback = create_event_grounder(config, repo_root=_ROOT)
        self.assertEqual(
            tuple(inspect.signature(callback).parameters),
            ("raw_input", "run_id", "bounds"),
        )
        self.assertNotIn("SYNTHETIC", repr(config))
        with self.assertRaisesRegex(TypeError, "host_context_preparer"):
            create_event_grounder(config, repo_root=_ROOT, host_context_preparer=object())

    def test_run_start_configuration_snapshot_is_exact_safe_and_detached(self):
        callback = create_event_grounder(_config(), repo_root=_ROOT)
        snapshot = callback.configuration_snapshot()
        self.assertEqual(set(snapshot), {"models", "sources", "skills"})
        self.assertEqual(snapshot["skills"], [])
        self.assertEqual(len(snapshot["models"]), 2)
        self.assertEqual(
            [model["role"] for model in snapshot["models"]],
            ["discovery", "semantic"],
        )
        model_fields = {
            "schema_version",
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
        }
        for model in snapshot["models"]:
            self.assertEqual(set(model), model_fields)
            self.assertEqual(model["schema_version"], "host-event-model-snapshot-v0.1")
            self.assertEqual(model["provider"], "deepseek")
            self.assertEqual(model["base_endpoint"], "https://api.deepseek.com")
        self.assertEqual(len(snapshot["sources"]), 1)
        source = snapshot["sources"][0]
        self.assertEqual(
            set(source),
            {
                "schema_version",
                "provider",
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
                "grounder_limits",
            },
        )
        self.assertEqual(source["schema_version"], "host-event-source-snapshot-v0.1")
        self.assertEqual(source["provider"], "tavily")
        self.assertEqual(source["grounder_limits"]["run_input_bounds"], {
            "max_run_input_bytes": 20_000,
            "max_string_bytes": 10_000,
            "max_array_items": 10,
        })
        encoded = json.dumps(snapshot, sort_keys=True)
        for forbidden in (
            "SYNTHETIC_TAVILY_KEY",
            "SYNTHETIC_DISCOVERY_KEY",
            "SYNTHETIC_SEMANTIC_KEY",
            "synthetic-only-key",
            "credential_ref",
            "properties_path",
            "env_name",
            "headers",
        ):
            self.assertNotIn(forbidden, encoded)
        self.assertLessEqual(len(encoded.encode("utf-8")), _config().max_json_bytes)

        snapshot["models"][0]["model"] = "caller-mutated-copy"
        fresh_snapshot = callback.configuration_snapshot()
        self.assertEqual(fresh_snapshot["models"][0]["model"], "fixture-discovery")

    def test_factory_revalidates_constructor_bypassed_model_role_and_source_budget(self):
        wrong_role = _config()
        object.__setattr__(wrong_role.discovery_model, "role", "semantic")
        with self.assertRaisesRegex(ValueError, "wrong role"):
            create_event_grounder(wrong_role, repo_root=_ROOT)

        invalid_budget = _config()
        object.__setattr__(invalid_budget.source, "request_budget", 0)
        with self.assertRaisesRegex(ValueError, "INVALID_REQUEST_BUDGET"):
            create_event_grounder(invalid_budget, repo_root=_ROOT)

    def test_factory_rejects_nonapproved_provider_and_endpoint_before_snapshot(self):
        for model_name in ("discovery_model", "semantic_model"):
            for field, value in (
                ("provider", "deepseek-compatible"),
                ("base_endpoint", "https://api.deepseek.com/v1"),
                ("base_endpoint", "https://api.deepseek.com.attacker.invalid"),
            ):
                with self.subTest(model=model_name, field=field, value=value):
                    config = _config()
                    model = getattr(config, model_name)
                    object.__setattr__(model, field, value)
                    source_transport = _SyntheticSourceTransport()
                    model_transport = _SyntheticModelTransport("{}", "{}")
                    with self.assertRaisesRegex(
                        ValueError, "UNAPPROVED_MODEL_CONFIGURATION"
                    ):
                        create_event_grounder(
                            config,
                            repo_root=_ROOT,
                            source_transport=source_transport,
                            discovery_transport=model_transport,
                            semantic_transport=model_transport,
                        )
                    self.assertEqual(source_transport.calls, [])
                    self.assertEqual(model_transport.calls, [])

    def test_resolved_futu_credential_symlink_is_rejected_without_reading_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "futu_api_config.properties"
            target.touch()
            alias = Path(directory) / "external-model.properties"
            alias.symlink_to(target)
            config = _config()
            object.__setattr__(
                config,
                "semantic_credential",
                ModelCredential(properties_path=alias),
            )

            def forbidden_read(*_args, **_kwargs):
                raise AssertionError("credential file contents must not be read")

            with patch.object(Path, "read_text", forbidden_read):
                with self.assertRaisesRegex(ValueError, "futu credential files"):
                    create_event_grounder(config, repo_root=_ROOT)

    def test_constructor_bypassed_core_bounds_fail_before_any_source_call(self):
        config = _config()
        source_transport = _SyntheticSourceTransport()
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
        )
        invalid_bounds = object.__new__(CoreOperationalBounds)
        object.__setattr__(invalid_bounds, "max_submissions", -1)
        object.__setattr__(invalid_bounds, "max_hypotheses", 1)
        object.__setattr__(invalid_bounds, "max_browser_rows", 1)
        object.__setattr__(invalid_bounds, "max_cases", 1)
        object.__setattr__(invalid_bounds, "quote_timeout_seconds", 1.0)

        with self.assertRaisesRegex(TypeError, "valid CoreOperationalBounds"):
            callback(_RAW_INPUT, run_id=_RUN_ID, bounds=invalid_bounds)
        self.assertEqual(source_transport.calls, [])

    def test_factory_config_is_revalidated_again_at_each_call(self):
        source_transport = _SyntheticSourceTransport()
        callback = create_event_grounder(
            _config(),
            repo_root=_ROOT,
            source_transport=source_transport,
        )
        captured_config = inspect.getclosurevars(callback).nonlocals["config"]
        object.__setattr__(captured_config.source, "credit_budget", 0)

        with self.assertRaisesRegex(ValueError, "INVALID_CREDIT_BUDGET"):
            callback(
                _RAW_INPUT,
                run_id=_RUN_ID,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
        self.assertEqual(source_transport.calls, [])

    def test_call_revalidates_model_allowlist_before_transport(self):
        source_transport = _SyntheticSourceTransport()
        callback = create_event_grounder(
            _config(),
            repo_root=_ROOT,
            source_transport=source_transport,
        )
        captured_config = inspect.getclosurevars(callback).nonlocals["config"]
        object.__setattr__(captured_config.semantic_model, "base_endpoint", "https://evil.invalid")

        with self.assertRaisesRegex(ValueError, "UNAPPROVED_MODEL_CONFIGURATION"):
            callback(
                _RAW_INPUT,
                run_id=_RUN_ID,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
        self.assertEqual(source_transport.calls, [])

    def test_synthetic_transport_wiring_returns_exact_runtime_and_fresh_budgets(self):
        config = _config()
        discovery_content, semantic_content, _normalized = _model_outputs(
            _RUN_ID, _RAW_INPUT, _SEARCH_ORDER, _BODY_BY_URL, config
        )
        source_transport = _SyntheticSourceTransport()
        model_transport = _SyntheticModelTransport(discovery_content, semantic_content)
        preparation_calls = []

        def independent_preparer(snapshot, receipt, original_context):
            preparation_calls.append((snapshot, receipt, original_context))
            return original_context

        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
            host_context_preparer=independent_preparer,
        )

        first = callback(
            _RAW_INPUT,
            run_id=_RUN_ID,
            bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
        )
        second = callback(
            _RAW_INPUT,
            run_id=_RUN_ID,
            bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
        )

        self.assertIs(type(first), HostGrounderEvidenceCatalogRuntimeResult)
        self.assertIs(type(second), HostGrounderEvidenceCatalogRuntimeResult)
        self.assertIsNone(first.build_result.submission)
        self.assertIsNone(second.build_result.submission)
        self.assertEqual(len(preparation_calls), 2)
        for snapshot, receipt, context in preparation_calls:
            self.assertTrue(snapshot.envelope_hash)
            self.assertEqual(receipt["schema_version"], "semantic-validation-v0.2")
            self.assertEqual(context.raw_input.description, _RAW_INPUT)
            self.assertIsNone(context.event_description_binding)
            self.assertIsNone(context.event_date_range)
            self.assertEqual(context.underlying_bindings, {})
            self.assertEqual(tuple(context.source_bodies), ("source-z", "source-a"))
            self.assertTrue(
                all(source.published_at is None for source in context.source_bodies.values())
            )

        self.assertEqual(
            source_transport.extract_url_orders,
            [tuple(url for _source_id, url in _SEARCH_ORDER)] * 2,
        )
        self.assertEqual(len(source_transport.calls), 4)
        self.assertEqual(len(model_transport.calls), 4)
        model_user_content = [
            message["content"]
            for call in model_transport.calls
            for message in call["messages"]
            if message["role"] == "user"
        ]
        self.assertTrue(
            all(
                "SEARCH_SNIPPET_MUST_NOT_REACH_MODELS" not in content
                for content in model_user_content
            )
        )
        self.assertTrue(any("ACME filed a report." in content for content in model_user_content))
        system_prompts = [call["messages"][0]["content"] for call in model_transport.calls]
        self.assertTrue(
            any("host-grounder-discovery-prompt-v0.6" in prompt for prompt in system_prompts)
        )
        self.assertTrue(
            any("host-grounder-semantic-verifier-prompt-v0.7" in prompt for prompt in system_prompts)
        )

    def test_partial_extract_is_explicit_failure_and_never_runs_models(self):
        config = _config()
        discovery, semantic, _normalized = _model_outputs(
            _RUN_ID, _RAW_INPUT, _SEARCH_ORDER, _BODY_BY_URL, config
        )
        source_transport = _SyntheticSourceTransport(
            failed_urls={_SEARCH_ORDER[1][1]}
        )
        model_transport = _SyntheticModelTransport(discovery, semantic)
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            callback(
                _RAW_INPUT,
                run_id=_RUN_ID,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
        self.assertEqual(raised.exception.code, "EXTRACTION_FAILURE")
        self.assertEqual(str(raised.exception), "EXTRACTION_FAILURE")
        self.assertEqual(len(source_transport.calls), 2)
        self.assertEqual(model_transport.calls, [])

    def test_empty_extracted_body_is_not_forwarded_to_a_model(self):
        config = _config(source_order=_SEARCH_ORDER[:1])
        discovery, semantic, _normalized = _model_outputs(
            _RUN_ID,
            _RAW_INPUT,
            _SEARCH_ORDER[:1],
            _BODY_BY_URL,
            config,
        )
        source_transport = _SyntheticSourceTransport(
            search_order=_SEARCH_ORDER[:1], body_overrides={_SEARCH_ORDER[0][1]: ""}
        )
        model_transport = _SyntheticModelTransport(discovery, semantic)
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            callback(
                _RAW_INPUT,
                run_id=_RUN_ID,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
        self.assertEqual(raised.exception.code, "EXTRACTION_FAILURE")
        self.assertEqual(model_transport.calls, [])

    def test_source_body_limit_rejects_without_truncation_or_model_calls(self):
        config = _config(max_source_body_bytes=4, source_order=_SEARCH_ORDER[:1])
        discovery, semantic, _normalized = _model_outputs(
            _RUN_ID, _RAW_INPUT, _SEARCH_ORDER[:1], _BODY_BY_URL, config
        )
        source_transport = _SyntheticSourceTransport(search_order=_SEARCH_ORDER[:1])
        model_transport = _SyntheticModelTransport(discovery, semantic)
        callback = create_event_grounder(
            config,
            repo_root=_ROOT,
            source_transport=source_transport,
            discovery_transport=model_transport,
            semantic_transport=model_transport,
        )

        with self.assertRaises(HostGrounderRuntimeError) as raised:
            callback(
                _RAW_INPUT,
                run_id=_RUN_ID,
                bounds=CoreOperationalBounds(1, 1, 1, 1, 1.0),
            )
        self.assertEqual(raised.exception.code, "SOURCE_BODY_LIMIT_EXCEEDED")
        self.assertEqual(model_transport.calls, [])

    def test_date_only_publication_is_not_promoted_to_an_aware_timestamp(self):
        self.assertIsNone(_publication_datetime("2026-10-03"))
        self.assertEqual(
            _publication_datetime("2026-10-03T09:30:00Z"),
            datetime.datetime(2026, 10, 3, 9, 30, tzinfo=datetime.timezone.utc),
        )
