"""Focused offline tests for the bounded native last30days controller."""

import datetime
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter._host_skill_launcher import (  # noqa: E402
    HostSkillLaunchError,
    StageExecution,
    StageRequest,
    build_child_environment,
    loader_guard_source,
    run_stage,
)
import convexity_hunter._host_skill_launcher as launcher  # noqa: E402
from convexity_hunter.host_skill import (  # noqa: E402
    HostSkillConfig,
    HostSkillError,
    Last30DaysSkillPin,
    compute_skill_content_sha256,
    run_last30days_discovery,
)


SKILL_DIR = pathlib.Path("/Users/erwinlee/.codex/skills/last30days")
NOW = datetime.datetime(2026, 9, 27, 12, 0, tzinfo=datetime.timezone.utc)
_DIGEST = hashlib.sha256(b"synthetic-child-output").hexdigest()


def _native_source_item(source, item_id, title):
    return {
        "item_id": item_id,
        "source": source,
        "title": title,
        "body": "Native retained source body.",
        "url": "https://example.test/" + item_id,
        "published_at": "2026-09-26T12:00:00+00:00",
        "date_confidence": "high",
        "engagement": {"score": 10},
        "relevance_hint": 0.9,
        "why_relevant": "Native source evidence.",
        "snippet": "Native source snippet.",
        "metadata": {},
        "freshness": 1.0,
        "engagement_score": 10.0,
        "source_quality": 0.8,
    }


def _native_nomination(name, source, item_id):
    return {
        "name": name,
        "seed_score": 0.8,
        "summary": "Native nomination summary.",
        "junk_shape": False,
        "items": [_native_source_item(source, item_id, name)],
    }


def _native_source_status(source, count=1):
    return {
        "source": source,
        "state": "ok",
        "items_returned": count,
        "attempted": True,
        "at": "2026-09-27T12:00:00+00:00",
    }


def native_bundle(generated_at):
    return {
        "schema_version": "1.0",
        "kind": "discovery-nominations",
        "bundle_id": "bundle-native-golden-1",
        "generated_at": generated_at,
        "from_date": "2026-09-20",
        "to_date": "2026-09-27",
        "domain": "synthetic domain",
        "tier": "deep",
        "mock": False,
        "source_status": {
            "reddit": _native_source_status("reddit"),
            "x": _native_source_status("x"),
        },
        "context": {
            "enrichment_source_boundary": ["reddit", "x"],
            "requested_sources": ["reddit", "x"],
            "lookback_days": 7,
        },
        "nominations": [
            {
                "id": "n1",
                "cluster_id": "cluster-1",
                "heuristic_name": "Native seed one",
                "heuristic_junk": False,
                "sources": ["reddit"],
                "engagement_by_source": {"reddit": {"score": 10}},
                "nomination": _native_nomination(
                    "Native seed one", "reddit", "reddit:n1"
                ),
            },
            {
                "id": "n2",
                "cluster_id": "cluster-2",
                "heuristic_name": "Native seed two",
                "heuristic_junk": False,
                "sources": ["x"],
                "engagement_by_source": {"x": {"score": 9}},
                "nomination": _native_nomination("Native seed two", "x", "x:n2"),
            },
        ],
    }


def native_report(generated_at):
    return {
        "domain": "synthetic domain",
        "range_from": "2026-09-20",
        "range_to": "2026-09-27",
        "generated_at": generated_at,
        "plan": {
            "domain": "synthetic domain",
            "category": "trending",
            "subreddits": [],
            "sources": ["reddit", "x"],
        },
        "topics": [
            {
                "rank": 1,
                "name": "Model topic two",
                "why_spiking": "Native listing evidence.",
                "momentum": "building",
                "velocity_score": 0.9,
                "sources": ["x"],
                "engagement_by_source": {"x": {"score": 9}},
                "command": "last30days topic two",
                "evidence_urls": ["https://example.test/x:n2"],
                "top_comment": "Native comment.",
                "corroboration_count": 1,
                "podcast_angle": "Native provisional podcast angle.",
                "x_article_angle": "Native provisional article angle.",
                "previously_surfaced_count": 0,
                "covered": False,
            },
            {
                "rank": 2,
                "name": "Model topic one",
                "why_spiking": "Native listing evidence.",
                "momentum": "new-this-week",
                "velocity_score": 0.8,
                "sources": ["reddit"],
                "engagement_by_source": {"reddit": {"score": 10}},
                "command": "last30days topic one",
                "evidence_urls": ["https://example.test/reddit:n1"],
                "top_comment": "Native comment.",
                "corroboration_count": 1,
                "podcast_angle": "Native provisional podcast angle one.",
                "x_article_angle": "Native provisional article angle one.",
                "previously_surfaced_count": 0,
                "covered": False,
            },
        ],
        "source_status": {
            "reddit": _native_source_status("reddit"),
            "x": _native_source_status("x"),
        },
        "warnings": [],
        "outcome": "ok",
    }


def native_pending(generated_at):
    return {
        "schema_version": "1.0",
        "kind": "discovery-pending",
        "bundle_id": "bundle-native-golden-1",
        "generated_at": generated_at,
        "run_ref": "discover:synthetic-domain:2026-09-27T12:00:00+00:00",
        "mock": False,
        "report": native_report(generated_at),
        "angle_inputs": {
            "n2": {
                "name": "Model topic two",
                "titles": "Native title two",
                "top_comment": "Native comment two",
                "engagement": "10 interactions",
            },
            "n1": {
                "name": "Model topic one",
                "titles": "Native title one",
                "top_comment": "Native comment one",
                "engagement": "20 interactions",
            },
        },
    }


def execution(returncode=0):
    return StageExecution(
        returncode=returncode,
        stdout_bytes=24,
        stderr_bytes=0,
        stdout_sha256=_DIGEST,
        stderr_sha256=hashlib.sha256(b"").hexdigest(),
    )


class SyntheticSkillRunner:
    """Writes pinned native protocol fixtures; it never starts the skill."""

    def __init__(
        self,
        *,
        generated_at=None,
        empty=False,
        exit_code=None,
        bundle_overrides=None,
        pending_overrides=None,
        omit_final=False,
    ):
        self.generated_at = generated_at or NOW.isoformat()
        self.empty = empty
        self.exit_code = exit_code
        self.bundle_overrides = bundle_overrides or {}
        self.pending_overrides = pending_overrides or {}
        self.omit_final = omit_final
        self.requests = []
        self.judgments = None
        self.angles = None

    def __call__(self, request):
        self.requests.append(request)
        if self.exit_code is not None and request.phase == "nominate":
            return execution(self.exit_code)
        if request.phase == "nominate":
            if self.empty:
                return execution()
            payload = native_bundle(self.generated_at)
            payload.update(self.bundle_overrides)
            (request.cwd / "discover-nominations.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
        elif request.phase == "resume":
            judgment_path = pathlib.Path(
                request.argv[request.argv.index("--judgments") + 1]
            )
            self.judgments = json.loads(judgment_path.read_text(encoding="utf-8"))
            payload = native_pending(self.generated_at)
            payload.update(self.pending_overrides)
            (request.cwd / "discover-pending.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
        elif request.phase == "finalize":
            angle_path = pathlib.Path(request.argv[request.argv.index("--angles") + 1])
            self.angles = json.loads(angle_path.read_text(encoding="utf-8"))
            if not self.omit_final:
                output_path = pathlib.Path(request.argv[request.argv.index("--output") + 1])
                output_path.write_text(json.dumps(native_report(self.generated_at)), encoding="utf-8")
        return execution()


class HostSkillTests(unittest.TestCase):
    def setUp(self):
        self.pin = Last30DaysSkillPin(
            path=SKILL_DIR,
            version="3.21.1",
            content_sha256=compute_skill_content_sha256(SKILL_DIR),
        )

    def config(self, **overrides):
        values = {
            "skill_pin": self.pin,
            "python_executable": sys.executable,
            "source_allowlist": ("reddit", "hackernews", "digg", "x"),
            "permitted_source_envs": ("AUTH_TOKEN", "CT0"),
            "stage_timeout_seconds": 0.5,
            "request_stage_budget": 3,
            "max_stdout_bytes": 2048,
            "max_stderr_bytes": 2048,
            "max_handoff_bytes": 128 * 1024,
        }
        values.update(overrides)
        return HostSkillConfig(**values)

    def execute(self, runner, callback, **config_overrides):
        return run_last30days_discovery(
            self.config(**config_overrides),
            "synthetic domain",
            callback,
            stage_runner=runner,
            clock=lambda: NOW,
        )

    def test_three_legs_use_same_dir_fixed_current_window_and_full_ids(self):
        runner = SyntheticSkillRunner()
        callback_phases = []

        def callback(phase, items):
            callback_phases.append((phase, items))
            if phase == "judgments":
                self.assertEqual([item.id for item in items], ["n1", "n2"])
                self.assertEqual(items[0].payload["nomination"]["items"][0]["title"], "Native seed one")
                # Return reverse order to prove the adapter writes protocol
                # order and does not use native score/rank fields.
                return {
                    "judgments": [
                        {"id": "n2", "name": "Topic two", "junk": True, "worthiness": 3},
                        {"id": "n1", "name": "Topic one", "junk": False, "worthiness": 97},
                    ]
                }
            self.assertEqual(phase, "angles")
            self.assertEqual([item.id for item in items], ["n2", "n1"])
            return {
                "angles": [
                    {"id": "n1", "podcast": "podcast one", "x_article": "article one"},
                    {"id": "n2", "podcast": "podcast two", "x_article": "article two"},
                ]
            }

        result = self.execute(runner, callback)

        self.assertEqual(result.status, "complete")
        self.assertEqual(result.bundle_id, "bundle-native-golden-1")
        self.assertEqual(result.survivor_ids, ("n2", "n1"))
        self.assertEqual([receipt.phase for receipt in result.stages], ["nominate", "resume", "finalize"])
        self.assertEqual([request.cwd for request in runner.requests], [request.cwd for request in runner.requests[:1]] * 3)
        save_dirs = []
        for request in runner.requests:
            self.assertNotIn("--as-of", request.argv)
            self.assertNotIn("--mock", request.argv)
            self.assertEqual(request.argv[request.argv.index("--days") + 1], "7")
            self.assertEqual(request.argv[request.argv.index("--search") + 1], "reddit,hackernews,digg,x")
            save_dirs.append(request.argv[request.argv.index("--save-dir") + 1])
        self.assertEqual(runner.requests[-1].argv[runner.requests[-1].argv.index("--emit") + 1], "json")
        self.assertEqual(runner.requests[-1].argv[runner.requests[-1].argv.index("--json-profile") + 1], "raw")
        self.assertEqual(len(set(save_dirs)), 1)
        self.assertEqual(runner.judgments["judgments"][0]["id"], "n1")
        self.assertEqual(runner.angles["angles"][0]["id"], "n2")
        self.assertEqual(callback_phases[0][0], "judgments")
        self.assertEqual(callback_phases[1][0], "angles")
        self.assertIsNotNone(result.provider_native)
        self.assertTrue(result.provider_native.native_editorial_provisional)
        self.assertEqual(
            json.loads(result.provider_native.raw_json)["source_status"]["reddit"]["state"],
            "ok",
        )

    def test_empty_nomination_sweep_is_valid_and_does_not_call_model_or_retry(self):
        runner = SyntheticSkillRunner(empty=True)

        def unexpected_model(_phase, _items):
            raise AssertionError("empty discovery must stop before model callback")

        result = self.execute(runner, unexpected_model)
        self.assertEqual(result.status, "empty")
        self.assertEqual(len(runner.requests), 1)
        self.assertEqual(result.remaining_request_budget, 2)

    def test_exit_two_is_typed_and_has_no_fallback(self):
        runner = SyntheticSkillRunner(exit_code=2)
        with self.assertRaises(HostSkillError) as context:
            self.execute(runner, lambda _phase, _items: [])
        self.assertEqual(context.exception.code, "SKILL_CONTRACT_FAILED")
        self.assertEqual(context.exception.exit_code, 2)
        self.assertEqual(context.exception.phase, "nominate")
        self.assertEqual(len(runner.requests), 1)

    def test_stale_bundle_fails_before_model_and_never_refetches(self):
        stale = (NOW - datetime.timedelta(seconds=3601)).isoformat()
        runner = SyntheticSkillRunner(generated_at=stale)
        called = []
        with self.assertRaises(HostSkillError) as context:
            self.execute(runner, lambda phase, _items: called.append(phase))
        self.assertEqual(context.exception.code, "BUNDLE_STALE")
        self.assertEqual(called, [])
        self.assertEqual(len(runner.requests), 1)

    def test_bundle_and_pending_use_pinned_native_envelopes(self):
        bad_bundle = SyntheticSkillRunner(
            bundle_overrides={"schema_version": "0.9"}
        )
        with self.assertRaises(HostSkillError) as context:
            self.execute(bad_bundle, lambda _phase, _items: [])
        self.assertEqual(context.exception.code, "BUNDLE_MALFORMED")
        self.assertEqual(len(bad_bundle.requests), 1)

        bad_pending = SyntheticSkillRunner(
            pending_overrides={"run_ref": ""}
        )

        def judgments_only(phase, items):
            self.assertEqual(phase, "judgments")
            return [
                {"id": item.id, "name": item.id, "junk": False, "worthiness": 50}
                for item in items
            ]

        with self.assertRaises(HostSkillError) as context:
            self.execute(bad_pending, judgments_only)
        self.assertEqual(context.exception.code, "PENDING_MALFORMED")
        self.assertEqual(len(bad_pending.requests), 2)

    def test_model_must_cover_exact_judgment_ids_and_native_types(self):
        runner = SyntheticSkillRunner()

        def bad_model(phase, _items):
            self.assertEqual(phase, "judgments")
            return {"judgments": [{"id": "n1", "name": "one", "junk": "false", "worthiness": 50}]}

        with self.assertRaises(HostSkillError) as context:
            self.execute(runner, bad_model)
        self.assertEqual(context.exception.code, "MODEL_OUTPUT_INVALID")
        self.assertEqual(len(runner.requests), 1)

    def test_model_angles_are_complete_and_capped(self):
        runner = SyntheticSkillRunner()

        def bad_angles(phase, _items):
            if phase == "judgments":
                return [
                    {"id": "n1", "name": "one", "junk": False, "worthiness": 1},
                    {"id": "n2", "name": "two", "junk": False, "worthiness": 2},
                ]
            return [
                {"id": "n1", "podcast": "x" * 201, "x_article": "ok"},
                {"id": "n2", "podcast": "ok", "x_article": "ok"},
            ]

        with self.assertRaises(HostSkillError) as context:
            self.execute(runner, bad_angles)
        self.assertEqual(context.exception.code, "MODEL_OUTPUT_INVALID")
        self.assertEqual(len(runner.requests), 2)

    def test_final_native_json_is_bounded_and_can_be_persisted(self):
        output_dir = pathlib.Path(tempfile.mkdtemp(prefix="host-skill-final-"))
        self.addCleanup(shutil.rmtree, str(output_dir), True)
        final_path = output_dir / "native-final.json"
        runner = SyntheticSkillRunner()

        def callback(phase, items):
            if phase == "judgments":
                return [
                    {"id": item.id, "name": item.id, "junk": False, "worthiness": 50}
                    for item in items
                ]
            return [
                {"id": item.id, "podcast": "podcast", "x_article": "article"}
                for item in items
            ]

        result = self.execute(runner, callback, final_output_path=final_path)
        self.assertTrue(final_path.is_file())
        persisted = json.loads(final_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["domain"], "synthetic domain")
        self.assertEqual(persisted["topics"][0]["sources"], ["x"])
        self.assertEqual(result.provider_native.persisted_path, final_path)
        self.assertEqual(result.provider_native.raw_json, final_path.read_bytes())

    def test_missing_final_native_output_is_typed_and_not_replaced_by_metadata(self):
        runner = SyntheticSkillRunner(omit_final=True)

        def callback(phase, items):
            if phase == "judgments":
                return [
                    {"id": item.id, "name": item.id, "junk": False, "worthiness": 50}
                    for item in items
                ]
            return [
                {"id": item.id, "podcast": "podcast", "x_article": "article"}
                for item in items
            ]

        with self.assertRaises(HostSkillError) as context:
            self.execute(runner, callback)
        self.assertEqual(context.exception.code, "FINAL_OUTPUT_UNREADABLE")
        self.assertEqual(context.exception.phase, "finalize")

    def test_pin_mismatch_fails_before_any_stage(self):
        runner = SyntheticSkillRunner()
        bad_pin = Last30DaysSkillPin(
            path=SKILL_DIR,
            version="3.21.0",
            content_sha256=self.pin.content_sha256,
        )
        with self.assertRaises(HostSkillError) as context:
            self.execute(runner, lambda _phase, _items: [], skill_pin=bad_pin)
        self.assertEqual(context.exception.code, "SKILL_VERSION_MISMATCH")
        self.assertEqual(runner.requests, [])

    def test_child_environment_and_loader_guard_exclude_ambient_model_auth(self):
        isolated = pathlib.Path(tempfile.mkdtemp(prefix="host-skill-env-test-"))
        self.addCleanup(shutil.rmtree, str(isolated), True)
        with mock.patch.dict(
            os.environ,
            {
                "AUTH_TOKEN": "synthetic-source-only",
                "DEEPSEEK_API_KEY": "synthetic-model-only",
                "OPENAI_API_KEY": "synthetic-model-only",
                "XAI_API_KEY": "synthetic-paid-source-only",
                "BRAVE_API_KEY": "synthetic-paid-source-only",
                "SCRAPECREATORS_API_KEY": "synthetic-scrapecreators-only",
            },
            clear=False,
        ):
            child = build_child_environment(("AUTH_TOKEN",), isolated)
        self.assertEqual(child["AUTH_TOKEN"], "synthetic-source-only")
        self.assertNotIn("DEEPSEEK_API_KEY", child)
        self.assertNotIn("OPENAI_API_KEY", child)
        self.assertNotIn("XAI_API_KEY", child)
        self.assertNotIn("BRAVE_API_KEY", child)
        self.assertNotIn("SCRAPECREATORS_API_KEY", child)
        self.assertEqual(child["LAST30DAYS_CONFIG_DIR"], "")
        self.assertEqual(child["LAST30DAYS_TRUST_PROJECT_CONFIG"], "0")
        self.assertIn("_load_keychain", loader_guard_source())
        self.assertIn("_load_pass", loader_guard_source())
        self.assertIn("get_openai_auth", loader_guard_source())
        self.assertNotIn("DEEPSEEK_API_KEY", loader_guard_source())
        with self.assertRaises(HostSkillError) as context:
            self.config(permitted_source_envs=("XAI_API_KEY",))
        self.assertEqual(context.exception.code, "SOURCE_ENV_NOT_PERMITTED")

        # The historical Reddit service is accepted only as an explicit
        # source grant, never as a default or ambient environment lookup.
        self.assertEqual(
            self.config(
                source_allowlist=("reddit",),
                permitted_source_envs=("SCRAPECREATORS_API_KEY",),
            ).permitted_source_envs,
            ("SCRAPECREATORS_API_KEY",),
        )
        with self.assertRaises(HostSkillError) as context:
            self.config(
                source_allowlist=("reddit",),
                permitted_source_envs=("AUTH_TOKEN",),
            )
        self.assertEqual(context.exception.code, "SOURCE_ENV_NOT_AUTHORIZED")

    def test_reddit_credential_is_read_and_injected_only_with_explicit_grant(self):
        isolated = pathlib.Path(tempfile.mkdtemp(prefix="host-skill-reddit-env-"))
        self.addCleanup(shutil.rmtree, str(isolated), True)

        class ReadSpy(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.reads = []

            def get(self, key, *args):
                self.reads.append(key)
                return super().get(key, *args)

        granted = ReadSpy(
            {
                "PATH": "/synthetic/path",
                "SCRAPECREATORS_API_KEY": "synthetic-scrapecreators-only",
                "DEEPSEEK_API_KEY": "synthetic-model-only",
            }
        )
        with mock.patch.object(launcher.os, "environ", granted):
            child = build_child_environment(("SCRAPECREATORS_API_KEY",), isolated)
        self.assertIn("SCRAPECREATORS_API_KEY", granted.reads)
        self.assertEqual(child["SCRAPECREATORS_API_KEY"], "synthetic-scrapecreators-only")
        self.assertNotIn("DEEPSEEK_API_KEY", child)

        denied = ReadSpy(
            {
                "PATH": "/synthetic/path",
                "SCRAPECREATORS_API_KEY": "synthetic-scrapecreators-only",
                "DEEPSEEK_API_KEY": "synthetic-model-only",
            }
        )
        with mock.patch.object(launcher.os, "environ", denied):
            child_without_grant = build_child_environment((), isolated)
        self.assertNotIn("SCRAPECREATORS_API_KEY", denied.reads)
        self.assertNotIn("SCRAPECREATORS_API_KEY", child_without_grant)
        self.assertNotIn("DEEPSEEK_API_KEY", child_without_grant)

    def test_launcher_direct_entrypoint_rejects_unwhitelisted_paid_env(self):
        skill_path = pathlib.Path("/tmp/last30days-synthetic.py")
        environment = {
            "LAST30DAYS_CONFIG_DIR": "",
            "LAST30DAYS_MEMORY_DIR": "/tmp/last30days-state",
            "LAST30DAYS_TRUST_PROJECT_CONFIG": "0",
            "HOME": "/tmp/last30days-home",
            "USERPROFILE": "/tmp/last30days-home",
            "XDG_CONFIG_HOME": "/tmp/last30days-home/.config",
            "PYTHONNOUSERSITE": "1",
            "DEEPSEEK_API_KEY": "synthetic-model-only",
        }
        request = StageRequest(
            phase="nominate",
            argv=(str(skill_path), "--discover", "--nominate-only"),
            skill_path=skill_path,
            python_executable=pathlib.Path(sys.executable),
            cwd=pathlib.Path("/tmp"),
            environment=environment,
            timeout_seconds=0.1,
            max_stdout_bytes=128,
            max_stderr_bytes=128,
        )
        with self.assertRaises(HostSkillLaunchError) as context:
            run_stage(request)
        self.assertEqual(context.exception.code, "CHILD_ENV_NOT_PERMITTED")

    def test_pin_covers_non_core_execution_module_not_only_four_files(self):
        copied_root = pathlib.Path(tempfile.mkdtemp(prefix="last30days-pin-copy-")) / "last30days"
        self.addCleanup(shutil.rmtree, str(copied_root.parent), True)
        shutil.copytree(
            str(SKILL_DIR),
            str(copied_root),
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        # reddit.py is outside the old four-file list but is an executable
        # lib dependency of the discovery pipeline.
        drifted_module = copied_root / "scripts" / "lib" / "reddit.py"
        drifted_module.write_text(
            drifted_module.read_text(encoding="utf-8") + "\n# synthetic pin drift\n",
            encoding="utf-8",
        )
        runner = SyntheticSkillRunner(empty=True)
        drifted_pin = Last30DaysSkillPin(
            path=copied_root,
            version="3.21.1",
            content_sha256=self.pin.content_sha256,
        )
        with self.assertRaises(HostSkillError) as context:
            self.execute(runner, lambda _phase, _items: [], skill_pin=drifted_pin)
        self.assertEqual(context.exception.code, "SKILL_CONTENT_MISMATCH")
        self.assertEqual(runner.requests, [])

    def test_receipts_keep_only_bounded_metadata_not_raw_child_output(self):
        runner = SyntheticSkillRunner(empty=True)
        result = self.execute(runner, lambda _phase, _items: [])
        receipt = result.stages[0]
        self.assertEqual(receipt.stdout_bytes, 24)
        self.assertFalse(hasattr(receipt, "stdout"))
        self.assertFalse(hasattr(receipt, "stderr"))
        self.assertEqual(len(receipt.stdout_sha256), 64)


if __name__ == "__main__":
    unittest.main()
