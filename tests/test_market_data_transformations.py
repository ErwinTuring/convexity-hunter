"""Contract tests for Milestone 3C.7a exact-structure liquidity."""

import base64
import copy
import dataclasses
import datetime
import decimal
import enum
import inspect
import json
import math
import pathlib
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
    NormalizationQualityFlag,
    OptionContractReference,
    OptionImpliedVolatilityObservation,
    OptionGreeksObservation,
    OptionQuoteObservation,
    OptionOpenInterestObservation,
    OptionVolumeObservation,
    SelectedFreshMarketDataBinding,
    SourceQualityFlag,
    UnderlyingDailyBarObservation,
    UnderlyingQuoteObservation,
    assess_market_data_historical_series,
    assess_market_data_relationships,
    assess_market_data_snapshot_timing,
    select_market_data_relationship_assessment,
)
from convexity_hunter.market_data_transformations import (
    HistoricalRealizedVolatility,
    HistoricalRealizedVolatilityTransformationResult,
    HistoricalReturnPriceBasis,
    StructureCostsTransformationResult,
    StructureLiquidityTransformationResult,
    ScenarioPricingCalculationResult,
    ScenarioPricingLegCalculation,
    ScenarioPricingMethodology,
    NonExpirationScenarioPricingCalculation,
    TailPricingTransformationResult,
    VolatilityEnvironmentTransformationResult,
    transform_historical_realized_volatility,
    transform_structure_costs,
    transform_structure_liquidity,
    transform_tail_pricing,
    transform_volatility_environment,
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
        self.assertEqual(first_result.lineage.parameters_json,
                         second_result.lineage.parameters_json)
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
        self.assertEqual(lineage.methodology_version, "v0.1")
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
            lineage.parameters_json,
            '{"$map":[["activity_count_unit","contracts"],'
            '["leg_correspondence",{"$list":[{"$map":['
            '["contract_multiplier",100],["currency","USD"],'
            '["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],'
            '["open_interest_record_id","liquidity-call-open-interest"],'
            '["option_type","call"],["quantity",1],'
            '["quote_record_id","liquidity-call-quote"],'
            '["strike",{"$decimal":"100.0"}],'
            '["underlying",{"$map":[["currency","USD"],'
            '["listing_mic","ARCX"],["security_type","etf"],'
            '["symbol","SPY"]]}],'
            '["volume_record_id","liquidity-call-volume"]]}]}],'
            '["minimum_leg_rule",'
            '"minimum_unscaled_contract_count_across_legs"],'
            '["position_value_rule",'
            '"sum(premium_per_underlying_unit*quantity*contract_multiplier)"],'
            '["position_value_unit","usd"],'
            '["premium_input_unit","usd_per_underlying_unit"]]}',
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

    def test_complete_canonical_parameters_golden(self):
        current = (
            (
                SESSION_DATE + datetime.timedelta(days=30),
                "100",
                "0.3",
                "0.3",
            ),
            (
                SESSION_DATE + datetime.timedelta(days=60),
                "100",
                "0.4",
                "0.4",
            ),
        )
        result = make_volatility_result(
            current_candidates=current,
            historical_values=("0.20",),
        )
        self.assertEqual(
            result.lineage.parameters_json,
            '{"$map":[["atm_candidate_universe",{"$map":[["completeness_semantics","no_eligible_paired_call_put_strike_omitted"],["declared_complete",true],["scope","all_exact_selected_session_expiration_universes"]]}],["atm_selection_rule","nearest_paired_call_put_strike_to_underlying_bid_ask_midpoint"],["call_put_combination_rule","arithmetic_mean_of_same_strike_call_and_put_implied_volatility"],["current_observations",{"$list":[{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","ve-current-0-call-reference"],["call_implied_volatility",{"$decimal":"0.3"}],["call_iv_record_id","ve-current-0-call-iv"],["call_quote_record_id","ve-current-0-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.30"}],["put_contract_reference_record_id","ve-current-0-put-reference"],["put_implied_volatility",{"$decimal":"0.3"}],["put_iv_record_id","ve-current-0-put-iv"],["put_quote_record_id","ve-current-0-put-quote"],["strike",{"$decimal":"100"}]]}]}],["expiration",{"$date":"2030-02-01"}],["selected_atm_iv",{"$decimal":"0.30"}],["selected_call_iv_record_id","ve-current-0-call-iv"],["selected_put_iv_record_id","ve-current-0-put-iv"],["selected_strike",{"$decimal":"100"}],["session_date",{"$date":"2030-01-02"}],["tenor_days",30],["underlying_midpoint",{"$decimal":"100.0"}],["underlying_quote_record_id","ve-current-underlying"]]},{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","ve-current-1-call-reference"],["call_implied_volatility",{"$decimal":"0.4"}],["call_iv_record_id","ve-current-1-call-iv"],["call_quote_record_id","ve-current-1-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.40"}],["put_contract_reference_record_id","ve-current-1-put-reference"],["put_implied_volatility",{"$decimal":"0.4"}],["put_iv_record_id","ve-current-1-put-iv"],["put_quote_record_id","ve-current-1-put-quote"],["strike",{"$decimal":"100"}]]}]}],["expiration",{"$date":"2030-03-03"}],["selected_atm_iv",{"$decimal":"0.40"}],["selected_call_iv_record_id","ve-current-1-call-iv"],["selected_put_iv_record_id","ve-current-1-put-iv"],["selected_strike",{"$decimal":"100"}],["session_date",{"$date":"2030-01-02"}],["tenor_days",60],["underlying_midpoint",{"$decimal":"100.0"}],["underlying_quote_record_id","ve-current-underlying"]]}]}],["float_conversion_rule","convert_only_final_decimal_research_values_to_finite_float"],["historical_expected_session_dates",{"$list":[{"$date":"2029-12-30"}]}],["historical_matched_tenor_rule","expiration_minus_session_date_calendar_days_equals_reference_tenor"],["historical_observation_count",1],["historical_observations",{"$list":[{"$map":[["candidate_pairs",{"$list":[{"$map":[["call_contract_reference_record_id","ve-history-0-0-call-reference"],["call_implied_volatility",{"$decimal":"0.19"}],["call_iv_record_id","ve-history-0-0-call-iv"],["call_quote_record_id","ve-history-0-0-call-quote"],["contract_multiplier",100],["currency","USD"],["deliverable_id",null],["distance_to_underlying_midpoint",{"$decimal":"0.0"}],["paired_implied_volatility",{"$decimal":"0.200"}],["put_contract_reference_record_id","ve-history-0-0-put-reference"],["put_implied_volatility",{"$decimal":"0.21"}],["put_iv_record_id","ve-history-0-0-put-iv"],["put_quote_record_id","ve-history-0-0-put-quote"],["strike",{"$decimal":"100"}]]}]}],["expiration",{"$date":"2030-01-29"}],["selected_atm_iv",{"$decimal":"0.200"}],["selected_call_iv_record_id","ve-history-0-0-call-iv"],["selected_put_iv_record_id","ve-history-0-0-put-iv"],["selected_strike",{"$decimal":"100"}],["session_date",{"$date":"2029-12-30"}],["tenor_days",30],["underlying_midpoint",{"$decimal":"100.0"}],["underlying_quote_record_id","ve-history-0-underlying"]]}]}],["historical_sample_semantics","caller_declared_observation_sample"],["iv_methodology",{"$map":[["dividend_input_description","Synthetic dividend input"],["model_name","Synthetic Black-Scholes"],["model_version","fixture-v1"],["rate_input_description","Synthetic USD curve input"],["unit_convention","annualized_decimal_ratio"]]}],["median_formula","odd_middle_even_arithmetic_mean_of_two_middle_values"],["percentile_formula","inclusive_count_historical_atm_iv_lte_current_reference_atm_iv_divided_by_count"],["realized_volatility_dependency",{"$map":[["adjustment_methodology",null],["annualization_sessions_per_year",252],["annualized_realized_volatility_float_repr","0.3328756933888896"],["calculated_at",{"$datetime":"2030-01-02T15:30:04.000000Z"}],["calculation_id","calculation-3c7c"],["calculation_type","historical_realized_volatility"],["end_session_date",{"$date":"2030-01-02"}],["input_record_ids",{"$list":["hrv-0","hrv-1","hrv-2"]}],["methodology_id","historical-log-return-sample-realized-volatility"],["methodology_version","v0.1"],["parameters_json","{\\"$map\\":[[\\"adjustment_methodology\\",null],[\\"annualization_rule\\",\\"daily_sample_standard_deviation_times_square_root_sessions_per_year\\"],[\\"annualization_sessions_per_year\\",252],[\\"expected_session_dates\\",{\\"$list\\":[{\\"$date\\":\\"2029-12-03\\"},{\\"$date\\":\\"2029-12-18\\"},{\\"$date\\":\\"2030-01-02\\"}]}],[\\"price_basis\\",\\"raw_close\\"],[\\"price_observation_count\\",3],[\\"price_unit\\",\\"usd_per_underlying_share\\"],[\\"return_association_rule\\",\\"ending_session\\"],[\\"return_formula\\",\\"natural_log_price_ratio\\"],[\\"return_observation_count\\",2],[\\"return_unit\\",\\"decimal_ratio\\"],[\\"underlying\\",{\\"$map\\":[[\\"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"symbol\\",\\"SPY\\"]]}],[\\"variance_estimator\\",\\"sample_variance\\"],[\\"volatility_unit\\",\\"annualized_decimal_ratio\\"],[\\"window_end_session_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"window_start_session_date\\",{\\"$date\\":\\"2029-12-03\\"}]]}"],["price_basis","raw_close"],["quality_flags",{"$list":["decimal_to_float_converted","annualized","assumption_applied"]}],["return_formula","natural_log_price_ratio"],["start_session_date",{"$date":"2029-12-03"}],["underlying",{"$map":[["currency","USD"],["listing_mic","ARCX"],["security_type","etf"],["symbol","SPY"]]}],["variance_estimator","sample_variance"]]}],["realized_window_matching_rule","realized_end_equals_current_as_of_and_calendar_span_equals_reference_tenor"],["reference_tenor_days",30],["strike_tie_rule","lower_strike"],["term_tenor_rule","expiration_minus_session_date_calendar_days"],["underlying_midpoint_rule","bid_ask_midpoint_no_last_fallback"],["volatility_unit","annualized_decimal_ratio"]]}',
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
        self.assertEqual(result.lineage.methodology_version, "v0.1")
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

    def test_complete_canonical_parameters_literal_golden(self):
        expected_compressed = "c-rk<S##US5&kPGRvyJI0;I5(-;&)tClx1ENfs^?1dOCv<KW_;R&n{ir+W@ya11a2Nr|A><+3HRr|0^n=j-kn;Opv7vA<t^{N<OGpZL*hL4(|jN%5S9X_P*_u5Q295>FW+Uve*`2O5$j^k}j#3oj&jkkNfX(`0qK`t+I<&ji%mNU<9xw)%WqDTvdML|)>@q*356kso|ne+r({h~!=Q1Icn;$0Pl{C^ND?SgKU!7i6SK|N8XvO;BbB(rr_j(83GS<UkTp?58v-GCwHRA$g<;32y>FNfR3Q(G3do7Sh8J!vTejhoX|z4g*Nc90DlW?Y^HRr61A%kq~qRH1;D@Pt(=s&)=|+U&Qdm9(qKQpotSd_tHl%gvPLs*$*FA_GY_TZ>;skUNHqQkU<&2ccJGOm0&^Rrtm+lyN}z=$Ib4C4g2%oW@%`wM?+|@^1*r={1~p<QpM{Y2l<fV?-4CtJ(3(~mL@UunM;>h20we)we%q;*@2bJS>qy_7tlMUn}COqVw=6aPcyw#6yeA+EO{AuBv3~{;HMzXLf-ZRS&O>Yn>7|#S8}o&kw@cwL}9S%4)8(alLKS6`C+@M1_$I1BX!V2t^Bt#Eymi!WOxzTow$q&ip|Pax7KD;4<aIB1z2O^09y*M^&cX_bSGsLvCm<!d>o4+1ptO5i(YB+<i#}Hr!*-#-4ngT(S~s_8V^~dEGEqX$hW2dHB6WRCVm*MK#V_%jtoCa*Q1{o8T~?9Ra>m9uryiq<o7*gt2ODaKpWN-Z)8p)67cmGLu>WJR|!r6R#j@kU{qxWI?2RxG=ifxrXWe0fz&Ik&MkxIIL@FFi8MucaE59*w2rsuwh`7bHezRHBdm!w!dj}0*v+#M)_fbWGqMrZBpYF!)<$gMubGY5O|=o$92;T1k&STP%0}=hcm{B%8B)r3;T*jBSFpfGu@38g(4ur|8MP^$63eqH_B5-a_IS2kv8^Gy(yn66vb5z-W?QVaeQ#!4Y*X8!gV>05(G1Da_Qk$mTlQK~!83D^x)UQ7MzJn{$P(+cnD@v0#Y$_#rmUW`!+HZ1;s2KS-`0^nz0)x4;`Gx&Ee9Ut>YBYq&sBz*RsSxe-FgQpf^Iv|LU_m+ju~(rzz5d$h$R|88-tn>HR9mp)^ZJtdtF<tb=&Dyi`B7>18ghYKKYpsBJhRxYtFv<>avZ_#huP&VTgKDEE6>MIdK8R4Y42v`w40iShQYFVn4x17l^s5B=umIc%ryR2m{Z|46X`p0lYM(1sDVuTjau~5=1@|6G}l%k(GpfnFr~fFukaQ{ElY7HYmbm)aJ2jF|>sTR(O|q5fsSEi0exTRGJsMHa2&%2MSg-|5Di((e$biH2r}lezOKYqs4QKVInUkeu6=q90p(3zzV}qd;R;7tU?4)R5Bx`1C0vKM{8=Dlx9SBgxIit4A>fV9QwMz>K1kw>U5bG?5@5kr4FOD(Suq|%W7-NFezEAOLAPva@>mMFhxLgDpaae$E~=IJ4SYTJ6-izOL;V7RTmr~KHYI>m>bb69n=QrslD6xS5?hY4+ZKkq0SLs6Fm*F_z;K<*j1>I6!uXGNY>#P+3*%28XICgEgA!+mKco;Rf`(wyU&Gdg4Ex4bi$-`O_N-~liZaVS{YfAYV>re-L+cM<x!irvr5+SR%vH$m8=<7$+{-1w3~00tYfXx&e$qhldY0<KC6TQpea^qH^(YjbFGr~K32(jd#fa->oH1wk)LA>x#n#AGoV{Z^y)nVrHkrx9m#<*2G8EXk4lo`LIVK`wKH{M@DvXbK+)u>I52&tPZ==j>tav8wH3yG5j=xFK8jVF75W>~q|6)jA#6wz`h3(q@>}Ugxw2H5u5Q~q-mS~sTb<B5a8kXuHpBi~_oMc|$E7sb0s8&T#qR<3^gTf93Qyk!Y-?;6=(_6T`#`T7f9jn8!*x@30(;6%poi$_UZ5SY6Yd78aeGsa+81U~_XEYIfrq|_h1HB{;8>E(t0EPub>s!aVBxWnIsnrNo9NHBuxfOtTZHoZa7#<NalEA=EcQ1hU!QLgBK^l(TDn^YTtv~<`4%4T(426oBQY@vsh@a{X$JPrXNA%*#CZ;3$O$O(dSWKUODaY9&MQ|k$pWk%K36r;B#6o!EF|BzyjD^OW+=j4QG``$dnLZ)BOiJXuX5kxV?{*Ql=Ck2ah=XY`{A!;USLqJg@?*k%h3`b;_D{&pi|x}&<qf@@9c&oRNmJL&Sf&P&sg`tqutsce!O$;x7!c!=iaF|srr17vNrLAP>Zc~&Il=cqjE|}E)DgZP|&JPo)luT%2f39M3ltkF^yEVBknDF;qs_EZvn>LtDitag-kWr+G^|?K8D>27EiL~t9>n-zwR`@C;rN<5O53$+-3}xef`yS1%O-*Ay*3`SAmh+1`;EMD1rZkJ_QylEgDb*pn<qJ4^&JHOg*qgpoAG1%``1~aOm<zyW@y;Ys|WAAM7K)E}I-zPLIp^pDQOAf5(61UIAVc{Pyj3K*ahmAW}iatq3*zw1;UW-h-dhyc(;_fANAS&56=uF4v{PSZ3RhL3>!KD)W$yin1@|&oIP_W{xJ$&+{~(Ju?T3fED9o*DWXwo|I2~_!yQI0L0@h;-<G#u)i~QQ>f9KrY)}(Dm!UCsZ9V^1Xk)o5?gCP1n_-6s3iXUkDvanh~xxxpp|1bq#B*#QI&a(AJVA$^3&h{!@jI$`v7|iW5ooj0~adIDp|2Kq=ceWF|du%&~9>d(HEM8>5JE~WA!Kvg0!Io7Hw7-s%fkk=)SZz3fR%o)IjIoqeIB|5&x-cI%Ox(*;Slomc420`TW;BFJs0cJb%xad}U!<z-1X24QM6f?sQ#4DC^LQ%I?|$$bM%^#UOse@F$6{iaq9N1Mb9k9CM5+0p2Qx(}OjXY2&PtueL!k-^|0u_EgS&C4qPn-g|YhmK_Yn6jJ5n=X)ScgHC?y(-!@f*)K}!CPe8ASTjlg1#{2hBf=0Bi|layT3tKk<|U~Y`FY_z0vUe*!Yh=tSL!GgWqHsB>KiF~J>nauxbc?`+C}QNZ;0h#1vYZ5L%P#Of{50<4ypoHx9U0k&^#R3UvRhTIh7^PGc?lXfMj_Zy_*7VoJf}dth^*Bt>%4YZZ)S*37dnc@RhW($p4BXMXl^_mHcgZWtxga(1M-z%BEDy^2&J3UG#*@;!<k)3;0o6QI%w_hD&HsmVm+Gv*wY1Z{De3ostQMgvX96*BzH(9_>N7q2pvnp4p#w8qL~xu#Y^ELVIjfmA3D6()JyfmX~7&Th4{}T@dp#?xr)I?$!Gj_>Hh=Q?4ASOQh4HJ9#8)=w#aMY398EAEj#MmbcTsJNM*UyD5_|5BT>?zNY!p5MY1kMSw>4R2XQ~7-GTR4PxQ$+*q(S=f;AZT{A35<QQTBnm-W>jxiQM_bIRdY7DVpSwmQ`&T1E6zgjR9c<ZMjVP_j5fvfHXg1nG8jsvd52nOpB9NeE91`FODc<U$91IH8wy1ii%3`}>1^~lz6f6|>{<Tl|#$RRfT^xRNk@}~1XbQ^MT%8i&I_ld&vCCO<>aNM{9m46{G-PPmBp_cM57!Sad6NZOKPl45hJDCOt_M3he>|z(rW{#z&i=!lRerA&rjDN6|t5YFx+W`YC><f2uzB^xK7z_s9$`}~zyDk_om~uYDa3X4ZBr#bQKOKUB5knn@!MfilAP&xF6Hdf!zbk?|f`f62I*NmaJutfhjYP+*kEgWFkik7h<EzhDY(Gk~pc@-oUVz+>vn(dx;qNo!)z%5()s{iLdiP%OYHP9aYHLosdN=BmSVzaJt!2ckon^<XotYePYrp}W({Mm%G4X0=+3{*;rgLbr`#Yy`4xPostDQy1tDSlNz@2S`gya1IXDRV&XVLL$XP!H-b4+1yq&wg&BVKJSHC}Dah*z6%!{g%B)-}ef>*s@AO1#>+fOz#%DaqBvtDOsoS1;99xwd$<^ZxPbCGyj&i&s1EAFo~_LA{Q6wR5rY>gIWD)-iGAgwI=DEnd}S*AzrJSwIyJdMnRuS5^-Hl3k<$UHLv0PkT=alI>G**Rk=e|5cJEeBSwO+<lhf<<hJrrMbv^BgJp{OtZ(gWhAC$?A2ETp?sO}U**yE#_4zU8T9;dWob?eydI0Ak&q`Je_1KGs-KnC>WnyD&v_}{>{F??fE=%tU)X3qbZuNiRb1Xafg&0C6?E_$Enel_;I$JH`!qpN0O*o5rh(_j5A><TC6B6lpYef%(0#%Ou3B~jiQT;6Ant$2$EwBANgAqm6B=mY_ZsT!47y2AA0MG+Kf1}t6W}yki)DNB*T4OIlPCT@e-=<{-%S@&s@_cJS3a>>-8<@yiw^__;nizgvEar6FFf$IUd^AJ+|g&7w9+hnPw;Fj>ORv18#n!lCUVI$JuAH{mE+BBE~Lo`b?$OZKVLL_wMYM8R^icA7OKnq9Ys(vWnIA!Z<`And-m}q2Ru4$pT;NT^P0_{qdO%dHt_J~%gTw>4PEFhj=l~|M8bft*{6M$x7nxYQgdUSwk|Ct($|5Bm~bXwVs1F9Ptm33$Qo^3V3w?>{SzZnwjm<sM<ROETxzbY-PA?z8gs%Cwqp*5nE{C&HJ6z)8-8!YVo2olyqSF0gz-xiCS=YA-aK&)xwHEH7d+~%_lcz8ZH0lfEAp&~wzE*9<2mml`OVcN+|J@deW#Al`y}4#=aCTh1jnHD;FLe!H}%K+rY`?|Q_Fsnl==Ih&Yw0vhqrsQkFq?M^=i`R=WutwL!b3R(&)`M)6ILe+}mWt2Ok_~lJXimqBt?-wKYz8*`_Hk`z=#mEsQ!F_FlF{WxfWwaFT~q4Cp_S@2jdVKON>QJsswp;ZXs7+K)%YV$xyG($iti8J;E5r~NdTSVTI^S$I0kIsIcKdXyi>C7tD@!<>bu!<^GUO`=EnDd2FK>9Bszv!tw;z6WRImosu?dPP_FSTsq=#!_WF!&KS!ZBu2=MWo7>%zdsfRpwkos%*(l(v_#m%wsi%8MEz1pD`PcdT0`7Mlp`1<j=Mf@@J+*$1shy-DuNjql}?Hn`Xohj!&v>jgo5P_!`QsjgG*gQ*6#9q}Z0~247){&AEgW+fx1D<)zrVoqFFqoAREe<|R>i9a7#7&Hb3DyJVTS?>{n$>Y`&M>IYex=jh4dtv%=$lfzc8dhYcqH(>`}lBznWOo95k)b`s^>uT70tpE&VfTQHWq>zliR?5!<@j63xUk@mUa=ov3CW)GN<fx&MmzD+E27KW<El9wJe#O+{Z9(<MW**_Y<BC#Vaa2*4w>V|(opzj-I>)FDawxl3*Roaa@*vV%uPbZ3Q>^*2GQ4&9e<R+{eg"
        expected = zlib.decompress(
            base64.b85decode(expected_compressed)
        ).decode()
        self.assertEqual(
            make_tail_result(
                historical_skews=("0.06",)
            ).lineage.parameters_json,
            expected,
        )

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
            arguments[4] = VolatilityEnvironmentTransformationResult(
                record=dependency.record,
                lineage=forged_lineage,
            )
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
        ordering_arguments[4] = VolatilityEnvironmentTransformationResult(
            record=dependency.record,
            lineage=forged_lineage,
        )
        with mock.patch.object(
            TailPricingSlice,
            "__init__",
            side_effect=AssertionError(
                "TailPricingSlice must not be constructed before "
                "methodology rejection"
            ),
        ) as tail_init, mock.patch.object(
            CalculationLineage,
            "__init__",
            side_effect=AssertionError(
                "CalculationLineage must not be constructed before "
                "methodology rejection"
            ),
        ) as lineage_init:
            with self.assertRaisesRegex(
                ValueError,
                "dependency IV methodology|authoritative IV inputs",
            ):
                transform_tail_pricing(*ordering_arguments)
            tail_init.assert_not_called()
            lineage_init.assert_not_called()

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


def make_scenario_pricing_result(option_types=("call",)):
    structure = make_structure(option_types)
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
            deliverable_id="standard-100-share",
        )
        for leg in structure.legs
    )
    methodology = make_scenario_pricing_methodology()
    base_ivs = tuple(
        decimal.Decimal(value)
        for value in (("0.20",) if len(contracts) == 1 else ("0.20", "0.30"))
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
                implied_volatility_record_id=f"scenario-iv-{index}",
                contract_reference_record_id=f"scenario-reference-{index}",
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
        self.assertEqual(len(transformations.__all__), 16)
        self.assertEqual(transformations.__all__[-4:], (
            "ScenarioPricingMethodology",
            "ScenarioPricingLegCalculation",
            "NonExpirationScenarioPricingCalculation",
            "ScenarioPricingCalculationResult",
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
        for name in transformations.__all__[-4:]:
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


if __name__ == "__main__":
    unittest.main()
