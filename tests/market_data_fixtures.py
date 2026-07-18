"""Fixed synthetic fixtures for provider-neutral market-data foundations."""

import datetime
import decimal
from typing import Optional

from convexity_hunter.market_data import (
    DataOrigin,
    NormalizationMetadata,
    OptionContractKey,
    SourceReference,
    UnderlyingKey,
    UnderlyingSecurityType,
)


UTC = datetime.timezone.utc
NON_UTC = datetime.timezone(datetime.timedelta(hours=-5))
OBSERVED_AT = datetime.datetime(2030, 1, 2, 15, 30, tzinfo=UTC)
RETRIEVED_AT = datetime.datetime(2030, 1, 2, 15, 30, 2, tzinfo=UTC)
NORMALIZED_AT = datetime.datetime(2030, 1, 2, 15, 30, 3, tzinfo=UTC)
NON_UTC_OBSERVED_AT = datetime.datetime(2030, 1, 2, 10, 30, tzinfo=NON_UTC)
NON_UTC_RETRIEVED_AT = datetime.datetime(2030, 1, 2, 10, 30, 2, tzinfo=NON_UTC)
EXPIRATION = datetime.date(2030, 3, 15)


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
