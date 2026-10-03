"""Focused closed-snapshot and Store tests for bounded World/Event batches."""

import datetime
import decimal
import hashlib
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from dataclasses import replace

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tests.test_core_application import (
    FakeMarketBridge,
    make_policy,
    make_row,
    make_submission,
)
from convexity_hunter.core_application import (
    CoreCaseRecord,
    CoreCaseSet,
    CoreOperationalBounds,
    CoreRunResult,
    CoreUnavailableCase,
    SourceSubmissionBatch,
    run_event_core,
    run_world_core,
)
from convexity_hunter.core_presentation import compact_summary, report
from convexity_hunter.core_research import evaluate_core_research
from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.event_intelligence import (
    DistributionChangeMode,
    EventIntelligenceAcceptanceStatus,
    assess_event_intelligence_submission,
)
from convexity_hunter.host_batch_snapshot import case_key
from convexity_hunter.host_profile import STANDARD_RESEARCH_PROFILE
from convexity_hunter.host_store import HostStore, StoreCorruptionError


_BASE_BOUNDS = {
    "max_submissions": 2,
    "max_hypotheses": 3,
    "max_browser_rows": 20,
    "max_cases": 8,
    "quote_timeout_seconds": 2.5,
}


def _policy(*, max_submissions=2, max_hypotheses=3, max_cases=8):
    return make_policy(
        [],
        max_submissions=max_submissions,
        max_hypotheses=max_hypotheses,
        max_browser_rows=20,
        max_cases=max_cases,
    )


def _standard_profile_result(result):
    """Bind test Core cases to the exact Host-approved risk policy."""

    cases = []
    for record in result.case_set.cases:
        request = replace(
            record.kernel_request,
            risk_policy=STANDARD_RESEARCH_PROFILE.to_core_risk_policy(
                record.kernel_request.structure
            ),
        )
        evaluated = evaluate_core_research(request)
        context = replace(
            record.context, kernel_request=request, kernel_result=evaluated
        )
        cases.append(
            CoreCaseRecord(
                record.case_id, context, request, evaluated, record.reasons
            )
        )
    case_set = CoreCaseSet(
        result.case_set.entry_origin,
        result.case_set.raw_input,
        result.case_set.submissions,
        tuple(cases),
        result.case_set.unavailable,
        result.case_set.reasons,
    )
    return CoreRunResult(case_set, compact_summary(case_set))


def _world_result(raw_input, *, submission=None, policy=None):
    policy = policy or _policy()
    submission = submission or make_submission(
        "world-submission", ("world-hypothesis",), DistributionChangeMode.EXTREME_TAIL_UP
    )
    batch = SourceSubmissionBatch(raw_input, (submission,))
    return run_world_core(
        raw_input,
        source_producer=lambda _raw: batch,
        market_bridge=FakeMarketBridge(
            (make_row(datetime.date(2030, 1, 31), "CALL", "100"),)
        ),
        policy=policy,
    )


def _event_result(description, *, source_locator="https://example.test/source"):
    raw_input = UserEventInput(
        description,
        provisional_symbols=("UNVERIFIED-SYMBOL",),
        source_locators=("https://example.test/user-hint",),
        event_date=datetime.date(2030, 1, 2),
    )
    submission = make_submission("event-submission", ("event-hypothesis",))
    submission = replace(
        submission,
        sources=(replace(submission.sources[0], locator=source_locator),),
    )
    batch = SourceSubmissionBatch(raw_input, (submission,))
    result = run_event_core(
        raw_input,
        grounder=lambda _raw: batch,
        market_bridge=FakeMarketBridge(
            (
                make_row(datetime.date(2030, 1, 31), "CALL", "100"),
                make_row(datetime.date(2030, 1, 31), "PUT", "100"),
            )
        ),
        policy=_policy(),
    )
    return _standard_profile_result(result)


def _metadata(mode):
    return {
        "configuration_snapshot": {"models": [], "sources": [], "skills": []},
        "execution_snapshot": {
            mode + "_executor": {
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


class HostBatchSnapshotTests(unittest.TestCase):
    def setUp(self):
        canonical_temp_root = pathlib.Path(tempfile.gettempdir()).resolve()
        self.temporary = tempfile.TemporaryDirectory(dir=str(canonical_temp_root))
        self.addCleanup(self.temporary.cleanup)
        self.db_path = pathlib.Path(self.temporary.name) / "host.sqlite3"
        self.store = HostStore(self.db_path)
        self.addCleanup(self.store.close)

    def _create_run(self, mode, raw_input, bounds=None, metadata=None):
        bounds = bounds or CoreOperationalBounds(**_BASE_BOUNDS)
        return self.store.create_run(
            mode,
            raw_input,
            bounds,
            STANDARD_RESEARCH_PROFILE.snapshot(),
            metadata or _metadata(mode),
        )

    def test_world_archive_preserves_long_unicode_ids_and_lazy_report(self):
        raw_input = "synthetic World request"
        long_submission = "提交/研究/" + "界" * 180
        long_hypothesis = "假设/路径/" + "x" * 190
        submission = make_submission(
            long_submission,
            (long_hypothesis,),
            DistributionChangeMode.EXTREME_TAIL_UP,
        )
        result = _standard_profile_result(_world_result(raw_input, submission=submission))
        self.assertEqual(len(result.case_set.cases), 1)
        record = result.case_set.cases[0]
        self.assertGreater(len(record.case_id), 256)
        self.assertIn("/", record.case_id)
        self.assertIn("界", record.case_id)

        run_id = self._create_run("world", raw_input, _policy().bounds)
        stage_id = self.store.start_stage(run_id, "world")
        self.assertIsNone(self.store.save_batch_result(run_id, result))
        summary = self.store.get_batch_summary(run_id)
        self.assertEqual(
            set(summary),
            {
                "entry_origin", "case_count", "unavailable_count", "disposition_counts",
                "case_ids", "reasons", "case_summaries", "unavailable_case_ids",
                "unavailable_cases", "host_status",
            },
        )
        self.assertEqual(summary["unavailable_case_ids"], [])
        self.assertEqual(summary["unavailable_cases"], [])
        self.assertEqual(summary["host_status"], "COMPLETED")
        self.assertEqual(summary["case_ids"], [record.case_id])
        self.assertEqual(summary["case_summaries"][0]["case_key"], case_key(record.case_id))
        listed = self.store.list_batch_cases(run_id)
        self.assertEqual(listed, [{
            "case_id": record.case_id,
            "case_key": case_key(record.case_id),
            "classification": record.kernel_result.disposition.value,
            "reasons": list(dict.fromkeys(
                [item.value for item in record.kernel_result.reasons] + list(record.reasons)
            )),
        }])
        detail = self.store.get_batch_case(run_id, case_key(record.case_id))
        self.assertEqual(detail["case_id"], record.case_id)
        self.assertEqual(detail["case_key"], case_key(record.case_id))
        self.assertEqual(detail["report"], report(record))
        with self.assertRaises(ValueError):
            self.store.get_batch_case(run_id, record.case_id)
        with self.assertRaises(ValueError):
            self.store.save_batch_result(run_id, result)

        archive, _decoded = self.store._read_batch_archive(run_id)
        wire = json.dumps(archive, ensure_ascii=False)
        self.assertNotIn("report_cache", archive)
        self.assertNotIn("raw_model_body", wire)
        self.assertEqual(archive["cases"][0]["lineage"], {
            "submission_id": long_submission,
            "hypothesis_id": long_hypothesis,
        })
        self.store.finish_stage(
            run_id,
            stage_id,
            "COMPLETED",
            archive["outcome"],
            (),
        )
        self.store.finish_run(run_id, "COMPLETED", ())

        self.store.close()
        reopened = HostStore(self.db_path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get_batch_case(run_id, case_key(record.case_id)), detail)
        self.assertEqual(reopened.get_run(run_id)["status"], "COMPLETED")

    def test_event_audit_is_unverified_and_retains_normalized_ei_lineage(self):
        description = "event description exactly bound to run input"
        result = _event_result(description)
        run_id = self._create_run("event", description, _policy().bounds)
        self.store.save_batch_result(run_id, result)
        summary = self.store.get_batch_summary(run_id)
        self.assertEqual(summary["host_status"], "COMPLETED")
        archive, _decoded = self.store._read_batch_archive(run_id)
        self.assertEqual(archive["event_input_audit"], {
            "evidence_role": "unverified_user_input",
            "description": description,
            "provisional_symbols": ["UNVERIFIED-SYMBOL"],
            "source_locators": ["https://example.test/user-hint"],
            "event_date": "2030-01-02",
        })
        audited = archive["ei_audit"]["submissions"][0]
        self.assertEqual(audited["submission_id"], "event-submission")
        self.assertEqual(audited["assessment"]["status"], "accepted")
        self.assertEqual(audited["assessment"]["issues"], [])
        self.assertEqual(audited["hypotheses"][0]["hypothesis_id"], "event-hypothesis")
        self.assertEqual(
            {item["kind"] for item in audited["statements"]},
            {"observed_fact", "interpretation"},
        )
        self.assertTrue(all("raw_body" not in item for item in audited["sources"]))

    def test_unavailable_sidecar_keeps_ids_and_reasons_and_status_precedence(self):
        raw_input = "synthetic rejected-source batch"
        incomplete = replace(make_submission("incomplete", ("hyp-1",)), event_id=None)
        result = _world_result(raw_input, submission=incomplete)
        self.assertEqual(len(result.case_set.cases), 0)
        self.assertEqual(len(result.case_set.unavailable), 1)
        original_id = result.case_set.unavailable[0].case_id
        run_id = self._create_run("world", raw_input, _policy().bounds)
        self.store.save_batch_result(run_id, result)
        summary = self.store.get_batch_summary(run_id)
        self.assertEqual(summary["unavailable_case_ids"], [original_id])
        item = summary["unavailable_cases"][0]
        self.assertEqual(item["case_id"], original_id)
        self.assertEqual(item["case_key"], case_key(original_id))
        self.assertTrue(item["reasons"])
        self.assertEqual(summary["host_status"], "BLOCKED")
        public = self.store.list_batch_cases(run_id)
        self.assertEqual(public[0]["classification"], "UNAVAILABLE")
        self.assertNotEqual(public[0]["classification"], "REJECT")
        detail = self.store.get_batch_case(run_id, item["case_key"])
        self.assertEqual(detail["report"], None)
        self.assertEqual(detail["reasons"], item["reasons"])

    def test_partial_summary_preserves_core_and_unavailable_array_orders(self):
        raw_input = "mixed accepted and unavailable branches"
        accepted = make_submission(
            "accepted", ("hyp-b", "hyp-a"), DistributionChangeMode.EXTREME_TAIL_UP
        )
        incomplete = replace(make_submission("incomplete", ("hyp-c",)), event_id=None)
        batch = SourceSubmissionBatch(raw_input, (accepted, incomplete))
        result = run_world_core(
            raw_input,
            source_producer=lambda _raw: batch,
            market_bridge=FakeMarketBridge(
                (make_row(datetime.date(2030, 1, 31), "CALL", "100"),)
            ),
            policy=_policy(),
        )
        result = _standard_profile_result(result)
        self.assertEqual(len(result.case_set.cases), 2)
        self.assertEqual(len(result.case_set.unavailable), 1)
        run_id = self._create_run("world", raw_input, _policy().bounds)
        stage_id = self.store.start_stage(run_id, "world")
        self.store.save_batch_result(run_id, result)
        listed = self.store.list_batch_cases(run_id)
        expected_ids = (
            [record.case_id for record in result.case_set.cases]
            + [record.case_id for record in result.case_set.unavailable]
        )
        self.assertEqual([item["case_id"] for item in listed], expected_ids)
        summary = self.store.get_batch_summary(run_id)
        self.assertEqual(summary["case_ids"], expected_ids[:2])
        self.assertEqual(summary["unavailable_case_ids"], expected_ids[2:])
        self.assertEqual(
            [item["case_id"] for item in summary["unavailable_cases"]], expected_ids[2:]
        )
        self.assertEqual(summary["host_status"], "PARTIAL")
        archive, _ = self.store._read_batch_archive(run_id)
        self.store.finish_stage(run_id, stage_id, "PARTIAL", archive["outcome"], ())
        self.store.finish_run(run_id, "PARTIAL", ())
        self.assertEqual(self.store.get_run(run_id)["status"], "PARTIAL")

    def test_case_limit_archives_empty_blocked_result_without_prefix(self):
        raw_input = "case limit request"
        limited = _world_result(
            raw_input,
            submission=make_submission(
                "limited", ("hyp-a", "hyp-b"), DistributionChangeMode.EXTREME_TAIL_UP
            ),
            policy=_policy(max_hypotheses=3, max_cases=1),
        )
        self.assertEqual(limited.case_set.reasons, ("LIMIT_EXCEEDED", "cases:2>1"))
        self.assertEqual(limited.case_set.cases, ())
        run_id = self._create_run("world", raw_input, _policy(max_hypotheses=3, max_cases=1).bounds)
        self.store.save_batch_result(run_id, limited)
        summary = self.store.get_batch_summary(run_id)
        self.assertEqual(summary["case_count"], 0)
        self.assertEqual(summary["case_summaries"], [])
        self.assertEqual(summary["host_status"], "BLOCKED")
        archive, _decoded = self.store._read_batch_archive(run_id)
        self.assertEqual(archive["outcome"], {
            "schema_version": "host-batch-outcome-v0.1",
            "case_count": 0,
            "unavailable_count": 0,
            "status": "BLOCKED",
        })

    def test_empty_submission_result_is_blocked_not_relabelled_as_core_reject(self):
        raw_input = "empty source result"
        case_set = CoreCaseSet("WORLD", raw_input, None, (), (), ("EMPTY_SUBMISSION",))
        result = CoreRunResult(case_set, compact_summary(case_set))
        run_id = self._create_run("world", raw_input, _policy().bounds)
        self.store.save_batch_result(run_id, result)
        summary = self.store.get_batch_summary(run_id)
        self.assertEqual(summary["host_status"], "BLOCKED")
        self.assertEqual(summary["case_count"], 0)
        self.assertEqual(summary["disposition_counts"], {})
        self.assertEqual(self.store.list_batch_cases(run_id), [])

    def test_core_submission_and_hypothesis_overflow_archives_full_limit_diagnostic(self):
        raw_input = "submission and hypothesis source-count limits"
        two_submissions = SourceSubmissionBatch(
            raw_input,
            (
                make_submission("overflow-a", ("hyp-a",)),
                make_submission("overflow-b", ("hyp-b",)),
            ),
        )
        submission_limited = run_world_core(
            raw_input,
            source_producer=lambda _raw: two_submissions,
            market_bridge=FakeMarketBridge(()),
            policy=_policy(max_submissions=1),
        )
        self.assertEqual(
            submission_limited.case_set.reasons,
            ("LIMIT_EXCEEDED", "submissions:2>1"),
        )
        submission_run = self._create_run(
            "world", raw_input, _policy(max_submissions=1).bounds
        )
        self.store.save_batch_result(submission_run, submission_limited)
        submission_archive, _ = self.store._read_batch_archive(submission_run)
        self.assertEqual(len(submission_archive["ei_audit"]["submissions"]), 2)
        self.assertEqual(submission_archive["case_set_reasons"], ["LIMIT_EXCEEDED", "submissions:2>1"])
        self.assertEqual(submission_archive["outcome"]["status"], "BLOCKED")
        self.assertEqual(self.store.get_batch_summary(submission_run)["host_status"], "BLOCKED")
        self.assertEqual(self.store.list_batch_cases(submission_run), [])

        hypothesis_batch = SourceSubmissionBatch(
            raw_input,
            (make_submission("hypothesis-overflow", ("hyp-a", "hyp-b")),),
        )
        hypothesis_limited = run_world_core(
            raw_input,
            source_producer=lambda _raw: hypothesis_batch,
            market_bridge=FakeMarketBridge(()),
            policy=_policy(max_hypotheses=1),
        )
        self.assertEqual(
            hypothesis_limited.case_set.reasons,
            ("LIMIT_EXCEEDED", "hypotheses:2>1"),
        )
        hypothesis_run = self._create_run(
            "world", raw_input, _policy(max_hypotheses=1).bounds
        )
        self.store.save_batch_result(hypothesis_run, hypothesis_limited)
        hypothesis_archive, _ = self.store._read_batch_archive(hypothesis_run)
        self.assertEqual(
            len(hypothesis_archive["ei_audit"]["submissions"][0]["hypotheses"]), 2
        )
        self.assertEqual(hypothesis_archive["outcome"]["status"], "BLOCKED")
        self.assertEqual(self.store.get_batch_summary(hypothesis_run)["host_status"], "BLOCKED")
        self.assertEqual(self.store.list_batch_cases(hypothesis_run), [])

        browser_batch = SourceSubmissionBatch(
            raw_input, (make_submission("browser-overflow", ("hyp",)),)
        )
        browser_limited = run_world_core(
            raw_input,
            source_producer=lambda _raw: browser_batch,
            market_bridge=FakeMarketBridge(
                (
                    make_row(datetime.date(2030, 1, 31), "CALL", "100"),
                    make_row(datetime.date(2030, 2, 28), "CALL", "105"),
                )
            ),
            policy=make_policy(
                [], max_submissions=2, max_hypotheses=3,
                max_browser_rows=1, max_cases=8,
            ),
        )
        self.assertEqual(
            browser_limited.case_set.reasons,
            ("LIMIT_EXCEEDED", "browser_rows:2>1"),
        )
        browser_run = self._create_run(
            "world",
            raw_input,
            CoreOperationalBounds(
                max_submissions=2, max_hypotheses=3, max_browser_rows=1,
                max_cases=8, quote_timeout_seconds=2.5,
            ),
        )
        self.store.save_batch_result(browser_run, browser_limited)
        browser_archive, _ = self.store._read_batch_archive(browser_run)
        self.assertEqual(browser_archive["case_set_reasons"], ["LIMIT_EXCEEDED", "browser_rows:2>1"])
        self.assertEqual(browser_archive["outcome"]["status"], "BLOCKED")

    def test_limit_diagnostic_must_match_bound_and_core_no_prefix(self):
        raw_input = "tampered limit diagnostic"
        batch = SourceSubmissionBatch(
            raw_input,
            (
                make_submission("limit-a", ("hyp-a",)),
                make_submission("limit-b", ("hyp-b",)),
            ),
        )
        limited = run_world_core(
            raw_input,
            source_producer=lambda _raw: batch,
            market_bridge=FakeMarketBridge(()),
            policy=_policy(max_submissions=1),
        )
        bad_set = CoreCaseSet(
            limited.case_set.entry_origin,
            limited.case_set.raw_input,
            limited.case_set.submissions,
            limited.case_set.cases,
            limited.case_set.unavailable,
            ("LIMIT_EXCEEDED", "submissions:2>2"),
        )
        bad_result = CoreRunResult(bad_set, compact_summary(bad_set))
        run_id = self._create_run("world", raw_input, _policy(max_submissions=1).bounds)
        with self.assertRaises(ValueError):
            self.store.save_batch_result(run_id, bad_result)
        self.assertIsNone(self.store.get_batch_summary(run_id))

        unavailable_prefix = CoreCaseSet(
            limited.case_set.entry_origin,
            limited.case_set.raw_input,
            limited.case_set.submissions,
            (),
            (CoreUnavailableCase("unexpected-prefix", ("branch_failure",)),),
            limited.case_set.reasons,
        )
        unavailable_result = CoreRunResult(
            unavailable_prefix, compact_summary(unavailable_prefix)
        )
        with self.assertRaises(ValueError):
            self.store.save_batch_result(run_id, unavailable_result)
        self.assertIsNone(self.store.get_batch_summary(run_id))

        no_limit_set = CoreCaseSet(
            limited.case_set.entry_origin,
            limited.case_set.raw_input,
            limited.case_set.submissions,
            (),
            (),
            (),
        )
        no_limit_result = CoreRunResult(no_limit_set, compact_summary(no_limit_set))
        with self.assertRaises(ValueError):
            self.store.save_batch_result(run_id, no_limit_result)
        self.assertIsNone(self.store.get_batch_summary(run_id))

    def test_write_rejects_binding_compact_bound_profile_and_ei_uri_credentials(self):
        raw_input = "safe world input"
        result = _standard_profile_result(_world_result(raw_input))
        run_id = self._create_run("world", raw_input, _policy().bounds)
        with self.assertRaises(ValueError):
            self.store.save_batch_result(run_id, replace(result, compact=replace(result.compact, case_count=99)))
        record = result.case_set.cases[0]
        altered_risk = replace(
            record.kernel_request.risk_policy,
            portfolio_value=decimal.Decimal("10000000"),
        )
        altered_request = replace(record.kernel_request, risk_policy=altered_risk)
        altered_core = evaluate_core_research(altered_request)
        altered_context = replace(
            record.context, kernel_request=altered_request, kernel_result=altered_core
        )
        altered_record = CoreCaseRecord(
            record.case_id, altered_context, altered_request, altered_core, record.reasons
        )
        altered_set = CoreCaseSet(
            result.case_set.entry_origin,
            result.case_set.raw_input,
            result.case_set.submissions,
            (altered_record,),
            result.case_set.unavailable,
            result.case_set.reasons,
        )
        with self.assertRaises(ValueError):
            self.store.save_batch_result(
                run_id, CoreRunResult(altered_set, compact_summary(altered_set))
            )
        with self.assertRaises(ValueError):
            self.store.save_batch_result(self._create_run("world", "different input", _policy().bounds), result)
        wrong_executor_run = self._create_run(
            "world", raw_input, _policy().bounds, metadata=_metadata("event")
        )
        with self.assertRaises(ValueError):
            self.store.save_batch_result(wrong_executor_run, result)
        self.assertIsNone(self.store.get_batch_summary(run_id))

        # An event-source URI is covered by the same credential guard as a Core SourceReference URI.
        description = "unsafe event source locator"
        bad_result = _event_result(description, source_locator="https://example.test/story?api_key=URI_SECRET_SENTINEL")
        event_run = self._create_run("event", description, _policy().bounds)
        with self.assertRaises(ValueError):
            self.store.save_batch_result(event_run, bad_result)
        self.assertIsNone(self.store.get_batch_summary(event_run))
        self.assertNotIn(b"URI_SECRET_SENTINEL", self.db_path.read_bytes())

    def test_batch_write_prevalidates_incomplete_ei_case_before_journaling(self):
        raw_input = "incomplete EI linked to evaluated case"
        result = _standard_profile_result(_world_result(raw_input))
        original_record = result.case_set.cases[0]
        incomplete_submission = replace(
            original_record.context.assessment.submission,
            event_description=None,
        )
        incomplete_assessment = assess_event_intelligence_submission(
            incomplete_submission
        )
        self.assertIs(
            incomplete_assessment.status,
            EventIntelligenceAcceptanceStatus.INCOMPLETE,
        )
        batch = SourceSubmissionBatch(raw_input, (incomplete_submission,))
        context = replace(
            original_record.context,
            submissions=batch,
            assessment=incomplete_assessment,
            hypothesis=incomplete_submission.hypotheses[0],
            automated_handoff=None,
            discovery_request=None,
            browser=None,
            listed_rows=(),
            listed_row=None,
            native_verification=(),
            quote_batch=None,
            native_quotes=(),
            provider_references=(),
            kernel_request=original_record.kernel_request,
            kernel_result=original_record.kernel_result,
        )
        invalid_record = CoreCaseRecord(
            original_record.case_id,
            context,
            original_record.kernel_request,
            original_record.kernel_result,
            original_record.reasons,
        )
        invalid_case_set = CoreCaseSet(
            result.case_set.entry_origin,
            result.case_set.raw_input,
            batch,
            (invalid_record,),
            (),
            result.case_set.reasons,
        )
        invalid_result = CoreRunResult(
            invalid_case_set, compact_summary(invalid_case_set)
        )
        run_id = self._create_run("world", raw_input, _policy().bounds)
        event_count_before = self.store._conn().execute(
            "SELECT COUNT(*) FROM events WHERE run_id=?", (run_id,)
        ).fetchone()[0]

        with self.assertRaises(ValueError):
            self.store.save_batch_result(run_id, invalid_result)

        self.assertIsNone(
            self.store._conn().execute(
                "SELECT 1 FROM batch_archives WHERE run_id=?", (run_id,)
            ).fetchone()
        )
        self.assertEqual(
            self.store._conn().execute(
                "SELECT COUNT(*) FROM events WHERE run_id=?", (run_id,)
            ).fetchone()[0],
            event_count_before,
        )
        self.assertIsNone(self.store.get_batch_summary(run_id))

    def test_batch_profile_checks_full_risk_policy_on_write_and_read(self):
        raw_input = "full Standard Research Profile mapping"
        result = _standard_profile_result(_world_result(raw_input))
        valid_run = self._create_run("world", raw_input, _policy().bounds)
        self.store.save_batch_result(valid_run, result)
        self.assertEqual(self.store.get_batch_summary(valid_run)["host_status"], "COMPLETED")

        original_record = result.case_set.cases[0]
        approved_risk = original_record.kernel_request.risk_policy
        changed_risks = (
            replace(approved_risk, methodology="unapproved-methodology"),
            replace(
                approved_risk,
                provenance=replace(
                    approved_risk.provenance,
                    description="unapproved risk provenance",
                ),
            ),
        )
        for bad_risk in changed_risks:
            bad_request = replace(
                original_record.kernel_request, risk_policy=bad_risk
            )
            bad_core_result = evaluate_core_research(bad_request)
            bad_context = replace(
                original_record.context,
                kernel_request=bad_request,
                kernel_result=bad_core_result,
            )
            bad_record = CoreCaseRecord(
                original_record.case_id,
                bad_context,
                bad_request,
                bad_core_result,
                original_record.reasons,
            )
            bad_case_set = CoreCaseSet(
                result.case_set.entry_origin,
                result.case_set.raw_input,
                result.case_set.submissions,
                (bad_record,),
                result.case_set.unavailable,
                result.case_set.reasons,
            )
            bad_run = self._create_run("world", raw_input, _policy().bounds)
            with self.assertRaises(ValueError):
                self.store.save_batch_result(
                    bad_run,
                    CoreRunResult(bad_case_set, compact_summary(bad_case_set)),
                )
            self.assertIsNone(self.store.get_batch_summary(bad_run))

        row = self.store._conn().execute(
            "SELECT archive_json FROM batch_archives WHERE run_id=?", (valid_run,)
        ).fetchone()
        original_wire = row["archive_json"]
        self.store._conn().execute("DROP TRIGGER batch_archives_no_update")
        for field in ("methodology", "provenance"):
            archive = json.loads(original_wire)
            risk_node = archive["cases"][0]["core_snapshot"]["request"]["risk_policy"]
            if field == "methodology":
                risk_node["methodology"] = "tampered-methodology"
            else:
                risk_node["provenance"]["description"] = "tampered risk provenance"
            case = archive["cases"][0]
            core_wire = json.dumps(
                case["core_snapshot"],
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            case["core_sha256"] = hashlib.sha256(core_wire.encode("utf-8")).hexdigest()
            archive_wire = json.dumps(
                archive,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            self.store._conn().execute(
                "UPDATE batch_archives SET archive_json=?,archive_sha256=? WHERE run_id=?",
                (
                    archive_wire,
                    hashlib.sha256(archive_wire.encode("utf-8")).hexdigest(),
                    valid_run,
                ),
            )
            with self.assertRaises(StoreCorruptionError):
                self.store.get_batch_summary(valid_run)

    def test_schema_digest_and_append_only_batch_archive(self):
        raw_input = "atomic archive"
        result = _standard_profile_result(_world_result(raw_input))
        run_id = self._create_run("world", raw_input, _policy().bounds)
        self.store.save_batch_result(run_id, result)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store._conn().execute("UPDATE batch_archives SET archive_json='{}'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store._conn().execute("DELETE FROM batch_archives")

        connection = self.store._conn()
        original = connection.execute(
            "SELECT archive_json FROM batch_archives WHERE run_id=?", (run_id,)
        ).fetchone()[0]
        connection.execute("DROP TRIGGER batch_archives_no_update")
        archive = json.loads(original)
        archive["ei_audit"]["submissions"][0]["sources"][0]["locator"] = (
            "https://example.test/source?api_key=READ_SECRET_SENTINEL"
        )
        wire = json.dumps(archive, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        connection.execute(
            "UPDATE batch_archives SET archive_json=?,archive_sha256=? WHERE run_id=?",
            (wire, hashlib.sha256(wire.encode("utf-8")).hexdigest(), run_id),
        )
        with self.assertRaises(StoreCorruptionError) as raised:
            self.store.get_batch_summary(run_id)
        self.assertNotIn("READ_SECRET_SENTINEL", str(raised.exception))

        archive = json.loads(original)
        archive["extra"] = "not closed"
        wire = json.dumps(archive, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        connection.execute(
            "UPDATE batch_archives SET archive_json=?,archive_sha256=? WHERE run_id=?",
            (wire, hashlib.sha256(wire.encode("utf-8")).hexdigest(), run_id),
        )
        with self.assertRaises(StoreCorruptionError):
            self.store.get_batch_summary(run_id)


if __name__ == "__main__":
    unittest.main()
