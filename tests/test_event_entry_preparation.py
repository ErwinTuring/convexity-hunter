"""Small offline research corpus; no market effects required or fabricated."""
import datetime as dt
import unittest
from dataclasses import replace, fields
from unittest.mock import patch

from tests.test_discovery_entry import make_submission
from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.event_entry_preparation import (
    PreparedEventStatement, EventCausalLink, EventEntryHypothesisSelection,
    EventEntryTranslation, prepare_event_entry_hypotheses,
    select_event_entry_hypothesis, translate_event_entry_selection,
)
from convexity_hunter.event_intelligence import EventStatement, EventStatementKind as K
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority as M


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.s = make_submission()
        self.user = UserEventInput('Investigate the announced event')

    def prepare(self, **changes):
        args = dict(sources=self.s.sources,
                    statements=tuple(PreparedEventStatement(s) for s in self.s.statements),
                    hypotheses=self.s.hypotheses,
                    grounding_methodology='Retained source describes event; transmission is conditional.',
                    chronology_review='No already-realized causal effect asserted.')
        args.update(changes)
        return prepare_event_entry_hypotheses(self.user, **args)

    def translate(self, selection):
        return translate_event_entry_selection(
            selection, submission_id='entry-1', event_id='event-1',
            observed_at=self.s.observed_at, event_description=self.s.event_description,
            event_date_range=self.s.event_date_range)

    def choose(self, preparation):
        return select_event_entry_hypothesis(preparation, hypothesis_id=self.s.hypotheses[0].hypothesis_id)

    def test_zero_hypotheses_without_ei(self):
        with patch('convexity_hunter.event_entry.assess_event_intelligence_submission', side_effect=AssertionError):
            p = self.prepare(hypotheses=())
        self.assertEqual(p.hypotheses, ())
        self.assertIs(p.user_input, self.user)

    def test_no_direction_input(self):
        self.assertEqual([f.name for f in fields(UserEventInput)],
                         ['description', 'provisional_symbols', 'source_locators', 'event_date'])
        self.prepare()

    def test_claim_attribution_survives_translation(self):
        fact = replace(self.s.statements[0], text='Researcher alleged: The lab is unsafe')
        wrapped = PreparedEventStatement(fact, claimant='Researcher', claim='The lab is unsafe')
        p = self.prepare(statements=(wrapped, PreparedEventStatement(self.s.statements[1])))
        translation = self.translate(self.choose(p))
        self.assertIs(translation.submission.statements[0], fact)
        self.assertEqual(translation.submission.statements[0].text, 'Researcher alleged: The lab is unsafe')
        with self.assertRaisesRegex(ValueError, 'attributed'):
            replace(wrapped, statement=replace(fact, text='The lab is unsafe'))

    def causal_preparation(self, effect_date):
        cause = PreparedEventStatement(self.s.statements[0], occurrence_date=dt.date(2030,1,3),
                                        date_methodology='Source occurrence date, not publication.')
        effect = PreparedEventStatement(EventStatement('effect', K.OBSERVED_FACT, 'Agency announced action.',
                                                       ('source-1',)), occurrence_date=effect_date,
                                        date_methodology='Agency announcement date.')
        interpretation = PreparedEventStatement(replace(self.s.statements[1],
            dependency_statement_ids=('fact-1', 'effect')))
        return self.prepare(statements=(cause, effect, interpretation),
            causal_links=(EventCausalLink('interpretation-1', 'fact-1', 'effect'),))

    def test_predating_effect_blocks_causal_interpretation(self):
        with self.assertRaisesRegex(ValueError, 'predates'):
            self.causal_preparation(dt.date(2030,1,2))

    def test_temporal_order_not_causal_proof(self):
        p = self.causal_preparation(dt.date(2030,1,4))
        self.assertIs(p.statements[2].statement.kind, K.INTERPRETATION)

    def test_causal_link_missing_date_rejected(self):
        p = self.causal_preparation(dt.date(2030,1,4))
        with self.assertRaisesRegex(ValueError, 'occurrence dates'):
            replace(p, statements=(replace(p.statements[0], occurrence_date=None, date_methodology=None),)
                    + p.statements[1:])

    def test_association_not_promoted(self):
        p = self.prepare(hypotheses=(), statements=(PreparedEventStatement(self.s.statements[0]),))
        self.assertEqual(p.hypotheses, ())
        h = replace(self.s.hypotheses[0], supporting_statement_ids=('fact-1',))
        with self.assertRaisesRegex(ValueError, 'association alone'):
            self.prepare(hypotheses=(h,))

    def test_future_transmission_and_falsification_required(self):
        h = replace(self.s.hypotheses[0], impact_path='Future restriction could delay customer deployment.',
                    expected_window=None, falsification_conditions=('Published rule exempts the product.',))
        p = self.prepare(hypotheses=(h,))
        self.assertIs(p.hypotheses[0], h)
        with self.assertRaisesRegex(ValueError, 'falsification'):
            self.prepare(hypotheses=(replace(h, falsification_conditions=()),))

    def test_no_default_selection(self):
        with self.assertRaises(TypeError):
            select_event_entry_hypothesis(self.prepare())
        with self.assertRaisesRegex(ValueError, 'unknown'):
            select_event_entry_hypothesis(self.prepare(), hypothesis_id='absent')

    def test_none_stops_before_ei(self):
        with patch('convexity_hunter.event_entry.assess_event_intelligence_submission', side_effect=AssertionError):
            selection = select_event_entry_hypothesis(self.prepare(), hypothesis_id=None)
            with self.assertRaisesRegex(ValueError, 'NONE'):
                self.translate(selection)

    def test_identity_to_existing_research(self):
        p = self.prepare()
        translation = self.translate(self.choose(p))
        context = translation.prepare_research(evaluation_date=dt.date(2030,1,3), maturity_authority=M.HYPOTHESIS_ALIGNED)
        self.assertIs(translation.selection.preparation, p)
        self.assertIs(context.user_input, p.user_input)
        self.assertIs(context.assessment.submission, translation.submission)
        self.assertIs(context.option_request.discovery_entry_handoff.selected_hypothesis, p.hypotheses[0])
        self.assertEqual(context.entry_origin, p.entry_origin)
        for a, b in zip(p.sources, translation.submission.sources):
            self.assertIs(a, b)

    def test_no_temporal_invention(self):
        p = self.prepare(hypotheses=(replace(self.s.hypotheses[0], expected_window=None),))
        t = self.translate(self.choose(p))
        context = t.prepare_research(evaluation_date=dt.date(2030,1,3), maturity_authority=M.HYPOTHESIS_ALIGNED)
        self.assertIsNone(t.submission.hypotheses[0].expected_window)
        self.assertIsNone(t.submission.hypotheses[0].reassessment)
        self.assertIsNone(context.option_request)
        self.assertEqual(context.assessment.status.value, 'incomplete')

    def test_no_scores_or_order_changes(self):
        h = self.s.hypotheses[0]
        p = self.prepare(hypotheses=(replace(h, hypothesis_id='z'), replace(h, hypothesis_id='a')))
        self.assertEqual([h.hypothesis_id for h in p.hypotheses], ['z', 'a'])
        self.assertFalse({'score', 'rank', 'recommendation'} & {f.name for f in fields(p)})

    def test_substitution_rejected(self):
        p = self.prepare()
        with self.assertRaisesRegex(ValueError, 'identity'):
            EventEntryHypothesisSelection(p, replace(p.hypotheses[0]))
        t = self.translate(self.choose(p))
        with self.assertRaisesRegex(ValueError, 'identity'):
            EventEntryTranslation(t.selection, replace(t.submission, sources=(replace(p.sources[0]),)))

    def test_dangling_and_cyclic_evidence(self):
        with self.assertRaisesRegex(ValueError, 'dangling'):
            self.prepare(sources=())
        a = EventStatement('a', K.INTERPRETATION, 'A', (), ('b',))
        b = EventStatement('b', K.INTERPRETATION, 'B', (), ('a',))
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            self.prepare(statements=(PreparedEventStatement(a), PreparedEventStatement(b)), hypotheses=())


if __name__ == '__main__':
    unittest.main()
