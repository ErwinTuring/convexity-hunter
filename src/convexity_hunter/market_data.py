"""Provider-neutral provenance and identity foundations for market data."""

import datetime
import decimal
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Type, TypeVar


__all__ = (
    "DataOrigin",
    "SourceQualityFlag",
    "NormalizationQualityFlag",
    "MarketPhase",
    "QuoteScope",
    "UnderlyingSecurityType",
    "DividendStatus",
    "SourceReference",
    "NormalizationMetadata",
    "UnderlyingKey",
    "OptionContractKey",
    "UnderlyingQuoteObservation",
    "OptionContractReference",
    "OptionQuoteObservation",
    "OptionVolumeObservation",
    "OptionOpenInterestObservation",
    "OptionImpliedVolatilityObservation",
    "OptionGreeksObservation",
    "UnderlyingDailyBarObservation",
    "RateCurvePointObservation",
    "DividendObservation",
)


_Flag = TypeVar("_Flag", bound=Enum)


def _normalize_required_string(name: str, value: object) -> str:
    """Require and trim a non-empty string."""

    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _normalize_optional_string(name: str, value: object) -> Optional[str]:
    """Require and trim an optional non-empty string."""

    if value is None:
        return None
    return _normalize_required_string(name, value)


def _validate_integer(name: str, value: object, minimum: int) -> None:
    """Require a non-Boolean integer at or above a field minimum."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        comparison = "greater than 0" if minimum == 1 else "0 or greater"
        raise ValueError(f"{name} must be {comparison}")


def _validate_date_only(name: str, value: object) -> None:
    """Require a calendar date without a time component."""

    if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
        raise TypeError(f"{name} must be a date without a time component")


def _validate_optional_date_only(name: str, value: object) -> None:
    """Require an optional calendar date without a time component."""

    if value is not None:
        _validate_date_only(name, value)


def _normalize_utc_datetime(name: str, value: object) -> datetime.datetime:
    """Require an aware datetime and normalize it to UTC."""

    if not isinstance(value, datetime.datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(datetime.timezone.utc)


def _validate_positive_decimal(name: str, value: object) -> None:
    """Require a finite Decimal greater than zero."""

    if not isinstance(value, decimal.Decimal):
        raise TypeError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")


def _normalize_finite_decimal(name: str, value: object) -> decimal.Decimal:
    """Require a finite Decimal and remove a zero sign without rounding."""

    if not isinstance(value, decimal.Decimal):
        raise TypeError(f"{name} must be a Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    return value.copy_abs() if value.is_zero() else value


def _normalize_nonnegative_decimal(
    name: str, value: object
) -> decimal.Decimal:
    """Require a finite nonnegative Decimal and remove a zero sign."""

    normalized = _normalize_finite_decimal(name, value)
    if normalized < 0:
        raise ValueError(f"{name} must be 0 or greater")
    return normalized


def _normalize_positive_decimal(name: str, value: object) -> decimal.Decimal:
    """Require and return a finite positive Decimal."""

    _validate_positive_decimal(name, value)
    return value  # type: ignore[return-value]


def _validate_optional_nonnegative_integer(name: str, value: object) -> None:
    """Require an optional nonnegative non-Boolean integer."""

    if value is not None:
        _validate_integer(name, value, 0)


def _validate_boolean(name: str, value: object) -> None:
    """Require an actual Boolean value."""

    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a Boolean")


def _validate_metadata(metadata: object) -> None:
    """Require normalization metadata for a normalized record."""

    if not isinstance(metadata, NormalizationMetadata):
        raise TypeError("metadata must be a NormalizationMetadata")


def _validate_market_observation_metadata(metadata: object) -> None:
    """Reject reference-origin metadata for a market observation."""

    _validate_metadata(metadata)
    if metadata.record_origin is DataOrigin.PROVIDER_REFERENCE:  # type: ignore[union-attr]
        raise ValueError("market observations must not use provider_reference origin")


def _validate_contract_reference_metadata(metadata: object) -> None:
    """Require reference or system-composite metadata for contract terms."""

    _validate_metadata(metadata)
    if metadata.record_origin not in {  # type: ignore[union-attr]
        DataOrigin.PROVIDER_REFERENCE,
        DataOrigin.SYSTEM_COMPOSITE,
    }:
        raise ValueError(
            "contract references require provider_reference or system_composite origin"
        )


def _validate_analytics_metadata(metadata: object) -> None:
    """Require calculated or composite origin for option analytics."""

    _validate_metadata(metadata)
    if metadata.record_origin not in {  # type: ignore[union-attr]
        DataOrigin.PROVIDER_CALCULATED,
        DataOrigin.SYSTEM_COMPOSITE,
    }:
        raise ValueError(
            "option analytics require provider_calculated or system_composite origin"
        )


def _validate_rate_metadata(metadata: object) -> None:
    """Reject exchange-observed origin for a normalized rate point."""

    _validate_metadata(metadata)
    if metadata.record_origin is DataOrigin.EXCHANGE_OBSERVED:  # type: ignore[union-attr]
        raise ValueError("rate points must not use exchange_observed origin")


def _validate_dividend_metadata(
    metadata: object, status: "DividendStatus"
) -> None:
    """Validate dividend origin according to its declared lifecycle status."""

    _validate_metadata(metadata)
    if status is DividendStatus.FORECAST:
        allowed = {
            DataOrigin.PROVIDER_CALCULATED,
            DataOrigin.SYSTEM_COMPOSITE,
        }
    else:
        allowed = {
            DataOrigin.PROVIDER_REFERENCE,
            DataOrigin.SYSTEM_COMPOSITE,
        }
    if metadata.record_origin not in allowed:  # type: ignore[union-attr]
        raise ValueError(
            f"{status.value} dividend has an incompatible metadata origin"
        )


def _normalize_quote_scope_and_venue(
    quote_scope: object, venue_mic: object
) -> Tuple["QuoteScope", Optional[str]]:
    """Validate quote scope and its optional execution venue."""

    if not isinstance(quote_scope, QuoteScope):
        raise TypeError("quote_scope must be a QuoteScope")
    normalized_venue = _normalize_optional_string("venue_mic", venue_mic)
    if normalized_venue is not None:
        normalized_venue = normalized_venue.upper()
    if quote_scope is QuoteScope.VENUE_SPECIFIC:
        if normalized_venue is None:
            raise ValueError("venue_specific quotes require venue_mic")
    elif normalized_venue is not None:
        raise ValueError(f"{quote_scope.value} quotes require venue_mic to be None")
    return quote_scope, normalized_venue


def _validate_locked_quote(
    bid: decimal.Decimal,
    ask: decimal.Decimal,
    metadata: "NormalizationMetadata",
) -> None:
    """Require source evidence when a normalized quote is locked."""

    if ask < bid:
        raise ValueError("ask must not be below bid")
    if bid == ask and not any(
        SourceQualityFlag.LOCKED in source.quality_flags
        for source in metadata.source_references
    ):
        raise ValueError("equal bid and ask require a locked source flag")


def _normalize_enum_flags(
    name: str,
    values: object,
    enum_type: Type[_Flag],
) -> Tuple[_Flag, ...]:
    """Normalize an ordered enum collection into declaration order."""

    if not isinstance(values, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list")
    normalized = tuple(values)
    if not all(isinstance(item, enum_type) for item in normalized):
        raise TypeError(f"every {name} item must be a {enum_type.__name__}")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{name} must not contain duplicates")
    selected = set(normalized)
    return tuple(item for item in enum_type if item in selected)


class DataOrigin(str, Enum):
    """Origin category for source and normalized records."""

    EXCHANGE_OBSERVED = "exchange_observed"
    PROVIDER_CALCULATED = "provider_calculated"
    PROVIDER_REFERENCE = "provider_reference"
    SYSTEM_COMPOSITE = "system_composite"


class SourceQualityFlag(str, Enum):
    """Provider or exchange conditions attached to a source."""

    DELAYED = "delayed"
    INDICATIVE = "indicative"
    NON_FIRM = "non_firm"
    LOCKED = "locked"
    HALTED = "halted"
    AFTER_HOURS = "after_hours"
    CORRECTED = "corrected"
    PROVIDER_ESTIMATED = "provider_estimated"
    PARTIAL = "partial"
    UNKNOWN_CONDITION = "unknown_condition"


class NormalizationQualityFlag(str, Enum):
    """Deterministic conditions introduced during normalization."""

    UNIT_CONVERTED = "unit_converted"
    SYMBOL_MAPPED = "symbol_mapped"
    CONTRACT_ADJUSTED = "contract_adjusted"
    COMPOSITE_SOURCE = "composite_source"
    INTERPOLATED = "interpolated"
    TIMESTAMP_ASSIGNED = "timestamp_assigned"
    INCOMPLETE = "incomplete"


class MarketPhase(str, Enum):
    """Declared market phase for a future observation."""

    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    POST_MARKET = "post_market"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class QuoteScope(str, Enum):
    """Aggregation scope for a future quote observation."""

    CONSOLIDATED = "consolidated"
    VENUE_SPECIFIC = "venue_specific"
    PROVIDER_COMPOSITE = "provider_composite"
    UNKNOWN = "unknown"


class UnderlyingSecurityType(str, Enum):
    """Supported MVP underlying-security categories."""

    EQUITY = "equity"
    ETF = "etf"


class DividendStatus(str, Enum):
    """Lifecycle status for a future dividend observation."""

    FORECAST = "forecast"
    ANNOUNCED = "announced"
    HISTORICAL = "historical"


@dataclass(frozen=True)
class SourceReference:
    """Immutable provider-neutral reference to source material."""

    source_id: str
    provider_name: str
    dataset_name: str
    provider_record_id: Optional[str]
    provider_request_id: Optional[str]
    source_symbol: Optional[str]
    source_uri: Optional[str]
    observed_at: datetime.datetime
    retrieved_at: datetime.datetime
    provider_timezone: Optional[str]
    timestamp_methodology: str
    origin: DataOrigin
    is_delayed: bool
    declared_delay_seconds: Optional[int]
    payload_sha256: Optional[str]
    revision_number: Optional[int]
    provider_correction_id: Optional[str]
    quality_flags: Tuple[SourceQualityFlag, ...]

    def __post_init__(self) -> None:
        required_strings = {
            "source_id": _normalize_required_string("source_id", self.source_id),
            "provider_name": _normalize_required_string(
                "provider_name", self.provider_name
            ),
            "dataset_name": _normalize_required_string(
                "dataset_name", self.dataset_name
            ),
            "timestamp_methodology": _normalize_required_string(
                "timestamp_methodology", self.timestamp_methodology
            ),
        }
        optional_strings = {
            "provider_record_id": _normalize_optional_string(
                "provider_record_id", self.provider_record_id
            ),
            "provider_request_id": _normalize_optional_string(
                "provider_request_id", self.provider_request_id
            ),
            "source_symbol": _normalize_optional_string(
                "source_symbol", self.source_symbol
            ),
            "source_uri": _normalize_optional_string("source_uri", self.source_uri),
            "provider_timezone": _normalize_optional_string(
                "provider_timezone", self.provider_timezone
            ),
            "payload_sha256": _normalize_optional_string(
                "payload_sha256", self.payload_sha256
            ),
            "provider_correction_id": _normalize_optional_string(
                "provider_correction_id", self.provider_correction_id
            ),
        }

        if not isinstance(self.origin, DataOrigin):
            raise TypeError("origin must be a DataOrigin")
        if self.origin is DataOrigin.SYSTEM_COMPOSITE:
            raise ValueError("SourceReference origin must not be system_composite")

        observed_at = _normalize_utc_datetime("observed_at", self.observed_at)
        retrieved_at = _normalize_utc_datetime("retrieved_at", self.retrieved_at)
        if retrieved_at < observed_at:
            raise ValueError("retrieved_at must not be earlier than observed_at")

        if not isinstance(self.is_delayed, bool):
            raise TypeError("is_delayed must be a Boolean")
        if self.declared_delay_seconds is not None:
            _validate_integer(
                "declared_delay_seconds", self.declared_delay_seconds, 1
            )

        flags = _normalize_enum_flags(
            "quality_flags", self.quality_flags, SourceQualityFlag
        )
        delayed_flag_present = SourceQualityFlag.DELAYED in flags
        if self.is_delayed:
            if self.declared_delay_seconds is None:
                raise ValueError("delayed sources require declared_delay_seconds")
            if not delayed_flag_present:
                raise ValueError("delayed sources require the delayed quality flag")
        else:
            if self.declared_delay_seconds is not None:
                raise ValueError(
                    "non-delayed sources require declared_delay_seconds to be None"
                )
            if delayed_flag_present:
                raise ValueError(
                    "non-delayed sources must not carry the delayed quality flag"
                )

        payload_sha256 = optional_strings["payload_sha256"]
        if payload_sha256 is not None and re.fullmatch(
            r"[0-9a-f]{64}", payload_sha256
        ) is None:
            raise ValueError(
                "payload_sha256 must be 64 lowercase hexadecimal characters"
            )

        if self.revision_number is not None:
            _validate_integer("revision_number", self.revision_number, 0)

        correction_id = optional_strings["provider_correction_id"]
        if correction_id is not None and correction_id in {
            optional_strings["provider_record_id"],
            optional_strings["provider_request_id"],
        }:
            raise ValueError(
                "provider_correction_id must differ from provider record and request IDs"
            )
        correction_identity_present = (
            self.revision_number is not None and self.revision_number > 0
        ) or correction_id is not None
        corrected_flag_present = SourceQualityFlag.CORRECTED in flags
        if corrected_flag_present and not correction_identity_present:
            raise ValueError(
                "the corrected flag requires a positive revision or correction ID"
            )
        if correction_identity_present and not corrected_flag_present:
            raise ValueError(
                "a positive revision or correction ID requires the corrected flag"
            )

        for name, value in required_strings.items():
            object.__setattr__(self, name, value)
        for name, value in optional_strings.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "retrieved_at", retrieved_at)
        object.__setattr__(self, "quality_flags", flags)


@dataclass(frozen=True)
class NormalizationMetadata:
    """Immutable provenance and timing for one normalized record version."""

    record_id: str
    source_references: Tuple[SourceReference, ...]
    effective_observed_at: datetime.datetime
    normalized_at: datetime.datetime
    record_origin: DataOrigin
    normalization_methodology: str
    unit_convention: str
    normalization_version: str
    quality_flags: Tuple[NormalizationQualityFlag, ...]

    def __post_init__(self) -> None:
        record_id = _normalize_required_string("record_id", self.record_id)
        methodology = _normalize_required_string(
            "normalization_methodology", self.normalization_methodology
        )
        unit_convention = _normalize_required_string(
            "unit_convention", self.unit_convention
        )
        version = _normalize_required_string(
            "normalization_version", self.normalization_version
        )

        if not isinstance(self.source_references, (tuple, list)):
            raise TypeError("source_references must be a tuple or list")
        sources = tuple(self.source_references)
        if not sources:
            raise ValueError("source_references must contain at least one item")
        if not all(isinstance(source, SourceReference) for source in sources):
            raise TypeError("every source_references item must be a SourceReference")
        source_ids = tuple(source.source_id for source in sources)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("source_references must have unique source IDs")
        sources = tuple(sorted(sources, key=lambda source: source.source_id))

        effective_at = _normalize_utc_datetime(
            "effective_observed_at", self.effective_observed_at
        )
        normalized_at = _normalize_utc_datetime("normalized_at", self.normalized_at)
        observed_times = tuple(source.observed_at for source in sources)
        if len(sources) == 1:
            if effective_at != observed_times[0]:
                raise ValueError(
                    "single-source effective_observed_at must equal source observed_at"
                )
        elif not min(observed_times) <= effective_at <= max(observed_times):
            raise ValueError(
                "multi-source effective_observed_at must fall within source times"
            )
        if normalized_at < effective_at:
            raise ValueError(
                "normalized_at must not be earlier than effective_observed_at"
            )
        if any(normalized_at < source.retrieved_at for source in sources):
            raise ValueError(
                "normalized_at must not be earlier than source retrieval times"
            )

        if not isinstance(self.record_origin, DataOrigin):
            raise TypeError("record_origin must be a DataOrigin")
        flags = _normalize_enum_flags(
            "quality_flags", self.quality_flags, NormalizationQualityFlag
        )
        if self.record_origin is DataOrigin.SYSTEM_COMPOSITE:
            if len(sources) < 2:
                raise ValueError("system_composite records require at least two sources")
            if NormalizationQualityFlag.COMPOSITE_SOURCE not in flags:
                raise ValueError(
                    "system_composite records require the composite_source flag"
                )

        object.__setattr__(self, "record_id", record_id)
        object.__setattr__(self, "source_references", sources)
        object.__setattr__(self, "effective_observed_at", effective_at)
        object.__setattr__(self, "normalized_at", normalized_at)
        object.__setattr__(self, "normalization_methodology", methodology)
        object.__setattr__(self, "unit_convention", unit_convention)
        object.__setattr__(self, "normalization_version", version)
        object.__setattr__(self, "quality_flags", flags)


@dataclass(frozen=True)
class UnderlyingKey:
    """Canonical identity for one supported underlying listing."""

    symbol: str
    listing_mic: Optional[str]
    security_type: UnderlyingSecurityType
    currency: str

    def __post_init__(self) -> None:
        symbol = _normalize_required_string("symbol", self.symbol).upper()
        listing_mic = _normalize_optional_string(
            "listing_mic", self.listing_mic
        )
        if listing_mic is not None:
            listing_mic = listing_mic.upper()
        if not isinstance(self.security_type, UnderlyingSecurityType):
            raise TypeError("security_type must be an UnderlyingSecurityType")
        currency = _normalize_required_string("currency", self.currency).upper()
        if currency != "USD":
            raise ValueError("currency must be USD for MVP v0.1")

        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "listing_mic", listing_mic)
        object.__setattr__(self, "currency", currency)


@dataclass(frozen=True)
class OptionContractKey:
    """Canonical economic identity for one option series."""

    underlying_key: UnderlyingKey
    expiration: datetime.date
    option_type: str
    strike: decimal.Decimal
    contract_multiplier: int
    currency: str
    deliverable_id: Optional[str]

    def __post_init__(self) -> None:
        if not isinstance(self.underlying_key, UnderlyingKey):
            raise TypeError("underlying_key must be an UnderlyingKey")
        _validate_date_only("expiration", self.expiration)
        option_type = _normalize_required_string(
            "option_type", self.option_type
        ).lower()
        if option_type not in {"call", "put"}:
            raise ValueError("option_type must be 'call' or 'put'")
        _validate_positive_decimal("strike", self.strike)
        _validate_integer("contract_multiplier", self.contract_multiplier, 1)
        currency = _normalize_required_string("currency", self.currency).upper()
        if currency != self.underlying_key.currency:
            raise ValueError("currency must equal underlying_key.currency")
        deliverable_id = _normalize_optional_string(
            "deliverable_id", self.deliverable_id
        )

        object.__setattr__(self, "option_type", option_type)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "deliverable_id", deliverable_id)


@dataclass(frozen=True)
class UnderlyingQuoteObservation:
    """One normalized underlying quote in canonical per-share units."""

    underlying_key: UnderlyingKey
    session_date: datetime.date
    bid_price: decimal.Decimal
    ask_price: decimal.Decimal
    last_price: Optional[decimal.Decimal]
    bid_size: Optional[int]
    ask_size: Optional[int]
    market_phase: MarketPhase
    quote_scope: QuoteScope
    venue_mic: Optional[str]
    metadata: NormalizationMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.underlying_key, UnderlyingKey):
            raise TypeError("underlying_key must be an UnderlyingKey")
        _validate_date_only("session_date", self.session_date)
        bid = _normalize_nonnegative_decimal("bid_price", self.bid_price)
        ask = _normalize_positive_decimal("ask_price", self.ask_price)
        last = None
        if self.last_price is not None:
            last = _normalize_positive_decimal("last_price", self.last_price)
        _validate_optional_nonnegative_integer("bid_size", self.bid_size)
        _validate_optional_nonnegative_integer("ask_size", self.ask_size)
        if not isinstance(self.market_phase, MarketPhase):
            raise TypeError("market_phase must be a MarketPhase")
        quote_scope, venue_mic = _normalize_quote_scope_and_venue(
            self.quote_scope, self.venue_mic
        )
        _validate_market_observation_metadata(self.metadata)
        _validate_locked_quote(bid, ask, self.metadata)

        object.__setattr__(self, "bid_price", bid)
        object.__setattr__(self, "ask_price", ask)
        object.__setattr__(self, "last_price", last)
        object.__setattr__(self, "quote_scope", quote_scope)
        object.__setattr__(self, "venue_mic", venue_mic)


@dataclass(frozen=True)
class OptionContractReference:
    """One normalized set of reference terms for an option contract."""

    contract_key: OptionContractKey
    listing_date: Optional[datetime.date]
    last_trade_date: Optional[datetime.date]
    exercise_style: Optional[str]
    settlement_type: Optional[str]
    metadata: NormalizationMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.contract_key, OptionContractKey):
            raise TypeError("contract_key must be an OptionContractKey")
        _validate_optional_date_only("listing_date", self.listing_date)
        _validate_optional_date_only("last_trade_date", self.last_trade_date)
        exercise_style = _normalize_optional_string(
            "exercise_style", self.exercise_style
        )
        settlement_type = _normalize_optional_string(
            "settlement_type", self.settlement_type
        )
        _validate_contract_reference_metadata(self.metadata)

        if (
            self.listing_date is not None
            and self.listing_date > self.contract_key.expiration
        ):
            raise ValueError("listing_date must not follow contract expiration")
        if (
            self.last_trade_date is not None
            and self.last_trade_date > self.contract_key.expiration
        ):
            raise ValueError("last_trade_date must not follow contract expiration")
        if (
            self.listing_date is not None
            and self.last_trade_date is not None
            and self.listing_date > self.last_trade_date
        ):
            raise ValueError("listing_date must not follow last_trade_date")

        object.__setattr__(self, "exercise_style", exercise_style)
        object.__setattr__(self, "settlement_type", settlement_type)


@dataclass(frozen=True)
class OptionQuoteObservation:
    """One normalized option quote in canonical per-underlying-unit premiums."""

    contract_key: OptionContractKey
    session_date: datetime.date
    bid_premium: decimal.Decimal
    ask_premium: decimal.Decimal
    bid_size: Optional[int]
    ask_size: Optional[int]
    market_phase: MarketPhase
    quote_scope: QuoteScope
    venue_mic: Optional[str]
    metadata: NormalizationMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.contract_key, OptionContractKey):
            raise TypeError("contract_key must be an OptionContractKey")
        _validate_date_only("session_date", self.session_date)
        bid = _normalize_nonnegative_decimal("bid_premium", self.bid_premium)
        ask = _normalize_positive_decimal("ask_premium", self.ask_premium)
        _validate_optional_nonnegative_integer("bid_size", self.bid_size)
        _validate_optional_nonnegative_integer("ask_size", self.ask_size)
        if not isinstance(self.market_phase, MarketPhase):
            raise TypeError("market_phase must be a MarketPhase")
        quote_scope, venue_mic = _normalize_quote_scope_and_venue(
            self.quote_scope, self.venue_mic
        )
        _validate_market_observation_metadata(self.metadata)
        _validate_locked_quote(bid, ask, self.metadata)

        object.__setattr__(self, "bid_premium", bid)
        object.__setattr__(self, "ask_premium", ask)
        object.__setattr__(self, "quote_scope", quote_scope)
        object.__setattr__(self, "venue_mic", venue_mic)


@dataclass(frozen=True)
class OptionVolumeObservation:
    """One normalized cumulative option-volume observation."""

    contract_key: OptionContractKey
    session_date: datetime.date
    cumulative_volume: int
    is_session_complete: bool
    metadata: NormalizationMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.contract_key, OptionContractKey):
            raise TypeError("contract_key must be an OptionContractKey")
        _validate_date_only("session_date", self.session_date)
        _validate_integer("cumulative_volume", self.cumulative_volume, 0)
        _validate_boolean("is_session_complete", self.is_session_complete)
        _validate_market_observation_metadata(self.metadata)


@dataclass(frozen=True)
class OptionOpenInterestObservation:
    """One normalized option open-interest observation."""

    contract_key: OptionContractKey
    open_interest_session_date: datetime.date
    open_interest: int
    metadata: NormalizationMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.contract_key, OptionContractKey):
            raise TypeError("contract_key must be an OptionContractKey")
        _validate_date_only(
            "open_interest_session_date", self.open_interest_session_date
        )
        _validate_integer("open_interest", self.open_interest, 0)
        _validate_market_observation_metadata(self.metadata)


@dataclass(frozen=True)
class OptionImpliedVolatilityObservation:
    """One supplied normalized option implied-volatility observation."""

    contract_key: OptionContractKey
    session_date: datetime.date
    implied_volatility: decimal.Decimal
    model_name: str
    model_version: Optional[str]
    rate_input_description: str
    dividend_input_description: str
    metadata: NormalizationMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.contract_key, OptionContractKey):
            raise TypeError("contract_key must be an OptionContractKey")
        _validate_date_only("session_date", self.session_date)
        implied_volatility = _normalize_positive_decimal(
            "implied_volatility", self.implied_volatility
        )
        model_name = _normalize_required_string("model_name", self.model_name)
        model_version = _normalize_optional_string(
            "model_version", self.model_version
        )
        rate_description = _normalize_required_string(
            "rate_input_description", self.rate_input_description
        )
        dividend_description = _normalize_required_string(
            "dividend_input_description", self.dividend_input_description
        )
        _validate_analytics_metadata(self.metadata)

        object.__setattr__(self, "implied_volatility", implied_volatility)
        object.__setattr__(self, "model_name", model_name)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "rate_input_description", rate_description)
        object.__setattr__(self, "dividend_input_description", dividend_description)


@dataclass(frozen=True)
class OptionGreeksObservation:
    """One supplied normalized set of option Greeks."""

    contract_key: OptionContractKey
    session_date: datetime.date
    delta: Optional[decimal.Decimal]
    gamma: Optional[decimal.Decimal]
    theta: Optional[decimal.Decimal]
    vega: Optional[decimal.Decimal]
    theta_day_basis: Optional[str]
    model_name: str
    model_version: Optional[str]
    rate_input_description: str
    dividend_input_description: str
    metadata: NormalizationMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.contract_key, OptionContractKey):
            raise TypeError("contract_key must be an OptionContractKey")
        _validate_date_only("session_date", self.session_date)

        greek_values = {}
        for name in ("delta", "gamma", "theta", "vega"):
            value = getattr(self, name)
            greek_values[name] = (
                None if value is None else _normalize_finite_decimal(name, value)
            )
        if all(value is None for value in greek_values.values()):
            raise ValueError("at least one Greek must be supplied")

        if greek_values["theta"] is None:
            if self.theta_day_basis is not None:
                raise ValueError("theta_day_basis must be None when theta is absent")
            theta_day_basis = None
        else:
            if self.theta_day_basis is None:
                raise ValueError("theta_day_basis is required when theta is supplied")
            theta_day_basis = _normalize_required_string(
                "theta_day_basis", self.theta_day_basis
            )

        model_name = _normalize_required_string("model_name", self.model_name)
        model_version = _normalize_optional_string(
            "model_version", self.model_version
        )
        rate_description = _normalize_required_string(
            "rate_input_description", self.rate_input_description
        )
        dividend_description = _normalize_required_string(
            "dividend_input_description", self.dividend_input_description
        )
        _validate_analytics_metadata(self.metadata)

        for name, value in greek_values.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "theta_day_basis", theta_day_basis)
        object.__setattr__(self, "model_name", model_name)
        object.__setattr__(self, "model_version", model_version)
        object.__setattr__(self, "rate_input_description", rate_description)
        object.__setattr__(self, "dividend_input_description", dividend_description)


@dataclass(frozen=True)
class UnderlyingDailyBarObservation:
    """One supplied normalized underlying daily bar."""

    underlying_key: UnderlyingKey
    session_date: datetime.date
    open_price: decimal.Decimal
    high_price: decimal.Decimal
    low_price: decimal.Decimal
    close_price: decimal.Decimal
    adjusted_close_price: Optional[decimal.Decimal]
    volume: int
    is_session_complete: bool
    adjustment_methodology: Optional[str]
    metadata: NormalizationMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.underlying_key, UnderlyingKey):
            raise TypeError("underlying_key must be an UnderlyingKey")
        _validate_date_only("session_date", self.session_date)
        prices = {
            name: _normalize_positive_decimal(name, getattr(self, name))
            for name in ("open_price", "high_price", "low_price", "close_price")
        }
        if prices["low_price"] > min(prices["open_price"], prices["close_price"]):
            raise ValueError("low_price must not exceed open_price or close_price")
        if prices["high_price"] < max(
            prices["open_price"], prices["close_price"]
        ):
            raise ValueError("high_price must not be below open_price or close_price")
        if prices["high_price"] < prices["low_price"]:
            raise ValueError("high_price must not be below low_price")

        if self.adjusted_close_price is None:
            adjusted_close = None
            if self.adjustment_methodology is not None:
                raise ValueError(
                    "adjustment_methodology must be None without adjusted close"
                )
            methodology = None
        else:
            adjusted_close = _normalize_positive_decimal(
                "adjusted_close_price", self.adjusted_close_price
            )
            if self.adjustment_methodology is None:
                raise ValueError(
                    "adjustment_methodology is required with adjusted close"
                )
            methodology = _normalize_required_string(
                "adjustment_methodology", self.adjustment_methodology
            )

        _validate_integer("volume", self.volume, 0)
        _validate_boolean("is_session_complete", self.is_session_complete)
        _validate_market_observation_metadata(self.metadata)

        for name, value in prices.items():
            object.__setattr__(self, name, value)
        object.__setattr__(self, "adjusted_close_price", adjusted_close)
        object.__setattr__(self, "adjustment_methodology", methodology)


@dataclass(frozen=True)
class RateCurvePointObservation:
    """One supplied normalized annualized rate-curve point."""

    curve_id: str
    currency: str
    tenor_days: int
    annualized_rate: decimal.Decimal
    compounding_convention: str
    day_count_convention: str
    effective_date: datetime.date
    metadata: NormalizationMetadata

    def __post_init__(self) -> None:
        curve_id = _normalize_required_string("curve_id", self.curve_id)
        currency = _normalize_required_string("currency", self.currency).upper()
        if currency != "USD":
            raise ValueError("currency must be USD for MVP v0.1")
        _validate_integer("tenor_days", self.tenor_days, 1)
        rate = _normalize_finite_decimal("annualized_rate", self.annualized_rate)
        compounding = _normalize_required_string(
            "compounding_convention", self.compounding_convention
        )
        day_count = _normalize_required_string(
            "day_count_convention", self.day_count_convention
        )
        _validate_date_only("effective_date", self.effective_date)
        _validate_rate_metadata(self.metadata)

        object.__setattr__(self, "curve_id", curve_id)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "annualized_rate", rate)
        object.__setattr__(self, "compounding_convention", compounding)
        object.__setattr__(self, "day_count_convention", day_count)


@dataclass(frozen=True)
class DividendObservation:
    """One supplied normalized dividend observation."""

    underlying_key: UnderlyingKey
    dividend_type: str
    ex_date: datetime.date
    payment_date: Optional[datetime.date]
    cash_amount: Optional[decimal.Decimal]
    annualized_yield: Optional[decimal.Decimal]
    currency: str
    status: DividendStatus
    metadata: NormalizationMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.underlying_key, UnderlyingKey):
            raise TypeError("underlying_key must be an UnderlyingKey")
        dividend_type = _normalize_required_string(
            "dividend_type", self.dividend_type
        )
        _validate_date_only("ex_date", self.ex_date)
        _validate_optional_date_only("payment_date", self.payment_date)
        cash_amount = (
            None if self.cash_amount is None else _normalize_nonnegative_decimal(
                "cash_amount", self.cash_amount
            )
        )
        annualized_yield = (
            None if self.annualized_yield is None else _normalize_nonnegative_decimal(
                "annualized_yield", self.annualized_yield
            )
        )
        if cash_amount is None and annualized_yield is None:
            raise ValueError("cash_amount or annualized_yield must be supplied")
        currency = _normalize_required_string("currency", self.currency).upper()
        if currency != self.underlying_key.currency:
            raise ValueError("currency must equal underlying_key.currency")
        if not isinstance(self.status, DividendStatus):
            raise TypeError("status must be a DividendStatus")
        _validate_dividend_metadata(self.metadata, self.status)

        object.__setattr__(self, "dividend_type", dividend_type)
        object.__setattr__(self, "cash_amount", cash_amount)
        object.__setattr__(self, "annualized_yield", annualized_yield)
        object.__setattr__(self, "currency", currency)
