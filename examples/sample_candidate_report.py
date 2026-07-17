"""Build and render a fixed bilingual synthetic candidate research record."""

import argparse
import datetime

from convexity_hunter.evidence import (
    CandidateState,
    ClassifiedEvidence,
    EvidenceImpact,
    EvidenceKind,
    OptionLeg,
    OptionStructure,
    Scenario,
    StructureCosts,
    TailPricingSlice,
    TermVolatilityPoint,
    VolatilityEnvironment,
)
from convexity_hunter.report import (
    CandidateResearchRecord,
    LegVolatilityInput,
    ScenarioResult,
    StructureLiquidity,
    render_candidate_markdown,
)


FIXTURE_TEXT = {
    "en": {
        "greeks": "synthetic fixture Greeks; total-position scaling by quantity and multiplier; synthetic daily theta convention",
        "quote": "synthetic fixture total-position quote assembled from synthetic leg quotes",
        "delta": "synthetic fixture spot-delta convention with synthetic linear IV interpolation",
        "pricing": "synthetic fixture supplied valuations; illustrative model assumptions for rates, dividends, proportional IV shocks, and interpolation; no pricing performed",
        "support_statement": "Synthetic reference ATM IV is at the 28th historical percentile and 2.50 percentage points below its historical median. This is only an investigation signal and is not proof that options are cheap.",
        "support_source": "synthetic fixture volatility-environment data",
        "support_method": "synthetic fixture percentile and median comparison using 252 end-of-day observations",
        "gap_statement": "Synthetic reference ATM IV exceeds matched-horizon realized volatility by 2.50 percentage points.",
        "gap_source": "synthetic fixture volatility-environment data",
        "gap_method": "synthetic fixture matched 30-day annualized implied-versus-realized comparison",
        "cost_statement": "Synthetic repeated entry costs would consume 7.45% of the assumed portfolio across three attempts.",
        "cost_source": "synthetic fixture structure-cost inputs",
        "cost_method": "synthetic fixture total entry cost multiplied by three attempts",
        "assumption_statement": "The expected holding period is assumed to be 14 calendar days.",
        "assumption_source": "synthetic fixture research assumption",
        "assumption_method": "synthetic fixture declared holding-horizon assumption",
        "ai_evidence": "The synthetic evidence is mixed and warrants human review rather than a conclusion.",
        "ai_source": "synthetic fixture interpretation",
        "ai_method": "synthetic fixture deterministic narrative supplied by the example",
        "rationale": "WATCH is supplied only to exercise the report model and is not a screening conclusion.",
        "hypothesis": "A synthetic SPY long straddle may merit further investigation if its declared convex payoff paths appear favorable relative to total-position costs.",
        "falsification": (
            "Volatility-environment support fails if real data show that structure-relevant ATM IV is not below its own historical median under the declared methodology.",
            "The convexity-versus-cost hypothesis fails if reproducible valuation using real quotes shows that reasonable two-sided move scenarios do not overcome entry cost, time decay, and estimated exit cost over the expected holding horizon.",
        ),
        "missing": ("No current or historical market data has been supplied.", "No independently validated pricing output has been supplied."),
        "false_positive": ("Invented values may accidentally resemble a favorable historical configuration.", "The simplified proportional IV shocks do not model skew or surface changes."),
        "ai_interpretation": "Interpretation only: this synthetic fixture demonstrates report organization and does not establish that any real option structure is attractive.",
        "questions": ("Are the synthetic cost fields internally understandable?", "Does each scenario disclose enough methodology for audit?", "Which real-data controls are required before this format is used for research?"),
    },
    "zh-CN": {
        "greeks": "合成样例希腊字母数据；已按数量与合约乘数缩放为总仓位；Theta 使用合成样例的每日口径",
        "quote": "合成样例数据：由合成的各腿报价汇总为总仓位报价",
        "delta": "合成样例数据：采用现货 Delta 口径与合成的隐含波动率线性插值",
        "pricing": "合成样例数据：直接提供估值结果，并使用示意性的利率、股息、比例 IV 变动与插值假设；脚本未执行期权定价",
        "support_statement": "合成样例的参考 ATM 隐含波动率位于历史第 28 百分位，并且比合成历史中位数低 2.50 个百分点。这只表示可能值得进一步调查，并不能证明期权便宜。",
        "support_source": "合成样例波动率环境数据",
        "support_method": "合成样例数据：使用 252 个日终观测值比较历史百分位与中位数",
        "gap_statement": "合成样例的参考 ATM 隐含波动率仍比匹配期限的实现波动率高 2.50 个百分点，说明相对于近期实现波动，期权并非明显便宜。",
        "gap_source": "合成样例波动率环境数据",
        "gap_method": "合成样例数据：采用匹配的 30 天年化隐含波动率与实现波动率比较",
        "cost_statement": "如果连续三次尝试均失败，合成样例的累计成本将占假设的 100,000 美元组合的 7.45%。",
        "cost_source": "合成样例结构成本数据",
        "cost_method": "合成样例数据：总入场成本乘以三次尝试",
        "assumption_statement": "预计持有期假设为 14 个日历日。",
        "assumption_source": "合成样例研究假设",
        "assumption_method": "合成样例数据：已声明的持有期假设",
        "ai_evidence": "合成证据方向并不一致，因此需要人工复核，而不是直接得出结论。",
        "ai_source": "合成样例 AI 解读",
        "ai_method": "合成样例数据：由示例提供的确定性叙述",
        "rationale": "观察（WATCH）状态仅用于演示报告模型，并不是筛选结论。",
        "hypothesis": "如果已声明的凸性收益路径相对于总仓位成本具有研究价值，这个合成的 SPY 买入跨式结构可能值得进一步调查。",
        "falsification": ("当合成输入替换为真实数据后，如果按已声明方法计算的结构相关 ATM 隐含波动率不低于其自身历史中位数，则波动率环境的支持理由失效。", "如果使用真实报价进行可复现估值后，合理的双向变动情景在预计持有期内仍无法覆盖入场成本、时间损耗和预估退出成本，则凸性相对于成本的研究假设失效。"),
        "missing": ("尚未提供当前或历史真实市场数据。", "尚未提供经过独立验证的定价结果。"),
        "false_positive": ("虚构数值可能偶然类似某段有利的历史环境。", "简化的比例 IV 变动没有模拟偏斜或波动率曲面的变化。"),
        "ai_interpretation": "仅作 AI 解读：该合成样例用于展示报告组织方式，不能证明任何真实期权结构具有吸引力。",
        "questions": ("合成成本字段是否足够清晰？", "每个情景是否披露了足够的方法信息以便审计？", "在该格式用于真实研究前，需要加入哪些真实数据控制？"),
    },
}


def build_synthetic_candidate(locale: str = "en") -> CandidateResearchRecord:
    """Return a complete localized long-straddle demonstration record."""

    if not isinstance(locale, str):
        raise TypeError("locale must be a string")
    normalized_locale = locale.strip()
    if normalized_locale not in FIXTURE_TEXT:
        raise ValueError("locale is not supported")
    text = FIXTURE_TEXT[normalized_locale]

    as_of_date = datetime.date(2030, 1, 2)
    expiration = datetime.date(2030, 2, 16)
    call = OptionLeg("SPY", "call", 500.0, expiration)
    put = OptionLeg("SPY", "put", 500.0, expiration)
    structure = OptionStructure(
        legs=(call, put),
        assumed_portfolio_value=100_000.0,
        expected_holding_days=14,
    )

    costs = StructureCosts(
        structure=structure,
        as_of_date=as_of_date,
        quoted_mid_premium=2_400.0,
        estimated_spread_cost=80.0,
        commissions_and_fees=2.60,
        theta_per_day=-45.0,
        gamma=0.55,
        underlying_price=500.0,
        greeks_methodology=text["greeks"],
        repeated_bet_count=3,
    )
    liquidity = StructureLiquidity(
        structure=structure,
        as_of_date=as_of_date,
        quoted_bid_value=2_320.0,
        quoted_ask_value=2_480.0,
        minimum_leg_open_interest=1_200,
        minimum_leg_daily_volume=350,
        quote_methodology=text["quote"],
    )
    volatility_environment = VolatilityEnvironment(
        underlying="SPY",
        as_of_date=as_of_date,
        reference_tenor_days=30,
        iv_percentile=0.28,
        iv_history_lookback_observations=252,
        historical_median_atm_iv=0.225,
        matched_realized_volatility=0.175,
        matched_realized_window_days=30,
        term_structure=(
            TermVolatilityPoint(30, 0.20),
            TermVolatilityPoint(60, 0.215),
        ),
    )
    tail_pricing_slices = (
        TailPricingSlice(
            underlying="SPY",
            as_of_date=as_of_date,
            expiration=expiration,
            atm_iv=0.20,
            put_25_delta_iv=0.218,
            call_25_delta_iv=0.205,
            put_10_delta_iv=0.245,
            call_10_delta_iv=0.219,
            skew_percentile=0.32,
            skew_history_lookback_observations=252,
            delta_methodology=text["delta"],
        ),
        TailPricingSlice(
            underlying="SPY",
            as_of_date=as_of_date,
            expiration=datetime.date(2030, 3, 15),
            atm_iv=0.21,
            put_25_delta_iv=0.231,
            call_25_delta_iv=0.214,
            put_10_delta_iv=0.262,
            call_10_delta_iv=0.229,
            skew_percentile=0.38,
            skew_history_lookback_observations=252,
            delta_methodology=text["delta"],
        ),
    )

    volatility_inputs = (
        LegVolatilityInput(call, 0.198),
        LegVolatilityInput(put, 0.202),
    )
    pricing_methodology = text["pricing"]
    scenario_results = (
        ScenarioResult(
            structure=structure,
            as_of_date=as_of_date,
            scenario=Scenario(-0.10, 0.50, "immediate"),
            valuation_date=as_of_date,
            base_underlying_price=costs.underlying_price,
            leg_volatility_inputs=volatility_inputs,
            estimated_position_value=5_200.0,
            entry_cost_basis=costs.total_entry_cost,
            estimated_exit_cost=90.0,
            pricing_methodology=pricing_methodology,
        ),
        ScenarioResult(
            structure=structure,
            as_of_date=as_of_date,
            scenario=Scenario(0.0, -0.20, "immediate"),
            valuation_date=as_of_date,
            base_underlying_price=costs.underlying_price,
            leg_volatility_inputs=volatility_inputs,
            estimated_position_value=1_600.0,
            entry_cost_basis=costs.total_entry_cost,
            estimated_exit_cost=30.0,
            pricing_methodology=pricing_methodology,
        ),
        ScenarioResult(
            structure=structure,
            as_of_date=as_of_date,
            scenario=Scenario(0.15, 0.20, "holding_horizon"),
            valuation_date=as_of_date + datetime.timedelta(days=14),
            base_underlying_price=costs.underlying_price,
            leg_volatility_inputs=volatility_inputs,
            estimated_position_value=9_000.0,
            entry_cost_basis=costs.total_entry_cost,
            estimated_exit_cost=110.0,
            pricing_methodology=pricing_methodology,
        ),
        ScenarioResult(
            structure=structure,
            as_of_date=as_of_date,
            scenario=Scenario(-0.20, 0.0, "expiration"),
            valuation_date=expiration,
            base_underlying_price=costs.underlying_price,
            leg_volatility_inputs=volatility_inputs,
            estimated_position_value=10_000.0,
            entry_cost_basis=costs.total_entry_cost,
            estimated_exit_cost=0.0,
            pricing_methodology=pricing_methodology,
        ),
    )

    evidence = (
        ClassifiedEvidence(
            evidence_id="SYNTHETIC-CALC-SUPPORT",
            kind=EvidenceKind.CALCULATED_METRIC,
            impact=EvidenceImpact.SUPPORTS,
            statement=text["support_statement"],
            source=text["support_source"],
            methodology=text["support_method"],
        ),
        ClassifiedEvidence(
            evidence_id="SYNTHETIC-CALC-WEAKEN-IV-GAP",
            kind=EvidenceKind.CALCULATED_METRIC,
            impact=EvidenceImpact.WEAKENS,
            statement=text["gap_statement"],
            source=text["gap_source"],
            methodology=text["gap_method"],
        ),
        ClassifiedEvidence(
            evidence_id="SYNTHETIC-CALC-WEAKEN",
            kind=EvidenceKind.CALCULATED_METRIC,
            impact=EvidenceImpact.WEAKENS,
            statement=text["cost_statement"],
            source=text["cost_source"],
            methodology=text["cost_method"],
        ),
        ClassifiedEvidence(
            evidence_id="SYNTHETIC-ASSUMPTION",
            kind=EvidenceKind.ASSUMPTION,
            impact=EvidenceImpact.NEUTRAL,
            statement=text["assumption_statement"],
            source=text["assumption_source"],
            methodology=text["assumption_method"],
        ),
        ClassifiedEvidence(
            evidence_id="SYNTHETIC-AI-INTERPRETATION",
            kind=EvidenceKind.AI_INTERPRETATION,
            impact=EvidenceImpact.NEUTRAL,
            statement=text["ai_evidence"],
            source=text["ai_source"],
            methodology=text["ai_method"],
        ),
    )

    return CandidateResearchRecord(
        candidate_id="SYNTHETIC-SPY-STRADDLE-001",
        state=CandidateState.WATCH,
        state_rationale=text["rationale"],
        as_of_date=as_of_date,
        hypothesis=text["hypothesis"],
        structure=structure,
        volatility_environment=volatility_environment,
        tail_pricing_slices=tail_pricing_slices,
        costs=costs,
        liquidity=liquidity,
        scenario_results=scenario_results,
        evidence=evidence,
        falsification_conditions=text["falsification"],
        missing_data=text["missing"],
        false_positive_reasons=text["false_positive"],
        ai_interpretation=text["ai_interpretation"],
        human_review_questions=text["questions"],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render a synthetic candidate report.")
    parser.add_argument("--locale", choices=("en", "zh-CN"), default="zh-CN")
    arguments = parser.parse_args()
    print(
        render_candidate_markdown(
            build_synthetic_candidate(arguments.locale), arguments.locale
        ),
        end="",
    )
