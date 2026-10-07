"""Synthetic-only coverage for the thin World composition."""

import datetime
import inspect
import json
import pathlib
import sys
import tempfile
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter.core_application import (  # noqa: E402
    CoreOperationalBounds,
    SourceSubmissionBatch,
    run_world_core as real_run_world_core,
)
from convexity_hunter.core_futu import FutuMarketBridge  # noqa: E402
from convexity_hunter.event_entry import UserEventInput  # noqa: E402
from convexity_hunter.event_intelligence import (  # noqa: E402
    EventIntelligenceSubmission,
    EventSourceReference,
    EventUnderlyingHypothesis,
)
from convexity_hunter.host_event import HostEventGrounderConfig  # noqa: E402
from convexity_hunter.host_grounder_run_input import HostGrounderRunInputBounds  # noqa: E402
from convexity_hunter.host_model import ModelCredential, ModelRuntimeConfig  # noqa: E402
from convexity_hunter.host_profile import (  # noqa: E402
    APPROVED_STANDARD_RESEARCH_PROFILE,
    STANDARD_RESEARCH_PROFILE,
)
from convexity_hunter.host_skill import (  # noqa: E402
    AngleInput,
    HostSkillConfig,
    HostSkillResult,
    Last30DaysSkillPin,
    NominationInput,
    ProviderNativeOutput,
)
from convexity_hunter.host_sources import TavilyCredentialRef, TavilySourceConfig  # noqa: E402
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority  # noqa: E402
from convexity_hunter.host_server import (  # noqa: E402
    ValidatedRunRequest,
    _validate_batch_result,
)
from convexity_hunter.host_store import HostStore  # noqa: E402
from convexity_hunter.host_world import (  # noqa: E402
    HostWorldConfig,
    HostWorldError,
    _model_json_object,
    create_world_runner,
)


def _model(role, model, *, request_budget=2):
    return ModelRuntimeConfig(
        provider="deepseek",
        model=model,
        base_endpoint="https://api.deepseek.com",
        role=role,
        capabilities=("json_mode",),
        timeout_seconds=1,
        request_budget=request_budget,
        max_tokens=1000,
        max_input_bytes=100_000,
        max_output_bytes=20_000,
        remote_enabled=True,
        fee_authorized=True,
        json_mode=True,
        thinking_enabled=False,
    )


def _config(*, bounds=None, final_output_path=None, model_budget=2):
    skill = HostSkillConfig(
        skill_pin=Last30DaysSkillPin("/synthetic/skill", "3.21.1", "a" * 64),
        python_executable=sys.executable,
        source_allowlist=("reddit",),
        permitted_source_envs=(),
        stage_timeout_seconds=1,
        request_stage_budget=3,
        max_stdout_bytes=4096,
        max_stderr_bytes=4096,
        max_handoff_bytes=100_000,
        final_output_path=final_output_path,
    )
    grounder = HostEventGrounderConfig(
        source=TavilySourceConfig(
            credential_ref=TavilyCredentialRef(env_name="SYNTHETIC_TAVILY_KEY"),
            paygo_off_confirmed=True,
            request_budget=2,
            credit_budget=2,
            max_request_bytes=100_000,
            max_response_bytes=100_000,
            timeout_seconds=1,
            max_search_results=5,
            max_extract_urls=5,
        ),
        discovery_model=_model("discovery", "synthetic-discovery", request_budget=model_budget),
        discovery_credential=ModelCredential(env_name="SYNTHETIC_DISCOVERY_KEY"),
        semantic_model=_model("semantic", "synthetic-semantic", request_budget=model_budget),
        semantic_credential=ModelCredential(env_name="SYNTHETIC_SEMANTIC_KEY"),
        run_input_bounds=HostGrounderRunInputBounds(100_000, 50_000, 20),
        max_json_bytes=100_000,
        max_source_body_bytes=100_000,
        max_catalog_entries=50,
        max_catalog_bytes=50_000,
        max_catalog_paragraphs=100,
    )
    return HostWorldConfig(
        skill=skill,
        grounder=grounder,
        evaluation_date=datetime.date(2026, 10, 7),
        maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
        bounds=bounds or CoreOperationalBounds(4, 8, 400, 200, 10),
    )


def _persist_world_result(raw_input, bounds, result):
    metadata = {
        "configuration_snapshot": {"models": [], "sources": [], "skills": []},
        "execution_snapshot": {
            "world_executor": {
                "status": "CONFIGURED",
                "version": "host-batch-executor-v0.1",
            }
        },
        "contract_versions": {
            "architecture": "standalone-mvp-architecture-v0.1",
            "host_shell": "host-server-v0.1",
            "standard_research_profile": "standard-research-profile:v0.1",
        },
    }
    canonical_temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(
        dir=str(canonical_temp_root), prefix="host-world-store-test-"
    ) as temp_dir:
        store = HostStore(pathlib.Path(temp_dir) / "journal.sqlite3")
        try:
            run_id = store.create_run(
                "world",
                raw_input,
                bounds,
                STANDARD_RESEARCH_PROFILE.snapshot(),
                metadata,
            )
            store.save_batch_result(run_id, result)
            return store.get_batch_summary(run_id)
        finally:
            store.close()


def _native_result(topics, *, outcome="ok", source_state="ok"):
    report = {
        "domain": "synthetic",
        "range_from": "2026-09-30",
        "range_to": "2026-10-07",
        "generated_at": "2026-10-07T00:00:00+00:00",
        "plan": {"domain": "synthetic", "subreddits": [], "sources": ["reddit"]},
        "topics": topics,
        "source_status": {"reddit": {"state": source_state}},
        "warnings": [],
        "outcome": outcome,
    }
    return HostSkillResult(
        status="complete",
        bundle_id="synthetic-bundle",
        nominations=(),
        survivor_ids=(),
        stages=(),
        remaining_request_budget=0,
        provider_native=ProviderNativeOutput(
            json.dumps(report, separators=(",", ":")).encode(), None
        ),
    )


def _topic(name, url, *, rank, score, angle):
    return {
        "rank": rank,
        "name": name,
        "why_spiking": "synthetic native reason",
        "momentum": "synthetic",
        "velocity_score": score,
        "sources": ["reddit"],
        "engagement_by_source": {},
        "command": "synthetic native command",
        "evidence_urls": [url],
        "corroboration_count": 1,
        "podcast_angle": angle,
        "x_article_angle": angle,
    }


def _submission(submission_id, source_url):
    return EventIntelligenceSubmission(
        submission_id=submission_id,
        event_id="event-" + submission_id,
        producer_id="convexity-hunter-event-grounder",
        producer_version="grounder-v-test",
        observed_at=datetime.datetime(2026, 10, 7, tzinfo=datetime.timezone.utc),
        event_description="synthetic grounded description",
        event_date_range=None,
        sources=(EventSourceReference("source-" + submission_id, source_url),),
        statements=(),
        hypotheses=(EventUnderlyingHypothesis("hyp-" + submission_id, None, None, None, None, None),),
    )


class _Response:
    status = 200
    headers = {}

    def __init__(self, content, model):
        self.body = json.dumps(
            {
                "id": "synthetic-response",
                "model": model,
                "choices": [
                    {
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
            }
        ).encode()

    def read(self, _size=-1):
        return self.body

    def close(self):
        pass


class HostWorldTests(unittest.TestCase):
    def setUp(self):
        self.config = _config()
        self.raw_input = "research a synthetic event"
        self.post_bounds = CoreOperationalBounds(3, 7, 123, 90, 5)
        self.lazy_bridge = FutuMarketBridge(lambda: self.fail("Futu must remain lazy"))
        self.submissions = (
            _submission("one", "https://grounded.example/one"),
            _submission("two", "https://grounded.example/two"),
        )
        self.grounder_calls = []
        self.policies = []

    def _fake_grounder(self, _config, **_kwargs):
        def grounder(text, *, run_id, bounds):
            self.grounder_calls.append((text, run_id, bounds))
            event_input = UserEventInput(text)
            batch = SourceSubmissionBatch(event_input, self.submissions)
            return SimpleNamespace(
                build_result=SimpleNamespace(raw_input=event_input, source_batch=batch)
            )

        return grounder

    def _run_through_real_core(
        self, *, skill_result, skill_error=None, topics=None, bounds=None
    ):
        discovery_calls = []
        semantic_calls = []

        def discovery_transport(request, _timeout):
            discovery_calls.append(json.loads(request.data.decode()))
            return _Response(
                '{"judgments":[{"id":"n1","name":"synthetic","junk":false,"worthiness":50}]}',
                "synthetic-discovery",
            )

        def semantic_transport(request, _timeout):
            semantic_calls.append(json.loads(request.data.decode()))
            return _Response(
                '{"angles":[{"id":"n1","podcast":"synthetic","x_article":"synthetic"}]}',
                "synthetic-semantic",
            )

        def synthetic_skill(config, *, domain, model_callback, **_kwargs):
            self.assertEqual(domain, self.raw_input)
            if skill_error is not None:
                raise skill_error
            if getattr(skill_result, "status", None) == "empty":
                return skill_result
            model_callback("judgments", (NominationInput("n1", {"nomination": {}}),))
            model_callback("angles", (AngleInput("n1", {"name": "synthetic"}),))
            return skill_result

        captured = []

        def core_spy(raw_request, *, source_producer, market_bridge, policy):
            self.policies.append(policy)
            batch = source_producer(raw_request)
            captured.append(batch)
            return real_run_world_core(
                raw_request,
                source_producer=lambda _raw: batch,
                market_bridge=market_bridge,
                policy=policy,
            )

        with mock.patch("convexity_hunter.host_world.create_event_grounder", side_effect=self._fake_grounder), \
                mock.patch("convexity_hunter.host_world.run_last30days_discovery", side_effect=synthetic_skill), \
                mock.patch("convexity_hunter.host_world.run_world_core", side_effect=core_spy), \
                mock.patch.object(ModelCredential, "resolve", return_value="synthetic-token"):
            runner = create_world_runner(
                self.config,
                repo_root=ROOT,
                market_bridge=self.lazy_bridge,
                discovery_transport=discovery_transport,
                semantic_transport=semantic_transport,
            )
            result = runner(self.raw_input, bounds=bounds or self.post_bounds)
        return result, captured, discovery_calls, semantic_calls

    def test_both_producers_reach_grounder_all_submissions_reach_core(self):
        url = "https://lead.example/a%2Fb?x=1"
        result, captured, discovery_calls, semantic_calls = self._run_through_real_core(
            skill_result=_native_result(
                [
                    _topic("Zeta lead", "https://lead.example/z", rank=1, score=99, angle="discard angle"),
                    _topic("Alpha lead", url, rank=9, score=1, angle="discard angle"),
                    _topic("alpha  lead", url, rank=2, score=88, angle="discard angle"),
                ]
            )
        )
        self.assertEqual(len(self.grounder_calls), 1)
        text, run_id, bounds = self.grounder_calls[0]
        self.assertTrue(text.startswith(self.raw_input))
        self.assertIn("Zeta lead", text)
        self.assertIn("Alpha lead", text)
        self.assertIn(url, text)
        self.assertNotIn("velocity_score", text)
        self.assertNotIn("discard angle", text)
        leads = json.loads(text.split("grounded:\n", 1)[1])
        self.assertEqual(len(leads), 2)
        self.assertIn("Alpha lead", leads[0]["topic_names"])
        self.assertIn("Zeta lead", leads[1]["topic_names"])
        self.assertTrue(run_id)
        self.assertIs(bounds, self.post_bounds)
        self.assertEqual(len(captured), 1)
        policy = self.policies[-1]
        self.assertEqual(policy.evaluation_date, datetime.date(2026, 10, 7))
        self.assertIs(
            policy.maturity_authority,
            OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
        )
        self.assertEqual(policy.generated_quantity, APPROVED_STANDARD_RESEARCH_PROFILE.quantity)
        self.assertIs(policy.request_factory.__self__, APPROVED_STANDARD_RESEARCH_PROFILE)
        self.assertIs(policy.bounds, self.post_bounds)
        batch = captured[0]
        self.assertIs(batch.raw_input, self.raw_input)
        self.assertIs(result.case_set.raw_input, self.raw_input)
        self.assertEqual(
            tuple(item.submission_id for item in batch.submissions),
            tuple(item.submission_id for item in self.submissions),
        )
        for actual, original in zip(batch.submissions, self.submissions):
            self.assertEqual(actual.sources, original.sources)
            self.assertEqual(actual.statements, original.statements)
            self.assertEqual(actual.hypotheses, original.hypotheses)
        self.assertEqual(len(result.case_set.submissions.submissions), 2)
        self.assertEqual(
            {item.producer_id for item in result.case_set.submissions.submissions},
            {"convexity-hunter-world"},
        )
        for item in result.case_set.submissions.submissions:
            self.assertIn("web=tavily", item.producer_version)
            self.assertIn("lead=last30days@3.21.1", item.producer_version)
            self.assertIn("grounder=convexity-hunter-event-grounder@grounder-v-test", item.producer_version)
        self.assertEqual(len(discovery_calls), 1)
        self.assertEqual(len(semantic_calls), 1)
        self.assertEqual(result.case_set.status, "COMPLETE")
        self.assertIs(
            _validate_batch_result(
                result,
                ValidatedRunRequest("world", self.raw_input, self.post_bounds),
            ),
            result,
        )
        saved_summary = _persist_world_result(
            self.raw_input, self.post_bounds, result
        )
        self.assertIsNotNone(saved_summary)
        self.assertEqual(saved_summary["entry_origin"], "WORLD")

    def test_empty_or_failed_skill_is_retained_as_partial_reason(self):
        empty = HostSkillResult("empty", None, (), (), (), 0)
        result, captured, _discovery, _semantic = self._run_through_real_core(skill_result=empty)
        self.assertEqual(len(self.grounder_calls), 1)
        self.assertEqual(self.grounder_calls[0][0], self.raw_input)
        self.assertIn("world_last30days_empty", result.case_set.reasons)
        self.assertEqual(len(captured[0].submissions), 2)
        self.assertTrue(
            all(
                "last30days_status=empty@3.21.1" in s.producer_version
                and "lead=last30days@" not in s.producer_version
                for s in captured[0].submissions
            )
        )

        self.grounder_calls.clear()
        result, captured, _discovery, _semantic = self._run_through_real_core(
            skill_result=None, skill_error=RuntimeError("synthetic hidden failure")
        )
        self.assertIn("world_last30days_failed", result.case_set.reasons)
        self.assertTrue(
            all(
                "last30days_status=failed@3.21.1" in s.producer_version
                and "lead=last30days@" not in s.producer_version
                for s in captured[0].submissions
            )
        )
        self.assertNotIn("synthetic hidden failure", repr(result.case_set.reasons))

    def test_model_json_rejects_duplicate_keys_and_nonfinite_values(self):
        for text in (
            '{"judgments":[],"judgments":[{"id":"replacement"}]}',
            '{"nested":{"id":"first","id":"replacement"}}',
            '{"worthiness":NaN}',
            '{"worthiness":Infinity}',
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                _model_json_object(text)
        self.assertEqual(_model_json_object('{"judgments":[]}'), {"judgments": []})

    def test_native_duplicate_keys_fail_without_consuming_leads(self):
        skill = _native_result([
            _topic("lead", "https://lead.example/1", rank=1, score=1, angle="x")
        ])
        raw = skill.provider_native.raw_json.decode()
        for malformed in (
            raw.replace('"topics":', '"topics":[],"topics":', 1),
            raw.replace('"name":"lead"', '"name":"discarded","name":"lead"', 1),
            raw.replace('"outcome":"ok"', '"outcome":"failed","outcome":"ok"', 1),
            raw.replace('"state":"ok"', '"state":"failed","state":"ok"', 1),
        ):
            with self.subTest(malformed=malformed):
                self.grounder_calls.clear()
                invalid = replace(
                    skill,
                    provider_native=ProviderNativeOutput(malformed.encode(), None),
                )
                result, captured, _, _ = self._run_through_real_core(skill_result=invalid)
                self.assertIn("world_last30days_failed", result.case_set.reasons)
                self.assertEqual(self.grounder_calls[0][0], self.raw_input)
                for submission in captured[0].submissions:
                    self.assertIn("last30days_status=failed@", submission.producer_version)
                    self.assertNotIn("lead=last30days@", submission.producer_version)

    def test_grounding_input_overflow_is_blocked_and_persistable(self):
        self.config = replace(
            self.config,
            grounder=replace(
                self.config.grounder,
                run_input_bounds=HostGrounderRunInputBounds(100_000, 50, 20),
            ),
        )
        skill = _native_result([
            _topic("lead", "https://lead.example/1", rank=1, score=1, angle="x")
        ])
        result, captured, _, _ = self._run_through_real_core(skill_result=skill)
        self.assertEqual(result.case_set.status, "BLOCKED")
        self.assertEqual(result.case_set.reasons, ("world_grounding_input_limit",))
        self.assertEqual(captured[0].submissions, ())
        self.assertEqual(self.grounder_calls, [])
        self.assertIs(result.case_set.raw_input, self.raw_input)
        _validate_batch_result(
            result, ValidatedRunRequest("world", self.raw_input, self.post_bounds)
        )
        saved = _persist_world_result(self.raw_input, self.post_bounds, result)
        self.assertEqual(saved["reasons"], ["world_grounding_input_limit"])

    def test_grounder_empty_and_failure_retain_no_source_reasons(self):
        skill = _native_result([_topic("lead", "https://lead.example/1", rank=1, score=1, angle="x")])
        for failure in ("empty", "failed"):
            self.grounder_calls.clear()

            def fake_factory(_config, **_kwargs):
                def grounder(text, *, run_id, bounds):
                    self.grounder_calls.append(text)
                    if failure == "failed":
                        raise RuntimeError("synthetic hidden failure")
                    event_input = UserEventInput(text)
                    return SimpleNamespace(
                        build_result=SimpleNamespace(
                            raw_input=event_input,
                            source_batch=SourceSubmissionBatch(event_input, ()),
                        )
                    )

                return grounder

            def core_spy(raw_request, *, source_producer, market_bridge, policy):
                batch = source_producer(raw_request)
                return real_run_world_core(
                    raw_request,
                    source_producer=lambda _raw: batch,
                    market_bridge=market_bridge,
                    policy=policy,
                )

            with mock.patch("convexity_hunter.host_world.create_event_grounder", side_effect=fake_factory), \
                    mock.patch("convexity_hunter.host_world.run_last30days_discovery", return_value=skill), \
                    mock.patch("convexity_hunter.host_world.run_world_core", side_effect=core_spy), \
                    mock.patch.object(ModelCredential, "resolve", return_value="synthetic-token"):
                runner = create_world_runner(
                    self.config,
                    repo_root=ROOT,
                    market_bridge=self.lazy_bridge,
                )
                result = runner(self.raw_input, bounds=self.post_bounds)
            self.assertEqual(result.case_set.status, "BLOCKED")
            self.assertIn(
                "world_grounder_no_submission" if failure == "empty" else "world_grounder_failed",
                result.case_set.reasons,
            )
            self.assertEqual(result.case_set.submissions.submissions, ())

    def test_capacity_and_lead_limit_refuse_grounder_before_request(self):
        empty_capacity = _config(bounds=CoreOperationalBounds(0, 8, 400, 200, 10))
        with mock.patch("convexity_hunter.host_world.create_event_grounder", side_effect=self._fake_grounder), \
                mock.patch("convexity_hunter.host_world.run_last30days_discovery", side_effect=AssertionError("Skill must not run")):
            runner = create_world_runner(empty_capacity, repo_root=ROOT, market_bridge=self.lazy_bridge)
            result = runner(self.raw_input, bounds=empty_capacity.bounds)
        self.assertEqual(result.case_set.status, "BLOCKED")
        self.assertIn("world_operational_capacity_zero", result.case_set.reasons)
        self.assertEqual(self.grounder_calls, [])

        limited = _config(bounds=CoreOperationalBounds(4, 1, 400, 200, 10))
        skill = _native_result(
            [
                _topic("one", "https://lead.example/1", rank=1, score=1, angle="x"),
                _topic("two", "https://lead.example/2", rank=2, score=2, angle="y"),
            ]
        )
        with mock.patch("convexity_hunter.host_world.create_event_grounder", side_effect=self._fake_grounder), \
                mock.patch("convexity_hunter.host_world.run_last30days_discovery", return_value=skill), \
                mock.patch.object(ModelCredential, "resolve", return_value="synthetic-token"):
            runner = create_world_runner(limited, repo_root=ROOT, market_bridge=self.lazy_bridge)
            result = runner(self.raw_input, bounds=limited.bounds)
        self.assertEqual(result.case_set.status, "BLOCKED")
        self.assertEqual(result.case_set.reasons, ("world_leads_capacity_exceeded",))
        self.assertEqual(self.grounder_calls, [])
        saved_summary = _persist_world_result(
            self.raw_input, limited.bounds, result
        )
        self.assertEqual(
            saved_summary["reasons"], ["world_leads_capacity_exceeded"]
        )

    def test_raw_native_persistence_is_rejected_at_factory(self):
        config = _config(final_output_path=pathlib.Path("/tmp/native.json"))
        with self.assertRaises(HostWorldError) as raised:
            create_world_runner(config, repo_root=ROOT, market_bridge=self.lazy_bridge)
        self.assertEqual(raised.exception.code, "NATIVE_PERSISTENCE_FORBIDDEN")

    def test_host_executor_signature_and_run_wide_model_budget_allocation(self):
        captured = {}

        def grounder_factory(config, **_kwargs):
            captured["config"] = config
            return self._fake_grounder(config)

        with mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            side_effect=grounder_factory,
        ):
            runner = create_world_runner(
                self.config, repo_root=ROOT, market_bridge=self.lazy_bridge
            )

        parameters = inspect.signature(runner).parameters
        self.assertEqual(tuple(parameters), ("raw_input", "bounds"))
        self.assertEqual(parameters["bounds"].kind, inspect.Parameter.KEYWORD_ONLY)
        # The original per-role budget is the explicit World total (2); one
        # request is allocated to each fresh phase client.
        self.assertEqual(self.config.grounder.discovery_model.request_budget, 2)
        self.assertEqual(self.config.grounder.semantic_model.request_budget, 2)
        self.assertEqual(captured["config"].discovery_model.request_budget, 1)
        self.assertEqual(captured["config"].semantic_model.request_budget, 1)

    def test_role_total_budget_preflights_before_grounder_or_skill(self):
        config = _config(model_budget=1)
        with mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            side_effect=AssertionError("budget must fail before factory creation"),
        ), mock.patch(
            "convexity_hunter.host_world.run_last30days_discovery",
            side_effect=AssertionError("Skill must not run"),
        ):
            with self.assertRaises(HostWorldError) as raised:
                create_world_runner(
                    config, repo_root=ROOT, market_bridge=self.lazy_bridge
                )
        self.assertEqual(raised.exception.code, "MODEL_BUDGET_INSUFFICIENT")

    def test_post_bounds_above_config_cap_are_refused_before_charged_calls(self):
        over_cap = CoreOperationalBounds(5, 7, 123, 90, 5)
        with mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            side_effect=self._fake_grounder,
        ), mock.patch(
            "convexity_hunter.host_world.run_last30days_discovery",
            side_effect=AssertionError("Skill must not run"),
        ), mock.patch.object(
            ModelCredential,
            "resolve",
            side_effect=AssertionError("credentials must not resolve"),
        ):
            runner = create_world_runner(
                self.config, repo_root=ROOT, market_bridge=self.lazy_bridge
            )
            result = runner(self.raw_input, bounds=over_cap)
        self.assertIn("world_bounds_exceed_config", result.case_set.reasons)
        self.assertIs(result.case_set.raw_input, self.raw_input)
        self.assertEqual(self.grounder_calls, [])


if __name__ == "__main__":
    unittest.main()
