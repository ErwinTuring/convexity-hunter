"""Tests for deterministic candidate Markdown rendering."""

import datetime
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from examples.sample_candidate_report import build_synthetic_candidate
from convexity_hunter.evidence import (
    CandidateState,
    ClassifiedEvidence,
    EvidenceImpact,
    EvidenceKind,
    OptionLeg,
    OptionStructure,
)
from convexity_hunter.report import CandidateResearchRecord, render_candidate_markdown


def build_minimal_watch() -> CandidateResearchRecord:
    """Return a valid record with all optional report records absent."""

    expiration = datetime.date(2030, 6, 21)
    structure = OptionStructure(
        legs=(OptionLeg("SPY", "call", 500.0, expiration),),
        assumed_portfolio_value=100_000.0,
        expected_holding_days=7,
    )
    return CandidateResearchRecord(
        candidate_id="MINIMAL-WATCH-001",
        state=CandidateState.WATCH,
        state_rationale="Optional records are intentionally absent.",
        as_of_date=datetime.date(2030, 5, 1),
        hypothesis="The minimal renderer path should remain explicit.",
        structure=structure,
        evidence=(
            ClassifiedEvidence(
                "assumption-1",
                EvidenceKind.ASSUMPTION,
                EvidenceImpact.NEUTRAL,
                "Optional records are assumed unavailable.",
            ),
        ),
        falsification_conditions=("Optional data becomes available.",),
        false_positive_reasons=("The minimal record may omit decisive context.",),
        human_review_questions=("Which optional record should be added first?",),
    )


class CandidateMarkdownRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = build_synthetic_candidate()
        self.rendered = render_candidate_markdown(self.candidate)

    def test_rejects_non_candidate_record(self) -> None:
        with self.assertRaises(TypeError):
            render_candidate_markdown("candidate")  # type: ignore[arg-type]

    def test_returns_string_with_exactly_one_trailing_newline(self) -> None:
        self.assertIsInstance(self.rendered, str)
        self.assertTrue(self.rendered.endswith("\n"))
        self.assertFalse(self.rendered.endswith("\n\n"))

    def test_rendering_is_deterministic(self) -> None:
        self.assertEqual(self.rendered, render_candidate_markdown(self.candidate))

    def test_synthetic_warning_appears(self) -> None:
        self.assertIn(
            "> **SYNTHETIC DEMONSTRATION — NOT CURRENT MARKET DATA AND NOT A TRADE RECOMMENDATION**",
            self.rendered,
        )

    def test_expected_section_order(self) -> None:
        headings = (
            "# Convexity Hunter Research Record",
            "## Research hypothesis",
            "## Concrete option structure",
            "## Bounded downside and costs",
            "## Liquidity",
            "## Layer 1 — Volatility pricing environment",
            "## Layer 2 — Tail relative pricing",
            "## Scenario analysis",
            "## Evidence",
            "### Supporting evidence",
            "### Weakening evidence",
            "### Neutral evidence",
            "## Falsification conditions",
            "## Missing data",
            "## False-positive risks",
            "## AI interpretation",
            "## Human-review questions",
        )
        positions = [self.rendered.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))

    def test_all_structure_legs_appear(self) -> None:
        self.assertIn("| 1 | call | $500.00 | 2030-02-16 | 1 | 100 |", self.rendered)
        self.assertIn("| 2 | put | $500.00 | 2030-02-16 | 1 | 100 |", self.rendered)

    def test_money_and_percentage_formatting(self) -> None:
        self.assertIn("**Assumed portfolio value:** $100,000.00", self.rendered)
        self.assertIn("**Total entry cost:** $2,482.60", self.rendered)
        self.assertIn("**Maximum loss percentage:** 2.48%", self.rendered)
        self.assertIn("**ATM IV:** 20.00%", self.rendered)

    def test_negative_values_retain_sign(self) -> None:
        self.assertIn("**Theta per day:** -$45.00", self.rendered)
        self.assertIn("-$912.60", self.rendered)
        self.assertIn("-20.00%", self.rendered)

    def test_all_optional_section_headings_appear(self) -> None:
        for heading in (
            "## Bounded downside and costs",
            "## Liquidity",
            "## Layer 1 — Volatility pricing environment",
            "## Layer 2 — Tail relative pricing",
            "## Scenario analysis",
            "## Missing data",
            "## AI interpretation",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, self.rendered)

    def test_evidence_groups_remain_separate(self) -> None:
        supporting_start = self.rendered.index("### Supporting evidence")
        weakening_start = self.rendered.index("### Weakening evidence")
        neutral_start = self.rendered.index("### Neutral evidence")
        self.assertIn(
            "SYNTHETIC-CALC-SUPPORT",
            self.rendered[supporting_start:weakening_start],
        )
        self.assertIn(
            "SYNTHETIC-CALC-WEAKEN-IV-GAP",
            self.rendered[weakening_start:neutral_start],
        )
        self.assertIn(
            "SYNTHETIC-CALC-WEAKEN",
            self.rendered[weakening_start:neutral_start],
        )
        self.assertIn("SYNTHETIC-ASSUMPTION", self.rendered[neutral_start:])
        self.assertIn("SYNTHETIC-AI-INTERPRETATION", self.rendered[neutral_start:])

    def test_corrected_evidence_direction_is_rendered(self) -> None:
        supporting_start = self.rendered.index("### Supporting evidence")
        weakening_start = self.rendered.index("### Weakening evidence")
        neutral_start = self.rendered.index("### Neutral evidence")
        supporting = self.rendered[supporting_start:weakening_start]
        weakening = self.rendered[weakening_start:neutral_start]
        self.assertIn("28th historical percentile", supporting)
        self.assertIn(
            "2.50 percentage points below its historical median", supporting
        )
        self.assertIn("not proof that options are cheap", supporting)
        self.assertIn(
            "exceeds matched-horizon realized volatility by 2.50 percentage points",
            weakening,
        )
        self.assertIn("SYNTHETIC-CALC-WEAKEN-IV-GAP", weakening)
        self.assertIn("SYNTHETIC-CALC-WEAKEN", weakening)

    def test_research_falsification_conditions_are_rendered(self) -> None:
        self.assertIn(
            "Volatility-environment support fails if real data show that structure-relevant ATM IV is not below its own historical median under the declared methodology.",
            self.rendered,
        )
        self.assertIn(
            "The convexity-versus-cost hypothesis fails if reproducible valuation using real quotes shows that reasonable two-sided move scenarios do not overcome entry cost, time decay, and estimated exit cost over the expected holding horizon.",
            self.rendered,
        )
        self.assertNotIn(
            "Synthetic scenario coverage fails to preserve bounded loss after declared costs.",
            self.rendered,
        )

    def test_missing_evidence_groups_report_none(self) -> None:
        rendered = render_candidate_markdown(build_minimal_watch())
        supporting = rendered.index("### Supporting evidence")
        weakening = rendered.index("### Weakening evidence")
        neutral = rendered.index("### Neutral evidence")
        self.assertIn("None reported.", rendered[supporting:weakening])
        self.assertIn("None reported.", rendered[weakening:neutral])

    def test_scenario_table_contains_all_sample_scenarios(self) -> None:
        self.assertEqual(self.rendered.count("| immediate |"), 2)
        self.assertIn("| holding_horizon | 2030-01-16 |", self.rendered)
        self.assertIn("| expiration | 2030-02-16 |", self.rendered)

    def test_per_leg_base_and_shocked_ivs_are_rendered(self) -> None:
        self.assertIn("Call: 19.80%; Put: 20.20%", self.rendered)
        self.assertIn("Call: 29.70%; Put: 30.30%", self.rendered)
        self.assertIn("Call: 15.84%; Put: 16.16%", self.rendered)

    def test_net_liquidation_value_is_rendered(self) -> None:
        self.assertIn("| Net liquidation value |", self.rendered)
        self.assertIn("$5,110.00", self.rendered)

    def test_bounded_loss_and_research_footer_appear(self) -> None:
        self.assertIn(
            "Scenario values are supplied research results, not expected returns or probability-weighted forecasts.",
            self.rendered,
        )
        self.assertTrue(
            self.rendered.endswith(
                "This record organizes research evidence. It does not recommend, execute, or guarantee any trade or investment outcome.\n"
            )
        )

    def test_report_contains_no_object_repr_or_memory_address(self) -> None:
        self.assertNotIn("CandidateResearchRecord(", self.rendered)
        self.assertNotIn("ScenarioResult(", self.rendered)
        self.assertNotIn(" object at 0x", self.rendered)

    def test_synthetic_builder_returns_valid_candidate(self) -> None:
        self.assertIsInstance(self.candidate, CandidateResearchRecord)
        self.assertEqual(self.candidate.structure.structure_type, "long_straddle")
        self.assertEqual(len(self.candidate.scenario_results), 4)

    def test_static_markdown_exactly_matches_renderer(self) -> None:
        sample_path = ROOT / "data" / "samples" / "sample-candidate-report.md"
        self.assertEqual(sample_path.read_text(), self.rendered)

    def test_minimal_watch_renders_absent_optional_records(self) -> None:
        rendered = render_candidate_markdown(build_minimal_watch())
        self.assertNotIn("SYNTHETIC DEMONSTRATION", rendered)
        self.assertGreaterEqual(rendered.count("Not supplied."), 6)
        for heading in (
            "## Bounded downside and costs",
            "## Liquidity",
            "## Layer 1 — Volatility pricing environment",
            "## Layer 2 — Tail relative pricing",
            "## Scenario analysis",
            "## AI interpretation",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, rendered)


if __name__ == "__main__":
    unittest.main()
