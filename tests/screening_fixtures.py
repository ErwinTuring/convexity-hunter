"""Purpose-built deterministic fixtures for screening-policy tests."""

import datetime
from typing import Dict, Iterable, Mapping, Optional, Tuple

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
)
from convexity_hunter.scanner import ScreeningPolicy


AS_OF_DATE = datetime.date(2030, 1, 2)
EXPIRATION = datetime.date(2030, 3, 15)
UNDERLYING = "XYZ"
STRIKE = 100.0
BASE_UNDERLYING_PRICE = 100.0
EXPECTED_HOLDING_DAYS = 10


def build_test_policy(label: str, **overrides: object) -> ScreeningPolicy:
    """Build a deterministic custom-identity policy for one test rule set."""

    if not isinstance(label, str) or not label.strip():
        raise ValueError("label must be a non-empty string")
    normalized_label = label.strip().lower().replace("_", "-").replace(" ", "-")
    values = {
        "policy_id": f"synthetic-screening-test-{normalized_label}",
        "policy_version": "test-1",
    }
    values.update(overrides)
    return ScreeningPolicy(**values)  # type: ignore[arg-type]


def make_structure(
    structure_type: str = "long_call",
    assumed_portfolio_value: float = 100_000.0,
) -> OptionStructure:
    """Build one supported synthetic long-option structure."""

    if structure_type not in {"long_call", "long_put", "long_straddle"}:
        raise ValueError("structure_type is not supported by the fixture")
    option_types = {
        "long_call": ("call",),
        "long_put": ("put",),
        "long_straddle": ("call", "put"),
    }[structure_type]
    return OptionStructure(
        legs=tuple(
            OptionLeg(UNDERLYING, option_type, STRIKE, EXPIRATION)
            for option_type in option_types
        ),
        assumed_portfolio_value=assumed_portfolio_value,
        expected_holding_days=EXPECTED_HOLDING_DAYS,
    )


def make_costs(
    structure: OptionStructure,
    overrides: Optional[Mapping[str, object]] = None,
) -> StructureCosts:
    values = {
        "structure": structure,
        "as_of_date": AS_OF_DATE,
        "quoted_mid_premium": 2_000.0,
        "estimated_spread_cost": 100.0,
        "commissions_and_fees": 2.0,
        "theta_per_day": -20.0,
        "gamma": 0.50,
        "underlying_price": BASE_UNDERLYING_PRICE,
        "greeks_methodology": "synthetic total-position Greeks; daily theta",
        "repeated_bet_count": 3,
    }
    if overrides:
        values.update(overrides)
    return StructureCosts(**values)  # type: ignore[arg-type]


def make_liquidity(
    structure: OptionStructure,
    quoted_mid_premium: float = 2_000.0,
    spread_percentage: float = 0.04,
    overrides: Optional[Mapping[str, object]] = None,
) -> StructureLiquidity:
    half_spread = quoted_mid_premium * spread_percentage / 2
    values = {
        "structure": structure,
        "as_of_date": AS_OF_DATE,
        "quoted_bid_value": quoted_mid_premium - half_spread,
        "quoted_ask_value": quoted_mid_premium + half_spread,
        "minimum_leg_open_interest": 500,
        "minimum_leg_daily_volume": 100,
        "quote_methodology": "synthetic total-position midpoint and spread",
    }
    if overrides:
        values.update(overrides)
    return StructureLiquidity(**values)  # type: ignore[arg-type]


def make_environment(
    overrides: Optional[Mapping[str, object]] = None,
) -> VolatilityEnvironment:
    values = {
        "underlying": UNDERLYING,
        "as_of_date": AS_OF_DATE,
        "reference_tenor_days": 30,
        "iv_percentile": 0.30,
        "iv_history_lookback_observations": 252,
        "historical_median_atm_iv": 0.22,
        "matched_realized_volatility": 0.21,
        "matched_realized_window_days": 30,
        "term_structure": (
            TermVolatilityPoint(30, 0.20),
            TermVolatilityPoint(60, 0.21),
        ),
    }
    if overrides:
        values.update(overrides)
    return VolatilityEnvironment(**values)  # type: ignore[arg-type]


def make_tail_slice(
    overrides: Optional[Mapping[str, object]] = None,
) -> TailPricingSlice:
    values = {
        "underlying": UNDERLYING,
        "as_of_date": AS_OF_DATE,
        "expiration": EXPIRATION,
        "atm_iv": 0.20,
        "put_25_delta_iv": 0.22,
        "call_25_delta_iv": 0.21,
        "put_10_delta_iv": 0.25,
        "call_10_delta_iv": 0.23,
        "skew_percentile": 0.90,
        "skew_history_lookback_observations": 252,
        "delta_methodology": "synthetic spot-delta interpolation",
    }
    if overrides:
        values.update(overrides)
    return TailPricingSlice(**values)  # type: ignore[arg-type]


def make_scenario_result(
    structure: OptionStructure,
    entry_cost_basis: float,
    underlying_move: float,
    iv_change: float,
    pnl_after_costs: float,
    valuation_time: str = "holding_horizon",
) -> ScenarioResult:
    scenario = Scenario(underlying_move, iv_change, valuation_time)
    if scenario.valuation_time == "holding_horizon":
        valuation_date = AS_OF_DATE + datetime.timedelta(
            days=structure.expected_holding_days
        )
    elif scenario.valuation_time == "immediate":
        valuation_date = AS_OF_DATE
    elif scenario.valuation_time == "expiration":
        valuation_date = EXPIRATION
    else:
        valuation_date = AS_OF_DATE + datetime.timedelta(days=scenario.days_forward)
    exit_cost = 10.0
    position_value = entry_cost_basis + pnl_after_costs + exit_cost
    if position_value < 0:
        raise ValueError("fixture P&L is below the long-only loss bound")
    return ScenarioResult(
        structure=structure,
        as_of_date=AS_OF_DATE,
        scenario=scenario,
        valuation_date=valuation_date,
        base_underlying_price=BASE_UNDERLYING_PRICE,
        leg_volatility_inputs=tuple(
            LegVolatilityInput(leg, 0.20) for leg in structure.legs
        ),
        estimated_position_value=position_value,
        entry_cost_basis=entry_cost_basis,
        estimated_exit_cost=exit_cost,
        pricing_methodology="synthetic supplied valuation; no option pricing",
    )


def _default_scenario_specs(structure_type: str) -> Dict[str, Tuple[float, float, float]]:
    targets = {
        "long_call": {"target": (0.10, 0.0, 500.0)},
        "long_put": {"target": (-0.10, 0.0, 500.0)},
        "long_straddle": {
            "downside_target": (-0.10, 0.0, 500.0),
            "upside_target": (0.10, 0.0, 500.0),
        },
    }[structure_type]
    return dict(targets, crush=(0.0, -0.20, -500.0))


def build_screening_candidate(
    structure_type: str = "long_call",
    supplied_state: CandidateState = CandidateState.WATCH,
    state_rationale: str = "Supplied fixture state is independent of screening.",
    assumed_portfolio_value: float = 100_000.0,
    cost_overrides: Optional[Mapping[str, object]] = None,
    liquidity_overrides: Optional[Mapping[str, object]] = None,
    spread_percentage: float = 0.04,
    environment_overrides: Optional[Mapping[str, object]] = None,
    tail_overrides: Optional[Mapping[str, object]] = None,
    omit: Iterable[str] = (),
    scenario_pnl_overrides: Optional[Mapping[str, float]] = None,
    scenario_value_overrides: Optional[
        Mapping[str, Tuple[float, float, float, str]]
    ] = None,
    extra_scenarios: Iterable[Tuple[float, float, float, str]] = (),
    missing_data: Tuple[str, ...] = (),
    evidence: Optional[Tuple[ClassifiedEvidence, ...]] = None,
) -> CandidateResearchRecord:
    """Build a flexible complete or intentionally incomplete screening record.

    ``omit`` accepts ``costs``, ``liquidity``, ``volatility``, ``tail``,
    ``target``, ``downside_target``, ``upside_target``, or ``crush``.
    Scenario value overrides map a scenario label to
    ``(underlying_move, iv_change, pnl_after_costs, valuation_time)``.
    """

    omitted = set(omit)
    structure = make_structure(structure_type, assumed_portfolio_value)
    costs = make_costs(structure, cost_overrides)
    quoted_mid = costs.quoted_mid_premium
    liquidity = make_liquidity(
        structure, quoted_mid, spread_percentage, liquidity_overrides
    )
    environment = make_environment(environment_overrides)
    tail_slice = make_tail_slice(tail_overrides)

    specs = _default_scenario_specs(structure_type)
    if scenario_pnl_overrides:
        for label, pnl in scenario_pnl_overrides.items():
            move, iv_change, _ = specs[label]
            specs[label] = (move, iv_change, pnl)

    scenario_results = []
    for label, (move, iv_change, pnl) in specs.items():
        if label in omitted or (label == "target" and "target" in omitted):
            continue
        valuation_time = "holding_horizon"
        if scenario_value_overrides and label in scenario_value_overrides:
            move, iv_change, pnl, valuation_time = scenario_value_overrides[label]
        scenario_results.append(
            make_scenario_result(
                structure,
                costs.total_entry_cost,
                move,
                iv_change,
                pnl,
                valuation_time,
            )
        )
    for move, iv_change, pnl, valuation_time in extra_scenarios:
        scenario_results.append(
            make_scenario_result(
                structure,
                costs.total_entry_cost,
                move,
                iv_change,
                pnl,
                valuation_time,
            )
        )

    if evidence is None:
        evidence = (
            ClassifiedEvidence(
                "neutral-assumption",
                EvidenceKind.ASSUMPTION,
                EvidenceImpact.NEUTRAL,
                "Synthetic neutral assumption for screening isolation.",
            ),
        )

    if supplied_state is CandidateState.DATA_INSUFFICIENT and not missing_data:
        missing_data = ("Supplied record discloses missing research context.",)

    return CandidateResearchRecord(
        candidate_id=f"SCREEN-{structure_type.upper()}",
        state=supplied_state,
        state_rationale=state_rationale,
        as_of_date=AS_OF_DATE,
        hypothesis="Synthetic structure may deserve further human investigation.",
        structure=structure,
        volatility_environment=None if "volatility" in omitted else environment,
        tail_pricing_slices=() if "tail" in omitted else (tail_slice,),
        costs=None if "costs" in omitted else costs,
        liquidity=None if "liquidity" in omitted else liquidity,
        scenario_results=tuple(scenario_results),
        evidence=evidence,
        falsification_conditions=("Structured market evidence changes.",),
        missing_data=missing_data,
        false_positive_reasons=("Synthetic economics may not generalize.",),
        human_review_questions=("Are the synthetic inputs internally valid?",),
    )
