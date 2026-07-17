"""Tests for deterministic bilingual candidate Markdown rendering."""

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


def economic_signature(candidate: CandidateResearchRecord) -> tuple:
    costs = candidate.costs
    liquidity = candidate.liquidity
    environment = candidate.volatility_environment
    return (
        candidate.candidate_id,
        candidate.state,
        candidate.as_of_date,
        candidate.structure,
        None if costs is None else (
            costs.as_of_date,
            costs.quoted_mid_premium,
            costs.estimated_spread_cost,
            costs.commissions_and_fees,
            costs.theta_per_day,
            costs.gamma,
            costs.underlying_price,
            costs.repeated_bet_count,
        ),
        None if liquidity is None else (
            liquidity.as_of_date,
            liquidity.quoted_bid_value,
            liquidity.quoted_ask_value,
            liquidity.minimum_leg_open_interest,
            liquidity.minimum_leg_daily_volume,
        ),
        None if environment is None else (
            environment.underlying,
            environment.as_of_date,
            environment.reference_tenor_days,
            environment.iv_percentile,
            environment.iv_history_lookback_observations,
            environment.historical_median_atm_iv,
            environment.matched_realized_volatility,
            environment.matched_realized_window_days,
            tuple((point.tenor_days, point.atm_iv) for point in environment.term_structure),
        ),
        tuple(
            (
                item.underlying,
                item.as_of_date,
                item.expiration,
                item.atm_iv,
                item.put_25_delta_iv,
                item.call_25_delta_iv,
                item.put_10_delta_iv,
                item.call_10_delta_iv,
                item.skew_percentile,
                item.skew_history_lookback_observations,
            )
            for item in candidate.tail_pricing_slices
        ),
        tuple(
            (
                result.scenario,
                result.valuation_date,
                result.base_underlying_price,
                result.base_ivs,
                result.estimated_position_value,
                result.entry_cost_basis,
                result.estimated_exit_cost,
            )
            for result in candidate.scenario_results
        ),
        tuple((item.evidence_id, item.kind, item.impact) for item in candidate.evidence),
    )


class LocaleValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = build_synthetic_candidate("en")

    def test_renderer_defaults_to_english(self) -> None:
        self.assertEqual(
            render_candidate_markdown(self.candidate),
            render_candidate_markdown(self.candidate, "en"),
        )

    def test_renderer_accepts_supported_and_normalized_locales(self) -> None:
        self.assertIn("# Convexity Hunter Research Record", render_candidate_markdown(self.candidate, "en"))
        self.assertIn("# Convexity Hunter 候选研究报告", render_candidate_markdown(build_synthetic_candidate("zh-CN"), "zh-CN"))
        self.assertEqual(
            render_candidate_markdown(self.candidate, "  en  "),
            render_candidate_markdown(self.candidate, "en"),
        )

    def test_renderer_rejects_invalid_candidate_and_locale(self) -> None:
        with self.assertRaises(TypeError):
            render_candidate_markdown("candidate")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            render_candidate_markdown(self.candidate, 1)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            render_candidate_markdown(self.candidate, "fr")

    def test_builder_accepts_supported_locales_and_defaults_to_english(self) -> None:
        self.assertEqual(build_synthetic_candidate().state_rationale, build_synthetic_candidate("en").state_rationale)
        self.assertIn("观察", build_synthetic_candidate("zh-CN").state_rationale)

    def test_builder_rejects_invalid_locale(self) -> None:
        with self.assertRaises(TypeError):
            build_synthetic_candidate(1)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            build_synthetic_candidate("fr")


class BilingualReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.en_candidate = build_synthetic_candidate("en")
        self.zh_candidate = build_synthetic_candidate("zh-CN")
        self.en = render_candidate_markdown(self.en_candidate, "en")
        self.zh = render_candidate_markdown(self.zh_candidate, "zh-CN")

    def test_chinese_title_warning_and_overview_order(self) -> None:
        self.assertTrue(self.zh.startswith("# Convexity Hunter 候选研究报告\n"))
        self.assertIn("> **合成演示数据——不是当前市场数据，也不是交易建议**", self.zh)
        self.assertIn("## 通俗概要：先看懂这份报告", self.zh)
        self.assertNotIn("小白", self.zh)
        self.assertLess(self.zh.index("## 通俗概要：先看懂这份报告"), self.zh.index("## 技术研究明细"))

    def test_chinese_seven_overview_sections_are_ordered(self) -> None:
        headings = (
            "### 1. 研究的是什么？", "### 2. 当前状态是什么？",
            "### 3. 为什么可能值得关注？", "### 4. 为什么仍然需要谨慎？",
            "### 5. 最多可能损失多少？", "### 6. 在给定情景下，结果可能怎样？",
            "### 7. 接下来需要人工核实什么？",
        )
        positions = [self.zh.index(item) for item in headings]
        self.assertEqual(positions, sorted(positions))

    def test_chinese_overview_content(self) -> None:
        self.assertIn("观察（watch）", self.zh)
        self.assertIn("同时买入相同执行价和到期日的看涨期权与看跌期权", self.zh)
        self.assertIn("$2,482.60", self.zh)
        self.assertIn("2.48%", self.zh)
        self.assertIn("$7,447.80", self.zh)
        self.assertIn("7.45%", self.zh)
        self.assertIn("3 个盈利、1 个亏损、0 个盈亏为零", self.zh)
        self.assertIn("已提供情景中的最高结果", self.zh)
        self.assertIn("$7,517.40", self.zh)
        self.assertIn("已提供情景中的最低结果", self.zh)
        self.assertIn("-$912.60", self.zh)
        self.assertIn("这里只比较报告中已提供的情景，不代表所有可能结果，也不是收益预测。", self.zh)

    def test_chinese_technical_report_is_localized(self) -> None:
        for text in (
            "### 研究假设", "### 具体期权结构", "### 有限损失与成本", "### 流动性",
            "### 第一层——整体波动率定价环境", "### 第二层——尾部相对定价",
            "### 情景分析", "### 证据", "#### 支持证据", "#### 弱化证据",
            "#### 中性证据", "### 证伪条件", "### 缺失数据", "### 假阳性风险",
            "### AI 解读", "### 人工复核问题", "| 期权腿 | 类型 | 执行价 |",
            "| 估值时间 | 估值日期 | 标的变动 |", "计算指标（calculated_metric）",
            "合成样例波动率环境数据",
        ):
            with self.subTest(text=text):
                self.assertIn(text, self.zh)
        self.assertTrue(self.zh.endswith("本记录用于整理研究证据，不推荐、不执行，也不保证任何交易或投资结果。\n"))

    def test_chinese_technical_heading_hierarchy(self) -> None:
        lines = self.zh.splitlines()
        parent_index = lines.index("## 技术研究明细")
        child_headings = (
            "研究假设", "具体期权结构", "有限损失与成本", "流动性",
            "第一层——整体波动率定价环境", "第二层——尾部相对定价", "情景分析", "证据",
            "证伪条件", "缺失数据", "假阳性风险", "AI 解读", "人工复核问题",
        )
        for heading in child_headings:
            with self.subTest(heading=heading):
                self.assertGreater(lines.index(f"### {heading}"), parent_index)
                self.assertNotIn(f"## {heading}", lines)
        for heading in ("支持证据", "弱化证据", "中性证据"):
            self.assertGreater(lines.index(f"#### {heading}"), lines.index("### 证据"))

    def test_english_title_warning_and_overview_order(self) -> None:
        self.assertTrue(self.en.startswith("# Convexity Hunter Research Record\n"))
        self.assertIn("> **SYNTHETIC DEMONSTRATION — NOT CURRENT MARKET DATA AND NOT A TRADE RECOMMENDATION**", self.en)
        self.assertLess(self.en.index("## Plain-language overview"), self.en.index("## Technical research details"))

    def test_english_seven_overview_sections_and_content(self) -> None:
        headings = tuple(f"### {number}. {title}" for number, title in (
            (1, "What is being studied?"), (2, "What is the current status?"),
            (3, "Why might it deserve attention?"), (4, "Why is caution still necessary?"),
            (5, "How much could be lost?"), (6, "What happens in the supplied scenarios?"),
            (7, "What should a human verify next?"),
        ))
        positions = [self.en.index(item) for item in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("buying a call and a put with the same strike and expiration", self.en)
        self.assertIn("$2,482.60", self.en)
        self.assertIn("Among the supplied scenarios: 3 positive, 1 negative", self.en)
        self.assertIn("Highest result among supplied scenarios", self.en)
        self.assertIn("Lowest result among supplied scenarios", self.en)

    def test_existing_english_technical_semantics_remain(self) -> None:
        for text in (
            "### Research hypothesis", "### Concrete option structure",
            "### Bounded downside and costs", "### Scenario analysis",
            "#### Supporting evidence", "#### Weakening evidence", "#### Neutral evidence",
            "28th historical percentile", "not proof that options are cheap",
            "SYNTHETIC-CALC-WEAKEN-IV-GAP",
            "Volatility-environment support fails if real data show",
        ):
            self.assertIn(text, self.en)
        self.assertTrue(self.en.endswith("This record organizes research evidence. It does not recommend, execute, or guarantee any trade or investment outcome.\n"))

    def test_english_technical_heading_hierarchy(self) -> None:
        lines = self.en.splitlines()
        parent_index = lines.index("## Technical research details")
        child_headings = (
            "Research hypothesis", "Concrete option structure", "Bounded downside and costs", "Liquidity",
            "Layer 1 — Volatility pricing environment", "Layer 2 — Tail relative pricing",
            "Scenario analysis", "Evidence", "Falsification conditions", "Missing data",
            "False-positive risks", "AI interpretation", "Human-review questions",
        )
        for heading in child_headings:
            with self.subTest(heading=heading):
                self.assertGreater(lines.index(f"### {heading}"), parent_index)
                self.assertNotIn(f"## {heading}", lines)
        for heading in ("Supporting evidence", "Weakening evidence", "Neutral evidence"):
            self.assertGreater(lines.index(f"#### {heading}"), lines.index("### Evidence"))

    def test_shared_determinism_newlines_and_no_repr(self) -> None:
        for locale, candidate, rendered in (("en", self.en_candidate, self.en), ("zh-CN", self.zh_candidate, self.zh)):
            with self.subTest(locale=locale):
                self.assertEqual(rendered, render_candidate_markdown(candidate, locale))
                self.assertTrue(rendered.endswith("\n"))
                self.assertFalse(rendered.endswith("\n\n"))
                self.assertNotIn("CandidateResearchRecord(", rendered)
                self.assertNotIn(" object at 0x", rendered)

    def test_minimal_candidate_renders_both_locales_with_localized_missing_values(self) -> None:
        candidate = build_minimal_watch()
        en = render_candidate_markdown(candidate, "en")
        zh = render_candidate_markdown(candidate, "zh-CN")
        self.assertIn("## Plain-language overview", en)
        self.assertIn("## 通俗概要：先看懂这份报告", zh)
        self.assertGreaterEqual(en.count("Not supplied."), 6)
        self.assertGreaterEqual(zh.count("未提供。"), 6)
        self.assertIn("No supporting evidence is currently reported.", en)
        self.assertIn("目前没有已报告的支持证据。", zh)

    def test_evidence_groups_remain_separate_in_both_languages(self) -> None:
        for rendered, headings in ((self.en, ("#### Supporting evidence", "#### Weakening evidence", "#### Neutral evidence")), (self.zh, ("#### 支持证据", "#### 弱化证据", "#### 中性证据"))):
            support, weaken, neutral = [rendered.index(item) for item in headings]
            self.assertIn("SYNTHETIC-CALC-SUPPORT", rendered[support:weaken])
            self.assertIn("SYNTHETIC-CALC-WEAKEN-IV-GAP", rendered[weaken:neutral])
            self.assertIn("SYNTHETIC-ASSUMPTION", rendered[neutral:])

    def test_cross_language_economic_and_identity_signature_matches(self) -> None:
        self.assertEqual(economic_signature(self.en_candidate), economic_signature(self.zh_candidate))
        self.assertNotEqual(self.en_candidate.hypothesis, self.zh_candidate.hypothesis)
        self.assertNotEqual(self.en_candidate.state_rationale, self.zh_candidate.state_rationale)

    def test_static_files_match_and_old_file_is_absent(self) -> None:
        zh_path = ROOT / "data" / "samples" / "sample-candidate-report.zh-CN.md"
        en_path = ROOT / "data" / "samples" / "sample-candidate-report.en.md"
        old_path = ROOT / "data" / "samples" / "sample-candidate-report.md"
        self.assertEqual(zh_path.read_text(), self.zh)
        self.assertEqual(en_path.read_text(), self.en)
        self.assertFalse(old_path.exists())


if __name__ == "__main__":
    unittest.main()
