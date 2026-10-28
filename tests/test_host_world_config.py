"""Offline tests for the explicit external World configuration boundary."""

import datetime
import json
import tempfile
import unittest
from dataclasses import fields, replace
from pathlib import Path
from unittest.mock import patch

from convexity_hunter.host_event import _safe_configuration_snapshot
from convexity_hunter.host_world_config import (
    APPROVED_SKILL_PATH,
    APPROVED_SKILL_PYTHON,
    APPROVED_SKILL_SHA256,
    APPROVED_SKILL_VERSION,
    HOST_WORLD_CONFIG_SCHEMA_VERSION,
    HostWorldConfigurationError,
    load_world_config,
)
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority
from tests.test_host_event import _config

ROOT = Path(__file__).resolve().parents[1]


def _document():
    return {
        "schema_version": HOST_WORLD_CONFIG_SCHEMA_VERSION,
        "skill": {
            "skill_pin": {
                "path": str(APPROVED_SKILL_PATH),
                "version": APPROVED_SKILL_VERSION,
                "content_sha256": APPROVED_SKILL_SHA256,
            },
            "python_executable": str(APPROVED_SKILL_PYTHON),
            "source_allowlist": ["hackernews"],
            "permitted_source_envs": [],
            "stage_timeout_seconds": 10.0,
            "request_stage_budget": 3,
            "max_stdout_bytes": 100_000,
            "max_stderr_bytes": 10_000,
            "days": 7,
            "current_only": True,
            "no_as_of": True,
            "handoff_ttl_seconds": 3600,
            "max_handoff_bytes": 200_000,
            "final_output_path": None,
        },
        "bounds": {
            "max_submissions": 1,
            "max_hypotheses": 4,
            "max_browser_rows": 400,
            "max_cases": 200,
            "quote_timeout_seconds": 10.0,
        },
    }


def _document_v0_2():
    document = _document()
    document["schema_version"] = "host-world-config-v0.2"
    document["grounder_budgets"] = {
        "source_requests": 7,
        "source_credits": 8,
        "discovery_requests": 9,
        "semantic_requests": 10,
    }
    return document


def _document_v0_3():
    document = _document_v0_2()
    document["schema_version"] = "host-world-config-v0.3"
    document["catalog_scan_paragraphs"] = 1024
    return document


def _document_v0_4(catalog_entries=128):
    document = _document_v0_3()
    document["schema_version"] = "host-world-config-v0.4"
    document["catalog_entries"] = catalog_entries
    return document


class HostWorldConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "world.json"
        self.grounder = _config()

    def load(self, text):
        self.path.write_text(text, encoding="utf-8")
        return load_world_config(
            self.path, repo_root=ROOT, grounder_config=self.grounder,
            evaluation_date=datetime.date(2030, 1, 1),
            maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
        )

    def test_complete_configuration_preserves_shared_event_inputs_and_explicit_caps(self):
        config = self.load(json.dumps(_document()))
        self.assertIs(config.grounder, self.grounder)
        self.assertEqual(config.skill.source_allowlist, ("hackernews",))
        self.assertEqual(config.skill.permitted_source_envs, ())
        self.assertEqual(config.skill.skill_pin.version, "3.21.1")
        self.assertEqual(config.bounds.max_cases, 200)
        self.assertEqual(config.evaluation_date, datetime.date(2030, 1, 1))
        self.assertEqual(repr(config), "HostWorldConfig(<redacted>)")

    def test_v0_2_applies_only_world_grounder_budgets(self):
        document = _document_v0_2()
        with patch(
            "convexity_hunter.host_sources.TavilyCredentialRef.resolve",
            side_effect=AssertionError("must not resolve credentials while loading"),
        ), patch(
            "convexity_hunter.host_model.ModelCredential.resolve",
            side_effect=AssertionError("must not resolve credentials while loading"),
        ):
            config = self.load(json.dumps(document))

        self.assertEqual(HOST_WORLD_CONFIG_SCHEMA_VERSION, "host-world-config-v0.1")
        self.assertIsNot(config.grounder, self.grounder)
        self.assertEqual(
            (
                config.grounder.source.request_budget,
                config.grounder.source.credit_budget,
                config.grounder.discovery_model.request_budget,
                config.grounder.semantic_model.request_budget,
            ),
            (7, 8, 9, 10),
        )
        for config_part, event_part, changed_fields in (
            (
                config.grounder.source,
                self.grounder.source,
                {"request_budget", "credit_budget"},
            ),
            (
                config.grounder.discovery_model,
                self.grounder.discovery_model,
                {"request_budget"},
            ),
            (
                config.grounder.semantic_model,
                self.grounder.semantic_model,
                {"request_budget"},
            ),
        ):
            for descriptor in fields(event_part):
                if descriptor.name not in changed_fields:
                    self.assertEqual(
                        getattr(config_part, descriptor.name),
                        getattr(event_part, descriptor.name),
                        descriptor.name,
                    )
        for descriptor in fields(self.grounder):
            if descriptor.name not in {
                "source", "discovery_model", "semantic_model"
            }:
                self.assertIs(
                    getattr(config.grounder, descriptor.name),
                    getattr(self.grounder, descriptor.name),
                    descriptor.name,
                )
        self.assertIs(
            config.grounder.source.credential_ref,
            self.grounder.source.credential_ref,
        )
        self.assertIs(
            config.grounder.discovery_credential,
            self.grounder.discovery_credential,
        )
        self.assertIs(
            config.grounder.semantic_credential,
            self.grounder.semantic_credential,
        )
        self.assertEqual(
            (
                self.grounder.source.request_budget,
                self.grounder.source.credit_budget,
                self.grounder.discovery_model.request_budget,
                self.grounder.semantic_model.request_budget,
            ),
            (2, 2, 1, 1),
        )

    def test_v0_3_applies_only_world_budgets_and_detached_scan_limit(self):
        document = _document_v0_3()
        with patch(
            "convexity_hunter.host_sources.TavilyCredentialRef.resolve",
            side_effect=AssertionError("must not resolve credentials while loading"),
        ), patch(
            "convexity_hunter.host_model.ModelCredential.resolve",
            side_effect=AssertionError("must not resolve credentials while loading"),
        ):
            config = self.load(json.dumps(document))

        self.assertEqual(HOST_WORLD_CONFIG_SCHEMA_VERSION, "host-world-config-v0.1")
        self.assertIsNot(config.grounder, self.grounder)
        self.assertEqual(
            (
                config.grounder.source.request_budget,
                config.grounder.source.credit_budget,
                config.grounder.discovery_model.request_budget,
                config.grounder.semantic_model.request_budget,
                config.grounder.max_catalog_paragraphs,
            ),
            (7, 8, 9, 10, 1024),
        )
        self.assertEqual(self.grounder.max_catalog_paragraphs, 128)
        self.assertIs(
            config.grounder.source.credential_ref,
            self.grounder.source.credential_ref,
        )
        self.assertIs(
            config.grounder.discovery_credential,
            self.grounder.discovery_credential,
        )
        self.assertIs(
            config.grounder.semantic_credential,
            self.grounder.semantic_credential,
        )
        for config_part, event_part, changed_fields in (
            (
                config.grounder.source,
                self.grounder.source,
                {"request_budget", "credit_budget"},
            ),
            (
                config.grounder.discovery_model,
                self.grounder.discovery_model,
                {"request_budget"},
            ),
            (
                config.grounder.semantic_model,
                self.grounder.semantic_model,
                {"request_budget"},
            ),
        ):
            for descriptor in fields(event_part):
                if descriptor.name not in changed_fields:
                    self.assertEqual(
                        getattr(config_part, descriptor.name),
                        getattr(event_part, descriptor.name),
                        descriptor.name,
                    )
        for descriptor in fields(self.grounder):
            if descriptor.name not in {
                "source", "discovery_model", "semantic_model", "max_catalog_paragraphs"
            }:
                self.assertIs(
                    getattr(config.grounder, descriptor.name),
                    getattr(self.grounder, descriptor.name),
                    descriptor.name,
                )
        self.assertEqual(
            (
                self.grounder.source.request_budget,
                self.grounder.source.credit_budget,
                self.grounder.discovery_model.request_budget,
                self.grounder.semantic_model.request_budget,
            ),
            (2, 2, 1, 1),
        )

    def test_v0_2_requires_exact_positive_integer_grounder_budgets(self):
        invalid = []
        for field in (
            "source_requests",
            "source_credits",
            "discovery_requests",
            "semantic_requests",
        ):
            for value in (True, 0, -1, 1.5, "1", None):
                document = _document_v0_2()
                document["grounder_budgets"][field] = value
                invalid.append((
                    "invalid {}={!r}".format(field, value),
                    document,
                    "INVALID_CONFIGURATION",
                ))

        document = _document_v0_2()
        document.pop("grounder_budgets")
        invalid.append(("missing top-level budgets", document, "MISSING_FIELD"))
        document = _document_v0_2()
        document["extra"] = "reject"
        invalid.append(("extra top-level field", document, "UNKNOWN_FIELD"))
        document = _document_v0_2()
        document["grounder_budgets"].pop("source_requests")
        invalid.append(("missing budget field", document, "MISSING_FIELD"))
        document = _document_v0_2()
        document["grounder_budgets"]["extra"] = 1
        invalid.append(("extra budget field", document, "UNKNOWN_FIELD"))
        document = _document_v0_2()
        document["grounder_budgets"] = []
        invalid.append(("non-object budgets", document, "INVALID_CONFIGURATION"))
        document = _document()
        document["schema_version"] = "host-world-config-v0.5"
        invalid.append(("unknown version", document, "UNSUPPORTED_SCHEMA_VERSION"))

        for label, document, code in invalid:
            with self.subTest(label=label):
                with self.assertRaises(HostWorldConfigurationError) as raised:
                    self.load(json.dumps(document))
                self.assertEqual(raised.exception.code, code)

    def test_v0_3_requires_exact_shape_and_bounded_non_boolean_scan_limit(self):
        invalid = []
        for value in (True, False, 0, -1, 1.0, 1024.0, "1", None, 1025):
            document = _document_v0_3()
            document["catalog_scan_paragraphs"] = value
            invalid.append(("invalid scan limit {!r}".format(value), document, "INVALID_CONFIGURATION"))

        document = _document_v0_3()
        document.pop("catalog_scan_paragraphs")
        invalid.append(("missing scan limit", document, "MISSING_FIELD"))
        document = _document_v0_3()
        document["extra"] = "reject"
        invalid.append(("extra root field", document, "UNKNOWN_FIELD"))
        document = _document_v0_3()
        document.pop("grounder_budgets")
        invalid.append(("missing v0.2 root field", document, "MISSING_FIELD"))
        document = _document_v0_3()
        document["grounder_budgets"].pop("source_requests")
        invalid.append(("missing budget field", document, "MISSING_FIELD"))
        document = _document_v0_3()
        document["grounder_budgets"]["extra"] = 1
        invalid.append(("extra budget field", document, "UNKNOWN_FIELD"))
        document = _document_v0_3()
        document["grounder_budgets"] = []
        invalid.append(("non-object budgets", document, "INVALID_CONFIGURATION"))
        document = _document_v0_3()
        document["grounder_budgets"]["source_requests"] = True
        invalid.append(("boolean budget", document, "INVALID_CONFIGURATION"))
        document = _document_v0_3()
        document["api_key"] = "PRIVATE_SENTINEL"
        invalid.append(("credential field", document, "FORBIDDEN_CREDENTIAL_FIELD"))

        for label, document, code in invalid:
            with self.subTest(label=label):
                with self.assertRaises(HostWorldConfigurationError) as raised:
                    self.load(json.dumps(document))
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn("PRIVATE_SENTINEL", str(raised.exception))

        document = _document_v0_3()
        document["catalog_scan_paragraphs"] = 1
        self.assertEqual(self.load(json.dumps(document)).grounder.max_catalog_paragraphs, 1)

    def test_v0_4_applies_only_world_entry_and_array_overrides(self):
        original = replace(
            self.grounder,
            run_input_bounds=replace(
                self.grounder.run_input_bounds, max_array_items=200
            ),
        )
        self.grounder = original
        with patch(
            "convexity_hunter.host_sources.TavilyCredentialRef.resolve",
            side_effect=AssertionError("must not resolve credentials while loading"),
        ), patch(
            "convexity_hunter.host_model.ModelCredential.resolve",
            side_effect=AssertionError("must not resolve credentials while loading"),
        ):
            config = self.load(json.dumps(_document_v0_4(128)))

        self.assertEqual(HOST_WORLD_CONFIG_SCHEMA_VERSION, "host-world-config-v0.1")
        self.assertIsNot(config.grounder, original)
        self.assertEqual(
            (
                config.grounder.source.request_budget,
                config.grounder.source.credit_budget,
                config.grounder.discovery_model.request_budget,
                config.grounder.semantic_model.request_budget,
                config.grounder.max_catalog_paragraphs,
                config.grounder.max_catalog_entries,
                config.grounder.run_input_bounds.max_array_items,
            ),
            (7, 8, 9, 10, 1024, 128, 200),
        )
        self.assertIsNot(config.grounder.run_input_bounds, original.run_input_bounds)
        self.assertEqual(
            (
                config.grounder.run_input_bounds.max_run_input_bytes,
                config.grounder.run_input_bounds.max_string_bytes,
            ),
            (
                original.run_input_bounds.max_run_input_bytes,
                original.run_input_bounds.max_string_bytes,
            ),
        )
        changed_fields = {
            "source", "discovery_model", "semantic_model", "run_input_bounds",
            "max_catalog_entries", "max_catalog_paragraphs",
        }
        for descriptor in fields(original):
            if descriptor.name not in changed_fields:
                self.assertIs(
                    getattr(config.grounder, descriptor.name),
                    getattr(original, descriptor.name),
                    descriptor.name,
                )
        self.assertIs(config.grounder.source.credential_ref, original.source.credential_ref)
        self.assertIs(config.grounder.discovery_credential, original.discovery_credential)
        self.assertIs(config.grounder.semantic_credential, original.semantic_credential)
        self.assertEqual(original.max_catalog_entries, 64)
        self.assertEqual(original.run_input_bounds.max_array_items, 200)

        snapshot = json.loads(_safe_configuration_snapshot(
            config.grounder,
            source_search_policy_version="host-event-source-snapshot-v0.1",
        ))
        limits = snapshot["sources"][0]["grounder_limits"]
        self.assertEqual(
            set(limits),
            {
                "run_input_bounds", "max_json_bytes", "max_source_body_bytes",
                "max_catalog_entries", "max_catalog_bytes", "max_catalog_paragraphs",
            },
        )
        self.assertEqual(limits["max_catalog_entries"], 128)
        self.assertEqual(limits["run_input_bounds"]["max_array_items"], 200)
        self.assertEqual(limits["max_catalog_bytes"], original.max_catalog_bytes)

        self.grounder = replace(
            original,
            run_input_bounds=replace(
                original.run_input_bounds, max_array_items=10
            ),
        )
        upper_bound = self.load(json.dumps(_document_v0_4(256)))
        self.assertEqual(upper_bound.grounder.max_catalog_entries, 256)
        self.assertEqual(upper_bound.grounder.run_input_bounds.max_array_items, 256)

    def test_v0_4_requires_exact_shape_and_bounded_non_boolean_catalog_entries(self):
        invalid = []
        for value in (True, False, 0, -1, 1.0, 256.0, "1", None, 257):
            document = _document_v0_4()
            document["catalog_entries"] = value
            invalid.append(("invalid catalog entries {!r}".format(value), document, "INVALID_CONFIGURATION"))

        document = _document_v0_3()
        document["schema_version"] = "host-world-config-v0.4"
        invalid.append(("missing catalog entries", document, "MISSING_FIELD"))
        document = _document_v0_4()
        document["extra"] = "reject"
        invalid.append(("extra root field", document, "UNKNOWN_FIELD"))
        document = _document_v0_4()
        document.pop("catalog_scan_paragraphs")
        invalid.append(("missing v0.3 root field", document, "MISSING_FIELD"))

        for label, document, code in invalid:
            with self.subTest(label=label):
                with self.assertRaises(HostWorldConfigurationError) as raised:
                    self.load(json.dumps(document))
                self.assertEqual(raised.exception.code, code)

        for value in (1, 256):
            with self.subTest(valid_catalog_entries=value):
                config = self.load(json.dumps(_document_v0_4(value)))
                self.assertEqual(config.grounder.max_catalog_entries, value)
                self.assertEqual(
                    config.grounder.run_input_bounds.max_array_items,
                    max(self.grounder.run_input_bounds.max_array_items, value),
                )

    def test_v0_4_rejects_original_array_capacity_above_256(self):
        self.grounder = replace(
            self.grounder,
            run_input_bounds=replace(
                self.grounder.run_input_bounds, max_array_items=257
            ),
        )
        with self.assertRaises(HostWorldConfigurationError) as raised:
            self.load(json.dumps(_document_v0_4(1)))
        self.assertEqual(raised.exception.code, "INVALID_CONFIGURATION")

    def test_strict_json_and_external_byte_cap_fail_closed(self):
        raw = json.dumps(_document())
        for text, code in (
            (raw.replace('"max_cases": 200', '"max_cases": 200, "max_cases": 1'), "DUPLICATE_KEY"),
            (raw.replace('"max_cases": 200', '"max_cases": NaN'), "NONFINITE_NUMBER"),
            (raw.replace('"max_cases": 200', '"max_cases": 1e309'), "NONFINITE_NUMBER"),
            (raw.replace('"bounds":', '"unknown": 1, "bounds":'), "UNKNOWN_FIELD"),
            (raw.replace('"bounds":', '"api_key": "PRIVATE_SENTINEL", "bounds":'), "FORBIDDEN_CREDENTIAL_FIELD"),
            (" " * 65_537, "CONFIG_TOO_LARGE"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(HostWorldConfigurationError) as raised:
                    self.load(text)
                self.assertEqual(raised.exception.code, code)
                self.assertNotIn("PRIVATE_SENTINEL", str(raised.exception))

        self.path.unlink()
        self.path.symlink_to(ROOT / "AGENTS.md")
        with self.assertRaises(HostWorldConfigurationError) as raised:
            load_world_config(
                self.path, repo_root=ROOT, grounder_config=self.grounder,
                evaluation_date=datetime.date(2030, 1, 1),
                maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
            )
        self.assertEqual(raised.exception.code, "CONFIG_NOT_EXTERNAL")

    def test_pin_interpreter_source_grants_and_persistence_are_closed(self):
        changes = (
            ("pin", "version", "new-version"),
            ("pin", "path", "/tmp/arbitrary-skill"),
            ("pin", "content_sha256", "0" * 64),
            ("skill", "python_executable", "/bin/sh"),
            ("skill", "permitted_source_envs", ["OPENAI_API_KEY"]),
            ("skill", "final_output_path", "/tmp/native.json"),
            ("skill", "source_allowlist", "hackernews"),
            ("bounds", "max_cases", -1),
        )
        for section, field, value in changes:
            document = _document()
            target = document["skill"]["skill_pin"] if section == "pin" else document[section]
            target[field] = value
            with self.subTest(section=section, field=field):
                with self.assertRaises(HostWorldConfigurationError):
                    self.load(json.dumps(document))

    def test_limits_are_required_and_zero_capacity_is_preserved(self):
        document = _document()
        del document["skill"]["stage_timeout_seconds"]
        with self.assertRaises(HostWorldConfigurationError) as raised:
            self.load(json.dumps(document))
        self.assertEqual(raised.exception.code, "MISSING_FIELD")
        document = _document()
        document["bounds"]["max_cases"] = 0
        self.assertEqual(self.load(json.dumps(document)).bounds.max_cases, 0)

    def test_valid_config_constructs_actual_world_factory_without_calls(self):
        from convexity_hunter.core_futu import FutuMarketBridge
        from convexity_hunter.host_world import create_world_runner

        self.grounder = replace(
            self.grounder,
            discovery_model=replace(self.grounder.discovery_model, request_budget=2),
            semantic_model=replace(self.grounder.semantic_model, request_budget=2),
        )
        def unexpected_call(*_args, **_kwargs):
            self.fail("configuration/factory construction must remain lazy")

        for document in (
            _document(), _document_v0_2(), _document_v0_3(), _document_v0_4()
        ):
            with self.subTest(schema_version=document["schema_version"]):
                config = self.load(json.dumps(document))
                runner = create_world_runner(
                    config, repo_root=ROOT,
                    market_bridge=FutuMarketBridge(quote_context_factory=unexpected_call),
                    source_transport=unexpected_call,
                    discovery_transport=unexpected_call,
                    semantic_transport=unexpected_call,
                    stage_runner=unexpected_call,
                )
                self.assertTrue(callable(runner))
