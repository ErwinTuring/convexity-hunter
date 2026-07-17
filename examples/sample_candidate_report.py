"""Build and render a fixed synthetic candidate research record."""

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


def build_synthetic_candidate() -> CandidateResearchRecord:
    """Return a complete fixed long-straddle demonstration record."""

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
        greeks_methodology=(
            "synthetic fixture Greeks; total-position scaling by quantity and "
            "multiplier; synthetic daily theta convention"
        ),
        repeated_bet_count=3,
    )
    liquidity = StructureLiquidity(
        structure=structure,
        as_of_date=as_of_date,
        quoted_bid_value=2_320.0,
        quoted_ask_value=2_480.0,
        minimum_leg_open_interest=1_200,
        minimum_leg_daily_volume=350,
        quote_methodology=(
            "synthetic fixture total-position quote assembled from synthetic leg quotes"
        ),
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
            delta_methodology=(
                "synthetic fixture spot-delta convention with synthetic linear IV interpolation"
            ),
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
            delta_methodology=(
                "synthetic fixture spot-delta convention with synthetic linear IV interpolation"
            ),
        ),
    )

    volatility_inputs = (
        LegVolatilityInput(call, 0.198),
        LegVolatilityInput(put, 0.202),
    )
    pricing_methodology = (
        "synthetic fixture supplied valuations; illustrative model assumptions "
        "for rates, dividends, proportional IV shocks, and interpolation; no pricing performed"
    )
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
            statement=(
                "Synthetic reference ATM IV is at the 28th historical percentile "
                "and 2.50 percentage points below its historical median. This is "
                "only an investigation signal and is not proof that options are cheap."
            ),
            source="synthetic fixture volatility-environment data",
            methodology=(
                "synthetic fixture percentile and median comparison using 252 "
                "end-of-day observations"
            ),
        ),
        ClassifiedEvidence(
            evidence_id="SYNTHETIC-CALC-WEAKEN-IV-GAP",
            kind=EvidenceKind.CALCULATED_METRIC,
            impact=EvidenceImpact.WEAKENS,
            statement=(
                "Synthetic reference ATM IV exceeds matched-horizon realized "
                "volatility by 2.50 percentage points."
            ),
            source="synthetic fixture volatility-environment data",
            methodology=(
                "synthetic fixture matched 30-day annualized implied-versus-realized comparison"
            ),
        ),
        ClassifiedEvidence(
            evidence_id="SYNTHETIC-CALC-WEAKEN",
            kind=EvidenceKind.CALCULATED_METRIC,
            impact=EvidenceImpact.WEAKENS,
            statement="Synthetic repeated entry costs would consume 7.45% of the assumed portfolio across three attempts.",
            source="synthetic fixture structure-cost inputs",
            methodology="synthetic fixture total entry cost multiplied by three attempts",
        ),
        ClassifiedEvidence(
            evidence_id="SYNTHETIC-ASSUMPTION",
            kind=EvidenceKind.ASSUMPTION,
            impact=EvidenceImpact.NEUTRAL,
            statement="The expected holding period is assumed to be 14 calendar days.",
            source="synthetic fixture research assumption",
            methodology="synthetic fixture declared holding-horizon assumption",
        ),
        ClassifiedEvidence(
            evidence_id="SYNTHETIC-AI-INTERPRETATION",
            kind=EvidenceKind.AI_INTERPRETATION,
            impact=EvidenceImpact.NEUTRAL,
            statement="The synthetic evidence is mixed and warrants human review rather than a conclusion.",
            source="synthetic fixture interpretation",
            methodology="synthetic fixture deterministic narrative supplied by the example",
        ),
    )

    return CandidateResearchRecord(
        candidate_id="SYNTHETIC-SPY-STRADDLE-001",
        state=CandidateState.WATCH,
        state_rationale=(
            "WATCH is supplied only to exercise the report model and is not a screening conclusion."
        ),
        as_of_date=as_of_date,
        hypothesis=(
            "A synthetic SPY long straddle may merit further investigation if its "
            "declared convex payoff paths appear favorable relative to total-position costs."
        ),
        structure=structure,
        volatility_environment=volatility_environment,
        tail_pricing_slices=tail_pricing_slices,
        costs=costs,
        liquidity=liquidity,
        scenario_results=scenario_results,
        evidence=evidence,
        falsification_conditions=(
            "Volatility-environment support fails if real data show that structure-relevant ATM IV is not below its own historical median under the declared methodology.",
            "The convexity-versus-cost hypothesis fails if reproducible valuation using real quotes shows that reasonable two-sided move scenarios do not overcome entry cost, time decay, and estimated exit cost over the expected holding horizon.",
        ),
        missing_data=(
            "No current or historical market data has been supplied.",
            "No independently validated pricing output has been supplied.",
        ),
        false_positive_reasons=(
            "Invented values may accidentally resemble a favorable historical configuration.",
            "The simplified proportional IV shocks do not model skew or surface changes.",
        ),
        ai_interpretation=(
            "Interpretation only: this synthetic fixture demonstrates report organization "
            "and does not establish that any real option structure is attractive."
        ),
        human_review_questions=(
            "Are the synthetic cost fields internally understandable?",
            "Does each scenario disclose enough methodology for audit?",
            "Which real-data controls are required before this format is used for research?",
        ),
    )


if __name__ == "__main__":
    print(render_candidate_markdown(build_synthetic_candidate()), end="")
