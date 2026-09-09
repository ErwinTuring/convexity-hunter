"""Offline Event Entry integration against existing EI and Browser fixtures."""
import datetime
import unittest
from dataclasses import replace
from unittest import mock
from tests.test_discovery_entry import make_submission
from tests.test_convexity_discrimination import make_browser
from convexity_hunter.event_entry import UserEventInput, prepare_event_entry_research
from convexity_hunter.event_intelligence import EventIntelligenceAcceptanceStatus
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority, HypothesisMaturityAlignment
from convexity_hunter.providers.futu import create_futu_exact_contract_browser

D = datetime.date(2030, 1, 3)


class EventEntryTests(unittest.TestCase):
    def run_entry(self, submission=None, **kwargs):
        submission = submission or make_submission()
        options = dict(evaluation_date=D, submission=submission,
                       grounding_methodology='Caller checked retained filing against the requested event.',
                       selected_hypothesis=submission.hypotheses[0])
        options.update(kwargs)
        return prepare_event_entry_research(UserEventInput('Investigate this event'), **options)

    def test_accepted_existing_handoff_and_identity(self):
        submission=make_submission(); context=self.run_entry(submission)
        self.assertIs(context.assessment.status, EventIntelligenceAcceptanceStatus.ACCEPTED)
        self.assertEqual(context.entry_origin, 'EVENT_ENTRY')
        self.assertIs(context.assessment.submission, submission)
        handoff=context.option_request.discovery_entry_handoff
        self.assertIs(handoff.acceptance_result,context.assessment)
        self.assertIs(handoff.selected_hypothesis,submission.hypotheses[0])
        self.assertEqual(context.blocking_reasons,())

    def test_prose_alone_is_not_evidence(self):
        user=UserEventInput('FDA has approved everything', ('FAKE',), ('https://example.com/user-claim',), D)
        context=prepare_event_entry_research(user,evaluation_date=D)
        self.assertIs(context.user_input,user)
        self.assertIsNone(context.assessment)
        self.assertIsNone(context.option_request)
        self.assertEqual(context.blocking_reasons,('missing_source_submission',))

    def test_hints_not_copied_into_evidence(self):
        submission=make_submission()
        user=UserEventInput('Unsupported bullish claim', ('WRONG',), ('user://unverified',), datetime.date(2099,1,1))
        context=prepare_event_entry_research(user,evaluation_date=D,submission=submission,
            grounding_methodology='Retained filing supports ABC instead; hints remain unverified.',
            selected_hypothesis=submission.hypotheses[0])
        self.assertIs(context.assessment.submission,submission)
        self.assertEqual(context.option_request.underlying_key.symbol,'ABC')
        self.assertNotIn('user://unverified',repr(submission))
        self.assertNotIn('Unsupported bullish claim',repr(submission))

    def test_explicit_grounding_required(self):
        context=self.run_entry(grounding_methodology=None)
        self.assertEqual(context.blocking_reasons,('missing_grounding_methodology',))
        self.assertIsNone(context.option_request)

    def test_missing_source_evidence_fails_existing_ei(self):
        original=make_submission()
        hypothesis=replace(original.hypotheses[0], supporting_statement_ids=(), contradicting_statement_ids=())
        submission=replace(original,sources=(),statements=(),hypotheses=(hypothesis,))
        context=self.run_entry(submission,selected_hypothesis=None)
        self.assertIsNot(context.assessment.status,EventIntelligenceAcceptanceStatus.ACCEPTED)
        self.assertIsNone(context.option_request)
        self.assertTrue(context.assessment.issues)

    def test_no_default_hypothesis_selection(self):
        context=self.run_entry(selected_hypothesis=None)
        self.assertIs(context.assessment.status,EventIntelligenceAcceptanceStatus.ACCEPTED)
        self.assertIsNone(context.option_request)
        self.assertEqual(context.blocking_reasons,('missing_selected_hypothesis',))

    def test_selected_hypothesis_must_retain_identity(self):
        with self.assertRaisesRegex(ValueError,'identity'):
            self.run_entry(selected_hypothesis=make_submission().hypotheses[0])

    def test_existing_bounded_maturity_preserved(self):
        context=self.run_entry()
        self.assertEqual(context.option_request.minimum_expiration_date,datetime.date(2030,2,9))
        self.assertEqual(context.option_request.maximum_expiration_date,D+datetime.timedelta(days=150))
        with self.assertRaisesRegex(ValueError,'absent_expected_window'):
            self.run_entry(maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH)

    def test_stale_and_boundary_day(self):
        self.assertIsNotNone(self.run_entry(evaluation_date=datetime.date(2030,1,10)).option_request)
        with self.assertRaisesRegex(ValueError,'expired'):
            self.run_entry(evaluation_date=datetime.date(2030,1,11))

    def test_structural_reuses_request_and_browser(self):
        browser=make_browser()
        old=browser.discovery_evidence.discovery_request
        sub=old.discovery_entry_handoff.acceptance_result.submission
        context=self.run_entry(sub,evaluation_date=old.evaluation_date,
                               maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH)
        self.assertIsNone(sub.hypotheses[0].expected_window)
        self.assertIs(context.option_request.hypothesis_maturity_alignment,HypothesisMaturityAlignment.NOT_ESTABLISHED)
        self.assertEqual(context.option_request.minimum_expiration_date,old.minimum_expiration_date)
        evidence=replace(browser.discovery_evidence,discovery_request=context.option_request)
        reused=create_futu_exact_contract_browser(evidence)
        self.assertEqual(reused.rows,browser.rows)
        self.assertIs(reused.discovery_evidence.discovery_request,context.option_request)
        self.assertEqual(context.entry_origin,'EVENT_ENTRY')
        with self.assertRaisesRegex(ValueError,'missing_authoritative_maturity_anchor'):
            self.run_entry(sub,evaluation_date=old.evaluation_date)

    def test_no_window_invented_for_incomplete_hypothesis(self):
        sub=make_submission()
        sub=replace(sub,hypotheses=(replace(sub.hypotheses[0],expected_window=None),))
        context=self.run_entry(sub)
        self.assertIsNone(context.option_request)
        self.assertIsNone(context.assessment.submission.hypotheses[0].expected_window)

    def test_no_candidate_direct_entry_or_provider_operations(self):
        with mock.patch('convexity_hunter.providers.futu.initialize_futu_quote_context',side_effect=AssertionError), \
             mock.patch('convexity_hunter.event_discovery.select_event_candidate',side_effect=AssertionError):
            context=self.run_entry()
        self.assertFalse(hasattr(context,'selected_structure'))
        self.assertFalse(hasattr(context,'candidate'))
        self.assertFalse(hasattr(context,'score'))
        self.assertIsNotNone(context.option_request)

    def test_input_validation(self):
        with self.assertRaises(ValueError): UserEventInput(' ')
        with self.assertRaises(TypeError): UserEventInput('event',provisional_symbols=['ABC'])
        with self.assertRaises(TypeError): UserEventInput('event',event_date=datetime.datetime.now())
        with self.assertRaises(TypeError): prepare_event_entry_research('raw',evaluation_date=D)


if __name__=='__main__': unittest.main()
