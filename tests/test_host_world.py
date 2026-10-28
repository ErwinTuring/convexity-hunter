"""Synthetic-only coverage for the thin World composition."""

import datetime
import inspect
import json
import math
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
import convexity_hunter.host_event as host_event_module  # noqa: E402
import convexity_hunter.host_world as host_world_module  # noqa: E402
from convexity_hunter.host_grounder_runtime import HostGrounderRuntimeError  # noqa: E402
from convexity_hunter.host_grounder_run_input import HostGrounderRunInputBounds  # noqa: E402
from convexity_hunter.host_model import (  # noqa: E402
    ModelCredential,
    ModelRuntimeConfig,
    ModelTransportError,
)
from convexity_hunter.host_profile import (  # noqa: E402
    APPROVED_STANDARD_RESEARCH_PROFILE,
    STANDARD_RESEARCH_PROFILE,
)
from convexity_hunter.host_skill import (  # noqa: E402
    AngleInput,
    HostSkillConfig,
    HostSkillError,
    HostSkillResult,
    Last30DaysSkillPin,
    NominationInput,
    ProviderNativeOutput,
    run_last30days_discovery as real_run_last30days_discovery,
)
from convexity_hunter.host_sources import (  # noqa: E402
    TavilyCredentialRef,
    TavilySourceConfig,
    TavilyTransportError,
)
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority  # noqa: E402
from convexity_hunter.host_server import (  # noqa: E402
    HostRequestHandler,
    ValidatedRunRequest,
    _public_run,
    _public_batch_summary,
    _run_start_metadata,
    _validate_batch_result,
)
from convexity_hunter.host_store import HostStore  # noqa: E402
from convexity_hunter.host_world import (  # noqa: E402
    HostWorldConfig,
    HostWorldError,
    _model_json_object,
    _world_model_transport_diagnostic,
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


def _config(*, bounds=None, final_output_path=None, model_budget=2, source_budget=2):
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
            request_budget=source_budget,
            credit_budget=source_budget,
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


def _expected_world_source_query(scope, evaluation_date):
    return (
        "Public company events for {} from {} through {} inclusive: "
        "explicit catalysts; narrative/belief shifts; second-order transmission."
    ).format(
        scope,
        (evaluation_date - datetime.timedelta(days=6)).isoformat(),
        evaluation_date.isoformat(),
    )


def _expected_world_unit_query(scope, evaluation_date, names):
    return _expected_world_source_query(scope, evaluation_date) + (
        " Provisional event lead: {}.".format(
            json.dumps(names, ensure_ascii=False, separators=(",", ":"))
        )
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
        database_path = pathlib.Path(temp_dir) / "journal.sqlite3"
        store = HostStore(database_path)
        try:
            run_id = store.create_run(
                "world",
                raw_input,
                bounds,
                STANDARD_RESEARCH_PROFILE.snapshot(),
                metadata,
            )
            store.save_batch_result(run_id, result)
        finally:
            store.close()
        reopened = HostStore(database_path)
        try:
            return reopened.get_batch_summary(run_id)
        finally:
            reopened.close()


def _native_result(topics, *, outcome="ok", source_state="ok", source_status=None):
    report = {
        "domain": "synthetic",
        "range_from": "2026-09-30",
        "range_to": "2026-10-07",
        "generated_at": "2026-10-07T00:00:00+00:00",
        "plan": {"domain": "synthetic", "subreddits": [], "sources": ["reddit"]},
        "topics": topics,
        "source_status": source_status
        if source_status is not None
        else {"reddit": {"state": source_state}},
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
        self.grounder_query_calls = []
        self.grounder_seed_calls = []
        self.policies = []
        self.grounder_query_error = None

    def _fake_grounder(self, _config, **_kwargs):
        def grounder(text, *, run_id, bounds):
            submission_index = len(self.grounder_calls)
            self.grounder_calls.append((text, run_id, bounds))
            event_input = UserEventInput(text)
            submissions = self.submissions[submission_index : submission_index + 1]
            batch = SourceSubmissionBatch(event_input, submissions)
            return SimpleNamespace(
                build_result=SimpleNamespace(raw_input=event_input, source_batch=batch)
            )

        def world_source_query_factory(query, *, seed_urls=()):
            self.grounder_query_calls.append(query)
            self.grounder_seed_calls.append(seed_urls)

            def query_bound_grounder(text, *, run_id, bounds):
                if self.grounder_query_error is not None:
                    raise self.grounder_query_error
                return grounder(text, run_id=run_id, bounds=bounds)

            return query_bound_grounder

        grounder._world_source_query_factory = world_source_query_factory
        grounder.configuration_snapshot = lambda: {
            "models": [], "sources": [], "skills": []
        }
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

    def _run_frozen_native_skill_world(self, outputs):
        from tests.test_host_skill import NOW as skill_now, SyntheticSkillRunner

        observed = {}

        def fake_transport(role):
            def transport(request, _timeout):
                body = json.loads(request.data.decode("utf-8"))
                system_prompt = body["messages"][0]["content"]
                source = json.loads(body["messages"][1]["content"])
                phase = source["phase"]
                expected_role = "discovery" if phase == "judgments" else "semantic"
                self.assertEqual(role, expected_role)
                observed[phase] = {
                    "system": system_prompt,
                    "source": source,
                }
                return _Response(
                    json.dumps(outputs[phase], separators=(",", ":")),
                    body["model"],
                )

            return transport

        stage_runner = SyntheticSkillRunner()
        self.grounder_calls.clear()
        self.grounder_query_calls.clear()
        with mock.patch.object(
            ModelCredential, "resolve", return_value="synthetic-token"
        ), mock.patch(
            "convexity_hunter.host_skill._verify_skill_pin",
            return_value=pathlib.Path("/synthetic/skill"),
        ), mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            side_effect=self._fake_grounder,
        ):
            world_runner = create_world_runner(
                self.config,
                repo_root=ROOT,
                market_bridge=self.lazy_bridge,
                discovery_transport=fake_transport("discovery"),
                semantic_transport=fake_transport("semantic"),
                stage_runner=stage_runner,
                skill_clock=lambda: skill_now,
            )
            result = world_runner(self.raw_input, bounds=self.post_bounds)
        return result, stage_runner, observed

    def test_world_model_callback_passes_frozen_native_skill_wire(self):
        self.config = _config(model_budget=3, source_budget=4)
        outputs = {
            "judgments": {
                "judgments": [
                    {"id": "n2", "name": "Topic two", "junk": True, "worthiness": 3},
                    {"id": "n1", "name": "Topic one", "junk": False, "worthiness": 97},
                ]
            },
            "angles": {
                "angles": [
                    {"id": "n1", "podcast": "podcast one", "x_article": "article one"},
                    {"id": "n2", "podcast": "podcast two", "x_article": "article two"},
                ]
            },
        }
        result, stage_runner, observed = self._run_frozen_native_skill_world(outputs)

        self.assertEqual(result.case_set.status, "COMPLETE")
        self.assertIn("lead=last30days@3.21.1", result.case_set.submissions.submissions[0].producer_version)
        self.assertEqual(len(self.grounder_calls), 2)
        self.assertEqual(len(self.grounder_query_calls), 2)
        self.assertTrue(all("Provisional event lead: [" in query for query in self.grounder_query_calls))
        for text, _run_id, _bounds in self.grounder_calls:
            lead_payload = json.loads(text.split("grounded:\n", 1)[1])
            self.assertEqual(len(lead_payload), 1)
        self.assertEqual(len(result.case_set.submissions.submissions), 2)
        self.assertEqual(
            self.grounder_query_calls,
            [
                _expected_world_unit_query(
                    self.raw_input, self.config.evaluation_date, ["Model topic one"]
                ),
                _expected_world_unit_query(
                    self.raw_input, self.config.evaluation_date, ["Model topic two"]
                ),
            ],
        )
        self.assertIn(self.raw_input, self.grounder_calls[0][0])
        self.assertIn("Provisional last30days lead hints only", self.grounder_calls[0][0])
        self.assertEqual(
            [row["id"] for row in stage_runner.judgments["judgments"]],
            ["n1", "n2"],
        )
        self.assertEqual(
            [row["id"] for row in stage_runner.angles["angles"]],
            ["n2", "n1"],
        )
        self.assertEqual(
            observed["judgments"]["source"]["rows"][0]["payload"]["nomination"]
            ["items"][0]["title"],
            "Native seed one",
        )
        self.assertEqual(
            observed["angles"]["source"]["rows"][0]["payload"]["name"],
            "Model topic two",
        )
        self.assertIn("exactly these keys and JSON types", observed["judgments"]["system"])
        self.assertIn("junk (boolean)", observed["judgments"]["system"])
        self.assertIn("worthiness (integer", observed["judgments"]["system"])
        self.assertIn("exactly these keys and JSON types", observed["angles"]["system"])
        self.assertIn("podcast (string)", observed["angles"]["system"])
        self.assertIn("at most 200 characters", observed["angles"]["system"])
        self.assertIn(
            "the returned ID set must exactly equal the input ID set",
            observed["judgments"]["system"],
        )
        self.assertIn(
            "the returned ID set must exactly equal the input ID set",
            observed["angles"]["system"],
        )

    def test_world_model_prompt_counterexamples_match_frozen_consumer(self):
        valid_outputs = {
            "judgments": {
                "judgments": [
                    {"id": "n1", "name": "Topic one", "junk": False, "worthiness": 50},
                    {"id": "n2", "name": "Topic two", "junk": False, "worthiness": 50},
                ]
            },
            "angles": {
                "angles": [
                    {"id": "n2", "podcast": "podcast two", "x_article": "article two"},
                    {"id": "n1", "podcast": "podcast one", "x_article": "article one"},
                ]
            },
        }
        counterexamples = (
            (
                "judgment_non_boolean",
                "judgments",
                lambda: {
                    "judgments": [
                        {"id": "n1", "name": "Topic one", "junk": "false", "worthiness": 50},
                        {"id": "n2", "name": "Topic two", "junk": False, "worthiness": 50},
                    ]
                },
                "junk (boolean)",
            ),
            (
                "judgment_extra_key",
                "judgments",
                lambda: {
                    "judgments": [
                        {"id": "n1", "name": "Topic one", "junk": False, "worthiness": 50, "certainty": 1},
                        {"id": "n2", "name": "Topic two", "junk": False, "worthiness": 50},
                    ]
                },
                "Do not add row keys",
            ),
            (
                "judgment_unknown_id_row",
                "judgments",
                lambda: {
                    "judgments": [
                        {"id": "n1", "name": "Topic one", "junk": False, "worthiness": 50},
                        {"id": "n2", "name": "Topic two", "junk": False, "worthiness": 50},
                        {"id": "n3", "name": "Unknown topic", "junk": False, "worthiness": 50},
                    ]
                },
                "the returned ID set must exactly equal the input ID set",
            ),
            (
                "angle_non_string",
                "angles",
                lambda: {
                    "angles": [
                        {"id": "n2", "podcast": None, "x_article": "article two"},
                        {"id": "n1", "podcast": "podcast one", "x_article": "article one"},
                    ]
                },
                "podcast (string)",
            ),
            (
                "angle_extra_key",
                "angles",
                lambda: {
                    "angles": [
                        {"id": "n2", "podcast": "podcast two", "x_article": "article two", "confidence": 1},
                        {"id": "n1", "podcast": "podcast one", "x_article": "article one"},
                    ]
                },
                "Do not add row keys",
            ),
        )

        for case_name, phase, invalid_output, prompt_clause in counterexamples:
            with self.subTest(case=case_name):
                outputs = dict(valid_outputs)
                outputs[phase] = invalid_output()
                result, stage_runner, observed = self._run_frozen_native_skill_world(outputs)

                self.assertIn("world_last30days_failed", result.case_set.reasons)
                if case_name != "judgment_unknown_id_row":
                    self.assertIn("world_last30days_model_failed", result.case_set.reasons)
                self.assertTrue(
                    all(
                        "last30days_status=failed@3.21.1" in item.producer_version
                        for item in result.case_set.submissions.submissions
                    )
                )
                self.assertIn(prompt_clause, observed[phase]["system"])
                expected_phases = ["nominate"]
                if phase == "angles":
                    expected_phases.append("resume")
                self.assertEqual(
                    [request.phase for request in stage_runner.requests],
                    expected_phases,
                )

    def test_only_stamped_bound_object_omission_failures_escape_world_catch(self):
        from tests.test_host_server import _normal_v09_omission_failure
        from convexity_hunter.host_grounder_evidence_catalog import (
            _BINDING_OMISSION_FAILURE_ROUTE,
            _BINDING_OMISSION_FAILURE_ROUTE_V0_10,
            _BINDING_OMISSION_FAILURE_ROUTE_V0_11,
        )

        empty_skill = HostSkillResult("empty", None, (), (), (), 0)

        def omission_failure(bound_object, historical_route=None):
            error, calls = _normal_v09_omission_failure(
                "delta", bound_object=bound_object
            )
            if historical_route is not None:
                error._producer_failure_route = historical_route
                error._semantic_transport_route = historical_route
            return error, calls

        accepted_fixtures = (
            (
                "legacy-v0.9-v0.8",
                _BINDING_OMISSION_FAILURE_ROUTE,
                lambda: omission_failure(False)[0],
            ),
            (
                "legacy-v0.10",
                _BINDING_OMISSION_FAILURE_ROUTE_V0_10,
                lambda: omission_failure(
                    True, _BINDING_OMISSION_FAILURE_ROUTE_V0_10
                )[0],
            ),
            (
                "current-v0.11",
                _BINDING_OMISSION_FAILURE_ROUTE_V0_11,
                lambda: omission_failure(True)[0],
            ),
        )
        for label, expected_route, make_error in accepted_fixtures:
            with self.subTest(accepted_route=label):
                omission_error = make_error()
                self.assertEqual(
                    omission_error._producer_failure_route, expected_route
                )
                self.assertEqual(
                    omission_error._semantic_transport_route, expected_route
                )
                self.grounder_query_error = omission_error
                with self.assertRaises(HostGrounderRuntimeError) as raised:
                    self._run_through_real_core(skill_result=empty_skill)
                self.assertIs(raised.exception, omission_error)

        invalid_fixtures = (
            ("unstamped", None, None),
            (
                "route-mismatch",
                _BINDING_OMISSION_FAILURE_ROUTE_V0_11,
                _BINDING_OMISSION_FAILURE_ROUTE_V0_10,
            ),
            (
                "unrelated-route",
                (
                    "host-grounder-discovery-prompt-v0.8",
                    "host-grounder-semantic-verifier-prompt-v0.7",
                ),
                (
                    "host-grounder-discovery-prompt-v0.8",
                    "host-grounder-semantic-verifier-prompt-v0.7",
                ),
            ),
        )
        for label, producer_route, semantic_route in invalid_fixtures:
            with self.subTest(rejected_route=label):
                error, _calls = omission_failure(True)
                if producer_route is None:
                    del error._producer_failure_route
                else:
                    error._producer_failure_route = producer_route
                if semantic_route is not None:
                    error._semantic_transport_route = semantic_route
                self.grounder_query_error = error
                result, captured, _discovery, _semantic = self._run_through_real_core(
                    skill_result=empty_skill
                )
                self.assertIn("world_grounder_failed", result.case_set.reasons)
                self.assertEqual(captured[0].submissions, ())

    def test_world_batch_failure_is_archived_with_v02_attempt_hashes(self):
        from tests.test_host_server import _normal_v09_omission_failure

        omission_error, _calls = _normal_v09_omission_failure("delta")
        self.grounder_query_error = omission_error
        empty_skill = HostSkillResult("empty", None, (), (), (), 0)
        observed_world_errors = []

        def world_executor(_raw_input, *, bounds):
            try:
                self._run_through_real_core(skill_result=empty_skill, bounds=bounds)
            except HostGrounderRuntimeError as error:
                observed_world_errors.append(error)
                raise

        request = ValidatedRunRequest("world", self.raw_input, self.post_bounds)
        with tempfile.TemporaryDirectory(
            dir=pathlib.Path(tempfile.gettempdir()).resolve()
        ) as temp_dir:
            store = HostStore(pathlib.Path(temp_dir) / "world-omission.sqlite3")
            try:
                run_id = store.create_run(
                    "world",
                    self.raw_input,
                    self.post_bounds,
                    STANDARD_RESEARCH_PROFILE.snapshot(),
                    _run_start_metadata(world_configured=True),
                )
                stage_id = store.start_stage(run_id, "executor")

                class HandlerHarness:
                    _post_batch_run = HostRequestHandler._post_batch_run
                    _complete_terminal_run = HostRequestHandler._complete_terminal_run

                    def __init__(self, journal):
                        self.server = SimpleNamespace(journal=journal)
                        self.responses = []

                    def _send_json(self, status, payload):
                        self.responses.append((status, payload))

                handler = HandlerHarness(store)
                handler._post_batch_run(
                    request, run_id, stage_id, world_executor
                )

                self.assertEqual(observed_world_errors, [omission_error])
                self.assertIs(observed_world_errors[0], omission_error)
                self.assertEqual(
                    handler.responses,
                    [(
                        201,
                        {
                            "run_id": run_id,
                            "status": "FAILED",
                            "reason": "HOST_BATCH_EXECUTOR_FAILED",
                        },
                    )],
                )
                stored = store.get_run(run_id)
                self.assertEqual(stored["status"], "FAILED")
                stored_outcome = stored["events"][1]["outcome"]
                self.assertEqual(
                    stored_outcome["schema_version"],
                    "host-grounder-producer-failure-audit-v0.2",
                )
                self.assertEqual(stored_outcome["status"], "FAILED")
                self.assertEqual(
                    stored_outcome["producer_prompt_version"],
                    "host-grounder-discovery-prompt-v0.9",
                )
                self.assertEqual(
                    stored_outcome["verifier_prompt_version"],
                    "host-grounder-semantic-verifier-prompt-v0.8",
                )
                expected_attempts = [item.to_json() for item in omission_error.producer_attempts]
                self.assertEqual(stored_outcome["producer_attempts"], expected_attempts)
                self.assertEqual(
                    [item["output_sha256"] for item in stored_outcome["producer_attempts"]],
                    [item.output_sha256 for item in omission_error.producer_attempts],
                )

                public = _public_run(stored)
                public_outcome = public["events"][1]["outcome"]
                self.assertEqual(public_outcome, stored_outcome)
                self.assertEqual(
                    [item["output_sha256"] for item in public_outcome["producer_attempts"]],
                    [item.output_sha256 for item in omission_error.producer_attempts],
                )

                ordinary_run_id = store.create_run(
                    "world",
                    self.raw_input,
                    self.post_bounds,
                    STANDARD_RESEARCH_PROFILE.snapshot(),
                    _run_start_metadata(world_configured=True),
                )
                ordinary_stage_id = store.start_stage(ordinary_run_id, "executor")

                def ordinary_executor(*_args, **_kwargs):
                    raise RuntimeError("PRIVATE_ORDINARY_BATCH_FAILURE")

                ordinary_handler = HandlerHarness(store)
                ordinary_handler._post_batch_run(
                    request, ordinary_run_id, ordinary_stage_id, ordinary_executor
                )
                self.assertEqual(
                    ordinary_handler.responses,
                    [(
                        201,
                        {
                            "run_id": ordinary_run_id,
                            "status": "FAILED",
                            "reason": "HOST_BATCH_EXECUTOR_FAILED",
                        },
                    )],
                )
                self.assertEqual(
                    store.get_run(ordinary_run_id)["events"][1]["outcome"],
                    "FAILED",
                )
            finally:
                store.close()

    def test_both_producers_reach_grounder_all_submissions_reach_core(self):
        self.config = _config(model_budget=3, source_budget=4)
        url = "https://lead.example/a%2Fb?x=1"
        long_url = "https://lead.example/" + ("u" * 450)
        long_topic_name = "Zeta lead"
        result, captured, discovery_calls, semantic_calls = self._run_through_real_core(
            skill_result=_native_result(
                [
                    _topic(long_topic_name, long_url, rank=1, score=99, angle="discard angle"),
                    _topic("Alpha lead", url, rank=9, score=1, angle="discard angle"),
                    _topic("alpha  lead", url, rank=2, score=88, angle="discard angle"),
                ]
            )
        )
        self.assertEqual(len(self.grounder_calls), 2)
        expected_contexts = [
            (("Alpha lead", "alpha  lead"), (url,)),
            ((long_topic_name,), (long_url,)),
        ]
        for (text, run_id, bounds), expected_group in zip(
            self.grounder_calls, expected_contexts
        ):
            self.assertTrue(text.startswith(self.raw_input))
            self.assertNotIn("velocity_score", text)
            self.assertNotIn("discard angle", text)
            leads = json.loads(text.split("grounded:\n", 1)[1])
            self.assertEqual(len(leads), 1)
            self.assertEqual(tuple(leads[0]["topic_names"]), expected_group[0])
            self.assertEqual(tuple(leads[0]["evidence_urls"]), expected_group[1])
            self.assertTrue(run_id)
            self.assertIs(bounds, self.post_bounds)
        self.assertEqual(len(captured), 1)
        self.assertEqual(
            self.grounder_query_calls,
            [
                _expected_world_unit_query(
                    self.raw_input,
                    self.config.evaluation_date,
                    ["Alpha lead", "alpha  lead"],
                ),
                _expected_world_unit_query(
                    self.raw_input, self.config.evaluation_date, [long_topic_name]
                ),
            ],
        )
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
            self.assertIn("world-v0.5", item.producer_version)
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
        self.assertIn("world_native_scope_fallback", result.case_set.reasons)
        self.assertEqual(len(captured[0].submissions), 1)
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
        self.assertIs(result.case_set.raw_input, self.raw_input)
        self.assertIs(captured[0].raw_input, self.raw_input)
        self.assertTrue(
            all(
                "last30days_status=failed@3.21.1" in s.producer_version
                and "lead=last30days@" not in s.producer_version
                for s in captured[0].submissions
            )
        )
        self.assertNotIn("synthetic hidden failure", repr(result.case_set.reasons))

    def test_typed_last30days_failures_add_only_closed_diagnostics(self):
        failures = (
            (
                HostSkillError("INVALID_DOMAIN"),
                "world_last30days_input_invalid",
            ),
            (
                HostSkillError("SKILL_PIN_UNAVAILABLE"),
                "world_last30days_skill_pin_failed",
            ),
            (
                HostSkillError("STAGE_RUNNER_FAILED"),
                "world_last30days_stage_failed",
            ),
            (
                HostSkillError("SKILL_STAGE_FAILED"),
                "world_last30days_stage_failed",
            ),
            (
                HostSkillError("STAGE_TIMEOUT"),
                "world_last30days_stage_failed",
            ),
            (
                HostSkillError("STAGE_OUTPUT_LIMIT"),
                "world_last30days_stage_failed",
            ),
            (
                HostSkillError("SPAWN_FAILED"),
                "world_last30days_stage_failed",
            ),
            (
                HostSkillError("PYTHON_VERSION_UNSUPPORTED"),
                "world_last30days_stage_failed",
            ),
            (
                HostSkillError("SKILL_CONTRACT_FAILED"),
                "world_last30days_contract_failed",
            ),
            (
                HostSkillError("MODEL_CALLBACK_FAILED"),
                "world_last30days_model_failed",
            ),
            (
                HostWorldError("LAST30DAYS_OUTPUT_INVALID"),
                "world_last30days_output_invalid",
            ),
            (HostSkillError("PRIVATE_TOKEN_DO_NOT_LEAK"), None),
        )
        for error, diagnostic in failures:
            with self.subTest(diagnostic=diagnostic):
                result, captured, _, _ = self._run_through_real_core(
                    skill_result=None, skill_error=error
                )
                self.assertIn("world_last30days_failed", result.case_set.reasons)
                self.assertIs(result.case_set.raw_input, self.raw_input)
                self.assertIs(captured[0].raw_input, self.raw_input)
                if diagnostic is not None:
                    self.assertIn(diagnostic, result.case_set.reasons)
                else:
                    self.assertFalse(
                        any(
                            reason.startswith("world_last30days_")
                            and reason != "world_last30days_failed"
                            for reason in result.case_set.reasons
                        )
                    )
                self.assertNotIn(str(error), repr(result.case_set.reasons))
                self.assertNotIn("PRIVATE_TOKEN_DO_NOT_LEAK", repr(result.case_set.reasons))

    def test_last30days_model_diagnostics_keep_closed_code_and_phase_without_leakage(self):
        class PhaseStr(str):
            pass

        cases = (
            (
                "MODEL_CALLBACK_FAILED",
                "judgments",
                "world_last30days_model_callback_failed",
                "world_last30days_model_phase_judgments",
                "world_last30days_model_failed",
            ),
            (
                "MODEL_OUTPUT_INVALID",
                "angles",
                "world_last30days_model_output_invalid",
                "world_last30days_model_phase_angles",
                "world_last30days_model_failed",
            ),
            (
                "MODEL_CALLBACK_FAILED",
                "PRIVATE_PHASE_DO_NOT_LEAK",
                "world_last30days_model_callback_failed",
                None,
                "world_last30days_model_failed",
            ),
            (
                "MODEL_OUTPUT_INVALID",
                PhaseStr("judgments"),
                "world_last30days_model_output_invalid",
                None,
                "world_last30days_model_failed",
            ),
            (
                "SKILL_STAGE_FAILED",
                "judgments",
                None,
                None,
                "world_last30days_stage_failed",
            ),
        )
        for code, phase, code_diagnostic, phase_diagnostic, coarse_diagnostic in cases:
            with self.subTest(code=code, phase=phase):
                self.grounder_calls.clear()
                self.grounder_query_calls.clear()
                error = HostSkillError(code, phase=phase)
                result, captured, discovery_calls, semantic_calls = (
                    self._run_through_real_core(
                        skill_result=None, skill_error=error
                    )
                )
                reasons = result.case_set.reasons
                self.assertIn("world_last30days_failed", reasons)
                self.assertIn(coarse_diagnostic, reasons)
                self.assertIn("world_native_scope_fallback", reasons)
                if code_diagnostic is not None:
                    self.assertIn(code_diagnostic, reasons)
                if phase_diagnostic is not None:
                    self.assertIn(phase_diagnostic, reasons)
                else:
                    self.assertFalse(
                        any("model_phase_" in reason for reason in reasons)
                    )
                self.assertNotIn("PRIVATE_PHASE_DO_NOT_LEAK", repr(reasons))
                self.assertEqual(len(self.grounder_calls), 1)
                self.assertEqual(len(self.grounder_query_calls), 1)
                self.assertEqual(len(captured), 1)
                self.assertEqual(discovery_calls, [])
                self.assertEqual(semantic_calls, [])

    def test_hidden_skill_model_transport_context_is_closed_and_query_uses_template(self):
        def hidden_skill_error(code, *, status=None):
            try:
                raise ModelTransportError(code, status=status)
            except ModelTransportError:
                try:
                    raise HostGrounderRuntimeError("DISCOVERY_CALL_FAILED") from None
                except HostGrounderRuntimeError:
                    try:
                        raise HostSkillError("MODEL_CALLBACK_FAILED") from None
                    except HostSkillError as error:
                        return error

        error = hidden_skill_error("HTTP_ERROR", status=503)
        self.assertTrue(error.__suppress_context__)
        self.assertIs(type(error.__context__), HostGrounderRuntimeError)
        self.assertTrue(error.__context__.__suppress_context__)
        self.assertIs(type(error.__context__.__context__), ModelTransportError)

        result, captured, discovery_calls, semantic_calls = self._run_through_real_core(
            skill_result=None, skill_error=error
        )
        self.assertIn("world_last30days_failed", result.case_set.reasons)
        self.assertIn("world_last30days_model_failed", result.case_set.reasons)
        self.assertIn("world_model_http_error", result.case_set.reasons)
        self.assertNotIn("503", repr(result.case_set.reasons))
        self.assertEqual(
            self.grounder_query_calls,
            [_expected_world_source_query(self.raw_input, self.config.evaluation_date)],
        )
        self.assertIs(self.grounder_calls[0][0], self.raw_input)
        self.assertIs(captured[0].raw_input, self.raw_input)
        self.assertEqual(discovery_calls, [])
        self.assertEqual(semantic_calls, [])

        self.grounder_query_calls.clear()
        self.grounder_calls.clear()
        unknown = hidden_skill_error("PRIVATE_TOKEN_DO_NOT_LEAK")
        result, _, _, _ = self._run_through_real_core(
            skill_result=None, skill_error=unknown
        )
        self.assertIn("world_last30days_failed", result.case_set.reasons)
        self.assertIn("world_last30days_model_failed", result.case_set.reasons)
        self.assertFalse(any(reason.startswith("world_model_") for reason in result.case_set.reasons))
        self.assertNotIn("PRIVATE_TOKEN_DO_NOT_LEAK", repr(result.case_set.reasons))
        self.assertEqual(
            self.grounder_query_calls,
            [_expected_world_source_query(self.raw_input, self.config.evaluation_date)],
        )
        self.assertIs(self.grounder_calls[0][0], self.raw_input)

    def test_model_transport_context_diagnostics_are_exact_type_closed_and_bounded(self):
        expected = {
            "REQUEST_TOO_LARGE": "world_model_request_too_large",
            "RESPONSE_TOO_LARGE": "world_model_response_too_large",
            "TRUNCATED_RESPONSE": "world_model_truncated_response",
            "TOKEN_BUDGET_EXCEEDED": "world_model_token_budget_exceeded",
            "TIMEOUT": "world_model_timeout",
            "NETWORK_ERROR": "world_model_network_error",
            "HTTP_ERROR": "world_model_http_error",
            "AUTHENTICATION_FAILED": "world_model_authentication_failed",
            "MALFORMED_JSON": "world_model_malformed_json",
            "MALFORMED_RESPONSE": "world_model_malformed_response",
        }
        for code, diagnostic in expected.items():
            with self.subTest(code=code):
                outer = HostSkillError("MODEL_CALLBACK_FAILED")
                outer.__context__ = ModelTransportError(code)
                self.assertEqual(
                    _world_model_transport_diagnostic(outer), diagnostic
                )

        class PoisonedModelTransportError(ModelTransportError):
            def __getattribute__(self, name):
                if name in {"code", "__context__"}:
                    raise AssertionError("untrusted exception attribute was accessed")
                return super().__getattribute__(name)

        poisoned = HostSkillError("MODEL_CALLBACK_FAILED")
        poisoned.__context__ = PoisonedModelTransportError("HTTP_ERROR")
        self.assertIsNone(_world_model_transport_diagnostic(poisoned))

        missing_code = ModelTransportError.__new__(ModelTransportError)
        outer = HostSkillError("MODEL_CALLBACK_FAILED")
        outer.__context__ = missing_code
        self.assertIsNone(_world_model_transport_diagnostic(outer))

        first = HostSkillError("MODEL_CALLBACK_FAILED")
        second = HostGrounderRuntimeError("DISCOVERY_CALL_FAILED")
        first.__context__ = second
        second.__context__ = first
        self.assertIsNone(_world_model_transport_diagnostic(first))

        bounded_chain = [
            HostSkillError("MODEL_CALLBACK_FAILED"),
            HostGrounderRuntimeError("DISCOVERY_CALL_FAILED"),
            HostGrounderRuntimeError("DISCOVERY_CALL_FAILED"),
            HostGrounderRuntimeError("DISCOVERY_CALL_FAILED"),
            ModelTransportError("HTTP_ERROR"),
        ]
        for outer, inner in zip(bounded_chain, bounded_chain[1:]):
            outer.__context__ = inner
        self.assertIsNone(_world_model_transport_diagnostic(bounded_chain[0]))

    def test_invalid_domain_is_rejected_before_callbacks_and_empty_world_fallback(self):
        self.raw_input = "x" * 401
        self.submissions = ()
        callback_calls = {"stage": 0, "model": 0}

        def fail_if_called(name):
            callback_calls[name] += 1
            raise AssertionError("{} callback must not run".format(name))

        def stage_runner(*_args, **_kwargs):
            fail_if_called("stage")

        def model_callback(*_args, **_kwargs):
            fail_if_called("model")

        with self.assertRaises(HostSkillError) as caught:
            real_run_last30days_discovery(
                None,
                self.raw_input,
                model_callback,
                stage_runner=stage_runner,
            )
        self.assertEqual(len(self.raw_input), 401)
        self.assertEqual(caught.exception.code, "INVALID_DOMAIN")
        self.assertEqual(callback_calls, {"stage": 0, "model": 0})

        # Exercise World's HostSkill error mapping with an otherwise valid
        # formatted query; both query limits now include template overhead.
        self.raw_input = "x" * 100
        result, captured, discovery_calls, semantic_calls = self._run_through_real_core(
            skill_result=None, skill_error=caught.exception
        )
        self.assertEqual(result.case_set.status, "COMPLETE")
        self.assertIs(result.case_set.raw_input, self.raw_input)
        self.assertIn("world_last30days_failed", result.case_set.reasons)
        self.assertIn("world_last30days_input_invalid", result.case_set.reasons)
        self.assertIn("world_grounder_no_submission", result.case_set.reasons)
        self.assertEqual(result.case_set.submissions.submissions, ())
        self.assertEqual(result.case_set.cases, ())
        self.assertEqual(len(result.case_set.unavailable), 1)
        self.assertEqual(
            result.case_set.unavailable[0].reasons, ("world_unit_no_submission",)
        )
        self.assertEqual(captured[0].submissions, ())
        self.assertEqual(len(self.grounder_calls), 1)
        self.assertIs(self.grounder_calls[0][0], self.raw_input)
        self.assertEqual(discovery_calls, [])
        self.assertEqual(semantic_calls, [])

    def test_native_partial_diagnostics_preserve_generic_reasons(self):
        self.config = replace(
            self.config,
            skill=replace(
                self.config.skill,
                source_allowlist=("reddit", "x", "hackernews", "digg"),
            ),
        )
        native = _native_result(
            [],
            outcome="incomplete",
            source_status={
                "reddit": {"state": "rate-limited"},
                "x": {},
                "hackernews": {"state": "ok"},
                "digg": {"state": "unavailable"},
            },
        )
        result, _captured, _discovery, _semantic = self._run_through_real_core(
            skill_result=native
        )
        reasons = result.case_set.reasons
        self.assertEqual(result.case_set.status, "COMPLETE")
        self.assertIn("world_last30days_partial", reasons)
        self.assertIn("world_last30days_empty", reasons)
        self.assertIn("world_last30days_native_outcome_not_ok", reasons)
        self.assertIn("world_last30days_native_source_reddit_not_ok", reasons)
        self.assertIn("world_last30days_native_source_x_unknown", reasons)
        self.assertNotIn("world_last30days_native_source_hackernews_unknown", reasons)
        self.assertNotIn("world_last30days_native_source_hackernews_not_ok", reasons)
        self.assertIn("world_last30days_native_source_digg_not_ok", reasons)
        self.assertLess(
            reasons.index("world_last30days_partial"),
            reasons.index("world_last30days_native_outcome_not_ok"),
        )
        self.assertLess(
            reasons.index("world_last30days_native_source_reddit_not_ok"),
            reasons.index("world_last30days_empty"),
        )

    def test_malicious_native_details_and_unallowlisted_sources_do_not_leak(self):
        secret_state = "SECRET_RAW_PROVIDER_STATE"
        secret_source = "SECRET_EXTRA_SOURCE_NAME"
        secret_url = "https://secret.example/private?q=token"
        native = _native_result(
            [_topic("lead", secret_url, rank=1, score=1, angle="x")],
            outcome="SECRET_RAW_OUTCOME",
            source_status={
                "reddit": {"state": secret_state},
                "x": {"state": "provider-error-detail"},
                secret_source: {"state": secret_state},
            },
        )
        result, _captured, _discovery, _semantic = self._run_through_real_core(
            skill_result=native
        )
        reasons_repr = repr(result.case_set.reasons)
        self.assertIn("world_last30days_native_outcome_not_ok", reasons_repr)
        self.assertIn("world_last30days_native_source_reddit_not_ok", reasons_repr)
        self.assertNotIn("world_last30days_native_source_x_", reasons_repr)
        self.assertNotIn("world_last30days_native_source_unknown", reasons_repr)
        for raw_detail in (
            secret_state,
            secret_source,
            secret_url,
            "SECRET_RAW_OUTCOME",
            "provider-error-detail",
        ):
            self.assertNotIn(raw_detail, reasons_repr)

        malformed = _native_result(
            [], outcome="ok", source_status="SECRET_MALFORMED_SOURCE_STATUS"
        )
        malformed_result, _captured, _discovery, _semantic = (
            self._run_through_real_core(skill_result=malformed)
        )
        self.assertIn(
            "world_last30days_native_source_reddit_unknown",
            malformed_result.case_set.reasons,
        )
        self.assertNotIn(
            "SECRET_MALFORMED_SOURCE_STATUS",
            repr(malformed_result.case_set.reasons),
        )

    def test_native_diagnostic_reasons_survive_store_save_reopen(self):
        native = _native_result(
            [_topic("lead", "https://lead.example/1", rank=1, score=1, angle="x")],
            outcome="partial",
        )
        native_report = json.loads(native.provider_native.raw_json.decode())
        del native_report["source_status"]
        native = replace(
            native,
            provider_native=ProviderNativeOutput(
                json.dumps(native_report, separators=(",", ":")).encode(), None
            ),
        )
        result, _captured, _discovery, _semantic = self._run_through_real_core(
            skill_result=native
        )
        reopened_summary = _persist_world_result(self.raw_input, self.post_bounds, result)
        self.assertIn("world_last30days_partial", reopened_summary["reasons"])
        self.assertIn("world_last30days_native_outcome_not_ok", reopened_summary["reasons"])
        self.assertIn("world_last30days_native_source_reddit_unknown", reopened_summary["reasons"])
        self.assertEqual(tuple(reopened_summary["reasons"]), result.case_set.reasons)

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
        self.assertEqual(result.case_set.status, "COMPLETE")
        self.assertIn("world_grounding_input_limit", result.case_set.reasons)
        self.assertEqual(
            result.case_set.unavailable[0].reasons,
            ("world_unit_input_invalid",),
        )
        self.assertEqual(captured[0].submissions, ())
        self.assertEqual(self.grounder_calls, [])
        self.assertIs(result.case_set.raw_input, self.raw_input)
        _validate_batch_result(
            result, ValidatedRunRequest("world", self.raw_input, self.post_bounds)
        )
        saved = _persist_world_result(self.raw_input, self.post_bounds, result)
        self.assertIn("world_grounding_input_limit", saved["reasons"])

    def test_grounder_empty_and_failure_retain_no_source_reasons(self):
        skill = _native_result([_topic("lead", "https://lead.example/1", rank=1, score=1, angle="x")])

        class PoisonedCodeError(RuntimeError):
            @property
            def code(self):
                raise AssertionError("unallowlisted code property was accessed")

        class DiagnosticString(str):
            pass

        private_url_sentinel = "https://private.invalid/PRIVATE_URL_SENTINEL"
        tampered_code = HostGrounderRuntimeError("DISCOVERY_RESPONSE_INVALID")
        object.__setattr__(tampered_code, "code", private_url_sentinel)
        object.__setattr__(tampered_code, "args", (private_url_sentinel,))
        subclassed_code = HostGrounderRuntimeError("DISCOVERY_RESPONSE_INVALID")
        object.__setattr__(
            subclassed_code,
            "code",
            DiagnosticString("DISCOVERY_RESPONSE_INVALID"),
        )
        object.__setattr__(subclassed_code, "args", (private_url_sentinel,))
        tampered_check = HostGrounderRuntimeError(
            "PRODUCER_ENVELOPE_INVALID",
            failure_stage="producer_envelope_normalization",
            failure_check="producer_wire_normalization",
        )
        object.__setattr__(tampered_check, "failure_check", private_url_sentinel)
        object.__setattr__(tampered_check, "args", (private_url_sentinel,))
        subclassed_check = HostGrounderRuntimeError(
            "PRODUCER_ENVELOPE_INVALID",
            failure_stage="producer_envelope_normalization",
            failure_check="producer_wire_normalization",
        )
        object.__setattr__(
            subclassed_check,
            "failure_check",
            DiagnosticString("producer_wire_normalization"),
        )
        object.__setattr__(subclassed_check, "args", (private_url_sentinel,))
        catalog_limit_failure = HostGrounderRuntimeError(
            "EVIDENCE_CATALOG_INVALID"
        )
        object.__setattr__(
            catalog_limit_failure,
            "_evidence_catalog_failure_check",
            "ENTRY_LIMIT",
        )
        tampered_catalog_check = HostGrounderRuntimeError(
            "EVIDENCE_CATALOG_INVALID"
        )
        object.__setattr__(
            tampered_catalog_check,
            "_evidence_catalog_failure_check",
            private_url_sentinel,
        )
        subclassed_catalog_check = HostGrounderRuntimeError(
            "EVIDENCE_CATALOG_INVALID"
        )
        object.__setattr__(
            subclassed_catalog_check,
            "_evidence_catalog_failure_check",
            DiagnosticString("ENTRY_LIMIT"),
        )
        subclassed_stage = HostGrounderRuntimeError(
            "PRODUCER_ENVELOPE_INVALID",
            failure_stage="producer_envelope_normalization",
            failure_check="producer_wire_normalization",
        )
        object.__setattr__(
            subclassed_stage,
            "failure_stage",
            DiagnosticString("producer_envelope_normalization"),
        )
        object.__setattr__(subclassed_stage, "args", (private_url_sentinel,))

        class DerivedGrounderError(HostGrounderRuntimeError):
            pass

        derived_grounder_error = DerivedGrounderError("DISCOVERY_RESPONSE_INVALID")
        object.__setattr__(derived_grounder_error, "args", (private_url_sentinel,))

        hidden_grounder_failure = None
        try:
            raise ModelTransportError("RESPONSE_TOO_LARGE", status=413)
        except ModelTransportError:
            try:
                raise HostGrounderRuntimeError("DISCOVERY_CALL_FAILED") from None
            except HostGrounderRuntimeError as caught_grounder_failure:
                hidden_grounder_failure = caught_grounder_failure
                self.assertTrue(caught_grounder_failure.__suppress_context__)
                self.assertIs(
                    type(caught_grounder_failure.__context__), ModelTransportError
                )

        failures = (
            ("empty", None),
            ("failed", None),
            (
                HostGrounderRuntimeError("SEMANTIC_CALL_FAILED"),
                "world_grounder_model_call_failed",
            ),
            (
                HostGrounderRuntimeError("DISCOVERY_RESPONSE_INVALID"),
                (
                    "world_grounder_output_invalid",
                    "world_grounder_discovery_response_invalid",
                ),
            ),
            (
                HostGrounderRuntimeError("EVIDENCE_CATALOG_INVALID"),
                (
                    "world_grounder_output_invalid",
                    "world_grounder_evidence_catalog_invalid",
                ),
            ),
            (
                catalog_limit_failure,
                (
                    "world_grounder_output_invalid",
                    "world_grounder_evidence_catalog_invalid",
                    "world_grounder_catalog_entry_limit",
                ),
            ),
            (hidden_grounder_failure, "world_model_response_too_large"),
            (
                HostGrounderRuntimeError("NO_SEARCH_RESULTS"),
                "world_grounder_no_search_results",
            ),
            (
                HostGrounderRuntimeError("EXTRACTION_FAILURE"),
                "world_grounder_extraction_failed",
            ),
            (
                TavilyTransportError("HTTP_ERROR", status=503),
                "world_grounder_source_transport_failed",
            ),
            (
                TavilyTransportError("NETWORK_ERROR"),
                "world_grounder_source_transport_failed",
            ),
            (
                TavilyTransportError("TIMEOUT"),
                "world_grounder_source_transport_failed",
            ),
            (
                TavilyTransportError("TRANSPORT_FAILED"),
                "world_grounder_source_transport_failed",
            ),
            (
                TavilyTransportError("UNKNOWN_RESPONSE_FIELD"),
                "world_grounder_source_response_invalid",
            ),
            (
                TavilyTransportError("MALFORMED_RESPONSE"),
                "world_grounder_source_response_invalid",
            ),
            (
                TavilyTransportError("MALFORMED_JSON"),
                "world_grounder_source_response_invalid",
            ),
            (
                TavilyTransportError("REQUEST_BUDGET_EXHAUSTED"),
                "world_grounder_source_budget_failed",
            ),
            (
                TavilyTransportError("CREDIT_BUDGET_EXHAUSTED"),
                "world_grounder_source_budget_failed",
            ),
            (
                TavilyTransportError("BYTE_BUDGET_EXHAUSTED"),
                "world_grounder_source_budget_failed",
            ),
            (
                TavilyTransportError("TIME_BUDGET_EXHAUSTED"),
                "world_grounder_source_budget_failed",
            ),
            (TavilyTransportError("PRIVATE_TOKEN_DO_NOT_LEAK"), None),
            (HostGrounderRuntimeError("PRIVATE_TOKEN_DO_NOT_LEAK"), None),
            (PoisonedCodeError("PRIVATE_EXCEPTION_MESSAGE"), None),
        )
        producer_checks = (
            ("producer_wire_normalization", "world_grounder_producer_wire_normalization_failed"),
            ("producer_run_stage_binding", "world_grounder_producer_run_stage_binding_failed"),
            ("producer_coverage_order", "world_grounder_producer_coverage_order_failed"),
            ("producer_binding_extraction", "world_grounder_producer_binding_extraction_failed"),
            ("producer_v0_3_wire_decode", "world_grounder_producer_v0_3_wire_decode_failed"),
            ("producer_v0_3_root_shape", "world_grounder_producer_v0_3_root_shape_failed"),
            ("producer_v0_3_catalog_source_validation", "world_grounder_producer_v0_3_catalog_source_validation_failed"),
            ("producer_v0_3_claims_catalog_expansion", "world_grounder_producer_v0_3_claims_catalog_expansion_failed"),
            ("producer_v0_3_bindings_catalog_expansion", "world_grounder_producer_v0_3_bindings_catalog_expansion_failed"),
            ("producer_v0_3_canonical_size", "world_grounder_producer_v0_3_canonical_size_failed"),
            ("producer_v0_3_internal_v0_1_schema", "world_grounder_producer_v0_3_internal_v0_1_schema_failed"),
            ("producer_v0_3_recanonicalization", "world_grounder_producer_v0_3_recanonicalization_failed"),
            ("producer_v0_3_json_format", "world_grounder_producer_v0_3_json_format_failed"),
            ("producer_v0_3_closed_shape", "world_grounder_producer_v0_3_closed_shape_failed"),
            ("producer_v0_3_required_binding_omission_v0_9", "world_grounder_producer_v0_3_required_binding_omission_v0_9_failed"),
            ("producer_v0_3_binding_omission_repair_delta", "world_grounder_producer_v0_3_binding_omission_repair_delta_failed"),
        )
        producer_check_failures = tuple(
            (
                HostGrounderRuntimeError(
                    "PRODUCER_ENVELOPE_INVALID",
                    failure_stage="producer_envelope_normalization",
                    failure_check=check,
                ),
                (
                    "world_grounder_output_invalid",
                    "world_grounder_producer_envelope_invalid",
                    check_reason,
                ),
            )
            for check, check_reason in producer_checks
        )
        tampered_failures = (
            (tampered_code, None),
            (subclassed_code, None),
            (
                tampered_check,
                (
                    "world_grounder_output_invalid",
                    "world_grounder_producer_envelope_invalid",
                ),
                ("world_grounder_producer_wire_normalization_failed",),
            ),
            (
                subclassed_check,
                (
                    "world_grounder_output_invalid",
                    "world_grounder_producer_envelope_invalid",
                ),
                ("world_grounder_producer_wire_normalization_failed",),
            ),
            (
                tampered_catalog_check,
                (
                    "world_grounder_output_invalid",
                    "world_grounder_evidence_catalog_invalid",
                ),
                (
                    "world_grounder_catalog_source_count_limit",
                    "world_grounder_catalog_paragraph_limit",
                    "world_grounder_catalog_entry_limit",
                    "world_grounder_catalog_byte_limit",
                    "world_grounder_catalog_empty",
                    "world_grounder_catalog_hash_invalid",
                    "world_grounder_catalog_unknown",
                ),
            ),
            (
                subclassed_catalog_check,
                (
                    "world_grounder_output_invalid",
                    "world_grounder_evidence_catalog_invalid",
                ),
                (
                    "world_grounder_catalog_source_count_limit",
                    "world_grounder_catalog_paragraph_limit",
                    "world_grounder_catalog_entry_limit",
                    "world_grounder_catalog_byte_limit",
                    "world_grounder_catalog_empty",
                    "world_grounder_catalog_hash_invalid",
                    "world_grounder_catalog_unknown",
                ),
            ),
            (
                subclassed_stage,
                (
                    "world_grounder_output_invalid",
                    "world_grounder_producer_envelope_invalid",
                ),
                ("world_grounder_producer_wire_normalization_failed",),
            ),
            (derived_grounder_error, None),
        )
        specific_reason_values = (
            "world_grounder_discovery_response_invalid",
            "world_grounder_producer_envelope_invalid",
            "world_grounder_evidence_catalog_invalid",
            "world_grounder_catalog_source_count_limit",
            "world_grounder_catalog_paragraph_limit",
            "world_grounder_catalog_entry_limit",
            "world_grounder_catalog_byte_limit",
            "world_grounder_catalog_empty",
            "world_grounder_catalog_hash_invalid",
            "world_grounder_catalog_unknown",
            *(reason for _check, reason in producer_checks),
        )
        for failure_case in failures + producer_check_failures + tampered_failures:
            failure, diagnostic = failure_case[:2]
            forbidden_diagnostics = failure_case[2] if len(failure_case) > 2 else ()
            self.grounder_calls.clear()
            self.grounder_query_calls.clear()

            def fake_factory(_config, **_kwargs):
                def grounder(text, *, run_id, bounds):
                    self.grounder_calls.append(text)
                    if isinstance(failure, Exception):
                        raise failure
                    if failure == "failed":
                        raise RuntimeError("synthetic hidden failure")
                    event_input = UserEventInput(text)
                    return SimpleNamespace(
                        build_result=SimpleNamespace(
                            raw_input=event_input,
                            source_batch=SourceSubmissionBatch(event_input, ()),
                        )
                    )

                def world_source_query_factory(query, *, seed_urls=()):
                    self.grounder_query_calls.append(query)
                    return grounder

                grounder._world_source_query_factory = world_source_query_factory
                grounder.configuration_snapshot = lambda: {
                    "models": [], "sources": [], "skills": []
                }
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
            self.assertIs(type(result), host_world_module.CoreRunResult)
            self.assertEqual(result.case_set.status, "COMPLETE")
            self.assertEqual(result.case_set.cases, ())
            self.assertEqual(len(result.case_set.unavailable), 1)
            self.assertIn(
                "world_grounder_no_submission" if failure == "empty" else "world_grounder_failed",
                result.case_set.reasons,
            )
            self.assertIs(result.case_set.raw_input, self.raw_input)
            self.assertEqual(
                self.grounder_query_calls,
                [
                    _expected_world_unit_query(
                        self.raw_input, self.config.evaluation_date, ["lead"]
                    )
                ],
            )
            if diagnostic is not None:
                expected_diagnostics = (
                    diagnostic if type(diagnostic) is tuple else (diagnostic,)
                )
                for expected_diagnostic in expected_diagnostics:
                    self.assertIn(expected_diagnostic, result.case_set.reasons)
            for forbidden_diagnostic in forbidden_diagnostics:
                self.assertNotIn(forbidden_diagnostic, result.case_set.reasons)
            if failure is hidden_grounder_failure:
                self.assertIn(
                    "world_grounder_model_call_failed", result.case_set.reasons
                )
            elif diagnostic is None and isinstance(failure, Exception):
                self.assertFalse(
                    any(
                        reason in result.case_set.reasons
                        for reason in (
                            "world_grounder_model_call_failed",
                            "world_grounder_output_invalid",
                            "world_grounder_no_search_results",
                            "world_grounder_extraction_failed",
                            "world_grounder_source_transport_failed",
                            "world_grounder_source_response_invalid",
                            "world_grounder_source_budget_failed",
                            *specific_reason_values,
                        )
                    )
                )
            if isinstance(failure, Exception):
                self.assertNotIn(str(failure), repr(result.case_set.reasons))
            self.assertNotIn("PRIVATE_TOKEN_DO_NOT_LEAK", repr(result.case_set.reasons))
            self.assertNotIn(private_url_sentinel, repr(result.case_set.reasons))
            self.assertEqual(result.case_set.submissions.submissions, ())

    def test_unit_failures_keep_only_their_own_diagnostics_through_archive_and_api(self):
        self.config = _config(model_budget=3, source_budget=4)
        skill = _native_result(
            [
                _topic("Beta lead", "https://lead.example/b", rank=2, score=2, angle="y"),
                _topic("Alpha lead", "https://lead.example/a", rank=1, score=1, angle="x"),
            ]
        )
        catalog_failure = HostGrounderRuntimeError("EVIDENCE_CATALOG_INVALID")
        object.__setattr__(catalog_failure, "_evidence_catalog_failure_check", "PARAGRAPH_LIMIT")
        producer_failure = HostGrounderRuntimeError(
            "PRODUCER_ENVELOPE_INVALID",
            failure_stage="producer_envelope_normalization",
            failure_check="producer_v0_3_root_shape",
        )
        failures = (catalog_failure, producer_failure)
        grounder_calls = []
        query_calls = []

        def failing_grounder_factory(_config, **_kwargs):
            def grounder(text, *, run_id, bounds):
                index = len(grounder_calls)
                grounder_calls.append((text, run_id, bounds))
                raise failures[index]

            def query_factory(query, *, seed_urls=()):
                query_calls.append(query)
                return grounder

            grounder._world_source_query_factory = query_factory
            return grounder

        with mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            side_effect=failing_grounder_factory,
        ), mock.patch(
            "convexity_hunter.host_world.run_last30days_discovery",
            return_value=skill,
        ), mock.patch.object(
            ModelCredential, "resolve", return_value="synthetic-token"
        ):
            runner = create_world_runner(
                self.config, repo_root=ROOT, market_bridge=self.lazy_bridge
            )
            result = runner(self.raw_input, bounds=self.post_bounds)

        expected_reasons = (
            (
                "world_unit_grounder_failed",
                "world_grounder_output_invalid",
                "world_grounder_evidence_catalog_invalid",
                "world_grounder_catalog_paragraph_limit",
            ),
            (
                "world_unit_grounder_failed",
                "world_grounder_output_invalid",
                "world_grounder_producer_envelope_invalid",
                "world_grounder_producer_v0_3_root_shape_failed",
            ),
        )
        self.assertEqual(len(query_calls), 2)
        self.assertEqual(len(grounder_calls), 2)
        self.assertEqual(
            tuple(item.reasons for item in result.case_set.unavailable),
            expected_reasons,
        )
        self.assertNotIn(
            "world_grounder_producer_envelope_invalid",
            result.case_set.unavailable[0].reasons,
        )
        self.assertNotIn(
            "world_grounder_evidence_catalog_invalid",
            result.case_set.unavailable[1].reasons,
        )
        self.assertTrue(
            set(code for reasons in expected_reasons for code in reasons[1:]).issubset(
                set(result.case_set.reasons)
            )
        )

        archived = _persist_world_result(self.raw_input, self.post_bounds, result)
        public_summary = _public_batch_summary(archived)
        self.assertEqual(
            tuple(tuple(item["reasons"]) for item in archived["unavailable_cases"]),
            expected_reasons,
        )
        self.assertEqual(
            tuple(tuple(item["reasons"]) for item in public_summary["unavailable_cases"]),
            expected_reasons,
        )

    def test_capacity_preflight_and_core_hypothesis_limit_are_all_or_none(self):
        empty_capacity = _config(bounds=CoreOperationalBounds(0, 8, 400, 200, 10))
        with mock.patch("convexity_hunter.host_world.create_event_grounder", side_effect=self._fake_grounder), \
                mock.patch("convexity_hunter.host_world.run_last30days_discovery", side_effect=AssertionError("Skill must not run")):
            runner = create_world_runner(empty_capacity, repo_root=ROOT, market_bridge=self.lazy_bridge)
            result = runner(self.raw_input, bounds=empty_capacity.bounds)
        self.assertEqual(result.case_set.status, "BLOCKED")
        self.assertIn("world_operational_capacity_zero", result.case_set.reasons)
        self.assertEqual(self.grounder_calls, [])

        limited = _config(
            bounds=CoreOperationalBounds(4, 1, 400, 200, 10),
            model_budget=3,
            source_budget=4,
        )
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
        self.assertEqual(result.case_set.status, "LIMIT_EXCEEDED")
        self.assertEqual(
            result.case_set.reasons, ("LIMIT_EXCEEDED", "hypotheses:2>1")
        )
        self.assertEqual(len(self.grounder_calls), 2)
        self.assertEqual(result.case_set.unavailable, ())
        self.assertEqual(len(result.case_set.submissions.submissions), 2)
        saved_summary = _persist_world_result(
            self.raw_input, limited.bounds, result
        )
        self.assertEqual(
            saved_summary["reasons"], ["LIMIT_EXCEEDED", "hypotheses:2>1"]
        )

    def test_raw_native_persistence_is_rejected_at_factory(self):
        config = _config(final_output_path=pathlib.Path("/tmp/native.json"))
        with self.assertRaises(HostWorldError) as raised:
            create_world_runner(config, repo_root=ROOT, market_bridge=self.lazy_bridge)
        self.assertEqual(raised.exception.code, "NATIVE_PERSISTENCE_FORBIDDEN")

    def test_mixed_unit_preflight_failures_keep_their_own_reasons(self):
        base_config = _config(model_budget=3, source_budget=4)
        self.config = replace(
            base_config,
            grounder=replace(
                base_config.grounder,
                run_input_bounds=HostGrounderRunInputBounds(100_000, 400, 20),
            ),
        )
        skill = _native_result(
            [
                _topic(
                    "Alpha " + ("x" * 300),
                    "https://lead.example/alpha",
                    rank=1,
                    score=1,
                    angle="x",
                ),
                _topic(
                    "Zulu",
                    "https://lead.example/" + ("u" * 500),
                    rank=2,
                    score=2,
                    angle="y",
                ),
            ]
        )
        result, captured, _, _ = self._run_through_real_core(skill_result=skill)

        self.assertEqual(self.grounder_calls, [])
        self.assertEqual(captured[0].submissions, ())
        self.assertEqual(
            tuple(item.reasons for item in result.case_set.unavailable),
            (
                ("world_unit_source_query_invalid",),
                ("world_unit_input_invalid",),
            ),
        )
        self.assertIn("world_unit_source_query_invalid", result.case_set.reasons)
        self.assertIn("world_unit_input_invalid", result.case_set.reasons)
        saved = _persist_world_result(self.raw_input, self.post_bounds, result)
        self.assertEqual(
            tuple(tuple(item["reasons"]) for item in saved["unavailable_cases"]),
            (
                ("world_unit_source_query_invalid",),
                ("world_unit_input_invalid",),
            ),
        )

    def test_invalid_native_seed_is_rejected_before_that_unit_grounder_call(self):
        self.config = _config(model_budget=3, source_budget=4)
        skill = _native_result(
            [
                _topic(
                    "Alpha private lead",
                    "http://127.0.0.1/private",
                    rank=1,
                    score=1,
                    angle="x",
                ),
                _topic(
                    "Zulu safe lead",
                    "https://lead.example/safe",
                    rank=2,
                    score=2,
                    angle="y",
                ),
            ]
        )

        result, _captured, _discovery, _semantic = self._run_through_real_core(
            skill_result=skill
        )

        self.assertEqual(len(self.grounder_calls), 1)
        self.assertEqual(
            self.grounder_seed_calls,
            [("https://lead.example/safe",)],
        )
        self.assertIn(
            ("world_unit_source_seed_invalid",),
            tuple(item.reasons for item in result.case_set.unavailable),
        )

    def test_capacity_unavailable_rows_aggregate_without_a_truncated_prefix(self):
        self.config = _config(model_budget=6, source_budget=10)
        skill = _native_result(
            [
                _topic(
                    "Lead {}".format(index),
                    "https://lead.example/{}".format(index),
                    rank=index,
                    score=index,
                    angle="synthetic",
                )
                for index in range(5)
            ]
        )
        bounds = CoreOperationalBounds(1, 1, 1, 1, 5)
        result, _captured, _, _ = self._run_through_real_core(
            skill_result=skill, bounds=bounds
        )

        self.assertEqual(self.grounder_calls, [])
        self.assertIn("world_event_unit_capacity_insufficient", result.case_set.reasons)
        self.assertEqual(len(result.case_set.unavailable), 1)
        self.assertEqual(
            result.case_set.unavailable[0].case_id, "world-units-aggregate"
        )
        self.assertEqual(
            result.case_set.unavailable[0].reasons,
            (
                "world_unit_capacity_insufficient",
                "world_event_units_unprocessed_count:5",
            ),
        )
        saved = _persist_world_result(self.raw_input, bounds, result)
        self.assertEqual(len(saved["unavailable_cases"]), 1)
        self.assertEqual(
            saved["unavailable_cases"][0]["reasons"],
            [
                "world_unit_capacity_insufficient",
                "world_event_units_unprocessed_count:5",
            ],
        )

    def test_two_unit_capacity_matrix_blocks_before_any_grounder_request(self):
        base = _config(model_budget=3, source_budget=4)
        skill = _native_result(
            [
                _topic("Alpha lead", "https://lead.example/a", rank=1, score=1, angle="x"),
                _topic("Beta lead", "https://lead.example/b", rank=2, score=2, angle="y"),
            ]
        )
        scenarios = []

        def with_source(**changes):
            return replace(
                base,
                grounder=replace(
                    base.grounder,
                    source=replace(base.grounder.source, **changes),
                ),
            )

        def with_model(role, budget):
            model_config = getattr(base.grounder, role)
            return replace(
                base,
                grounder=replace(
                    base.grounder,
                    **{role: replace(model_config, request_budget=budget)},
                ),
            )

        scenarios.extend(
            (
                (
                    "max_submissions",
                    base,
                    CoreOperationalBounds(1, 7, 123, 90, 5),
                ),
                ("source_requests", with_source(request_budget=3), self.post_bounds),
                ("source_credits", with_source(credit_budget=3), self.post_bounds),
                ("discovery_model", with_model("discovery_model", 2), self.post_bounds),
                ("semantic_model", with_model("semantic_model", 2), self.post_bounds),
                ("source_byte_budget", with_source(byte_budget=1), self.post_bounds),
                (
                    "source_time_budget",
                    with_source(time_budget_seconds=5e-324),
                    self.post_bounds,
                ),
            )
        )

        for name, config, bounds in scenarios:
            with self.subTest(capacity=name):
                query_factory_calls = []
                source_calls = []
                model_calls = []
                skill_calls = []
                real_factory = host_event_module.create_event_grounder

                def instrumented_factory(grounder_config, **kwargs):
                    callback = real_factory(grounder_config, **kwargs)
                    query_factory = callback._world_source_query_factory

                    def track_query_factory(query, *, seed_urls=()):
                        query_factory_calls.append(query)
                        return query_factory(query, seed_urls=seed_urls)

                    callback._world_source_query_factory = track_query_factory
                    return callback

                def forbidden_transport(calls):
                    def transport(_request, _timeout):
                        calls.append("called")
                        raise AssertionError("capacity preflight must precede transport")

                    return transport

                def native_skill(*_args, **_kwargs):
                    skill_calls.append("called")
                    return skill

                with mock.patch.object(
                    ModelCredential, "resolve", return_value="offline-test-only"
                ), mock.patch(
                    "convexity_hunter.host_world.create_event_grounder",
                    side_effect=instrumented_factory,
                ), mock.patch(
                    "convexity_hunter.host_world.run_last30days_discovery",
                    side_effect=native_skill,
                ):
                    runner = create_world_runner(
                        config,
                        repo_root=ROOT,
                        market_bridge=self.lazy_bridge,
                        source_transport=forbidden_transport(source_calls),
                        discovery_transport=forbidden_transport(model_calls),
                        semantic_transport=forbidden_transport(model_calls),
                    )
                    result = runner(self.raw_input, bounds=bounds)

                self.assertEqual(skill_calls, ["called"])
                self.assertEqual(query_factory_calls, [])
                self.assertEqual(source_calls, [])
                self.assertEqual(model_calls, [])
                self.assertIn("world_event_unit_capacity_insufficient", result.case_set.reasons)
                self.assertEqual(len(result.case_set.unavailable), 2)
                self.assertEqual(
                    tuple(item.reasons for item in result.case_set.unavailable),
                    (
                        ("world_unit_capacity_insufficient",),
                        ("world_unit_capacity_insufficient",),
                    ),
                )

    def test_shared_real_grounder_processes_two_units_with_offline_transports(self):
        from tests.test_host_event import (
            _SyntheticModelTransport,
            _SyntheticSourceTransport,
            _config as event_grounder_config,
            _listing_runtime_wires,
            _listing_source_material,
            _url_source_id,
            _NoNetworkAdmissionClient,
        )

        base_event_config = event_grounder_config()
        event_config = replace(
            base_event_config,
            source=replace(
                base_event_config.source,
                byte_budget=100_000,
                time_budget_seconds=20.0,
            ),
        )
        world_grounder_config = replace(
            event_config,
            source=replace(event_config.source, request_budget=4, credit_budget=4),
            discovery_model=replace(event_config.discovery_model, request_budget=5),
            semantic_model=replace(event_config.semantic_model, request_budget=5),
        )
        self.config = replace(
            _config(model_budget=5, source_budget=4),
            grounder=world_grounder_config,
        )
        skill = _native_result(
            [
                _topic("Beta lead", "https://lead.example/beta", rank=2, score=2, angle="x"),
                _topic("Alpha lead", "https://lead.example/alpha", rank=1, score=1, angle="y"),
            ]
        )
        report = json.loads(skill.provider_native.raw_json.decode("utf-8"))
        leads = host_world_module._native_leads(report)
        run_ids = ("world-unit-run-alpha", "world-unit-run-beta")
        _source_ids, full_source_order, _source_bodies, bodies_by_url = (
            _listing_source_material(run_ids[0], "ACME")
        )
        search_url = full_source_order[0][1]
        source_order = ((_url_source_id(search_url), search_url),)
        discovery_outputs = []
        semantic_outputs = []
        source_bodies_by_url = dict(bodies_by_url)
        for run_id, lead in zip(run_ids, leads):
            unit_input = host_world_module._grounding_input(self.raw_input, (lead,))
            seed_url = lead[1][0]
            source_bodies_by_url[seed_url] = "Fetched source body.\n"
            unit_bodies_by_url = dict(bodies_by_url)
            unit_bodies_by_url[seed_url] = "Fetched source body.\n"
            unit_source_order = source_order + ((_url_source_id(seed_url), seed_url),)
            discovery, semantic, _normalized = _listing_runtime_wires(
                run_id,
                "ACME",
                unit_source_order,
                unit_bodies_by_url,
                event_config,
                raw_input=unit_input,
            )
            discovery_outputs.append(discovery)
            semantic_outputs.append(semantic)

        source_transport = _SyntheticSourceTransport(
            search_order=source_order, body_overrides=source_bodies_by_url
        )
        model_transport = _SyntheticModelTransport(
            discovery_outputs, semantic_outputs
        )
        captured = []

        def core_spy(raw_request, *, source_producer, market_bridge, policy):
            batch = source_producer(raw_request)
            captured.append(batch)
            return real_run_world_core(
                raw_request,
                source_producer=lambda _raw: batch,
                market_bridge=market_bridge,
                policy=policy,
            )

        with mock.patch.dict(
            "os.environ", {"SYNTHETIC_TAVILY_KEY": "offline-test-only"}
        ), mock.patch.object(
            ModelCredential, "resolve", return_value="offline-test-only"
        ), mock.patch(
            "convexity_hunter.host_event._create_source_admission_client",
            return_value=_NoNetworkAdmissionClient(),
        ), mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            wraps=host_event_module.create_event_grounder,
        ) as grounder_factory, mock.patch(
            "convexity_hunter.host_world.run_last30days_discovery",
            return_value=skill,
        ), mock.patch(
            "convexity_hunter.host_world.run_world_core", side_effect=core_spy
        ), mock.patch(
            "convexity_hunter.host_world.uuid.uuid4",
            side_effect=[SimpleNamespace(hex=run_id) for run_id in run_ids],
        ):
            runner = create_world_runner(
                self.config,
                repo_root=ROOT,
                market_bridge=self.lazy_bridge,
                source_transport=source_transport,
                discovery_transport=model_transport,
                semantic_transport=model_transport,
            )
            result = runner(self.raw_input, bounds=self.post_bounds)

        self.assertEqual(len(captured), 1)
        self.assertIs(captured[0].raw_input, self.raw_input)
        self.assertEqual(
            len(captured[0].submissions),
            2,
            "offline Grounder returned no complete pair: reasons={!r}, unavailable={!r}, queries={!r}".format(
                result.case_set.reasons,
                tuple(item.reasons for item in result.case_set.unavailable),
                [payload["query"] for _url, payload in source_transport.calls],
            ),
        )
        self.assertEqual(len(result.case_set.submissions.submissions), 2)
        self.assertEqual(grounder_factory.call_count, 2)
        initial_grounder_config = grounder_factory.call_args_list[0].args[0]
        unit_source_config = grounder_factory.call_args_list[1].args[0].source
        self.assertEqual(
            grounder_factory.call_args_list[1].args[0].discovery_model.request_budget,
            initial_grounder_config.discovery_model.request_budget,
        )
        self.assertEqual(initial_grounder_config.source.byte_budget, 100_000)
        self.assertEqual(unit_source_config.byte_budget, 50_000)
        self.assertEqual(unit_source_config.request_budget, 2)
        self.assertEqual(unit_source_config.credit_budget, 2)
        self.assertEqual(
            unit_source_config.time_budget_seconds, math.nextafter(10.0, 0.0)
        )
        self.assertTrue(
            all(len(submission.hypotheses) == 1 for submission in captured[0].submissions)
        )
        self.assertEqual(
            [payload["query"] for _url, payload in source_transport.calls],
            [
                _expected_world_unit_query(
                    self.raw_input, self.config.evaluation_date, ["Alpha lead"]
                ),
                _expected_world_unit_query(
                    self.raw_input, self.config.evaluation_date, ["Alpha lead"]
                ),
                _expected_world_unit_query(
                    self.raw_input, self.config.evaluation_date, ["Beta lead"]
                ),
                _expected_world_unit_query(
                    self.raw_input, self.config.evaluation_date, ["Beta lead"]
                ),
            ],
        )
        self.assertEqual(
            source_transport.extract_url_orders,
            [
                (leads[0][1][0], search_url),
                (leads[1][1][0], search_url),
            ],
        )
        discovery_messages = [
            call["messages"][1]["content"]
            for call in model_transport.calls
            if call["model"] == event_config.discovery_model.model
        ]
        self.assertEqual(len(discovery_messages), 2)
        self.assertIn("Alpha lead", discovery_messages[0])
        self.assertNotIn("Beta lead", discovery_messages[0])
        self.assertIn("Beta lead", discovery_messages[1])
        self.assertNotIn("Alpha lead", discovery_messages[1])

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

        expanded_budget = _config(model_budget=3)
        with mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            side_effect=grounder_factory,
        ):
            create_world_runner(
                expanded_budget, repo_root=ROOT, market_bridge=self.lazy_bridge
            )
        self.assertEqual(expanded_budget.grounder.discovery_model.request_budget, 3)
        self.assertEqual(captured["config"].discovery_model.request_budget, 2)
        self.assertEqual(captured["config"].semantic_model.request_budget, 1)

    def test_world_uses_the_shared_event_grounder_factory(self):
        self.assertIs(
            host_world_module.create_event_grounder,
            host_event_module.create_event_grounder,
        )
        with mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            wraps=host_event_module.create_event_grounder,
        ) as factory:
            runner = create_world_runner(
                self.config, repo_root=ROOT, market_bridge=self.lazy_bridge
            )

        factory.assert_called_once()
        self.assertTrue(callable(runner))
        snapshot = runner.configuration_snapshot()
        self.assertEqual(
            snapshot["sources"][0]["schema_version"],
            "host-event-source-snapshot-v0.3",
        )
        self.assertEqual(
            set(snapshot),
            {"models", "sources", "skills", "world_source_query_policy"},
        )
        self.assertEqual(
            snapshot["world_source_query_policy"],
            {
                "schema_version": "world-source-query-v0.4",
                "basis": "independent_native_event_units_seed_urls_plus_search",
                "max_characters": 400,
                "full_research_context_preserved": True,
                "evaluation_date": "2026-10-07",
            },
        )
        self.assertEqual(
            [model["request_budget"] for model in snapshot["models"]],
            [
                self.config.grounder.discovery_model.request_budget,
                self.config.grounder.semantic_model.request_budget,
            ],
        )
        self.assertEqual(
            snapshot["sources"][0]["request_budget"],
            self.config.grounder.source.request_budget,
        )
        self.assertEqual(
            snapshot["sources"][0]["credit_budget"],
            self.config.grounder.source.credit_budget,
        )
        allocated = factory.call_args.args[0]
        self.assertEqual(allocated.discovery_model.request_budget, 1)
        self.assertEqual(allocated.semantic_model.request_budget, 1)
        snapshot["models"][0]["capabilities"].append("caller-mutation")
        snapshot["sources"][0]["grounder_limits"]["run_input_bounds"][
            "max_array_items"
        ] = 999
        snapshot["world_source_query_policy"]["max_characters"] = 401
        snapshot["world_source_query_policy"]["evaluation_date"] = "2026-10-08"
        fresh_snapshot = runner.configuration_snapshot()
        self.assertEqual(fresh_snapshot["world_source_query_policy"]["max_characters"], 400)
        self.assertEqual(
            fresh_snapshot["world_source_query_policy"]["evaluation_date"],
            "2026-10-07",
        )
        self.assertNotIn("caller-mutation", fresh_snapshot["models"][0]["capabilities"])
        self.assertNotEqual(
            fresh_snapshot["sources"][0]["grounder_limits"]["run_input_bounds"][
                "max_array_items"
            ],
            999,
        )

    def test_world_snapshot_keeps_legacy_search_policy_when_source_budget_is_three(self):
        grounder = replace(
            self.config.grounder,
            source=replace(
                self.config.grounder.source,
                request_budget=3,
                credit_budget=3,
            ),
        )
        config = replace(self.config, grounder=grounder)
        runner = create_world_runner(
            config, repo_root=ROOT, market_bridge=self.lazy_bridge
        )

        source_snapshot = runner.configuration_snapshot()["sources"][0]
        self.assertEqual(source_snapshot["request_budget"], 3)
        self.assertEqual(
            source_snapshot["schema_version"],
            "host-event-source-snapshot-v0.3",
        )

    def test_world_source_query_preflight_accepts_400_and_rejects_invalid_without_calls(self):
        prefix = "Public company events for "
        suffix = (
            " from 2026-10-01 through 2026-10-07 inclusive: explicit catalysts; "
            "narrative/belief shifts; second-order transmission."
        )
        max_scope_characters = 400 - len(prefix) - len(suffix)
        exactly_400 = "q" * max_scope_characters
        expected_query = prefix + exactly_400 + suffix
        overflow_401 = "q" * (max_scope_characters + 1)
        empty = HostSkillResult("empty", None, (), (), (), 0)
        skill_queries = []

        def capture_skill_query(_config, *, domain, **_kwargs):
            skill_queries.append(domain)
            return empty

        with mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            side_effect=self._fake_grounder,
        ), mock.patch(
            "convexity_hunter.host_world.run_last30days_discovery",
            side_effect=capture_skill_query,
        ):
            runner = create_world_runner(
                self.config, repo_root=ROOT, market_bridge=self.lazy_bridge
            )
            accepted = runner(exactly_400, bounds=self.post_bounds)
            accepted_second = runner(
                "second original request", bounds=self.post_bounds
            )
        self.assertNotIn("world_source_query_invalid", accepted.case_set.reasons)
        self.assertEqual(self.grounder_query_calls[0], expected_query)
        self.assertEqual(self.grounder_calls[0][0], exactly_400)
        self.assertNotIn(
            "world_source_query_invalid", accepted_second.case_set.reasons
        )
        self.assertEqual(
            self.grounder_query_calls,
            [
                expected_query,
                "Public company events for second original request from "
                "2026-10-01 through 2026-10-07 inclusive: explicit catalysts; "
                "narrative/belief shifts; second-order transmission.",
            ],
        )
        self.assertEqual(
            skill_queries,
            [exactly_400, "second original request"],
        )

        for invalid in (
            "q" * 401,
            overflow_401,
            "q" * 400,
            "request ",
            "\ud800",
        ):
            with self.subTest(length=len(invalid), invalid=repr(invalid)):
                self.grounder_calls.clear()
                self.grounder_query_calls.clear()
                with mock.patch(
                    "convexity_hunter.host_world.create_event_grounder",
                    side_effect=self._fake_grounder,
                ), mock.patch(
                    "convexity_hunter.host_world.run_last30days_discovery",
                    side_effect=AssertionError("Skill must not run"),
                ):
                    runner = create_world_runner(
                        self.config,
                        repo_root=ROOT,
                        market_bridge=self.lazy_bridge,
                    )
                    result = runner(invalid, bounds=self.post_bounds)
                self.assertIn(
                    "world_source_query_invalid", result.case_set.reasons
                )
                self.assertEqual(result.case_set.submissions.submissions, ())
                self.assertEqual(result.case_set.cases, ())
                self.assertEqual(self.grounder_calls, [])
                self.assertEqual(self.grounder_query_calls, [])

    def test_world_source_query_date_underflow_fails_closed_before_calls(self):
        config = replace(self.config, evaluation_date=datetime.date.min)
        with mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            side_effect=self._fake_grounder,
        ), mock.patch(
            "convexity_hunter.host_world.run_last30days_discovery",
            side_effect=AssertionError("Skill must not run"),
        ):
            runner = create_world_runner(
                config, repo_root=ROOT, market_bridge=self.lazy_bridge
            )
            result = runner("market scope", bounds=self.post_bounds)

        self.assertIn("world_source_query_invalid", result.case_set.reasons)
        self.assertEqual(result.case_set.submissions.submissions, ())
        self.assertEqual(result.case_set.cases, ())
        self.assertEqual(self.grounder_calls, [])
        self.assertEqual(self.grounder_query_calls, [])

    def test_world_source_query_uses_frozen_evaluation_date_for_window_and_snapshot(self):
        config = replace(
            self.config, evaluation_date=datetime.date(2026, 10, 28)
        )
        empty = HostSkillResult("empty", None, (), (), (), 0)
        with mock.patch(
            "convexity_hunter.host_world.create_event_grounder",
            side_effect=self._fake_grounder,
        ), mock.patch(
            "convexity_hunter.host_world.run_last30days_discovery",
            return_value=empty,
        ):
            runner = create_world_runner(
                config, repo_root=ROOT, market_bridge=self.lazy_bridge
            )
            runner("US listed companies", bounds=self.post_bounds)

        self.assertEqual(
            self.grounder_query_calls,
            [
                "Public company events for US listed companies from "
                "2026-10-22 through 2026-10-28 inclusive: explicit catalysts; "
                "narrative/belief shifts; second-order transmission."
            ],
        )
        self.assertEqual(
            runner.configuration_snapshot()["world_source_query_policy"][
                "evaluation_date"
            ],
            "2026-10-28",
        )

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
