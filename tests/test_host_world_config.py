"""Offline tests for the explicit external World configuration boundary."""

import datetime
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

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
        config = self.load(json.dumps(_document()))

        def unexpected_call(*_args, **_kwargs):
            self.fail("configuration/factory construction must remain lazy")

        runner = create_world_runner(
            config, repo_root=ROOT,
            market_bridge=FutuMarketBridge(quote_context_factory=unexpected_call),
            source_transport=unexpected_call,
            discovery_transport=unexpected_call,
            semantic_transport=unexpected_call,
            stage_runner=unexpected_call,
        )
        self.assertTrue(callable(runner))
