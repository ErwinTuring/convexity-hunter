"""Offline pre-Core gate tests; no source or market requests."""

import datetime
import unittest
from dataclasses import FrozenInstanceError, replace
from unittest.mock import Mock, patch

import convexity_hunter.core_application as core
import convexity_hunter.host_gate as gate_module
from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.event_intelligence import (
    EventIntelligenceSubmission, EventSourceReference, EventUnderlyingHypothesis,
)
from convexity_hunter.host_gate import run_event_core_gated, run_world_core_gated
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority


def partial_submission():
    return EventIntelligenceSubmission(
        "partial", None, None, None, None, None, None,
        (EventSourceReference("s", "https://example.test/source"),), (),
        tuple(EventUnderlyingHypothesis(i, None, None, None, None, None)
              for i in ("h1", "h2")),
    )


def forged_batch(raw_input, submissions):
    value = object.__new__(core.SourceSubmissionBatch)
    object.__setattr__(value, "raw_input", raw_input)
    object.__setattr__(value, "submissions", submissions)
    return value


class HostGateTests(unittest.TestCase):
    def setUp(self):
        self.input = UserEventInput("Original event")
        self.submission = partial_submission()
        self.batch = core.SourceSubmissionBatch(self.input, (self.submission,))

    def test_invalid_batches_never_call_either_core(self):
        no_sources = replace(self.submission, sources=())
        malformed = object.__new__(EventIntelligenceSubmission)
        cases = [
            (None, "INVALID_BATCH_TYPE"),
            ({}, "INVALID_BATCH_TYPE"),
            (core.SourceSubmissionBatch(self.input, ()), "EMPTY_BATCH"),
            (core.SourceSubmissionBatch(UserEventInput("Original event"),
                                        (self.submission,)), "RAW_INPUT_IDENTITY_MISMATCH"),
            (forged_batch(self.input, [self.submission]), "INVALID_BATCH"),
            (forged_batch(self.input, (self.submission,) * 2), "INVALID_BATCH"),
            (forged_batch(self.input, (no_sources,)), "INVALID_BATCH"),
            (forged_batch(self.input, (malformed,)), "INVALID_BATCH"),
            (forged_batch(self.input, (object(),)), "INVALID_BATCH"),
        ]
        for wrapper, name in ((run_event_core_gated, "run_event_core"),
                              (run_world_core_gated, "run_world_core")):
            for batch, reason in cases:
                with self.subTest(wrapper=name, reason=reason), patch.object(
                    gate_module, name
                ) as runner:
                    gate, result = wrapper(self.input, batch=batch,
                                           market_bridge=None, policy=None)
                    self.assertIsNone(result)
                    self.assertFalse(gate.allowed)
                    self.assertEqual(gate.reason_codes, ("BLOCKED", reason))
                    self.assertIs(gate.raw_input, self.input)
                    self.assertIs(gate.batch, batch)
                    runner.assert_not_called()

    def test_event_input_type_and_constructor_bypass_block(self):
        class InputSubclass(UserEventInput):
            pass
        forged = object.__new__(UserEventInput)
        object.__setattr__(forged, "description", "")
        for value in ("event", InputSubclass("event"), forged):
            with patch.object(gate_module, "run_event_core") as runner:
                gate, result = run_event_core_gated(
                    value, batch=self.batch, market_bridge=None, policy=None)
                self.assertEqual(gate.reason_codes, ("BLOCKED", "INVALID_EVENT_INPUT"))
                self.assertIsNone(result)
                runner.assert_not_called()

    def test_batch_subclass_and_forged_nested_record_block(self):
        class BatchSubclass(core.SourceSubmissionBatch):
            pass
        forged_source = object.__new__(EventSourceReference)
        forged = replace(self.submission)
        object.__setattr__(forged, "sources", (forged_source,))
        for batch in (BatchSubclass(self.input, (self.submission,)),
                      forged_batch(self.input, (forged,))):
            with patch.object(gate_module, "run_world_core") as runner:
                gate, result = run_world_core_gated(
                    self.input, batch=batch, market_bridge=None, policy=None)
                self.assertFalse(gate.allowed)
                self.assertIsNone(result)
                runner.assert_not_called()

    def test_all_accepted_hypotheses_reach_existing_core_branches(self):
        from tests.test_core_application import make_submission

        submission = make_submission(hypothesis_ids=("h1", "h2"))
        batch = core.SourceSubmissionBatch(self.input, (submission,))
        policy = core.CoreResearchPolicy(
            datetime.date(2030, 1, 1), OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
            1, core.CoreOperationalBounds(10, 10, 10, 10, 1), Mock())
        bridge = Mock()
        bridge.discover_browser.side_effect = RuntimeError("offline boundary")
        gate, result = run_event_core_gated(
            self.input, batch=batch, market_bridge=bridge, policy=policy)
        self.assertTrue(gate.allowed)
        self.assertEqual(bridge.discover_browser.call_count, 2)
        self.assertEqual(len(result.case_set.unavailable), 2)
        for case, hypothesis in zip(result.case_set.unavailable, submission.hypotheses):
            self.assertIs(case.hypothesis, hypothesis)
            self.assertIs(case.submissions, batch)

    def test_exactly_once_retains_batch_order_and_core_result_identity(self):
        for wrapper, name, producer_name in (
            (run_event_core_gated, "run_event_core", "grounder"),
            (run_world_core_gated, "run_world_core", "source_producer"),
        ):
            original = self.input if producer_name == "grounder" else object()
            batch = core.SourceSubmissionBatch(original, (
                replace(self.submission, submission_id="z"), self.submission))
            result_sentinel = object()
            with patch.object(gate_module, name, return_value=result_sentinel) as runner:
                gate, result = wrapper(original, batch=batch, market_bridge=None, policy=None)
                runner.assert_called_once()
                self.assertIs(runner.call_args.args[0], original)
                self.assertIs(runner.call_args.kwargs[producer_name](original), batch)
                self.assertIs(gate.batch, batch)
                self.assertIs(result, result_sentinel)
                self.assertTrue(gate.allowed)
                with self.assertRaises(FrozenInstanceError):
                    gate.allowed = False

    def test_incomplete_delegates_to_real_core_once_with_all_issues(self):
        policy = core.CoreResearchPolicy(
            datetime.date(2030, 1, 1), OptionMaturityAuthority.HYPOTHESIS_ALIGNED,
            1, core.CoreOperationalBounds(10, 10, 10, 10, 1), Mock())
        for wrapper, name in ((run_event_core_gated, "run_event_core"),
                              (run_world_core_gated, "run_world_core")):
            with patch.object(gate_module, name, wraps=getattr(core, name)) as runner, patch.object(
                core, "assess_event_intelligence_submission",
                wraps=core.assess_event_intelligence_submission,
            ) as assessor:
                gate, result = wrapper(self.input, batch=self.batch,
                                       market_bridge=None, policy=policy)
                self.assertTrue(gate.allowed)
                runner.assert_called_once()
                assessor.assert_called_once_with(self.submission)
                self.assertIs(result.case_set.submissions, self.batch)
                self.assertIs(result.case_set.raw_input, self.input)
                unavailable = result.case_set.unavailable[0]
                self.assertIn("event_intelligence_not_accepted", unavailable.reasons)
                self.assertTrue(unavailable.assessment.issues)
                self.assertIs(unavailable.assessment.submission.hypotheses,
                              self.submission.hypotheses)


if __name__ == "__main__":
    unittest.main()
