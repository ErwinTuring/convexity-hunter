"""Contract tests for Milestone 3C.7a exact-structure liquidity."""

import base64
import copy
import dataclasses
import datetime
import decimal
import enum
import hashlib
import inspect
import json
import math
import pathlib
import subprocess
import sys
import unittest
import zlib
from contextlib import ExitStack, contextmanager
from dataclasses import FrozenInstanceError
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
import convexity_hunter.market_data as market_data
import convexity_hunter.market_data_transformations as transformations
from convexity_hunter.evidence import (
    OptionLeg,
    OptionStructure,
    Scenario,
    TailPricingSlice,
)
from convexity_hunter.market_data import (
    CalculationInputReference,
    CalculationLineage,
    CalculationQualityFlag,
    CorrectionSelection,
    CorrectionSelectionReasonCode,
    CorrectionSelectionStatus,
    DataOrigin,
    FreshnessAssessment,
    FreshnessContext,
    FreshnessReasonCode,
    FreshnessStatus,
    MarketDataHistoricalSeriesAssessment,
    MarketDataHistoricalSeriesFrequency,
    MarketDataHistoricalSeriesReasonCode,
    MarketDataHistoricalSeriesRequest,
    MarketDataBindingReference,
    MarketDataCategory,
    MarketDataFreshnessPolicy,
    MarketDataRelationshipAssessment,
    MarketDataRelationshipGroup,
    MarketDataRelationshipGroupKind,
    MarketDataRelationshipRequest,
    MarketDataRelationshipRole,
    MarketDataRelationshipSelection,
    MarketDataSelectionStatus,
    MarketPhase,
    NormalizationMetadata,
    NormalizationQualityFlag,
    OptionContractReference,
    OptionImpliedVolatilityObservation,
    OptionGreeksObservation,
    OptionQuoteObservation,
    OptionOpenInterestObservation,
    OptionVolumeObservation,
    RateCurvePointObservation,
    SelectedFreshMarketDataBinding,
    SourceQualityFlag,
    SourceReference,
    UnderlyingDailyBarObservation,
    UnderlyingQuoteObservation,
    assess_market_data_historical_series,
    assess_market_data_relationships,
    assess_market_data_snapshot_timing,
    select_market_data_relationship_assessment,
)
from convexity_hunter.market_data_transformations import (
    ExactRational,
    ExpirationPayoffThreshold,
    ExpirationPayoffThresholdEvidence,
    ExpirationPayoffThresholdSide,
    ExpirationPayoffThresholdStatus,
    ExpirationPayoffThresholdTransformationResult,
    HistoricalRealizedVolatility,
    HistoricalRealizedVolatilityTransformationResult,
    HistoricalReturnPriceBasis,
    StructureCostsTransformationResult,
    StructureLiquidityTransformationResult,
    ScenarioPricingCalculationResult,
    ScenarioValuationTransformationResult,
    ScenarioPricingLegCalculation,
    ScenarioPricingMethodology,
    NonExpirationScenarioPricingCalculation,
    TailPricingTransformationResult,
    VolatilityEnvironmentTransformationResult,
    transform_historical_realized_volatility,
    transform_expiration_payoff_thresholds,
    transform_structure_costs,
    transform_structure_liquidity,
    transform_tail_pricing,
    transform_scenario_valuation,
    transform_volatility_environment,
    TreasuryPricingRateInput,
    TreasuryPricingRateTransformationResult,
    transform_treasury_pricing_rate,
)
from convexity_hunter.evidence import StructureCosts
from convexity_hunter.report import StructureLiquidity
from tests.market_data_fixtures import (
    CALCULATED_AT,
    EXPIRATION,
    SESSION_DATE,
    build_freshness_policy,
    build_normalization_metadata,
    build_option_implied_volatility_observation,
    build_option_contract_key,
    build_source_reference,
    build_underlying_key,
)
from tests.test_market_data import (
    build_timed_record,
    build_timing_binding,
    build_historical_series_binding,
    build_relationship_binding,
    build_resolved_relationship_group,
)


def make_structure(option_types=("call",), quantity=1, multiplier=100):
    return OptionStructure(
        tuple(
            OptionLeg(
                "SPY",
                option_type,
                100.0,
                EXPIRATION,
                quantity,
                multiplier,
            )
            for option_type in option_types
        ),
        assumed_portfolio_value=100000.0,
        expected_holding_days=14,
    )


def make_selection(
    structure,
    *,
    bid=("1.25", "2.00"),
    ask=("1.50", "2.50"),
    volume=(40, 30),
    open_interest=(80, 70),
    contracts=None,
):
    groups = []
    all_bindings = []
    bindings_by_group = []
    for index, leg in enumerate(structure.legs):
        label = leg.option_type
        contract = (
            build_option_contract_key(
                option_type=leg.option_type,
                strike=decimal.Decimal(str(leg.strike)),
                contract_multiplier=leg.contract_multiplier,
                expiration=leg.expiration,
            )
            if contracts is None
            else contracts[index]
        )
        bindings = {
            MarketDataRelationshipRole.OPTION_QUOTE: (
                build_relationship_binding(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    f"liquidity-{label}-quote",
                    contract_key=contract,
                    bid_premium=decimal.Decimal(bid[index]),
                    ask_premium=decimal.Decimal(ask[index]),
                    session_date=SESSION_DATE,
                )
            ),
            MarketDataRelationshipRole.OPTION_VOLUME: (
                build_relationship_binding(
                    MarketDataRelationshipRole.OPTION_VOLUME,
                    f"liquidity-{label}-volume",
                    contract_key=contract,
                    cumulative_volume=volume[index],
                    is_session_complete=True,
                    session_date=SESSION_DATE,
                )
            ),
            MarketDataRelationshipRole.OPTION_OPEN_INTEREST: (
                build_relationship_binding(
                    MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                    f"liquidity-{label}-open-interest",
                    contract_key=contract,
                    open_interest=open_interest[index],
                    open_interest_session_date=SESSION_DATE,
                )
            ),
        }
        group, aligned = build_resolved_relationship_group(
            f"activity-{label}",
            MarketDataRelationshipGroupKind.OPTION_ACTIVITY_V0_1,
            bindings,
        )
        groups.append(group)
        all_bindings.extend(aligned)
        bindings_by_group.append(bindings)
    assessment = assess_market_data_relationships(
        MarketDataRelationshipRequest(tuple(groups)),
        assess_market_data_snapshot_timing(tuple(all_bindings)),
    )
    return (
        select_market_data_relationship_assessment((assessment,)),
        assessment,
        tuple(bindings_by_group),
    )


def transform(structure, selection):
    return transform_structure_liquidity(
        " calculation-3c7a ",
        structure,
        selection,
        CALCULATED_AT,
    )


def make_historical_assessment(
    prices=("100", "110", "99"),
    *,
    adjusted_prices=None,
    methodologies=None,
    dates=None,
    policy=None,
):
    selected_dates = (
        tuple(
            SESSION_DATE - datetime.timedelta(days=offset)
            for offset in range(len(prices) - 1, -1, -1)
        )
        if dates is None
        else dates
    )
    if adjusted_prices is None:
        adjusted_prices = (None,) * len(prices)
    if methodologies is None:
        methodologies = tuple(
            None if value is None else "total-return-v1"
            for value in adjusted_prices
        )
    bindings = []
    for index, (session_date, price, adjusted, methodology) in enumerate(
        zip(selected_dates, prices, adjusted_prices, methodologies)
    ):
        close = decimal.Decimal(price)
        bindings.append(build_historical_series_binding(
            f"hrv-{index}",
            session_date=session_date,
            policy=policy,
            open_price=close,
            high_price=close,
            low_price=close,
            close_price=close,
            adjusted_close_price=(
                None if adjusted is None else decimal.Decimal(adjusted)
            ),
            adjustment_methodology=methodology,
        ))
    request = MarketDataHistoricalSeriesRequest(
        build_underlying_key(),
        MarketDataHistoricalSeriesFrequency.DAILY,
        selected_dates,
    )
    return (
        assess_market_data_historical_series(request, tuple(bindings)),
        tuple(bindings),
    )


def transform_historical(
    assessment,
    basis=HistoricalReturnPriceBasis.RAW_CLOSE,
    annualization=252,
):
    return transform_historical_realized_volatility(
        " calculation-3c7c ",
        assessment,
        basis,
        annualization,
        CALCULATED_AT,
    )


def make_volatility_selection(
    session_date, candidates, label, iv_overrides=None
):
    underlying_key = build_underlying_key()
    underlying = build_relationship_binding(
        MarketDataRelationshipRole.UNDERLYING_QUOTE,
        f"{label}-underlying",
        underlying_key=underlying_key,
        session_date=session_date,
        bid_price=decimal.Decimal("99"),
        ask_price=decimal.Decimal("101"),
        last_price=decimal.Decimal("777"),
    )
    groups = []
    unique_bindings = [underlying]
    for index, candidate in enumerate(candidates):
        if len(candidate) == 4:
            expiration, strike, call_iv, put_iv = candidate
            contract_multiplier = 100
        else:
            (
                expiration,
                strike,
                call_iv,
                put_iv,
                contract_multiplier,
            ) = candidate
        for option_type, implied_volatility in (
            ("call", call_iv),
            ("put", put_iv),
        ):
            item_label = f"{label}-{index}-{option_type}"
            contract = build_option_contract_key(
                underlying_key=underlying_key,
                expiration=expiration,
                option_type=option_type,
                strike=decimal.Decimal(str(strike)),
                contract_multiplier=contract_multiplier,
            )
            quote = build_relationship_binding(
                MarketDataRelationshipRole.OPTION_QUOTE,
                f"{item_label}-quote",
                contract_key=contract,
                session_date=session_date,
            )
            iv_fields = (
                {}
                if iv_overrides is None
                else {
                    key: value for key, value in iv_overrides.items()
                    if key != "unit_convention"
                }
            )
            iv_record = build_timed_record(
                build_option_implied_volatility_observation,
                f"{item_label}-iv",
                contract_key=contract,
                session_date=session_date,
                implied_volatility=decimal.Decimal(str(implied_volatility)),
                **iv_fields,
            )
            iv_record = dataclasses.replace(
                iv_record,
                metadata=dataclasses.replace(
                    iv_record.metadata,
                    unit_convention=(
                        "annualized_decimal_ratio"
                        if iv_overrides is None
                        else iv_overrides.get(
                            "unit_convention",
                            "annualized_decimal_ratio",
                        )
                    ),
                ),
            )
            iv = build_timing_binding(iv_record)
            reference = build_relationship_binding(
                MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                f"{item_label}-reference",
                contract_key=contract,
                listing_date=None,
                last_trade_date=None,
            )
            specs = (
                (
                    "snapshot",
                    MarketDataRelationshipGroupKind
                    .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1,
                    {
                        MarketDataRelationshipRole.UNDERLYING_QUOTE: underlying,
                        MarketDataRelationshipRole.OPTION_QUOTE: quote,
                    },
                ),
                (
                    "analytics",
                    MarketDataRelationshipGroupKind
                    .OPTION_QUOTE_ANALYTICS_V0_1,
                    {
                        MarketDataRelationshipRole.OPTION_QUOTE: quote,
                        MarketDataRelationshipRole
                        .OPTION_IMPLIED_VOLATILITY: iv,
                    },
                ),
                (
                    "reference",
                    MarketDataRelationshipGroupKind
                    .OPTION_CONTRACT_REFERENCE_V0_1,
                    {
                        MarketDataRelationshipRole.OPTION_QUOTE: quote,
                        MarketDataRelationshipRole
                        .OPTION_IMPLIED_VOLATILITY: iv,
                        MarketDataRelationshipRole
                        .OPTION_CONTRACT_REFERENCE: reference,
                    },
                ),
            )
            for suffix, kind, bindings in specs:
                group, _aligned = build_resolved_relationship_group(
                    f"{item_label}-{suffix}", kind, bindings
                )
                groups.append(group)
            unique_bindings.extend((quote, iv, reference))
    assessment = assess_market_data_relationships(
        MarketDataRelationshipRequest(tuple(groups)),
        assess_market_data_snapshot_timing(tuple(unique_bindings)),
    )
    return select_market_data_relationship_assessment((assessment,))


def make_volatility_result(
    *,
    current_candidates=None,
    historical_values=("0.20", "0.30", "0.40"),
    reference_tenor=30,
    return_arguments=False,
):
    current_candidates = (
        (
            (
                SESSION_DATE + datetime.timedelta(days=30),
                "95",
                "0.31",
                "0.29",
            ),
            (
                SESSION_DATE + datetime.timedelta(days=30),
                "105",
                "0.35",
                "0.33",
            ),
            (
                SESSION_DATE + datetime.timedelta(days=60),
                "100",
                "0.41",
                "0.39",
            ),
        )
        if current_candidates is None
        else current_candidates
    )
    current = make_volatility_selection(
        SESSION_DATE, current_candidates, "ve-current"
    )
    historical_dates = tuple(
        SESSION_DATE - datetime.timedelta(
            days=(len(historical_values) - index) * 3
        )
        for index in range(len(historical_values))
    )
    historical = tuple(
        make_volatility_selection(
            session_date,
            ((
                session_date + datetime.timedelta(days=reference_tenor),
                "100",
                decimal.Decimal(value) - decimal.Decimal("0.01"),
                decimal.Decimal(value) + decimal.Decimal("0.01"),
            ),),
            f"ve-history-{index}",
        )
        for index, (session_date, value) in enumerate(
            zip(historical_dates, historical_values)
        )
    )
    realized_dates = (
        SESSION_DATE - datetime.timedelta(days=reference_tenor),
        SESSION_DATE - datetime.timedelta(days=reference_tenor // 2),
        SESSION_DATE,
    )
    assessment, _bindings = make_historical_assessment(
        prices=("100", "102", "101"),
        dates=realized_dates,
        policy=build_freshness_policy(
            maximum_historical_bar_session_date_gap_days=reference_tenor
        ),
    )
    realized = transform_historical(assessment)
    arguments = (
        " calculation-3c7d ",
        current,
        historical,
        historical_dates,
        realized,
        reference_tenor,
        True,
        CALCULATED_AT,
    )
    if return_arguments:
        return arguments
    return transform_volatility_environment(*arguments)


TAIL_DELTA_METHODOLOGY = {
    "signed_delta_convention": "call_positive_put_negative",
    "delta_basis": "spot",
    "premium_adjustment": "unadjusted",
    "model_provider_methodology": "Synthetic Black-Scholes provider delta",
    "target_selection_methodology": "nearest_observed_signed_delta",
    "interpolation_methodology": "none",
}
TAIL_EOD_METHODOLOGY = "Synthetic official regular-session EOD snapshot"


def make_tail_selection(
    session_date,
    candidates,
    label,
    market_phase=MarketPhase.REGULAR,
    analytics_overrides=None,
):
    underlying_key = build_underlying_key()
    underlying = build_relationship_binding(
        MarketDataRelationshipRole.UNDERLYING_QUOTE,
        f"{label}-underlying",
        underlying_key=underlying_key,
        session_date=session_date,
        bid_price=decimal.Decimal("99"),
        ask_price=decimal.Decimal("101"),
        last_price=decimal.Decimal("777"),
        market_phase=market_phase,
    )
    groups = []
    unique_bindings = [underlying]
    for stem, expiration, option_type, strike, iv_value, delta in candidates:
        contract = build_option_contract_key(
            underlying_key=underlying_key,
            expiration=expiration,
            option_type=option_type,
            strike=decimal.Decimal(str(strike)),
        )
        quote = build_relationship_binding(
            MarketDataRelationshipRole.OPTION_QUOTE,
            f"{stem}-quote",
            contract_key=contract,
            session_date=session_date,
            market_phase=market_phase,
        )
        iv_record = build_timed_record(
            build_option_implied_volatility_observation,
            f"{stem}-iv",
            contract_key=contract,
            session_date=session_date,
            implied_volatility=decimal.Decimal(str(iv_value)),
            **({} if analytics_overrides is None else analytics_overrides),
        )
        iv_record = dataclasses.replace(
            iv_record,
            metadata=dataclasses.replace(
                iv_record.metadata,
                unit_convention="annualized_decimal_ratio",
            ),
        )
        iv = build_timing_binding(iv_record)
        greeks = build_relationship_binding(
            MarketDataRelationshipRole.OPTION_GREEKS,
            f"{stem}-greeks",
            contract_key=contract,
            session_date=session_date,
            delta=decimal.Decimal(str(delta)),
            gamma=decimal.Decimal("0.01"),
            theta=None,
            vega=None,
            theta_day_basis=None,
            **({} if analytics_overrides is None else analytics_overrides),
        )
        reference = build_relationship_binding(
            MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
            f"{stem}-reference",
            contract_key=contract,
            listing_date=None,
            last_trade_date=None,
        )
        specs = (
            (
                "snapshot",
                MarketDataRelationshipGroupKind
                .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1,
                {
                    MarketDataRelationshipRole.UNDERLYING_QUOTE: underlying,
                    MarketDataRelationshipRole.OPTION_QUOTE: quote,
                },
            ),
            (
                "analytics",
                MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
                {
                    MarketDataRelationshipRole.OPTION_QUOTE: quote,
                    MarketDataRelationshipRole
                    .OPTION_IMPLIED_VOLATILITY: iv,
                    MarketDataRelationshipRole.OPTION_GREEKS: greeks,
                },
            ),
            (
                "reference",
                MarketDataRelationshipGroupKind
                .OPTION_CONTRACT_REFERENCE_V0_1,
                {
                    MarketDataRelationshipRole.OPTION_QUOTE: quote,
                    MarketDataRelationshipRole
                    .OPTION_IMPLIED_VOLATILITY: iv,
                    MarketDataRelationshipRole.OPTION_GREEKS: greeks,
                    MarketDataRelationshipRole
                    .OPTION_CONTRACT_REFERENCE: reference,
                },
            ),
        )
        for suffix, kind, bindings in specs:
            group, _aligned = build_resolved_relationship_group(
                f"{stem}-{suffix}", kind, bindings
            )
            groups.append(group)
        unique_bindings.extend((quote, iv, greeks, reference))
    assessment = assess_market_data_relationships(
        MarketDataRelationshipRequest(tuple(groups)),
        assess_market_data_snapshot_timing(tuple(unique_bindings)),
    )
    return select_market_data_relationship_assessment((assessment,))


def _tail_candidates(
    session_date,
    tenor,
    label,
    atm,
    put_25,
    call_25,
    put_10,
    call_10,
    atm_stems=None,
):
    expiration = session_date + datetime.timedelta(days=tenor)
    call_atm_stem, put_atm_stem = (
        (
            f"{label}-atm-call",
            f"{label}-atm-put",
        )
        if atm_stems is None
        else atm_stems
    )
    call_atm, put_atm = (
        atm if type(atm) is tuple else (atm, atm)
    )
    return (
        (call_atm_stem, expiration, "call", "100", call_atm, "0.50"),
        (put_atm_stem, expiration, "put", "100", put_atm, "-0.50"),
        (f"{label}-call25", expiration, "call", "105", call_25, "0.24"),
        (f"{label}-call10", expiration, "call", "110", call_10, "0.11"),
        (f"{label}-put25", expiration, "put", "95", put_25, "-0.24"),
        (f"{label}-put10", expiration, "put", "90", put_10, "-0.11"),
    )


def _tail_selection_fixture_parts(selection):
    validated = transformations._validate_tail_selection(selection)
    candidates = tuple(
        (
            item[0].metadata.record_id.removesuffix("-quote"),
            item[0].contract_key.expiration,
            item[0].contract_key.option_type,
            item[0].contract_key.strike,
            item[1].implied_volatility,
            item[2].delta,
        )
        for item in validated["candidates"]
    )
    label = validated[
        "underlying_quote"
    ].metadata.record_id.removesuffix("-underlying")
    return validated["session_date"], candidates, label


def make_tail_result(
    *,
    historical_skews=("0.04", "0.06", "0.08"),
    return_arguments=False,
):
    historical_atms = tuple(
        decimal.Decimal("0.20") + decimal.Decimal(index) / 100
        for index in range(len(historical_skews))
    )
    dependency = make_volatility_result(
        current_candidates=(
            (
                SESSION_DATE + datetime.timedelta(days=30),
                "100",
                "0.30",
                "0.30",
            ),
            (
                SESSION_DATE + datetime.timedelta(days=60),
                "100",
                "0.40",
                "0.40",
            ),
        ),
        historical_values=tuple(str(value) for value in historical_atms),
    )
    current_candidates = (
        _tail_candidates(
            SESSION_DATE,
            30,
            "tail-current-30",
            "0.30",
            "0.36",
            "0.28",
            "0.42",
            "0.26",
            ("ve-current-0-call", "ve-current-0-put"),
        )
        + _tail_candidates(
            SESSION_DATE,
            60,
            "tail-current-60",
            "0.40",
            "0.46",
            "0.38",
            "0.52",
            "0.36",
            ("ve-current-1-call", "ve-current-1-put"),
        )
    )
    current = make_tail_selection(
        SESSION_DATE, current_candidates, "ve-current"
    )
    historical_dates = tuple(
        SESSION_DATE - datetime.timedelta(
            days=(len(historical_skews) - index) * 3
        )
        for index in range(len(historical_skews))
    )
    historical = []
    for index, (session_date, atm, skew) in enumerate(
        zip(historical_dates, historical_atms, historical_skews)
    ):
        skew_value = decimal.Decimal(skew)
        for tenor in (30, 60):
            selected_atm = (
                atm if tenor == 30 else atm + decimal.Decimal("0.10")
            )
            candidates = _tail_candidates(
                session_date,
                tenor,
                f"tail-history-{index}-{tenor}",
                (
                    (selected_atm - decimal.Decimal("0.01"),
                     selected_atm + decimal.Decimal("0.01"))
                    if tenor == 30
                    else selected_atm
                ),
                selected_atm + skew_value,
                selected_atm - decimal.Decimal("0.02"),
                selected_atm + skew_value + decimal.Decimal("0.06"),
                selected_atm - decimal.Decimal("0.04"),
                (
                    (
                        f"ve-history-{index}-0-call",
                        f"ve-history-{index}-0-put",
                    )
                    if tenor == 30
                    else None
                ),
            )
            historical.append(make_tail_selection(
                session_date,
                candidates,
                (
                    f"ve-history-{index}"
                    if tenor == 30
                    else f"tail-history-{index}-{tenor}"
                ),
            ))
    arguments = (
        " calculation-3c7e ",
        current,
        tuple(reversed(historical)),
        historical_dates,
        dependency,
        True,
        True,
        TAIL_EOD_METHODOLOGY,
        dict(TAIL_DELTA_METHODOLOGY),
        CALCULATED_AT + datetime.timedelta(seconds=1),
    )
    if return_arguments:
        return arguments
    return transform_tail_pricing(*arguments)


def make_cost_selection(
    structure,
    *,
    bid=("1.00", "2.00"),
    ask=("1.40", "2.60"),
    gamma=("0.020", "0.030"),
    theta=("-0.100", "-0.150"),
    underlying_bid="99.00",
    underlying_ask="101.00",
    model_version="fixture-v1",
    contracts=None,
):
    exact_contracts = (
        tuple(
            build_option_contract_key(
                option_type=leg.option_type,
                strike=decimal.Decimal(str(leg.strike)),
                contract_multiplier=leg.contract_multiplier,
                expiration=leg.expiration,
            )
            for leg in structure.legs
        )
        if contracts is None
        else tuple(contracts)
    )
    underlying = build_relationship_binding(
        MarketDataRelationshipRole.UNDERLYING_QUOTE,
        "cost-underlying-quote",
        underlying_key=exact_contracts[0].underlying_key,
        bid_price=decimal.Decimal(underlying_bid),
        ask_price=decimal.Decimal(underlying_ask),
        session_date=SESSION_DATE,
    )
    groups = []
    unique_bindings = [underlying]
    bindings_by_leg = []
    for index, (leg, contract) in enumerate(zip(structure.legs, exact_contracts)):
        label = leg.option_type
        quote = build_relationship_binding(
            MarketDataRelationshipRole.OPTION_QUOTE,
            f"cost-{label}-quote",
            contract_key=contract,
            bid_premium=decimal.Decimal(bid[index]),
            ask_premium=decimal.Decimal(ask[index]),
            session_date=SESSION_DATE,
        )
        greeks = build_relationship_binding(
            MarketDataRelationshipRole.OPTION_GREEKS,
            f"cost-{label}-greeks",
            contract_key=contract,
            gamma=decimal.Decimal(gamma[index]),
            theta=decimal.Decimal(theta[index]),
            theta_day_basis="Provider calendar-day convention",
            model_name="Synthetic Black-Scholes",
            model_version=model_version,
            rate_input_description="Synthetic USD curve input",
            dividend_input_description="Synthetic dividend input",
            session_date=SESSION_DATE,
        )
        contract_reference = build_relationship_binding(
            MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
            f"cost-{label}-contract-reference",
            contract_key=contract,
            **(
                {}
                if leg.expiration == EXPIRATION
                else {"last_trade_date": leg.expiration}
            ),
        )
        group_specs = (
            (
                f"cost-{label}-snapshot",
                MarketDataRelationshipGroupKind
                .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1,
                {
                    MarketDataRelationshipRole.UNDERLYING_QUOTE: underlying,
                    MarketDataRelationshipRole.OPTION_QUOTE: quote,
                },
            ),
            (
                f"cost-{label}-analytics",
                MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
                {
                    MarketDataRelationshipRole.OPTION_QUOTE: quote,
                    MarketDataRelationshipRole.OPTION_GREEKS: greeks,
                },
            ),
            (
                f"cost-{label}-reference",
                MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1,
                {
                    MarketDataRelationshipRole.OPTION_QUOTE: quote,
                    MarketDataRelationshipRole.OPTION_GREEKS: greeks,
                    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE: (
                        contract_reference
                    ),
                },
            ),
        )
        for group_id, group_kind, group_bindings in group_specs:
            group, _aligned = build_resolved_relationship_group(
                group_id, group_kind, group_bindings
            )
            groups.append(group)
        unique_bindings.extend((quote, greeks, contract_reference))
        bindings_by_leg.append({
            MarketDataRelationshipRole.OPTION_QUOTE: quote,
            MarketDataRelationshipRole.OPTION_GREEKS: greeks,
            MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE: (
                contract_reference
            ),
        })
    assessment = assess_market_data_relationships(
        MarketDataRelationshipRequest(tuple(groups)),
        assess_market_data_snapshot_timing(tuple(unique_bindings)),
    )
    return (
        select_market_data_relationship_assessment((assessment,)),
        assessment,
        underlying,
        tuple(bindings_by_leg),
    )


def transform_costs(
    structure,
    selection,
    commissions_and_fees=decimal.Decimal("0"),
    repeated_bet_count=1,
    calculation_id=" calculation-3c7b ",
    calculated_at=CALCULATED_AT,
):
    return transform_structure_costs(
        calculation_id,
        structure,
        selection,
        commissions_and_fees,
        repeated_bet_count,
        calculated_at,
    )


def mutate_cost_parameters(result, mutate):
    parameters = copy.deepcopy(
        transformations._decode_cost_parameters(
            result.lineage.parameters_json
        )
    )
    mutate(parameters)
    return dataclasses.replace(
        result.lineage,
        parameters_json=market_data.canonicalize_lineage_parameters(
            parameters
        ),
    )


def decimal_context_state():
    context = decimal.getcontext()
    return (
        context.prec,
        context.rounding,
        tuple(context.traps.items()),
        tuple(context.flags.items()),
        context.Emin,
        context.Emax,
        context.capitals,
        context.clamp,
    )


@contextmanager
def force_selected(assessment):
    with mock.patch.object(
        MarketDataRelationshipSelection,
        "status",
        new=property(lambda _self: MarketDataSelectionStatus.SELECTED),
    ), mock.patch.object(
        MarketDataRelationshipSelection,
        "selected_candidate",
        new=property(lambda _self: assessment),
    ):
        yield


@contextmanager
def changed(target, name, value):
    original = getattr(target, name)
    object.__setattr__(target, name, value)
    try:
        yield
    finally:
        object.__setattr__(target, name, original)


@contextmanager
def changed_with_semantic_proof(
    assessment,
    binding,
    target,
    name,
    value,
):
    original_value = getattr(target, name)
    original_key = binding.correction_selection.semantic_observation_key
    matching_references = tuple(
        member.reference
        for group in assessment.request.groups
        for member in group.members
        if member.reference.selected_record_id
        == binding.selected_record.metadata.record_id
    )
    object.__setattr__(target, name, value)
    updated_key = market_data.semantic_observation_key(binding.selected_record)
    object.__setattr__(
        binding.correction_selection,
        "semantic_observation_key",
        updated_key,
    )
    for reference in matching_references:
        object.__setattr__(reference, "semantic_observation_key", updated_key)
    try:
        yield
    finally:
        object.__setattr__(target, name, original_value)
        object.__setattr__(
            binding.correction_selection,
            "semantic_observation_key",
            original_key,
        )
        for reference in matching_references:
            object.__setattr__(reference, "semantic_observation_key", original_key)


class PublicSurfaceTests(unittest.TestCase):
    def test_exact_surface_signature_fields_and_frozen_result(self):
        self.assertEqual(
            transformations.__all__,
            (
                "StructureLiquidityTransformationResult",
                "transform_structure_liquidity",
                "StructureCostsTransformationResult",
                "transform_structure_costs",
                "HistoricalReturnPriceBasis",
                "HistoricalRealizedVolatility",
                "HistoricalRealizedVolatilityTransformationResult",
                "transform_historical_realized_volatility",
                "VolatilityEnvironmentTransformationResult",
                "transform_volatility_environment",
                "TailPricingTransformationResult",
                "transform_tail_pricing",
                "ScenarioPricingMethodology",
                "ScenarioPricingLegCalculation",
                "NonExpirationScenarioPricingCalculation",
                "ScenarioPricingCalculationResult",
                "ScenarioValuationTransformationResult",
                "transform_scenario_valuation",
                "ExactRational",
                "ExpirationPayoffThresholdSide",
                "ExpirationPayoffThresholdStatus",
                "ExpirationPayoffThreshold",
                "ExpirationPayoffThresholdEvidence",
                "ExpirationPayoffThresholdTransformationResult",
                "transform_expiration_payoff_thresholds",
                "TreasuryPricingRateInput",
                "TreasuryPricingRateTransformationResult",
                "transform_treasury_pricing_rate",
            ),
        )
        self.assertEqual(len(market_data.__all__), 64)
        self.assertFalse(
            hasattr(convexity_hunter, "transform_structure_liquidity")
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                StructureLiquidityTransformationResult
            )),
            ("record", "lineage"),
        )
        signature = inspect.signature(transform_structure_liquidity)
        self.assertEqual(
            tuple(signature.parameters),
            (
                "calculation_id",
                "structure",
                "relationship_selection",
                "calculated_at",
            ),
        )
        self.assertTrue(all(
            parameter.annotation is object
            for parameter in signature.parameters.values()
        ))
        self.assertIs(
            signature.return_annotation,
            StructureLiquidityTransformationResult,
        )
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        result = transform(structure, selection)
        with self.assertRaises(FrozenInstanceError):
            result.record = result.record

    def test_direct_result_construction_is_exact_type_structural_only(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        result = transform(structure, selection)
        self.assertIs(
            StructureLiquidityTransformationResult(
                result.record, result.lineage
            ).record,
            result.record,
        )

        class LiquiditySubclass(StructureLiquidity):
            pass

        class LineageSubclass(CalculationLineage):
            pass

        with self.assertRaises(TypeError):
            StructureLiquidityTransformationResult(object(), result.lineage)
        with self.assertRaises(TypeError):
            StructureLiquidityTransformationResult(result.record, object())
        liquidity_subclass = LiquiditySubclass(
            result.record.structure,
            result.record.as_of_date,
            result.record.quoted_bid_value,
            result.record.quoted_ask_value,
            result.record.minimum_leg_open_interest,
            result.record.minimum_leg_daily_volume,
            result.record.quote_methodology,
        )
        lineage_subclass = LineageSubclass(
            result.lineage.calculation_id,
            result.lineage.calculation_type,
            result.lineage.methodology_id,
            result.lineage.methodology_version,
            result.lineage.calculated_at,
            result.lineage.inputs,
            result.lineage.parameters_json,
            result.lineage.quality_flags,
        )
        with self.assertRaises(TypeError):
            StructureLiquidityTransformationResult(
                liquidity_subclass, result.lineage
            )
        with self.assertRaises(TypeError):
            StructureLiquidityTransformationResult(
                result.record, lineage_subclass
            )


class SuccessfulCalculationTests(unittest.TestCase):
    def test_one_leg_call_and_put_literal_values_zeros_and_identity(self):
        for option_type in ("call", "put"):
            with self.subTest(option_type=option_type):
                structure = make_structure((option_type,), quantity=2)
                selection, _, _ = make_selection(
                    structure,
                    bid=("0", "2"),
                    ask=("1.50", "2"),
                    volume=(0, 30),
                    open_interest=(0, 70),
                )
                result = transform(structure, selection)
                self.assertIs(result.record.structure, structure)
                self.assertEqual(result.record.as_of_date, SESSION_DATE)
                self.assertEqual(result.record.quoted_bid_value, 0.0)
                self.assertEqual(result.record.quoted_ask_value, 300.0)
                self.assertEqual(result.record.minimum_leg_daily_volume, 0)
                self.assertEqual(result.record.minimum_leg_open_interest, 0)

    def test_two_leg_straddle_exact_sum_scaling_and_unscaled_minima(self):
        structure = make_structure(("put", "call"), quantity=3, multiplier=25)
        selection, _, _ = make_selection(structure)
        result = transform(structure, selection)
        self.assertEqual(result.record.quoted_bid_value, 243.75)
        self.assertEqual(result.record.quoted_ask_value, 300.0)
        self.assertEqual(result.record.minimum_leg_daily_volume, 30)
        self.assertEqual(result.record.minimum_leg_open_interest, 70)

    def test_group_and_leg_permutations_have_invariant_values_and_parameters(self):
        first = make_structure(("call", "put"))
        second = make_structure(("put", "call"))
        first_selection, _, _ = make_selection(first)
        second_selection, _, _ = make_selection(
            second,
            bid=("2.00", "1.25"),
            ask=("2.50", "1.50"),
            volume=(30, 40),
            open_interest=(70, 80),
        )
        first_result = transform(first, first_selection)
        second_result = transform(second, second_selection)
        self.assertEqual(
            (
                first_result.record.quoted_bid_value,
                first_result.record.quoted_ask_value,
                first_result.record.minimum_leg_daily_volume,
                first_result.record.minimum_leg_open_interest,
            ),
            (325.0, 400.0, 30, 70),
        )
        self.assertNotEqual(
            first_result.lineage.parameters_json,
            second_result.lineage.parameters_json,
        )
        first_parameters = transformations._decode_strict_tagged_parameters(
            first_result.lineage.parameters_json,
            transformations._LIQUIDITY_PARAMETER_KEYS,
            "test liquidity",
        )
        second_parameters = transformations._decode_strict_tagged_parameters(
            second_result.lineage.parameters_json,
            transformations._LIQUIDITY_PARAMETER_KEYS,
            "test liquidity",
        )
        self.assertEqual(
            tuple(
                item["option_type"]
                for item in first_parameters["structure_identity"]["legs"]
            ),
            ("call", "put"),
        )
        self.assertEqual(
            tuple(
                item["option_type"]
                for item in second_parameters["structure_identity"]["legs"]
            ),
            ("put", "call"),
        )
        self.assertEqual(
            tuple(item.record_id for item in first_result.lineage.inputs),
            tuple(sorted(item.record_id for item in first_result.lineage.inputs)),
        )


class BoundaryAndProofTests(unittest.TestCase):
    def test_top_level_exact_types_and_precedence(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)

        class StringSubclass(str):
            pass

        class StructureSubclass(OptionStructure):
            pass

        class SelectionSubclass(MarketDataRelationshipSelection):
            pass

        class DatetimeSubclass(datetime.datetime):
            pass

        invalid_calls = (
            ((object(), structure, selection, CALCULATED_AT), TypeError),
            ((StringSubclass("x"), structure, selection, CALCULATED_AT), TypeError),
            ((" ", structure, selection, CALCULATED_AT), ValueError),
            (("x", object(), selection, CALCULATED_AT), TypeError),
            (("x", StructureSubclass(structure.legs, 1.0, 1),
              selection, CALCULATED_AT), TypeError),
            (("x", structure, object(), CALCULATED_AT), TypeError),
            (("x", structure, SelectionSubclass(selection.candidates),
              CALCULATED_AT), TypeError),
            (("x", structure, selection, object()), TypeError),
            (("x", structure, selection,
              DatetimeSubclass(2030, 1, 2)), TypeError),
            (("x", structure, selection,
              datetime.datetime(2030, 1, 2)), ValueError),
        )
        for arguments, error in invalid_calls:
            with self.subTest(arguments=tuple(type(x).__name__ for x in arguments)):
                with self.assertRaises(error):
                    transform_structure_liquidity(*arguments)

    def test_every_nonselected_status_stops_before_candidate_access(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        for status in tuple(MarketDataSelectionStatus)[1:]:
            with self.subTest(status=status):
                with mock.patch.object(
                    MarketDataRelationshipSelection,
                    "status",
                    new=property(lambda _self, value=status: value),
                ), mock.patch.object(
                    MarketDataRelationshipSelection,
                    "selected_candidate",
                    new=property(lambda _self: (_ for _ in ()).throw(
                        AssertionError("selected candidate accessed")
                    )),
                ):
                    with self.assertRaises(ValueError):
                        transform(structure, selection)

    def test_missing_candidate_and_group_shape_failures(self):
        structure = make_structure()
        selection, assessment, _ = make_selection(structure)
        with mock.patch.object(
            MarketDataRelationshipSelection,
            "status",
            new=property(lambda _self: MarketDataSelectionStatus.SELECTED),
        ), mock.patch.object(
            MarketDataRelationshipSelection,
            "selected_candidate",
            new=property(lambda _self: None),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)

        original = assessment.request
        extra = MarketDataRelationshipRequest(
            original.groups + (
                dataclasses.replace(original.groups[0], group_id="extra"),
            )
        )
        object.__setattr__(assessment, "request", extra)
        try:
            with mock.patch.object(
                MarketDataRelationshipSelection,
                "status",
                new=property(lambda _self: MarketDataSelectionStatus.SELECTED),
            ), mock.patch.object(
                MarketDataRelationshipSelection,
                "selected_candidate",
                new=property(lambda _self: assessment),
            ):
                with self.assertRaises(ValueError):
                    transform(structure, selection)
        finally:
            object.__setattr__(assessment, "request", original)

    def test_wrong_group_kind_missing_role_and_unreferenced_binding(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        group = assessment.request.groups[0]
        original_kind = group.group_kind
        object.__setattr__(
            group,
            "group_kind",
            MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
        )
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(group, "group_kind", original_kind)

        original_members = group.members
        object.__setattr__(group, "members", original_members[:-1])
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(group, "members", original_members)

        timing = assessment.timing_assessment
        original_bindings = timing.bindings
        object.__setattr__(timing, "bindings", original_bindings + (
            bindings[0][MarketDataRelationshipRole.OPTION_QUOTE],
        ))
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(timing, "bindings", original_bindings)

    def test_proof_layer_functions_are_never_called(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        names = (
            "select_correction_candidate",
            "assess_market_data_freshness",
            "bind_selected_fresh_market_data",
            "assess_market_data_snapshot_timing",
            "assess_market_data_relationships",
            "select_market_data_relationship_assessment",
            "assess_market_data_historical_series",
        )
        patches = [
            mock.patch.object(
                market_data,
                name,
                side_effect=AssertionError(f"{name} called"),
            )
            for name in names
        ]
        for patch in patches:
            patch.start()
        try:
            self.assertEqual(transform(structure, selection).record.quoted_bid_value,
                             125.0)
        finally:
            for patch in reversed(patches):
                patch.stop()


class CorrespondenceSessionAndLineageTests(unittest.TestCase):
    def test_every_contract_identity_component_is_required(self):
        structure = make_structure()
        base = build_option_contract_key()
        alternatives = (
            dataclasses.replace(
                base,
                underlying_key=dataclasses.replace(
                    base.underlying_key, symbol="QQQ"
                ),
            ),
            dataclasses.replace(base, option_type="put"),
            dataclasses.replace(
                base, expiration=EXPIRATION + datetime.timedelta(days=1)
            ),
            dataclasses.replace(base, strike=decimal.Decimal("101")),
            dataclasses.replace(base, contract_multiplier=50),
        )
        for contract in alternatives:
            with self.subTest(contract=contract):
                selection, _, _ = make_selection(
                    structure, contracts=(contract,)
                )
                with self.assertRaises(ValueError):
                    transform(structure, selection)

    def test_duplicate_group_leg_mixed_session_and_incomplete_volume_rejected(self):
        structure = make_structure(("call", "put"))
        selection, assessment, bindings = make_selection(structure)
        second_records = tuple(
            bindings[1][role].selected_record
            for role in (
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_VOLUME,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
            )
        )
        original_contracts = tuple(record.contract_key for record in second_records)
        call_contract = bindings[0][
            MarketDataRelationshipRole.OPTION_QUOTE
        ].selected_record.contract_key
        for record in second_records:
            object.__setattr__(record, "contract_key", call_contract)
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            for record, contract in zip(second_records, original_contracts):
                object.__setattr__(record, "contract_key", contract)

        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        volume = bindings[0][MarketDataRelationshipRole.OPTION_VOLUME].selected_record
        original_date = volume.session_date
        object.__setattr__(
            volume, "session_date", SESSION_DATE + datetime.timedelta(days=1)
        )
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(volume, "session_date", original_date)
        object.__setattr__(volume, "is_session_complete", False)
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(volume, "is_session_complete", True)

    def test_duplicate_consumed_record_id_rejected(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE].selected_record
        volume_binding = bindings[0][MarketDataRelationshipRole.OPTION_VOLUME]
        volume = volume_binding.selected_record
        original = volume.metadata
        original_selected_id = volume_binding.correction_selection.selected_record_id
        group = assessment.request.groups[0]
        volume_member = next(
            member for member in group.members
            if member.role is MarketDataRelationshipRole.OPTION_VOLUME
        )
        original_reference_id = volume_member.reference.selected_record_id
        object.__setattr__(
            volume,
            "metadata",
            dataclasses.replace(
                original, record_id=quote.metadata.record_id
            ),
        )
        object.__setattr__(
            volume_binding.correction_selection,
            "selected_record_id",
            quote.metadata.record_id,
        )
        object.__setattr__(
            volume_member.reference,
            "selected_record_id",
            quote.metadata.record_id,
        )
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(volume, "metadata", original)
            object.__setattr__(
                volume_binding.correction_selection,
                "selected_record_id",
                original_selected_id,
            )
            object.__setattr__(
                volume_member.reference,
                "selected_record_id",
                original_reference_id,
            )

    def test_lineage_exact_fields_inputs_parameters_and_default_flags(self):
        structure = make_structure()
        selection, _, bindings = make_selection(structure)
        result = transform(structure, selection)
        lineage = result.lineage
        self.assertEqual(lineage.calculation_id, "calculation-3c7a")
        self.assertEqual(lineage.calculation_type, "structure_liquidity")
        self.assertEqual(lineage.methodology_id, "exact-structure-liquidity")
        self.assertEqual(lineage.methodology_version, "v0.2")
        self.assertEqual(lineage.calculated_at, CALCULATED_AT)
        self.assertEqual(
            lineage.quality_flags,
            (CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,),
        )
        expected_records = tuple(
            bindings[0][role].selected_record
            for role in (
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_VOLUME,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
            )
        )
        self.assertEqual(
            tuple(item.record_id for item in lineage.inputs),
            tuple(sorted(record.metadata.record_id for record in expected_records)),
        )
        for item in lineage.inputs:
            record = next(
                record for record in expected_records
                if record.metadata.record_id == item.record_id
            )
            self.assertEqual(item.normalized_at, record.metadata.normalized_at)
            self.assertEqual(
                item.source_ids,
                tuple(source.source_id
                      for source in record.metadata.source_references),
            )
        self.assertEqual(
            hashlib.sha256(lineage.parameters_json.encode()).hexdigest(),
            "e396a0d698bab8f9eede00c457527cb0e56c2749cc5796a107f0c7c2a83eb055",
        )

    def test_all_authorized_quality_flags_and_prohibited_flags(self):
        structure = make_structure()
        selection, _, bindings = make_selection(structure)
        records = tuple(
            bindings[0][role].selected_record
            for role in (
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_VOLUME,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
            )
        )
        originals = tuple(record.metadata for record in records)
        partial_source = dataclasses.replace(
            originals[2].source_references[0],
            quality_flags=(SourceQualityFlag.PARTIAL,),
        )
        composite_sources = (
            dataclasses.replace(
                originals[1].source_references[0], source_id="composite-a"
            ),
            dataclasses.replace(
                originals[1].source_references[0],
                source_id="composite-b",
                provider_record_id="composite-record-b",
                provider_request_id="composite-request-b",
                source_uri="synthetic://composite/b",
            ),
        )
        changed = (
            dataclasses.replace(
                originals[0],
                quality_flags=(NormalizationQualityFlag.INTERPOLATED,),
            ),
            build_normalization_metadata(
                composite_sources,
                record_id=originals[1].record_id,
                effective_observed_at=originals[1].effective_observed_at,
                normalized_at=originals[1].normalized_at,
                record_origin=DataOrigin.SYSTEM_COMPOSITE,
                quality_flags=(NormalizationQualityFlag.COMPOSITE_SOURCE,),
            ),
            dataclasses.replace(
                originals[2], source_references=(partial_source,)
            ),
        )
        for record, metadata in zip(records, changed):
            object.__setattr__(record, "metadata", metadata)
        try:
            flags = transform(structure, selection).lineage.quality_flags
            self.assertEqual(
                flags,
                (
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                    CalculationQualityFlag.INTERPOLATED,
                    CalculationQualityFlag.COMPOSITE_INPUT_USED,
                    CalculationQualityFlag.INCOMPLETE_INPUT_USED,
                ),
            )
            self.assertNotIn(CalculationQualityFlag.ANNUALIZED, flags)
            self.assertNotIn(CalculationQualityFlag.ADJUSTED_INPUT_USED, flags)
            self.assertNotIn(CalculationQualityFlag.ASSUMPTION_APPLIED, flags)
        finally:
            for record, metadata in zip(records, originals):
                object.__setattr__(record, "metadata", metadata)

    def test_calculated_at_chronology_is_enforced(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        with self.assertRaises(ValueError):
            transform_structure_liquidity(
                "calculation",
                structure,
                selection,
                datetime.datetime(2029, 1, 1, tzinfo=datetime.timezone.utc),
            )

    def test_calculation_id_collision_and_discarded_candidate_exclusion(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote_binding = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        selected = quote_binding.selected_record
        discarded = dataclasses.replace(
            selected,
            metadata=dataclasses.replace(
                selected.metadata, record_id="discarded-not-consumed"
            ),
        )
        object.__setattr__(
            quote_binding, "candidate_records", (discarded, selected)
        )
        object.__setattr__(
            quote_binding.correction_selection,
            "candidate_record_ids",
            tuple(sorted((
                discarded.metadata.record_id,
                selected.metadata.record_id,
            ))),
        )
        object.__setattr__(
            quote_binding.correction_selection,
            "reason_codes",
            (
                CorrectionSelectionReasonCode
                .DOMINATING_REVISION_VECTOR_SELECTED,
            ),
        )
        with force_selected(assessment):
            result = transform(structure, selection)
        self.assertNotIn(
            discarded.metadata.record_id,
            tuple(item.record_id for item in result.lineage.inputs),
        )
        with force_selected(assessment), self.assertRaises(ValueError):
            transform_structure_liquidity(
                selected.metadata.record_id,
                structure,
                selection,
                CALCULATED_AT,
            )

    def test_session_after_expiration_missing_value_and_float_overflow_rejected(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE].selected_record
        volume = bindings[0][MarketDataRelationshipRole.OPTION_VOLUME].selected_record
        original_quote_date = quote.session_date
        original_volume_date = volume.session_date
        after_expiration = EXPIRATION + datetime.timedelta(days=1)
        object.__setattr__(quote, "session_date", after_expiration)
        object.__setattr__(volume, "session_date", after_expiration)
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(quote, "session_date", original_quote_date)
            object.__setattr__(volume, "session_date", original_volume_date)

        original_volume = volume.cumulative_volume
        object.__setattr__(volume, "cumulative_volume", None)
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(volume, "cumulative_volume", original_volume)

        original_bid = quote.bid_premium
        original_ask = quote.ask_premium
        object.__setattr__(quote, "bid_premium", decimal.Decimal("1e10000"))
        object.__setattr__(quote, "ask_premium", decimal.Decimal("2e10000"))
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(quote, "bid_premium", original_bid)
            object.__setattr__(quote, "ask_premium", original_ask)

    def test_dominating_revision_reason_adds_correction_flag_in_enum_order(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        correction = bindings[0][
            MarketDataRelationshipRole.OPTION_QUOTE
        ].correction_selection
        binding = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        selected_record = binding.selected_record
        discarded_record = dataclasses.replace(
            selected_record,
            metadata=dataclasses.replace(
                selected_record.metadata,
                record_id="discarded-correction-candidate",
            ),
        )
        original_reasons = correction.reason_codes
        original_candidate_ids = correction.candidate_record_ids
        original_candidates = binding.candidate_records
        object.__setattr__(
            binding,
            "candidate_records",
            (discarded_record, selected_record),
        )
        object.__setattr__(
            correction,
            "candidate_record_ids",
            tuple(sorted((
                discarded_record.metadata.record_id,
                selected_record.metadata.record_id,
            ))),
        )
        object.__setattr__(
            correction,
            "reason_codes",
            (
                CorrectionSelectionReasonCode
                .DOMINATING_REVISION_VECTOR_SELECTED,
            ),
        )
        try:
            with force_selected(assessment):
                flags = transform(structure, selection).lineage.quality_flags
            self.assertEqual(
                flags,
                (
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                    CalculationQualityFlag.CORRECTION_SELECTED,
                ),
            )
        finally:
            object.__setattr__(correction, "reason_codes", original_reasons)
            object.__setattr__(
                correction, "candidate_record_ids", original_candidate_ids
            )
            object.__setattr__(
                binding, "candidate_records", original_candidates
            )


class CorrectedProofIntegrityTests(unittest.TestCase):
    def _one_leg(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        return structure, selection, assessment, bindings[0]

    def _assert_proof_rejected(self, mutate):
        structure, selection, assessment, bindings = self._one_leg()
        mutate(assessment, bindings)
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_match_structure_legs",
            side_effect=AssertionError("leg correspondence reached"),
        ):
            with self.assertRaises((TypeError, ValueError)):
                transform(structure, selection)

    def test_correction_terminal_and_candidate_universe_matrix(self):
        def correction(bindings):
            return bindings[
                MarketDataRelationshipRole.OPTION_QUOTE
            ].correction_selection

        mutations = {
            "ambiguous_status": lambda _a, b: object.__setattr__(
                correction(b), "status", CorrectionSelectionStatus.AMBIGUOUS
            ),
            "missing_selected_id": lambda _a, b: object.__setattr__(
                correction(b), "selected_record_id", None
            ),
            "incompatible_reason": lambda _a, b: object.__setattr__(
                correction(b),
                "reason_codes",
                (CorrectionSelectionReasonCode.MISSING_PROVIDER_RECORD_ID,),
            ),
            "multiple_reasons": lambda _a, b: object.__setattr__(
                correction(b),
                "reason_codes",
                (
                    CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
                    CorrectionSelectionReasonCode
                    .DOMINATING_REVISION_VECTOR_SELECTED,
                ),
            ),
            "candidate_id_tuple_mismatch": lambda _a, b: object.__setattr__(
                correction(b),
                "candidate_record_ids",
                ("foreign-candidate",),
            ),
            "selected_id_absent": lambda _a, b: (
                object.__setattr__(
                    correction(b),
                    "candidate_record_ids",
                    tuple(sorted((
                        correction(b).selected_record_id,
                        "absent-candidate",
                    ))),
                )
            ),
            "correction_semantic_key": lambda _a, b: object.__setattr__(
                correction(b), "semantic_observation_key", "forged-semantic"
            ),
            "correction_chronology": lambda _a, b: object.__setattr__(
                correction(b),
                "evaluated_at",
                b[
                    MarketDataRelationshipRole.OPTION_QUOTE
                ].freshness_context.evaluation_at
                + datetime.timedelta(microseconds=1),
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self._assert_proof_rejected(mutation)

    def test_candidate_count_duplicate_and_identity_matrix(self):
        def add_candidate(_assessment, bindings, duplicate_id=False):
            binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
            selected = binding.selected_record
            record_id = (
                selected.metadata.record_id
                if duplicate_id
                else "discarded-quote-candidate"
            )
            discarded = dataclasses.replace(
                selected,
                metadata=dataclasses.replace(
                    selected.metadata, record_id=record_id
                ),
            )
            object.__setattr__(
                binding, "candidate_records", (discarded, selected)
            )
            object.__setattr__(
                binding.correction_selection,
                "candidate_record_ids",
                tuple(sorted((
                    record_id, selected.metadata.record_id
                ))),
            )

        with self.subTest(name="only_candidate_with_multiple"):
            self._assert_proof_rejected(add_candidate)
        with self.subTest(name="duplicate_candidate_ids"):
            self._assert_proof_rejected(
                lambda a, b: add_candidate(a, b, duplicate_id=True)
            )
        with self.subTest(name="dominating_with_one"):
            self._assert_proof_rejected(
                lambda _a, b: object.__setattr__(
                    b[
                        MarketDataRelationshipRole.OPTION_QUOTE
                    ].correction_selection,
                    "reason_codes",
                    (
                        CorrectionSelectionReasonCode
                        .DOMINATING_REVISION_VECTOR_SELECTED,
                    ),
                )
            )

        structure, selection, assessment, bindings = self._one_leg()
        binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
        entries = transformations._resolve_selected_objects(
            assessment.request.groups,
            assessment.timing_assessment.bindings,
        )
        forged = dataclasses.replace(entries[0][3])
        forged_entries = ((entries[0][0], entries[0][1], binding, forged),) + entries[1:]
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_resolve_selected_objects",
            return_value=forged_entries,
        ), mock.patch.object(
            transformations,
            "_match_structure_legs",
            side_effect=AssertionError("leg correspondence reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)

    def test_freshness_terminal_correspondence_and_regime_matrix(self):
        def freshness(bindings):
            return bindings[
                MarketDataRelationshipRole.OPTION_QUOTE
            ].freshness_assessment

        mutations = {
            "stale": lambda _a, b: object.__setattr__(
                freshness(b), "status", FreshnessStatus.STALE
            ),
            "unknown": lambda _a, b: object.__setattr__(
                freshness(b), "status", FreshnessStatus.UNKNOWN
            ),
            "ineligible": lambda _a, b: object.__setattr__(
                freshness(b), "status", FreshnessStatus.INELIGIBLE
            ),
            "wrong_reason": lambda _a, b: object.__setattr__(
                freshness(b),
                "reason_codes",
                (FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,),
            ),
            "wrong_category": lambda _a, b: object.__setattr__(
                freshness(b), "category", MarketDataCategory.ACTIVITY
            ),
            "record_id": lambda _a, b: object.__setattr__(
                freshness(b), "record_id", "wrong-record"
            ),
            "policy_id": lambda _a, b: object.__setattr__(
                freshness(b), "policy_id", "wrong-policy"
            ),
            "policy_version": lambda _a, b: object.__setattr__(
                freshness(b), "policy_version", "wrong-version"
            ),
            "evaluated_at": lambda _a, b: object.__setattr__(
                freshness(b),
                "evaluated_at",
                freshness(b).evaluated_at + datetime.timedelta(microseconds=1),
            ),
            "policy_type": lambda _a, b: object.__setattr__(
                b[MarketDataRelationshipRole.OPTION_QUOTE],
                "freshness_policy",
                object(),
            ),
            "context_type": lambda _a, b: object.__setattr__(
                b[MarketDataRelationshipRole.OPTION_QUOTE],
                "freshness_context",
                object(),
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self._assert_proof_rejected(mutation)

        class FreshnessSubclass(FreshnessAssessment):
            pass

        def subclass_mutation(_assessment, bindings):
            binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
            source = binding.freshness_assessment
            subclass = FreshnessSubclass(
                *(getattr(source, field.name)
                  for field in dataclasses.fields(FreshnessAssessment))
            )
            object.__setattr__(binding, "freshness_assessment", subclass)

        self._assert_proof_rejected(subclass_mutation)

    def test_semantic_and_reference_integrity_matrix(self):
        def quote_parts(assessment, bindings):
            binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
            member = next(
                member
                for member in assessment.request.groups[0].members
                if member.role is MarketDataRelationshipRole.OPTION_QUOTE
            )
            return binding, member

        mutations = {
            "reference_semantic": lambda a, b: object.__setattr__(
                quote_parts(a, b)[1].reference,
                "semantic_observation_key",
                "forged-reference",
            ),
            "coordinated_semantic_forgery": lambda a, b: (
                object.__setattr__(
                    quote_parts(a, b)[0].correction_selection,
                    "semantic_observation_key",
                    "coordinated-forgery",
                ),
                object.__setattr__(
                    quote_parts(a, b)[1].reference,
                    "semantic_observation_key",
                    "coordinated-forgery",
                ),
            ),
            "reference_selected_id": lambda a, b: object.__setattr__(
                quote_parts(a, b)[1].reference,
                "selected_record_id",
                "outside-timing-assessment",
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self._assert_proof_rejected(mutation)

        def actual_record_semantic(_assessment, bindings):
            binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
            record = binding.selected_record
            object.__setattr__(
                record,
                "contract_key",
                dataclasses.replace(
                    record.contract_key, strike=decimal.Decimal("101")
                ),
            )

        self._assert_proof_rejected(actual_record_semantic)

        def candidate_semantic(_assessment, bindings):
            binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
            selected = binding.selected_record
            discarded = dataclasses.replace(
                selected,
                contract_key=dataclasses.replace(
                    selected.contract_key, strike=decimal.Decimal("101")
                ),
                metadata=dataclasses.replace(
                    selected.metadata, record_id="semantic-mismatch-candidate"
                ),
            )
            object.__setattr__(
                binding, "candidate_records", (discarded, selected)
            )
            object.__setattr__(
                binding.correction_selection,
                "candidate_record_ids",
                tuple(sorted((
                    discarded.metadata.record_id,
                    selected.metadata.record_id,
                ))),
            )
            object.__setattr__(
                binding.correction_selection,
                "reason_codes",
                (
                    CorrectionSelectionReasonCode
                    .DOMINATING_REVISION_VECTOR_SELECTED,
                ),
            )

        self._assert_proof_rejected(candidate_semantic)

    def test_exact_sidecar_types_are_structural_prerequisites(self):
        sidecars = (
            ("correction_selection", CorrectionSelection),
            ("freshness_assessment", FreshnessAssessment),
            ("freshness_policy", MarketDataFreshnessPolicy),
            ("freshness_context", FreshnessContext),
        )
        for field_name, field_type in sidecars:
            for raw in (False, True):
                with self.subTest(field_name=field_name, raw=raw):
                    structure, selection, assessment, bindings = (
                        self._one_leg()
                    )
                    binding = bindings[
                        MarketDataRelationshipRole.OPTION_QUOTE
                    ]
                    if raw:
                        forged = object()
                    else:
                        class SidecarSubclass(field_type):
                            pass

                        source = getattr(binding, field_name)
                        forged = SidecarSubclass(
                            *(getattr(source, field.name)
                              for field in dataclasses.fields(field_type))
                        )
                    object.__setattr__(binding, field_name, forged)
                    with force_selected(assessment), mock.patch.object(
                        transformations,
                        "_resolve_selected_objects",
                        side_effect=AssertionError(
                            "selected resolution reached"
                        ),
                    ):
                        with self.assertRaises(TypeError):
                            transform(structure, selection)

    def test_unreferenced_reused_and_duplicate_selected_bindings(self):
        def extra_binding(assessment, bindings):
            timing = assessment.timing_assessment
            object.__setattr__(
                timing,
                "bindings",
                timing.bindings
                + (bindings[MarketDataRelationshipRole.OPTION_QUOTE],),
            )

        self._assert_proof_rejected(extra_binding)

        structure = make_structure(("call", "put"))
        selection, assessment, groups = make_selection(structure)
        first_quote = groups[0][MarketDataRelationshipRole.OPTION_QUOTE]
        second_member = next(
            member
            for member in assessment.request.groups[1].members
            if member.role is MarketDataRelationshipRole.OPTION_QUOTE
        )
        object.__setattr__(
            second_member.reference,
            "selected_record_id",
            first_quote.correction_selection.selected_record_id,
        )
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_match_structure_legs",
            side_effect=AssertionError("leg correspondence reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)


class CorrectedGlobalPrecedenceTests(unittest.TestCase):
    def test_early_phase_failures_poison_every_immediate_successor(self):
        structure = make_structure()
        selection, assessment, _bindings = make_selection(structure)
        scenarios = (
            (
                (object(), structure, selection, CALCULATED_AT),
                "_validate_structure",
                TypeError,
            ),
            (
                ("id", object(), selection, CALCULATED_AT),
                "_validate_relationship_selection",
                TypeError,
            ),
            (
                ("id", structure, object(), CALCULATED_AT),
                "_normalize_calculated_at",
                TypeError,
            ),
            (
                (
                    "id",
                    structure,
                    selection,
                    datetime.datetime(2030, 1, 2),
                ),
                "_validate_selection_status",
                ValueError,
            ),
        )
        for arguments, later, error in scenarios:
            with self.subTest(later=later), mock.patch.object(
                transformations,
                later,
                side_effect=AssertionError(f"{later} reached"),
            ):
                with self.assertRaises(error):
                    transform_structure_liquidity(*arguments)

        with mock.patch.object(
            transformations,
            "_validate_selection_status",
            side_effect=ValueError("not selected"),
        ), mock.patch.object(
            transformations,
            "_resolve_selected_candidate",
            side_effect=AssertionError("candidate reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_resolve_selected_candidate",
            side_effect=ValueError("missing candidate"),
        ), mock.patch.object(
            transformations,
            "_validate_selected_shape",
            side_effect=AssertionError("shape reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_validate_selected_shape",
            side_effect=ValueError("shape"),
        ), mock.patch.object(
            transformations,
            "_resolve_selected_objects",
            side_effect=AssertionError("resolution reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_resolve_selected_objects",
            side_effect=ValueError("resolution"),
        ), mock.patch.object(
            transformations,
            "_validate_selected_record_types",
            side_effect=AssertionError("type pass reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)

    def test_structural_types_and_cardinality_precede_selected_object_access(self):
        mutations = []

        def add(name, callback, error):
            mutations.append((name, callback, error))

        add(
            "extra_group",
            lambda assessment: object.__setattr__(
                assessment.request,
                "groups",
                assessment.request.groups
                + (dataclasses.replace(
                    assessment.request.groups[0], group_id="extra"
                ),),
            ),
            ValueError,
        )
        add(
            "repeated_role",
            lambda assessment: object.__setattr__(
                assessment.request.groups[0].members[1],
                "role",
                MarketDataRelationshipRole.OPTION_QUOTE,
            ),
            ValueError,
        )
        add(
            "wrong_reference",
            lambda assessment: object.__setattr__(
                assessment.request.groups[0].members[0],
                "reference",
                object(),
            ),
            TypeError,
        )
        add(
            "wrong_binding",
            lambda assessment: object.__setattr__(
                assessment.timing_assessment,
                "bindings",
                (object(),)
                + assessment.timing_assessment.bindings[1:],
            ),
            TypeError,
        )
        add(
            "reference_subclass",
            lambda assessment: object.__setattr__(
                assessment.request.groups[0].members[0],
                "reference",
                type(
                    "ReferenceSubclass",
                    (MarketDataBindingReference,),
                    {},
                )(
                    assessment.request.groups[0]
                    .members[0].reference.semantic_observation_key,
                    assessment.request.groups[0]
                    .members[0].reference.selected_record_id,
                ),
            ),
            TypeError,
        )
        add(
            "binding_subclass",
            lambda assessment: object.__setattr__(
                assessment.timing_assessment,
                "bindings",
                (
                    type(
                        "BindingSubclass",
                        (SelectedFreshMarketDataBinding,),
                        {},
                    )(
                        assessment.timing_assessment.bindings[0]
                        .candidate_records,
                        assessment.timing_assessment.bindings[0]
                        .correction_selection,
                        assessment.timing_assessment.bindings[0]
                        .freshness_policy,
                        assessment.timing_assessment.bindings[0]
                        .freshness_context,
                        assessment.timing_assessment.bindings[0]
                        .freshness_assessment,
                    ),
                )
                + assessment.timing_assessment.bindings[1:],
            ),
            TypeError,
        )
        for name, mutation, error in mutations:
            with self.subTest(name=name):
                structure = make_structure()
                selection, assessment, _bindings = make_selection(structure)
                mutation(assessment)
                with force_selected(assessment), mock.patch.object(
                    transformations,
                    "_resolve_selected_objects",
                    side_effect=AssertionError("selected object accessed"),
                ):
                    with self.assertRaises(error):
                        transform(structure, selection)

    def test_same_binding_wrong_type_precedes_forged_semantic_and_freshness(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote_binding = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        volume_record = bindings[0][
            MarketDataRelationshipRole.OPTION_VOLUME
        ].selected_record
        wrong_record = dataclasses.replace(
            volume_record,
            metadata=dataclasses.replace(
                volume_record.metadata,
                record_id=quote_binding.correction_selection.selected_record_id,
            ),
        )
        object.__setattr__(quote_binding, "candidate_records", (wrong_record,))
        object.__setattr__(
            quote_binding.correction_selection,
            "semantic_observation_key",
            "forged-semantic",
        )
        object.__setattr__(
            quote_binding.freshness_assessment,
            "status",
            FreshnessStatus.STALE,
        )
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_validate_proof_integrity",
            side_effect=AssertionError("proof integrity reached"),
        ):
            with self.assertRaises(TypeError):
                transform(structure, selection)

    def test_cross_binding_integrity_poison_loses_to_later_wrong_type_permutations(self):
        for reversed_groups in (False, True):
            for reversed_bindings in (False, True):
                with self.subTest(
                    reversed_groups=reversed_groups,
                    reversed_bindings=reversed_bindings,
                ):
                    self._run_cross_binding_permutation(
                        reversed_groups, reversed_bindings
                    )

    def _run_cross_binding_permutation(
        self,
        reversed_groups,
        reversed_bindings,
    ):
        structure = make_structure(("call", "put"))
        selection, assessment, bindings = make_selection(structure)
        first = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        object.__setattr__(
            first.freshness_assessment,
            "status",
            FreshnessStatus.STALE,
        )
        later = bindings[1][
            MarketDataRelationshipRole.OPTION_OPEN_INTEREST
        ]
        wrong = dataclasses.replace(
            bindings[1][
                MarketDataRelationshipRole.OPTION_VOLUME
            ].selected_record,
            metadata=dataclasses.replace(
                bindings[1][
                    MarketDataRelationshipRole.OPTION_VOLUME
                ].selected_record.metadata,
                record_id=later.correction_selection.selected_record_id,
            ),
        )
        object.__setattr__(later, "candidate_records", (wrong,))
        if reversed_groups:
            object.__setattr__(
                assessment.request,
                "groups",
                tuple(reversed(assessment.request.groups)),
            )
        if reversed_bindings:
            object.__setattr__(
                assessment.timing_assessment,
                "bindings",
                tuple(reversed(assessment.timing_assessment.bindings)),
            )
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_validate_proof_integrity",
            side_effect=AssertionError("proof integrity reached"),
        ):
            with self.assertRaises(TypeError):
                transform(structure, selection)

    def test_selected_record_subclass_is_rejected_before_integrity(self):
        class QuoteSubclass(OptionQuoteObservation):
            pass

        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        binding = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        source = binding.selected_record
        subclass = QuoteSubclass(
            *(getattr(source, field.name)
              for field in dataclasses.fields(OptionQuoteObservation))
        )
        object.__setattr__(binding, "candidate_records", (subclass,))
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_validate_proof_integrity",
            side_effect=AssertionError("proof integrity reached"),
        ):
            with self.assertRaises(TypeError):
                transform(structure, selection)


class SecondReviewProofExactnessTests(unittest.TestCase):
    def _fixture(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        group_bindings = bindings[0]
        quote_binding = group_bindings[
            MarketDataRelationshipRole.OPTION_QUOTE
        ]
        quote_member = next(
            member
            for member in assessment.request.groups[0].members
            if member.role is MarketDataRelationshipRole.OPTION_QUOTE
        )
        return (
            structure,
            selection,
            assessment,
            group_bindings,
            quote_binding,
            quote_member,
        )

    def test_wrong_correction_sidecar_types_fail_shape_without_id_access(self):
        class PoisonCorrection:
            @property
            def selected_record_id(self):
                raise AssertionError("wrong correction sidecar accessed")

        for value in (PoisonCorrection(), object()):
            with self.subTest(value=type(value).__name__):
                (
                    structure,
                    selection,
                    assessment,
                    _bindings,
                    quote_binding,
                    _member,
                ) = self._fixture()
                object.__setattr__(
                    quote_binding, "correction_selection", value
                )
                with force_selected(assessment), mock.patch.object(
                    transformations,
                    "_resolve_selected_objects",
                    side_effect=AssertionError("selected resolution reached"),
                ):
                    with self.assertRaises(TypeError):
                        transform(structure, selection)

        class CorrectionSubclass(CorrectionSelection):
            pass

        (
            structure,
            selection,
            assessment,
            _bindings,
            quote_binding,
            _member,
        ) = self._fixture()
        source = quote_binding.correction_selection
        subclass = CorrectionSubclass(
            *(getattr(source, field.name)
              for field in dataclasses.fields(CorrectionSelection))
        )
        object.__setattr__(quote_binding, "correction_selection", subclass)
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_resolve_selected_objects",
            side_effect=AssertionError("selected resolution reached"),
        ):
            with self.assertRaises(TypeError):
                transform(structure, selection)

    def test_exact_correction_reason_values_reject_strings_and_foreign_enums(self):
        class ForeignCorrectionReason(str, enum.Enum):
            ONLY = "only_candidate_selected"

        class StringSubclass(str):
            pass

        values = (
            ("only_candidate_selected",),
            ("dominating_revision_vector_selected",),
            ("foreign_reason",),
            (ForeignCorrectionReason.ONLY,),
            (StringSubclass("only_candidate_selected"),),
            [
                CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED
            ],
            (
                CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
                CorrectionSelectionReasonCode
                .DOMINATING_REVISION_VECTOR_SELECTED,
            ),
        )
        for reasons in values:
            with self.subTest(reasons=reasons):
                (
                    structure,
                    selection,
                    assessment,
                    _bindings,
                    quote_binding,
                    _member,
                ) = self._fixture()
                object.__setattr__(
                    quote_binding.correction_selection,
                    "reason_codes",
                    reasons,
                )
                with force_selected(assessment), self.assertRaises(ValueError):
                    transform(structure, selection)

    def test_exact_freshness_reason_category_and_status_values(self):
        class ForeignFreshnessReason(str, enum.Enum):
            FRESH = "fresh_within_policy"

        class ForeignCategory(str, enum.Enum):
            QUOTE = "quote"

        malformed = (
            ("reason", ("fresh_within_policy",)),
            ("reason", ("foreign_reason",)),
            ("reason", (ForeignFreshnessReason.FRESH,)),
            ("reason", (FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,)),
            ("reason", [FreshnessReasonCode.FRESH_WITHIN_POLICY]),
            (
                "reason",
                (
                    FreshnessReasonCode.FRESH_WITHIN_POLICY,
                    FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,
                ),
            ),
            ("category", "quote"),
            ("category", ForeignCategory.QUOTE),
            ("status", "fresh"),
        )
        for field, value in malformed:
            with self.subTest(field=field, value=value):
                (
                    structure,
                    selection,
                    assessment,
                    _bindings,
                    quote_binding,
                    _member,
                ) = self._fixture()
                target_field = "reason_codes" if field == "reason" else field
                object.__setattr__(
                    quote_binding.freshness_assessment,
                    target_field,
                    value,
                )
                with force_selected(assessment), self.assertRaises(ValueError):
                    transform(structure, selection)

    def test_coordinated_malformed_retained_ids_never_pass(self):
        class StringSubclass(str):
            pass

        malformed = (
            ("", ValueError),
            ("   ", ValueError),
            (" id", ValueError),
            ("id ", ValueError),
            (StringSubclass("id"), TypeError),
            (7, TypeError),
        )
        for value, error in malformed:
            with self.subTest(value=repr(value)):
                (
                    structure,
                    selection,
                    assessment,
                    _bindings,
                    quote_binding,
                    quote_member,
                ) = self._fixture()
                record = quote_binding.selected_record
                object.__setattr__(
                    record.metadata,
                    "record_id",
                    value,
                )
                object.__setattr__(
                    quote_binding.correction_selection,
                    "candidate_record_ids",
                    (value,),
                )
                object.__setattr__(
                    quote_binding.correction_selection,
                    "selected_record_id",
                    value,
                )
                object.__setattr__(
                    quote_binding.freshness_assessment,
                    "record_id",
                    value,
                )
                object.__setattr__(
                    quote_member.reference,
                    "selected_record_id",
                    value,
                )
                with force_selected(assessment), mock.patch.object(
                    transformations,
                    "_match_structure_legs",
                    side_effect=AssertionError("correspondence reached"),
                ):
                    with self.assertRaises(error):
                        transform(structure, selection)

    def test_each_role_specific_selected_record_subclass_is_rejected_globally(self):
        cases = (
            (
                MarketDataRelationshipRole.OPTION_QUOTE,
                OptionQuoteObservation,
            ),
            (
                MarketDataRelationshipRole.OPTION_VOLUME,
                OptionVolumeObservation,
            ),
            (
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                OptionOpenInterestObservation,
            ),
        )
        for role, record_type in cases:
            with self.subTest(role=role):
                (
                    structure,
                    selection,
                    assessment,
                    bindings,
                    _quote_binding,
                    _member,
                ) = self._fixture()
                binding = bindings[role]
                source = binding.selected_record
                subclass_type = type(
                    f"{record_type.__name__}Subclass",
                    (record_type,),
                    {},
                )
                subclass = subclass_type(
                    *(getattr(source, field.name)
                      for field in dataclasses.fields(record_type))
                )
                object.__setattr__(binding, "candidate_records", (subclass,))
                with force_selected(assessment), mock.patch.object(
                    transformations,
                    "_validate_proof_integrity",
                    side_effect=AssertionError("proof integrity reached"),
                ):
                    with self.assertRaises(TypeError):
                        transform(structure, selection)


class CorrectedDecimalContextTests(unittest.TestCase):
    def _assert_context_unchanged(self, ambient, before):
        self.assertEqual(ambient.prec, before.prec)
        self.assertEqual(ambient.rounding, before.rounding)
        self.assertEqual(ambient.Emin, before.Emin)
        self.assertEqual(ambient.Emax, before.Emax)
        self.assertEqual(ambient.capitals, before.capitals)
        self.assertEqual(ambient.clamp, before.clamp)
        self.assertEqual(dict(ambient.traps), dict(before.traps))
        self.assertEqual(dict(ambient.flags), dict(before.flags))

    @contextmanager
    def _record_phases(self, phases):
        with ExitStack() as stack:
            for phase, helper_name in (
                CorrectedPhaseSequenceTests.PHASE_HELPERS
            ):
                original = getattr(transformations, helper_name)

                def wrapper(
                    *args,
                    _phase=phase,
                    _original=original,
                    **kwargs,
                ):
                    if not phases or phases[-1] != _phase:
                        phases.append(_phase)
                    return _original(*args, **kwargs)

                stack.enter_context(mock.patch.object(
                    transformations, helper_name, wrapper
                ))
            yield

    def test_exact_results_are_invariant_under_adversarial_ambient_contexts(self):
        structure = make_structure(
            ("call", "put"), quantity=999, multiplier=1000
        )
        selection, _, _ = make_selection(
            structure,
            bid=("9.9900", "0.010"),
            ask=("10.0100", "0.020"),
        )
        cases = (
            (2, decimal.ROUND_FLOOR, False),
            (6, decimal.ROUND_CEILING, False),
            (28, decimal.ROUND_HALF_UP, False),
            (2, decimal.ROUND_DOWN, True),
        )
        for precision, rounding, trap in cases:
            with self.subTest(
                precision=precision, rounding=rounding, trap=trap
            ), decimal.localcontext() as ambient:
                ambient.prec = precision
                ambient.rounding = rounding
                ambient.traps[decimal.Inexact] = trap
                ambient.traps[decimal.Rounded] = trap
                before = ambient.copy()
                result = transform(structure, selection)
                self.assertEqual(result.record.quoted_bid_value, 9990000.0)
                self.assertEqual(result.record.quoted_ask_value, 10019970.0)
                self.assertEqual(ambient.prec, before.prec)
                self.assertEqual(ambient.rounding, before.rounding)
                self.assertEqual(ambient.Emin, before.Emin)
                self.assertEqual(ambient.Emax, before.Emax)
                self.assertEqual(ambient.clamp, before.clamp)
                self.assertEqual(dict(ambient.traps), dict(before.traps))
                self.assertEqual(dict(ambient.flags), dict(before.flags))

    def test_reviewed_one_leg_reproduction_survives_precision_two(self):
        structure = make_structure()
        selection, _, _ = make_selection(
            structure, bid=("1.25", "2"), ask=("1.50", "2")
        )
        with decimal.localcontext() as ambient:
            ambient.prec = 2
            ambient.traps[decimal.Inexact] = True
            ambient.traps[decimal.Rounded] = True
            result = transform(structure, selection)
        self.assertEqual(result.record.quoted_bid_value, 125.0)
        self.assertEqual(result.record.quoted_ask_value, 150.0)

    def test_ambient_context_is_unchanged_on_failure(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE].selected_record
        object.__setattr__(quote, "bid_premium", decimal.Decimal("1e10000"))
        object.__setattr__(quote, "ask_premium", decimal.Decimal("2e10000"))
        with decimal.localcontext() as ambient:
            ambient.prec = 2
            ambient.rounding = decimal.ROUND_FLOOR
            ambient.traps[decimal.Inexact] = True
            ambient.traps[decimal.Rounded] = True
            before = ambient.copy()
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
            self.assertEqual(ambient.prec, before.prec)
            self.assertEqual(ambient.rounding, before.rounding)
            self.assertEqual(dict(ambient.traps), dict(before.traps))
            self.assertEqual(dict(ambient.flags), dict(before.flags))

    def test_upper_exponent_failures_are_value_errors_in_all_caller_contexts(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE].selected_record
        object.__setattr__(
            quote,
            "bid_premium",
            decimal.Decimal("1e999999999999999999"),
        )
        object.__setattr__(
            quote,
            "ask_premium",
            decimal.Decimal("2e999999999999999999"),
        )
        cases = (
            (2, decimal.ROUND_FLOOR),
            (6, decimal.ROUND_CEILING),
            (28, decimal.ROUND_DOWN),
        )
        for precision, rounding in cases:
            with self.subTest(
                precision=precision, rounding=rounding
            ), decimal.localcontext() as ambient:
                phases = []
                ambient.prec = precision
                ambient.rounding = rounding
                ambient.traps[decimal.Inexact] = True
                ambient.traps[decimal.Rounded] = True
                ambient.traps[decimal.Overflow] = True
                before = ambient.copy()
                with force_selected(assessment), ExitStack() as stack:
                    for phase, helper_name in (
                        CorrectedPhaseSequenceTests.PHASE_HELPERS
                    ):
                        original = getattr(transformations, helper_name)

                        def wrapper(
                            *args,
                            _phase=phase,
                            _original=original,
                            **kwargs,
                        ):
                            if not phases or phases[-1] != _phase:
                                phases.append(_phase)
                            return _original(*args, **kwargs)

                        stack.enter_context(mock.patch.object(
                            transformations, helper_name, wrapper
                        ))
                    with self.assertRaises(ValueError) as raised:
                        transform(structure, selection)
                self.assertNotIsInstance(
                    raised.exception, decimal.DecimalException
                )
                self.assertIn(
                    "Decimal aggregation", str(raised.exception)
                )
                self.assertEqual(ambient.prec, before.prec)
                self.assertEqual(ambient.rounding, before.rounding)
                self.assertEqual(dict(ambient.traps), dict(before.traps))
                self.assertEqual(dict(ambient.flags), dict(before.flags))
                self.assertEqual(
                    tuple(phases),
                    tuple(
                        phase
                        for phase, _helper_name in (
                            CorrectedPhaseSequenceTests.PHASE_HELPERS
                        )[:14]
                    ),
                )

    def test_lower_exponent_representability_and_rejection_are_deterministic(self):
        representable = decimal.Decimal(
            (0, (1,), decimal.MIN_EMIN)
        )
        exact = transformations._exact_scaled_sum(((representable, 100),))
        self.assertEqual(
            exact.as_tuple(),
            decimal.Decimal(
                (0, (1, 0, 0), decimal.MIN_EMIN)
            ).as_tuple(),
        )

        unrepresentable = decimal.Decimal(
            (0, (1,), decimal.MIN_EMIN - 20)
        )
        for precision in (2, 6, 28):
            with self.subTest(precision=precision), decimal.localcontext() as ambient:
                ambient.prec = precision
                ambient.traps[decimal.Inexact] = True
                ambient.traps[decimal.Rounded] = True
                ambient.traps[decimal.Overflow] = True
                before = ambient.copy()
                with self.assertRaises(ValueError) as raised:
                    transformations._exact_scaled_sum(
                        ((unrepresentable, 100),)
                    )
                self.assertNotIsInstance(
                    raised.exception, decimal.DecimalException
                )
                self.assertEqual(ambient.prec, before.prec)
                self.assertEqual(dict(ambient.traps), dict(before.traps))
                self.assertEqual(dict(ambient.flags), dict(before.flags))

    def test_max_emax_coefficient_carry_matrix_is_exact_and_context_isolated(self):
        one = decimal.Decimal((0, (1,), decimal.MAX_EMAX))
        nine = decimal.Decimal((0, (9,), decimal.MAX_EMAX))
        lower = decimal.Decimal((0, (1,), decimal.MAX_EMAX - 1))
        cases = (
            (
                "two_terms",
                ((one, 1), (one, 1)),
                decimal.Decimal((0, (2,), decimal.MAX_EMAX)),
            ),
            (
                "several_terms",
                tuple((one, 1) for _index in range(8)),
                decimal.Decimal((0, (8,), decimal.MAX_EMAX)),
            ),
            (
                "different_exponents",
                ((one, 1), (lower, 1)),
                decimal.Decimal((0, (1, 1), decimal.MAX_EMAX - 1)),
            ),
        )
        caller_contexts = (
            (2, decimal.ROUND_FLOOR),
            (6, decimal.ROUND_CEILING),
            (28, decimal.ROUND_DOWN),
        )
        for precision, rounding in caller_contexts:
            with self.subTest(
                precision=precision, rounding=rounding
            ), decimal.localcontext() as ambient:
                ambient.prec = precision
                ambient.rounding = rounding
                ambient.traps[decimal.Inexact] = True
                ambient.traps[decimal.Rounded] = True
                ambient.traps[decimal.Overflow] = True
                before = ambient.copy()
                for name, terms, expected in cases:
                    with self.subTest(name=name):
                        result = transformations._exact_scaled_sum(terms)
                        self.assertEqual(result.as_tuple(), expected.as_tuple())
                        self._assert_context_unchanged(ambient, before)
                with self.assertRaises(ValueError) as raised:
                    transformations._exact_scaled_sum(
                        ((nine, 1), (one, 1))
                    )
                self.assertNotIsInstance(
                    raised.exception, decimal.DecimalException
                )
                self.assertIsInstance(
                    raised.exception.__cause__, decimal.DecimalException
                )
                self._assert_context_unchanged(ambient, before)

    def test_public_upper_boundary_reaches_float_and_actual_sum_overflow_does_not(self):
        one = decimal.Decimal((0, (1,), decimal.MAX_EMAX))
        two = decimal.Decimal((0, (2,), decimal.MAX_EMAX))
        nine = decimal.Decimal((0, (9,), decimal.MAX_EMAX))
        nine_point_one = decimal.Decimal(
            (0, (9, 1), decimal.MAX_EMAX - 1)
        )
        expected_bid = decimal.Decimal(
            (0, (2,), decimal.MAX_EMAX)
        )
        expected_ask = decimal.Decimal(
            (0, (4,), decimal.MAX_EMAX)
        )
        expected_prefix = tuple(
            phase
            for phase, _helper_name in (
                CorrectedPhaseSequenceTests.PHASE_HELPERS
            )
        )

        structure = make_structure(
            ("call", "put"), quantity=1, multiplier=1
        )
        selection, assessment, _bindings = make_selection(
            structure,
            bid=(one, one),
            ask=(two, two),
        )
        phases = []

        def reject_float_boundary(bid_value, ask_value):
            if not phases or phases[-1] != "float_boundary":
                phases.append("float_boundary")
            self.assertEqual(
                (bid_value.as_tuple(), ask_value.as_tuple()),
                (
                    expected_bid.as_tuple(),
                    expected_ask.as_tuple(),
                ),
            )
            raise ValueError("position values must be finite floats")

        with force_selected(assessment), self._record_phases(phases), (
            mock.patch.object(
                transformations,
                "_convert_position_values",
                side_effect=reject_float_boundary,
            )
        ), self.assertRaises(ValueError) as raised:
            transform(structure, selection)
        self.assertNotIsInstance(raised.exception, decimal.DecimalException)
        self.assertEqual(tuple(phases), expected_prefix[:15])

        overflow_selection, overflow_assessment, _bindings = make_selection(
            structure,
            bid=(nine, one),
            ask=(nine_point_one, two),
        )
        phases = []
        with force_selected(overflow_assessment), self._record_phases(phases), (
            mock.patch.object(
                transformations,
                "_convert_position_values",
                side_effect=AssertionError("float boundary reached"),
            )
        ), self.assertRaises(ValueError) as raised:
            transform(structure, overflow_selection)
        self.assertNotIsInstance(raised.exception, decimal.DecimalException)
        self.assertIsInstance(
            raised.exception.__cause__, decimal.DecimalException
        )
        self.assertEqual(tuple(phases), expected_prefix[:14])


class CorrectedPhaseSequenceTests(unittest.TestCase):
    PHASE_HELPERS = (
        ("calculation_id", "_validate_calculation_id"),
        ("structure", "_validate_structure"),
        ("relationship_selection", "_validate_relationship_selection"),
        ("calculated_at", "_normalize_calculated_at"),
        ("selection_status", "_validate_selection_status"),
        ("selected_candidate", "_resolve_selected_candidate"),
        ("shape", "_validate_selected_shape"),
        ("selected_resolution", "_resolve_selected_objects"),
        ("selected_record_types", "_validate_selected_record_types"),
        ("proof_integrity", "_validate_proof_integrity"),
        ("leg_correspondence", "_match_structure_legs"),
        ("contract_session", "_validate_contract_sessions"),
        ("required_values", "_validate_required_values"),
        ("decimal_aggregation", "_aggregate_decimal_values"),
        ("float_boundary", "_convert_position_values"),
        ("research_record", "_construct_research_record"),
        ("input_references", "_construct_input_references"),
        ("parameters", "_construct_parameters"),
        ("quality_flags", "_derive_quality_flags"),
        ("lineage", "_construct_lineage"),
        ("result", "_construct_result"),
    )

    def test_success_has_exact_literal_21_phase_sequence(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        phases = []
        with ExitStack() as stack:
            for phase, helper_name in self.PHASE_HELPERS:
                original = getattr(transformations, helper_name)

                def wrapper(*args, _phase=phase, _original=original, **kwargs):
                    if not phases or phases[-1] != _phase:
                        phases.append(_phase)
                    return _original(*args, **kwargs)

                stack.enter_context(mock.patch.object(
                    transformations, helper_name, side_effect=wrapper
                ))
            transform(structure, selection)
        expected = tuple(phase for phase, _helper in self.PHASE_HELPERS)
        self.assertEqual(tuple(phases), expected)
        mutations = (
            expected[:-1],
            expected[:8] + expected[9:],
            expected[:8] + (expected[7],) + expected[8:],
            expected + ("trailing",),
        )
        for mutated in mutations:
            with self.subTest(mutated=mutated):
                self.assertNotEqual(mutated, expected)

    def test_each_late_failure_poison_protects_the_next_phase(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        scenarios = (
            ("_validate_proof_integrity", ValueError("proof"),
             "_match_structure_legs"),
            ("_match_structure_legs", ValueError("leg"),
             "_validate_contract_sessions"),
            ("_validate_contract_sessions", ValueError("session"),
             "_validate_required_values"),
            ("_validate_required_values", ValueError("values"),
             "_aggregate_decimal_values"),
            ("_aggregate_decimal_values", decimal.Inexact(),
             "_convert_position_values"),
            ("_convert_position_values", ValueError("float"),
             "_construct_research_record"),
            ("_construct_research_record", ValueError("record"),
             "_construct_input_references"),
            ("_construct_input_references", ValueError("inputs"),
             "_construct_parameters"),
            ("_construct_parameters", ValueError("parameters"),
             "_derive_quality_flags"),
            ("_derive_quality_flags", ValueError("flags"),
             "_construct_lineage"),
            ("_construct_lineage", ValueError("lineage"),
             "_construct_result"),
        )
        for failing, error, later in scenarios:
            with self.subTest(failing=failing), force_selected(assessment):
                with mock.patch.object(
                    transformations, failing, side_effect=error
                ), mock.patch.object(
                    transformations,
                    later,
                    side_effect=AssertionError(f"{later} reached"),
                ):
                    with self.assertRaises(type(error)):
                        transform(structure, selection)


class StructureCostsPublicSurfaceTests(unittest.TestCase):
    def test_exact_cost_surface_signature_fields_and_structural_result(self):
        self.assertEqual(
            transformations.__all__,
            (
                "StructureLiquidityTransformationResult",
                "transform_structure_liquidity",
                "StructureCostsTransformationResult",
                "transform_structure_costs",
                "HistoricalReturnPriceBasis",
                "HistoricalRealizedVolatility",
                "HistoricalRealizedVolatilityTransformationResult",
                "transform_historical_realized_volatility",
                "VolatilityEnvironmentTransformationResult",
                "transform_volatility_environment",
                "TailPricingTransformationResult",
                "transform_tail_pricing",
                "ScenarioPricingMethodology",
                "ScenarioPricingLegCalculation",
                "NonExpirationScenarioPricingCalculation",
                "ScenarioPricingCalculationResult",
                "ScenarioValuationTransformationResult",
                "transform_scenario_valuation",
                "ExactRational",
                "ExpirationPayoffThresholdSide",
                "ExpirationPayoffThresholdStatus",
                "ExpirationPayoffThreshold",
                "ExpirationPayoffThresholdEvidence",
                "ExpirationPayoffThresholdTransformationResult",
                "transform_expiration_payoff_thresholds",
                "TreasuryPricingRateInput",
                "TreasuryPricingRateTransformationResult",
                "transform_treasury_pricing_rate",
            ),
        )
        self.assertEqual(len(market_data.__all__), 64)
        self.assertFalse(
            hasattr(convexity_hunter, "StructureCostsTransformationResult")
        )
        self.assertFalse(hasattr(convexity_hunter, "transform_structure_costs"))
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                StructureCostsTransformationResult
            )),
            ("record", "lineage"),
        )
        signature = inspect.signature(transform_structure_costs)
        self.assertEqual(
            tuple(signature.parameters),
            (
                "calculation_id",
                "structure",
                "relationship_selection",
                "commissions_and_fees",
                "repeated_bet_count",
                "calculated_at",
            ),
        )
        self.assertTrue(all(
            parameter.annotation is object
            for parameter in signature.parameters.values()
        ))
        self.assertIs(
            signature.return_annotation,
            StructureCostsTransformationResult,
        )
        structure = make_structure()
        selection, _, _, _ = make_cost_selection(structure)
        result = transform_costs(structure, selection)
        self.assertIs(
            StructureCostsTransformationResult(
                result.record, result.lineage
            ).record,
            result.record,
        )
        with self.assertRaises(TypeError):
            StructureCostsTransformationResult(object(), result.lineage)
        with self.assertRaises(TypeError):
            StructureCostsTransformationResult(result.record, object())


class StructureCostsSuccessfulCalculationTests(unittest.TestCase):
    METHODOLOGY = (
        "model=Synthetic Black-Scholes;model_version=fixture-v1;"
        "rate_input=Synthetic USD curve input;"
        "dividend_input=Synthetic dividend input;"
        "theta_day_basis=Provider calendar-day convention;"
        "unit_convention=Contract-defined canonical units"
    )

    def test_one_leg_call_and_put_literal_economics_and_assumptions(self):
        for option_type in ("call", "put"):
            with self.subTest(option_type=option_type):
                structure = make_structure(
                    (option_type,), quantity=2, multiplier=25
                )
                selection, _, _, _ = make_cost_selection(structure)
                result = transform_costs(
                    structure,
                    selection,
                    decimal.Decimal("1.25"),
                    3,
                )
                self.assertIs(result.record.structure, structure)
                self.assertEqual(result.record.as_of_date, SESSION_DATE)
                self.assertEqual(result.record.quoted_mid_premium, 60.0)
                self.assertEqual(result.record.estimated_spread_cost, 10.0)
                self.assertEqual(result.record.commissions_and_fees, 1.25)
                self.assertEqual(result.record.theta_per_day, -5.0)
                self.assertEqual(result.record.gamma, 1.0)
                self.assertEqual(result.record.underlying_price, 100.0)
                self.assertEqual(
                    result.record.greeks_methodology, self.METHODOLOGY
                )
                self.assertEqual(result.record.repeated_bet_count, 3)

    def test_two_leg_straddle_scaling_zero_values_and_leg_order_evidence(self):
        first = make_structure(("call", "put"), quantity=3, multiplier=10)
        second = make_structure(("put", "call"), quantity=3, multiplier=10)
        first_selection, _, _, _ = make_cost_selection(
            first, gamma=("0", "0"), theta=("0", "0")
        )
        second_selection, _, _, _ = make_cost_selection(
            second,
            bid=("2.00", "1.00"),
            ask=("2.60", "1.40"),
            gamma=("0", "0"),
            theta=("0", "0"),
        )
        first_result = transform_costs(first, first_selection)
        second_result = transform_costs(second, second_selection)
        for result in (first_result, second_result):
            self.assertEqual(result.record.quoted_mid_premium, 105.0)
            self.assertEqual(result.record.estimated_spread_cost, 15.0)
            self.assertEqual(result.record.commissions_and_fees, 0.0)
            self.assertEqual(result.record.theta_per_day, 0.0)
            self.assertEqual(result.record.gamma, 0.0)
            self.assertEqual(result.record.repeated_bet_count, 1)
            self.assertEqual(
                result.lineage.quality_flags,
                (
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                    CalculationQualityFlag.ASSUMPTION_APPLIED,
                ),
            )
        first_parameters = transformations._decode_cost_parameters(
            first_result.lineage.parameters_json
        )
        second_parameters = transformations._decode_cost_parameters(
            second_result.lineage.parameters_json
        )
        self.assertEqual(
            tuple(
                item["option_type"]
                for item in first_parameters["structure_identity"]["legs"]
            ),
            ("call", "put"),
        )
        self.assertEqual(
            tuple(
                item["option_type"]
                for item in second_parameters["structure_identity"]["legs"]
            ),
            ("put", "call"),
        )

    def test_lineage_has_all_four_inputs_and_literal_canonical_parameters(self):
        structure = make_structure(("call",), quantity=2, multiplier=25)
        selection, _, underlying, bindings = make_cost_selection(structure)
        result = transform_costs(
            structure, selection, decimal.Decimal("1.25"), 3
        )
        expected_records = (
            underlying.selected_record,
            bindings[0][MarketDataRelationshipRole.OPTION_QUOTE].selected_record,
            bindings[0][MarketDataRelationshipRole.OPTION_GREEKS].selected_record,
            bindings[0][
                MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
            ].selected_record,
        )
        self.assertEqual(len(result.lineage.inputs), 4)
        self.assertEqual(
            tuple(item.record_id for item in result.lineage.inputs),
            tuple(sorted(record.metadata.record_id for record in expected_records)),
        )
        for item in result.lineage.inputs:
            record = next(
                record for record in expected_records
                if record.metadata.record_id == item.record_id
            )
            self.assertEqual(item.normalized_at, record.metadata.normalized_at)
            self.assertEqual(
                item.source_ids,
                tuple(source.source_id
                      for source in record.metadata.source_references),
            )
        decoded = transformations._decode_cost_parameters(
            result.lineage.parameters_json
        )
        self.assertEqual(len(decoded), 20)
        self.assertEqual(
            set(decoded),
            transformations._COST_PARAMETER_KEYS,
        )
        self.assertEqual(result.lineage.calculation_id, "calculation-3c7b")
        self.assertEqual(result.lineage.calculation_type, "structure_costs")
        self.assertEqual(
            result.lineage.methodology_id, "exact-structure-costs"
        )
        self.assertEqual(result.lineage.methodology_version, "v0.2")

    def test_two_leg_lineage_contains_seven_unique_authoritative_inputs(self):
        structure = make_structure(("call", "put"))
        selection, _, _, _ = make_cost_selection(structure)
        result = transform_costs(structure, selection)
        self.assertEqual(len(result.lineage.inputs), 7)
        self.assertEqual(
            len({item.record_id for item in result.lineage.inputs}), 7
        )
        self.assertEqual(
            sum("contract-reference" in item.record_id
                for item in result.lineage.inputs),
            2,
        )


class StructureCostsBoundaryAndProofTests(unittest.TestCase):
    def test_top_level_types_and_assumption_boundaries(self):
        structure = make_structure()
        selection, _, _, _ = make_cost_selection(structure)
        invalid = (
            ((object(), structure, selection, decimal.Decimal("0"), 1,
              CALCULATED_AT), TypeError),
            ((" ", structure, selection, decimal.Decimal("0"), 1,
              CALCULATED_AT), ValueError),
            (("x", object(), selection, decimal.Decimal("0"), 1,
              CALCULATED_AT), TypeError),
            (("x", structure, object(), decimal.Decimal("0"), 1,
              CALCULATED_AT), TypeError),
            (("x", structure, selection, 0.0, 1, CALCULATED_AT), TypeError),
            (("x", structure, selection, decimal.Decimal("-0.01"), 1,
              CALCULATED_AT), ValueError),
            (("x", structure, selection, decimal.Decimal("NaN"), 1,
              CALCULATED_AT), ValueError),
            (("x", structure, selection, decimal.Decimal("0"), True,
              CALCULATED_AT), TypeError),
            (("x", structure, selection, decimal.Decimal("0"), 0,
              CALCULATED_AT), ValueError),
            (("x", structure, selection, decimal.Decimal("0"), 1,
              datetime.datetime(2030, 1, 2)), ValueError),
        )
        for arguments, error_type in invalid:
            with self.subTest(arguments=arguments, error_type=error_type):
                with self.assertRaises(error_type):
                    transform_structure_costs(*arguments)

    def test_exact_shape_binding_universe_and_reuse_multiplicities(self):
        structure = make_structure(("call", "put"))
        selection, assessment, underlying, bindings = make_cost_selection(
            structure
        )
        result = transform_costs(structure, selection)
        self.assertEqual(len(assessment.request.groups), 6)
        self.assertEqual(len(assessment.timing_assessment.bindings), 7)
        references = tuple(
            member.reference.selected_record_id
            for group in assessment.request.groups
            for member in group.members
        )
        self.assertEqual(
            references.count(underlying.selected_record.metadata.record_id), 2
        )
        for leg_bindings in bindings:
            expected_counts = (
                (MarketDataRelationshipRole.OPTION_QUOTE, 3),
                (MarketDataRelationshipRole.OPTION_GREEKS, 2),
                (MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE, 1),
            )
            for role, count in expected_counts:
                self.assertEqual(
                    references.count(
                        leg_bindings[role].selected_record.metadata.record_id
                    ),
                    count,
                )
        self.assertIs(result.record.structure, structure)
        with changed(
            assessment.timing_assessment,
            "bindings",
            assessment.timing_assessment.bindings[:-1],
        ), force_selected(assessment):
            with self.assertRaises(ValueError):
                transform_costs(structure, selection)

    def test_wrong_record_type_is_type_error_before_economic_access(self):
        structure = make_structure()
        selection, assessment, _, bindings = make_cost_selection(structure)
        quote_binding = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        greeks_binding = bindings[0][MarketDataRelationshipRole.OPTION_GREEKS]
        wrong_record = dataclasses.replace(
            greeks_binding.selected_record,
            metadata=dataclasses.replace(
                greeks_binding.selected_record.metadata,
                record_id=quote_binding.correction_selection.selected_record_id,
            ),
        )
        with changed(
            quote_binding,
            "candidate_records",
            (wrong_record,),
        ), force_selected(assessment):
            with self.assertRaises(TypeError):
                transform_costs(structure, selection)

    def test_contract_correspondence_and_methodology_failures(self):
        structure = make_structure(("call", "put"))
        selection, assessment, _, bindings = make_cost_selection(structure)
        put_greeks = bindings[1][MarketDataRelationshipRole.OPTION_GREEKS]
        scenarios = (
            (put_greeks.selected_record, "model_name", "Different model"),
            (put_greeks.selected_record, "model_version", "different-version"),
            (put_greeks.selected_record, "rate_input_description", "Different rate"),
            (
                put_greeks.selected_record,
                "dividend_input_description",
                "Different dividend",
            ),
            (put_greeks.selected_record, "theta_day_basis", "Trading day"),
            (
                put_greeks.selected_record.metadata,
                "unit_convention",
                "Different units",
            ),
        )
        for target, name, value in scenarios:
            with self.subTest(name=name), changed_with_semantic_proof(
                assessment,
                put_greeks,
                target,
                name,
                value,
            ), force_selected(assessment):
                with self.assertRaises(ValueError):
                    transform_costs(structure, selection)

    def test_mixed_session_and_contract_reference_mismatch_are_rejected(self):
        structure = make_structure()
        selection, assessment, _, bindings = make_cost_selection(structure)
        greeks_binding = bindings[0][MarketDataRelationshipRole.OPTION_GREEKS]
        with changed_with_semantic_proof(
            assessment,
            greeks_binding,
            greeks_binding.selected_record,
            "session_date",
            SESSION_DATE + datetime.timedelta(days=1),
        ), force_selected(assessment):
            with self.assertRaises(ValueError):
                transform_costs(structure, selection)

        reference_binding = bindings[0][
            MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
        ]
        mismatched_contract = build_option_contract_key(
            option_type="put",
            expiration=structure.legs[0].expiration,
            strike=decimal.Decimal(str(structure.legs[0].strike)),
            contract_multiplier=structure.legs[0].contract_multiplier,
        )
        with changed_with_semantic_proof(
            assessment,
            reference_binding,
            reference_binding.selected_record,
            "contract_key",
            mismatched_contract,
        ), force_selected(assessment):
            with self.assertRaises(ValueError):
                transform_costs(structure, selection)

    def test_missing_or_wrong_sign_greeks_and_float_overflow_are_rejected(self):
        structure = make_structure()
        selection, assessment, _, bindings = make_cost_selection(structure)
        greeks = bindings[0][
            MarketDataRelationshipRole.OPTION_GREEKS
        ].selected_record
        scenarios = (
            ("gamma", None),
            ("theta", None),
            ("gamma", decimal.Decimal("-0.01")),
            ("theta", decimal.Decimal("0.01")),
        )
        for name, value in scenarios:
            with self.subTest(name=name), changed(greeks, name, value), force_selected(
                assessment
            ):
                with self.assertRaises(ValueError):
                    transform_costs(structure, selection)
        with self.assertRaises(ValueError):
            transform_costs(
                structure, selection, decimal.Decimal("1E+10000")
            )

    def test_underlying_midpoint_ignores_last_and_proof_layers_are_not_called(self):
        structure = make_structure()
        selection, _, underlying, _ = make_cost_selection(
            structure, underlying_bid="98", underlying_ask="102"
        )
        forbidden = (
            "select_correction_candidate",
            "assess_market_data_freshness",
            "bind_selected_fresh_market_data",
            "assess_market_data_snapshot_timing",
            "assess_market_data_relationships",
            "select_market_data_relationship_assessment",
            "assess_market_data_historical_series",
        )
        with ExitStack() as stack:
            for name in forbidden:
                stack.enter_context(mock.patch.object(
                    market_data,
                    name,
                    side_effect=AssertionError(f"{name} must not be called"),
                ))
            with changed(
                underlying.selected_record,
                "last_price",
                decimal.Decimal("999"),
            ):
                result = transform_costs(structure, selection)
        self.assertEqual(result.record.underlying_price, 100.0)

    def test_lineage_chronology_and_calculation_id_collision(self):
        structure = make_structure()
        selection, _, _, _ = make_cost_selection(structure)
        with self.assertRaises(ValueError):
            transform_costs(
                structure,
                selection,
                calculated_at=datetime.datetime(
                    2029, 1, 1, tzinfo=datetime.timezone.utc
                ),
            )
        input_id = selection.selected_candidate.timing_assessment.bindings[
            0
        ].selected_record.metadata.record_id
        with self.assertRaises(ValueError):
            transform_costs(
                structure,
                selection,
                calculation_id=input_id,
            )

    def test_discarded_correction_candidate_is_excluded_and_flagged(self):
        structure = make_structure()
        selection, assessment, _, bindings = make_cost_selection(structure)
        quote_binding = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        selected = quote_binding.selected_record
        discarded = dataclasses.replace(
            selected,
            metadata=dataclasses.replace(
                selected.metadata, record_id="cost-discarded-not-consumed"
            ),
        )
        object.__setattr__(
            quote_binding, "candidate_records", (discarded, selected)
        )
        object.__setattr__(
            quote_binding.correction_selection,
            "candidate_record_ids",
            tuple(sorted((
                discarded.metadata.record_id,
                selected.metadata.record_id,
            ))),
        )
        object.__setattr__(
            quote_binding.correction_selection,
            "reason_codes",
            (
                CorrectionSelectionReasonCode
                .DOMINATING_REVISION_VECTOR_SELECTED,
            ),
        )
        with force_selected(assessment):
            result = transform_costs(structure, selection)
        self.assertNotIn(
            discarded.metadata.record_id,
            tuple(item.record_id for item in result.lineage.inputs),
        )
        self.assertIn(
            CalculationQualityFlag.CORRECTION_SELECTED,
            result.lineage.quality_flags,
        )

    def test_shape_and_unique_binding_universe_failures(self):
        structure = make_structure()
        selection, assessment, _, _ = make_cost_selection(structure)
        original_groups = assessment.request.groups
        original_bindings = assessment.timing_assessment.bindings
        analytics = next(
            group for group in original_groups
            if group.group_kind
            is MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1
        )
        snapshot = next(
            group for group in original_groups
            if group.group_kind
            is MarketDataRelationshipGroupKind
            .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
        )
        underlying_member = next(
            member for member in snapshot.members
            if member.role is MarketDataRelationshipRole.UNDERLYING_QUOTE
        )
        scenarios = (
            (assessment.request, "groups", original_groups[:-1]),
            (analytics, "members", analytics.members[:-1]),
            (
                analytics,
                "members",
                analytics.members + (underlying_member,),
            ),
            (
                assessment.timing_assessment,
                "bindings",
                original_bindings + (original_bindings[0],),
            ),
        )
        for target, name, value in scenarios:
            with self.subTest(name=name), changed(target, name, value), force_selected(
                assessment
            ):
                with self.assertRaises(ValueError):
                    transform_costs(structure, selection)

    def test_each_structure_identity_component_is_required(self):
        structure = make_structure()
        alternatives = (
            build_option_contract_key(option_type="put"),
            build_option_contract_key(
                expiration=EXPIRATION + datetime.timedelta(days=1)
            ),
            build_option_contract_key(strike=decimal.Decimal("101")),
            build_option_contract_key(contract_multiplier=50),
            build_option_contract_key(
                underlying_key=build_underlying_key(symbol="QQQ")
            ),
        )
        for contract in alternatives:
            with self.subTest(contract=contract):
                selection, _, _, _ = make_cost_selection(
                    structure, contracts=(contract,)
                )
                with self.assertRaises(ValueError):
                    transform_costs(structure, selection)

    def test_all_cost_quality_flags_and_prohibited_flags(self):
        structure = make_structure()
        selection, assessment, underlying, bindings = make_cost_selection(
            structure
        )
        records = (
            underlying.selected_record,
            bindings[0][MarketDataRelationshipRole.OPTION_QUOTE].selected_record,
            bindings[0][MarketDataRelationshipRole.OPTION_GREEKS].selected_record,
            bindings[0][
                MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
            ].selected_record,
        )
        originals = tuple(record.metadata for record in records)
        partial_source = dataclasses.replace(
            originals[3].source_references[0],
            quality_flags=(SourceQualityFlag.PARTIAL,),
        )
        composite_sources = (
            dataclasses.replace(
                originals[1].source_references[0], source_id="cost-composite-a"
            ),
            dataclasses.replace(
                originals[1].source_references[0],
                source_id="cost-composite-b",
                provider_record_id="cost-composite-record-b",
                provider_request_id="cost-composite-request-b",
                source_uri="synthetic://cost-composite/b",
            ),
        )
        complete_replacements = (
            dataclasses.replace(
                originals[0],
                quality_flags=(NormalizationQualityFlag.INTERPOLATED,),
            ),
            build_normalization_metadata(
                composite_sources,
                record_id=originals[1].record_id,
                effective_observed_at=originals[1].effective_observed_at,
                normalized_at=originals[1].normalized_at,
                record_origin=DataOrigin.SYSTEM_COMPOSITE,
                quality_flags=(NormalizationQualityFlag.COMPOSITE_SOURCE,),
            ),
            originals[2],
            originals[3],
        )
        for record, metadata in zip(records, complete_replacements):
            object.__setattr__(record, "metadata", metadata)
        try:
            with force_selected(assessment):
                flags = transform_costs(structure, selection).lineage.quality_flags
            self.assertEqual(
                flags,
                (
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                    CalculationQualityFlag.INTERPOLATED,
                    CalculationQualityFlag.COMPOSITE_INPUT_USED,
                    CalculationQualityFlag.ASSUMPTION_APPLIED,
                ),
            )
            self.assertNotIn(CalculationQualityFlag.ANNUALIZED, flags)
            self.assertNotIn(CalculationQualityFlag.ADJUSTED_INPUT_USED, flags)
            object.__setattr__(
                records[3],
                "metadata",
                dataclasses.replace(
                    originals[3], source_references=(partial_source,)
                ),
            )
            with force_selected(assessment), self.assertRaises(ValueError):
                transform_costs(structure, selection)
        finally:
            for record, metadata in zip(records, originals):
                object.__setattr__(record, "metadata", metadata)


class StructureCostsVerifiabilityCorrectionTests(unittest.TestCase):
    def make_result(self, option_types=("call",)):
        structure = make_structure(option_types)
        selection, _, _, _ = make_cost_selection(structure)
        return transform_costs(
            structure, selection, decimal.Decimal("1.25"), 3
        )

    def test_ordinary_one_leg_and_straddle_literal_values_and_evidence_counts(self):
        one_leg = self.make_result()
        straddle = self.make_result(("call", "put"))
        self.assertEqual(
            (
                one_leg.record.quoted_mid_premium,
                one_leg.record.estimated_spread_cost,
                one_leg.record.commissions_and_fees,
                one_leg.record.theta_per_day,
                one_leg.record.gamma,
                one_leg.record.underlying_price,
                one_leg.record.total_entry_cost,
            ),
            (120.0, 20.0, 1.25, -10.0, 2.0, 100.0, 141.25),
        )
        self.assertEqual(
            (
                straddle.record.quoted_mid_premium,
                straddle.record.estimated_spread_cost,
                straddle.record.commissions_and_fees,
                straddle.record.theta_per_day,
                straddle.record.gamma,
                straddle.record.underlying_price,
                straddle.record.total_entry_cost,
            ),
            (350.0, 50.0, 1.25, -25.0, 5.0, 100.0, 401.25),
        )
        self.assertEqual(len(one_leg.lineage.inputs), 4)
        self.assertEqual(len(straddle.lineage.inputs), 7)
        integer_valued_structure = OptionStructure(
            (
                OptionLeg(
                    "SPY", "call", 100, EXPIRATION, 1, 100
                ),
            ),
            100000,
            14,
        )
        integer_selection, _, _, _ = make_cost_selection(
            integer_valued_structure
        )
        integer_result = transform_costs(
            integer_valued_structure,
            integer_selection,
            decimal.Decimal("1.25"),
            3,
        )
        integer_identity = transformations._decode_cost_parameters(
            integer_result.lineage.parameters_json
        )["structure_identity"]
        self.assertEqual(
            integer_identity["assumed_portfolio_value_repr"], "100000"
        )
        self.assertEqual(
            integer_identity["legs"][0]["strike_float_repr"], "100"
        )

    def test_complete_v02_document_has_literal_byte_golden_and_exact_schemas(self):
        result = self.make_result()
        expected_compressed = (
            "c-qxiZExE)5dJHMun$RVWwPUJNWOL54+xeGSXTrDO`UBbl&F%F5v}ll-;vb2<XJJ&F8gFyy!U(Vc"
            "*n274++hJyU(8kMg_|SHC(1-Pel$on15{@%Ov4i<EbVzjmZW;6L_Y~II<WRPpAm)g2mPHCOACKkt"
            "I)@z&#KJ8BhZ;S%V==YBS2ZT3%oMd=q(Y&;~zS9-S$m@o~0gbQMJ<*On#;9j9uD68g-OJRw5rBR;"
            "IG7bW$VTv{s<9uqVq;mA13(>6mJx)#=LCRIE+oERk)%zXq;2CyXdF$<1ItfaHn1x<viujR*1L@F~"
            "@wIL%RsEBI0W(S6n3>1lJQ5}bi`dAt&2&6_89lKgu@-zk|3Z8CJ3ujQ1L{7-#VW?&-5l&~7h=JOZ"
            "=^j`y$`MsMyj4v)t85a@WCm!x*DX^~5N}K-HMdn3bQxPX$aQ?QsC@c(n&pP%DM!NsnKeaA*p8-KZ"
            "~;OwM1RSt!qmC{jc1Ot5m%W+R4%N|I!`XjlObPU_B;GZ4L8L*Cec?67D3n=o(T@>(rZxwPnslPb~"
            "2ViZi`Ma#C*?VK<~X<F=(c^a|&&FC{mkq&Sn+a%#nHA$`}MmX#yR}Uj$`O;RD-Afpymq?m=lUb;F"
            "-ct{~hm+_A#4IidZJhhJwbS9@rw_h7U@TvN@l!h?Gyt&wVm?G#O=D#X(n24;^qsFLoY*!ngPK9-R"
            "SW7zN%Vq{Nc%2CM766*^60=CGg6zEK1R#FBokb-N2k?i!BK`MedqSm(+6p%8^L4Zy<i!eCYWt3}L"
            "9Ko07Lb#UloN-0Hkrt2`Cf9JUqcFM-7bPZ30M<GcY`|)$8=w^#*zya}BN0}FVNDpc#FSteXZ43|a"
            "@U)VP`k4>u_;_l+QYK3dFWzneA`z13C3!@-y6Ekd>Bxh5nC_`XZZEQZy*13pEV#Y>Z=R^v+>`HWG"
            "#io+x@31*R8TU;$uTmd5WBlH<b#F=YM16gDaX6C<A!Z8PMMvNT3+k*cMIUTFi$8u)9)U5Yu2LDE4"
            "nOCI;dt#z<EsX&L?@-SRe!Zo|b-K|fB^)P#7AHbNI+wETT>b9Wux`KBL5%fC9f?}I8+GNW5}5hK2"
            "YP4`C7Z70HyhY|R_s9H1_BOt*RQW<c+E3|DH{#fRU*&KA#{;Sx~^MrWU9^O_pRIu)Jh;Iwn^Y5f-"
            "V0PDQFSZ!jWi_I{(#7`10Dj&zd-5vK;AgM#wqPAB$MRD};bp$G5ZoBhpF*RnMbth&XH596x6N5I$"
            ")SG}A1h0$pQ_zqFx#%mIIWxgVn9>H^1BW;|A*_LnQ>mN3Y^Hde;f1%q>f&XH_nC@H(2s`8`9j~)+"
            "D&{W|HF_TW&@dHP8E6!{v|5SLn6VVKHG2d?hsW1@|%WU(Lf47jw^7FSmX{E|+GzWBaiC_l(X)ZMW"
            "NF8*|0bM~2;*FD_aw?0u`{Aw(`G?8&`Xo;*cku3bFZ4?1mqEgfM?_e6bdu_NylwTng)R1}nLAZK>"
            "MAa?HY-KkS{XqSC&kjiYN;IfQ*^OO@s)sqnRU|`l;oMvJ_trrNw#j4zN&zbOEw6IRv2C)hyHNCf}"
            "9`<XP9=aha6$pvW)mlaw&z}-J+Z6cvS2JM3y$CgmTF+`D??BCi+ca?#U^jf|JKbCdJjZ?2JG96~^"
            "&ekD+oA"
        )
        expected = zlib.decompress(
            base64.b85decode(expected_compressed)
        ).decode("utf-8")
        self.assertEqual(result.lineage.parameters_json, expected)
        decoded = transformations._decode_cost_parameters(expected)
        self.assertEqual(len(decoded), 20)
        self.assertEqual(set(decoded), transformations._COST_PARAMETER_KEYS)
        self.assertEqual(
            set(decoded["structure_identity"]),
            {
                "structure_type",
                "underlying",
                "assumed_portfolio_value_repr",
                "expected_holding_days",
                "legs",
            },
        )
        self.assertEqual(
            set(decoded["calculation_values"]),
            transformations._COST_CALCULATION_VALUE_KEYS,
        )
        self.assertEqual(
            set(decoded["normalized_evidence"]),
            transformations._COST_EVIDENCE_KEYS,
        )
        def assert_no_json_float(value):
            self.assertIsNot(type(value), float)
            if type(value) is list:
                for item in value:
                    assert_no_json_float(item)
            elif type(value) is dict:
                for item in value.values():
                    assert_no_json_float(item)
        assert_no_json_float(json.loads(expected))

    def test_exact_total_and_componentwise_stable_float_total_both_hold(self):
        structure = make_structure()
        selection, _, _, _ = make_cost_selection(
            structure, bid=("0",), ask=("0.002",)
        )
        result = transform_costs(
            structure, selection, decimal.Decimal("0.1"), 3
        )
        decoded = transformations._decode_cost_parameters(
            result.lineage.parameters_json
        )
        values = decoded["calculation_values"]
        self.assertEqual(
            values["total_entry_cost_exact"], decimal.Decimal("0.300")
        )
        self.assertEqual(result.record.total_entry_cost, 0.30000000000000004)
        self.assertNotEqual(
            float(values["total_entry_cost_exact"]),
            result.record.total_entry_cost,
        )
        StructureCostsTransformationResult(result.record, result.lineage)

    def test_decisive_forgery_and_complete_public_field_matrix_reject(self):
        result = self.make_result()
        forged = dataclasses.replace(
            result.record, quoted_mid_premium=1120.0
        )
        self.assertEqual(forged.total_entry_cost, 1141.25)
        with self.assertRaises(ValueError):
            StructureCostsTransformationResult(forged, result.lineage)
        changes = {
            "quoted_mid_premium": {"quoted_mid_premium": 1120.0},
            "estimated_spread_cost": {"estimated_spread_cost": 21.0},
            "commissions_and_fees": {"commissions_and_fees": 2.25},
            "theta_per_day": {"theta_per_day": -11.0},
            "gamma": {"gamma": 3.0},
            "underlying_price": {"underlying_price": 101.0},
            "greeks_methodology": {"greeks_methodology": "forged methodology"},
            "repeated_bet_count": {"repeated_bet_count": 4},
            "structure": {
                "structure": dataclasses.replace(
                    result.record.structure,
                    assumed_portfolio_value=200000.0,
                )
            },
            "as_of_date": {
                "as_of_date": result.record.as_of_date
                - datetime.timedelta(days=1)
            },
        }
        for name, change in changes.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                StructureCostsTransformationResult(
                    dataclasses.replace(result.record, **change),
                    result.lineage,
                )

    def test_parameter_only_forgery_matrix_rejects(self):
        result = self.make_result()
        mutations = {
            "quoted midpoint": lambda p: p["calculation_values"].__setitem__(
                "quoted_mid_premium_exact", decimal.Decimal("121.000")
            ),
            "total entry": lambda p: p["calculation_values"].__setitem__(
                "total_entry_cost_exact", decimal.Decimal("142.250")
            ),
            "stable total": lambda p: p["calculation_values"][
                "stable_record_values"
            ].__setitem__("total_entry_cost_repr", "142.25"),
            "structure": lambda p: p["structure_identity"].__setitem__(
                "assumed_portfolio_value_repr", "200000.0"
            ),
            "methodology": lambda p: p["greeks_methodology"].__setitem__(
                "model_name", "Forged model"
            ),
            "repeated bet": lambda p: p.__setitem__("repeated_bet_count", 4),
            "leg correspondence": lambda p: p["leg_correspondence"][0].__setitem__(
                "quantity", 2
            ),
        }
        for name, mutate in mutations.items():
            lineage = mutate_cost_parameters(result, mutate)
            with self.subTest(name=name), self.assertRaises(ValueError):
                StructureCostsTransformationResult(result.record, lineage)

    def test_normalized_evidence_only_forgery_matrix_rejects(self):
        result = self.make_result()
        mutations = {
            "underlying bid": lambda p: p["normalized_evidence"][
                "underlying_quote"
            ].__setitem__("bid_price", decimal.Decimal("98.00")),
            "underlying midpoint": lambda p: p["normalized_evidence"][
                "underlying_quote"
            ].__setitem__("underlying_price_exact", decimal.Decimal("99.500")),
            "option ask": lambda p: p["normalized_evidence"]["option_quotes"][
                0
            ].__setitem__("ask_premium", decimal.Decimal("1.50")),
            "gamma": lambda p: p["normalized_evidence"]["option_greeks"][
                0
            ].__setitem__("gamma", decimal.Decimal("0.030")),
            "theta": lambda p: p["normalized_evidence"]["option_greeks"][
                0
            ].__setitem__("theta", decimal.Decimal("-0.200")),
            "Greeks methodology": lambda p: p["normalized_evidence"][
                "option_greeks"
            ][0].__setitem__("model_name", "Forged model"),
            "contract key": lambda p: p["normalized_evidence"][
                "option_quotes"
            ][0].__setitem__("strike", decimal.Decimal("101.0")),
            "session date": lambda p: p["normalized_evidence"][
                "option_quotes"
            ][0].__setitem__(
                "session_date", SESSION_DATE - datetime.timedelta(days=1)
            ),
            "record ID": lambda p: p["normalized_evidence"]["option_quotes"][
                0
            ].__setitem__("record_id", "forged-record"),
            "normalized at": lambda p: p["normalized_evidence"][
                "option_quotes"
            ][0].__setitem__(
                "normalized_at",
                CALCULATED_AT - datetime.timedelta(days=1),
            ),
            "source IDs": lambda p: p["normalized_evidence"]["option_quotes"][
                0
            ].__setitem__("source_ids", ("forged-source",)),
            "exercise": lambda p: p["normalized_evidence"][
                "contract_references"
            ][0].__setitem__("exercise_style", "European"),
            "settlement": lambda p: p["normalized_evidence"][
                "contract_references"
            ][0].__setitem__("settlement_type", "Cash"),
        }
        for name, mutate in mutations.items():
            lineage = mutate_cost_parameters(result, mutate)
            with self.subTest(name=name), self.assertRaises(ValueError):
                StructureCostsTransformationResult(result.record, lineage)

    def test_lineage_and_quality_forgery_matrix_rejects(self):
        result = self.make_result()
        lineage = result.lineage
        extra = CalculationInputReference(
            "extra-input",
            lineage.inputs[0].normalized_at,
            ("extra-source",),
        )
        changes = {
            "missing": {"inputs": lineage.inputs[:-1]},
            "extra": {"inputs": lineage.inputs + (extra,)},
            "normalized at": {
                "inputs": (
                    dataclasses.replace(
                        lineage.inputs[0],
                        normalized_at=lineage.inputs[0].normalized_at
                        - datetime.timedelta(seconds=1),
                    ),
                ) + lineage.inputs[1:]
            },
            "source IDs": {
                "inputs": (
                    dataclasses.replace(
                        lineage.inputs[0], source_ids=("forged-source",)
                    ),
                ) + lineage.inputs[1:]
            },
            "version": {"methodology_version": "v0.1"},
            "type": {"calculation_type": "forged"},
            "methodology": {"methodology_id": "forged"},
            "missing required flag": {
                "quality_flags": (
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                )
            },
            "prohibited flag": {
                "quality_flags": lineage.quality_flags
                + (CalculationQualityFlag.ANNUALIZED,)
            },
            "undisclosed conditional flag": {
                "quality_flags": lineage.quality_flags
                + (CalculationQualityFlag.INTERPOLATED,)
            },
        }
        for name, change in changes.items():
            forged_lineage = dataclasses.replace(lineage, **change)
            with self.subTest(name=name), self.assertRaises(ValueError):
                StructureCostsTransformationResult(
                    result.record, forged_lineage
                )
        duplicate = dataclasses.replace(
            lineage.inputs[1], record_id=lineage.inputs[0].record_id
        )
        with self.assertRaises(ValueError):
            dataclasses.replace(
                lineage, inputs=(lineage.inputs[0], duplicate) + lineage.inputs[2:]
            )
        with self.assertRaises(ValueError):
            dataclasses.replace(
                lineage,
                calculated_at=min(
                    item.normalized_at for item in lineage.inputs
                ) - datetime.timedelta(microseconds=1),
            )

    def test_strict_decoder_rejects_malformed_and_wrong_schemas(self):
        result = self.make_result()
        serialized = result.lineage.parameters_json
        malformed = (
            serialized.replace(
                '{"$map":[',
                '{"$map":[],"$map":[',
                1,
            ),
            serialized.replace(
                '{"$decimal":"120.000"}', '120.0', 1
            ),
            serialized.replace(
                '{"$decimal":"120.000"}', 'NaN', 1
            ),
            serialized.replace('"$decimal"', '"$unknown"', 1),
            serialized.replace(
                '{"$decimal":"120.000"}',
                '{"$decimal":"+120.000"}',
                1,
            ),
        )
        for value in malformed:
            with self.subTest(value=value[:50]), self.assertRaises(ValueError):
                transformations._decode_cost_parameters(value)
        changes = (
            lambda p: p.pop("structure_identity"),
            lambda p: p.__setitem__("extra", "value"),
            lambda p: p["calculation_values"].pop("gamma_exact"),
            lambda p: p["calculation_values"].__setitem__("extra", "value"),
            lambda p: p.__setitem__("normalized_evidence", ()),
        )
        for mutate in changes:
            parameters = copy.deepcopy(
                transformations._decode_cost_parameters(serialized)
            )
            mutate(parameters)
            forged = market_data.canonicalize_lineage_parameters(parameters)
            if set(parameters) != transformations._COST_PARAMETER_KEYS:
                with self.assertRaises(ValueError):
                    transformations._decode_cost_parameters(forged)
            else:
                lineage = dataclasses.replace(
                    result.lineage, parameters_json=forged
                )
                with self.assertRaises((TypeError, ValueError)):
                    StructureCostsTransformationResult(result.record, lineage)

    def test_complete_decimal_context_is_preserved_on_success_and_failures(self):
        original = decimal.getcontext().copy()
        try:
            context = decimal.getcontext()
            context.prec = 17
            context.rounding = decimal.ROUND_FLOOR
            context.Emin = -99
            context.Emax = 99
            context.capitals = 0
            context.clamp = 1
            context.traps[decimal.Inexact] = False
            context.flags[decimal.DivisionByZero] = True
            before = decimal_context_state()
            result = self.make_result()
            self.assertEqual(decimal_context_state(), before)
            StructureCostsTransformationResult(result.record, result.lineage)
            self.assertEqual(decimal_context_state(), before)
            forged_record = dataclasses.replace(
                result.record, quoted_mid_premium=1120.0
            )
            with self.assertRaises(ValueError):
                StructureCostsTransformationResult(
                    forged_record, result.lineage
                )
            self.assertEqual(decimal_context_state(), before)
            forged_lineage = mutate_cost_parameters(
                result,
                lambda p: p["normalized_evidence"]["option_quotes"][
                    0
                ].__setitem__("ask_premium", decimal.Decimal("1.50")),
            )
            with self.assertRaises(ValueError):
                StructureCostsTransformationResult(
                    result.record, forged_lineage
                )
            self.assertEqual(decimal_context_state(), before)
            forged_parameters = mutate_cost_parameters(
                result,
                lambda p: p["calculation_values"].__setitem__(
                    "gamma_exact", decimal.Decimal("3.000")
                ),
            )
            with self.assertRaises(ValueError):
                StructureCostsTransformationResult(
                    result.record, forged_parameters
                )
            self.assertEqual(decimal_context_state(), before)
            with self.assertRaises(ValueError):
                transformations._decode_cost_parameters(
                    result.lineage.parameters_json.replace(
                        '"$decimal"', '"$unknown"', 1
                    )
                )
            self.assertEqual(decimal_context_state(), before)
            missing_input = dataclasses.replace(
                result.lineage, inputs=result.lineage.inputs[:-1]
            )
            with self.assertRaises(ValueError):
                StructureCostsTransformationResult(
                    result.record, missing_input
                )
            self.assertEqual(decimal_context_state(), before)
        finally:
            decimal.setcontext(original)

    def test_direct_wrapper_does_not_replay_upstream_or_later_transformations(self):
        result = self.make_result()
        forbidden = (
            "_validate_selection_status",
            "transform_structure_costs",
            "transform_tail_pricing",
            "transform_volatility_environment",
        )
        with ExitStack() as stack:
            for name in forbidden:
                stack.enter_context(mock.patch.object(
                    transformations,
                    name,
                    side_effect=AssertionError(f"{name} must not be called"),
                ))
            for name in (
                "select_correction_candidate",
                "assess_market_data_freshness",
                "assess_market_data_snapshot_timing",
                "assess_market_data_relationships",
                "select_market_data_relationship_assessment",
            ):
                stack.enter_context(mock.patch.object(
                    market_data,
                    name,
                    side_effect=AssertionError(f"{name} must not be called"),
                ))
            stack.enter_context(mock.patch.object(
                CalculationLineage,
                "__init__",
                side_effect=AssertionError(
                    "direct verification must not construct lineage"
                ),
            ))
            verified = StructureCostsTransformationResult(
                result.record, result.lineage
            )
        self.assertIs(verified.record, result.record)


class HistoricalRealizedVolatilityPublicContractTests(unittest.TestCase):
    def test_exact_api_enum_fields_signature_and_package_boundary(self):
        self.assertEqual(
            transformations.__all__,
            (
                "StructureLiquidityTransformationResult",
                "transform_structure_liquidity",
                "StructureCostsTransformationResult",
                "transform_structure_costs",
                "HistoricalReturnPriceBasis",
                "HistoricalRealizedVolatility",
                "HistoricalRealizedVolatilityTransformationResult",
                "transform_historical_realized_volatility",
                "VolatilityEnvironmentTransformationResult",
                "transform_volatility_environment",
                "TailPricingTransformationResult",
                "transform_tail_pricing",
                "ScenarioPricingMethodology",
                "ScenarioPricingLegCalculation",
                "NonExpirationScenarioPricingCalculation",
                "ScenarioPricingCalculationResult",
                "ScenarioValuationTransformationResult",
                "transform_scenario_valuation",
                "ExactRational",
                "ExpirationPayoffThresholdSide",
                "ExpirationPayoffThresholdStatus",
                "ExpirationPayoffThreshold",
                "ExpirationPayoffThresholdEvidence",
                "ExpirationPayoffThresholdTransformationResult",
                "transform_expiration_payoff_thresholds",
                "TreasuryPricingRateInput",
                "TreasuryPricingRateTransformationResult",
                "transform_treasury_pricing_rate",
            ),
        )
        self.assertEqual(
            tuple(item.value for item in HistoricalReturnPriceBasis),
            ("raw_close", "adjusted_close"),
        )
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(HistoricalRealizedVolatility)
            ),
            (
                "underlying_key",
                "start_session_date",
                "end_session_date",
                "price_basis",
                "adjustment_methodology",
                "session_dates",
                "prices",
                "log_returns",
                "annualized_realized_volatility",
                "annualization_sessions_per_year",
                "return_formula",
                "variance_estimator",
            ),
        )
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    HistoricalRealizedVolatilityTransformationResult
                )
            ),
            ("record", "lineage"),
        )
        self.assertEqual(
            str(inspect.signature(transform_historical_realized_volatility)),
            (
                "(calculation_id: object, historical_series_assessment: object, "
                "price_basis: object, annualization_sessions_per_year: object, "
                "calculated_at: object) -> "
                "convexity_hunter.market_data_transformations."
                "HistoricalRealizedVolatilityTransformationResult"
            ),
        )
        self.assertEqual(len(market_data.__all__), 64)
        for name in transformations.__all__[4:]:
            self.assertFalse(hasattr(convexity_hunter, name))

    def test_artifact_and_wrapper_are_frozen_and_exact_typed(self):
        assessment, _ = make_historical_assessment()
        result = transform_historical(assessment)
        with self.assertRaises(FrozenInstanceError):
            result.record.prices = ()  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.record = object()  # type: ignore[misc]
        self.assertIs(
            HistoricalRealizedVolatilityTransformationResult(
                result.record, result.lineage
            ).record,
            result.record,
        )
        with self.assertRaises(TypeError):
            HistoricalRealizedVolatilityTransformationResult(
                object(), result.lineage
            )
        with self.assertRaises(TypeError):
            HistoricalRealizedVolatilityTransformationResult(
                result.record, object()
            )


class HistoricalRealizedVolatilityCalculationTests(unittest.TestCase):
    def test_raw_literal_precision_34_returns_sample_volatility_and_lineage(self):
        assessment, bindings = make_historical_assessment()
        result = transform_historical(assessment)
        record = result.record
        self.assertIs(record.underlying_key, assessment.request.underlying_key)
        self.assertEqual(
            record.session_dates,
            (
                datetime.date(2029, 12, 31),
                datetime.date(2030, 1, 1),
                datetime.date(2030, 1, 2),
            ),
        )
        self.assertEqual(
            record.prices,
            tuple(map(decimal.Decimal, ("100", "110", "99"))),
        )
        self.assertEqual(
            record.log_returns,
            (
                decimal.Decimal(
                    "0.09531017980432486004395212328076509"
                ),
                decimal.Decimal(
                    "-0.1053605156578263012275009808393128"
                ),
            ),
        )
        self.assertEqual(record.annualized_realized_volatility, 2.252522969955066)
        oracle_returns = (
            math.log(110.0 / 100.0),
            math.log(99.0 / 110.0),
        )
        oracle_mean = sum(oracle_returns) / 2
        oracle_variance = sum(
            (value - oracle_mean) ** 2 for value in oracle_returns
        )
        self.assertAlmostEqual(
            record.annualized_realized_volatility,
            math.sqrt(oracle_variance) * math.sqrt(252),
            places=14,
        )
        self.assertEqual(record.price_observation_count, 3)
        self.assertEqual(record.return_observation_count, 2)
        self.assertEqual(
            tuple(item.record_id for item in result.lineage.inputs),
            ("hrv-0", "hrv-1", "hrv-2"),
        )
        self.assertEqual(
            tuple(item.source_ids for item in result.lineage.inputs),
            tuple(
                tuple(
                    source.source_id
                    for source in binding.selected_record.metadata.source_references
                )
                for binding in bindings
            ),
        )
        self.assertEqual(
            result.lineage.parameters_json,
            '{"$map":[["adjustment_methodology",null],'
            '["annualization_rule","daily_sample_standard_deviation_times_'
            'square_root_sessions_per_year"],'
            '["annualization_sessions_per_year",252],'
            '["expected_session_dates",{"$list":[{"$date":"2029-12-31"},'
            '{"$date":"2030-01-01"},{"$date":"2030-01-02"}]}],'
            '["price_basis","raw_close"],["price_observation_count",3],'
            '["price_unit","usd_per_underlying_share"],'
            '["return_association_rule","ending_session"],'
            '["return_formula","natural_log_price_ratio"],'
            '["return_observation_count",2],["return_unit","decimal_ratio"],'
            '["underlying",{"$map":[["currency","USD"],'
            '["listing_mic","ARCX"],["security_type","etf"],'
            '["symbol","SPY"]]}],["variance_estimator","sample_variance"],'
            '["volatility_unit","annualized_decimal_ratio"],'
            '["window_end_session_date",{"$date":"2030-01-02"}],'
            '["window_start_session_date",{"$date":"2029-12-31"}]]}'
        )
        self.assertEqual(
            (
                result.lineage.calculation_type,
                result.lineage.methodology_id,
                result.lineage.methodology_version,
            ),
            (
                "historical_realized_volatility",
                "historical-log-return-sample-realized-volatility",
                "v0.1",
            ),
        )
        self.assertEqual(
            result.lineage.quality_flags,
            (
                CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                CalculationQualityFlag.ANNUALIZED,
                CalculationQualityFlag.ASSUMPTION_APPLIED,
            ),
        )

    def test_adjusted_consumes_only_adjusted_and_retains_methodology(self):
        assessment, _ = make_historical_assessment(
            prices=("900", "800", "700"),
            adjusted_prices=("100", "110", "99"),
        )
        result = transform_historical(
            assessment, HistoricalReturnPriceBasis.ADJUSTED_CLOSE
        )
        self.assertEqual(
            result.record.prices,
            tuple(map(decimal.Decimal, ("100", "110", "99"))),
        )
        self.assertEqual(result.record.adjustment_methodology, "total-return-v1")
        self.assertIn(
            CalculationQualityFlag.ADJUSTED_INPUT_USED,
            result.lineage.quality_flags,
        )

    def test_raw_ignores_materially_different_populated_adjusted_prices(self):
        assessment, _ = make_historical_assessment(
            prices=("100", "110", "99"),
            adjusted_prices=("900", "800", "700"),
        )
        result = transform_historical(
            assessment,
            HistoricalReturnPriceBasis.RAW_CLOSE,
            annualization=252,
        )
        self.assertIs(
            result.record.price_basis,
            HistoricalReturnPriceBasis.RAW_CLOSE,
        )
        self.assertEqual(
            result.record.prices,
            (
                decimal.Decimal("100"),
                decimal.Decimal("110"),
                decimal.Decimal("99"),
            ),
        )
        self.assertIsNone(result.record.adjustment_methodology)
        self.assertEqual(
            result.record.log_returns,
            (
                decimal.Decimal(
                    "0.09531017980432486004395212328076509"
                ),
                decimal.Decimal(
                    "-0.1053605156578263012275009808393128"
                ),
            ),
        )
        self.assertEqual(
            result.record.annualized_realized_volatility,
            2.252522969955066,
        )
        self.assertNotIn(
            CalculationQualityFlag.ADJUSTED_INPUT_USED,
            result.lineage.quality_flags,
        )

    def test_constant_prices_and_complete_longer_window(self):
        assessment, _ = make_historical_assessment(("100", "100", "100"))
        result = transform_historical(assessment, annualization=365)
        self.assertEqual(
            result.record.log_returns,
            (decimal.Decimal("0"), decimal.Decimal("0")),
        )
        self.assertEqual(result.record.annualized_realized_volatility, 0.0)
        self.assertEqual(
            math.copysign(1.0, result.record.annualized_realized_volatility),
            1.0,
        )
        longer, _ = make_historical_assessment(
            ("100", "102", "101", "105", "103")
        )
        longer_result = transform_historical(longer)
        self.assertEqual(
            longer_result.record.session_dates,
            longer.request.expected_session_dates,
        )
        self.assertEqual(longer_result.record.price_observation_count, 5)
        self.assertEqual(longer_result.record.return_observation_count, 4)


class HistoricalRealizedVolatilityAcceptanceTests(unittest.TestCase):
    def test_adjustment_only_acceptance_matrix(self):
        mixed, _ = make_historical_assessment(
            adjusted_prices=("99", None, "98")
        )
        mismatch, _ = make_historical_assessment(
            adjusted_prices=("99", "109", "98"),
            methodologies=("method-a", "method-b", "method-a"),
        )
        self.assertEqual(
            mixed.reason_codes,
            (
                MarketDataHistoricalSeriesReasonCode
                .MIXED_ADJUSTED_CLOSE_AVAILABILITY,
            ),
        )
        self.assertEqual(
            mismatch.reason_codes,
            (
                MarketDataHistoricalSeriesReasonCode
                .ADJUSTMENT_METHODOLOGY_MISMATCH,
            ),
        )
        transform_historical(mixed)
        transform_historical(mismatch)
        for assessment in (mixed, mismatch):
            with self.assertRaises(ValueError):
                transform_historical(
                    assessment, HistoricalReturnPriceBasis.ADJUSTED_CLOSE
                )

    def test_each_session_integrity_reason_blocks_both_bases(self):
        complete, bindings = make_historical_assessment(
            adjusted_prices=("99", "109", "98")
        )
        dates = complete.request.expected_session_dates
        scenarios = [
            assess_market_data_historical_series(
                complete.request, bindings[:2]
            )
        ]
        unexpected = build_historical_series_binding(
            "hrv-unexpected",
            session_date=SESSION_DATE - datetime.timedelta(days=3),
        )
        scenarios.append(assess_market_data_historical_series(
            complete.request, bindings + (unexpected,)
        ))
        duplicate = build_historical_series_binding(
            "hrv-duplicate", session_date=dates[0]
        )
        scenarios.append(assess_market_data_historical_series(
            complete.request, bindings + (duplicate,)
        ))
        object.__setattr__(
            bindings[0].selected_record, "is_session_complete", False
        )
        try:
            scenarios.append(complete)
            expected_reasons = (
                MarketDataHistoricalSeriesReasonCode.MISSING_EXPECTED_SESSION,
                MarketDataHistoricalSeriesReasonCode.UNEXPECTED_SESSION,
                MarketDataHistoricalSeriesReasonCode.DUPLICATE_SESSION,
                MarketDataHistoricalSeriesReasonCode.INCOMPLETE_SESSION,
            )
            for assessment, expected_reason in zip(
                scenarios, expected_reasons
            ):
                self.assertIn(expected_reason, assessment.reason_codes)
                for basis in HistoricalReturnPriceBasis:
                    with self.subTest(reason=expected_reason, basis=basis):
                        with self.assertRaises(ValueError):
                            transform_historical(assessment, basis)
        finally:
            object.__setattr__(
                bindings[0].selected_record, "is_session_complete", True
            )

    def test_exact_boundaries_no_fallback_and_incomplete_sources(self):
        assessment, bindings = make_historical_assessment()
        with self.assertRaises(TypeError):
            transform_historical_realized_volatility(
                "id", assessment, "raw_close", 252, CALCULATED_AT
            )
        for annualization in (True, 0, -1):
            with self.subTest(annualization=annualization):
                with self.assertRaises((TypeError, ValueError)):
                    transform_historical(
                        assessment, annualization=annualization
                    )
        with self.assertRaises(TypeError):
            transform_historical_realized_volatility(
                "id",
                object(),
                HistoricalReturnPriceBasis.RAW_CLOSE,
                252,
                CALCULATED_AT,
            )
        with self.assertRaises(ValueError):
            transform_historical(
                assessment, HistoricalReturnPriceBasis.ADJUSTED_CLOSE
            )
        raw_result = transform_historical(assessment)
        self.assertEqual(
            raw_result.record.prices,
            tuple(binding.selected_record.close_price for binding in bindings),
        )
        for kind in ("normalization", "source"):
            changed, changed_bindings = make_historical_assessment()
            bar = changed_bindings[0].selected_record
            original = bar.metadata
            if kind == "normalization":
                replacement = dataclasses.replace(
                    original,
                    quality_flags=(NormalizationQualityFlag.INCOMPLETE,),
                )
            else:
                partial = dataclasses.replace(
                    original.source_references[0],
                    quality_flags=(SourceQualityFlag.PARTIAL,),
                )
                replacement = dataclasses.replace(
                    original, source_references=(partial,)
                )
            object.__setattr__(bar, "metadata", replacement)
            try:
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    transform_historical(changed)
            finally:
                object.__setattr__(bar, "metadata", original)

    def test_conditional_quality_flags_and_discarded_candidate_exclusion(self):
        assessment, bindings = make_historical_assessment(
            adjusted_prices=("99", "109", "98")
        )
        binding = bindings[0]
        bar = binding.selected_record
        original_metadata = bar.metadata
        original_candidates = binding.candidate_records
        original_selection = binding.correction_selection
        source_a = dataclasses.replace(
            original_metadata.source_references[0],
            source_id="hrv-composite-a",
        )
        source_b = dataclasses.replace(
            original_metadata.source_references[0],
            source_id="hrv-composite-b",
            provider_record_id="hrv-composite-record-b",
            provider_request_id="hrv-composite-request-b",
            source_uri="synthetic://hrv/composite/b",
        )
        composite_metadata = build_normalization_metadata(
            (source_a, source_b),
            record_id=original_metadata.record_id,
            effective_observed_at=original_metadata.effective_observed_at,
            normalized_at=original_metadata.normalized_at,
            record_origin=DataOrigin.SYSTEM_COMPOSITE,
            quality_flags=(
                NormalizationQualityFlag.INTERPOLATED,
                NormalizationQualityFlag.COMPOSITE_SOURCE,
            ),
        )
        discarded_metadata = dataclasses.replace(
            original_metadata, record_id="hrv-discarded"
        )
        discarded = dataclasses.replace(bar, metadata=discarded_metadata)
        correction = dataclasses.replace(
            original_selection,
            candidate_record_ids=(
                original_metadata.record_id,
                discarded_metadata.record_id,
            ),
            reason_codes=(
                CorrectionSelectionReasonCode
                .DOMINATING_REVISION_VECTOR_SELECTED,
            ),
        )
        object.__setattr__(bar, "metadata", composite_metadata)
        object.__setattr__(
            binding, "candidate_records", (bar, discarded)
        )
        object.__setattr__(binding, "correction_selection", correction)
        try:
            result = transform_historical(
                assessment, HistoricalReturnPriceBasis.ADJUSTED_CLOSE
            )
            self.assertEqual(
                result.lineage.quality_flags,
                (
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                    CalculationQualityFlag.INTERPOLATED,
                    CalculationQualityFlag.ANNUALIZED,
                    CalculationQualityFlag.ADJUSTED_INPUT_USED,
                    CalculationQualityFlag.CORRECTION_SELECTED,
                    CalculationQualityFlag.COMPOSITE_INPUT_USED,
                    CalculationQualityFlag.ASSUMPTION_APPLIED,
                ),
            )
            self.assertNotIn(
                CalculationQualityFlag.INCOMPLETE_INPUT_USED,
                result.lineage.quality_flags,
            )
            self.assertNotIn(
                "hrv-discarded",
                tuple(item.record_id for item in result.lineage.inputs),
            )
        finally:
            object.__setattr__(bar, "metadata", original_metadata)
            object.__setattr__(
                binding, "candidate_records", original_candidates
            )
            object.__setattr__(
                binding, "correction_selection", original_selection
            )


class HistoricalRealizedVolatilityBoundaryTests(unittest.TestCase):
    def test_wrapper_requires_exact_price_observation_input_count(self):
        result = transform_historical(make_historical_assessment()[0])
        HistoricalRealizedVolatilityTransformationResult(
            result.record, result.lineage
        )
        extra = CalculationInputReference(
            "historical-surplus-input",
            result.lineage.calculated_at,
            ("fixture-source",),
        )
        for inputs in (
            (),
            result.lineage.inputs[:-1],
            result.lineage.inputs + (extra,),
        ):
            with self.subTest(count=len(inputs)):
                lineage = dataclasses.replace(result.lineage, inputs=inputs)
                with self.assertRaisesRegex(ValueError, "input count"):
                    HistoricalRealizedVolatilityTransformationResult(
                        result.record, lineage
                    )

    def test_direct_construction_rejection_and_methodology_taxonomy_matrix(self):
        valid = transform_historical(make_historical_assessment()[0]).record
        dates = valid.session_dates
        value_error_cases = (
            (
                "reordered returns",
                {"log_returns": tuple(reversed(valid.log_returns))},
                "log_returns are inconsistent with prices",
            ),
            (
                "wrong return count",
                {
                    "log_returns": (
                        valid.log_returns
                        + (valid.log_returns[-1],)
                    )
                },
                "log_returns length must be one less than prices",
            ),
            (
                "session and price count mismatch",
                {"session_dates": dates[:2]},
                "session_dates and prices lengths must match",
            ),
            (
                "nonascending sessions",
                {"session_dates": (dates[1], dates[0], dates[2])},
                "session_dates must be strictly ascending",
            ),
            (
                "incorrect start",
                {
                    "start_session_date": (
                        valid.start_session_date
                        - datetime.timedelta(days=1)
                    )
                },
                "window endpoints must match session_dates",
            ),
            (
                "incorrect end",
                {
                    "end_session_date": (
                        valid.end_session_date
                        + datetime.timedelta(days=1)
                    )
                },
                "window endpoints must match session_dates",
            ),
            (
                "raw with methodology",
                {"adjustment_methodology": "total-return-v1"},
                "raw close requires no adjustment methodology",
            ),
            (
                "adjusted with None methodology",
                {
                    "price_basis": HistoricalReturnPriceBasis.ADJUSTED_CLOSE,
                    "adjustment_methodology": None,
                },
                "adjusted close requires an adjustment methodology",
            ),
            (
                "adjusted with empty methodology",
                {
                    "price_basis": HistoricalReturnPriceBasis.ADJUSTED_CLOSE,
                    "adjustment_methodology": "",
                },
                (
                    "adjustment_methodology must be a nonempty canonical "
                    "string"
                ),
            ),
            (
                "adjusted with whitespace methodology",
                {
                    "price_basis": HistoricalReturnPriceBasis.ADJUSTED_CLOSE,
                    "adjustment_methodology": " ",
                },
                (
                    "adjustment_methodology must be a nonempty canonical "
                    "string"
                ),
            ),
            (
                "wrong return formula",
                {"return_formula": "simple_return"},
                "return_formula is inconsistent",
            ),
            (
                "wrong variance estimator",
                {"variance_estimator": "population_variance"},
                "variance_estimator is inconsistent",
            ),
        )
        for label, changes, message in value_error_cases:
            with self.subTest(label=label), self.assertRaisesRegex(
                ValueError, f"^{message}$"
            ):
                dataclasses.replace(valid, **changes)

        type_error_cases = (
            (
                "adjusted non-string methodology",
                {
                    "price_basis": HistoricalReturnPriceBasis.ADJUSTED_CLOSE,
                    "adjustment_methodology": object(),
                },
            ),
            (
                "raw non-string methodology",
                {"adjustment_methodology": object()},
            ),
        )
        for label, changes in type_error_cases:
            with self.subTest(label=label), self.assertRaisesRegex(
                TypeError,
                "^adjustment_methodology must have exact type str$",
            ):
                dataclasses.replace(valid, **changes)

    def test_minimum_and_direct_derived_consistency_and_negative_zero(self):
        assessment, _ = make_historical_assessment(("100", "101"))
        with self.assertRaises(ValueError):
            transform_historical(assessment)
        valid, _ = make_historical_assessment()
        record = transform_historical(valid).record
        with self.assertRaises(ValueError):
            dataclasses.replace(
                record,
                log_returns=(
                    decimal.Decimal("0"),
                    record.log_returns[1],
                ),
            )
        with self.assertRaises(ValueError):
            dataclasses.replace(
                record, annualized_realized_volatility=0.0
            )
        zeros = transform_historical(
            make_historical_assessment(("100", "100", "100"))[0]
        ).record
        normalized = dataclasses.replace(
            zeros,
            log_returns=(
                decimal.Decimal("-0"),
                decimal.Decimal("-0.00"),
            ),
            annualized_realized_volatility=-0.0,
        )
        self.assertEqual(
            normalized.log_returns,
            (decimal.Decimal("0"), decimal.Decimal("0")),
        )
        self.assertEqual(
            math.copysign(1.0, normalized.annualized_realized_volatility),
            1.0,
        )

    def test_context_is_unchanged_and_upstream_functions_not_called(self):
        assessment, _ = make_historical_assessment()
        original = decimal.getcontext().copy()
        context = decimal.getcontext()
        context.prec = 7
        context.rounding = decimal.ROUND_DOWN
        context.traps[decimal.Inexact] = True
        context.flags[decimal.Rounded] = True
        before = context.copy()
        try:
            with mock.patch.object(
                market_data,
                "select_correction_candidate",
                side_effect=AssertionError("selection recomputed"),
            ), mock.patch.object(
                market_data,
                "assess_market_data_freshness",
                side_effect=AssertionError("freshness recomputed"),
            ), mock.patch.object(
                market_data,
                "bind_selected_fresh_market_data",
                side_effect=AssertionError("binding recomputed"),
            ), mock.patch.object(
                market_data,
                "assess_market_data_historical_series",
                side_effect=AssertionError("historical assessment recomputed"),
            ):
                transform_historical(assessment)
            self.assertEqual(context.prec, before.prec)
            self.assertEqual(context.rounding, before.rounding)
            self.assertEqual(context.traps, before.traps)
            self.assertEqual(context.flags, before.flags)
            self.assertEqual(context.Emin, before.Emin)
            self.assertEqual(context.Emax, before.Emax)
            self.assertEqual(context.capitals, before.capitals)
            self.assertEqual(context.clamp, before.clamp)
        finally:
            decimal.setcontext(original)

    def test_lineage_boundaries_and_nonpositive_price(self):
        assessment, bindings = make_historical_assessment()
        with self.assertRaises(ValueError):
            transform_historical_realized_volatility(
                bindings[0].selected_record.metadata.record_id,
                assessment,
                HistoricalReturnPriceBasis.RAW_CLOSE,
                252,
                CALCULATED_AT,
            )
        with self.assertRaises(ValueError):
            transform_historical_realized_volatility(
                "early",
                assessment,
                HistoricalReturnPriceBasis.RAW_CLOSE,
                252,
                datetime.datetime(2000, 1, 1, tzinfo=datetime.timezone.utc),
            )
        bar = bindings[0].selected_record
        original = bar.close_price
        object.__setattr__(bar, "close_price", decimal.Decimal("0"))
        try:
            with self.assertRaises(ValueError):
                transform_historical(assessment)
        finally:
            object.__setattr__(bar, "close_price", original)

class VolatilityEnvironmentTransformationTests(unittest.TestCase):
    def test_exact_public_contract_wrapper_and_signature(self):
        self.assertEqual(
            transformations.__all__,
            (
                "StructureLiquidityTransformationResult",
                "transform_structure_liquidity",
                "StructureCostsTransformationResult",
                "transform_structure_costs",
                "HistoricalReturnPriceBasis",
                "HistoricalRealizedVolatility",
                "HistoricalRealizedVolatilityTransformationResult",
                "transform_historical_realized_volatility",
                "VolatilityEnvironmentTransformationResult",
                "transform_volatility_environment",
                "TailPricingTransformationResult",
                "transform_tail_pricing",
                "ScenarioPricingMethodology",
                "ScenarioPricingLegCalculation",
                "NonExpirationScenarioPricingCalculation",
                "ScenarioPricingCalculationResult",
                "ScenarioValuationTransformationResult",
                "transform_scenario_valuation",
                "ExactRational",
                "ExpirationPayoffThresholdSide",
                "ExpirationPayoffThresholdStatus",
                "ExpirationPayoffThreshold",
                "ExpirationPayoffThresholdEvidence",
                "ExpirationPayoffThresholdTransformationResult",
                "transform_expiration_payoff_thresholds",
                "TreasuryPricingRateInput",
                "TreasuryPricingRateTransformationResult",
                "transform_treasury_pricing_rate",
            ),
        )
        self.assertEqual(len(market_data.__all__), 64)
        self.assertFalse(
            hasattr(convexity_hunter, "VolatilityEnvironmentTransformationResult")
        )
        self.assertFalse(
            hasattr(convexity_hunter, "transform_volatility_environment")
        )
        self.assertEqual(
            tuple(
                field.name for field in dataclasses.fields(
                    VolatilityEnvironmentTransformationResult
                )
            ),
            ("record", "lineage"),
        )
        self.assertEqual(
            str(inspect.signature(transform_volatility_environment)),
            (
                "(calculation_id: object, current_relationship_selection: "
                "object, historical_relationship_selections: object, "
                "historical_expected_session_dates: object, "
                "historical_realized_volatility_result: object, "
                "reference_tenor_days: object, "
                "atm_candidate_universes_complete: object, calculated_at: "
                "object) -> convexity_hunter.market_data_transformations."
                "VolatilityEnvironmentTransformationResult"
            ),
        )
        result = make_volatility_result()
        with self.assertRaises(FrozenInstanceError):
            result.record = result.record
        with self.assertRaises(TypeError):
            VolatilityEnvironmentTransformationResult(
                object(), result.lineage
            )
        with self.assertRaises(TypeError):
            VolatilityEnvironmentTransformationResult(
                result.record, object()
            )

    def test_literal_term_percentile_median_realized_and_lineage(self):
        result = make_volatility_result()
        self.assertEqual(result.record.underlying, "SPY")
        self.assertEqual(result.record.as_of_date, SESSION_DATE)
        self.assertEqual(result.record.reference_tenor_days, 30)
        self.assertEqual(result.record.iv_percentile, 2 / 3)
        self.assertEqual(result.record.historical_median_atm_iv, 0.30)
        self.assertEqual(
            result.record.term_structure,
            (
                transformations.TermVolatilityPoint(30, 0.30),
                transformations.TermVolatilityPoint(60, 0.40),
            ),
        )
        self.assertEqual(result.record.atm_iv, 0.30)
        self.assertEqual(result.record.matched_realized_window_days, 30)
        self.assertEqual(result.record.iv_history_lookback_observations, 3)
        self.assertEqual(len(result.lineage.inputs), 43)
        self.assertEqual(
            result.lineage.calculation_id, "calculation-3c7d"
        )
        self.assertEqual(
            (
                result.lineage.calculation_type,
                result.lineage.methodology_id,
                result.lineage.methodology_version,
            ),
            (
                "volatility_environment",
                "paired-atm-volatility-environment",
                "v0.2",
            ),
        )
        self.assertEqual(
            result.lineage.quality_flags,
            (
                CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                CalculationQualityFlag.ANNUALIZED,
                CalculationQualityFlag.ASSUMPTION_APPLIED,
            ),
        )

    def test_lower_strike_tie_last_ignored_and_order_independent(self):
        expiration_30 = SESSION_DATE + datetime.timedelta(days=30)
        expiration_60 = SESSION_DATE + datetime.timedelta(days=60)
        candidates = (
            (expiration_60, "100", "0.41", "0.39"),
            (expiration_30, "105", "0.81", "0.79"),
            (expiration_30, "95", "0.21", "0.19"),
        )
        first = make_volatility_result(current_candidates=candidates)
        second = make_volatility_result(
            current_candidates=tuple(reversed(candidates))
        )
        self.assertEqual(first.record, second.record)
        self.assertEqual(first.record.atm_iv, 0.20)
        tagged = json.loads(first.lineage.parameters_json)
        serialized = first.lineage.parameters_json
        self.assertIn('"underlying_midpoint"', serialized)
        self.assertIn('"100"', serialized)
        self.assertIn('"selected_strike"', serialized)
        self.assertIsInstance(tagged, dict)

    def test_same_strike_multiplier_pairs_are_ambiguous(self):
        expiration_30 = SESSION_DATE + datetime.timedelta(days=30)
        expiration_60 = SESSION_DATE + datetime.timedelta(days=60)
        candidates = (
            (expiration_30, "100", "0.10", "0.10", 50),
            (expiration_30, "100", "0.90", "0.90", 100),
            (expiration_60, "100", "0.40", "0.40", 100),
        )
        with self.assertRaisesRegex(
            ValueError,
            "ATM candidate selection remains ambiguous",
        ):
            make_volatility_result(current_candidates=candidates)

    def test_percentile_boundaries_ties_and_odd_even_medians(self):
        cases = (
            (("0.30",), 1.0, 0.30),
            (("0.40",), 0.0, 0.40),
            (("0.20", "0.20", "0.40"), 2 / 3, 0.20),
            (("0.10", "0.20", "0.40", "0.50"), 0.5, 0.30),
        )
        for sample, percentile, median in cases:
            with self.subTest(sample=sample):
                result = make_volatility_result(historical_values=sample)
                self.assertEqual(result.record.iv_percentile, percentile)
                self.assertEqual(result.record.historical_median_atm_iv, median)

    def test_percentile_compares_decimal_before_float_conversion(self):
        current_iv = decimal.Decimal("0.30000000000000002")
        historical_iv = decimal.Decimal("0.30000000000000003")
        self.assertLess(current_iv, historical_iv)
        self.assertEqual(float(current_iv), float(historical_iv))
        result = make_volatility_result(
            current_candidates=(
                (
                    SESSION_DATE + datetime.timedelta(days=30),
                    "100",
                    current_iv,
                    current_iv,
                ),
                (
                    SESSION_DATE + datetime.timedelta(days=60),
                    "100",
                    "0.40",
                    "0.40",
                ),
            ),
            historical_values=(historical_iv,),
        )
        self.assertEqual(result.record.iv_percentile, 0.0)

    def test_exact_parameter_keys_and_decimal_tagging(self):
        result = make_volatility_result()
        tree = json.loads(result.lineage.parameters_json)
        self.assertEqual(tuple(tree), ("$map",))
        keys = tuple(item[0] for item in tree["$map"])
        self.assertEqual(
            keys,
            (
                "atm_candidate_universe",
                "atm_selection_rule",
                "call_put_combination_rule",
                "current_observations",
                "float_conversion_rule",
                "historical_expected_session_dates",
                "historical_matched_tenor_rule",
                "historical_observation_count",
                "historical_observations",
                "historical_sample_semantics",
                "iv_methodology",
                "median_formula",
                "normalized_evidence",
                "percentile_formula",
                "realized_volatility_dependency",
                "realized_window_matching_rule",
                "reference_tenor_days",
                "strike_tie_rule",
                "term_tenor_rule",
                "underlying_midpoint_rule",
                "volatility_unit",
            ),
        )
        self.assertIn('{"$decimal":"0.300"}', result.lineage.parameters_json)
        self.assertNotIn('0.3,', result.lineage.parameters_json)
        self.assertIn(
            '"historical_sample_semantics"',
            result.lineage.parameters_json,
        )
        self.assertIn(
            '"caller_declared_observation_sample"',
            result.lineage.parameters_json,
        )

    def test_top_level_type_and_completeness_failures(self):
        current = make_volatility_selection(
            SESSION_DATE,
            (
                (SESSION_DATE + datetime.timedelta(days=30), "100", "0.3", "0.3"),
                (SESSION_DATE + datetime.timedelta(days=60), "100", "0.4", "0.4"),
            ),
            "ve-types-current",
        )
        historical_date = SESSION_DATE - datetime.timedelta(days=3)
        historical = make_volatility_selection(
            historical_date,
            ((
                historical_date + datetime.timedelta(days=30),
                "100",
                "0.2",
                "0.2",
            ),),
            "ve-types-history",
        )
        assessment, _ = make_historical_assessment(
            prices=("100", "102", "101"),
            dates=(
                SESSION_DATE - datetime.timedelta(days=30),
                SESSION_DATE - datetime.timedelta(days=15),
                SESSION_DATE,
            ),
            policy=build_freshness_policy(
                maximum_historical_bar_session_date_gap_days=30
            ),
        )
        dependency = transform_historical(assessment)
        base = (
            "id",
            current,
            (historical,),
            (historical_date,),
            dependency,
            30,
            True,
            CALCULATED_AT,
        )
        scenarios = (
            (2, [historical], TypeError),
            (3, [historical_date], TypeError),
            (5, True, TypeError),
            (6, 1, TypeError),
            (6, False, ValueError),
        )
        for index, value, error in scenarios:
            arguments = list(base)
            arguments[index] = value
            with self.subTest(index=index, value=value):
                with self.assertRaises(error):
                    transform_volatility_environment(*arguments)

    def test_historical_dates_tenor_and_realized_dependency_failures(self):
        arguments = list(make_volatility_result(return_arguments=True))
        expected = transform_volatility_environment(*arguments)
        reversed_arguments = list(arguments)
        reversed_arguments[2] = tuple(reversed(arguments[2]))
        reversed_result = transform_volatility_environment(
            *reversed_arguments
        )
        self.assertEqual(reversed_result.record, expected.record)
        self.assertEqual(
            reversed_result.lineage.parameters_json,
            expected.lineage.parameters_json,
        )
        bad_dates = list(arguments)
        bad_dates[3] = tuple(reversed(arguments[3]))
        with self.assertRaises(ValueError):
            transform_volatility_environment(*bad_dates)
        duplicate_dates = list(arguments)
        duplicate_dates[3] = (
            arguments[3][0],
            arguments[3][0],
            arguments[3][2],
        )
        with self.assertRaises(ValueError):
            transform_volatility_environment(*duplicate_dates)
        tenor_date = arguments[3][0]
        wrong_tenor = make_volatility_selection(
            tenor_date,
            ((
                tenor_date + datetime.timedelta(days=31),
                "100",
                "0.19",
                "0.21",
            ),),
            "ve-wrong-tenor",
        )
        wrong_tenor_arguments = list(arguments)
        wrong_tenor_arguments[2] = (
            wrong_tenor,
        ) + arguments[2][1:]
        with self.assertRaises(ValueError):
            transform_volatility_environment(*wrong_tenor_arguments)

    def test_iv_methodology_compatibility_matrix(self):
        arguments = list(make_volatility_result(return_arguments=True))
        session_date = arguments[3][0]
        cases = (
            {"model_name": "Other model"},
            {"model_version": "other-v2"},
            {"rate_input_description": "Other curve"},
            {"dividend_input_description": "Other dividends"},
            {"unit_convention": "percent_points"},
        )
        for index, overrides in enumerate(cases):
            selection = make_volatility_selection(
                session_date,
                ((
                    session_date + datetime.timedelta(days=30),
                    "100",
                    "0.19",
                    "0.21",
                ),),
                f"ve-method-{index}",
                iv_overrides=overrides,
            )
            changed_arguments = list(arguments)
            changed_arguments[2] = (
                selection,
            ) + arguments[2][1:]
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    transform_volatility_environment(*changed_arguments)

    def test_realized_dependency_integrity_matrix(self):
        arguments = list(make_volatility_result(return_arguments=True))
        dependency = arguments[4]
        lineage = dependency.lineage
        record = dependency.record
        scenarios = (
            (lineage, "calculation_type", "other"),
            (lineage, "methodology_id", "other"),
            (lineage, "methodology_version", "v9"),
            (lineage, "parameters_json", '{"$map":[]}'),
            (lineage, "inputs", lineage.inputs[:-1]),
            (
                lineage,
                "quality_flags",
                tuple(
                    flag for flag in lineage.quality_flags
                    if flag is not CalculationQualityFlag.ANNUALIZED
                ),
            ),
            (lineage, "calculation_id", "calculation-3c7d"),
            (
                record,
                "end_session_date",
                record.end_session_date - datetime.timedelta(days=1),
            ),
            (
                record,
                "start_session_date",
                record.start_session_date + datetime.timedelta(days=1),
            ),
        )
        for target, name, value in scenarios:
            with self.subTest(name=name), changed(target, name, value):
                with self.assertRaises(ValueError):
                    transform_volatility_environment(*arguments)

    def test_decimal_context_is_unchanged_after_success_and_failure(self):
        context = decimal.getcontext()
        original = context.copy()
        context.prec = 7
        context.rounding = decimal.ROUND_DOWN
        context.clear_flags()
        def state():
            return (
                context.prec,
                context.rounding,
                context.Emin,
                context.Emax,
                context.capitals,
                context.clamp,
                tuple(context.traps.items()),
                tuple(context.flags.items()),
            )
        configured = state()
        try:
            make_volatility_result()
            self.assertEqual(state(), configured)
            with self.assertRaises(ValueError):
                make_volatility_result(reference_tenor=31)
            self.assertEqual(state(), configured)
        finally:
            decimal.setcontext(original)

    def test_no_proof_or_dependency_recomputation(self):
        blocked = (
            "select_correction_candidate",
            "assess_market_data_freshness",
            "bind_selected_fresh_market_data",
            "assess_market_data_snapshot_timing",
            "assess_market_data_relationships",
            "select_market_data_relationship_assessment",
            "assess_market_data_historical_series",
        )
        with ExitStack() as stack:
            for name in blocked:
                stack.enter_context(mock.patch.object(
                    transformations,
                    name,
                    side_effect=AssertionError(f"{name} called"),
                    create=True,
                ))
            stack.enter_context(mock.patch.object(
                transformations,
                "transform_historical_realized_volatility",
                side_effect=AssertionError("dependency recalculated"),
            ))
            make_volatility_result()


class TailPricingTransformationTests(unittest.TestCase):
    def test_public_contract_wrapper_and_signature(self):
        self.assertEqual(
            transformations.__all__,
            (
                "StructureLiquidityTransformationResult",
                "transform_structure_liquidity",
                "StructureCostsTransformationResult",
                "transform_structure_costs",
                "HistoricalReturnPriceBasis",
                "HistoricalRealizedVolatility",
                "HistoricalRealizedVolatilityTransformationResult",
                "transform_historical_realized_volatility",
                "VolatilityEnvironmentTransformationResult",
                "transform_volatility_environment",
                "TailPricingTransformationResult",
                "transform_tail_pricing",
                "ScenarioPricingMethodology",
                "ScenarioPricingLegCalculation",
                "NonExpirationScenarioPricingCalculation",
                "ScenarioPricingCalculationResult",
                "ScenarioValuationTransformationResult",
                "transform_scenario_valuation",
                "ExactRational",
                "ExpirationPayoffThresholdSide",
                "ExpirationPayoffThresholdStatus",
                "ExpirationPayoffThreshold",
                "ExpirationPayoffThresholdEvidence",
                "ExpirationPayoffThresholdTransformationResult",
                "transform_expiration_payoff_thresholds",
                "TreasuryPricingRateInput",
                "TreasuryPricingRateTransformationResult",
                "transform_treasury_pricing_rate",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                TailPricingTransformationResult
            )),
            ("records", "lineage"),
        )
        self.assertEqual(
            str(inspect.signature(transform_tail_pricing)),
            (
                "(calculation_id: object, current_relationship_selection: "
                "object, historical_relationship_selections: object, "
                "historical_expected_session_dates: object, "
                "volatility_environment_result: object, "
                "tail_candidate_universes_complete: object, "
                "historical_end_of_day_observations_declared: object, "
                "historical_end_of_day_methodology: object, "
                "delta_methodology: object, calculated_at: object) -> "
                "convexity_hunter.market_data_transformations."
                "TailPricingTransformationResult"
            ),
        )
        self.assertEqual(len(market_data.__all__), 64)
        self.assertFalse(hasattr(convexity_hunter, "transform_tail_pricing"))
        self.assertFalse(
            hasattr(convexity_hunter, "TailPricingTransformationResult")
        )

    def test_ordinary_two_expiration_tail_term_structure(self):
        result = make_tail_result()
        self.assertEqual(len(result.records), 2)
        first, second = result.records
        self.assertEqual(
            tuple(record.expiration for record in result.records),
            (
                SESSION_DATE + datetime.timedelta(days=30),
                SESSION_DATE + datetime.timedelta(days=60),
            ),
        )
        self.assertEqual(
            (
                first.atm_iv,
                first.put_25_delta_iv,
                first.call_25_delta_iv,
                first.put_10_delta_iv,
                first.call_10_delta_iv,
            ),
            (0.30, 0.36, 0.28, 0.42, 0.26),
        )
        self.assertEqual(
            (
                second.atm_iv,
                second.put_25_delta_iv,
                second.call_25_delta_iv,
                second.put_10_delta_iv,
                second.call_10_delta_iv,
            ),
            (0.40, 0.46, 0.38, 0.52, 0.36),
        )
        for record in result.records:
            self.assertAlmostEqual(record.downside_25_delta_skew, 0.06)
            self.assertAlmostEqual(record.upside_25_delta_skew, -0.02)
            self.assertAlmostEqual(record.downside_wing_curvature, 0.06)
            self.assertAlmostEqual(record.upside_wing_curvature, -0.02)
            self.assertEqual(record.skew_percentile, 2 / 3)
            self.assertEqual(record.skew_history_lookback_observations, 3)
            self.assertEqual(
                record.delta_methodology,
                market_data.canonicalize_lineage_parameters(
                    TAIL_DELTA_METHODOLOGY
                ),
            )
        self.assertEqual(len(result.lineage.inputs), 202)

    def test_parameters_identity_flags_and_exact_top_level_keys(self):
        result = make_tail_result(historical_skews=("0.06",))
        tree = json.loads(result.lineage.parameters_json)
        keys = tuple(item[0] for item in tree["$map"])
        self.assertEqual(
            keys,
            (
                "analytics_methodology",
                "atm_dependency",
                "candidate_universe",
                "current_expiration_observations",
                "current_skew_formula",
                "delta_convention",
                "delta_point_selection_rule",
                "delta_tie_rule",
                "float_conversion_rule",
                "historical_eod_semantics",
                "historical_expected_session_dates",
                "historical_matched_tenor_rule",
                "historical_observations_by_tenor",
                "interpolation_rule",
                "normalized_evidence",
                "same_contract_reuse_rule",
                "skew_percentile_formula",
                "skew_term_structure_ordering",
                "tail_output_architecture",
                "target_deltas",
                "volatility_unit",
            ),
        )
        self.assertEqual(result.lineage.calculation_type, "tail_pricing")
        self.assertEqual(
            result.lineage.methodology_id,
            "nearest-observed-delta-wing-tail-relative-pricing",
        )
        self.assertEqual(result.lineage.methodology_version, "v0.2")
        self.assertEqual(
            set(result.lineage.quality_flags),
            {
                CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                CalculationQualityFlag.ANNUALIZED,
                CalculationQualityFlag.ASSUMPTION_APPLIED,
            },
        )
        serialized = result.lineage.parameters_json
        self.assertIn(
            '"current_delta_and_historical_atm_and_delta_candidate_universes"',
            serialized,
        )
        self.assertIn('"nearest_observed_signed_delta"', serialized)
        self.assertIn('"caller_declared_daily_eod_observation_sample"', serialized)
        self.assertIn('{"$decimal":"0.25"}', serialized)
        self.assertNotIn('"incomplete_input_used"', serialized)

    def test_percentile_boundaries_tie_and_decimal_before_float(self):
        cases = (
            (("0.07",), 0.0),
            (("0.06",), 1.0),
            (("0.05",), 1.0),
            (("0.04", "0.06", "0.08"), 2 / 3),
        )
        for history, expected in cases:
            with self.subTest(history=history):
                result = make_tail_result(historical_skews=history)
                self.assertEqual(result.records[0].skew_percentile, expected)
        current = decimal.Decimal("0.06")
        historical = decimal.Decimal("0.060000000000000001")
        self.assertLess(current, historical)
        self.assertEqual(float(current), float(historical))
        result = make_tail_result(historical_skews=(str(historical),))
        self.assertEqual(result.records[0].skew_percentile, 0.0)

    def test_historical_caller_order_invariance(self):
        arguments = list(make_tail_result(
            historical_skews=("0.04",),
            return_arguments=True,
        ))
        expected = transform_tail_pricing(*arguments)
        arguments[2] = tuple(reversed(arguments[2]))
        actual = transform_tail_pricing(*arguments)
        self.assertEqual(actual.records, expected.records)
        self.assertEqual(
            actual.lineage.parameters_json,
            expected.lineage.parameters_json,
        )
        self.assertEqual(actual.lineage.inputs, expected.lineage.inputs)

    def test_delta_tie_same_contract_reuse_and_wrong_sign_rejected(self):
        base = list(make_tail_result(
            historical_skews=("0.04",),
            return_arguments=True,
        ))
        ordinary_30 = list(_tail_candidates(
            SESSION_DATE,
            30,
            "tail-current-30",
            "0.30",
            "0.36",
            "0.28",
            "0.42",
            "0.26",
            ("ve-current-0-call", "ve-current-0-put"),
        ))
        ordinary_60 = _tail_candidates(
            SESSION_DATE,
            60,
            "tail-current-60",
            "0.40",
            "0.46",
            "0.38",
            "0.52",
            "0.36",
            ("ve-current-1-call", "ve-current-1-put"),
        )
        expiration_30 = SESSION_DATE + datetime.timedelta(days=30)

        tied = tuple(ordinary_30) + ((
            "tail-current-30-call25-tie",
            expiration_30,
            "call",
            "106",
            "0.29",
            "0.26",
        ),) + ordinary_60
        base[1] = make_tail_selection(SESSION_DATE, tied, "ve-current")
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            transform_tail_pricing(*base)

        reused = [
            item for item in ordinary_30
            if item[0] != "tail-current-30-call10"
        ]
        reused = [
            (
                item[0], item[1], item[2], item[3], item[4],
                "0.18" if item[0] == "tail-current-30-call25" else item[5],
            )
            for item in reused
        ]
        base[1] = make_tail_selection(
            SESSION_DATE, tuple(reused) + ordinary_60, "ve-current"
        )
        with self.assertRaisesRegex(ValueError, "one economic contract"):
            transform_tail_pricing(*base)

        wrong_sign = [
            (
                item[0], item[1], item[2], item[3], item[4],
                "-0.24" if item[0] == "tail-current-30-call25" else item[5],
            )
            for item in ordinary_30
        ]
        base[1] = make_tail_selection(
            SESSION_DATE, tuple(wrong_sign) + ordinary_60, "ve-current"
        )
        with self.assertRaisesRegex(ValueError, "call delta"):
            transform_tail_pricing(*base)

    def test_historical_matrix_regular_eod_and_dependency_decoder_failures(self):
        arguments = list(make_tail_result(
            historical_skews=("0.04",),
            return_arguments=True,
        ))
        arguments[2] = (arguments[2][0], arguments[2][0])
        with self.assertRaisesRegex(ValueError, "intrinsic keys"):
            transform_tail_pricing(*arguments)

        arguments = list(make_tail_result(
            historical_skews=("0.04",),
            return_arguments=True,
        ))
        lineage = arguments[4].lineage
        malformed = (
            '{"$map":[],"$map":[]}',
            lineage.parameters_json.replace(
                '{"$decimal":"0.30"}',
                '{"$bogus":"0.30"}',
                1,
            ),
            lineage.parameters_json.replace(
                '"historical_observation_count",1',
                '"historical_observation_count",1.0',
                1,
            ),
        )
        for parameters_json in malformed:
            with self.subTest(parameters_json=parameters_json[:40]):
                with changed(lineage, "parameters_json", parameters_json):
                    with self.assertRaises(ValueError):
                        transform_tail_pricing(*arguments)

    def test_current_and_historical_methodology_partitions_are_both_authoritative(self):
        def iv_methodologies(selection):
            self.assertIs(
                selection.status,
                MarketDataSelectionStatus.SELECTED,
            )
            selected = selection.selected_candidate
            self.assertIsNotNone(selected)
            self.assertTrue(selected.is_coherent)
            self.assertTrue(selected.timing_assessment.is_temporally_coherent)
            validated = transformations._validate_tail_selection(selection)
            results = set()
            for _quote, iv, greeks, _reference in validated["candidates"]:
                self.assertEqual(
                    (
                        iv.model_name,
                        iv.model_version,
                        iv.rate_input_description,
                        iv.dividend_input_description,
                    ),
                    (
                        greeks.model_name,
                        greeks.model_version,
                        greeks.rate_input_description,
                        greeks.dividend_input_description,
                    ),
                )
                results.add((
                    iv.model_name,
                    iv.model_version,
                    iv.rate_input_description,
                    iv.dividend_input_description,
                    iv.metadata.unit_convention,
                ))
            return results

        base = list(make_tail_result(
            historical_skews=("0.04",),
            return_arguments=True,
        ))
        current_parts = _tail_selection_fixture_parts(base[1])
        forged_current = make_tail_selection(
            *current_parts,
            analytics_overrides={
                "model_name": "Current-only forged model",
            },
        )
        current_methods = iv_methodologies(forged_current)
        historical_methods = {
            methodology
            for selection in base[2]
            for methodology in iv_methodologies(selection)
        }
        self.assertEqual(len(current_methods), 1)
        self.assertEqual(len(historical_methods), 1)
        self.assertNotEqual(current_methods, historical_methods)
        current_arguments = list(base)
        current_arguments[1] = forged_current
        with self.subTest(partition="current"):
            with self.assertRaises(ValueError):
                transform_tail_pricing(*current_arguments)

        forged_historical = tuple(
            make_tail_selection(
                *_tail_selection_fixture_parts(selection),
                analytics_overrides={
                    "model_name": "Historical-only forged model",
                },
            )
            for selection in base[2]
        )
        current_methods = iv_methodologies(base[1])
        historical_methods = {
            methodology
            for selection in forged_historical
            for methodology in iv_methodologies(selection)
        }
        self.assertEqual(len(current_methods), 1)
        self.assertEqual(len(historical_methods), 1)
        self.assertNotEqual(current_methods, historical_methods)
        historical_arguments = list(base)
        historical_arguments[2] = forged_historical
        with self.subTest(partition="historical"):
            with self.assertRaises(ValueError):
                transform_tail_pricing(*historical_arguments)

    def test_canonical_dependency_fixed_methodology_forgery_matrix(self):
        arguments = list(make_tail_result(
            historical_skews=("0.04",),
            return_arguments=True,
        ))
        dependency = arguments[4]
        decoded = transformations._decode_volatility_parameters(
            dependency.lineage.parameters_json
        )
        mutations = (
            (
                ("atm_candidate_universe", "declared_complete"),
                False,
                ValueError,
            ),
            (
                ("atm_candidate_universe", "scope"),
                "wrong_scope",
                ValueError,
            ),
            (
                ("atm_candidate_universe", "completeness_semantics"),
                "wrong_semantics",
                ValueError,
            ),
            (("atm_selection_rule",), "wrong_rule", ValueError),
            (("strike_tie_rule",), "upper_strike", ValueError),
            (
                ("historical_sample_semantics",),
                "calendar_complete_history",
                ValueError,
            ),
            (("volatility_unit",), "percentage_points", ValueError),
            (("atm_candidate_universe",), ("not", "a", "dict"), TypeError),
            (
                ("atm_candidate_universe", "declared_complete"),
                1,
                TypeError,
            ),
            (("atm_selection_rule",), 1, TypeError),
            (("iv_methodology",), ("not", "a", "dict"), TypeError),
            (
                ("iv_methodology", "unit_convention"),
                1,
                TypeError,
            ),
            (
                ("iv_methodology", "model_name"),
                "Forged canonical model",
                ValueError,
            ),
            (
                ("iv_methodology", "model_version"),
                "forged-v9",
                ValueError,
            ),
            (
                ("iv_methodology", "rate_input_description"),
                "Forged curve",
                ValueError,
            ),
            (
                ("iv_methodology", "dividend_input_description"),
                "Forged dividends",
                ValueError,
            ),
        )
        for path, forged_value, expected_error in mutations:
            forged = copy.deepcopy(decoded)
            target = forged
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = forged_value
            forged_parameters = (
                market_data.canonicalize_lineage_parameters(forged)
            )
            forged_lineage = CalculationLineage(
                calculation_id=dependency.lineage.calculation_id,
                calculation_type=dependency.lineage.calculation_type,
                methodology_id=dependency.lineage.methodology_id,
                methodology_version=dependency.lineage.methodology_version,
                calculated_at=dependency.lineage.calculated_at,
                inputs=dependency.lineage.inputs,
                parameters_json=forged_parameters,
                quality_flags=dependency.lineage.quality_flags,
            )
            forged_dependency = object.__new__(
                VolatilityEnvironmentTransformationResult
            )
            object.__setattr__(
                forged_dependency, "record", dependency.record
            )
            object.__setattr__(
                forged_dependency, "lineage", forged_lineage
            )
            arguments[4] = forged_dependency
            with self.subTest(path=path, forged_value=forged_value):
                if path == (
                    "atm_candidate_universe",
                    "declared_complete",
                ) and forged_value is False:
                    with self.assertRaisesRegex(
                        ValueError,
                        "complete ATM candidate universe|"
                        "incompatible fixed methodology",
                    ):
                        transform_tail_pricing(*arguments)
                elif (
                    path[0] == "iv_methodology"
                    and path[-1] in {
                        "model_name",
                        "model_version",
                        "rate_input_description",
                        "dividend_input_description",
                    }
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "dependency IV methodology|authoritative IV inputs",
                    ):
                        transform_tail_pricing(*arguments)
                else:
                    with self.assertRaises(expected_error):
                        transform_tail_pricing(*arguments)

        forged = copy.deepcopy(decoded)
        forged["iv_methodology"]["model_name"] = (
            "Forged canonical model"
        )
        forged_lineage = CalculationLineage(
            calculation_id=dependency.lineage.calculation_id,
            calculation_type=dependency.lineage.calculation_type,
            methodology_id=dependency.lineage.methodology_id,
            methodology_version=dependency.lineage.methodology_version,
            calculated_at=dependency.lineage.calculated_at,
            inputs=dependency.lineage.inputs,
            parameters_json=(
                market_data.canonicalize_lineage_parameters(forged)
            ),
            quality_flags=dependency.lineage.quality_flags,
        )
        ordering_arguments = list(make_tail_result(
            historical_skews=("0.04",),
            return_arguments=True,
        ))
        forged_dependency = object.__new__(
            VolatilityEnvironmentTransformationResult
        )
        object.__setattr__(
            forged_dependency, "record", dependency.record
        )
        object.__setattr__(
            forged_dependency, "lineage", forged_lineage
        )
        ordering_arguments[4] = forged_dependency
        with mock.patch.object(
            TailPricingSlice,
            "__init__",
            side_effect=AssertionError(
                "TailPricingSlice must not be constructed before "
                "methodology rejection"
            ),
        ) as tail_init:
            with self.assertRaisesRegex(
                ValueError,
                "dependency IV methodology|authoritative IV inputs",
            ):
                transform_tail_pricing(*ordering_arguments)
            tail_init.assert_not_called()

    def test_declarations_and_delta_methodology_exactness(self):
        base = list(make_tail_result(
            historical_skews=("0.04",),
            return_arguments=True,
        ))
        cases = (
            (5, 1, TypeError),
            (5, False, ValueError),
            (6, 1, TypeError),
            (6, False, ValueError),
            (7, f" {TAIL_EOD_METHODOLOGY}", ValueError),
            (8, tuple(TAIL_DELTA_METHODOLOGY.items()), TypeError),
        )
        for index, value, error in cases:
            arguments = list(base)
            arguments[index] = value
            with self.subTest(index=index, value=value):
                with self.assertRaises(error):
                    transform_tail_pricing(*arguments)
        bad_delta = dict(TAIL_DELTA_METHODOLOGY)
        bad_delta["interpolation_methodology"] = "linear"
        base[8] = bad_delta
        with self.assertRaises(ValueError):
            transform_tail_pricing(*base)

    def test_wrapper_rejects_reordering_and_wrong_exact_types(self):
        result = make_tail_result(historical_skews=("0.04",))
        with self.assertRaises(FrozenInstanceError):
            result.records = ()  # type: ignore[misc]
        with self.assertRaises(TypeError):
            TailPricingTransformationResult(
                list(result.records), result.lineage  # type: ignore[arg-type]
            )
        with self.assertRaises(ValueError):
            TailPricingTransformationResult(
                tuple(reversed(result.records)), result.lineage
            )
        class SliceSubclass(TailPricingSlice):
            pass
        with self.assertRaises(TypeError):
            TailPricingTransformationResult(
                (
                    SliceSubclass(**dataclasses.asdict(result.records[0])),
                    result.records[1],
                ),
                result.lineage,
            )

    def test_no_proof_or_dependency_recomputation(self):
        blocked = (
            "select_correction_candidate",
            "assess_market_data_freshness",
            "bind_selected_fresh_market_data",
            "assess_market_data_snapshot_timing",
            "assess_market_data_relationships",
            "select_market_data_relationship_assessment",
            "assess_market_data_historical_series",
            "transform_volatility_environment",
        )
        with ExitStack() as stack:
            for name in blocked:
                stack.enter_context(mock.patch.object(
                    transformations,
                    name,
                    side_effect=AssertionError(f"{name} called"),
                    create=True,
                ))
            make_tail_result(historical_skews=("0.04",))

    def test_decimal_context_is_unchanged_after_success_and_failure(self):
        context = decimal.getcontext()
        original = context.copy()
        context.prec = 7
        context.rounding = decimal.ROUND_DOWN
        context.clear_flags()
        def state():
            return (
                context.prec,
                context.rounding,
                context.Emin,
                context.Emax,
                context.capitals,
                context.clamp,
                tuple(context.traps.items()),
                tuple(context.flags.items()),
            )
        configured = state()
        try:
            make_tail_result(historical_skews=("0.04",))
            self.assertEqual(state(), configured)
            arguments = list(make_tail_result(
                historical_skews=("0.04",),
                return_arguments=True,
            ))
            arguments[5] = False
            with self.assertRaises(ValueError):
                transform_tail_pricing(*arguments)
            self.assertEqual(state(), configured)
        finally:
            decimal.setcontext(original)


def make_scenario_pricing_methodology(**overrides):
    values = {
        "pricing_source_classification": "provider_calculated",
        "producer_name": "Synthetic Scenario Provider",
        "producer_version": "provider-v3",
        "pricing_request_id": "scenario-request-001",
        "pricing_payload_sha256": "b" * 64,
        "producer_calculated_at": (
            CALCULATED_AT + datetime.timedelta(seconds=1)
        ),
        "pricing_model_name": "Synthetic disclosed option model",
        "pricing_model_version": "model-v2",
        "supported_exercise_settlement_pairs": (
            ("american", "physical"),
        ),
        "settlement_treatment": "physical settlement at declared terms",
        "rate_source": "Synthetic USD curve",
        "rate_curve_identity": "synthetic-usd-curve-20300102",
        "rate_effective_date": SESSION_DATE,
        "rate_currency": "USD",
        "rate_remaining_tenor_treatment": "remaining calendar tenor",
        "rate_compounding_conversion": "continuous equivalent",
        "rate_day_count_convention": "actual_365",
        "rate_interpolation": "none",
        "dividend_source": "explicit_zero_dividend_assumption",
        "dividend_treatment": "explicit_zero_dividend_assumption",
        "dividend_coverage_start_date": SESSION_DATE,
        "dividend_coverage_end_date": EXPIRATION,
        "explicit_zero_dividend_assumption": True,
        "volatility_surface_treatment": "actual leg IV parallel shock",
        "skew_treatment": "preserve leg-level base differences",
        "term_treatment": "remaining tenor per scenario",
        "volatility_interpolation": "none",
        "remaining_time_rule": (
            "expiration_minus_valuation_date_calendar_days"
        ),
        "position_scaling_rule": (
            "per_underlying_unit_value_times_quantity_times_contract_multiplier"
        ),
        "numerical_calculation_boundary": (
            "provider option values; local validation only"
        ),
        "limitations": (
            "Self-consistent declarations are not provider-authenticated."
        ),
    }
    values.update(overrides)
    return ScenarioPricingMethodology(**values)


def _pricing_test_underlying_identity(key):
    return {
        "symbol": key.symbol,
        "listing_mic": key.listing_mic,
        "security_type": key.security_type.value,
        "currency": key.currency,
    }


def _pricing_test_contract_identity(key):
    return {
        "underlying_key": _pricing_test_underlying_identity(
            key.underlying_key
        ),
        "expiration": key.expiration,
        "option_type": key.option_type,
        "strike": key.strike,
        "contract_multiplier": key.contract_multiplier,
        "currency": key.currency,
        "deliverable_id": key.deliverable_id,
    }


def _pricing_test_leg_identity(leg):
    return {
        "underlying": leg.underlying,
        "option_type": leg.option_type,
        "strike": decimal.Decimal(str(leg.strike)),
        "expiration": leg.expiration,
        "quantity": leg.quantity,
        "contract_multiplier": leg.contract_multiplier,
    }


def make_scenario_pricing_result(
    option_types=("call",),
    structure=None,
    *,
    deliverable_id="standard-100-share",
    base_iv_values=None,
    iv_record_ids=None,
    reference_record_ids=None,
):
    structure = (
        make_structure(option_types) if structure is None else structure
    )
    contracts = tuple(
        build_option_contract_key(
            option_type=leg.option_type,
            strike=decimal.Decimal(str(leg.strike)),
            contract_multiplier=leg.contract_multiplier,
            expiration=leg.expiration,
            underlying_key=build_underlying_key(
                listing_mic="ARCX",
                currency="USD",
            ),
            currency="USD",
            deliverable_id=deliverable_id,
        )
        for leg in structure.legs
    )
    methodology = make_scenario_pricing_methodology()
    base_ivs = tuple(decimal.Decimal(value) for value in (
        (("0.20",) if len(contracts) == 1 else ("0.20", "0.30"))
        if base_iv_values is None else base_iv_values
    ))
    iv_record_ids = (
        tuple(f"scenario-iv-{index}" for index in range(len(contracts)))
        if iv_record_ids is None else tuple(iv_record_ids)
    )
    reference_record_ids = (
        tuple(
            f"scenario-reference-{index}" for index in range(len(contracts))
        )
        if reference_record_ids is None else tuple(reference_record_ids)
    )
    scenario_specs = (
        (Scenario(0.0, 0.0, "immediate"), ("2.50", "3.50")),
        (Scenario(0.1, 0.2, "days_forward", 7), ("3.00", "4.00")),
        (Scenario(-0.05, -0.1, "holding_horizon"), ("2.00", "3.00")),
    )
    records = []
    for scenario, per_unit_values in scenario_specs:
        valuation_date = (
            SESSION_DATE
            if scenario.valuation_time == "immediate"
            else SESSION_DATE + datetime.timedelta(
                days=(
                    scenario.days_forward
                    if scenario.valuation_time == "days_forward"
                    else structure.expected_holding_days
                )
            )
        )
        shocked_underlying = decimal.Decimal("100") * (
            decimal.Decimal(1)
            + decimal.Decimal(str(scenario.underlying_move))
        )
        calculations = []
        for index, (leg, contract, base_iv) in enumerate(
            zip(structure.legs, contracts, base_ivs)
        ):
            per_unit = decimal.Decimal(per_unit_values[index])
            total = (
                per_unit
                * decimal.Decimal(leg.quantity)
                * decimal.Decimal(leg.contract_multiplier)
            )
            calculations.append(ScenarioPricingLegCalculation(
                leg=leg,
                contract_key=contract,
                base_iv=base_iv,
                shocked_iv=base_iv * (
                    decimal.Decimal(1)
                    + decimal.Decimal(str(scenario.iv_change))
                ),
                remaining_calendar_days=(
                    leg.expiration - valuation_date
                ).days,
                per_underlying_unit_option_value=per_unit,
                total_leg_value=total,
                exercise_style="american",
                settlement_type="physical",
                implied_volatility_record_id=iv_record_ids[index],
                contract_reference_record_id=reference_record_ids[index],
            ))
        records.append(NonExpirationScenarioPricingCalculation(
            structure=structure,
            as_of_date=SESSION_DATE,
            scenario=scenario,
            valuation_date=valuation_date,
            base_underlying_price=decimal.Decimal("100"),
            shocked_underlying_price=shocked_underlying,
            underlying_quote_record_id="scenario-underlying-quote",
            leg_calculations=tuple(calculations),
            estimated_gross_position_value=sum(
                (item.total_leg_value for item in calculations),
                decimal.Decimal(0),
            ),
            pricing_methodology=methodology,
        ))
    records = tuple(records)
    first = records[0]
    common_evidence = {
        "normalized_at": CALCULATED_AT,
        "source_ids": ("source-001",),
        "propagated_quality_flags": (),
    }
    underlying_evidence = {
        **common_evidence,
        "record_id": first.underlying_quote_record_id,
        "underlying_key": _pricing_test_underlying_identity(
            contracts[0].underlying_key
        ),
        "session_date": SESSION_DATE,
        "bid_price": decimal.Decimal("99"),
        "ask_price": decimal.Decimal("101"),
        "midpoint_formula": "bid_price_plus_ask_price_divided_by_2",
        "base_underlying_price": decimal.Decimal("100"),
    }
    iv_evidence = tuple({
        **common_evidence,
        "record_id": item.implied_volatility_record_id,
        "leg": _pricing_test_leg_identity(item.leg),
        "contract_key": _pricing_test_contract_identity(item.contract_key),
        "session_date": SESSION_DATE,
        "implied_volatility": item.base_iv,
        "model_name": "Synthetic IV model",
        "model_version": "iv-v1",
        "rate_input_description": "Synthetic USD curve",
        "dividend_input_description": "Explicit zero dividends",
        "unit_convention": "annualized_decimal_ratio",
    } for item in first.leg_calculations)
    reference_evidence = tuple({
        **common_evidence,
        "record_id": item.contract_reference_record_id,
        "leg": _pricing_test_leg_identity(item.leg),
        "contract_key": _pricing_test_contract_identity(item.contract_key),
        "exercise_style": item.exercise_style,
        "settlement_type": item.settlement_type,
    } for item in first.leg_calculations)
    parameters = transformations._scenario_pricing_expected_fixed_parameters(
        records
    )
    parameters.update({
        "base_underlying_evidence": underlying_evidence,
        "leg_iv_evidence": iv_evidence,
        "contract_reference_evidence": reference_evidence,
    })
    inputs = tuple(
        CalculationInputReference(
            evidence["record_id"],
            evidence["normalized_at"],
            evidence["source_ids"],
        )
        for evidence in (
            (underlying_evidence,) + iv_evidence + reference_evidence
        )
    )
    lineage = CalculationLineage(
        calculation_id="scenario-pricing-calculation-001",
        calculation_type="nonexpiration_scenario_pricing",
        methodology_id=(
            "authoritative-provider-option-scenario-pricing-evidence"
        ),
        methodology_version="v0.1",
        calculated_at=CALCULATED_AT + datetime.timedelta(seconds=2),
        inputs=inputs,
        parameters_json=market_data.canonicalize_lineage_parameters(
            parameters
        ),
        quality_flags=(
            CalculationQualityFlag.ANNUALIZED,
            CalculationQualityFlag.ASSUMPTION_APPLIED,
        ),
    )
    return ScenarioPricingCalculationResult(records, lineage)


def rebuild_scenario_pricing_result(
    result,
    *,
    decoded_parameters=None,
    inputs=None,
    records=None,
):
    parameters_json = result.lineage.parameters_json
    if decoded_parameters is not None:
        parameters_json = market_data.canonicalize_lineage_parameters(
            decoded_parameters
        )
    lineage = dataclasses.replace(
        result.lineage,
        inputs=result.lineage.inputs if inputs is None else inputs,
        parameters_json=parameters_json,
    )
    return ScenarioPricingCalculationResult(
        result.records if records is None else records,
        lineage,
    )


class ScenarioPricingCalculationContractTests(unittest.TestCase):
    def test_exact_public_api_fields_and_root_exclusions(self):
        self.assertEqual(len(transformations.__all__), 28)
        self.assertEqual(transformations.__all__[12:18], (
            "ScenarioPricingMethodology",
            "ScenarioPricingLegCalculation",
            "NonExpirationScenarioPricingCalculation",
            "ScenarioPricingCalculationResult",
            "ScenarioValuationTransformationResult",
            "transform_scenario_valuation",
        ))
        self.assertEqual(len(market_data.__all__), 64)
        for record_type, expected in (
            (ScenarioPricingMethodology, (
                "pricing_source_classification", "producer_name",
                "producer_version", "pricing_request_id",
                "pricing_payload_sha256", "producer_calculated_at",
                "pricing_model_name", "pricing_model_version",
                "supported_exercise_settlement_pairs",
                "settlement_treatment", "rate_source",
                "rate_curve_identity", "rate_effective_date",
                "rate_currency", "rate_remaining_tenor_treatment",
                "rate_compounding_conversion",
                "rate_day_count_convention", "rate_interpolation",
                "dividend_source", "dividend_treatment",
                "dividend_coverage_start_date",
                "dividend_coverage_end_date",
                "explicit_zero_dividend_assumption",
                "volatility_surface_treatment", "skew_treatment",
                "term_treatment", "volatility_interpolation",
                "remaining_time_rule", "position_scaling_rule",
                "numerical_calculation_boundary", "limitations",
            )),
            (ScenarioPricingLegCalculation, (
                "leg", "contract_key", "base_iv", "shocked_iv",
                "remaining_calendar_days",
                "per_underlying_unit_option_value", "total_leg_value",
                "exercise_style", "settlement_type",
                "implied_volatility_record_id",
                "contract_reference_record_id",
            )),
            (NonExpirationScenarioPricingCalculation, (
                "structure", "as_of_date", "scenario", "valuation_date",
                "base_underlying_price", "shocked_underlying_price",
                "underlying_quote_record_id", "leg_calculations",
                "estimated_gross_position_value",
                "pricing_methodology",
            )),
            (ScenarioPricingCalculationResult, ("records", "lineage")),
        ):
            self.assertEqual(
                tuple(field.name for field in dataclasses.fields(record_type)),
                expected,
            )
        for name in transformations.__all__[14:18]:
            self.assertFalse(hasattr(convexity_hunter, name))
        public_functions = tuple(
            name for name in transformations.__all__
            if inspect.isfunction(getattr(transformations, name))
        )
        self.assertEqual(public_functions, (
            "transform_structure_liquidity",
            "transform_structure_costs",
            "transform_historical_realized_volatility",
            "transform_volatility_environment",
            "transform_tail_pricing",
            "transform_scenario_valuation",
            "transform_expiration_payoff_thresholds",
            "transform_treasury_pricing_rate",
        ))

    def test_call_put_and_straddle_direct_construction(self):
        call = make_scenario_pricing_result(("call",))
        put = make_scenario_pricing_result(("put",))
        straddle = make_scenario_pricing_result(("call", "put"))
        self.assertEqual(
            tuple(record.estimated_gross_position_value for record in call.records),
            (
                decimal.Decimal("250.00"),
                decimal.Decimal("300.00"),
                decimal.Decimal("200.00"),
            ),
        )
        self.assertEqual(
            tuple(record.estimated_gross_position_value for record in put.records),
            (
                decimal.Decimal("250.00"),
                decimal.Decimal("300.00"),
                decimal.Decimal("200.00"),
            ),
        )
        self.assertEqual(
            tuple(
                record.estimated_gross_position_value
                for record in straddle.records
            ),
            (
                decimal.Decimal("600.00"),
                decimal.Decimal("700.00"),
                decimal.Decimal("500.00"),
            ),
        )
        self.assertEqual(
            straddle.records[1].leg_calculations[0].shocked_iv,
            decimal.Decimal("0.240"),
        )
        self.assertEqual(
            straddle.records[1].leg_calculations[1].shocked_iv,
            decimal.Decimal("0.360"),
        )
        self.assertEqual(
            tuple(record.valuation_date for record in call.records),
            (
                SESSION_DATE,
                SESSION_DATE + datetime.timedelta(days=7),
                SESSION_DATE + datetime.timedelta(days=14),
            ),
        )

    def test_methodology_and_nonexpiration_boundaries(self):
        with self.assertRaises(ValueError):
            make_scenario_pricing_methodology(
                pricing_source_classification="internal_model"
            )
        with self.assertRaises(ValueError):
            make_scenario_pricing_methodology(
                pricing_payload_sha256="A" * 64
            )
        with self.assertRaises(TypeError):
            make_scenario_pricing_methodology(
                producer_calculated_at=SESSION_DATE
            )
        result = make_scenario_pricing_result()
        record = result.records[0]
        with self.assertRaisesRegex(ValueError, "expiration"):
            NonExpirationScenarioPricingCalculation(
                **{
                    **dataclasses.asdict(record),
                    "structure": record.structure,
                    "scenario": Scenario(0.0, 0.0, "expiration"),
                    "valuation_date": EXPIRATION,
                    "leg_calculations": record.leg_calculations,
                    "pricing_methodology": record.pricing_methodology,
                }
            )

    def test_lineage_schema_flags_and_forgery_rejection(self):
        result = make_scenario_pricing_result(("call", "put"))
        decoded = transformations._decode_scenario_pricing_parameters(
            result.lineage.parameters_json
        )
        self.assertEqual(
            set(decoded),
            transformations._SCENARIO_PRICING_PARAMETER_KEYS,
        )
        self.assertEqual(len(decoded), 23)
        self.assertIn('"$decimal"', result.lineage.parameters_json)
        forged = copy.deepcopy(decoded)
        forged["producer_provenance"]["pricing_request_id"] = "forged"
        forged_lineage = dataclasses.replace(
            result.lineage,
            parameters_json=market_data.canonicalize_lineage_parameters(forged),
        )
        with self.assertRaises(ValueError):
            ScenarioPricingCalculationResult(
                result.records, forged_lineage
            )
        forged_flags = dataclasses.replace(
                result.lineage,
                quality_flags=(
                    CalculationQualityFlag.ANNUALIZED,
                    CalculationQualityFlag.ASSUMPTION_APPLIED,
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                ),
            )
        with self.assertRaises(ValueError):
            ScenarioPricingCalculationResult(
                result.records, forged_flags
            )

    def test_exact_types_order_and_decimal_context(self):
        result = make_scenario_pricing_result()
        with self.assertRaises(TypeError):
            ScenarioPricingCalculationResult(
                list(result.records), result.lineage
            )
        with self.assertRaises(ValueError):
            ScenarioPricingCalculationResult(
                tuple(reversed(result.records)), result.lineage
            )
        context = decimal.getcontext()
        original = context.copy()
        context.prec = 7
        context.rounding = decimal.ROUND_DOWN
        context.clear_flags()
        configured = (
            context.prec, context.rounding, context.Emin, context.Emax,
            context.capitals, context.clamp, tuple(context.traps.items()),
            tuple(context.flags.items()),
        )
        try:
            make_scenario_pricing_result()
            self.assertEqual(configured, (
                context.prec, context.rounding, context.Emin, context.Emax,
                context.capitals, context.clamp,
                tuple(context.traps.items()), tuple(context.flags.items()),
            ))
        finally:
            decimal.setcontext(original)

    def test_complete_canonical_parameters_literal_golden(self):
        expected_compressed = "c-rk*OK;pZ5dJHI(BsO`?q;3XJr!vVy%a&+7HtEApe61uYl>7zO7SMhf6wqC>bVaiiIV{9lUL$AIP=ZN;pjvBQ-RC)`puj84l9Bxo)gJ-ly4BJX-;@X;@O9G5mxu8l+-`XNk$9I;_G;x&f|}_v$2-x#i?IR^T`EQSMGg5^HNZ*(OSr&VmO|)BB*4QLct%DQ{!)r?sjMq8(|JIn9=v}3~OfqYocjEz``P3rb#+a(#4<i)%7yHPM=+*_U}Jux|E{C8xY9R+X~d^9a=NIQC1P7N<%nq?Mg{9A#+4?@J?lfV@XBQMj&}x2~Dg=iYP?|N5+rfP|q1>TZu}-j%ePq<{u|1gxXo|g!!KAdU?t!DIt0AF#hZ2S8Ls<F-r@Y!P8&<c=?Za3f7wK>0Jq4#YC^&^IdT#7(BRn{cn5=2A$0evkWq!%|2?(D$?`u!+tm&1Ofrq3LET=6iT5|DB7ABNG(?BMI*?_<^(rrJy4NeEWCnDa4m7B#}RB^0Pr*|86`5Ffx}j49NnBSS`&%y81YchnCDpL3CJXBi>1Q=c_^v0;Tt1hnao$tD^c3r`;<V;nahcm^nN0U7k)F}0uYdaljHVTn};&w8vFunkBddeWmDKhc41j@s*$%i3AT%sS13t=DK|3U5;3`jLf!%Ho-eFFTan!ZfG4r$RcN6xLjkk<a1D++9`J0^i?6Y1`0yQIE1ub~(i&x3%r|6Yd5nuf)O(j1r(9)QmYl`3C`e9CmVEG<O&+i73DcGc(dl&Ax^s{)Z$HkSgm#wcnRd>!^F*|>3{cxkJD00twDasF+6lOR1noROOgoFyXlK5Mc6zoR$vpEXVxFrfWS+&DdCtu9bPdl@=2^Ws!aVaAr!_q37jAfxz$u5R2iB#lJ>;_$EH`3XA?bU_+vE7>Y8ArwRrzOr*$G=fpd@QzKu`LY_c2MFN#HX{fIJYHQD9o7cg(EE1pzo<9{-3G@l8i10klc#Godvj1>w5cZn@nlh^<G%DZ`PbGTcyz=cpihD{{farVo&?AQJ}18>k%kF<o_SHpWtbd#R5Oc7mMq*1+rm(2xNmzb8_l@E$8w6*lE@PfkmMwF%A1qQ_Uww5-Sw*4Q}NCPGzZDWo2-NfY~k{cfs!2G&eq4RPWSC_DU;m8};pI9Oo}EwktAIRapC0VU~s8|2O&)S%dtz9r#CgKu;!Z!2Wf*@>VRL8ca<%-f@)>7D?BlBiPfLj-y5qQ3SVaeQW-#14mvmlh`CIjV&jQCcdR)Jkiw?nh(lL*&?$oB=t&{@en5T?7X%rM#?w`-#dV^^_XF^0XTn+Krl}Y7a>F(#($r&q4qk5XZKYzS(iTg)SnCe)~JJZ{l{1KMu^0u}<pw(|)mmMUz=;JqD;mfQH&(_b`Wi`OiAkpP1bHg*mT$V4CC2X1Y`Jw4mB1UzvRnwoX8U0u!Jl0wIPSHdF)!8F8T_h?ha7OmGF822+`d-G$wfsI-X=mf4nSlIcp4Ar1i|Rc5htCn{6$roxOWxHlP3YB-Oj$g2#lpE-pH+C2p+Ux=L8?kN)%j+QNQbcc1e?FQbX^>@Kv1(4tPJiG?>2OPd^ze{x_m9eRzlQ4A>!vkXU>#Ag7q#Y(N3W~w7f^RRTuFbYN@eM~)G5+UNWja(^_x3iRymIFkL)|ZHosc$Zid^MJu0i@aVgdxrFPdAKNN~36o18AjoT`ioMe;^tTbg~zwnXjkq+X2r^G-Y3oI_FjKEe(3z?deoaQvt4$-BNN^kW2SEdshr7^w-1O#cO*uKnTf1dWQGV3<&Vb|8-kau$Udg1tz$eE{VkUJ4Hp*MJV!s7kIelxWum<P>VpxMpaqgfe0b9JH-yz)%Bp!}7Wz^d`mO?I;xuhNIU$$#G9xn}ATO^>Sp>yaP4EFZE3>OT2>?9J=`}UaT%n-~5?>J)}tT7SO0iO`Cn{IIXkVGaw)W7;|k1r@y^W10?T9qJ4hS$*}623?0hfSA+ItCW_Kjot<}u>xwxep|UBjM5Q9w7Ol-JOvgd#M1RpduSo|G&_?*QCzZ+*`#LeMr}K2tisg6*<|{rt0W1p9@^aNKB~TriCE8;rk3aDC6o7r(4*P5=?J2Wn5a{Zyl@9mW$rJQ;FitdiYiPFZTA&@{aDVI1z6PVm?vN0U!ZqmgXWnFw`^~<UelK56zOy-MZ^(=6aco=2j+fBB_uHf4EOcNA8X<l^-1%(icNiqh+C8_!g^3M#wR^*7yX4^(XA9TfH$Z?OhueZ{e4vk-J|nO~VturZ?bHT1(9B}if<X+Y#_Ds+eGO2dz<?z{sPWd#@aNC`{X!kPAAXNl4L_2%-QsD^wDI@;FyTIIuyD0@GcM5BuJw&+FDyj?o9Y_1^D`4nqtSL@;ZcDfXi*i&&7CU4ri-yReZaSlc_*P0Z~g^2oad%_ZE)2A`gl4v{8({hRyHj5@uvu@T^*>44v@Wx&g%&>@5T{Mi2p5A<H_P0sh&jkgpE!?cI(X5<|q3o3@r"
        expected = zlib.decompress(
            base64.b85decode(expected_compressed)
        ).decode()
        self.assertEqual(
            make_scenario_pricing_result().lineage.parameters_json,
            expected,
        )

    def test_contract_mapping_actual_iv_and_date_boundaries(self):
        result = make_scenario_pricing_result(("call", "put"))
        call, put = result.records[0].leg_calculations
        self.assertEqual(call.base_iv, decimal.Decimal("0.20"))
        self.assertEqual(put.base_iv, decimal.Decimal("0.30"))
        self.assertEqual(call.contract_key.underlying_key.listing_mic, "ARCX")
        self.assertEqual(call.contract_key.currency, "USD")
        self.assertEqual(
            call.contract_key.deliverable_id, "standard-100-share"
        )
        self.assertEqual(
            call.contract_key.strike,
            decimal.Decimal(str(call.leg.strike)),
        )
        immediate = result.records[0]
        with self.assertRaises(ValueError):
            dataclasses.replace(
                immediate,
                scenario=Scenario(0.0, 0.0, "days_forward", 72),
                valuation_date=EXPIRATION,
            )
        horizon_structure = dataclasses.replace(
            immediate.structure,
            expected_holding_days=72,
        )
        with self.assertRaises(ValueError):
            dataclasses.replace(
                immediate,
                structure=horizon_structure,
                scenario=Scenario(0.0, 0.0, "holding_horizon"),
                valuation_date=EXPIRATION,
            )

    def test_canonical_decoder_and_evidence_lineage_failures(self):
        result = make_scenario_pricing_result()
        lineage = result.lineage
        malformed = (
            lineage.parameters_json
            .replace('"maximum_leg_count",2', '"maximum_leg_count",2.0', 1)
        )
        with self.assertRaises(ValueError):
            dataclasses.replace(lineage, parameters_json=malformed)
        unknown = lineage.parameters_json.replace(
            '"$decimal"', '"$unknown"', 1
        )
        with self.assertRaises(ValueError):
            dataclasses.replace(lineage, parameters_json=unknown)
        decoded = transformations._decode_scenario_pricing_parameters(
            lineage.parameters_json
        )
        missing = copy.deepcopy(decoded)
        missing.pop("limitations")
        with self.assertRaises(ValueError):
            forged = dataclasses.replace(
                lineage,
                parameters_json=market_data.canonicalize_lineage_parameters(
                    missing
                ),
            )
            ScenarioPricingCalculationResult(result.records, forged)
        evidence_mismatch = copy.deepcopy(decoded)
        evidence_mismatch["base_underlying_evidence"]["normalized_at"] = (
            CALCULATED_AT - datetime.timedelta(seconds=1)
        )
        forged = dataclasses.replace(
            lineage,
            parameters_json=market_data.canonicalize_lineage_parameters(
                evidence_mismatch
            ),
        )
        with self.assertRaises(ValueError):
            ScenarioPricingCalculationResult(result.records, forged)
        wrong_type = copy.deepcopy(decoded)
        wrong_type["base_underlying_evidence"][
            "base_underlying_price"
        ] = 100
        forged = dataclasses.replace(
            lineage,
            parameters_json=market_data.canonicalize_lineage_parameters(
                wrong_type
            ),
        )
        with self.assertRaises(TypeError):
            ScenarioPricingCalculationResult(result.records, forged)

    def test_conditional_quality_flags_and_interpolation(self):
        result = make_scenario_pricing_result()
        decoded = transformations._decode_scenario_pricing_parameters(
            result.lineage.parameters_json
        )
        decoded["base_underlying_evidence"][
            "propagated_quality_flags"
        ] = ("correction_selected",)
        lineage = dataclasses.replace(
            result.lineage,
            parameters_json=market_data.canonicalize_lineage_parameters(
                decoded
            ),
            quality_flags=(
                CalculationQualityFlag.ANNUALIZED,
                CalculationQualityFlag.CORRECTION_SELECTED,
                CalculationQualityFlag.ASSUMPTION_APPLIED,
            ),
        )
        flagged = ScenarioPricingCalculationResult(result.records, lineage)
        self.assertIn(
            CalculationQualityFlag.CORRECTION_SELECTED,
            flagged.lineage.quality_flags,
        )
        methodology = dataclasses.replace(
            result.records[0].pricing_methodology,
            rate_interpolation="linear disclosed interpolation",
        )
        records = tuple(
            dataclasses.replace(record, pricing_methodology=methodology)
            for record in result.records
        )
        parameters = (
            transformations._scenario_pricing_expected_fixed_parameters(
                records
            )
        )
        parameters.update({
            "base_underlying_evidence": decoded["base_underlying_evidence"],
            "leg_iv_evidence": decoded["leg_iv_evidence"],
            "contract_reference_evidence": (
                decoded["contract_reference_evidence"]
            ),
        })
        lineage = dataclasses.replace(
            result.lineage,
            parameters_json=market_data.canonicalize_lineage_parameters(
                parameters
            ),
            quality_flags=(
                CalculationQualityFlag.INTERPOLATED,
                CalculationQualityFlag.ANNUALIZED,
                CalculationQualityFlag.CORRECTION_SELECTED,
                CalculationQualityFlag.ASSUMPTION_APPLIED,
            ),
        )
        interpolated = ScenarioPricingCalculationResult(records, lineage)
        self.assertIn(
            CalculationQualityFlag.INTERPOLATED,
            interpolated.lineage.quality_flags,
        )

    def test_wrong_exact_public_types_and_immutability(self):
        result = make_scenario_pricing_result()
        record = result.records[0]
        with self.assertRaises(FrozenInstanceError):
            record.valuation_date = SESSION_DATE  # type: ignore[misc]
        with self.assertRaises(TypeError):
            make_scenario_pricing_methodology(
                supported_exercise_settlement_pairs=[
                    ("american", "physical")
                ]
            )
        with self.assertRaises(TypeError):
            dataclasses.replace(
                record,
                leg_calculations=list(record.leg_calculations),
            )
        with self.assertRaises(TypeError):
            dataclasses.replace(
                record.leg_calculations[0],
                base_iv=0.20,
            )
        with self.assertRaises(ValueError):
            dataclasses.replace(
                record.leg_calculations[0],
                total_leg_value=decimal.Decimal("249.99"),
            )
        class UnderlyingKeySubclass(market_data.UnderlyingKey):
            pass
        key = record.leg_calculations[0].contract_key.underlying_key
        subclass_key = UnderlyingKeySubclass(
            key.symbol,
            key.listing_mic,
            key.security_type,
            key.currency,
        )
        contract = dataclasses.replace(
            record.leg_calculations[0].contract_key,
            underlying_key=subclass_key,
        )
        with self.assertRaises(TypeError):
            dataclasses.replace(
                record.leg_calculations[0],
                contract_key=contract,
            )

    def test_review_mutation_matrix_evidence_and_lineage(self):
        one_leg = make_scenario_pricing_result()
        calculation = one_leg.records[0].leg_calculations[0]
        near_contract = dataclasses.replace(
            calculation.contract_key,
            strike=decimal.Decimal("100.00000000000001"),
        )
        with self.subTest(mutation="near_strike_substitution"):
            with self.assertRaises(ValueError):
                dataclasses.replace(
                    calculation,
                    contract_key=near_contract,
                )

        straddle = make_scenario_pricing_result(("call", "put"))
        base_parameters = (
            transformations._decode_scenario_pricing_parameters(
                straddle.lineage.parameters_json
            )
        )
        evidence_mutations = (
            (
                "iv_value_substitution",
                lambda parameters: parameters["leg_iv_evidence"][0].__setitem__(
                    "implied_volatility", decimal.Decimal("0.20000000000001")
                ),
            ),
            (
                "cross_leg_iv_record_substitution",
                lambda parameters: parameters["leg_iv_evidence"][0].__setitem__(
                    "record_id",
                    parameters["leg_iv_evidence"][1]["record_id"],
                ),
            ),
            (
                "current_session_iv_mismatch",
                lambda parameters: parameters["leg_iv_evidence"][0].__setitem__(
                    "session_date",
                    SESSION_DATE - datetime.timedelta(days=1),
                ),
            ),
        )
        for name, mutate in evidence_mutations:
            parameters = copy.deepcopy(base_parameters)
            mutate(parameters)
            with self.subTest(mutation=name):
                with self.assertRaises(ValueError):
                    rebuild_scenario_pricing_result(
                        straddle,
                        decoded_parameters=parameters,
                    )

        missing_inputs = straddle.lineage.inputs[:-1]
        extra_inputs = straddle.lineage.inputs + (
            CalculationInputReference(
                "undisclosed-extra-input",
                CALCULATED_AT,
                ("extra-source-001",),
            ),
        )
        first_input = straddle.lineage.inputs[0]
        mismatched_source_inputs = (
            dataclasses.replace(
                first_input,
                source_ids=("different-source-001",),
            ),
        ) + straddle.lineage.inputs[1:]
        lineage_mutations = (
            ("missing_lineage_input", missing_inputs),
            ("extra_lineage_input", extra_inputs),
            ("lineage_source_id_mismatch", mismatched_source_inputs),
        )
        for name, inputs in lineage_mutations:
            with self.subTest(mutation=name):
                with self.assertRaises(ValueError):
                    rebuild_scenario_pricing_result(
                        straddle,
                        inputs=inputs,
                    )

    def test_review_mutation_matrix_methodology_and_batch(self):
        one_leg = make_scenario_pricing_result()
        record = one_leg.records[0]
        methodology_cases = (
            (
                "rate_effective_date",
                {
                    "rate_effective_date": (
                        SESSION_DATE - datetime.timedelta(days=1)
                    )
                },
            ),
            (
                "dividend_coverage_end",
                {
                    "dividend_coverage_end_date": (
                        EXPIRATION - datetime.timedelta(days=1)
                    )
                },
            ),
            (
                "dividend_coverage_start",
                {
                    "dividend_coverage_start_date": (
                        SESSION_DATE + datetime.timedelta(days=1)
                    )
                },
            ),
        )
        for name, changes in methodology_cases:
            methodology = dataclasses.replace(
                record.pricing_methodology,
                **changes,
            )
            with self.subTest(mutation=name):
                with self.assertRaises(ValueError):
                    dataclasses.replace(
                        record,
                        pricing_methodology=methodology,
                    )

        zero_dividend_cases = (
            {
                "explicit_zero_dividend_assumption": True,
                "dividend_source": "provider forecast",
            },
            {
                "explicit_zero_dividend_assumption": True,
                "dividend_treatment": "provider forecast",
            },
            {
                "explicit_zero_dividend_assumption": False,
                "dividend_source": "explicit_zero_dividend_assumption",
                "dividend_treatment": "provider forecast",
            },
            {
                "explicit_zero_dividend_assumption": False,
                "dividend_source": "provider forecast",
                "dividend_treatment": "explicit_zero_dividend_assumption",
            },
        )
        for changes in zero_dividend_cases:
            with self.subTest(mutation="zero_dividend", changes=changes):
                with self.assertRaises(ValueError):
                    dataclasses.replace(
                        record.pricing_methodology,
                        **changes,
                    )

        duplicate_records = (record, record)
        original_parameters = (
            transformations._decode_scenario_pricing_parameters(
                one_leg.lineage.parameters_json
            )
        )
        duplicate_parameters = (
            transformations._scenario_pricing_expected_fixed_parameters(
                duplicate_records
            )
        )
        duplicate_parameters.update({
            "base_underlying_evidence": (
                original_parameters["base_underlying_evidence"]
            ),
            "leg_iv_evidence": original_parameters["leg_iv_evidence"],
            "contract_reference_evidence": (
                original_parameters["contract_reference_evidence"]
            ),
        })
        duplicate_lineage = dataclasses.replace(
            one_leg.lineage,
            parameters_json=market_data.canonicalize_lineage_parameters(
                duplicate_parameters
            ),
        )
        with self.subTest(mutation="duplicate_scenario_identity"):
            with self.assertRaises(ValueError):
                ScenarioPricingCalculationResult(
                    duplicate_records,
                    duplicate_lineage,
                )

        straddle = make_scenario_pricing_result(("call", "put"))
        straddle_record = straddle.records[0]
        with self.subTest(mutation="aggregate_gross_value"):
            with self.assertRaises(ValueError):
                dataclasses.replace(
                    straddle_record,
                    estimated_gross_position_value=decimal.Decimal("599.99"),
                )

        unsupported_leg = dataclasses.replace(
            record.leg_calculations[0],
            exercise_style="european",
            settlement_type="cash",
        )
        with self.subTest(mutation="unsupported_exercise_settlement"):
            with self.assertRaises(ValueError):
                dataclasses.replace(
                    record,
                    leg_calculations=(unsupported_leg,),
                )

    def test_review_quantity_scaling(self):
        source = make_scenario_pricing_result().records[0].leg_calculations[0]
        quantity_two_leg = dataclasses.replace(source.leg, quantity=2)
        valid = ScenarioPricingLegCalculation(
            leg=quantity_two_leg,
            contract_key=source.contract_key,
            base_iv=source.base_iv,
            shocked_iv=source.shocked_iv,
            remaining_calendar_days=source.remaining_calendar_days,
            per_underlying_unit_option_value=decimal.Decimal("1.25"),
            total_leg_value=decimal.Decimal("250.00"),
            exercise_style=source.exercise_style,
            settlement_type=source.settlement_type,
            implied_volatility_record_id=source.implied_volatility_record_id,
            contract_reference_record_id=source.contract_reference_record_id,
        )
        self.assertEqual(valid.leg.quantity, 2)
        self.assertEqual(valid.leg.contract_multiplier, 100)
        self.assertEqual(valid.total_leg_value, decimal.Decimal("250.00"))
        with self.assertRaises(ValueError):
            dataclasses.replace(
                valid,
                total_leg_value=decimal.Decimal("125.00"),
            )

    def test_review_decimal_context_preserved_on_ordinary_failure(self):
        record = make_scenario_pricing_result(
            ("call", "put")
        ).records[0]
        context = decimal.getcontext()
        original = context.copy()
        context.prec = 9
        context.rounding = decimal.ROUND_FLOOR
        context.clear_flags()

        def context_state():
            return (
                context.prec,
                context.rounding,
                tuple(context.traps.items()),
                tuple(context.flags.items()),
                context.Emin,
                context.Emax,
                context.capitals,
                context.clamp,
            )

        configured = context_state()
        try:
            with self.assertRaises(ValueError):
                dataclasses.replace(
                    record,
                    estimated_gross_position_value=decimal.Decimal("599.99"),
                )
            self.assertEqual(context_state(), configured)
        finally:
            decimal.setcontext(original)

    def test_scope_exclusions_are_not_called(self):
        blocked = (
            "ScenarioResult",
            "transform_structure_costs",
            "transform_tail_pricing",
            "transform_volatility_environment",
            "black_scholes",
            "expiration_payoff",
            "entry_cost",
            "exit_cost",
            "profit_and_loss",
        )
        with ExitStack() as stack:
            for name in blocked:
                stack.enter_context(mock.patch.object(
                    transformations,
                    name,
                    side_effect=AssertionError(f"{name} called"),
                    create=True,
                ))
            make_scenario_pricing_result()


def make_scenario_valuation_result(
    option_types=("call",),
    *,
    quantity=1,
    expiration_move=None,
    expiration_iv_change=0.5,
    expiration_exit_cost="0",
    include_expiration=True,
    scenario_grid_complete=False,
    return_arguments=False,
):
    expiration = SESSION_DATE + datetime.timedelta(days=60)
    structure = OptionStructure(
        tuple(
            OptionLeg(
                "SPY",
                option_type,
                100.0,
                expiration,
                quantity,
                100,
            )
            for option_type in option_types
        ),
        assumed_portfolio_value=100000.0,
        expected_holding_days=14,
    )
    selection = make_cost_selection(structure)[0]
    costs = transform_costs(
        structure,
        selection,
        commissions_and_fees=decimal.Decimal("1.25"),
        calculation_id="scenario-valuation-costs",
    )
    tail = make_tail_result()
    pricing = make_scenario_pricing_result(option_types, structure)
    scenarios = tuple(record.scenario for record in pricing.records)
    if include_expiration:
        if expiration_move is None:
            expiration_move = (
                -0.1 if option_types == ("put",) else 0.1
            )
        scenarios += (
            Scenario(
                expiration_move,
                expiration_iv_change,
                "expiration",
            ),
        )
    exit_costs = tuple(
        (
            scenario,
            decimal.Decimal(expiration_exit_cost)
            if scenario.valuation_time == "expiration"
            else decimal.Decimal("2.50"),
        )
        for scenario in scenarios
    )
    arguments = (
        "scenario-valuation-calculation-001",
        costs,
        tail,
        pricing,
        scenarios,
        scenario_grid_complete,
        exit_costs,
        "explicit_fixture_exit_cost_v0.1",
        CALCULATED_AT + datetime.timedelta(seconds=10),
    )
    if return_arguments:
        return arguments
    return transform_scenario_valuation(*arguments)


def rebuild_scenario_pricing_scenarios(result, scenarios):
    first = result.records[0]
    records = []
    for scenario in scenarios:
        valuation_date = transformations._scenario_pricing_valuation_date(
            first.structure, first.as_of_date, scenario
        )
        calculations = tuple(
            dataclasses.replace(
                item,
                shocked_iv=transformations._scenario_pricing_shock(
                    item.base_iv, scenario.iv_change
                ),
                remaining_calendar_days=(
                    item.leg.expiration - valuation_date
                ).days,
            )
            for item in first.leg_calculations
        )
        records.append(NonExpirationScenarioPricingCalculation(
            structure=first.structure,
            as_of_date=first.as_of_date,
            scenario=scenario,
            valuation_date=valuation_date,
            base_underlying_price=first.base_underlying_price,
            shocked_underlying_price=transformations._scenario_pricing_shock(
                first.base_underlying_price, scenario.underlying_move
            ),
            underlying_quote_record_id=first.underlying_quote_record_id,
            leg_calculations=calculations,
            estimated_gross_position_value=sum(
                (item.total_leg_value for item in calculations),
                decimal.Decimal(0),
            ),
            pricing_methodology=first.pricing_methodology,
        ))
    records = tuple(records)
    old = transformations._decode_scenario_pricing_parameters(
        result.lineage.parameters_json
    )
    parameters = transformations._scenario_pricing_expected_fixed_parameters(
        records
    )
    for key in (
        "base_underlying_evidence",
        "leg_iv_evidence",
        "contract_reference_evidence",
    ):
        parameters[key] = old[key]
    lineage = dataclasses.replace(
        result.lineage,
        parameters_json=market_data.canonicalize_lineage_parameters(
            parameters
        ),
    )
    return ScenarioPricingCalculationResult(records, lineage)


def reidentify_scenario_pricing(
    result,
    *,
    underlying_record_id,
    iv_record_ids=None,
    reference_record_ids=None,
    normalized_at=CALCULATED_AT,
    reference_overrides=None,
):
    first = result.records[0]
    iv_record_ids = (
        tuple(item.implied_volatility_record_id
              for item in first.leg_calculations)
        if iv_record_ids is None else iv_record_ids
    )
    reference_record_ids = (
        tuple(item.contract_reference_record_id
              for item in first.leg_calculations)
        if reference_record_ids is None else reference_record_ids
    )
    records = tuple(
        dataclasses.replace(
            record,
            underlying_quote_record_id=underlying_record_id,
            leg_calculations=tuple(
                dataclasses.replace(
                    item,
                    implied_volatility_record_id=iv_id,
                    contract_reference_record_id=reference_id,
                )
                for item, iv_id, reference_id in zip(
                    record.leg_calculations,
                    iv_record_ids,
                    reference_record_ids,
                )
            ),
        )
        for record in result.records
    )
    old = transformations._decode_scenario_pricing_parameters(
        result.lineage.parameters_json
    )
    reference_overrides = (
        {} if reference_overrides is None else reference_overrides
    )

    def reference_values(record_id):
        return reference_overrides.get(
            record_id, (normalized_at, ("source-001",))
        )

    underlying_normalized_at, underlying_source_ids = reference_values(
        underlying_record_id
    )
    underlying = dict(old["base_underlying_evidence"])
    underlying.update({
        "record_id": underlying_record_id,
        "normalized_at": underlying_normalized_at,
        "source_ids": underlying_source_ids,
    })
    iv_evidence = tuple(
        {
            **item,
            "record_id": record_id,
            "normalized_at": reference_values(record_id)[0],
            "source_ids": reference_values(record_id)[1],
        }
        for item, record_id in zip(old["leg_iv_evidence"], iv_record_ids)
    )
    references = tuple(
        {
            **item,
            "record_id": record_id,
            "normalized_at": reference_values(record_id)[0],
            "source_ids": reference_values(record_id)[1],
        }
        for item, record_id in zip(
            old["contract_reference_evidence"], reference_record_ids
        )
    )
    parameters = transformations._scenario_pricing_expected_fixed_parameters(
        records
    )
    parameters.update({
        "base_underlying_evidence": underlying,
        "leg_iv_evidence": iv_evidence,
        "contract_reference_evidence": references,
    })
    inputs = tuple(
        CalculationInputReference(
            evidence["record_id"],
            evidence["normalized_at"],
            evidence["source_ids"],
        )
        for evidence in (underlying,) + iv_evidence + references
    )
    lineage = dataclasses.replace(
        result.lineage,
        inputs=inputs,
        parameters_json=market_data.canonicalize_lineage_parameters(
            parameters
        ),
    )
    return ScenarioPricingCalculationResult(records, lineage)


def mutate_scenario_valuation_lineage(result, mutate):
    parameters = copy.deepcopy(
        transformations._decode_scenario_valuation_parameters(
            result.lineage.parameters_json
        )
    )
    mutate(parameters)
    return dataclasses.replace(
        result.lineage,
        parameters_json=market_data.canonicalize_lineage_parameters(
            parameters
        ),
    )


def mutate_embedded_tail_pricing_parameters(result, mutate):
    downstream = copy.deepcopy(
        transformations._decode_scenario_valuation_parameters(
            result.lineage.parameters_json
        )
    )
    embedded = transformations._decode_strict_tagged_parameters(
        downstream["tail_pricing_dependency"]["parameters_json"],
        transformations._TAIL_PRICING_PARAMETER_KEYS,
        "test TailPricing",
    )
    mutate(embedded)
    downstream["tail_pricing_dependency"]["parameters_json"] = (
        market_data.canonicalize_lineage_parameters(embedded)
    )
    return dataclasses.replace(
        result.lineage,
        parameters_json=market_data.canonicalize_lineage_parameters(
            downstream
        ),
    )


def make_tail_matching_scenario_valuation_arguments(iv_id, reference_id):
    expiration = SESSION_DATE + datetime.timedelta(days=60)
    structure = OptionStructure(
        (OptionLeg("SPY", "call", 100.0, expiration, 1, 100),),
        100000.0,
        14,
    )
    costs = transform_costs(
        structure,
        make_cost_selection(structure)[0],
        calculation_id="scenario-valuation-costs",
    )
    tail = make_tail_result()
    pricing = make_scenario_pricing_result(
        ("call",),
        structure,
        deliverable_id=None,
        base_iv_values=("0.40",),
        iv_record_ids=(iv_id,),
        reference_record_ids=(reference_id,),
    )
    pricing = reidentify_scenario_pricing(
        pricing,
        underlying_record_id=pricing.records[0].underlying_quote_record_id,
        iv_record_ids=(iv_id,),
        reference_record_ids=(reference_id,),
        reference_overrides={
            item.record_id: (item.normalized_at, item.source_ids)
            for item in tail.lineage.inputs
            if item.record_id in {iv_id, reference_id}
        },
    )
    scenarios = tuple(record.scenario for record in pricing.records)
    return (
        costs,
        tail,
        pricing,
        scenarios,
        tuple((scenario, decimal.Decimal("0")) for scenario in scenarios),
    )


class ScenarioValuationTransformationTests(unittest.TestCase):
    def test_exact_public_surface_fields_signature_and_package_boundary(self):
        self.assertEqual(len(transformations.__all__), 28)
        self.assertEqual(transformations.__all__[16:18], (
            "ScenarioValuationTransformationResult",
            "transform_scenario_valuation",
        ))
        self.assertEqual(len(market_data.__all__), 64)
        self.assertEqual(
            tuple(
                field.name for field in dataclasses.fields(
                    ScenarioValuationTransformationResult
                )
            ),
            ("records", "lineage"),
        )
        self.assertEqual(
            tuple(inspect.signature(transform_scenario_valuation).parameters),
            (
                "calculation_id",
                "structure_costs_result",
                "tail_pricing_result",
                "scenario_pricing_result",
                "scenarios",
                "scenario_grid_complete",
                "exit_cost_assumptions",
                "exit_cost_methodology",
                "calculated_at",
            ),
        )
        self.assertFalse(
            hasattr(convexity_hunter, "ScenarioValuationTransformationResult")
        )
        self.assertFalse(
            hasattr(convexity_hunter, "transform_scenario_valuation")
        )
        result = make_scenario_valuation_result()
        with self.assertRaises(FrozenInstanceError):
            result.records = ()

    def test_long_call_put_and_straddle_literal_outputs(self):
        call = make_scenario_valuation_result(("call",))
        put = make_scenario_valuation_result(("put",))
        straddle = make_scenario_valuation_result(("call", "put"))
        self.assertEqual(
            tuple(item.estimated_position_value for item in call.records),
            (250.0, 300.0, 200.0, 1000.0),
        )
        self.assertEqual(
            tuple(item.estimated_position_value for item in put.records),
            (250.0, 300.0, 200.0, 1000.0),
        )
        self.assertEqual(
            tuple(item.estimated_position_value for item in straddle.records),
            (600.0, 700.0, 500.0, 1000.0),
        )
        self.assertEqual(call.records[-1].base_ivs, (0.2,))
        self.assertEqual(straddle.records[-1].base_ivs, (0.2, 0.3))
        self.assertEqual(call.records[-1].valuation_date,
                         SESSION_DATE + datetime.timedelta(days=60))
        self.assertEqual(
            call.lineage.calculation_type, "scenario_valuation"
        )
        self.assertEqual(
            call.lineage.methodology_id,
            "hybrid-authoritative-nonexpiration-terminal-intrinsic-after-costs",
        )
        self.assertEqual(call.lineage.methodology_version, "v0.1")
        self.assertEqual(len(call.lineage.inputs), 209)
        self.assertEqual(len(straddle.lineage.inputs), 214)

    def test_expiration_payoff_scaling_zero_and_iv_independence(self):
        zero_call = make_scenario_valuation_result(
            ("call",), expiration_move=-0.1, expiration_iv_change=-0.2
        )
        positive_call = make_scenario_valuation_result(
            ("call",), expiration_move=0.1, expiration_iv_change=0.5
        )
        same_call = make_scenario_valuation_result(
            ("call",), expiration_move=0.1, expiration_iv_change=-0.2
        )
        self.assertEqual(zero_call.records[-1].estimated_position_value, 0.0)
        self.assertEqual(
            positive_call.records[-1].estimated_position_value, 1000.0
        )
        self.assertEqual(
            same_call.records[-1].estimated_position_value, 1000.0
        )
        quantity_two = make_scenario_valuation_result(
            ("call",),
            quantity=2,
            expiration_move=0.1,
        )
        self.assertEqual(
            quantity_two.records[-1].estimated_position_value, 2000.0
        )

    def test_exit_cost_floor_and_exact_methodology_schemas(self):
        result = make_scenario_valuation_result(
            expiration_exit_cost="2000"
        )
        expiration = result.records[-1]
        self.assertEqual(expiration.net_liquidation_value, 0.0)
        self.assertEqual(
            expiration.pnl_after_costs, -expiration.entry_cost_basis
        )
        self.assertTrue(expiration.loss_is_within_entry_cost)
        methodology = transformations._decode_strict_tagged_parameters(
            expiration.pricing_methodology,
            transformations._SCENARIO_METHODOLOGY_KEYS,
            "test",
        )
        self.assertEqual(len(methodology), 15)
        self.assertEqual(
            methodology["valuation_source"],
            "terminal_intrinsic_expiration",
        )
        parameters = transformations._decode_scenario_valuation_parameters(
            result.lineage.parameters_json
        )
        self.assertEqual(len(parameters), 25)
        self.assertEqual(
            set(parameters),
            transformations._SCENARIO_VALUATION_PARAMETER_KEYS,
        )
        self.assertEqual(
            hashlib.sha256(
                result.records[0].pricing_methodology.encode()
            ).hexdigest(),
            "f66351122871403e24a8613f9083596f4a933aef11913a92e4e4a4fed55de9c9",
        )
        self.assertEqual(
            hashlib.sha256(
                expiration.pricing_methodology.encode()
            ).hexdigest(),
            "7ad4c54760eeea8507a6ee11cbc40e32d1fd794b91da702fd8f2cdf09de32c08",
        )
        self.assertEqual(
            hashlib.sha256(
                result.lineage.parameters_json.encode()
            ).hexdigest(),
            "d66b73f30424ceadbee00358f2113386e5efb378546283c8639abc904632eded",
        )

    def test_complete_grid_and_explicit_subset(self):
        expiration = SESSION_DATE + datetime.timedelta(days=60)
        structure = OptionStructure(
            (OptionLeg("SPY", "call", 100.0, expiration, 1, 100),),
            100000.0,
            14,
        )
        costs = transform_costs(
            structure,
            make_cost_selection(structure)[0],
            calculation_id="scenario-valuation-costs",
        )
        tail = make_tail_result()
        base_pricing = make_scenario_pricing_result(("call",), structure)
        scenarios = tuple(
            Scenario(float(move), float(iv), "immediate")
            for move in transformations._SCENARIO_GRID_MOVES
            for iv in transformations._SCENARIO_GRID_IV_CHANGES
        )
        pricing = rebuild_scenario_pricing_scenarios(
            base_pricing, scenarios
        )
        assumptions = tuple(
            (scenario, decimal.Decimal("0")) for scenario in scenarios
        )
        result = transform_scenario_valuation(
            "scenario-valuation-complete-grid",
            costs,
            tail,
            pricing,
            scenarios,
            True,
            assumptions,
            "explicit_fixture_exit_cost_v0.1",
            CALCULATED_AT + datetime.timedelta(seconds=10),
        )
        self.assertEqual(len(result.records), 28)
        with self.assertRaises(ValueError):
            transform_scenario_valuation(
                "scenario-valuation-incomplete-grid",
                costs,
                tail,
                rebuild_scenario_pricing_scenarios(
                    base_pricing, scenarios[:-1]
                ),
                scenarios[:-1],
                True,
                assumptions[:-1],
                "explicit_fixture_exit_cost_v0.1",
                CALCULATED_AT + datetime.timedelta(seconds=10),
            )
        subset = make_scenario_valuation_result(
            include_expiration=False,
            scenario_grid_complete=False,
        )
        self.assertEqual(len(subset.records), 3)

    def test_scenario_and_exit_cost_contract_mutation_matrix(self):
        expiration = SESSION_DATE + datetime.timedelta(days=60)
        structure = OptionStructure(
            (OptionLeg("SPY", "call", 100.0, expiration, 1, 100),),
            100000.0,
            14,
        )
        costs = transform_costs(
            structure,
            make_cost_selection(structure)[0],
            calculation_id="scenario-valuation-costs",
        )
        tail = make_tail_result()
        pricing = make_scenario_pricing_result(("call",), structure)
        scenarios = tuple(record.scenario for record in pricing.records)
        assumptions = tuple(
            (scenario, decimal.Decimal("0")) for scenario in scenarios
        )

        def invoke(declared=scenarios, exits=assumptions, complete=False):
            return transform_scenario_valuation(
                "scenario-valuation-mutation",
                costs,
                tail,
                pricing,
                declared,
                complete,
                exits,
                "explicit_fixture_exit_cost_v0.1",
                CALCULATED_AT + datetime.timedelta(seconds=10),
            )

        wrong_scenario_cases = (
            (),
            scenarios + (scenarios[0],),
            tuple(reversed(scenarios)),
            (Scenario(0.0, 0.0, "expiration"),),
        )
        for declared in wrong_scenario_cases:
            with self.subTest(declared=declared):
                with self.assertRaises(ValueError):
                    invoke(
                        declared=declared,
                        exits=tuple(
                            (scenario, decimal.Decimal("0"))
                            for scenario in declared
                        ),
                    )
        with self.assertRaises(ValueError):
            invoke(complete=True)

        exit_cases = (
            assumptions[:-1],
            assumptions + ((scenarios[-1], decimal.Decimal("0")),),
            tuple(reversed(assumptions)),
            tuple((dataclasses.replace(scenario), cost)
                  for scenario, cost in assumptions),
            tuple((scenario, decimal.Decimal("-0.01"))
                  for scenario in scenarios),
            tuple((scenario, decimal.Decimal("NaN"))
                  for scenario in scenarios),
        )
        for exits in exit_cases:
            with self.subTest(exits=exits):
                with self.assertRaises(ValueError):
                    invoke(exits=exits)
        wrong_inner = ((scenarios[0], decimal.Decimal("0"), "extra"),) + (
            assumptions[1:]
        )
        with self.assertRaises(ValueError):
            invoke(exits=wrong_inner)
        wrong_decimal = ((scenarios[0], 0.0),) + assumptions[1:]
        with self.assertRaises(TypeError):
            invoke(exits=wrong_decimal)

    def test_lineage_exact_overlap_deduplication_and_conflict(self):
        expiration = SESSION_DATE + datetime.timedelta(days=60)
        structure = OptionStructure(
            (OptionLeg("SPY", "call", 100.0, expiration, 1, 100),),
            100000.0,
            14,
        )
        costs = transform_costs(
            structure,
            make_cost_selection(structure)[0],
            calculation_id="scenario-valuation-costs",
        )
        tail = make_tail_result()
        base = make_scenario_pricing_result(("call",), structure)
        scenarios = tuple(record.scenario for record in base.records)
        assumptions = tuple(
            (scenario, decimal.Decimal("0")) for scenario in scenarios
        )

        def invoke(pricing, calculation_id):
            return transform_scenario_valuation(
                calculation_id,
                costs,
                tail,
                pricing,
                scenarios,
                False,
                assumptions,
                "explicit_fixture_exit_cost_v0.1",
                CALCULATED_AT + datetime.timedelta(seconds=10),
            )

        one_overlap = reidentify_scenario_pricing(
            base,
            underlying_record_id="cost-underlying-quote",
            reference_overrides={
                item.record_id: (item.normalized_at, item.source_ids)
                for item in costs.lineage.inputs
            },
        )
        self.assertEqual(
            len(invoke(one_overlap, "scenario-valuation-one-overlap").lineage.inputs),
            208,
        )
        multiple_overlaps = reidentify_scenario_pricing(
            base,
            underlying_record_id="cost-underlying-quote",
            reference_record_ids=("cost-call-contract-reference",),
            reference_overrides={
                item.record_id: (item.normalized_at, item.source_ids)
                for item in costs.lineage.inputs
            },
        )
        self.assertEqual(
            len(invoke(
                multiple_overlaps,
                "scenario-valuation-multiple-overlaps",
            ).lineage.inputs),
            207,
        )
        conflicting = reidentify_scenario_pricing(
            base,
            underlying_record_id="cost-underlying-quote",
            reference_overrides={
                "cost-underlying-quote": (
                    next(
                        item.normalized_at for item in costs.lineage.inputs
                        if item.record_id == "cost-underlying-quote"
                    ) + datetime.timedelta(microseconds=1),
                    next(
                        item.source_ids for item in costs.lineage.inputs
                        if item.record_id == "cost-underlying-quote"
                    ),
                ),
            },
        )
        with self.assertRaises(ValueError):
            invoke(conflicting, "scenario-valuation-conflicting-overlap")

    def test_direct_wrapper_requires_exact_three_dependency_input_union(self):
        result = make_scenario_valuation_result()
        costs, tail, pricing, _volatility = (
            transformations._reconstruct_scenario_valuation_dependencies(
                result.records, result.lineage
            )
        )
        groups = (
            costs.lineage.inputs,
            tail.lineage.inputs,
            pricing.lineage.inputs,
        )
        identifiers = tuple({item.record_id for item in group} for group in groups)
        labels = ("costs", "tail", "pricing")
        for index, label in enumerate(labels):
            other = set().union(*(
                value for offset, value in enumerate(identifiers)
                if offset != index
            ))
            exclusive = next(iter(identifiers[index] - other))
            inputs = tuple(
                item for item in result.lineage.inputs
                if item.record_id != exclusive
            )
            lineage = dataclasses.replace(result.lineage, inputs=inputs)
            with self.subTest(label=label), self.assertRaises(ValueError):
                ScenarioValuationTransformationResult(
                    result.records, lineage
                )
        surplus = CalculationInputReference(
            "scenario-surplus-input",
            result.lineage.calculated_at,
            ("fixture-source",),
        )
        lineage = dataclasses.replace(
            result.lineage, inputs=result.lineage.inputs + (surplus,)
        )
        with self.assertRaisesRegex(ValueError, "exact dependency union"):
            ScenarioValuationTransformationResult(result.records, lineage)

    def test_direct_wrapper_rejects_record_lineage_and_quality_forgery(self):
        result = make_scenario_valuation_result()
        ScenarioValuationTransformationResult(
            result.records, result.lineage
        )
        with self.assertRaises(TypeError):
            ScenarioValuationTransformationResult(list(result.records),
                                                  result.lineage)
        with self.assertRaises(ValueError):
            ScenarioValuationTransformationResult(
                result.records,
                dataclasses.replace(
                    result.lineage,
                    calculation_type="forged",
                ),
            )
        with self.assertRaises(ValueError):
            ScenarioValuationTransformationResult(
                result.records,
                dataclasses.replace(
                    result.lineage,
                    quality_flags=(
                        CalculationQualityFlag.ANNUALIZED,
                    ),
                ),
            )

    def test_review_public_base_iv_and_cross_leg_forgery_reject(self):
        call = make_scenario_valuation_result(("call",))
        forged_input = dataclasses.replace(
            call.records[0].leg_volatility_inputs[0],
            base_iv=0.91,
        )
        forged_call_record = dataclasses.replace(
            call.records[0],
            leg_volatility_inputs=(forged_input,),
        )
        with self.assertRaises(ValueError):
            ScenarioValuationTransformationResult(
                (forged_call_record,) + call.records[1:],
                call.lineage,
            )

        straddle = make_scenario_valuation_result(("call", "put"))
        first = straddle.records[0]
        swapped_inputs = (
            dataclasses.replace(
                first.leg_volatility_inputs[0],
                base_iv=first.leg_volatility_inputs[1].base_iv,
            ),
            dataclasses.replace(
                first.leg_volatility_inputs[1],
                base_iv=first.leg_volatility_inputs[0].base_iv,
            ),
        )
        forged_straddle_record = dataclasses.replace(
            first, leg_volatility_inputs=swapped_inputs
        )
        with self.assertRaises(ValueError):
            ScenarioValuationTransformationResult(
                (forged_straddle_record,) + straddle.records[1:],
                straddle.lineage,
            )

    def test_review_dependency_identity_and_nested_schema_mutations_reject(self):
        result = make_scenario_valuation_result()
        dependency_mutations = (
            lambda value: value["structure_costs_dependency"].__setitem__(
                "methodology_version", "v0.1"
            ),
            lambda value: value["tail_pricing_dependency"].__setitem__(
                "methodology_version", "v9.9"
            ),
            lambda value: value["scenario_pricing_dependency"].__setitem__(
                "methodology_id", "forged-scenario-pricing-methodology"
            ),
        )
        for mutate in dependency_mutations:
            with self.subTest(mutate=mutate):
                lineage = mutate_scenario_valuation_lineage(result, mutate)
                with self.assertRaises(ValueError):
                    ScenarioValuationTransformationResult(
                        result.records, lineage
                    )

        nested_mutations = (
            lambda value: value["calculation_values"][0].pop(
                "base_leg_ivs_exact"
            ),
            lambda value: value["calculation_values"][0].__setitem__(
                "extra", "forged"
            ),
            lambda value: value["calculation_values"][0].__setitem__(
                "shocked_leg_ivs_exact", (decimal.Decimal("0.91"),)
            ),
            lambda value: value["calculation_values"][0].__setitem__(
                "scenario_identity",
                {
                    **value["calculation_values"][0]["scenario_identity"],
                    "iv_change": decimal.Decimal("0.91"),
                },
            ),
            lambda value: value["calculation_values"][0].__setitem__(
                "valuation_source", "terminal_intrinsic_expiration"
            ),
            lambda value: value["calculation_values"][0].__setitem__(
                "stable_gross_value_repr", "999.0"
            ),
            lambda value: value["calculation_values"][0].__setitem__(
                "pricing_methodology", "forged"
            ),
            lambda value: value["structure_costs_dependency"].pop("selected"),
            lambda value: value["tail_pricing_dependency"].__setitem__(
                "extra", "forged"
            ),
        )
        for mutate in nested_mutations:
            with self.subTest(mutate=mutate):
                lineage = mutate_scenario_valuation_lineage(result, mutate)
                with self.assertRaises(ValueError):
                    ScenarioValuationTransformationResult(
                        result.records, lineage
                    )

    def test_review_record_methodology_mutations_reject(self):
        result = make_scenario_valuation_result()
        methodology = transformations._decode_strict_tagged_parameters(
            result.records[0].pricing_methodology,
            transformations._SCENARIO_METHODOLOGY_KEYS,
            "test",
        )
        mutations = (
            lambda value: value.pop("schema_version"),
            lambda value: value.__setitem__("extra", "forged"),
            lambda value: value["scenario_pricing_dependency"].__setitem__(
                "identity",
                (
                    "nonexpiration_scenario_pricing",
                    "forged-methodology",
                    "v0.1",
                ),
            ),
            lambda value: value["expiration_rule"].__setitem__(
                "active", True
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                forged_methodology = copy.deepcopy(methodology)
                mutate(forged_methodology)
                forged_string = market_data.canonicalize_lineage_parameters(
                    forged_methodology
                )
                forged_record = dataclasses.replace(
                    result.records[0],
                    pricing_methodology=forged_string,
                )

                def mutate_lineage(value):
                    value["calculation_values"][0][
                        "pricing_methodology"
                    ] = forged_string

                lineage = mutate_scenario_valuation_lineage(
                    result, mutate_lineage
                )
                with self.assertRaises(ValueError):
                    ScenarioValuationTransformationResult(
                        (forged_record,) + result.records[1:],
                        lineage,
                    )

    def test_final_review_current_tail_nested_schema_mutations_reject(self):
        result = make_scenario_valuation_result()
        ScenarioValuationTransformationResult(
            result.records, result.lineage
        )
        mutations = (
            (
                "missing_selected_put",
                lambda value: value[
                    "current_expiration_observations"
                ][0]["selected_put_25"].pop("target_delta"),
            ),
            (
                "extra_selected_put",
                lambda value: value[
                    "current_expiration_observations"
                ][0]["selected_put_25"].__setitem__("extra", "forged"),
            ),
            (
                "missing_selected_call",
                lambda value: value[
                    "current_expiration_observations"
                ][0]["selected_call_25"].pop("distance"),
            ),
            (
                "missing_current_candidate",
                lambda value: value[
                    "current_expiration_observations"
                ][0]["candidate_contracts"][0].pop("signed_delta"),
            ),
            (
                "extra_current_candidate",
                lambda value: value[
                    "current_expiration_observations"
                ][0]["candidate_contracts"][0].__setitem__(
                    "extra", "forged"
                ),
            ),
            (
                "wrong_selected_container",
                lambda value: value[
                    "current_expiration_observations"
                ][0].__setitem__("selected_put_25", ()),
            ),
            (
                "reordered_current_candidates",
                lambda value: value[
                    "current_expiration_observations"
                ][0].__setitem__(
                    "candidate_contracts",
                    tuple(reversed(value[
                        "current_expiration_observations"
                    ][0]["candidate_contracts"])),
                ),
            ),
            (
                "decimal_replaced_by_string",
                lambda value: value[
                    "current_expiration_observations"
                ][0]["candidate_contracts"][0].__setitem__(
                    "implied_volatility", "0.30"
                ),
            ),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                lineage = mutate_embedded_tail_pricing_parameters(
                    result, mutate
                )
                with self.assertRaises(ValueError):
                    ScenarioValuationTransformationResult(
                        result.records, lineage
                    )

    def test_final_review_historical_tail_nested_schema_mutations_reject(self):
        result = make_scenario_valuation_result()
        mutations = (
            (
                "missing_historical_field",
                lambda value: value[
                    "historical_observations_by_tenor"
                ][0]["historical_observations"][0].pop("atm_iv"),
            ),
            (
                "extra_historical_field",
                lambda value: value[
                    "historical_observations_by_tenor"
                ][0]["historical_observations"][0].__setitem__(
                    "extra", "forged"
                ),
            ),
            (
                "missing_historical_selected_option_field",
                lambda value: value[
                    "historical_observations_by_tenor"
                ][0]["historical_observations"][0][
                    "selected_call_25"
                ].pop("contract_reference_record_id"),
            ),
            (
                "wrong_historical_collection_container",
                lambda value: value[
                    "historical_observations_by_tenor"
                ][0].__setitem__("historical_observations", {}),
            ),
            (
                "reordered_historical_observations",
                lambda value: value[
                    "historical_observations_by_tenor"
                ][0].__setitem__(
                    "historical_observations",
                    tuple(reversed(value[
                        "historical_observations_by_tenor"
                    ][0]["historical_observations"])),
                ),
            ),
            (
                "date_replaced_by_datetime",
                lambda value: value[
                    "historical_observations_by_tenor"
                ][0]["historical_observations"][0].__setitem__(
                    "session_date", CALCULATED_AT
                ),
            ),
            (
                "missing_historical_candidate_field",
                lambda value: value[
                    "historical_observations_by_tenor"
                ][0]["historical_observations"][0][
                    "candidate_contracts"
                ][0].pop("contract_multiplier"),
            ),
            (
                "extra_historical_atm_pair_field",
                lambda value: value[
                    "historical_observations_by_tenor"
                ][0]["historical_observations"][0][
                    "selected_paired_atm_evidence"
                ]["candidate_pairs"][0].__setitem__("extra", "forged"),
            ),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                lineage = mutate_embedded_tail_pricing_parameters(
                    result, mutate
                )
                with self.assertRaises(ValueError):
                    ScenarioValuationTransformationResult(
                        result.records, lineage
                    )

    def test_final_review_tail_schema_decimal_context_is_preserved(self):
        result = make_scenario_valuation_result()
        mutations = (
            lambda value: value[
                "current_expiration_observations"
            ][0]["selected_put_25"].pop("target_delta"),
            lambda value: value[
                "current_expiration_observations"
            ][0]["selected_put_25"].__setitem__("extra", "forged"),
            lambda value: value[
                "historical_observations_by_tenor"
            ][0]["historical_observations"][0].pop("atm_iv"),
            lambda value: value[
                "historical_observations_by_tenor"
            ][0]["historical_observations"][0].__setitem__(
                "extra", "forged"
            ),
            lambda value: value[
                "current_expiration_observations"
            ][0].__setitem__("selected_put_25", ()),
        )
        lineages = tuple(
            mutate_embedded_tail_pricing_parameters(result, mutate)
            for mutate in mutations
        )
        context = decimal.getcontext()
        original = context.copy()
        context.prec = 11
        context.rounding = decimal.ROUND_CEILING
        context.clear_flags()
        configured = decimal_context_state()
        try:
            for index, lineage in enumerate(lineages):
                with self.subTest(index=index):
                    with self.assertRaises(ValueError):
                        ScenarioValuationTransformationResult(
                            result.records, lineage
                        )
                    self.assertEqual(decimal_context_state(), configured)
        finally:
            decimal.setcontext(original)

    def test_review_tail_scenario_matching_evidence_ids(self):
        expiration = SESSION_DATE + datetime.timedelta(days=60)
        structure = OptionStructure(
            (OptionLeg("SPY", "call", 100.0, expiration, 1, 100),),
            100000.0,
            14,
        )
        costs = transform_costs(
            structure,
            make_cost_selection(structure)[0],
            calculation_id="scenario-valuation-costs",
        )
        tail = make_tail_result()

        def pricing(iv_id, reference_id):
            result = make_scenario_pricing_result(
                ("call",),
                structure,
                deliverable_id=None,
                base_iv_values=("0.40",),
                iv_record_ids=(iv_id,),
                reference_record_ids=(reference_id,),
            )
            return reidentify_scenario_pricing(
                result,
                underlying_record_id=(
                    result.records[0].underlying_quote_record_id
                ),
                iv_record_ids=(iv_id,),
                reference_record_ids=(reference_id,),
                reference_overrides={
                    item.record_id: (item.normalized_at, item.source_ids)
                    for item in tail.lineage.inputs
                    if item.record_id in {iv_id, reference_id}
                },
            )

        def invoke(pricing_result, calculation_id):
            scenarios = tuple(
                record.scenario for record in pricing_result.records
            )
            return transform_scenario_valuation(
                calculation_id,
                costs,
                tail,
                pricing_result,
                scenarios,
                False,
                tuple(
                    (scenario, decimal.Decimal("0"))
                    for scenario in scenarios
                ),
                "explicit_fixture_exit_cost_v0.1",
                CALCULATED_AT + datetime.timedelta(seconds=10),
            )

        matching = pricing(
            "ve-current-1-call-iv",
            "ve-current-1-call-reference",
        )
        self.assertEqual(
            len(invoke(matching, "matching-evidence-ids").records), 3
        )
        mismatches = (
            pricing(
                "scenario-iv-0",
                "ve-current-1-call-reference",
            ),
            pricing(
                "ve-current-1-call-iv",
                "scenario-reference-0",
            ),
        )
        for index, mismatch in enumerate(mismatches):
            with self.subTest(index=index):
                with ExitStack() as stack:
                    for name in (
                        "LegVolatilityInput",
                        "ScenarioResult",
                        "_construct_scenario_valuation_lineage",
                        "ScenarioValuationTransformationResult",
                    ):
                        stack.enter_context(mock.patch.object(
                            transformations,
                            name,
                            side_effect=AssertionError(f"{name} called"),
                        ))
                    with self.assertRaises(ValueError):
                        invoke(mismatch, f"mismatched-evidence-{index}")

    def test_review_failures_preserve_complete_decimal_context(self):
        call = make_scenario_valuation_result(("call",))
        forged_call_record = dataclasses.replace(
            call.records[0],
            leg_volatility_inputs=(
                dataclasses.replace(
                    call.records[0].leg_volatility_inputs[0],
                    base_iv=0.91,
                ),
            ),
        )
        straddle = make_scenario_valuation_result(("call", "put"))
        first = straddle.records[0]
        forged_straddle_record = dataclasses.replace(
            first,
            leg_volatility_inputs=(
                dataclasses.replace(
                    first.leg_volatility_inputs[0],
                    base_iv=first.leg_volatility_inputs[1].base_iv,
                ),
                dataclasses.replace(
                    first.leg_volatility_inputs[1],
                    base_iv=first.leg_volatility_inputs[0].base_iv,
                ),
            ),
        )
        dependency_lineage = mutate_scenario_valuation_lineage(
            call,
            lambda value: value[
                "structure_costs_dependency"
            ].__setitem__("methodology_version", "v0.1"),
        )
        nested_lineage = mutate_scenario_valuation_lineage(
            call,
            lambda value: value["calculation_values"][0].pop(
                "base_leg_ivs_exact"
            ),
        )
        tail_mismatch_arguments = (
            make_tail_matching_scenario_valuation_arguments(
                "scenario-iv-0",
                "ve-current-1-call-reference",
            ),
            make_tail_matching_scenario_valuation_arguments(
                "ve-current-1-call-iv",
                "scenario-reference-0",
            ),
        )
        failures = (
            lambda: ScenarioValuationTransformationResult(
                (forged_call_record,) + call.records[1:], call.lineage
            ),
            lambda: ScenarioValuationTransformationResult(
                (forged_straddle_record,) + straddle.records[1:],
                straddle.lineage,
            ),
            lambda: ScenarioValuationTransformationResult(
                call.records, dependency_lineage
            ),
            lambda: ScenarioValuationTransformationResult(
                call.records, nested_lineage
            ),
        ) + tuple(
            (
                lambda arguments=arguments: transform_scenario_valuation(
                    "decimal-context-tail-mismatch",
                    arguments[0],
                    arguments[1],
                    arguments[2],
                    arguments[3],
                    False,
                    arguments[4],
                    "explicit_fixture_exit_cost_v0.1",
                    CALCULATED_AT + datetime.timedelta(seconds=10),
                )
            )
            for arguments in tail_mismatch_arguments
        )
        context = decimal.getcontext()
        original = context.copy()
        context.prec = 11
        context.rounding = decimal.ROUND_CEILING
        context.clear_flags()
        configured = decimal_context_state()
        try:
            for index, failure in enumerate(failures):
                with self.subTest(index=index):
                    with self.assertRaises(ValueError):
                        failure()
                    self.assertEqual(decimal_context_state(), configured)
        finally:
            decimal.setcontext(original)

    def test_dependency_and_exit_cost_mutations_reject(self):
        expiration = SESSION_DATE + datetime.timedelta(days=60)
        structure = OptionStructure(
            (OptionLeg("SPY", "call", 100.0, expiration, 1, 100),),
            100000.0,
            14,
        )
        costs = transform_costs(
            structure,
            make_cost_selection(structure)[0],
            calculation_id="scenario-valuation-costs",
        )
        tail = make_tail_result()
        pricing = make_scenario_pricing_result(("call",), structure)
        scenarios = tuple(record.scenario for record in pricing.records)
        assumptions = tuple(
            (scenario, decimal.Decimal("0")) for scenario in scenarios
        )
        arguments = (
            "scenario-valuation-calculation-001",
            costs,
            tail,
            pricing,
            scenarios,
            False,
            assumptions,
            "explicit_fixture_exit_cost_v0.1",
            CALCULATED_AT + datetime.timedelta(seconds=10),
        )
        with self.assertRaises(TypeError):
            transform_scenario_valuation(*arguments[:4], list(scenarios),
                                         *arguments[5:])
        with self.assertRaises(ValueError):
            transform_scenario_valuation(
                *arguments[:6],
                tuple((scenario, decimal.Decimal("-1"))
                      for scenario in scenarios),
                *arguments[7:],
            )
        with self.assertRaises(ValueError):
            transform_scenario_valuation(
                *arguments[:7],
                " noncanonical ",
                arguments[8],
            )
        forged_tail = object.__new__(TailPricingTransformationResult)
        object.__setattr__(forged_tail, "records", tail.records)
        object.__setattr__(
            forged_tail,
            "lineage",
            dataclasses.replace(tail.lineage, methodology_version="v9"),
        )
        with self.assertRaises(ValueError):
            transform_scenario_valuation(
                arguments[0],
                costs,
                forged_tail,
                *arguments[3:],
            )

    def test_dependency_failures_precede_downstream_constructors(self):
        expiration = SESSION_DATE + datetime.timedelta(days=60)
        structure = OptionStructure(
            (OptionLeg("SPY", "call", 100.0, expiration, 1, 100),),
            100000.0,
            14,
        )
        costs = transform_costs(
            structure,
            make_cost_selection(structure)[0],
            calculation_id="scenario-valuation-costs",
        )
        tail = make_tail_result()
        pricing = make_scenario_pricing_result(("call",), structure)
        scenarios = tuple(record.scenario for record in pricing.records)
        assumptions = tuple(
            (scenario, decimal.Decimal("0")) for scenario in scenarios
        )
        forged_costs = object.__new__(StructureCostsTransformationResult)
        object.__setattr__(forged_costs, "record", costs.record)
        object.__setattr__(
            forged_costs,
            "lineage",
            dataclasses.replace(costs.lineage, methodology_version="v0.1"),
        )
        forged_tail = object.__new__(TailPricingTransformationResult)
        object.__setattr__(forged_tail, "records", tail.records)
        object.__setattr__(
            forged_tail,
            "lineage",
            dataclasses.replace(tail.lineage, methodology_version="v9"),
        )
        forged_pricing = object.__new__(ScenarioPricingCalculationResult)
        object.__setattr__(forged_pricing, "records", pricing.records)
        object.__setattr__(
            forged_pricing,
            "lineage",
            dataclasses.replace(pricing.lineage, methodology_version="v9"),
        )
        for dependency_index, forged in (
            (1, forged_costs),
            (2, forged_tail),
            (3, forged_pricing),
        ):
            arguments = [
                "scenario-valuation-calculation-001",
                costs,
                tail,
                pricing,
                scenarios,
                False,
                assumptions,
                "explicit_fixture_exit_cost_v0.1",
                CALCULATED_AT + datetime.timedelta(seconds=10),
            ]
            arguments[dependency_index] = forged
            with self.subTest(dependency_index=dependency_index):
                with ExitStack() as stack:
                    for name in (
                        "LegVolatilityInput",
                        "ScenarioResult",
                        "ScenarioValuationTransformationResult",
                    ):
                        stack.enter_context(mock.patch.object(
                            transformations,
                            name,
                            side_effect=AssertionError(f"{name} called"),
                        ))
                    with self.assertRaises(ValueError):
                        transform_scenario_valuation(*arguments)

    def test_decimal_context_preserved_and_scope_sentinels(self):
        context = decimal.getcontext()
        original = context.copy()
        context.prec = 9
        context.rounding = decimal.ROUND_FLOOR
        context.clear_flags()
        configured = (
            context.prec,
            context.rounding,
            tuple(context.traps.items()),
            tuple(context.flags.items()),
            context.Emin,
            context.Emax,
            context.capitals,
            context.clamp,
        )
        try:
            result = make_scenario_valuation_result()
            self.assertEqual(
                (
                    context.prec,
                    context.rounding,
                    tuple(context.traps.items()),
                    tuple(context.flags.items()),
                    context.Emin,
                    context.Emax,
                    context.capitals,
                    context.clamp,
                ),
                configured,
            )
            self.assertTrue(result.records)
        finally:
            decimal.setcontext(original)

        blocked = (
            "transform_structure_costs",
            "transform_tail_pricing",
            "transform_volatility_environment",
            "black_scholes",
            "binomial",
            "CandidateResearchRecord",
            "screening",
            "recommendation",
            "position_sizing",
            "execution",
        )
        result = make_scenario_valuation_result()
        with ExitStack() as stack:
            for name in blocked:
                stack.enter_context(mock.patch.object(
                    transformations,
                    name,
                    side_effect=AssertionError(f"{name} called"),
                    create=True,
                ))
            ScenarioValuationTransformationResult(
                result.records, result.lineage
            )


def make_expiration_threshold_result(
    option_types=("call",),
    *,
    quantity=1,
    multiplier=100,
    commissions_and_fees=decimal.Decimal("1.25"),
):
    structure = make_structure(
        option_types, quantity=quantity, multiplier=multiplier
    )
    selection, _, _, _ = make_cost_selection(structure)
    costs = transform_costs(
        structure,
        selection,
        commissions_and_fees=commissions_and_fees,
    )
    return transform_expiration_payoff_thresholds(
        " expiration-thresholds ",
        costs,
        CALCULATED_AT + datetime.timedelta(seconds=1),
    )


def mutate_expiration_threshold_parameters(result, mutate):
    parameters = copy.deepcopy(
        transformations._decode_expiration_threshold_parameters(
            result.lineage.parameters_json
        )
    )
    mutate(parameters)
    return dataclasses.replace(
        result.lineage,
        parameters_json=market_data.canonicalize_lineage_parameters(
            parameters
        ),
    )


def bypass_frozen_dataclass(value, **changes):
    forged = object.__new__(type(value))
    for field in dataclasses.fields(value):
        object.__setattr__(
            forged,
            field.name,
            changes.get(field.name, getattr(value, field.name)),
        )
    return forged


class ExpirationPayoffThresholdPublicContractTests(unittest.TestCase):
    def test_exact_public_api_signature_fields_and_boundaries(self):
        self.assertEqual(len(transformations.__all__), 28)
        self.assertEqual(transformations.__all__[-10:-3], (
            "ExactRational",
            "ExpirationPayoffThresholdSide",
            "ExpirationPayoffThresholdStatus",
            "ExpirationPayoffThreshold",
            "ExpirationPayoffThresholdEvidence",
            "ExpirationPayoffThresholdTransformationResult",
            "transform_expiration_payoff_thresholds",
        ))
        self.assertEqual(len(market_data.__all__), 64)
        self.assertEqual(
            tuple(item.value for item in ExpirationPayoffThresholdSide),
            ("downside", "upside"),
        )
        self.assertEqual(
            tuple(item.value for item in ExpirationPayoffThresholdStatus),
            ("available", "unavailable_negative_underlying_price"),
        )
        self.assertEqual(
            tuple(inspect.signature(
                transform_expiration_payoff_thresholds
            ).parameters),
            ("calculation_id", "structure_costs_result", "calculated_at"),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(ExactRational)),
            ("numerator", "denominator"),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                ExpirationPayoffThreshold
            )),
            (
                "position_value_multiple",
                "side",
                "status",
                "target_position_value",
                "threshold_underlying_price",
                "absolute_move_from_base",
                "relative_move_from_base",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                ExpirationPayoffThresholdEvidence
            )),
            (
                "structure",
                "as_of_date",
                "base_underlying_price",
                "total_entry_cost",
                "thresholds",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                ExpirationPayoffThresholdTransformationResult
            )),
            ("record", "lineage"),
        )
        for name in transformations.__all__[-10:-3]:
            self.assertFalse(hasattr(convexity_hunter, name))

    def test_direct_imports_are_the_module_objects(self):
        self.assertIs(ExactRational, transformations.ExactRational)
        self.assertIs(
            ExpirationPayoffThresholdEvidence,
            transformations.ExpirationPayoffThresholdEvidence,
        )
        self.assertIs(
            transform_expiration_payoff_thresholds,
            transformations.transform_expiration_payoff_thresholds,
        )


class ExactRationalContractTests(unittest.TestCase):
    def test_reduction_zero_sign_equality_hashing_and_freezing(self):
        self.assertEqual(ExactRational(6, 8), ExactRational(3, 4))
        self.assertEqual(hash(ExactRational(6, 8)), hash(ExactRational(3, 4)))
        self.assertEqual(ExactRational(-6, 8), ExactRational(-3, 4))
        self.assertEqual(ExactRational(0, 999), ExactRational(0, 1))
        with self.assertRaises(FrozenInstanceError):
            ExactRational(1, 2).numerator = 2

    def test_exact_field_and_denominator_rejections(self):
        for numerator, denominator, error in (
            (True, 1, TypeError),
            (1, True, TypeError),
            (1.0, 1, TypeError),
            (1, 1.0, TypeError),
            (1, 0, ValueError),
            (1, -2, ValueError),
        ):
            with self.subTest(
                numerator=numerator, denominator=denominator
            ), self.assertRaises(error):
                ExactRational(numerator, denominator)

    def test_exact_finite_decimal_conversion_literals(self):
        cases = (
            ("123.4500", ExactRational(2469, 20)),
            ("-0.00000125", ExactRational(-1, 800000)),
            ("0E+100", ExactRational(0, 1)),
            ("1E-1000", ExactRational(1, 10 ** 1000)),
            ("9.99E+1000", ExactRational(999 * 10 ** 998, 1)),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(
                    transformations._exact_rational_from_decimal(
                        decimal.Decimal(text)
                    ),
                    expected,
                )
        with self.assertRaises(TypeError):
            transformations._exact_rational_from_decimal(1.25)
        for text in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(ValueError):
                transformations._exact_rational_from_decimal(
                    decimal.Decimal(text)
                )

    def test_extreme_exponents_are_accepted_exactly_without_context_change(self):
        before = decimal_context_state()
        positive = transformations._exact_rational_from_decimal(
            decimal.Decimal("1E+100001")
        )
        negative = transformations._exact_rational_from_decimal(
            decimal.Decimal("1E-100001")
        )
        self.assertEqual(positive, ExactRational(10 ** 100001, 1))
        self.assertEqual(negative, ExactRational(1, 10 ** 100001))
        self.assertEqual(
            transformations._exact_rational_from_decimal(
                decimal.Decimal("-123456789012345678901234567890E+250")
            ),
            ExactRational(
                -123456789012345678901234567890 * 10 ** 250,
                1,
            ),
        )
        self.assertEqual(hash(positive), hash(ExactRational(10 ** 100001, 1)))
        self.assertEqual(decimal_context_state(), before)


class ExpirationPayoffThresholdLiteralEconomicsTests(unittest.TestCase):
    def test_long_call_literal_1x_2x_5x_10x_values_and_moves(self):
        result = make_expiration_threshold_result(("call",))
        self.assertEqual(result.record.base_underlying_price, decimal.Decimal("100"))
        self.assertEqual(result.record.total_entry_cost, decimal.Decimal("141.250"))
        self.assertEqual(
            tuple(
                (
                    item.position_value_multiple,
                    item.side,
                    item.target_position_value,
                    item.threshold_underlying_price,
                    item.absolute_move_from_base,
                    item.relative_move_from_base,
                )
                for item in result.record.thresholds
            ),
            (
                (1, ExpirationPayoffThresholdSide.UPSIDE,
                 ExactRational(565, 4), ExactRational(8113, 80),
                 ExactRational(113, 80), ExactRational(113, 8000)),
                (2, ExpirationPayoffThresholdSide.UPSIDE,
                 ExactRational(565, 2), ExactRational(4113, 40),
                 ExactRational(113, 40), ExactRational(113, 4000)),
                (5, ExpirationPayoffThresholdSide.UPSIDE,
                 ExactRational(2825, 4), ExactRational(1713, 16),
                 ExactRational(113, 16), ExactRational(113, 1600)),
                (10, ExpirationPayoffThresholdSide.UPSIDE,
                 ExactRational(2825, 2), ExactRational(913, 8),
                 ExactRational(113, 8), ExactRational(113, 800)),
            ),
        )

    def test_long_put_literal_values_and_signed_moves(self):
        result = make_expiration_threshold_result(("put",))
        self.assertEqual(
            tuple(
                (
                    item.position_value_multiple,
                    item.side,
                    item.threshold_underlying_price,
                    item.absolute_move_from_base,
                    item.relative_move_from_base,
                )
                for item in result.record.thresholds
            ),
            (
                (1, ExpirationPayoffThresholdSide.DOWNSIDE,
                 ExactRational(7887, 80), ExactRational(-113, 80),
                 ExactRational(-113, 8000)),
                (2, ExpirationPayoffThresholdSide.DOWNSIDE,
                 ExactRational(3887, 40), ExactRational(-113, 40),
                 ExactRational(-113, 4000)),
                (5, ExpirationPayoffThresholdSide.DOWNSIDE,
                 ExactRational(1487, 16), ExactRational(-113, 16),
                 ExactRational(-113, 1600)),
                (10, ExpirationPayoffThresholdSide.DOWNSIDE,
                 ExactRational(687, 8), ExactRational(-113, 8),
                 ExactRational(-113, 800)),
            ),
        )

    def test_straddle_literal_order_and_both_branches(self):
        result = make_expiration_threshold_result(("put", "call"))
        self.assertEqual(len(result.record.thresholds), 8)
        self.assertEqual(
            tuple(
                (item.position_value_multiple, item.side)
                for item in result.record.thresholds
            ),
            (
                (1, ExpirationPayoffThresholdSide.DOWNSIDE),
                (1, ExpirationPayoffThresholdSide.UPSIDE),
                (2, ExpirationPayoffThresholdSide.DOWNSIDE),
                (2, ExpirationPayoffThresholdSide.UPSIDE),
                (5, ExpirationPayoffThresholdSide.DOWNSIDE),
                (5, ExpirationPayoffThresholdSide.UPSIDE),
                (10, ExpirationPayoffThresholdSide.DOWNSIDE),
                (10, ExpirationPayoffThresholdSide.UPSIDE),
            ),
        )
        self.assertEqual(
            tuple(item.threshold_underlying_price
                  for item in result.record.thresholds[:2]),
            (ExactRational(7679, 80), ExactRational(8321, 80)),
        )

    def test_quantity_three_nonterminating_distance_and_scaling(self):
        quantity_three = make_expiration_threshold_result(
            ("call",), quantity=3
        )
        multiplier_twenty_five = make_expiration_threshold_result(
            ("call",), multiplier=25
        )
        self.assertEqual(
            quantity_three.record.thresholds[0].threshold_underlying_price,
            ExactRational(24337, 240),
        )
        self.assertEqual(
            multiplier_twenty_five.record.thresholds[0]
            .threshold_underlying_price,
            ExactRational(2029, 20),
        )

    def test_total_entry_cost_includes_spread_commissions_and_fees(self):
        no_fee = make_expiration_threshold_result(
            ("call",), commissions_and_fees=decimal.Decimal("0")
        )
        with_fee = make_expiration_threshold_result(
            ("call",), commissions_and_fees=decimal.Decimal("7.50")
        )
        self.assertEqual(no_fee.record.total_entry_cost, decimal.Decimal("140.00"))
        self.assertEqual(
            with_fee.record.total_entry_cost, decimal.Decimal("147.500")
        )
        self.assertEqual(
            no_fee.record.thresholds[0].threshold_underlying_price,
            ExactRational(507, 5),
        )
        self.assertEqual(
            with_fee.record.thresholds[0].threshold_underlying_price,
            ExactRational(4059, 40),
        )

    def test_side_is_not_the_move_sign(self):
        structure = make_structure(("call",))
        selection, _, _, _ = make_cost_selection(
            structure, underlying_bid="119", underlying_ask="121"
        )
        costs = transform_costs(
            structure, selection, commissions_and_fees=decimal.Decimal("0")
        )
        result = transform_expiration_payoff_thresholds(
            "threshold-opposite-move",
            costs,
            CALCULATED_AT + datetime.timedelta(seconds=1),
        )
        first = result.record.thresholds[0]
        self.assertIs(first.side, ExpirationPayoffThresholdSide.UPSIDE)
        self.assertEqual(first.absolute_move_from_base, ExactRational(-93, 5))
        self.assertEqual(first.relative_move_from_base, ExactRational(-31, 200))


class ExpirationPayoffThresholdDomainAndRecordTests(unittest.TestCase):
    def test_zero_lower_root_is_available_and_negative_roots_are_explicit(self):
        put = make_expiration_threshold_result(
            ("put",), commissions_and_fees=decimal.Decimal("9860")
        )
        self.assertEqual(
            put.record.thresholds[0].threshold_underlying_price,
            ExactRational(0, 1),
        )
        self.assertIs(
            put.record.thresholds[0].status,
            ExpirationPayoffThresholdStatus.AVAILABLE,
        )
        for item in put.record.thresholds[1:]:
            self.assertIs(
                item.status,
                ExpirationPayoffThresholdStatus
                .UNAVAILABLE_NEGATIVE_UNDERLYING_PRICE,
            )
            self.assertIsNone(item.threshold_underlying_price)
            self.assertIsNone(item.absolute_move_from_base)
            self.assertIsNone(item.relative_move_from_base)
        decoded = transformations._decode_expiration_threshold_parameters(
            put.lineage.parameters_json
        )
        self.assertEqual(
            decoded["calculation_values"][1]
            ["unconstrained_threshold_underlying_price"],
            {"numerator": -100, "denominator": 1},
        )

    def test_straddle_retains_unavailable_downside_in_canonical_position(self):
        result = make_expiration_threshold_result(
            ("call", "put"),
            commissions_and_fees=decimal.Decimal("19860"),
        )
        for index in range(0, 8, 2):
            self.assertIs(
                result.record.thresholds[index].status,
                ExpirationPayoffThresholdStatus
                .UNAVAILABLE_NEGATIVE_UNDERLYING_PRICE,
            )
            self.assertIs(
                result.record.thresholds[index + 1].status,
                ExpirationPayoffThresholdStatus.AVAILABLE,
            )

    def test_threshold_record_status_type_and_optional_invariants(self):
        available = make_expiration_threshold_result(
            ("call",)
        ).record.thresholds[0]
        mutations = (
            ({"position_value_multiple": True}, TypeError),
            ({"position_value_multiple": 3}, ValueError),
            ({"side": "upside"}, TypeError),
            ({"status": "available"}, TypeError),
            ({"target_position_value": ExactRational(0, 1)}, ValueError),
            ({"threshold_underlying_price": None}, TypeError),
            ({"threshold_underlying_price": ExactRational(-1, 1)}, ValueError),
        )
        for changes, error in mutations:
            with self.subTest(changes=changes), self.assertRaises(error):
                dataclasses.replace(available, **changes)
        with self.assertRaises(ValueError):
            ExpirationPayoffThreshold(
                1,
                ExpirationPayoffThresholdSide.UPSIDE,
                ExpirationPayoffThresholdStatus
                .UNAVAILABLE_NEGATIVE_UNDERLYING_PRICE,
                ExactRational(1, 1),
                None,
                None,
                None,
            )

    def test_evidence_rejects_wrong_types_order_cardinality_and_formulas(self):
        result = make_expiration_threshold_result(("call",))
        record = result.record
        cases = (
            ({"as_of_date": datetime.datetime.combine(
                record.as_of_date, datetime.time()
            )}, TypeError),
            ({"base_underlying_price": 100}, TypeError),
            ({"total_entry_cost": decimal.Decimal("0")}, ValueError),
            ({"thresholds": list(record.thresholds)}, TypeError),
            ({"thresholds": record.thresholds[:-1]}, ValueError),
            ({"thresholds": tuple(reversed(record.thresholds))}, ValueError),
            ({"thresholds": (
                dataclasses.replace(
                    record.thresholds[0],
                    absolute_move_from_base=ExactRational(999, 1),
                ),
            ) + record.thresholds[1:]}, ValueError),
        )
        for changes, error in cases:
            with self.subTest(changes=tuple(changes)), self.assertRaises(error):
                dataclasses.replace(record, **changes)
        with self.assertRaises(FrozenInstanceError):
            record.total_entry_cost = decimal.Decimal("1")

    def assert_forged_nested_value_rejects(self, result, **record_changes):
        with self.assertRaises((TypeError, ValueError)):
            dataclasses.replace(result.record, **record_changes)
        forged_record = bypass_frozen_dataclass(
            result.record, **record_changes
        )
        with self.assertRaises((TypeError, ValueError)):
            ExpirationPayoffThresholdTransformationResult(
                forged_record, result.lineage
            )

    def test_bypassed_threshold_and_rational_objects_reject_strictly(self):
        result = make_expiration_threshold_result(("call",))
        first = result.record.thresholds[0]
        forged_multiple = bypass_frozen_dataclass(
            first, position_value_multiple=True
        )
        self.assert_forged_nested_value_rejects(
            result,
            thresholds=(forged_multiple,) + result.record.thresholds[1:],
        )

        class IntSubclass(int):
            pass

        forged_rational = bypass_frozen_dataclass(
            first.target_position_value,
            numerator=IntSubclass(first.target_position_value.numerator),
        )
        forged_target = bypass_frozen_dataclass(
            first, target_position_value=forged_rational
        )
        with self.assertRaises(TypeError):
            ExpirationPayoffThreshold(
                first.position_value_multiple,
                first.side,
                first.status,
                forged_rational,
                first.threshold_underlying_price,
                first.absolute_move_from_base,
                first.relative_move_from_base,
            )
        self.assert_forged_nested_value_rejects(
            result,
            thresholds=(forged_target,) + result.record.thresholds[1:],
        )

    def test_bypassed_structure_and_leg_objects_reject_strictly(self):
        result = make_expiration_threshold_result(("call",))
        structure = result.record.structure
        structure_mutations = (
            {"assumed_portfolio_value": math.nan},
            {"expected_holding_days": -1},
        )
        for changes in structure_mutations:
            forged = bypass_frozen_dataclass(structure, **changes)
            with self.subTest(changes=changes):
                self.assert_forged_nested_value_rejects(
                    result, structure=forged
                )

        leg = structure.legs[0]
        for underlying in ("", " spy ", "spy"):
            forged_leg = bypass_frozen_dataclass(
                leg, underlying=underlying
            )
            forged_structure = bypass_frozen_dataclass(
                structure, legs=(forged_leg,)
            )
            with self.subTest(underlying=underlying):
                self.assert_forged_nested_value_rejects(
                    result, structure=forged_structure
                )
        forged_quantity = bypass_frozen_dataclass(leg, quantity=True)
        forged_structure = bypass_frozen_dataclass(
            structure, legs=(forged_quantity,)
        )
        self.assert_forged_nested_value_rejects(
            result, structure=forged_structure
        )


class ExpirationPayoffThresholdLineageTrustTests(unittest.TestCase):
    def test_authentic_wrapper_reconstruction_and_identity(self):
        result = make_expiration_threshold_result(("call",))
        rebuilt = ExpirationPayoffThresholdTransformationResult(
            result.record, result.lineage
        )
        self.assertIs(rebuilt.record, result.record)
        self.assertEqual(
            (
                result.lineage.calculation_type,
                result.lineage.methodology_id,
                result.lineage.methodology_version,
            ),
            (
                "expiration_payoff_thresholds",
                "closed-form-terminal-intrinsic-position-value-multiples",
                "v0.1",
            ),
        )
        self.assertEqual(
            result.lineage.quality_flags,
            (CalculationQualityFlag.ASSUMPTION_APPLIED,),
        )

    def test_canonical_top_nested_and_calculation_mutations_reject(self):
        result = make_expiration_threshold_result(("call",))
        mutations = (
            lambda value: value.pop("limitations"),
            lambda value: value.__setitem__("extra", True),
            lambda value: value["calculation_values"][0].__setitem__(
                "position_value_multiple", True
            ),
            lambda value: value.__setitem__(
                "target_multiples", (True, 2, 5, 10)
            ),
            lambda value: value["numeric_representation"].__setitem__(
                "reduced", 1
            ),
            lambda value: value["calculation_values"][0][
                "position_scale"
            ].__setitem__("quantity", True),
            lambda value: value["solution_domain"].__setitem__(
                "zero_lower_threshold", False
            ),
            lambda value: value["structure_costs_dependency"].pop(
                "input_rule"
            ),
            lambda value: value["structure_costs_dependency"].__setitem__(
                "input_rule", "forged"
            ),
            lambda value: value["calculation_values"][0].pop("payoff_distance"),
            lambda value: value["calculation_values"][0].__setitem__(
                "extra", 1
            ),
            lambda value: value["calculation_values"][0]
            ["threshold_underlying_price"].__setitem__("denominator", 160),
            lambda value: value["calculation_values"][0].__setitem__(
                "target_position_value",
                {"numerator": 1130, "denominator": 8},
            ),
            lambda value: value["calculation_values"][0].__setitem__(
                "target_position_value",
                {"numerator": 565, "denominator": 0},
            ),
            lambda value: value["calculation_values"][0].__setitem__(
                "target_position_value",
                {"numerator": 565, "denominator": -4},
            ),
            lambda value: value["calculation_values"][0].__setitem__(
                "target_position_value",
                {"numerator": True, "denominator": 4},
            ),
            lambda value: value["calculation_values"][0].__setitem__(
                "side", "downside"
            ),
            lambda value: value["structure_costs_dependency"].__setitem__(
                "methodology_version", "v9"
            ),
            lambda value: value["structure_costs_dependency"].__setitem__(
                "calculated_at",
                result.lineage.calculated_at + datetime.timedelta(seconds=1),
            ),
            lambda value: value.__setitem__(
                "target_multiples", (1, 2, 10, 5)
            ),
            lambda value: value.__setitem__(
                "calculation_values",
                tuple(reversed(value["calculation_values"])),
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(
                (TypeError, ValueError)
            ):
                ExpirationPayoffThresholdTransformationResult(
                    result.record,
                    mutate_expiration_threshold_parameters(result, mutate),
                )

    def test_forged_retained_cost_parameters_and_public_record_reject(self):
        result = make_expiration_threshold_result(("call",))

        def forge_dependency(parameters):
            dependency = parameters["structure_costs_dependency"]
            decoded = transformations._decode_cost_parameters(
                dependency["parameters_json"]
            )
            decoded["calculation_values"]["total_entry_cost_exact"] = (
                decimal.Decimal("999")
            )
            dependency["parameters_json"] = (
                market_data.canonicalize_lineage_parameters(decoded)
            )

        with self.assertRaises(ValueError):
            ExpirationPayoffThresholdTransformationResult(
                result.record,
                mutate_expiration_threshold_parameters(
                    result, forge_dependency
                ),
            )
        forged_record = object.__new__(ExpirationPayoffThresholdEvidence)
        for field in dataclasses.fields(result.record):
            object.__setattr__(
                forged_record, field.name, getattr(result.record, field.name)
            )
        object.__setattr__(
            forged_record,
            "total_entry_cost",
            decimal.Decimal("999"),
        )
        with self.assertRaises(ValueError):
            ExpirationPayoffThresholdTransformationResult(
                forged_record, result.lineage
            )

    def test_wrong_identity_chronology_inputs_and_quality_flags_reject(self):
        result = make_expiration_threshold_result(("call",))
        cases = (
            {"methodology_version": "v9"},
            {"calculation_id": "calculation-3c7b"},
            {"calculated_at": CALCULATED_AT - datetime.timedelta(seconds=1)},
            {"quality_flags": ()},
            {"quality_flags": (
                CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                CalculationQualityFlag.ASSUMPTION_APPLIED,
            )},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ExpirationPayoffThresholdTransformationResult(
                    result.record, dataclasses.replace(result.lineage, **changes)
                )
        extra_input = CalculationInputReference(
            "extra-input",
            CALCULATED_AT - datetime.timedelta(days=1),
            ("extra-source",),
        )
        with self.assertRaises(ValueError):
            ExpirationPayoffThresholdTransformationResult(
                result.record,
                dataclasses.replace(
                    result.lineage,
                    inputs=result.lineage.inputs + (extra_input,),
                ),
            )

    def test_quality_flag_propagation_is_exact_and_excludes_cost_float_flag(self):
        structure = make_structure(("call",))
        selection, _, _, _ = make_cost_selection(structure)
        original = transform_costs(structure, selection)
        cases = (
            ("interpolated", CalculationQualityFlag.INTERPOLATED),
            ("correction_selected", CalculationQualityFlag.CORRECTION_SELECTED),
            (
                "composite_input_used",
                CalculationQualityFlag.COMPOSITE_INPUT_USED,
            ),
        )
        for disclosed, flag in cases:
            decoded = transformations._decode_cost_parameters(
                original.lineage.parameters_json
            )
            decoded["normalized_evidence"]["underlying_quote"][
                "propagated_quality_flags"
            ] = (disclosed,)
            dependency_lineage = dataclasses.replace(
                original.lineage,
                parameters_json=market_data.canonicalize_lineage_parameters(
                    decoded
                ),
                quality_flags=(
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                    flag,
                    CalculationQualityFlag.ASSUMPTION_APPLIED,
                ),
            )
            dependency = StructureCostsTransformationResult(
                original.record, dependency_lineage
            )
            result = transform_expiration_payoff_thresholds(
                f"threshold-{disclosed}",
                dependency,
                CALCULATED_AT + datetime.timedelta(seconds=1),
            )
            with self.subTest(flag=flag):
                self.assertEqual(
                    result.lineage.quality_flags,
                    tuple(
                        item
                        for item in CalculationQualityFlag
                        if item in {
                            flag,
                            CalculationQualityFlag.ASSUMPTION_APPLIED,
                        }
                    ),
                )
                self.assertNotIn(
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                    result.lineage.quality_flags,
                )

    def test_duplicate_float_and_malformed_tag_json_reject(self):
        result = make_expiration_threshold_result(("call",))
        malformed = (
            '{"$map":[],"$map":[]}',
            '{"$map":[["x",1.5]]}',
            '{"$map":[["x",{"$rational":"1/2"}]]}',
            '{"$map":[["x",{"$decimal":"NaN"}]]}',
            '{"$map":[["x",{"$datetime":"2026-01-01"}]]}',
        )
        for text in malformed:
            forged = object.__new__(CalculationLineage)
            for field in dataclasses.fields(result.lineage):
                object.__setattr__(
                    forged, field.name, getattr(result.lineage, field.name)
                )
            object.__setattr__(forged, "parameters_json", text)
            with self.subTest(text=text), self.assertRaises(ValueError):
                ExpirationPayoffThresholdTransformationResult(
                    result.record, forged
                )


class ExpirationPayoffThresholdExecutionPropertiesTests(unittest.TestCase):
    def test_exact_argument_types_ids_and_chronology(self):
        result = make_expiration_threshold_result(("call",))
        structure = make_structure(("call",))
        selection, _, _, _ = make_cost_selection(structure)
        costs = transform_costs(structure, selection)
        cases = (
            ((1, costs, CALCULATED_AT), TypeError),
            (("x", object(), CALCULATED_AT), TypeError),
            (("x", costs, SESSION_DATE), TypeError),
            ((" ", costs, CALCULATED_AT), ValueError),
            (("calculation-3c7b", costs, CALCULATED_AT), ValueError),
            (("cost-underlying-quote", costs, CALCULATED_AT), ValueError),
            (("x", costs, CALCULATED_AT - datetime.timedelta(days=1)),
             ValueError),
        )
        for arguments, error in cases:
            with self.subTest(arguments=arguments), self.assertRaises(error):
                transform_expiration_payoff_thresholds(*arguments)
        self.assertTrue(result.record.thresholds)

    def test_dependency_validation_precedes_arithmetic_and_new_constructors(self):
        valid = make_expiration_threshold_result(("call",))
        dependency = transformations._expiration_threshold_dependency_from_disclosure(
            valid.record,
            valid.lineage,
            transformations._decode_expiration_threshold_parameters(
                valid.lineage.parameters_json
            )["structure_costs_dependency"],
        )
        invalid_lineage = dataclasses.replace(
            dependency.lineage, methodology_version="v9"
        )
        invalid_dependency = object.__new__(StructureCostsTransformationResult)
        object.__setattr__(
            invalid_dependency, "record", dependency.record
        )
        object.__setattr__(invalid_dependency, "lineage", invalid_lineage)
        with mock.patch.object(
            transformations,
            "_expected_expiration_thresholds",
            side_effect=AssertionError("arithmetic reached"),
        ), mock.patch.object(
            transformations,
            "ExpirationPayoffThresholdEvidence",
            side_effect=AssertionError("evidence constructor reached"),
        ), mock.patch.object(
            transformations,
            "_construct_expiration_threshold_lineage",
            side_effect=AssertionError("new lineage constructor reached"),
        ):
            with self.assertRaises((TypeError, ValueError)):
                transform_expiration_payoff_thresholds(
                    "new-thresholds",
                    invalid_dependency,
                    CALCULATED_AT + datetime.timedelta(seconds=1),
                )

    def test_determinism_isolation_and_decimal_context_preservation(self):
        structure = make_structure(("call", "put"))
        selection, _, _, _ = make_cost_selection(structure)
        costs = transform_costs(structure, selection)
        arguments = (
            "threshold-determinism",
            costs,
            CALCULATED_AT + datetime.timedelta(seconds=1),
        )
        original = decimal.getcontext().copy()
        configured = decimal.Context(
            prec=7,
            rounding=decimal.ROUND_UP,
            Emin=-17,
            Emax=19,
            capitals=0,
            clamp=1,
        )
        configured.traps[decimal.Inexact] = True
        configured.flags[decimal.Rounded] = True
        try:
            decimal.setcontext(configured)
            before = decimal_context_state()
            first = transform_expiration_payoff_thresholds(*arguments)
            second = transform_expiration_payoff_thresholds(*arguments)
            self.assertEqual(first, second)
            self.assertEqual(decimal_context_state(), before)
            with self.assertRaises(ValueError):
                transform_expiration_payoff_thresholds(
                    " ",
                    costs,
                    arguments[2],
                )
            self.assertEqual(decimal_context_state(), before)
        finally:
            decimal.setcontext(original)

        blocked = (
            "transform_scenario_valuation",
            "transform_tail_pricing",
            "transform_volatility_environment",
            "black_scholes",
            "provider",
            "network",
        )
        with ExitStack() as stack:
            for name in blocked:
                stack.enter_context(mock.patch.object(
                    transformations,
                    name,
                    side_effect=AssertionError(f"{name} called"),
                    create=True,
                ))
            self.assertTrue(
                transform_expiration_payoff_thresholds(*arguments)
                .record.thresholds
            )



EXPECTED_VOLATILITY_ENVIRONMENT_V02_JSON = '{"$map":[["atm_candidate_universe",{"$map":[["completeness_semantics","no_eligible_paired_call_put_strike_omitted"],["declared_complete",true],["scope","all_exact_selected_session_expiration_universes"]]}],["atm_selection_rule","nearest_paired_call_put_strike_to_underlying_bid_ask_midpoint"],["call_put_combination_rule","arithmetic_mean_of_same_strike_call_and_put_implied_volatility"],["current_observations",{"$list":[{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","ve-current-0-call-reference"],["call_implied_volatility",{"$decimal":"0.3"}],["call_iv_record_id","ve-current-0-call-iv"],["call_quote_record_id","ve-current-0-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.30"}],["put_contract_reference_record_id","ve-current-0-put-reference"],["put_implied_volatility",{"$decimal":"0.3"}],["put_iv_record_id","ve-current-0-put-iv"],["put_quote_record_id","ve-current-0-put-quote"],["strike",{"$decimal":"100"}]]}]}],["expiration",{"$date":"2030-02-01"}],["selected_atm_iv",{"$decimal":"0.30"}],["selected_call_iv_record_id","ve-current-0-call-iv"],["selected_put_iv_record_id","ve-current-0-put-iv"],["selected_strike",{"$decimal":"100"}],["session_date",{"$date":"2030-01-02"}],["tenor_days",30],["underlying_midpoint",{"$decimal":"100.0"}],["underlying_quote_record_id","ve-current-underlying"]]},{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","ve-current-1-call-reference"],["call_implied_volatility",{"$decimal":"0.4"}],["call_iv_record_id","ve-current-1-call-iv"],["call_quote_record_id","ve-current-1-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.40"}],["put_contract_reference_record_id","ve-current-1-put-reference"],["put_implied_volatility",{"$decimal":"0.4"}],["put_iv_record_id","ve-current-1-put-iv"],["put_quote_record_id","ve-current-1-put-quote"],["strike",{"$decimal":"100"}]]}]}],["expiration",{"$date":"2030-03-03"}],["selected_atm_iv",{"$decimal":"0.40"}],["selected_call_iv_record_id","ve-current-1-call-iv"],["selected_put_iv_record_id","ve-current-1-put-iv"],["selected_strike",{"$decimal":"100"}],["session_date",{"$date":"2030-01-02"}],["tenor_days",60],["underlying_midpoint",{"$decimal":"100.0"}],["underlying_quote_record_id","ve-current-underlying"]]}]}],["float_conversion_rule","convert_only_final_decimal_research_values_to_finite_float"],["historical_expected_session_dates",{"$list":[{"$date":"2029-12-30"}]}],["historical_matched_tenor_rule","expiration_minus_session_date_calendar_days_equals_reference_tenor"],["historical_observation_count",1],["historical_observations",{"$list":[{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","ve-history-0-0-call-reference"],["call_implied_volatility",{"$decimal":"0.19"}],["call_iv_record_id","ve-history-0-0-call-iv"],["call_quote_record_id","ve-history-0-0-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.200"}],["put_contract_reference_record_id","ve-history-0-0-put-reference"],["put_implied_volatility",{"$decimal":"0.21"}],["put_iv_record_id","ve-history-0-0-put-iv"],["put_quote_record_id","ve-history-0-0-put-quote"],["strike",{"$decimal":"100"}]]}]}],["expiration",{"$date":"2030-01-29"}],["selected_atm_iv",{"$decimal":"0.200"}],["selected_call_iv_record_id","ve-history-0-0-call-iv"],["selected_put_iv_record_id","ve-history-0-0-put-iv"],["selected_strike",{"$decimal":"100"}],["session_date",{"$date":"2029-12-30"}],["tenor_days",30],["underlying_midpoint",{"$decimal":"100.0"}],["underlying_quote_record_id","ve-history-0-underlying"]]}]}],["historical_sample_semantics","caller_declared_observation_sample"],["iv_methodology",{"$map":[["dividend_input_description","Synthetic dividend input"],["model_name","Synthetic Black-Scholes"],["model_version","fixture-v1"],["rate_input_description","Synthetic USD curve input"],["unit_convention","annualized_decimal_ratio"]]}],["median_formula","odd_middle_even_arithmetic_mean_of_two_middle_values"],["normalized_evidence",{"$map":[["direct_inputs",{"$list":[{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-call-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-current-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-call-quote"],["role","option_quote"],["source_ids",{"$list":["ve-current-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-call-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-current-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-put-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-current-0-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-put-quote"],["role","option_quote"],["source_ids",{"$list":["ve-current-0-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-put-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-current-0-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-call-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-current-1-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-call-quote"],["role","option_quote"],["source_ids",{"$list":["ve-current-1-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-call-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-current-1-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-put-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-current-1-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-put-quote"],["role","option_quote"],["source_ids",{"$list":["ve-current-1-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-put-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-current-1-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-underlying"],["role","underlying_quote"],["source_ids",{"$list":["ve-current-underlying-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-call-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-history-0-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-call-quote"],["role","option_quote"],["source_ids",{"$list":["ve-history-0-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-call-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-history-0-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-put-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-history-0-0-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-put-quote"],["role","option_quote"],["source_ids",{"$list":["ve-history-0-0-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-put-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-history-0-0-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-underlying"],["role","underlying_quote"],["source_ids",{"$list":["ve-history-0-underlying-source-0"]}]]}]}]]}],["percentile_formula","inclusive_count_historical_atm_iv_lte_current_reference_atm_iv_divided_by_count"],["realized_volatility_dependency",{"$map":[["adjustment_methodology",null],["annualization_sessions_per_year",252],["annualized_realized_volatility_float_repr","0.3328756933888896"],["calculated_at",{"$datetime":"2030-01-02T15:30:04.000000Z"}],["calculation_id","calculation-3c7c"],["calculation_type","historical_realized_volatility"],["end_session_date",{"$date":"2030-01-02"}],["inputs",{"$list":[{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-0"],["source_ids",{"$list":["hrv-0-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-1"],["source_ids",{"$list":["hrv-1-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-2"],["source_ids",{"$list":["hrv-2-source-0"]}]]}]}],["log_returns",{"$list":[{"$decimal":"0.01980262729617971302602906688510039"},{"$decimal":"-0.009852296443011630177813709340839653"}]}],["methodology_id","historical-log-return-sample-realized-volatility"],["methodology_version","v0.1"],["parameters_json","{\\"$map\\":[[\\"adjustment_methodology\\",null],[\\"annualization_rule\\",\\"daily_sample_standard_deviation_times_square_root_sessions_per_year\\"],[\\"annualization_sessions_per_year\\",252],[\\"expected_session_dates\\",{\\"$list\\":[{\\"$date\\":\\"2029-12-03\\"},{\\"$date\\":\\"2029-12-18\\"},{\\"$date\\":\\"2030-01-02\\"}]}],[\\"price_basis\\",\\"raw_close\\"],[\\"price_observation_count\\",3],[\\"price_unit\\",\\"usd_per_underlying_share\\"],[\\"return_association_rule\\",\\"ending_session\\"],[\\"return_formula\\",\\"natural_log_price_ratio\\"],[\\"return_observation_count\\",2],[\\"return_unit\\",\\"decimal_ratio\\"],[\\"underlying\\",{\\"$map\\":[[\\"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"symbol\\",\\"SPY\\"]]}],[\\"variance_estimator\\",\\"sample_variance\\"],[\\"volatility_unit\\",\\"annualized_decimal_ratio\\"],[\\"window_end_session_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"window_start_session_date\\",{\\"$date\\":\\"2029-12-03\\"}]]}"],["price_basis","raw_close"],["price_observation_count",3],["prices",{"$list":[{"$decimal":"100"},{"$decimal":"102"},{"$decimal":"101"}]}],["quality_flags",{"$list":["decimal_to_float_converted","annualized","assumption_applied"]}],["return_formula","natural_log_price_ratio"],["return_observation_count",2],["session_dates",{"$list":[{"$date":"2029-12-03"},{"$date":"2029-12-18"},{"$date":"2030-01-02"}]}],["start_session_date",{"$date":"2029-12-03"}],["underlying",{"$map":[["currency","USD"],["listing_mic","ARCX"],["security_type","etf"],["symbol","SPY"]]}],["variance_estimator","sample_variance"]]}],["realized_window_matching_rule","realized_end_equals_current_as_of_and_calendar_span_equals_reference_tenor"],["reference_tenor_days",30],["strike_tie_rule","lower_strike"],["term_tenor_rule","expiration_minus_session_date_calendar_days"],["underlying_midpoint_rule","bid_ask_midpoint_no_last_fallback"],["volatility_unit","annualized_decimal_ratio"]]}'
EXPECTED_TAIL_PRICING_V02_JSON = '{"$map":[["analytics_methodology",{"$map":[["greeks_dividend_input_description","Synthetic dividend input"],["greeks_model_name","Synthetic Black-Scholes"],["greeks_model_version","fixture-v1"],["greeks_rate_input_description","Synthetic USD curve input"],["greeks_unit_convention","Contract-defined canonical units"],["iv_dividend_input_description","Synthetic dividend input"],["iv_model_name","Synthetic Black-Scholes"],["iv_model_version","fixture-v1"],["iv_rate_input_description","Synthetic USD curve input"],["iv_unit_convention","annualized_decimal_ratio"]]}],["atm_dependency",{"$map":[["as_of_date",{"$date":"2030-01-02"}],["calculated_at",{"$datetime":"2030-01-02T15:30:04.000000Z"}],["calculation_id","calculation-3c7d"],["calculation_type","volatility_environment"],["current_atm_observations",{"$list":[{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","ve-current-0-call-reference"],["call_implied_volatility",{"$decimal":"0.30"}],["call_iv_record_id","ve-current-0-call-iv"],["call_quote_record_id","ve-current-0-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.300"}],["put_contract_reference_record_id","ve-current-0-put-reference"],["put_implied_volatility",{"$decimal":"0.30"}],["put_iv_record_id","ve-current-0-put-iv"],["put_quote_record_id","ve-current-0-put-quote"],["strike",{"$decimal":"100"}]]}]}],["expiration",{"$date":"2030-02-01"}],["selected_atm_iv",{"$decimal":"0.300"}],["selected_call_iv_record_id","ve-current-0-call-iv"],["selected_put_iv_record_id","ve-current-0-put-iv"],["selected_strike",{"$decimal":"100"}],["session_date",{"$date":"2030-01-02"}],["tenor_days",30],["underlying_midpoint",{"$decimal":"100.0"}],["underlying_quote_record_id","ve-current-underlying"]]},{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","ve-current-1-call-reference"],["call_implied_volatility",{"$decimal":"0.40"}],["call_iv_record_id","ve-current-1-call-iv"],["call_quote_record_id","ve-current-1-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.400"}],["put_contract_reference_record_id","ve-current-1-put-reference"],["put_implied_volatility",{"$decimal":"0.40"}],["put_iv_record_id","ve-current-1-put-iv"],["put_quote_record_id","ve-current-1-put-quote"],["strike",{"$decimal":"100"}]]}]}],["expiration",{"$date":"2030-03-03"}],["selected_atm_iv",{"$decimal":"0.400"}],["selected_call_iv_record_id","ve-current-1-call-iv"],["selected_put_iv_record_id","ve-current-1-put-iv"],["selected_strike",{"$decimal":"100"}],["session_date",{"$date":"2030-01-02"}],["tenor_days",60],["underlying_midpoint",{"$decimal":"100.0"}],["underlying_quote_record_id","ve-current-underlying"]]}]}],["historical_atm_observations",{"$list":[{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","ve-history-0-0-call-reference"],["call_implied_volatility",{"$decimal":"0.19"}],["call_iv_record_id","ve-history-0-0-call-iv"],["call_quote_record_id","ve-history-0-0-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.200"}],["put_contract_reference_record_id","ve-history-0-0-put-reference"],["put_implied_volatility",{"$decimal":"0.21"}],["put_iv_record_id","ve-history-0-0-put-iv"],["put_quote_record_id","ve-history-0-0-put-quote"],["strike",{"$decimal":"100"}]]}]}],["expiration",{"$date":"2030-01-29"}],["selected_atm_iv",{"$decimal":"0.200"}],["selected_call_iv_record_id","ve-history-0-0-call-iv"],["selected_put_iv_record_id","ve-history-0-0-put-iv"],["selected_strike",{"$decimal":"100"}],["session_date",{"$date":"2029-12-30"}],["tenor_days",30],["underlying_midpoint",{"$decimal":"100.0"}],["underlying_quote_record_id","ve-history-0-underlying"]]}]}],["historical_median_atm_iv_float_repr","0.2"],["historical_observation_count",1],["inputs",{"$list":[{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-0"],["source_ids",{"$list":["hrv-0-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-1"],["source_ids",{"$list":["hrv-1-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-2"],["source_ids",{"$list":["hrv-2-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-call-iv"],["source_ids",{"$list":["ve-current-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-call-quote"],["source_ids",{"$list":["ve-current-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-call-reference"],["source_ids",{"$list":["ve-current-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-put-iv"],["source_ids",{"$list":["ve-current-0-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-put-quote"],["source_ids",{"$list":["ve-current-0-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-put-reference"],["source_ids",{"$list":["ve-current-0-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-call-iv"],["source_ids",{"$list":["ve-current-1-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-call-quote"],["source_ids",{"$list":["ve-current-1-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-call-reference"],["source_ids",{"$list":["ve-current-1-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-put-iv"],["source_ids",{"$list":["ve-current-1-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-put-quote"],["source_ids",{"$list":["ve-current-1-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-put-reference"],["source_ids",{"$list":["ve-current-1-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-underlying"],["source_ids",{"$list":["ve-current-underlying-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-call-iv"],["source_ids",{"$list":["ve-history-0-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-call-quote"],["source_ids",{"$list":["ve-history-0-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-call-reference"],["source_ids",{"$list":["ve-history-0-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-put-iv"],["source_ids",{"$list":["ve-history-0-0-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-put-quote"],["source_ids",{"$list":["ve-history-0-0-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-put-reference"],["source_ids",{"$list":["ve-history-0-0-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-underlying"],["source_ids",{"$list":["ve-history-0-underlying-source-0"]}]]}]}],["iv_percentile_float_repr","1.0"],["matched_realized_volatility_float_repr","0.3328756933888896"],["matched_realized_window_days",30],["methodology_id","paired-atm-volatility-environment"],["methodology_version","v0.2"],["parameters_json","{\\"$map\\":[[\\"atm_candidate_universe\\",{\\"$map\\":[[\\"completeness_semantics\\",\\"no_eligible_paired_call_put_strike_omitted\\"],[\\"declared_complete\\",true],[\\"scope\\",\\"all_exact_selected_session_expiration_universes\\"]]}],[\\"atm_selection_rule\\",\\"nearest_paired_call_put_strike_to_underlying_bid_ask_midpoint\\"],[\\"call_put_combination_rule\\",\\"arithmetic_mean_of_same_strike_call_and_put_implied_volatility\\"],[\\"current_observations\\",{\\"$list\\":[{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve-current-0-call-reference\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"call_iv_record_id\\",\\"ve-current-0-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-current-0-call-quote\\"],[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.300\\"}],[\\"put_contract_reference_record_id\\",\\"ve-current-0-put-reference\\"],[\\"put_implied_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"put_iv_record_id\\",\\"ve-current-0-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-current-0-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"2030-02-01\\"}],[\\"selected_atm_iv\\",{\\"$decimal\\":\\"0.300\\"}],[\\"selected_call_iv_record_id\\",\\"ve-current-0-call-iv\\"],[\\"selected_put_iv_record_id\\",\\"ve-current-0-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"100\\"}],[\\"session_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"tenor_days\\",30],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-current-underlying\\"]]},{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve-current-1-call-reference\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.40\\"}],[\\"call_iv_record_id\\",\\"ve-current-1-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-current-1-call-quote\\"],[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.400\\"}],[\\"put_contract_reference_record_id\\",\\"ve-current-1-put-reference\\"],[\\"put_implied_volatility\\",{\\"$decimal\\":\\"0.40\\"}],[\\"put_iv_record_id\\",\\"ve-current-1-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-current-1-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"selected_atm_iv\\",{\\"$decimal\\":\\"0.400\\"}],[\\"selected_call_iv_record_id\\",\\"ve-current-1-call-iv\\"],[\\"selected_put_iv_record_id\\",\\"ve-current-1-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"100\\"}],[\\"session_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"tenor_days\\",60],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-current-underlying\\"]]}]}],[\\"float_conversion_rule\\",\\"convert_only_final_decimal_research_values_to_finite_float\\"],[\\"historical_expected_session_dates\\",{\\"$list\\":[{\\"$date\\":\\"2029-12-30\\"}]}],[\\"historical_matched_tenor_rule\\",\\"expiration_minus_session_date_calendar_days_equals_reference_tenor\\"],[\\"historical_observation_count\\",1],[\\"historical_observations\\",{\\"$list\\":[{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve-history-0-0-call-reference\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.19\\"}],[\\"call_iv_record_id\\",\\"ve-history-0-0-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-history-0-0-call-quote\\"],[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.200\\"}],[\\"put_contract_reference_record_id\\",\\"ve-history-0-0-put-reference\\"],[\\"put_implied_volatility\\",{\\"$decimal\\":\\"0.21\\"}],[\\"put_iv_record_id\\",\\"ve-history-0-0-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-history-0-0-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"2030-01-29\\"}],[\\"selected_atm_iv\\",{\\"$decimal\\":\\"0.200\\"}],[\\"selected_call_iv_record_id\\",\\"ve-history-0-0-call-iv\\"],[\\"selected_put_iv_record_id\\",\\"ve-history-0-0-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"100\\"}],[\\"session_date\\",{\\"$date\\":\\"2029-12-30\\"}],[\\"tenor_days\\",30],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-history-0-underlying\\"]]}]}],[\\"historical_sample_semantics\\",\\"caller_declared_observation_sample\\"],[\\"iv_methodology\\",{\\"$map\\":[[\\"dividend_input_description\\",\\"Synthetic dividend input\\"],[\\"model_name\\",\\"Synthetic Black-Scholes\\"],[\\"model_version\\",\\"fixture-v1\\"],[\\"rate_input_description\\",\\"Synthetic USD curve input\\"],[\\"unit_convention\\",\\"annualized_decimal_ratio\\"]]}],[\\"median_formula\\",\\"odd_middle_even_arithmetic_mean_of_two_middle_values\\"],[\\"normalized_evidence\\",{\\"$map\\":[[\\"direct_inputs\\",{\\"$list\\":[{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-call-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-call-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-put-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-call-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-call-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-put-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-underlying\\"],[\\"role\\",\\"underlying_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-underlying-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-call-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-call-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-put-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-underlying\\"],[\\"role\\",\\"underlying_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-underlying-source-0\\"]}]]}]}]]}],[\\"percentile_formula\\",\\"inclusive_count_historical_atm_iv_lte_current_reference_atm_iv_divided_by_count\\"],[\\"realized_volatility_dependency\\",{\\"$map\\":[[\\"adjustment_methodology\\",null],[\\"annualization_sessions_per_year\\",252],[\\"annualized_realized_volatility_float_repr\\",\\"0.3328756933888896\\"],[\\"calculated_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:04.000000Z\\"}],[\\"calculation_id\\",\\"calculation-3c7c\\"],[\\"calculation_type\\",\\"historical_realized_volatility\\"],[\\"end_session_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"inputs\\",{\\"$list\\":[{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"hrv-0\\"],[\\"source_ids\\",{\\"$list\\":[\\"hrv-0-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"hrv-1\\"],[\\"source_ids\\",{\\"$list\\":[\\"hrv-1-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"hrv-2\\"],[\\"source_ids\\",{\\"$list\\":[\\"hrv-2-source-0\\"]}]]}]}],[\\"log_returns\\",{\\"$list\\":[{\\"$decimal\\":\\"0.01980262729617971302602906688510039\\"},{\\"$decimal\\":\\"-0.009852296443011630177813709340839653\\"}]}],[\\"methodology_id\\",\\"historical-log-return-sample-realized-volatility\\"],[\\"methodology_version\\",\\"v0.1\\"],[\\"parameters_json\\",\\"{\\\\\\"$map\\\\\\":[[\\\\\\"adjustment_methodology\\\\\\",null],[\\\\\\"annualization_rule\\\\\\",\\\\\\"daily_sample_standard_deviation_times_square_root_sessions_per_year\\\\\\"],[\\\\\\"annualization_sessions_per_year\\\\\\",252],[\\\\\\"expected_session_dates\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$date\\\\\\":\\\\\\"2029-12-03\\\\\\"},{\\\\\\"$date\\\\\\":\\\\\\"2029-12-18\\\\\\"},{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}]}],[\\\\\\"price_basis\\\\\\",\\\\\\"raw_close\\\\\\"],[\\\\\\"price_observation_count\\\\\\",3],[\\\\\\"price_unit\\\\\\",\\\\\\"usd_per_underlying_share\\\\\\"],[\\\\\\"return_association_rule\\\\\\",\\\\\\"ending_session\\\\\\"],[\\\\\\"return_formula\\\\\\",\\\\\\"natural_log_price_ratio\\\\\\"],[\\\\\\"return_observation_count\\\\\\",2],[\\\\\\"return_unit\\\\\\",\\\\\\"decimal_ratio\\\\\\"],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"variance_estimator\\\\\\",\\\\\\"sample_variance\\\\\\"],[\\\\\\"volatility_unit\\\\\\",\\\\\\"annualized_decimal_ratio\\\\\\"],[\\\\\\"window_end_session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"window_start_session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-03\\\\\\"}]]}\\"],[\\"price_basis\\",\\"raw_close\\"],[\\"price_observation_count\\",3],[\\"prices\\",{\\"$list\\":[{\\"$decimal\\":\\"100\\"},{\\"$decimal\\":\\"102\\"},{\\"$decimal\\":\\"101\\"}]}],[\\"quality_flags\\",{\\"$list\\":[\\"decimal_to_float_converted\\",\\"annualized\\",\\"assumption_applied\\"]}],[\\"return_formula\\",\\"natural_log_price_ratio\\"],[\\"return_observation_count\\",2],[\\"session_dates\\",{\\"$list\\":[{\\"$date\\":\\"2029-12-03\\"},{\\"$date\\":\\"2029-12-18\\"},{\\"$date\\":\\"2030-01-02\\"}]}],[\\"start_session_date\\",{\\"$date\\":\\"2029-12-03\\"}],[\\"underlying\\",{\\"$map\\":[[\\"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"symbol\\",\\"SPY\\"]]}],[\\"variance_estimator\\",\\"sample_variance\\"]]}],[\\"realized_window_matching_rule\\",\\"realized_end_equals_current_as_of_and_calendar_span_equals_reference_tenor\\"],[\\"reference_tenor_days\\",30],[\\"strike_tie_rule\\",\\"lower_strike\\"],[\\"term_tenor_rule\\",\\"expiration_minus_session_date_calendar_days\\"],[\\"underlying_midpoint_rule\\",\\"bid_ask_midpoint_no_last_fallback\\"],[\\"volatility_unit\\",\\"annualized_decimal_ratio\\"]]}"],["quality_flags",{"$list":["decimal_to_float_converted","annualized","assumption_applied"]}],["reference_tenor_days",30],["term_points",{"$list":[{"$map":[["atm_iv_float_repr","0.3"],["tenor_days",30]]},{"$map":[["atm_iv_float_repr","0.4"],["tenor_days",60]]}]}],["underlying","SPY"]]}],["candidate_universe",{"$map":[["current_semantics","no_eligible_nearest_signed_delta_candidate_omitted"],["declared_complete",true],["historical_semantics","no_eligible_paired_atm_or_nearest_signed_delta_candidate_omitted"],["scope","current_delta_and_historical_atm_and_delta_candidate_universes"]]}],["current_expiration_observations",{"$list":[{"$map":[["atm_dependency_selected_call_iv_record_id","ve-current-0-call-iv"],["atm_dependency_selected_put_iv_record_id","ve-current-0-put-iv"],["atm_iv",{"$decimal":"0.300"}],["candidate_contracts",{"$list":[{"$map":[["contract_multiplier",100],["contract_reference_record_id","ve-current-0-call-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.40"}],["distance_to_25_target",{"$decimal":"0.25"}],["greeks_record_id","ve-current-0-call-greeks"],["implied_volatility",{"$decimal":"0.30"}],["iv_record_id","ve-current-0-call-iv"],["option_type","call"],["quote_record_id","ve-current-0-call-quote"],["signed_delta",{"$decimal":"0.50"}],["strike",{"$decimal":"100"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-30-call25-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.14"}],["distance_to_25_target",{"$decimal":"0.01"}],["greeks_record_id","tail-current-30-call25-greeks"],["implied_volatility",{"$decimal":"0.28"}],["iv_record_id","tail-current-30-call25-iv"],["option_type","call"],["quote_record_id","tail-current-30-call25-quote"],["signed_delta",{"$decimal":"0.24"}],["strike",{"$decimal":"105"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-30-call10-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.01"}],["distance_to_25_target",{"$decimal":"0.14"}],["greeks_record_id","tail-current-30-call10-greeks"],["implied_volatility",{"$decimal":"0.26"}],["iv_record_id","tail-current-30-call10-iv"],["option_type","call"],["quote_record_id","tail-current-30-call10-quote"],["signed_delta",{"$decimal":"0.11"}],["strike",{"$decimal":"110"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-30-put10-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.01"}],["distance_to_25_target",{"$decimal":"0.14"}],["greeks_record_id","tail-current-30-put10-greeks"],["implied_volatility",{"$decimal":"0.42"}],["iv_record_id","tail-current-30-put10-iv"],["option_type","put"],["quote_record_id","tail-current-30-put10-quote"],["signed_delta",{"$decimal":"-0.11"}],["strike",{"$decimal":"90"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-30-put25-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.14"}],["distance_to_25_target",{"$decimal":"0.01"}],["greeks_record_id","tail-current-30-put25-greeks"],["implied_volatility",{"$decimal":"0.36"}],["iv_record_id","tail-current-30-put25-iv"],["option_type","put"],["quote_record_id","tail-current-30-put25-quote"],["signed_delta",{"$decimal":"-0.24"}],["strike",{"$decimal":"95"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","ve-current-0-put-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.40"}],["distance_to_25_target",{"$decimal":"0.25"}],["greeks_record_id","ve-current-0-put-greeks"],["implied_volatility",{"$decimal":"0.30"}],["iv_record_id","ve-current-0-put-iv"],["option_type","put"],["quote_record_id","ve-current-0-put-quote"],["signed_delta",{"$decimal":"-0.50"}],["strike",{"$decimal":"100"}]]}]}],["downside_25_delta_skew",{"$decimal":"0.060"}],["downside_wing_curvature",{"$decimal":"0.06"}],["expiration",{"$date":"2030-02-01"}],["historical_observation_count",1],["selected_call_10",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-30-call10-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-current-30-call10-greeks"],["implied_volatility",{"$decimal":"0.26"}],["iv_record_id","tail-current-30-call10-iv"],["option_type","call"],["quote_record_id","tail-current-30-call10-quote"],["selected_delta",{"$decimal":"0.11"}],["strike",{"$decimal":"110"}],["target_delta",{"$decimal":"0.10"}]]}],["selected_call_25",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-30-call25-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-current-30-call25-greeks"],["implied_volatility",{"$decimal":"0.28"}],["iv_record_id","tail-current-30-call25-iv"],["option_type","call"],["quote_record_id","tail-current-30-call25-quote"],["selected_delta",{"$decimal":"0.24"}],["strike",{"$decimal":"105"}],["target_delta",{"$decimal":"0.25"}]]}],["selected_put_10",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-30-put10-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-current-30-put10-greeks"],["implied_volatility",{"$decimal":"0.42"}],["iv_record_id","tail-current-30-put10-iv"],["option_type","put"],["quote_record_id","tail-current-30-put10-quote"],["selected_delta",{"$decimal":"-0.11"}],["strike",{"$decimal":"90"}],["target_delta",{"$decimal":"-0.10"}]]}],["selected_put_25",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-30-put25-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-current-30-put25-greeks"],["implied_volatility",{"$decimal":"0.36"}],["iv_record_id","tail-current-30-put25-iv"],["option_type","put"],["quote_record_id","tail-current-30-put25-quote"],["selected_delta",{"$decimal":"-0.24"}],["strike",{"$decimal":"95"}],["target_delta",{"$decimal":"-0.25"}]]}],["session_date",{"$date":"2030-01-02"}],["skew_percentile",{"$decimal":"1"}],["tenor_days",30],["underlying_quote_record_id","ve-current-underlying"],["upside_25_delta_skew",{"$decimal":"-0.020"}],["upside_wing_curvature",{"$decimal":"-0.02"}]]},{"$map":[["atm_dependency_selected_call_iv_record_id","ve-current-1-call-iv"],["atm_dependency_selected_put_iv_record_id","ve-current-1-put-iv"],["atm_iv",{"$decimal":"0.400"}],["candidate_contracts",{"$list":[{"$map":[["contract_multiplier",100],["contract_reference_record_id","ve-current-1-call-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.40"}],["distance_to_25_target",{"$decimal":"0.25"}],["greeks_record_id","ve-current-1-call-greeks"],["implied_volatility",{"$decimal":"0.40"}],["iv_record_id","ve-current-1-call-iv"],["option_type","call"],["quote_record_id","ve-current-1-call-quote"],["signed_delta",{"$decimal":"0.50"}],["strike",{"$decimal":"100"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-60-call25-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.14"}],["distance_to_25_target",{"$decimal":"0.01"}],["greeks_record_id","tail-current-60-call25-greeks"],["implied_volatility",{"$decimal":"0.38"}],["iv_record_id","tail-current-60-call25-iv"],["option_type","call"],["quote_record_id","tail-current-60-call25-quote"],["signed_delta",{"$decimal":"0.24"}],["strike",{"$decimal":"105"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-60-call10-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.01"}],["distance_to_25_target",{"$decimal":"0.14"}],["greeks_record_id","tail-current-60-call10-greeks"],["implied_volatility",{"$decimal":"0.36"}],["iv_record_id","tail-current-60-call10-iv"],["option_type","call"],["quote_record_id","tail-current-60-call10-quote"],["signed_delta",{"$decimal":"0.11"}],["strike",{"$decimal":"110"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-60-put10-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.01"}],["distance_to_25_target",{"$decimal":"0.14"}],["greeks_record_id","tail-current-60-put10-greeks"],["implied_volatility",{"$decimal":"0.52"}],["iv_record_id","tail-current-60-put10-iv"],["option_type","put"],["quote_record_id","tail-current-60-put10-quote"],["signed_delta",{"$decimal":"-0.11"}],["strike",{"$decimal":"90"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-60-put25-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.14"}],["distance_to_25_target",{"$decimal":"0.01"}],["greeks_record_id","tail-current-60-put25-greeks"],["implied_volatility",{"$decimal":"0.46"}],["iv_record_id","tail-current-60-put25-iv"],["option_type","put"],["quote_record_id","tail-current-60-put25-quote"],["signed_delta",{"$decimal":"-0.24"}],["strike",{"$decimal":"95"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","ve-current-1-put-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.40"}],["distance_to_25_target",{"$decimal":"0.25"}],["greeks_record_id","ve-current-1-put-greeks"],["implied_volatility",{"$decimal":"0.40"}],["iv_record_id","ve-current-1-put-iv"],["option_type","put"],["quote_record_id","ve-current-1-put-quote"],["signed_delta",{"$decimal":"-0.50"}],["strike",{"$decimal":"100"}]]}]}],["downside_25_delta_skew",{"$decimal":"0.060"}],["downside_wing_curvature",{"$decimal":"0.06"}],["expiration",{"$date":"2030-03-03"}],["historical_observation_count",1],["selected_call_10",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-60-call10-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-current-60-call10-greeks"],["implied_volatility",{"$decimal":"0.36"}],["iv_record_id","tail-current-60-call10-iv"],["option_type","call"],["quote_record_id","tail-current-60-call10-quote"],["selected_delta",{"$decimal":"0.11"}],["strike",{"$decimal":"110"}],["target_delta",{"$decimal":"0.10"}]]}],["selected_call_25",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-60-call25-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-current-60-call25-greeks"],["implied_volatility",{"$decimal":"0.38"}],["iv_record_id","tail-current-60-call25-iv"],["option_type","call"],["quote_record_id","tail-current-60-call25-quote"],["selected_delta",{"$decimal":"0.24"}],["strike",{"$decimal":"105"}],["target_delta",{"$decimal":"0.25"}]]}],["selected_put_10",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-60-put10-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-current-60-put10-greeks"],["implied_volatility",{"$decimal":"0.52"}],["iv_record_id","tail-current-60-put10-iv"],["option_type","put"],["quote_record_id","tail-current-60-put10-quote"],["selected_delta",{"$decimal":"-0.11"}],["strike",{"$decimal":"90"}],["target_delta",{"$decimal":"-0.10"}]]}],["selected_put_25",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-current-60-put25-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-current-60-put25-greeks"],["implied_volatility",{"$decimal":"0.46"}],["iv_record_id","tail-current-60-put25-iv"],["option_type","put"],["quote_record_id","tail-current-60-put25-quote"],["selected_delta",{"$decimal":"-0.24"}],["strike",{"$decimal":"95"}],["target_delta",{"$decimal":"-0.25"}]]}],["session_date",{"$date":"2030-01-02"}],["skew_percentile",{"$decimal":"1"}],["tenor_days",60],["underlying_quote_record_id","ve-current-underlying"],["upside_25_delta_skew",{"$decimal":"-0.020"}],["upside_wing_curvature",{"$decimal":"-0.02"}]]}]}],["current_skew_formula","put_25_delta_iv_minus_atm_iv"],["delta_convention",{"$map":[["delta_basis","spot"],["interpolation_methodology","none"],["model_provider_methodology","Synthetic Black-Scholes provider delta"],["premium_adjustment","unadjusted"],["signed_delta_convention","call_positive_put_negative"],["target_selection_methodology","nearest_observed_signed_delta"]]}],["delta_point_selection_rule","nearest_observed_signed_delta"],["delta_tie_rule","reject_equal_distance_or_remaining_economic_ambiguity"],["float_conversion_rule","convert_only_final_tail_pricing_record_values_to_finite_float"],["historical_eod_semantics",{"$map":[["declared",true],["methodology","Synthetic official regular-session EOD snapshot"],["sample_semantics","caller_declared_daily_eod_observation_sample"],["scope","every_historical_session_and_tenor_selection"]]}],["historical_expected_session_dates",{"$list":[{"$date":"2029-12-30"}]}],["historical_matched_tenor_rule","expiration_minus_session_date_calendar_days_equals_current_tenor"],["historical_observations_by_tenor",{"$list":[{"$map":[["current_expiration",{"$date":"2030-02-01"}],["historical_observations",{"$list":[{"$map":[["atm_iv",{"$decimal":"0.200"}],["call_10_delta_iv",{"$decimal":"0.16"}],["call_25_delta_iv",{"$decimal":"0.18"}],["candidate_contracts",{"$list":[{"$map":[["contract_multiplier",100],["contract_reference_record_id","ve-history-0-0-call-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.40"}],["distance_to_25_target",{"$decimal":"0.25"}],["greeks_record_id","ve-history-0-0-call-greeks"],["implied_volatility",{"$decimal":"0.19"}],["iv_record_id","ve-history-0-0-call-iv"],["option_type","call"],["quote_record_id","ve-history-0-0-call-quote"],["signed_delta",{"$decimal":"0.50"}],["strike",{"$decimal":"100"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-30-call25-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.14"}],["distance_to_25_target",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-30-call25-greeks"],["implied_volatility",{"$decimal":"0.18"}],["iv_record_id","tail-history-0-30-call25-iv"],["option_type","call"],["quote_record_id","tail-history-0-30-call25-quote"],["signed_delta",{"$decimal":"0.24"}],["strike",{"$decimal":"105"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-30-call10-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.01"}],["distance_to_25_target",{"$decimal":"0.14"}],["greeks_record_id","tail-history-0-30-call10-greeks"],["implied_volatility",{"$decimal":"0.16"}],["iv_record_id","tail-history-0-30-call10-iv"],["option_type","call"],["quote_record_id","tail-history-0-30-call10-quote"],["signed_delta",{"$decimal":"0.11"}],["strike",{"$decimal":"110"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-30-put10-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.01"}],["distance_to_25_target",{"$decimal":"0.14"}],["greeks_record_id","tail-history-0-30-put10-greeks"],["implied_volatility",{"$decimal":"0.32"}],["iv_record_id","tail-history-0-30-put10-iv"],["option_type","put"],["quote_record_id","tail-history-0-30-put10-quote"],["signed_delta",{"$decimal":"-0.11"}],["strike",{"$decimal":"90"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-30-put25-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.14"}],["distance_to_25_target",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-30-put25-greeks"],["implied_volatility",{"$decimal":"0.26"}],["iv_record_id","tail-history-0-30-put25-iv"],["option_type","put"],["quote_record_id","tail-history-0-30-put25-quote"],["signed_delta",{"$decimal":"-0.24"}],["strike",{"$decimal":"95"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","ve-history-0-0-put-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.40"}],["distance_to_25_target",{"$decimal":"0.25"}],["greeks_record_id","ve-history-0-0-put-greeks"],["implied_volatility",{"$decimal":"0.21"}],["iv_record_id","ve-history-0-0-put-iv"],["option_type","put"],["quote_record_id","ve-history-0-0-put-quote"],["signed_delta",{"$decimal":"-0.50"}],["strike",{"$decimal":"100"}]]}]}],["downside_25_delta_skew",{"$decimal":"0.060"}],["downside_wing_curvature",{"$decimal":"0.06"}],["expiration",{"$date":"2030-01-29"}],["put_10_delta_iv",{"$decimal":"0.32"}],["put_25_delta_iv",{"$decimal":"0.26"}],["selected_call_10",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-30-call10-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-30-call10-greeks"],["implied_volatility",{"$decimal":"0.16"}],["iv_record_id","tail-history-0-30-call10-iv"],["option_type","call"],["quote_record_id","tail-history-0-30-call10-quote"],["selected_delta",{"$decimal":"0.11"}],["strike",{"$decimal":"110"}],["target_delta",{"$decimal":"0.10"}]]}],["selected_call_25",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-30-call25-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-30-call25-greeks"],["implied_volatility",{"$decimal":"0.18"}],["iv_record_id","tail-history-0-30-call25-iv"],["option_type","call"],["quote_record_id","tail-history-0-30-call25-quote"],["selected_delta",{"$decimal":"0.24"}],["strike",{"$decimal":"105"}],["target_delta",{"$decimal":"0.25"}]]}],["selected_paired_atm_evidence",{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","ve-history-0-0-call-reference"],["call_implied_volatility",{"$decimal":"0.19"}],["call_iv_record_id","ve-history-0-0-call-iv"],["call_quote_record_id","ve-history-0-0-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.200"}],["put_contract_reference_record_id","ve-history-0-0-put-reference"],["put_implied_volatility",{"$decimal":"0.21"}],["put_iv_record_id","ve-history-0-0-put-iv"],["put_quote_record_id","ve-history-0-0-put-quote"],["strike",{"$decimal":"100"}]]}]}],["selected_atm_iv",{"$decimal":"0.200"}],["selected_call_iv_record_id","ve-history-0-0-call-iv"],["selected_put_iv_record_id","ve-history-0-0-put-iv"],["selected_strike",{"$decimal":"100"}],["underlying_midpoint",{"$decimal":"100.0"}]]}],["selected_put_10",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-30-put10-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-30-put10-greeks"],["implied_volatility",{"$decimal":"0.32"}],["iv_record_id","tail-history-0-30-put10-iv"],["option_type","put"],["quote_record_id","tail-history-0-30-put10-quote"],["selected_delta",{"$decimal":"-0.11"}],["strike",{"$decimal":"90"}],["target_delta",{"$decimal":"-0.10"}]]}],["selected_put_25",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-30-put25-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-30-put25-greeks"],["implied_volatility",{"$decimal":"0.26"}],["iv_record_id","tail-history-0-30-put25-iv"],["option_type","put"],["quote_record_id","tail-history-0-30-put25-quote"],["selected_delta",{"$decimal":"-0.24"}],["strike",{"$decimal":"95"}],["target_delta",{"$decimal":"-0.25"}]]}],["session_date",{"$date":"2029-12-30"}],["underlying_quote_record_id","ve-history-0-underlying"],["upside_25_delta_skew",{"$decimal":"-0.020"}],["upside_wing_curvature",{"$decimal":"-0.02"}]]}]}],["tenor_days",30]]},{"$map":[["current_expiration",{"$date":"2030-03-03"}],["historical_observations",{"$list":[{"$map":[["atm_iv",{"$decimal":"0.300"}],["call_10_delta_iv",{"$decimal":"0.26"}],["call_25_delta_iv",{"$decimal":"0.28"}],["candidate_contracts",{"$list":[{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-60-atm-call-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.40"}],["distance_to_25_target",{"$decimal":"0.25"}],["greeks_record_id","tail-history-0-60-atm-call-greeks"],["implied_volatility",{"$decimal":"0.30"}],["iv_record_id","tail-history-0-60-atm-call-iv"],["option_type","call"],["quote_record_id","tail-history-0-60-atm-call-quote"],["signed_delta",{"$decimal":"0.50"}],["strike",{"$decimal":"100"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-60-call25-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.14"}],["distance_to_25_target",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-60-call25-greeks"],["implied_volatility",{"$decimal":"0.28"}],["iv_record_id","tail-history-0-60-call25-iv"],["option_type","call"],["quote_record_id","tail-history-0-60-call25-quote"],["signed_delta",{"$decimal":"0.24"}],["strike",{"$decimal":"105"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-60-call10-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.01"}],["distance_to_25_target",{"$decimal":"0.14"}],["greeks_record_id","tail-history-0-60-call10-greeks"],["implied_volatility",{"$decimal":"0.26"}],["iv_record_id","tail-history-0-60-call10-iv"],["option_type","call"],["quote_record_id","tail-history-0-60-call10-quote"],["signed_delta",{"$decimal":"0.11"}],["strike",{"$decimal":"110"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-60-put10-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.01"}],["distance_to_25_target",{"$decimal":"0.14"}],["greeks_record_id","tail-history-0-60-put10-greeks"],["implied_volatility",{"$decimal":"0.42"}],["iv_record_id","tail-history-0-60-put10-iv"],["option_type","put"],["quote_record_id","tail-history-0-60-put10-quote"],["signed_delta",{"$decimal":"-0.11"}],["strike",{"$decimal":"90"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-60-put25-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.14"}],["distance_to_25_target",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-60-put25-greeks"],["implied_volatility",{"$decimal":"0.36"}],["iv_record_id","tail-history-0-60-put25-iv"],["option_type","put"],["quote_record_id","tail-history-0-60-put25-quote"],["signed_delta",{"$decimal":"-0.24"}],["strike",{"$decimal":"95"}]]},{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-60-atm-put-reference"],["currency","USD"],["deliverable_id",null],["distance_to_10_target",{"$decimal":"0.40"}],["distance_to_25_target",{"$decimal":"0.25"}],["greeks_record_id","tail-history-0-60-atm-put-greeks"],["implied_volatility",{"$decimal":"0.30"}],["iv_record_id","tail-history-0-60-atm-put-iv"],["option_type","put"],["quote_record_id","tail-history-0-60-atm-put-quote"],["signed_delta",{"$decimal":"-0.50"}],["strike",{"$decimal":"100"}]]}]}],["downside_25_delta_skew",{"$decimal":"0.060"}],["downside_wing_curvature",{"$decimal":"0.06"}],["expiration",{"$date":"2030-02-28"}],["put_10_delta_iv",{"$decimal":"0.42"}],["put_25_delta_iv",{"$decimal":"0.36"}],["selected_call_10",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-60-call10-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-60-call10-greeks"],["implied_volatility",{"$decimal":"0.26"}],["iv_record_id","tail-history-0-60-call10-iv"],["option_type","call"],["quote_record_id","tail-history-0-60-call10-quote"],["selected_delta",{"$decimal":"0.11"}],["strike",{"$decimal":"110"}],["target_delta",{"$decimal":"0.10"}]]}],["selected_call_25",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-60-call25-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-60-call25-greeks"],["implied_volatility",{"$decimal":"0.28"}],["iv_record_id","tail-history-0-60-call25-iv"],["option_type","call"],["quote_record_id","tail-history-0-60-call25-quote"],["selected_delta",{"$decimal":"0.24"}],["strike",{"$decimal":"105"}],["target_delta",{"$decimal":"0.25"}]]}],["selected_paired_atm_evidence",{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","tail-history-0-60-atm-call-reference"],["call_implied_volatility",{"$decimal":"0.30"}],["call_iv_record_id","tail-history-0-60-atm-call-iv"],["call_quote_record_id","tail-history-0-60-atm-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.300"}],["put_contract_reference_record_id","tail-history-0-60-atm-put-reference"],["put_implied_volatility",{"$decimal":"0.30"}],["put_iv_record_id","tail-history-0-60-atm-put-iv"],["put_quote_record_id","tail-history-0-60-atm-put-quote"],["strike",{"$decimal":"100"}]]}]}],["selected_atm_iv",{"$decimal":"0.300"}],["selected_call_iv_record_id","tail-history-0-60-atm-call-iv"],["selected_put_iv_record_id","tail-history-0-60-atm-put-iv"],["selected_strike",{"$decimal":"100"}],["underlying_midpoint",{"$decimal":"100.0"}]]}],["selected_put_10",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-60-put10-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-60-put10-greeks"],["implied_volatility",{"$decimal":"0.42"}],["iv_record_id","tail-history-0-60-put10-iv"],["option_type","put"],["quote_record_id","tail-history-0-60-put10-quote"],["selected_delta",{"$decimal":"-0.11"}],["strike",{"$decimal":"90"}],["target_delta",{"$decimal":"-0.10"}]]}],["selected_put_25",{"$map":[["contract_multiplier",100],["contract_reference_record_id","tail-history-0-60-put25-reference"],["currency","USD"],["deliverable_id",null],["distance",{"$decimal":"0.01"}],["greeks_record_id","tail-history-0-60-put25-greeks"],["implied_volatility",{"$decimal":"0.36"}],["iv_record_id","tail-history-0-60-put25-iv"],["option_type","put"],["quote_record_id","tail-history-0-60-put25-quote"],["selected_delta",{"$decimal":"-0.24"}],["strike",{"$decimal":"95"}],["target_delta",{"$decimal":"-0.25"}]]}],["session_date",{"$date":"2029-12-30"}],["underlying_quote_record_id","tail-history-0-60-underlying"],["upside_25_delta_skew",{"$decimal":"-0.020"}],["upside_wing_curvature",{"$decimal":"-0.02"}]]}]}],["tenor_days",60]]}]}],["interpolation_rule","none"],["normalized_evidence",{"$map":[["direct_inputs",{"$list":[{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-call10-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-current-30-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-call10-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-current-30-call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-call10-quote"],["role","option_quote"],["source_ids",{"$list":["tail-current-30-call10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-call10-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-current-30-call10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-call25-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-current-30-call25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-call25-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-current-30-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-call25-quote"],["role","option_quote"],["source_ids",{"$list":["tail-current-30-call25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-call25-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-current-30-call25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-put10-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-current-30-put10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-put10-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-current-30-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-put10-quote"],["role","option_quote"],["source_ids",{"$list":["tail-current-30-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-put10-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-current-30-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-put25-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-current-30-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-put25-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-current-30-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-put25-quote"],["role","option_quote"],["source_ids",{"$list":["tail-current-30-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-30-put25-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-current-30-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-call10-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-current-60-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-call10-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-current-60-call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-call10-quote"],["role","option_quote"],["source_ids",{"$list":["tail-current-60-call10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-call10-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-current-60-call10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-call25-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-current-60-call25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-call25-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-current-60-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-call25-quote"],["role","option_quote"],["source_ids",{"$list":["tail-current-60-call25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-call25-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-current-60-call25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-put10-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-current-60-put10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-put10-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-current-60-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-put10-quote"],["role","option_quote"],["source_ids",{"$list":["tail-current-60-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-put10-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-current-60-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-put25-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-current-60-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-put25-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-current-60-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-put25-quote"],["role","option_quote"],["source_ids",{"$list":["tail-current-60-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-current-60-put25-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-current-60-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-call10-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-history-0-30-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-call10-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-history-0-30-call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-call10-quote"],["role","option_quote"],["source_ids",{"$list":["tail-history-0-30-call10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-call10-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-history-0-30-call10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-call25-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-history-0-30-call25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-call25-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-history-0-30-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-call25-quote"],["role","option_quote"],["source_ids",{"$list":["tail-history-0-30-call25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-call25-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-history-0-30-call25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-put10-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-history-0-30-put10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-put10-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-history-0-30-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-put10-quote"],["role","option_quote"],["source_ids",{"$list":["tail-history-0-30-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-put10-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-history-0-30-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-put25-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-history-0-30-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-put25-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-history-0-30-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-put25-quote"],["role","option_quote"],["source_ids",{"$list":["tail-history-0-30-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-30-put25-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-history-0-30-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-atm-call-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-history-0-60-atm-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-atm-call-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-history-0-60-atm-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-atm-call-quote"],["role","option_quote"],["source_ids",{"$list":["tail-history-0-60-atm-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-atm-call-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-history-0-60-atm-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-atm-put-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-history-0-60-atm-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-atm-put-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-history-0-60-atm-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-atm-put-quote"],["role","option_quote"],["source_ids",{"$list":["tail-history-0-60-atm-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-atm-put-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-history-0-60-atm-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-call10-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-history-0-60-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-call10-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-history-0-60-call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-call10-quote"],["role","option_quote"],["source_ids",{"$list":["tail-history-0-60-call10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-call10-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-history-0-60-call10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-call25-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-history-0-60-call25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-call25-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-history-0-60-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-call25-quote"],["role","option_quote"],["source_ids",{"$list":["tail-history-0-60-call25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-call25-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-history-0-60-call25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-put10-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-history-0-60-put10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-put10-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-history-0-60-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-put10-quote"],["role","option_quote"],["source_ids",{"$list":["tail-history-0-60-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-put10-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-history-0-60-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-put25-greeks"],["role","option_greeks"],["source_ids",{"$list":["tail-history-0-60-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-put25-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["tail-history-0-60-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-put25-quote"],["role","option_quote"],["source_ids",{"$list":["tail-history-0-60-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-put25-reference"],["role","option_contract_reference"],["source_ids",{"$list":["tail-history-0-60-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","tail-history-0-60-underlying"],["role","underlying_quote"],["source_ids",{"$list":["tail-history-0-60-underlying-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-call-greeks"],["role","option_greeks"],["source_ids",{"$list":["ve-current-0-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-call-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-current-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-call-quote"],["role","option_quote"],["source_ids",{"$list":["ve-current-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-call-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-current-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-put-greeks"],["role","option_greeks"],["source_ids",{"$list":["ve-current-0-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-put-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-current-0-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-put-quote"],["role","option_quote"],["source_ids",{"$list":["ve-current-0-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-0-put-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-current-0-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-call-greeks"],["role","option_greeks"],["source_ids",{"$list":["ve-current-1-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-call-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-current-1-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-call-quote"],["role","option_quote"],["source_ids",{"$list":["ve-current-1-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-call-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-current-1-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-put-greeks"],["role","option_greeks"],["source_ids",{"$list":["ve-current-1-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-put-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-current-1-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-put-quote"],["role","option_quote"],["source_ids",{"$list":["ve-current-1-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-1-put-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-current-1-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-current-underlying"],["role","underlying_quote"],["source_ids",{"$list":["ve-current-underlying-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-call-greeks"],["role","option_greeks"],["source_ids",{"$list":["ve-history-0-0-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-call-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-history-0-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-call-quote"],["role","option_quote"],["source_ids",{"$list":["ve-history-0-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-call-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-history-0-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-put-greeks"],["role","option_greeks"],["source_ids",{"$list":["ve-history-0-0-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-put-iv"],["role","option_implied_volatility"],["source_ids",{"$list":["ve-history-0-0-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-put-quote"],["role","option_quote"],["source_ids",{"$list":["ve-history-0-0-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-0-put-reference"],["role","option_contract_reference"],["source_ids",{"$list":["ve-history-0-0-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","ve-history-0-underlying"],["role","underlying_quote"],["source_ids",{"$list":["ve-history-0-underlying-source-0"]}]]}]}]]}],["same_contract_reuse_rule","reject_same_economic_contract_across_10_and_25_same_side"],["skew_percentile_formula","inclusive_count_historical_downside_25_skew_lte_current_divided_by_count"],["skew_term_structure_ordering","ascending_days_to_expiration_then_expiration"],["tail_output_architecture","ordered_tail_pricing_slice_tuple"],["target_deltas",{"$map":[["call_10",{"$decimal":"0.10"}],["call_25",{"$decimal":"0.25"}],["put_10",{"$decimal":"-0.10"}],["put_25",{"$decimal":"-0.25"}]]}],["volatility_unit","annualized_decimal_ratio"]]}'
EXPECTED_STRUCTURE_LIQUIDITY_V02_JSON = '{"$map":[["activity_count_unit","contracts"],["calculation_values",{"$map":[["as_of_date",{"$date":"2030-01-02"}],["minimum_leg_daily_volume",30],["minimum_leg_open_interest",70],["quote_methodology","exact selected option quotes scaled by quantity and contract multiplier"],["quoted_ask_value_exact",{"$decimal":"400.00"}],["quoted_bid_value_exact",{"$decimal":"325.00"}],["stable_public_values",{"$map":[["quoted_ask_value_repr","400.0"],["quoted_bid_value_repr","325.0"]]}]]}],["leg_correspondence",{"$list":[{"$map":[["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],["open_interest_record_id","liquidity-call-open-interest"],["option_type","call"],["quantity",1],["quote_record_id","liquidity-call-quote"],["strike",{"$decimal":"100.0"}],["underlying",{"$map":[["currency","USD"],["listing_mic","ARCX"],["security_type","etf"],["symbol","SPY"]]}],["volume_record_id","liquidity-call-volume"]]},{"$map":[["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],["open_interest_record_id","liquidity-put-open-interest"],["option_type","put"],["quantity",1],["quote_record_id","liquidity-put-quote"],["strike",{"$decimal":"100.0"}],["underlying",{"$map":[["currency","USD"],["listing_mic","ARCX"],["security_type","etf"],["symbol","SPY"]]}],["volume_record_id","liquidity-put-volume"]]}]}],["minimum_leg_rule","minimum_unscaled_contract_count_across_legs"],["normalized_evidence",{"$map":[["option_open_interest",{"$list":[{"$map":[["contract",{"$map":[["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],["option_type","call"],["strike",{"$decimal":"100.0"}],["underlying",{"$map":[["currency","USD"],["listing_mic","ARCX"],["security_type","etf"],["symbol","SPY"]]}]]}],["leg_index",0],["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["open_interest",80],["open_interest_session_date",{"$date":"2030-01-02"}],["propagated_quality_flags",{"$list":[]}],["record_id","liquidity-call-open-interest"],["source_ids",{"$list":["liquidity-call-open-interest-source-0"]}]]},{"$map":[["contract",{"$map":[["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],["option_type","put"],["strike",{"$decimal":"100.0"}],["underlying",{"$map":[["currency","USD"],["listing_mic","ARCX"],["security_type","etf"],["symbol","SPY"]]}]]}],["leg_index",1],["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["open_interest",70],["open_interest_session_date",{"$date":"2030-01-02"}],["propagated_quality_flags",{"$list":[]}],["record_id","liquidity-put-open-interest"],["source_ids",{"$list":["liquidity-put-open-interest-source-0"]}]]}]}],["option_quotes",{"$list":[{"$map":[["ask_premium",{"$decimal":"1.50"}],["bid_premium",{"$decimal":"1.25"}],["contract",{"$map":[["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],["option_type","call"],["strike",{"$decimal":"100.0"}],["underlying",{"$map":[["currency","USD"],["listing_mic","ARCX"],["security_type","etf"],["symbol","SPY"]]}]]}],["leg_index",0],["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","liquidity-call-quote"],["session_date",{"$date":"2030-01-02"}],["source_ids",{"$list":["liquidity-call-quote-source-0"]}]]},{"$map":[["ask_premium",{"$decimal":"2.50"}],["bid_premium",{"$decimal":"2.00"}],["contract",{"$map":[["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],["option_type","put"],["strike",{"$decimal":"100.0"}],["underlying",{"$map":[["currency","USD"],["listing_mic","ARCX"],["security_type","etf"],["symbol","SPY"]]}]]}],["leg_index",1],["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","liquidity-put-quote"],["session_date",{"$date":"2030-01-02"}],["source_ids",{"$list":["liquidity-put-quote-source-0"]}]]}]}],["option_volumes",{"$list":[{"$map":[["contract",{"$map":[["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],["option_type","call"],["strike",{"$decimal":"100.0"}],["underlying",{"$map":[["currency","USD"],["listing_mic","ARCX"],["security_type","etf"],["symbol","SPY"]]}]]}],["cumulative_volume",40],["is_session_complete",true],["leg_index",0],["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","liquidity-call-volume"],["session_date",{"$date":"2030-01-02"}],["source_ids",{"$list":["liquidity-call-volume-source-0"]}]]},{"$map":[["contract",{"$map":[["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],["option_type","put"],["strike",{"$decimal":"100.0"}],["underlying",{"$map":[["currency","USD"],["listing_mic","ARCX"],["security_type","etf"],["symbol","SPY"]]}]]}],["cumulative_volume",30],["is_session_complete",true],["leg_index",1],["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["propagated_quality_flags",{"$list":[]}],["record_id","liquidity-put-volume"],["session_date",{"$date":"2030-01-02"}],["source_ids",{"$list":["liquidity-put-volume-source-0"]}]]}]}]]}],["position_value_rule","sum(premium_per_underlying_unit*quantity*contract_multiplier)"],["position_value_unit","usd"],["premium_input_unit","usd_per_underlying_unit"],["structure_identity",{"$map":[["assumed_portfolio_value_repr","100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-03-15"}],["option_type","call"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]},{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-03-15"}],["option_type","put"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]}]}],["structure_type","long_straddle"],["underlying","SPY"]]}]]}'

class Milestone6AReviewedArtifactVerifiabilityTests(unittest.TestCase):
    @staticmethod
    def _tagged_map(value):
        if type(value) is not dict or tuple(value) != ("$map",):
            raise AssertionError("expected a literal tagged map")
        pairs = value["$map"]
        if type(pairs) is not list:
            raise AssertionError("expected a literal map-pair list")
        return {pair[0]: pair[1] for pair in pairs}

    @staticmethod
    def _bypass_replace(value, **changes):
        forged = object.__new__(type(value))
        for field in dataclasses.fields(value):
            object.__setattr__(
                forged,
                field.name,
                changes.get(field.name, getattr(value, field.name)),
            )
        return forged

    def _forged_volatility_lineage(self, result, mutate):
        parameters = copy.deepcopy(
            transformations._decode_volatility_parameters(
                result.lineage.parameters_json
            )
        )
        mutate(parameters)
        return dataclasses.replace(
            result.lineage,
            parameters_json=market_data.canonicalize_lineage_parameters(
                parameters
            ),
        )

    def _forged_tail_lineage(self, result, mutate):
        parameters = copy.deepcopy(
            transformations._decode_tail_pricing_parameters(
                result.lineage.parameters_json
            )
        )
        mutate(parameters)
        return dataclasses.replace(
            result.lineage,
            parameters_json=market_data.canonicalize_lineage_parameters(
                parameters
            ),
        )

    @staticmethod
    def _coordinate_realized_field(parameters, field, value):
        realized = parameters["realized_volatility_dependency"]
        realized[field] = value
        historical = transformations._decode_strict_tagged_parameters(
            realized["parameters_json"],
            transformations._HISTORICAL_PARAMETER_KEYS,
            "test historical dependency",
        )
        historical_field = {
            "start_session_date": "window_start_session_date",
            "end_session_date": "window_end_session_date",
        }.get(field, field)
        historical[historical_field] = value
        realized["parameters_json"] = (
            market_data.canonicalize_lineage_parameters(historical)
        )

    @staticmethod
    def _coordinate_realized_underlying_field(
        parameters, field, value
    ):
        realized = parameters["realized_volatility_dependency"]
        realized["underlying"][field] = value
        historical = transformations._decode_strict_tagged_parameters(
            realized["parameters_json"],
            transformations._HISTORICAL_PARAMETER_KEYS,
            "test historical dependency",
        )
        historical["underlying"][field] = value
        realized["parameters_json"] = (
            market_data.canonicalize_lineage_parameters(historical)
        )

    def test_literal_v02_byte_goldens_and_frozen_nested_schemas(self):
        volatility = make_volatility_result(
            current_candidates=(
                (
                    SESSION_DATE + datetime.timedelta(days=30),
                    "100", "0.3", "0.3",
                ),
                (
                    SESSION_DATE + datetime.timedelta(days=60),
                    "100", "0.4", "0.4",
                ),
            ),
            historical_values=("0.20",),
        )
        tail = make_tail_result(historical_skews=("0.06",))
        structure = make_structure(("call", "put"))
        liquidity = transform(structure, make_selection(structure)[0])
        artifacts = (
            (
                "Volatility Environment v0.2",
                volatility.lineage.parameters_json,
                EXPECTED_VOLATILITY_ENVIRONMENT_V02_JSON,
                (
                    "atm_candidate_universe", "atm_selection_rule",
                    "call_put_combination_rule", "current_observations",
                    "float_conversion_rule",
                    "historical_expected_session_dates",
                    "historical_matched_tenor_rule",
                    "historical_observation_count",
                    "historical_observations",
                    "historical_sample_semantics", "iv_methodology",
                    "median_formula", "normalized_evidence",
                    "percentile_formula",
                    "realized_volatility_dependency",
                    "realized_window_matching_rule", "reference_tenor_days",
                    "strike_tie_rule", "term_tenor_rule",
                    "underlying_midpoint_rule", "volatility_unit",
                ),
            ),
            (
                "Tail Pricing v0.2",
                tail.lineage.parameters_json,
                EXPECTED_TAIL_PRICING_V02_JSON,
                (
                    "analytics_methodology", "atm_dependency",
                    "candidate_universe", "current_expiration_observations",
                    "current_skew_formula", "delta_convention",
                    "delta_point_selection_rule", "delta_tie_rule",
                    "float_conversion_rule", "historical_eod_semantics",
                    "historical_expected_session_dates",
                    "historical_matched_tenor_rule",
                    "historical_observations_by_tenor",
                    "interpolation_rule", "normalized_evidence",
                    "same_contract_reuse_rule", "skew_percentile_formula",
                    "skew_term_structure_ordering",
                    "tail_output_architecture", "target_deltas",
                    "volatility_unit",
                ),
            ),
            (
                "Structure Liquidity v0.2",
                liquidity.lineage.parameters_json,
                EXPECTED_STRUCTURE_LIQUIDITY_V02_JSON,
                (
                    "activity_count_unit", "calculation_values",
                    "leg_correspondence", "minimum_leg_rule",
                    "normalized_evidence", "position_value_rule",
                    "position_value_unit", "premium_input_unit",
                    "structure_identity",
                ),
            ),
        )
        for name, actual, expected, top_level_keys in artifacts:
            with self.subTest(name=name):
                self.assertEqual(actual, expected)
                self.assertEqual(
                    hashlib.sha256(actual.encode()).hexdigest(),
                    hashlib.sha256(expected.encode()).hexdigest(),
                )
                self.assertEqual(
                    tuple(self._tagged_map(json.loads(expected))),
                    top_level_keys,
                )

        volatility_map = self._tagged_map(
            json.loads(EXPECTED_VOLATILITY_ENVIRONMENT_V02_JSON)
        )
        realized = self._tagged_map(
            volatility_map["realized_volatility_dependency"]
        )
        self.assertEqual(
            set(realized),
            {
                "adjustment_methodology",
                "annualization_sessions_per_year",
                "annualized_realized_volatility_float_repr",
                "calculated_at", "calculation_id", "calculation_type",
                "end_session_date", "inputs", "log_returns",
                "methodology_id", "methodology_version", "parameters_json",
                "price_basis", "price_observation_count", "prices",
                "quality_flags", "return_formula",
                "return_observation_count", "session_dates",
                "start_session_date", "underlying", "variance_estimator",
            },
        )
        tail_map = self._tagged_map(
            json.loads(EXPECTED_TAIL_PRICING_V02_JSON)
        )
        atm = self._tagged_map(tail_map["atm_dependency"])
        self.assertIn("inputs", atm)
        self.assertNotIn("input_record_ids", atm)
        liquidity_map = self._tagged_map(
            json.loads(EXPECTED_STRUCTURE_LIQUIDITY_V02_JSON)
        )
        normalized = self._tagged_map(
            liquidity_map["normalized_evidence"]
        )
        self.assertEqual(
            set(normalized),
            {"option_quotes", "option_volumes", "option_open_interest"},
        )
        calculations = self._tagged_map(
            liquidity_map["calculation_values"]
        )
        self.assertEqual(
            set(calculations),
            {
                "as_of_date", "quoted_bid_value_exact",
                "quoted_ask_value_exact", "minimum_leg_daily_volume",
                "minimum_leg_open_interest", "quote_methodology",
                "stable_public_values",
            },
        )

    def test_authentic_direct_reconstruction_and_v01_rejection(self):
        volatility = make_volatility_result()
        tail = make_tail_result()
        structure = make_structure(("put", "call"))
        liquidity = transform(structure, make_selection(structure)[0])
        self.assertEqual(
            VolatilityEnvironmentTransformationResult(
                volatility.record, volatility.lineage
            ),
            volatility,
        )
        self.assertEqual(
            TailPricingTransformationResult(tail.records, tail.lineage), tail
        )
        self.assertEqual(
            StructureLiquidityTransformationResult(
                liquidity.record, liquidity.lineage
            ),
            liquidity,
        )
        for wrapper, public, lineage in (
            (
                VolatilityEnvironmentTransformationResult,
                volatility.record,
                volatility.lineage,
            ),
            (TailPricingTransformationResult, tail.records, tail.lineage),
            (
                StructureLiquidityTransformationResult,
                liquidity.record,
                liquidity.lineage,
            ),
        ):
            with self.subTest(wrapper=wrapper.__name__), self.assertRaises(
                ValueError
            ):
                wrapper(
                    public,
                    dataclasses.replace(lineage, methodology_version="v0.1"),
                )

    def test_complete_realized_dependency_mutation_matrix_rejects(self):
        result = make_volatility_result()
        mutations = (
            (
                "incomplete_underlying",
                ValueError,
                lambda value: value["realized_volatility_dependency"]
                ["underlying"].pop("listing_mic"),
            ),
            (
                "surplus_underlying",
                ValueError,
                lambda value: value["realized_volatility_dependency"]
                ["underlying"].__setitem__("extra", "forged"),
            ),
            (
                "forged_currency",
                ValueError,
                lambda value: self._coordinate_realized_underlying_field(
                    value, "currency", "EUR"
                ),
            ),
            (
                "forged_return_formula",
                ValueError,
                lambda value: self._coordinate_realized_field(
                    value, "return_formula", "forged"
                ),
            ),
            (
                "forged_variance_estimator",
                ValueError,
                lambda value: self._coordinate_realized_field(
                    value, "variance_estimator", "forged"
                ),
            ),
            (
                "forged_price_basis",
                ValueError,
                lambda value: self._coordinate_realized_field(
                    value, "price_basis", "forged"
                ),
            ),
            (
                "boolean_annualization_sessions",
                TypeError,
                lambda value: self._coordinate_realized_field(
                    value, "annualization_sessions_per_year", True
                ),
            ),
            (
                "inconsistent_start_and_window",
                ValueError,
                lambda value: self._coordinate_realized_field(
                    value,
                    "start_session_date",
                    SESSION_DATE - datetime.timedelta(days=31),
                ),
            ),
            (
                "inconsistent_end_and_window",
                ValueError,
                lambda value: self._coordinate_realized_field(
                    value,
                    "end_session_date",
                    SESSION_DATE - datetime.timedelta(days=1),
                ),
            ),
            (
                "malformed_underlying_type",
                TypeError,
                lambda value: value.__setitem__(
                    "realized_volatility_dependency",
                    {
                        **value["realized_volatility_dependency"],
                        "underlying": "SPY",
                    },
                ),
            ),
        )
        for name, exception, mutate in mutations:
            with self.subTest(name=name), self.assertRaises(exception):
                VolatilityEnvironmentTransformationResult(
                    result.record,
                    self._forged_volatility_lineage(result, mutate),
                )

        forged_window = self._bypass_replace(
            result.record,
            matched_realized_window_days=result.reference_tenor_days + 1
            if hasattr(result, "reference_tenor_days")
            else result.record.reference_tenor_days + 1,
        )
        with self.assertRaises(ValueError):
            VolatilityEnvironmentTransformationResult(
                forged_window, result.lineage
            )

    def test_complete_calculation_id_namespace_rejects(self):
        volatility = make_volatility_result()
        decoded = transformations._decode_volatility_parameters(
            volatility.lineage.parameters_json
        )
        realized = decoded["realized_volatility_dependency"]
        dependency_input_id = realized["inputs"][0]["record_id"]
        direct_input_id = decoded["normalized_evidence"]["direct_inputs"][0][
            "record_id"
        ]
        for name, collision_id in (
            ("realized_own_input", dependency_input_id),
            ("realized_direct_input", direct_input_id),
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                VolatilityEnvironmentTransformationResult(
                    volatility.record,
                    self._forged_volatility_lineage(
                        volatility,
                        lambda value, collision_id=collision_id: value[
                            "realized_volatility_dependency"
                        ].__setitem__("calculation_id", collision_id),
                    ),
                )
        for name, collision_id in (
            ("volatility_input", direct_input_id),
            ("volatility_dependency", realized["calculation_id"]),
        ):
            with self.subTest(name=name), self.assertRaises(ValueError):
                VolatilityEnvironmentTransformationResult(
                    volatility.record,
                    self._bypass_replace(
                        volatility.lineage, calculation_id=collision_id
                    ),
                )

        tail = make_tail_result()
        tail_only_id = "tail-current-30-call10-greeks"
        with self.assertRaises(ValueError):
            TailPricingTransformationResult(
                tail.records,
                self._forged_tail_lineage(
                    tail,
                    lambda value: value["atm_dependency"].__setitem__(
                        "calculation_id", tail_only_id
                    ),
                ),
            )

        def collide_realized_with_tail_direct(value):
            dependency = value["atm_dependency"]
            parameters = transformations._decode_volatility_parameters(
                dependency["parameters_json"]
            )
            parameters["realized_volatility_dependency"][
                "calculation_id"
            ] = tail_only_id
            dependency["parameters_json"] = (
                market_data.canonicalize_lineage_parameters(parameters)
            )

        with self.assertRaises(ValueError):
            TailPricingTransformationResult(
                tail.records,
                self._forged_tail_lineage(
                    tail, collide_realized_with_tail_direct
                ),
            )

    def test_complete_public_mutation_matrix_rejects(self):
        volatility = make_volatility_result()
        volatility_changes = {
            "underlying": "QQQ",
            "as_of_date": volatility.record.as_of_date - datetime.timedelta(days=1),
            "reference_tenor_days": 60,
            "iv_percentile": 0.5,
            "iv_history_lookback_observations": 2,
            "historical_median_atm_iv": 0.31,
            "matched_realized_volatility": 0.1,
            "matched_realized_window_days": 60,
            "term_structure": tuple(reversed(volatility.record.term_structure)),
        }
        for field, value in volatility_changes.items():
            forged = self._bypass_replace(volatility.record, **{field: value})
            with self.subTest(artifact="volatility", field=field), self.assertRaises(
                (TypeError, ValueError)
            ):
                VolatilityEnvironmentTransformationResult(
                    forged, volatility.lineage
                )
        tail = make_tail_result()
        first = tail.records[0]
        tail_changes = {
            "underlying": "QQQ",
            "as_of_date": first.as_of_date - datetime.timedelta(days=1),
            "expiration": first.expiration + datetime.timedelta(days=1),
            "atm_iv": 0.99,
            "put_25_delta_iv": 0.99,
            "call_25_delta_iv": 0.99,
            "put_10_delta_iv": 0.99,
            "call_10_delta_iv": 0.99,
            "skew_percentile": 0.5,
            "skew_history_lookback_observations": 2,
            "delta_methodology": "forged",
        }
        for field, value in tail_changes.items():
            forged_first = self._bypass_replace(first, **{field: value})
            with self.subTest(artifact="tail", field=field), self.assertRaises(
                (TypeError, ValueError)
            ):
                TailPricingTransformationResult(
                    (forged_first,) + tail.records[1:], tail.lineage
                )
        structure = make_structure(("call", "put"))
        liquidity = transform(structure, make_selection(structure)[0])
        liquidity_changes = {
            "structure": make_structure(("put", "call")),
            "as_of_date": liquidity.record.as_of_date - datetime.timedelta(days=1),
            "quoted_bid_value": liquidity.record.quoted_bid_value + 1.0,
            "quoted_ask_value": liquidity.record.quoted_ask_value + 1.0,
            "minimum_leg_open_interest": 0,
            "minimum_leg_daily_volume": 0,
            "quote_methodology": "forged",
        }
        for field, value in liquidity_changes.items():
            forged = self._bypass_replace(liquidity.record, **{field: value})
            with self.subTest(artifact="liquidity", field=field), self.assertRaises(
                (TypeError, ValueError)
            ):
                StructureLiquidityTransformationResult(
                    forged, liquidity.lineage
                )

    def test_lineage_canonical_type_and_quality_adversaries_reject(self):
        results = (
            make_volatility_result(),
            make_tail_result(),
            transform(make_structure(), make_selection(make_structure())[0]),
        )
        wrappers = (
            VolatilityEnvironmentTransformationResult,
            TailPricingTransformationResult,
            StructureLiquidityTransformationResult,
        )
        for result, wrapper in zip(results, wrappers):
            public = getattr(result, "record", None)
            if public is None:
                public = result.records
            mutations = (
                {"calculation_type": "forged"},
                {"methodology_id": "forged"},
                {"methodology_version": "v0.1"},
                {"calculation_id": result.lineage.inputs[0].record_id},
                {"calculated_at": result.lineage.inputs[0].normalized_at - datetime.timedelta(microseconds=1)},
                {"quality_flags": ()},
                {"parameters_json": '{"$map":[],"$map":[]}'},
                {"parameters_json": '{"$map":[["x",1.5]]}'},
                {"parameters_json": result.lineage.parameters_json + " "},
            )
            for changes in mutations:
                forged_lineage = self._bypass_replace(
                    result.lineage, **changes
                )
                with self.subTest(
                    wrapper=wrapper.__name__, changes=tuple(changes)
                ), self.assertRaises((TypeError, ValueError)):
                    wrapper(public, forged_lineage)

    def test_direct_verification_and_consumers_do_not_call_producers(self):
        volatility = make_volatility_result()
        tail = make_tail_result()
        structure = make_structure()
        liquidity = transform(structure, make_selection(structure)[0])
        blocked = (
            "transform_volatility_environment", "transform_tail_pricing",
            "transform_structure_liquidity", "transform_scenario_valuation",
            "select_market_data_relationship_assessment",
            "assess_market_data_snapshot_timing", "provider", "network",
            "scanner", "renderer", "risk_assessment",
        )
        with ExitStack() as stack:
            for name in blocked:
                stack.enter_context(mock.patch.object(
                    transformations, name,
                    side_effect=AssertionError(f"{name} called"),
                    create=True,
                ))
            VolatilityEnvironmentTransformationResult(
                volatility.record, volatility.lineage
            )
            TailPricingTransformationResult(tail.records, tail.lineage)
            StructureLiquidityTransformationResult(
                liquidity.record, liquidity.lineage
            )

        tail_arguments = list(make_tail_result(return_arguments=True))
        with mock.patch.object(
            transformations,
            "transform_volatility_environment",
            side_effect=AssertionError("Volatility producer called"),
        ) as volatility_producer:
            consumed_tail = transform_tail_pricing(*tail_arguments)
        self.assertTrue(consumed_tail.records)
        volatility_producer.assert_not_called()

        authentic_volatility = tail_arguments[4]
        forged_volatility = object.__new__(
            VolatilityEnvironmentTransformationResult
        )
        object.__setattr__(
            forged_volatility, "record", authentic_volatility.record
        )
        object.__setattr__(
            forged_volatility,
            "lineage",
            self._forged_volatility_lineage(
                authentic_volatility,
                lambda value: self._coordinate_realized_field(
                    value, "return_formula", "forged"
                ),
            ),
        )
        tail_arguments[4] = forged_volatility
        with mock.patch.object(
            transformations,
            "transform_volatility_environment",
            side_effect=AssertionError("Volatility producer called"),
        ) as volatility_producer, self.assertRaises(ValueError):
            transform_tail_pricing(*tail_arguments)
        volatility_producer.assert_not_called()

        scenario_arguments = list(
            make_scenario_valuation_result(return_arguments=True)
        )
        with mock.patch.object(
            transformations,
            "transform_tail_pricing",
            side_effect=AssertionError("Tail producer called"),
        ) as tail_producer:
            consumed_scenario = transform_scenario_valuation(
                *scenario_arguments
            )
        self.assertTrue(consumed_scenario.records)
        tail_producer.assert_not_called()

        authentic_tail = scenario_arguments[2]
        forged_tail = object.__new__(TailPricingTransformationResult)
        object.__setattr__(forged_tail, "records", authentic_tail.records)
        object.__setattr__(
            forged_tail,
            "lineage",
            self._forged_tail_lineage(
                authentic_tail,
                lambda value: value["atm_dependency"].__setitem__(
                    "calculation_id", "tail-current-30-call10-greeks"
                ),
            ),
        )
        scenario_arguments[2] = forged_tail
        with mock.patch.object(
            transformations,
            "transform_tail_pricing",
            side_effect=AssertionError("Tail producer called"),
        ) as tail_producer, self.assertRaises(ValueError):
            transform_scenario_valuation(*scenario_arguments)
        tail_producer.assert_not_called()


class TreasuryPricingRateTransformationTests(unittest.TestCase):
    TENORS = (30, 45, 60, 90, 120, 180)
    RATES = tuple(decimal.Decimal(value) for value in (
        "0.0400", "0.0410", "0.0420", "0.0430", "0.0440", "0.0450",
    ))
    CURVE_ID = "USD-US-TREASURY-DAILY-PAR-YIELD"
    COMPOUNDING = (
        "Bond-equivalent yield; simple annualized with semiannual interest convention"
    )
    DAY_COUNT = "Actual days; 365- or 366-day year"
    NORMALIZATION_VERSION = "us-treasury-daily-par-yield-v0.1"

    @classmethod
    def _times(cls, effective_date):
        hour = 20 if effective_date.month == 1 else 19
        observed = datetime.datetime(
            effective_date.year, effective_date.month, effective_date.day,
            hour, 30, tzinfo=datetime.timezone.utc,
        )
        return observed, observed + datetime.timedelta(seconds=1), observed + datetime.timedelta(seconds=2)

    @classmethod
    def _metadata(
        cls,
        effective_date,
        tenor,
        record_prefix="record",
        origin=DataOrigin.PROVIDER_CALCULATED,
        normalization_version=None,
        source_quality_flags=(),
    ):
        observed, retrieved, normalized = cls._times(effective_date)
        source = SourceReference(
            source_id=f"{record_prefix}-source-{tenor:03d}",
            provider_name="U.S. Department of the Treasury",
            dataset_name="Daily Treasury Par Yield Curve Rates",
            provider_record_id=f"{effective_date.isoformat()}:{tenor}",
            provider_request_id=None,
            source_symbol=None,
            source_uri=None,
            observed_at=observed,
            retrieved_at=retrieved,
            provider_timezone="America/New_York",
            timestamp_methodology="synthetic exact effective-date timestamp",
            origin=origin,
            is_delayed=False,
            declared_delay_seconds=None,
            payload_sha256="a" * 64,
            revision_number=None,
            provider_correction_id=None,
            quality_flags=source_quality_flags,
        )
        return NormalizationMetadata(
            record_id=f"{record_prefix}-{tenor:03d}",
            source_references=(source,),
            effective_observed_at=observed,
            normalized_at=normalized,
            record_origin=origin,
            normalization_methodology="synthetic Treasury normalization",
            unit_convention="annualized decimal par yield",
            normalization_version=(
                cls.NORMALIZATION_VERSION
                if normalization_version is None else normalization_version
            ),
            quality_flags=(),
        )

    @classmethod
    def _point(
        cls,
        effective_date,
        tenor,
        rate,
        **overrides,
    ):
        values = {
            "curve_id": cls.CURVE_ID,
            "currency": "USD",
            "tenor_days": tenor,
            "annualized_rate": rate,
            "compounding_convention": cls.COMPOUNDING,
            "day_count_convention": cls.DAY_COUNT,
            "effective_date": effective_date,
            "metadata": cls._metadata(effective_date, tenor),
        }
        values.update(overrides)
        return RateCurvePointObservation(**values)

    @classmethod
    def _curve(
        cls,
        effective_date=datetime.date(2030, 1, 2),
        rates=None,
        record_prefix="record",
    ):
        selected_rates = cls.RATES if rates is None else tuple(rates)
        return tuple(
            cls._point(
                effective_date,
                tenor,
                rate,
                metadata=cls._metadata(
                    effective_date, tenor, record_prefix=record_prefix
                ),
            )
            for tenor, rate in zip(cls.TENORS, selected_rates)
        )

    @classmethod
    def _calculated_at(cls, effective_date=datetime.date(2030, 1, 2)):
        return cls._times(effective_date)[2] + datetime.timedelta(seconds=1)

    @classmethod
    def _transform(cls, target=75, curve=None, calculation_id="treasury-calc"):
        selected_curve = cls._curve() if curve is None else curve
        return transform_treasury_pricing_rate(
            calculation_id, selected_curve, target, cls._calculated_at()
        )

    def test_public_boundary_and_immutable_record_shape(self):
        self.assertEqual(transformations.__all__[-3:], (
            "TreasuryPricingRateInput",
            "TreasuryPricingRateTransformationResult",
            "transform_treasury_pricing_rate",
        ))
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(TreasuryPricingRateInput)),
            (
                "effective_date", "target_tenor_days", "source_curve_id",
                "currency", "source_tenors_days", "source_annualized_par_yields",
                "source_input_references",
                "interpolated_annualized_par_yield",
                "continuously_compounded_rate_proxy",
                "interpolation_methodology", "compounding_conversion_methodology",
                "economic_semantics",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(TreasuryPricingRateTransformationResult)),
            ("record", "lineage"),
        )
        self.assertEqual(
            tuple(inspect.signature(transform_treasury_pricing_rate).parameters),
            ("calculation_id", "curve_points", "target_tenor_days", "calculated_at"),
        )
        self.assertNotIn("TreasuryPricingRateInput", market_data.__all__)
        self.assertFalse(hasattr(convexity_hunter, "TreasuryPricingRateInput"))
        result = self._transform()
        with self.assertRaises(FrozenInstanceError):
            result.record.target_tenor_days = 60  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            result.lineage.calculation_id = "changed"  # type: ignore[misc]

    def test_exact_matches_all_tenors_and_declared_flags(self):
        for target, expected in zip(self.TENORS, self.RATES):
            with self.subTest(target=target):
                result = self._transform(target=target)
                self.assertEqual(result.record.target_tenor_days, target)
                self.assertEqual(result.record.interpolated_annualized_par_yield, expected)
                self.assertEqual(result.record.interpolation_methodology, "exact_tenor_match")
                self.assertEqual(
                    result.record.source_tenors_days,
                    self.TENORS,
                )
                self.assertEqual(
                    result.record.source_annualized_par_yields,
                    self.RATES,
                )
                self.assertEqual(
                    result.lineage.quality_flags,
                    (CalculationQualityFlag.ANNUALIZED,
                     CalculationQualityFlag.ASSUMPTION_APPLIED),
                )
                self.assertEqual(len(result.lineage.inputs), 6)

    def test_est_edt_interpolation_negative_zero_and_literal_formula(self):
        expected = decimal.Decimal(
            "0.04205473438415117438838134298088490"
        )
        for effective_date in (
            datetime.date(2030, 1, 2), datetime.date(2030, 7, 1)
        ):
            with self.subTest(effective_date=effective_date):
                result = transform_treasury_pricing_rate(
                    "interpolation-calc",
                    self._curve(effective_date=effective_date),
                    75,
                    self._calculated_at(effective_date),
                )
                self.assertEqual(
                    result.record.interpolated_annualized_par_yield,
                    decimal.Decimal("0.0425"),
                )
                self.assertEqual(
                    result.record.continuously_compounded_rate_proxy,
                    expected,
                )
                self.assertEqual(
                    result.record.interpolation_methodology,
                    "linear_in_calendar_days_on_provider_native_annualized_par_yields",
                )
                self.assertEqual(
                    result.lineage.quality_flags,
                    (CalculationQualityFlag.INTERPOLATED,
                     CalculationQualityFlag.ANNUALIZED,
                     CalculationQualityFlag.ASSUMPTION_APPLIED),
                )
        for rate in (decimal.Decimal("0.01"), decimal.Decimal("0"), decimal.Decimal("-0.01")):
            with self.subTest(rate=rate):
                result = self._transform(
                    target=30,
                    curve=self._curve(rates=(rate,) * 6),
                    calculation_id=f"rate-{rate}",
                )
                self.assertEqual(
                    result.record.interpolated_annualized_par_yield,
                    rate,
                )
                self.assertFalse(
                    result.record.continuously_compounded_rate_proxy.is_zero()
                    and result.record.continuously_compounded_rate_proxy.is_signed()
                )
        with self.assertRaises(ValueError):
            self._transform(target=30, curve=self._curve(rates=(decimal.Decimal("-2"),) * 6))

    def test_shape_declarations_types_and_no_extrapolation(self):
        curve = self._curve()
        for bad_curve in (
            curve[:5],
            curve[1:] + curve[:1],
            (curve[0], curve[0], *curve[2:]),
        ):
            with self.subTest(bad_curve=bad_curve):
                with self.assertRaises(ValueError):
                    self._transform(curve=bad_curve)
        mixed_date = list(curve)
        mixed_date[1] = self._point(datetime.date(2030, 1, 3), 45, self.RATES[1])
        mixed_curve = list(curve)
        mixed_curve[1] = self._point(
            datetime.date(2030, 1, 2), 45, self.RATES[1], curve_id="OTHER"
        )
        mixed_convention = list(curve)
        mixed_convention[1] = self._point(
            datetime.date(2030, 1, 2), 45, self.RATES[1],
            compounding_convention="Continuous",
        )
        mixed_origin = list(curve)
        mixed_origin[1] = self._point(
            datetime.date(2030, 1, 2), 45, self.RATES[1],
            metadata=self._metadata(
                datetime.date(2030, 1, 2), 45,
                origin=DataOrigin.PROVIDER_REFERENCE,
            ),
        )
        mixed_version = list(curve)
        mixed_version[1] = self._point(
            datetime.date(2030, 1, 2), 45, self.RATES[1],
            metadata=self._metadata(
                datetime.date(2030, 1, 2), 45,
                normalization_version="other-v1",
            ),
        )
        for bad_curve in (tuple(mixed_date), tuple(mixed_curve), tuple(mixed_convention), tuple(mixed_origin), tuple(mixed_version)):
            with self.subTest(bad_curve=bad_curve):
                with self.assertRaises((TypeError, ValueError)):
                    self._transform(curve=bad_curve)
        forged = object.__new__(RateCurvePointObservation)
        for field in dataclasses.fields(RateCurvePointObservation):
            object.__setattr__(forged, field.name, getattr(curve[1], field.name))
        object.__setattr__(forged, "currency", "EUR")
        forged_curve = curve[:1] + (forged,) + curve[2:]
        with self.assertRaises((TypeError, ValueError)):
            self._transform(curve=forged_curve)
        for target in (29, 181):
            with self.subTest(target=target), self.assertRaises(ValueError):
                self._transform(target=target)
        for target in (True, 75.0, decimal.Decimal("75")):
            with self.subTest(target=target), self.assertRaises(TypeError):
                self._transform(target=target)

    def test_lineage_parameters_context_preservation_and_direct_guards(self):
        saved_context = decimal.getcontext().copy()
        try:
            context = decimal.getcontext()
            context.prec = 7
            context.rounding = decimal.ROUND_DOWN
            context.Emin = -5
            context.Emax = 5
            context.flags[decimal.Inexact] = True
            context.traps[decimal.InvalidOperation] = True
            expected_context = context.copy()
            result = self._transform()
            actual_context = decimal.getcontext()
            for attribute in (
                "prec", "rounding", "Emin", "Emax", "capitals", "clamp",
            ):
                self.assertEqual(
                    getattr(actual_context, attribute),
                    getattr(expected_context, attribute),
                )
            self.assertEqual(actual_context.flags, expected_context.flags)
            self.assertEqual(actual_context.traps, expected_context.traps)
        finally:
            decimal.setcontext(saved_context)
        self.assertEqual(result.lineage.calculation_type, "treasury_pricing_rate_proxy")
        self.assertEqual(result.lineage.methodology_version, "v0.1")
        self.assertEqual(
            tuple(item.record_id for item in result.lineage.inputs),
            tuple(f"record-{tenor:03d}" for tenor in self.TENORS),
        )
        self.assertIn('"$decimal":"0.0425"', result.lineage.parameters_json)
        self.assertIn('"$decimal":"0.04205473438415117438838134298088490"', result.lineage.parameters_json)
        decoded = json.loads(result.lineage.parameters_json)

        def assert_no_float(value):
            self.assertNotIsInstance(value, float)
            if isinstance(value, dict):
                for child in value.values():
                    assert_no_float(child)
            elif isinstance(value, list):
                for child in value:
                    assert_no_float(child)

        assert_no_float(decoded)
        with self.assertRaises(TypeError):
            TreasuryPricingRateInput(
                result.record.effective_date,
                result.record.target_tenor_days,
                result.record.source_curve_id,
                result.record.currency,
                list(result.record.source_tenors_days),
                result.record.source_annualized_par_yields,
                result.record.source_input_references,
                result.record.interpolated_annualized_par_yield,
                result.record.continuously_compounded_rate_proxy,
                result.record.interpolation_methodology,
                result.record.compounding_conversion_methodology,
                result.record.economic_semantics,
            )
        forged_record = object.__new__(TreasuryPricingRateInput)
        for field in dataclasses.fields(TreasuryPricingRateInput):
            object.__setattr__(forged_record, field.name, getattr(result.record, field.name))
        object.__setattr__(
            forged_record,
            "continuously_compounded_rate_proxy",
            decimal.Decimal("1"),
        )
        with self.assertRaises(ValueError):
            TreasuryPricingRateTransformationResult(forged_record, result.lineage)

    def test_arbitrary_record_ids_preserve_tenor_binding_and_canonical_lineage(self):
        record_ids = (
            "z-record", "a-record", "y-record",
            "b-record", "x-record", "c-record",
        )
        curve = tuple(
            self._point(
                datetime.date(2030, 1, 2),
                tenor,
                rate,
                metadata=dataclasses.replace(
                    self._metadata(datetime.date(2030, 1, 2), tenor),
                    record_id=record_id,
                ),
            )
            for tenor, rate, record_id in zip(
                self.TENORS, self.RATES, record_ids
            )
        )
        result = self._transform(curve=curve)
        self.assertEqual(
            tuple(
                reference.record_id
                for reference in result.record.source_input_references
            ),
            record_ids,
        )
        self.assertEqual(
            tuple(reference.record_id for reference in result.lineage.inputs),
            tuple(sorted(record_ids)),
        )
        self.assertIs(
            TreasuryPricingRateTransformationResult(
                result.record, result.lineage
            ).record,
            result.record,
        )

    def test_retained_reference_binding_and_nested_integrity(self):
        result = self._transform()
        first = result.record.source_input_references[0]
        changed_reference = dataclasses.replace(
            first, source_ids=("forged-source",)
        )
        changed_record = dataclasses.replace(
            result.record,
            source_input_references=(changed_reference,)
            + result.record.source_input_references[1:],
        )
        with self.assertRaises(ValueError):
            TreasuryPricingRateTransformationResult(
                changed_record, result.lineage
            )

        forged_reference = object.__new__(CalculationInputReference)
        object.__setattr__(forged_reference, "record_id", first.record_id)
        object.__setattr__(forged_reference, "normalized_at", first.normalized_at)
        object.__setattr__(forged_reference, "source_ids", ())
        forged_lineage = object.__new__(CalculationLineage)
        for field in dataclasses.fields(CalculationLineage):
            object.__setattr__(
                forged_lineage, field.name, getattr(result.lineage, field.name)
            )
        object.__setattr__(
            forged_lineage,
            "inputs",
            (forged_reference,) + result.lineage.inputs[1:],
        )
        with self.assertRaises((TypeError, ValueError)):
            TreasuryPricingRateTransformationResult(
                result.record, forged_lineage
            )

    def test_identity_chronology_extremes_and_decimal_exponent_are_guarded(self):
        curve = self._curve()
        with self.assertRaises(ValueError):
            transform_treasury_pricing_rate(
                curve[0].metadata.record_id,
                curve,
                75,
                self._calculated_at(),
            )
        with self.assertRaises(ValueError):
            transform_treasury_pricing_rate(
                "early-calculation",
                curve,
                75,
                curve[0].metadata.normalized_at
                - datetime.timedelta(microseconds=1),
            )
        extreme = decimal.Decimal("1E-999999999999999999")
        with self.assertRaises(ValueError):
            self._transform(
                target=30,
                curve=self._curve(rates=(extreme,) * 6),
            )
        result = self._transform()
        with self.assertRaises(ValueError):
            dataclasses.replace(
                result.record,
                interpolated_annualized_par_yield=decimal.Decimal("0.04250"),
            )

    def test_both_import_orders_are_local_and_unexported(self):
        scripts = (
            "import convexity_hunter.market_data_transformations as t; "
            "import convexity_hunter.market_data as m; "
            "assert t.__all__[-3:] == ('TreasuryPricingRateInput', 'TreasuryPricingRateTransformationResult', 'transform_treasury_pricing_rate'); "
            "assert 'TreasuryPricingRateInput' not in m.__all__",
            "import convexity_hunter.market_data as m; "
            "import convexity_hunter.market_data_transformations as t; "
            "assert t.__all__[-3:] == ('TreasuryPricingRateInput', 'TreasuryPricingRateTransformationResult', 'transform_treasury_pricing_rate'); "
            "assert 'TreasuryPricingRateInput' not in m.__all__",
        )
        for script in scripts:
            completed = subprocess.run(
                [sys.executable, "-c", script],
                cwd=ROOT,
                env={
                    "PYTHONPATH": str(ROOT / "src"),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
