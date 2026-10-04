"""Synthetic tests for strict external Event Grounder config loading only."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import convexity_hunter.host_event_config as config_module
from convexity_hunter.host_event import HostEventGrounderConfig
from convexity_hunter.host_event_config import (
    HOST_EVENT_CONFIG_SCHEMA_VERSION,
    HostEventConfigurationError,
    _MAX_CONFIG_BYTES,
    load_event_grounder_config,
)
from convexity_hunter.host_grounder_run_input import HostGrounderRunInputBounds
from convexity_hunter.host_model import ModelCredential, ModelRuntimeConfig
from convexity_hunter.host_sources import TavilyCredentialRef, TavilySourceConfig


REPO_ROOT = Path(__file__).resolve().parents[1]


def _model(role):
    return {
        "provider": "synthetic-provider",
        "model": "synthetic-model",
        "base_endpoint": "https://models.example.invalid/v1",
        "role": role,
        "capabilities": ["json_mode", "thinking"],
        "timeout_seconds": 5.0,
        "request_budget": 1,
        "max_tokens": 256,
        "max_input_bytes": 8192,
        "max_output_bytes": 4096,
        "remote_enabled": True,
        "fee_authorized": True,
        "json_mode": True,
        "thinking_enabled": True,
    }


def _document():
    return {
        "schema_version": HOST_EVENT_CONFIG_SCHEMA_VERSION,
        "source": {
            "credential_ref": {"env_name": "TAVILY_TEST_KEY"},
            "paygo_off_confirmed": True,
            "request_budget": 2,
            "credit_budget": 2,
            "max_request_bytes": 8192,
            "max_response_bytes": 16384,
            "timeout_seconds": 5.0,
            "time_budget_seconds": 30.0,
            "byte_budget": 32768,
            "max_search_results": 5,
            "max_extract_urls": 5,
        },
        "discovery_model": _model("discovery"),
        "discovery_credential": {"env_name": "DISCOVERY_TEST_KEY"},
        "semantic_model": _model("semantic"),
        "semantic_credential": {"env_name": "SEMANTIC_TEST_KEY"},
        "run_input_bounds": {
            "max_run_input_bytes": 32768,
            "max_string_bytes": 8192,
            "max_array_items": 32,
        },
        "max_json_bytes": 16384,
        "max_source_body_bytes": 32768,
        "max_catalog_entries": 32,
        "max_catalog_bytes": 65536,
        "max_catalog_paragraphs": 64,
    }


class HostEventConfigLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.external_root = Path(self.temp_dir.name)
        self.config_path = self.external_root / "event-config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_json(self, value):
        self.config_path.write_text(
            json.dumps(value, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        return self.config_path

    def _load(self, config_path=None):
        return load_event_grounder_config(
            self.config_path if config_path is None else config_path,
            repo_root=REPO_ROOT,
        )

    def _assert_error(self, code, config_path=None):
        with self.assertRaises(HostEventConfigurationError) as caught:
            self._load(config_path)
        self.assertEqual(caught.exception.code, code)
        self.assertNotIn(str(self.config_path), str(caught.exception))
        self.assertNotIn(str(self.config_path), repr(caught.exception))
        return caught.exception

    def test_loads_exact_existing_typed_config_without_resolving_credentials(self):
        self._write_json(_document())
        with patch.object(
            ModelCredential, "resolve", side_effect=AssertionError("must not resolve")
        ) as resolve_model, patch.object(
            TavilyCredentialRef,
            "resolve",
            side_effect=AssertionError("must not resolve"),
        ) as resolve_source:
            config = self._load()

        self.assertIs(type(config), HostEventGrounderConfig)
        self.assertIs(type(config.source), TavilySourceConfig)
        self.assertIs(type(config.source.credential_ref), TavilyCredentialRef)
        self.assertIs(type(config.discovery_model), ModelRuntimeConfig)
        self.assertIs(type(config.discovery_credential), ModelCredential)
        self.assertIs(type(config.run_input_bounds), HostGrounderRunInputBounds)
        self.assertEqual(config.discovery_model.provider, "synthetic-provider")
        self.assertEqual(config.discovery_model.model, "synthetic-model")
        self.assertEqual(config.discovery_model.role, "discovery")
        self.assertEqual(config.semantic_model.provider, "synthetic-provider")
        self.assertEqual(config.semantic_model.model, "synthetic-model")
        self.assertEqual(config.semantic_model.role, "semantic")
        self.assertTrue(config.source.paygo_off_confirmed)
        self.assertTrue(config.discovery_model.remote_enabled)
        self.assertTrue(config.discovery_model.fee_authorized)
        self.assertEqual(config.source.byte_budget, 32768)
        self.assertEqual(config.source.time_budget_seconds, 30.0)
        self.assertEqual(config.source.max_search_results, 5)
        self.assertEqual(config.source.max_extract_urls, 5)
        self.assertEqual(config.max_catalog_paragraphs, 64)
        self.assertEqual(repr(config), "HostEventGrounderConfig(<redacted>)")
        resolve_model.assert_not_called()
        resolve_source.assert_not_called()

    def test_defaults_are_not_silently_supplied_and_flags_are_required(self):
        mutations = (
            (lambda doc: doc["source"].pop("time_budget_seconds")),
            (lambda doc: doc["source"].pop("max_search_results")),
            (lambda doc: doc["source"].pop("paygo_off_confirmed")),
            (lambda doc: doc["discovery_model"].pop("remote_enabled")),
            (lambda doc: doc["semantic_model"].pop("fee_authorized")),
            (lambda doc: doc["run_input_bounds"].pop("max_array_items")),
            (lambda doc: doc.pop("max_catalog_paragraphs")),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                doc = _document()
                mutate(doc)
                self._write_json(doc)
                self._assert_error("MISSING_FIELD")

    def test_explicit_optional_budget_fields_must_be_bounded_values(self):
        for field, value in (("time_budget_seconds", None), ("byte_budget", None)):
            with self.subTest(field=field):
                doc = _document()
                doc["source"][field] = value
                self._write_json(doc)
                self._assert_error("INVALID_CONFIGURATION")

    def test_rejects_unknown_and_raw_credential_fields_without_echoing_values(self):
        doc = _document()
        doc["unrecognized"] = "must not appear"
        self._write_json(doc)
        unknown = self._assert_error("UNKNOWN_FIELD")
        self.assertNotIn("unrecognized", str(unknown))

        doc = _document()
        doc["source"]["api_key"] = "SECRET_SENTINEL"
        self._write_json(doc)
        forbidden = self._assert_error("FORBIDDEN_CREDENTIAL_FIELD")
        self.assertNotIn("SECRET_SENTINEL", str(forbidden))
        self.assertNotIn("SECRET_SENTINEL", repr(forbidden))

    def test_credential_reference_requires_exactly_one_reference(self):
        doc = _document()
        doc["source"]["credential_ref"] = {
            "properties_path": "/outside/tavily.properties",
            "env_name": "TAVILY_TEST_KEY",
        }
        self._write_json(doc)
        self._assert_error("INVALID_CREDENTIAL_REFERENCE")

    def test_duplicate_keys_nan_and_overflowing_float_are_rejected(self):
        self.config_path.write_text(
            '{"schema_version":"host-event-config-v0.1",'
            '"schema_version":"host-event-config-v0.1"}',
            encoding="utf-8",
        )
        self._assert_error("DUPLICATE_KEY")

        doc = _document()
        doc["max_json_bytes"] = float("nan")
        self.config_path.write_text(
            json.dumps(doc, allow_nan=True), encoding="utf-8"
        )
        self._assert_error("NONFINITE_NUMBER")

        doc["max_json_bytes"] = 1e999
        self.config_path.write_text(
            json.dumps(doc, allow_nan=True), encoding="utf-8"
        )
        self._assert_error("NONFINITE_NUMBER")

    def test_rejects_non_utf8_and_oversized_config(self):
        self.config_path.write_bytes(b"\xff\xfe")
        self._assert_error("INVALID_UTF8")

        self.config_path.write_bytes(b" " * (_MAX_CONFIG_BYTES + 1))
        self._assert_error("CONFIG_TOO_LARGE")

    def test_rejects_internal_config_and_external_symlink_to_repository(self):
        internal = self._assert_error(
            "CONFIG_NOT_EXTERNAL", REPO_ROOT / "pyproject.toml"
        )
        self.assertNotIn(str(REPO_ROOT), str(internal))
        self._assert_error(
            "CONFIG_NOT_EXTERNAL", REPO_ROOT / "not-yet-created-event-config.json"
        )

        link = self.external_root / "repo-config-link.json"
        try:
            os.symlink(REPO_ROOT / "pyproject.toml", link)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is unavailable")
        linked = self._assert_error("CONFIG_NOT_EXTERNAL", link)
        self.assertNotIn(str(REPO_ROOT), repr(linked))

    def test_error_codes_are_closed_and_messages_never_include_paths(self):
        self.config_path.write_text("not json", encoding="utf-8")
        error = self._assert_error("INVALID_JSON")
        self.assertEqual(str(error), "INVALID_JSON")
        self.assertEqual(
            repr(error), "HostEventConfigurationError(code='INVALID_JSON')"
        )
        self.assertEqual(
            HostEventConfigurationError("/sensitive/path").code,
            "INVALID_CONFIGURATION",
        )
        self.assertEqual(
            config_module.__all__,
            (
                "HOST_EVENT_CONFIG_SCHEMA_VERSION",
                "HostEventConfigurationError",
                "load_event_grounder_config",
            ),
        )

    def test_rejects_unsupported_schema_version(self):
        doc = _document()
        doc["schema_version"] = "host-event-config-v0.2"
        self._write_json(doc)
        self._assert_error("UNSUPPORTED_SCHEMA_VERSION")


if __name__ == "__main__":
    unittest.main()
