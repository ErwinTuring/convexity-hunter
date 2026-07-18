"""Fixed synthetic fixtures for provider-neutral market-data foundations."""

import datetime
import decimal
from typing import Optional

from convexity_hunter.market_data import (
    CalculationInputReference,
    CalculationLineage,
    CalculationQualityFlag,
    CorrectionSelection,
    CorrectionSelectionReasonCode,
    CorrectionSelectionStatus,
    DataOrigin,
    DividendObservation,
    DividendStatus,
    FreshnessContext,
    MarketDataFreshnessPolicy,
    MarketPhase,
    NormalizationMetadata,
    OptionContractKey,
    OptionContractReference,
    OptionGreeksObservation,
    OptionImpliedVolatilityObservation,
    OptionOpenInterestObservation,
    OptionQuoteObservation,
    OptionVolumeObservation,
    QuoteScope,
    RateCurvePointObservation,
    SourceReference,
    SourceQualityFlag,
    UnderlyingDailyBarObservation,
    UnderlyingKey,
    UnderlyingQuoteObservation,
    UnderlyingSecurityType,
    canonicalize_lineage_parameters,
)


UTC = datetime.timezone.utc
NON_UTC = datetime.timezone(datetime.timedelta(hours=-5))
OBSERVED_AT = datetime.datetime(2030, 1, 2, 15, 30, tzinfo=UTC)
RETRIEVED_AT = datetime.datetime(2030, 1, 2, 15, 30, 2, tzinfo=UTC)
NORMALIZED_AT = datetime.datetime(2030, 1, 2, 15, 30, 3, tzinfo=UTC)
EVALUATION_AT = datetime.datetime(2030, 1, 2, 15, 31, tzinfo=UTC)
NON_UTC_OBSERVED_AT = datetime.datetime(2030, 1, 2, 10, 30, tzinfo=NON_UTC)
NON_UTC_RETRIEVED_AT = datetime.datetime(2030, 1, 2, 10, 30, 2, tzinfo=NON_UTC)
EXPIRATION = datetime.date(2030, 3, 15)
SESSION_DATE = datetime.date(2030, 1, 2)
CALCULATED_AT = datetime.datetime(2030, 1, 2, 15, 30, 4, tzinfo=UTC)


def build_freshness_policy(**overrides: object) -> MarketDataFreshnessPolicy:
    """Build one explicit synthetic single-record freshness policy."""

    values = {
        "policy_id": "synthetic-freshness",
        "policy_version": "v1",
        "maximum_quote_age_seconds": 60,
        "maximum_analytics_age_seconds": 60,
        "maximum_activity_age_seconds": 120,
        "maximum_reference_age_seconds": 86400,
        "maximum_rate_age_seconds": 86400,
        "maximum_dividend_age_seconds": 86400,
        "maximum_retrieval_lag_seconds": 5,
        "maximum_source_observation_span_seconds": 2,
        "maximum_cross_record_skew_seconds": 10,
        "maximum_open_interest_session_date_gap_days": 3,
        "maximum_historical_bar_session_date_gap_days": 5,
        "allow_delayed_data": False,
        "allow_indicative_data": False,
        "allow_non_firm_data": False,
        "allow_partial_data": False,
        "allow_assigned_timestamps": False,
        "require_regular_session_quotes": True,
        "require_completed_historical_sessions": True,
    }
    values.update(overrides)
    return MarketDataFreshnessPolicy(**values)  # type: ignore[arg-type]


def build_freshness_context(**overrides: object) -> FreshnessContext:
    """Build one explicit synthetic freshness evaluation context."""

    values = {
        "evaluation_at": EVALUATION_AT,
        "latest_completed_session_date": SESSION_DATE,
    }
    values.update(overrides)
    return FreshnessContext(**values)  # type: ignore[arg-type]


def build_source_reference(**overrides: object) -> SourceReference:
    """Build one deterministic non-delayed exchange-observed source."""

    values = {
        "source_id": "source-001",
        "provider_name": "Synthetic Provider",
        "dataset_name": "Synthetic Quotes",
        "provider_record_id": "record-001",
        "provider_request_id": "request-001",
        "source_symbol": "SPY",
        "source_uri": "synthetic://quotes/SPY",
        "observed_at": OBSERVED_AT,
        "retrieved_at": RETRIEVED_AT,
        "provider_timezone": "America/New_York",
        "timestamp_methodology": "Synthetic exchange timestamp",
        "origin": DataOrigin.EXCHANGE_OBSERVED,
        "is_delayed": False,
        "declared_delay_seconds": None,
        "payload_sha256": "a" * 64,
        "revision_number": None,
        "provider_correction_id": None,
        "quality_flags": (),
    }
    values.update(overrides)
    return SourceReference(**values)  # type: ignore[arg-type]


def build_normalization_metadata(
    sources: Optional[object] = None,
    **overrides: object,
) -> NormalizationMetadata:
    """Build one deterministic valid normalization metadata record."""

    normalized_sources = (
        (build_source_reference(),) if sources is None else sources
    )
    source_tuple = tuple(normalized_sources) if isinstance(
        normalized_sources, (tuple, list)
    ) else ()
    effective_at = source_tuple[0].observed_at if len(source_tuple) == 1 else OBSERVED_AT
    values = {
        "record_id": "normalized-001",
        "source_references": normalized_sources,
        "effective_observed_at": effective_at,
        "normalized_at": NORMALIZED_AT,
        "record_origin": DataOrigin.EXCHANGE_OBSERVED,
        "normalization_methodology": "Synthetic direct normalization",
        "unit_convention": "Contract-defined canonical units",
        "normalization_version": "synthetic-v1",
        "quality_flags": (),
    }
    values.update(overrides)
    return NormalizationMetadata(**values)  # type: ignore[arg-type]


def build_correction_source(
    lineage_name: str = "a",
    revision_number: Optional[int] = None,
    provider_correction_id: Optional[str] = None,
    **overrides: object,
) -> SourceReference:
    """Build one fixed source version for correction-selection tests."""

    corrected = (
        revision_number is not None and revision_number > 0
    ) or provider_correction_id is not None
    values = {
        "source_id": f"correction-source-{lineage_name}",
        "provider_name": "Synthetic Provider",
        "dataset_name": f"Synthetic Corrections {lineage_name}",
        "provider_record_id": f"correction-record-{lineage_name}",
        "provider_request_id": f"correction-request-{lineage_name}",
        "source_uri": f"synthetic://corrections/{lineage_name}",
        "payload_sha256": "b" * 64,
        "revision_number": revision_number,
        "provider_correction_id": provider_correction_id,
        "quality_flags": (
            (SourceQualityFlag.CORRECTED,) if corrected else ()
        ),
    }
    values.update(overrides)
    return build_source_reference(**values)


def build_correction_candidate(
    record_id: str = "candidate-001",
    sources: Optional[object] = None,
    **overrides: object,
) -> NormalizationMetadata:
    """Build one fixed normalization candidate for correction selection."""

    normalized_sources = (
        (build_correction_source(),) if sources is None else sources
    )
    values = {
        "record_id": record_id,
        "normalization_methodology": "Synthetic correction normalization",
    }
    values.update(overrides)
    return build_normalization_metadata(
        normalized_sources,
        **values,
    )


def correction_selection_values(**overrides: object) -> dict:
    """Return canonical direct-constructor values for a selected correction."""

    values = {
        "semantic_observation_key": "SPY quote",
        "candidate_record_ids": ("candidate-001",),
        "selected_record_id": "candidate-001",
        "status": CorrectionSelectionStatus.SELECTED,
        "reason_codes": (
            CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
        ),
        "rule_id": "provider-correction-selection",
        "rule_version": "v0.1",
        "evaluated_at": EVALUATION_AT,
    }
    values.update(overrides)
    return values


def build_correction_selection(**overrides: object) -> CorrectionSelection:
    """Build one canonical direct correction-selection result."""

    return CorrectionSelection(**correction_selection_values(**overrides))


def build_underlying_key(**overrides: object) -> UnderlyingKey:
    """Build one deterministic USD-listed ETF identity."""

    values = {
        "symbol": "SPY",
        "listing_mic": "ARCX",
        "security_type": UnderlyingSecurityType.ETF,
        "currency": "USD",
    }
    values.update(overrides)
    return UnderlyingKey(**values)  # type: ignore[arg-type]


def build_option_contract_key(**overrides: object) -> OptionContractKey:
    """Build one deterministic standard option-series identity."""

    values = {
        "underlying_key": build_underlying_key(),
        "expiration": EXPIRATION,
        "option_type": "call",
        "strike": decimal.Decimal("500.1250"),
        "contract_multiplier": 100,
        "currency": "USD",
        "deliverable_id": None,
    }
    values.update(overrides)
    return OptionContractKey(**values)  # type: ignore[arg-type]


def build_underlying_quote_observation(
    **overrides: object,
) -> UnderlyingQuoteObservation:
    """Build one deterministic consolidated underlying quote."""

    values = {
        "underlying_key": build_underlying_key(),
        "session_date": SESSION_DATE,
        "bid_price": decimal.Decimal("499.95"),
        "ask_price": decimal.Decimal("500.05"),
        "last_price": decimal.Decimal("500.00"),
        "bid_size": 800,
        "ask_size": 900,
        "market_phase": MarketPhase.REGULAR,
        "quote_scope": QuoteScope.CONSOLIDATED,
        "venue_mic": None,
        "metadata": build_normalization_metadata(),
    }
    values.update(overrides)
    return UnderlyingQuoteObservation(**values)  # type: ignore[arg-type]


def build_option_contract_reference(
    **overrides: object,
) -> OptionContractReference:
    """Build one deterministic provider-reference option contract record."""

    source = build_source_reference(
        source_id="contract-source-001",
        dataset_name="Synthetic Contract Reference",
        provider_record_id="contract-record-001",
        source_uri="synthetic://contracts/SPY",
        origin=DataOrigin.PROVIDER_REFERENCE,
    )
    metadata = build_normalization_metadata(
        [source],
        record_id="contract-reference-001",
        record_origin=DataOrigin.PROVIDER_REFERENCE,
        normalization_methodology="Synthetic direct contract normalization",
    )
    values = {
        "contract_key": build_option_contract_key(),
        "listing_date": datetime.date(2029, 9, 16),
        "last_trade_date": datetime.date(2030, 3, 14),
        "exercise_style": "American",
        "settlement_type": "Physical",
        "metadata": metadata,
    }
    values.update(overrides)
    return OptionContractReference(**values)  # type: ignore[arg-type]


def build_option_quote_observation(**overrides: object) -> OptionQuoteObservation:
    """Build one deterministic consolidated option quote."""

    values = {
        "contract_key": build_option_contract_key(),
        "session_date": SESSION_DATE,
        "bid_premium": decimal.Decimal("10.25"),
        "ask_premium": decimal.Decimal("10.35"),
        "bid_size": 120,
        "ask_size": 140,
        "market_phase": MarketPhase.REGULAR,
        "quote_scope": QuoteScope.CONSOLIDATED,
        "venue_mic": None,
        "metadata": build_normalization_metadata(),
    }
    values.update(overrides)
    return OptionQuoteObservation(**values)  # type: ignore[arg-type]


def build_option_volume_observation(
    **overrides: object,
) -> OptionVolumeObservation:
    """Build one deterministic incomplete cumulative option-volume record."""

    values = {
        "contract_key": build_option_contract_key(),
        "session_date": SESSION_DATE,
        "cumulative_volume": 1250,
        "is_session_complete": False,
        "metadata": build_normalization_metadata(),
    }
    values.update(overrides)
    return OptionVolumeObservation(**values)  # type: ignore[arg-type]


def build_option_open_interest_observation(
    **overrides: object,
) -> OptionOpenInterestObservation:
    """Build one deterministic option open-interest record."""

    values = {
        "contract_key": build_option_contract_key(),
        "open_interest_session_date": datetime.date(2030, 1, 1),
        "open_interest": 5000,
        "metadata": build_normalization_metadata(),
    }
    values.update(overrides)
    return OptionOpenInterestObservation(**values)  # type: ignore[arg-type]


def build_metadata_for_origin(
    origin: DataOrigin,
    record_id: str,
    dataset_name: str,
) -> NormalizationMetadata:
    """Build deterministic single-source metadata for a non-composite origin."""

    source = build_source_reference(
        source_id=f"{record_id}-source",
        dataset_name=dataset_name,
        provider_record_id=f"{record_id}-provider-record",
        source_uri=f"synthetic://market-data/{record_id}",
        origin=origin,
    )
    return build_normalization_metadata(
        [source],
        record_id=record_id,
        record_origin=origin,
        normalization_methodology="Synthetic direct normalization",
    )


def build_option_implied_volatility_observation(
    **overrides: object,
) -> OptionImpliedVolatilityObservation:
    """Build one deterministic provider-calculated IV observation."""

    values = {
        "contract_key": build_option_contract_key(),
        "session_date": SESSION_DATE,
        "implied_volatility": decimal.Decimal("0.201250"),
        "model_name": "Synthetic Black-Scholes",
        "model_version": "fixture-v1",
        "rate_input_description": "Synthetic USD curve input",
        "dividend_input_description": "Synthetic dividend input",
        "metadata": build_metadata_for_origin(
            DataOrigin.PROVIDER_CALCULATED,
            "iv-observation-001",
            "Synthetic Option Analytics",
        ),
    }
    values.update(overrides)
    return OptionImpliedVolatilityObservation(**values)  # type: ignore[arg-type]


def build_option_greeks_observation(
    **overrides: object,
) -> OptionGreeksObservation:
    """Build one deterministic provider-calculated Greeks observation."""

    values = {
        "contract_key": build_option_contract_key(),
        "session_date": SESSION_DATE,
        "delta": decimal.Decimal("0.512500"),
        "gamma": decimal.Decimal("0.018750"),
        "theta": decimal.Decimal("-0.125000"),
        "vega": decimal.Decimal("1.875000"),
        "theta_day_basis": "Provider calendar-day convention",
        "model_name": "Synthetic Black-Scholes",
        "model_version": "fixture-v1",
        "rate_input_description": "Synthetic USD curve input",
        "dividend_input_description": "Synthetic dividend input",
        "metadata": build_metadata_for_origin(
            DataOrigin.PROVIDER_CALCULATED,
            "greeks-observation-001",
            "Synthetic Option Analytics",
        ),
    }
    values.update(overrides)
    return OptionGreeksObservation(**values)  # type: ignore[arg-type]


def build_underlying_daily_bar_observation(
    **overrides: object,
) -> UnderlyingDailyBarObservation:
    """Build one deterministic completed adjusted underlying daily bar."""

    values = {
        "underlying_key": build_underlying_key(),
        "session_date": SESSION_DATE,
        "open_price": decimal.Decimal("498.2500"),
        "high_price": decimal.Decimal("502.7500"),
        "low_price": decimal.Decimal("497.5000"),
        "close_price": decimal.Decimal("501.1250"),
        "adjusted_close_price": decimal.Decimal("500.8750"),
        "volume": 75000000,
        "is_session_complete": True,
        "adjustment_methodology": "Synthetic split-and-dividend adjustment",
        "metadata": build_metadata_for_origin(
            DataOrigin.PROVIDER_CALCULATED,
            "daily-bar-001",
            "Synthetic Daily Bars",
        ),
    }
    values.update(overrides)
    return UnderlyingDailyBarObservation(**values)  # type: ignore[arg-type]


def build_rate_curve_point_observation(
    **overrides: object,
) -> RateCurvePointObservation:
    """Build one deterministic provider-reference USD rate point."""

    values = {
        "curve_id": "USD-SYNTHETIC-OIS",
        "currency": "USD",
        "tenor_days": 30,
        "annualized_rate": decimal.Decimal("0.042500"),
        "compounding_convention": "Continuous",
        "day_count_convention": "Actual/365",
        "effective_date": SESSION_DATE,
        "metadata": build_metadata_for_origin(
            DataOrigin.PROVIDER_REFERENCE,
            "rate-point-001",
            "Synthetic Rate Curve",
        ),
    }
    values.update(overrides)
    return RateCurvePointObservation(**values)  # type: ignore[arg-type]


def build_dividend_observation(**overrides: object) -> DividendObservation:
    """Build one deterministic announced provider-reference dividend."""

    values = {
        "underlying_key": build_underlying_key(),
        "dividend_type": "Regular Cash",
        "ex_date": datetime.date(2030, 2, 15),
        "payment_date": datetime.date(2030, 3, 1),
        "cash_amount": decimal.Decimal("1.7500"),
        "annualized_yield": decimal.Decimal("0.014000"),
        "currency": "USD",
        "status": DividendStatus.ANNOUNCED,
        "metadata": build_metadata_for_origin(
            DataOrigin.PROVIDER_REFERENCE,
            "dividend-001",
            "Synthetic Dividend Reference",
        ),
    }
    values.update(overrides)
    return DividendObservation(**values)  # type: ignore[arg-type]


def build_calculation_input_reference(
    record_id: str = "normalized-001",
    **overrides: object,
) -> CalculationInputReference:
    """Build one fixed normalized-record reference for lineage tests."""

    values = {
        "record_id": record_id,
        "normalized_at": NORMALIZED_AT,
        "source_ids": ("source-001",),
    }
    values.update(overrides)
    return CalculationInputReference(**values)  # type: ignore[arg-type]


def build_calculation_lineage(**overrides: object) -> CalculationLineage:
    """Build one fixed deterministic calculation-lineage sidecar."""

    values = {
        "calculation_id": "calculation-001",
        "calculation_type": "synthetic-volatility-metric",
        "methodology_id": "synthetic-methodology",
        "methodology_version": "v1",
        "calculated_at": CALCULATED_AT,
        "inputs": (build_calculation_input_reference(),),
        "parameters_json": canonicalize_lineage_parameters({
            "annualization_days": 252,
            "window": decimal.Decimal("30.00"),
        }),
        "quality_flags": (CalculationQualityFlag.ANNUALIZED,),
    }
    values.update(overrides)
    return CalculationLineage(**values)  # type: ignore[arg-type]
