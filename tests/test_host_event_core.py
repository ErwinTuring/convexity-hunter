"""Synthetic adapter-contract tests; mocked Core runs are not completion evidence."""

import datetime
import unittest
from unittest.mock import patch

from convexity_hunter.core_application import (
    CoreOperationalBounds,
    SourceSubmissionBatch,
)
from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.event_intelligence import (
    EventIntelligenceSubmission,
    EventSourceReference,
    EventUnderlyingHypothesis,
)
from convexity_hunter.host_event_core import create_event_core_executor
from convexity_hunter.host_profile import APPROVED_STANDARD_RESEARCH_PROFILE
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority


def _submission():
    return EventIntelligenceSubmission(
        "synthetic-submission",
        None,
        None,
        None,
        None,
        None,
        None,
        (EventSourceReference("synthetic-source", "https://example.test/event"),),
        (),
        (
            EventUnderlyingHypothesis(
                "synthetic-hypothesis", None, None, None, None, None
            ),
        ),
    )


def _bounds():
    return CoreOperationalBounds(4, 8, 10, 8, 1.0)


class HostEventCoreTests(unittest.TestCase):
    def setUp(self):
        self.raw_input = "Synthetic event description"
        self.user_input = UserEventInput(self.raw_input)
        self.batch = SourceSubmissionBatch(self.user_input, (_submission(),))
        self.bounds = _bounds()
        self.maturity_authority = OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH
        self.evaluation_date = datetime.date(2030, 1, 1)
        self.market_bridge = object()

    def _executor(self):
        return create_event_core_executor(
            evaluation_date=self.evaluation_date,
            maturity_authority=self.maturity_authority,
            market_bridge=self.market_bridge,
        )

    def test_forwards_exact_batch_input_bounds_policy_and_result(self):
        policy = object()
        result = object()
        with patch(
            "convexity_hunter.host_event_core.create_core_research_policy",
            return_value=policy,
        ) as make_policy, patch(
            "convexity_hunter.host_event_core.run_event_core",
            return_value=result,
        ) as run_core:
            actual = self._executor()(
                self.raw_input, bounds=self.bounds, source_batch=self.batch
            )

        self.assertIs(actual, result)
        make_policy.assert_called_once_with(
            profile=APPROVED_STANDARD_RESEARCH_PROFILE,
            evaluation_date=self.evaluation_date,
            maturity_authority=self.maturity_authority,
            bounds=self.bounds,
        )
        run_core.assert_called_once()
        self.assertIs(run_core.call_args.args[0], self.user_input)
        self.assertIs(run_core.call_args.kwargs["market_bridge"], self.market_bridge)
        self.assertIs(run_core.call_args.kwargs["policy"], policy)
        grounder = run_core.call_args.kwargs["grounder"]
        self.assertIs(grounder(self.user_input), self.batch)
        with self.assertRaises(ValueError):
            grounder(UserEventInput("different event"))

    def test_missing_empty_or_mismatched_batch_fails_before_core_calls(self):
        class BatchSubclass(SourceSubmissionBatch):
            pass

        class InputSubclass(UserEventInput):
            pass

        cases = (
            (None, TypeError),
            (SourceSubmissionBatch(self.user_input, ()), ValueError),
            (
                SourceSubmissionBatch(
                    UserEventInput("different event"), (_submission(),)
                ),
                ValueError,
            ),
            (BatchSubclass(self.user_input, (_submission(),)), TypeError),
            (SourceSubmissionBatch(self.raw_input, (_submission(),)), TypeError),
            (
                SourceSubmissionBatch(
                    InputSubclass(self.raw_input), (_submission(),)
                ),
                TypeError,
            ),
        )
        for batch, error in cases:
            with self.subTest(batch=batch), patch(
                "convexity_hunter.host_event_core.create_core_research_policy"
            ) as make_policy, patch(
                "convexity_hunter.host_event_core.run_event_core"
            ) as run_core:
                with self.assertRaises(error):
                    self._executor()(
                        self.raw_input, bounds=self.bounds, source_batch=batch
                    )
                make_policy.assert_not_called()
                run_core.assert_not_called()

    def test_invalid_bounds_fail_before_policy_or_core(self):
        with patch(
            "convexity_hunter.host_event_core.create_core_research_policy"
        ) as make_policy, patch(
            "convexity_hunter.host_event_core.run_event_core"
        ) as run_core:
            with self.assertRaises(TypeError):
                self._executor()(
                    self.raw_input, bounds=object(), source_batch=self.batch
                )
            make_policy.assert_not_called()
            run_core.assert_not_called()

    def test_invalid_date_or_maturity_authority_fails_before_policy_or_core(self):
        invalid_factories = (
            {"evaluation_date": datetime.datetime(2030, 1, 1)},
            {"maturity_authority": "neutral_structural_research"},
        )
        for override in invalid_factories:
            arguments = {
                "evaluation_date": self.evaluation_date,
                "maturity_authority": self.maturity_authority,
                "market_bridge": self.market_bridge,
            }
            arguments.update(override)
            with self.subTest(override=override), patch(
                "convexity_hunter.host_event_core.create_core_research_policy"
            ) as make_policy, patch(
                "convexity_hunter.host_event_core.run_event_core"
            ) as run_core:
                with self.assertRaises(TypeError):
                    create_event_core_executor(**arguments)
                make_policy.assert_not_called()
                run_core.assert_not_called()


if __name__ == "__main__":
    unittest.main()
