"""Presentation-only checks using existing synthetic domain fixtures."""
import datetime
import decimal
import json
import unittest
from tests.test_convexity_discrimination import (
    make_browser, make_quote_batch, make_bar, quote_for, NOW,
    DistributionChangeMode, discrimination, futu,
)
from convexity_hunter.convexity_presentation import render_convexity_comparison_markdown


def result(browser=None, factory=quote_for):
    browser = browser or make_browser()
    latest = datetime.date(2029, 12, 31)
    return discrimination.discriminate_probability_free_convexity(
        browser, make_quote_batch(browser, factory), (make_bar(browser, latest),),
        latest_completed_session_date=latest,
    )


def audit(text):
    return json.loads(text.split('```json\n')[1].split('\n```')[0])


def rows(text):
    return [line for line in text.splitlines() if line.startswith('|2030')]


class PresentationTests(unittest.TestCase):
    def test_complete_order_and_distant_longer_rows(self):
        value = result(make_browser(expirations=(datetime.date(2030, 3, 15), datetime.date(2030, 5, 17)),
                                    strikes=(decimal.Decimal('10'), decimal.Decimal('100'), decimal.Decimal('500'))))
        actual = rows(render_convexity_comparison_markdown(value))
        self.assertEqual(len(actual), 6)
        self.assertEqual([(r.split('|')[1], r.split('|')[2]) for r in actual],
                         [(str(c.structure.rows[0].expiration), str(c.structure.rows[0].strike)) for c in value.comparisons])

    def test_primary_golden_fields(self):
        row = rows(render_convexity_comparison_markdown(result()))[0]
        self.assertEqual(row, '|2030-03-15|100|LONG_STRADDLE|TWO_SIDED_AVAILABLE, TWO_SIDED_AVAILABLE|4.0000|4.0000%|-4.0000% / 4.0000%|-8.0000% / 8.0000%|7.5000x / 5.0000x / 2.5000x|2.5000x / 5.0000x / 7.5000x|')
        for excluded in ('US.NDAQ', 'relative_spread', '5x', '10x', 'numerator'):
            self.assertNotIn(excluded, row)

    def test_audit_complete_exact_evidence(self):
        value = result()
        data = audit(render_convexity_comparison_markdown(value))['result']
        comp = data['comparisons'][0]
        self.assertEqual(len(comp['response_ladder']), 9)
        self.assertEqual([h['gross_value_multiple'] for h in comp['payoff_multiple_hurdles']], [1,1,2,2,5,5,10,10])
        self.assertEqual(comp['structure']['rows'][0]['provider_identifier'], value.comparisons[0].structure.rows[0].provider_identifier)
        self.assertEqual(comp['premium_to_reference']['ratio_to_reference'], {'numerator':1,'denominator':25})
        self.assertIn('relative_spread', comp['indicative_relative_spread'])
        self.assertEqual(data['reference_price']['observation']['metadata']['source_references'][0]['provider_name'], 'Futu OpenAPI')

    def test_threshold_unavailable_reason(self):
        value = result(make_browser(strikes=(decimal.Decimal('1'),)))
        text = render_convexity_comparison_markdown(value)
        self.assertIn('UNAVAILABLE[negative_underlying_threshold]', rows(text)[0])
        self.assertIn('negative_underlying_threshold', json.dumps(audit(text)))

    def test_ask_unavailable_no_imputation(self):
        def missing(row, index):
            return futu.FutuBrowserQuoteEvidence(row,index,futu.FutuBrowserQuoteAvailability.UNAVAILABLE,
                None,None,None,None,None,None,None,(futu.FutuBrowserQuoteReasonCode.NO_FRAME_RECEIVED,))
        text = render_convexity_comparison_markdown(result(factory=missing))
        self.assertEqual(len(rows(text)),1)
        self.assertIn('UNAVAILABLE[straddle_leg_ask_unavailable]',rows(text)[0])
        self.assertIn('no_frame_received',json.dumps(audit(text)))
        self.assertNotIn('0.0000', rows(text)[0])

    def test_ask_only_and_spread_retained_in_audit(self):
        text = render_convexity_comparison_markdown(result(factory=lambda r,i: quote_for(r,i,bid=None)))
        self.assertIn('ASK_SIDE_AVAILABLE',rows(text)[0])
        self.assertEqual(audit(text)['result']['comparisons'][0]['indicative_relative_spread']['status']['name'],'UNAVAILABLE')

    def test_authorities_and_reference(self):
        value=result(); text=render_convexity_comparison_markdown(value)
        authority=audit(text)['authority']
        self.assertEqual(authority['quote_authority'],'INDICATIVE_ONLY')
        self.assertEqual(authority['hypothesis_maturity_alignment'], value.hypothesis_maturity_alignment.name)
        self.assertEqual(authority['payoff_geometry_authority'],'CONDITIONAL_PROVIDER_STANDARD')
        for key in ('exact_deliverable_verification','quote_reference_temporal_alignment','cross_structure_quote_synchronicity'):
            self.assertEqual(authority[key],'NOT_ESTABLISHED')
        self.assertIn('LATEST_COMPLETED_NORMALIZED_CLOSE',text)
        self.assertIn('不是 current spot',text)

    def test_determinism_without_mutation_or_decimal_context_dependence(self):
        value=result(); before=repr(value)
        first=render_convexity_comparison_markdown(value)
        with decimal.localcontext() as ctx:
            ctx.prec=2
            self.assertEqual(first,render_convexity_comparison_markdown(value))
        self.assertEqual(repr(value),before)

    def test_directional_and_noncomparison_evidence(self):
        for mode in DistributionChangeMode:
            text=render_convexity_comparison_markdown(result(make_browser(mode)))
            self.assertEqual(len(rows(text)),1)
            if mode is not DistributionChangeMode.BIDIRECTIONAL_EXPANSION:
                self.assertIn('NOT_APPLICABLE',rows(text)[0])
                self.assertEqual(len(audit(text)['result']['non_comparison_rows']),1)

    def test_no_ranking_or_selection_columns(self):
        header=next(l for l in render_convexity_comparison_markdown(result()).splitlines() if l.startswith('|Expiration'))
        for token in ('rank','score','nearest','preferred','recommended','selected','spread'):
            self.assertNotIn(token,header.lower())

    def test_wrong_input_rejected(self):
        with self.assertRaises(TypeError): render_convexity_comparison_markdown(None)

    def test_empty_comparisons_still_preserve_browser_rows(self):
        value=result(make_browser(option_types=('call',)))
        text=render_convexity_comparison_markdown(value)
        self.assertEqual(rows(text),[])
        self.assertEqual(len(audit(text)['result']['non_comparison_rows']),1)


if __name__ == '__main__':
    unittest.main()
