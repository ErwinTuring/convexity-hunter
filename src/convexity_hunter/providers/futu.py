"""Bounded Futu OpenAPI runtime and provider evidence."""

import datetime as _datetime
import decimal as _decimal
import hashlib as _hashlib
import importlib as _importlib
import logging as _logging
import math as _math
import numbers as _numbers
import re as _re
import threading as _threading
from dataclasses import dataclass as _dataclass
from enum import Enum as _Enum
from typing import Optional as _Optional
from typing import Tuple as _Tuple
from zoneinfo import ZoneInfo as _ZoneInfo

from convexity_hunter.evidence import OptionLeg as _OptionLeg
from convexity_hunter.evidence import OptionStructure as _OptionStructure
from convexity_hunter.option_chain_discovery import (
    OptionChainDiscoveryRequest as _OptionChainDiscoveryRequest,
)
from convexity_hunter.market_data import (
    DataOrigin as _DataOrigin,
    NormalizationMetadata as _NormalizationMetadata,
    NormalizationQualityFlag as _NormalizationQualityFlag,
    OptionContractKey as _OptionContractKey,
    OptionContractReference as _OptionContractReference,
    SourceReference as _SourceReference,
    UnderlyingDailyBarObservation as _UnderlyingDailyBarObservation,
    UnderlyingKey as _UnderlyingKey,
)


__all__ = (
    "initialize_futu_quote_context",
    "FutuExactOptionContractVerification",
    "verify_futu_monthly_option_contract",
    "FutuOptionChainRowStatus",
    "FutuOptionChainExpirationEvidence",
    "FutuOptionChainContractEvidence",
    "FutuOptionChainDiscoveryEvidence",
    "retrieve_futu_option_chain_discovery_evidence",
    "FutuExactContractBrowser",
    "FutuExactContractSelection",
    "create_futu_exact_contract_browser",
    "select_futu_exact_contracts",
    "FutuBboEvidence",
    "FutuDirectEntryBboEvidence",
    "retrieve_futu_direct_entry_bbo_evidence",
    "retrieve_futu_underlying_daily_bars",
    "FutuHistoricalOptionBarEvidence",
    "retrieve_futu_historical_option_bar_evidence",
    "FutuExactOptionAnalyticsActivityEvidence",
    "retrieve_futu_exact_option_analytics_activity_evidence",
)


_US_EASTERN = _ZoneInfo("America/New_York")
_UTC = _datetime.timezone.utc
_NORMALIZATION_VERSION = "futu-option-contract-v0.1"
_DAILY_BAR_NORMALIZATION_VERSION = "futu-underlying-daily-bar-v0.1"
_SDK_UNAVAILABLE_MESSAGE = (
    "Futu OpenAPI SDK is unavailable. Install convexity-hunter[futu]."
)
_SDK_INITIALIZATION_MESSAGE = "Futu OpenD quote-context initialization failed."
_EXPIRATION_RETRIEVAL_MESSAGE = "Futu option-expiration retrieval failed."
_CHAIN_RETRIEVAL_MESSAGE = "Futu option-chain retrieval failed."
_SNAPSHOT_RETRIEVAL_MESSAGE = "Futu market-snapshot retrieval failed."
_EXPIRATION_RESPONSE_MESSAGE = "Futu option-expiration response is invalid."
_CHAIN_RESPONSE_MESSAGE = "Futu option-chain response is invalid."
_SNAPSHOT_RESPONSE_MESSAGE = "Futu market-snapshot response is invalid."
_EXACT_EXPIRATION_MESSAGE = (
    "Futu option-expiration response must contain exactly one exact match."
)
_MONTHLY_MESSAGE = "Futu does not classify the exact expiration as monthly."
_EXACT_CHAIN_MESSAGE = (
    "Futu option-chain response must contain exactly one exact contract match."
)
_STANDARD_MESSAGE = "Futu does not classify the exact contract as standard."
_IDENTIFIER_MESSAGE = "Futu option identifier is inconsistent."
_BBO_RETRIEVAL_MESSAGE = "Futu direct-entry BBO retrieval failed."
_BBO_RESPONSE_MESSAGE = "Futu direct-entry BBO response is invalid."
_BAR_RETRIEVAL_MESSAGE = "Futu underlying daily-bar retrieval failed."
_BAR_RESPONSE_MESSAGE = "Futu underlying daily-bar response is invalid."
_OPTION_BAR_RETRIEVAL_MESSAGE = "Futu historical option-bar retrieval failed."
_OPTION_BAR_RESPONSE_MESSAGE = "Futu historical option-bar response is invalid."
_ANALYTICS_RETRIEVAL_MESSAGE = (
    "Futu exact-option analytics/activity retrieval failed."
)
_ANALYTICS_RESPONSE_MESSAGE = (
    "Futu exact-option analytics/activity response is invalid."
)
_DISCOVERY_EXPIRATION_RETRIEVAL_MESSAGE = (
    "Futu option-chain discovery expiration retrieval failed."
)
_DISCOVERY_EXPIRATION_RESPONSE_MESSAGE = (
    "Futu option-chain discovery expiration response is invalid."
)
_DISCOVERY_CHAIN_RETRIEVAL_MESSAGE = (
    "Futu option-chain discovery chain retrieval failed."
)
_DISCOVERY_CHAIN_RESPONSE_MESSAGE = (
    "Futu option-chain discovery chain response is invalid."
)
_OPTION_IDENTIFIER_PATTERN = _re.compile(
    r"^US\.(?P<root>.+)(?P<expiration>\d{6})(?P<type>[CP])"
    r"(?P<strike>\d+)$"
)


def _load_futu_sdk() -> object:
    try:
        sdk = _importlib.import_module("futu")
        logger_module = _importlib.import_module("futu.common.ft_logger")
        logger = logger_module.logger
        logger.file_level = _logging.CRITICAL
        logger.console_level = _logging.CRITICAL
        logger.enable_console_log(False)
        required = (
            "OpenQuoteContext",
            "OrderBookHandlerBase",
            "RET_OK",
            "SubType",
            "KLType",
            "AuType",
        )
        if any(not hasattr(sdk, name) for name in required):
            raise AttributeError
        return sdk
    except Exception:
        raise RuntimeError(_SDK_UNAVAILABLE_MESSAGE) from None


def initialize_futu_quote_context(
    *, host: str = "127.0.0.1", port: int = 11111
) -> object:
    """Connect to an already-authenticated Futu OpenD quote service."""

    if type(host) is not str or not host or "\x00" in host:
        raise ValueError("host must be a nonempty string")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be an integer from 1 through 65535")
    sdk = _load_futu_sdk()
    try:
        return sdk.OpenQuoteContext(host=host, port=port)
    except Exception:
        raise RuntimeError(_SDK_INITIALIZATION_MESSAGE) from None


def _utc_now() -> _datetime.datetime:
    return _datetime.datetime.now(_UTC)


def _normalize_utc_timestamp(name: str, value: object) -> _datetime.datetime:
    if type(value) is not _datetime.datetime or value.tzinfo is None:
        raise TypeError(f"{name} must be a timezone-aware datetime")
    normalized = value.astimezone(_UTC)
    if normalized.utcoffset() != _datetime.timedelta(0):
        raise ValueError(f"{name} must normalize to UTC")
    return normalized


def _validate_date(name: str, value: object) -> _datetime.date:
    if type(value) is not _datetime.date:
        raise TypeError(f"{name} must be a date without a time component")
    return value


def _canonical_option_type(value: object) -> str:
    if type(value) is not str:
        raise TypeError("option_type must be a string")
    normalized = value.lower()
    if normalized not in {"call", "put"}:
        raise ValueError("option_type must be call or put")
    return normalized


def _provider_decimal(value: object, message: str) -> _decimal.Decimal:
    if isinstance(value, bool):
        raise ValueError(message)
    try:
        normalized = _decimal.Decimal(str(value))
    except Exception:
        raise ValueError(message) from None
    if not normalized.is_finite():
        raise ValueError(message)
    return normalized


def _positive_decimal(value: object, message: str) -> _decimal.Decimal:
    normalized = _provider_decimal(value, message)
    if normalized <= 0:
        raise ValueError(message)
    return normalized


def _nonnegative_decimal(value: object, message: str) -> _decimal.Decimal:
    normalized = _provider_decimal(value, message)
    if normalized < 0:
        raise ValueError(message)
    return normalized


def _provider_integer(value: object, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, _numbers.Real):
        raise ValueError(message)
    try:
        normalized = int(value)
    except Exception:
        raise ValueError(message) from None
    if not _math.isfinite(float(value)) or normalized != value:
        raise ValueError(message)
    return normalized


def _records(table: object, *, columns: frozenset, message: str) -> tuple:
    try:
        accessor = getattr(table, "to_dict", None)
    except Exception:
        raise ValueError(message) from None
    if not callable(accessor):
        raise ValueError(message)
    try:
        rows = accessor(orient="records")
    except Exception:
        raise ValueError(message) from None
    if type(rows) is not list:
        raise ValueError(message)
    normalized = []
    for row in rows:
        if type(row) is not dict or not columns.issubset(row):
            raise ValueError(message)
        normalized.append(row)
    return tuple(normalized)


def _decode_identifier(
    value: object,
) -> _Tuple[str, _datetime.date, str, _decimal.Decimal]:
    if type(value) is not str:
        raise ValueError(_IDENTIFIER_MESSAGE)
    match = _OPTION_IDENTIFIER_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(_IDENTIFIER_MESSAGE)
    try:
        expiration = _datetime.datetime.strptime(
            match.group("expiration"), "%y%m%d"
        ).date()
        strike = _decimal.Decimal(int(match.group("strike"))) / 1000
    except Exception:
        raise ValueError(_IDENTIFIER_MESSAGE) from None
    option_type = "call" if match.group("type") == "C" else "put"
    return match.group("root"), expiration, option_type, strike


def _parse_eastern_timestamp(
    value: object, message: str
) -> _datetime.datetime:
    if type(value) is not str:
        raise ValueError(message)
    parsed = None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = _datetime.datetime.strptime(value, fmt)
            break
        except ValueError:
            pass
    if parsed is None:
        raise ValueError(message)
    return parsed.replace(tzinfo=_US_EASTERN).astimezone(_UTC)


def _normalization_ids(
    provider_identifier: str,
    expiration_retrieved_at: _datetime.datetime,
    chain_retrieved_at: _datetime.datetime,
    snapshot_retrieved_at: _datetime.datetime,
) -> _Tuple[str, str, str, str]:
    material = "\x00".join(
        (
            _NORMALIZATION_VERSION,
            provider_identifier,
            expiration_retrieved_at.isoformat(),
            chain_retrieved_at.isoformat(),
            snapshot_retrieved_at.isoformat(),
        )
    ).encode("utf-8")
    digest = _hashlib.sha256(material).hexdigest()
    return (
        "futu-option-expirations:" + digest,
        "futu-option-chain:" + digest,
        "futu-option-snapshot:" + digest,
        "futu-option-contract:" + digest,
    )


def _build_contract_reference(
    *,
    underlying_key: _UnderlyingKey,
    expiration: _datetime.date,
    option_type: str,
    strike: _decimal.Decimal,
    multiplier: int,
    provider_identifier: str,
    exercise_style: str,
    expiration_retrieved_at: _datetime.datetime,
    chain_retrieved_at: _datetime.datetime,
    snapshot_retrieved_at: _datetime.datetime,
    normalized_at: _datetime.datetime,
) -> _OptionContractReference:
    expiration_id, chain_id, snapshot_id, record_id = _normalization_ids(
        provider_identifier,
        expiration_retrieved_at,
        chain_retrieved_at,
        snapshot_retrieved_at,
    )

    def source(
        source_id: str,
        dataset_name: str,
        provider_record_id: str,
        source_symbol: str,
        retrieved_at: _datetime.datetime,
    ) -> _SourceReference:
        return _SourceReference(
            source_id=source_id,
            provider_name="Futu OpenAPI",
            dataset_name=dataset_name,
            provider_record_id=provider_record_id,
            provider_request_id=None,
            source_symbol=source_symbol,
            source_uri=None,
            observed_at=retrieved_at,
            retrieved_at=retrieved_at,
            provider_timezone=None,
            timestamp_methodology=(
                "Futu supplied no observation timestamp for reference terms; "
                "adapter receipt time is assigned."
            ),
            origin=_DataOrigin.PROVIDER_REFERENCE,
            is_delayed=False,
            declared_delay_seconds=None,
            payload_sha256=None,
            revision_number=None,
            provider_correction_id=None,
            quality_flags=(),
        )

    sources = (
        source(
            expiration_id,
            "option_expiration_dates",
            underlying_key.symbol + ":" + expiration.isoformat(),
            "US." + underlying_key.symbol,
            expiration_retrieved_at,
        ),
        source(
            chain_id,
            "option_chain",
            provider_identifier,
            provider_identifier,
            chain_retrieved_at,
        ),
        source(
            snapshot_id,
            "market_snapshot",
            provider_identifier,
            provider_identifier,
            snapshot_retrieved_at,
        ),
    )
    metadata = _NormalizationMetadata(
        record_id=record_id,
        source_references=sources,
        effective_observed_at=snapshot_retrieved_at,
        normalized_at=normalized_at,
        record_origin=_DataOrigin.PROVIDER_REFERENCE,
        normalization_methodology=(
            "Futu exact expiration, chain, and snapshot fields were matched "
            "without substitution. STANDARD is retained provider-natively; "
            "exact OCC deliverable contents and settlement remain incomplete."
        ),
        unit_convention=(
            "USD per underlying unit strike; provider-supplied contract size."
        ),
        normalization_version=_NORMALIZATION_VERSION,
        quality_flags=(
            _NormalizationQualityFlag.SYMBOL_MAPPED,
            _NormalizationQualityFlag.TIMESTAMP_ASSIGNED,
            _NormalizationQualityFlag.INCOMPLETE,
        ),
    )
    return _OptionContractReference(
        contract_key=_OptionContractKey(
            underlying_key=underlying_key,
            expiration=expiration,
            option_type=option_type,
            strike=strike,
            contract_multiplier=multiplier,
            currency=underlying_key.currency,
            deliverable_id=None,
        ),
        listing_date=None,
        last_trade_date=None,
        exercise_style=exercise_style,
        settlement_type=None,
        metadata=metadata,
    )


@_dataclass(frozen=True)
class FutuExactOptionContractVerification:
    """Exact Futu monthly and provider-standard contract evidence."""

    provider_identifier: str
    provider_expiration_cycle: str
    provider_standard_type: str
    provider_exercise_type: str
    contract_reference: _OptionContractReference

    def __post_init__(self) -> None:
        if type(self.provider_identifier) is not str:
            raise TypeError("provider_identifier must be a string")
        if self.provider_expiration_cycle != "MONTH":
            raise ValueError(_MONTHLY_MESSAGE)
        if self.provider_standard_type != "STANDARD":
            raise ValueError(_STANDARD_MESSAGE)
        if type(self.provider_exercise_type) is not str or not self.provider_exercise_type:
            raise ValueError(_SNAPSHOT_RESPONSE_MESSAGE)
        if type(self.contract_reference) is not _OptionContractReference:
            raise TypeError(
                "contract_reference must be an OptionContractReference"
            )
        root, expiration, option_type, strike = _decode_identifier(
            self.provider_identifier
        )
        key = self.contract_reference.contract_key
        if (
            root != key.underlying_key.symbol
            or expiration != key.expiration
            or option_type != key.option_type
            or strike != key.strike
            or self.contract_reference.exercise_style
            != self.provider_exercise_type
            or self.contract_reference.settlement_type is not None
            or key.deliverable_id is not None
            or _NormalizationQualityFlag.INCOMPLETE
            not in self.contract_reference.metadata.quality_flags
        ):
            raise ValueError(_IDENTIFIER_MESSAGE)


def verify_futu_monthly_option_contract(
    quote_context: object,
    *,
    underlying_key: _UnderlyingKey,
    expiration: _datetime.date,
    option_type: str,
    strike: _decimal.Decimal,
) -> FutuExactOptionContractVerification:
    """Verify one caller-specified exact Futu monthly standard option."""

    if type(underlying_key) is not _UnderlyingKey:
        raise TypeError("underlying_key must be an UnderlyingKey")
    expiration = _validate_date("expiration", expiration)
    option_type = _canonical_option_type(option_type)
    if type(strike) is not _decimal.Decimal:
        raise TypeError("strike must be a Decimal")
    strike = _positive_decimal(strike, _CHAIN_RESPONSE_MESSAGE)
    try:
        get_expirations = getattr(
            quote_context, "get_option_expiration_date", None
        )
        get_chain = getattr(quote_context, "get_option_chain", None)
        get_snapshot = getattr(quote_context, "get_market_snapshot", None)
    except Exception:
        raise TypeError("quote_context must provide Futu quote methods") from None
    if not all(
        callable(method) for method in (get_expirations, get_chain, get_snapshot)
    ):
        raise TypeError("quote_context must provide Futu quote methods")

    provider_underlying = "US." + underlying_key.symbol
    try:
        ret, table = get_expirations(provider_underlying)
    except Exception:
        raise RuntimeError(_EXPIRATION_RETRIEVAL_MESSAGE) from None
    expiration_retrieved_at = _utc_now()
    if ret != 0:
        raise RuntimeError(_EXPIRATION_RETRIEVAL_MESSAGE)
    expiration_rows = _records(
        table,
        columns=frozenset(("strike_time", "expiration_cycle")),
        message=_EXPIRATION_RESPONSE_MESSAGE,
    )
    exact_expirations = tuple(
        row
        for row in expiration_rows
        if type(row["strike_time"]) is str
        and row["strike_time"] == expiration.isoformat()
    )
    if len(exact_expirations) != 1:
        raise ValueError(_EXACT_EXPIRATION_MESSAGE)
    if exact_expirations[0]["expiration_cycle"] != "MONTH":
        raise ValueError(_MONTHLY_MESSAGE)

    try:
        ret, table = get_chain(
            provider_underlying,
            start=expiration.isoformat(),
            end=expiration.isoformat(),
            option_type=option_type.upper(),
        )
    except Exception:
        raise RuntimeError(_CHAIN_RETRIEVAL_MESSAGE) from None
    chain_retrieved_at = _utc_now()
    if ret != 0:
        raise RuntimeError(_CHAIN_RETRIEVAL_MESSAGE)
    chain_columns = frozenset(
        (
            "code",
            "lot_size",
            "option_type",
            "stock_owner",
            "strike_time",
            "strike_price",
            "suspension",
            "expiration_cycle",
            "option_standard_type",
        )
    )
    chain_rows = _records(
        table, columns=chain_columns, message=_CHAIN_RESPONSE_MESSAGE
    )
    normalized_rows = []
    for row in chain_rows:
        if (
            type(row["code"]) is not str
            or type(row["stock_owner"]) is not str
            or type(row["strike_time"]) is not str
            or type(row["option_type"]) is not str
        ):
            raise ValueError(_CHAIN_RESPONSE_MESSAGE)
        row_strike = _provider_decimal(
            row["strike_price"], _CHAIN_RESPONSE_MESSAGE
        )
        normalized_rows.append((row, row_strike))
    exact_rows = tuple(
        row
        for row, row_strike in normalized_rows
        if row["stock_owner"] == provider_underlying
        and row["strike_time"] == expiration.isoformat()
        and row["option_type"] == option_type.upper()
        and row_strike == strike
    )
    if len(exact_rows) != 1:
        raise ValueError(_EXACT_CHAIN_MESSAGE)
    row = exact_rows[0]
    if row["expiration_cycle"] != "MONTH":
        raise ValueError(_MONTHLY_MESSAGE)
    if row["option_standard_type"] != "STANDARD":
        raise ValueError(_STANDARD_MESSAGE)
    if type(row["suspension"]) is not bool or row["suspension"]:
        raise ValueError(_CHAIN_RESPONSE_MESSAGE)
    multiplier = _provider_integer(row["lot_size"], _CHAIN_RESPONSE_MESSAGE)
    if multiplier <= 0:
        raise ValueError(_CHAIN_RESPONSE_MESSAGE)
    provider_identifier = row["code"]
    root, decoded_expiration, decoded_type, decoded_strike = _decode_identifier(
        provider_identifier
    )
    if (
        root != underlying_key.symbol
        or decoded_expiration != expiration
        or decoded_type != option_type
        or decoded_strike != strike
    ):
        raise ValueError(_IDENTIFIER_MESSAGE)

    try:
        ret, table = get_snapshot([provider_identifier])
    except Exception:
        raise RuntimeError(_SNAPSHOT_RETRIEVAL_MESSAGE) from None
    snapshot_retrieved_at = _utc_now()
    if ret != 0:
        raise RuntimeError(_SNAPSHOT_RETRIEVAL_MESSAGE)
    snapshot_columns = frozenset(
        (
            "code",
            "stock_owner",
            "option_type",
            "strike_time",
            "option_strike_price",
            "option_contract_size",
            "option_area_type",
            "option_valid",
        )
    )
    snapshot_rows = _records(
        table, columns=snapshot_columns, message=_SNAPSHOT_RESPONSE_MESSAGE
    )
    exact_snapshots = tuple(
        item for item in snapshot_rows if item["code"] == provider_identifier
    )
    if len(exact_snapshots) != 1:
        raise ValueError(_SNAPSHOT_RESPONSE_MESSAGE)
    snapshot = exact_snapshots[0]
    exercise_type = snapshot["option_area_type"]
    if (
        snapshot["stock_owner"] != provider_underlying
        or snapshot["option_type"] != option_type.upper()
        or snapshot["strike_time"] != expiration.isoformat()
        or _provider_decimal(
            snapshot["option_strike_price"], _SNAPSHOT_RESPONSE_MESSAGE
        )
        != strike
        or _provider_integer(
            snapshot["option_contract_size"], _SNAPSHOT_RESPONSE_MESSAGE
        )
        != multiplier
        or type(snapshot["option_valid"]) is not bool
        or not snapshot["option_valid"]
        or type(exercise_type) is not str
        or not exercise_type
        or exercise_type == "N/A"
    ):
        raise ValueError(_SNAPSHOT_RESPONSE_MESSAGE)

    normalized_at = _utc_now()
    reference = _build_contract_reference(
        underlying_key=underlying_key,
        expiration=expiration,
        option_type=option_type,
        strike=strike,
        multiplier=multiplier,
        provider_identifier=provider_identifier,
        exercise_style=exercise_type,
        expiration_retrieved_at=expiration_retrieved_at,
        chain_retrieved_at=chain_retrieved_at,
        snapshot_retrieved_at=snapshot_retrieved_at,
        normalized_at=normalized_at,
    )
    return FutuExactOptionContractVerification(
        provider_identifier=provider_identifier,
        provider_expiration_cycle="MONTH",
        provider_standard_type="STANDARD",
        provider_exercise_type=exercise_type,
        contract_reference=reference,
    )


class FutuOptionChainRowStatus(str, _Enum):
    """Provider-classified applicability for one retained chain row."""

    ELIGIBLE = "eligible"
    NON_MONTHLY = "non_monthly"
    NON_STANDARD = "non_standard"
    SUSPENDED = "suspended"


def _discovery_statuses(
    provider_expiration_cycle: str,
    provider_standard_type: str,
    suspension: bool,
) -> _Tuple[FutuOptionChainRowStatus, ...]:
    statuses = []
    if provider_expiration_cycle != "MONTH":
        statuses.append(FutuOptionChainRowStatus.NON_MONTHLY)
    if provider_standard_type != "STANDARD":
        statuses.append(FutuOptionChainRowStatus.NON_STANDARD)
    if suspension:
        statuses.append(FutuOptionChainRowStatus.SUSPENDED)
    if not statuses:
        statuses.append(FutuOptionChainRowStatus.ELIGIBLE)
    return tuple(statuses)


def _discovery_string(value: object, message: str) -> str:
    if type(value) is not str or not value:
        raise ValueError(message)
    return value


def _discovery_provider_underlying(request: _OptionChainDiscoveryRequest) -> str:
    return "US." + request.underlying_key.symbol


def _validate_discovery_request(value: object) -> _OptionChainDiscoveryRequest:
    if type(value) is not _OptionChainDiscoveryRequest:
        raise TypeError(
            "discovery_request must have exact type OptionChainDiscoveryRequest"
        )
    try:
        rebuilt = _OptionChainDiscoveryRequest(
            value.discovery_entry_handoff,
            value.evaluation_date,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("discovery_request is malformed") from error
    if rebuilt != value:
        raise ValueError("discovery_request is not intrinsically valid")
    return value


@_dataclass(frozen=True)
class FutuOptionChainExpirationEvidence:
    """One retained provider expiration classification and receipt time."""

    expiration: _datetime.date
    provider_expiration_cycle: str
    expiration_retrieved_at: _datetime.datetime
    chain_retrieved_at: _Optional[_datetime.datetime]

    def __post_init__(self) -> None:
        expiration = _validate_date("expiration", self.expiration)
        cycle = _discovery_string(
            self.provider_expiration_cycle,
            _DISCOVERY_EXPIRATION_RESPONSE_MESSAGE,
        )
        expiration_at = _checked_runtime_timestamp(
            "expiration_retrieved_at",
            self.expiration_retrieved_at,
            _DISCOVERY_EXPIRATION_RESPONSE_MESSAGE,
        )
        if self.chain_retrieved_at is None:
            if cycle == "MONTH":
                raise ValueError(_DISCOVERY_EXPIRATION_RESPONSE_MESSAGE)
            chain_at = None
        else:
            chain_at = _checked_runtime_timestamp(
                "chain_retrieved_at",
                self.chain_retrieved_at,
                _DISCOVERY_CHAIN_RESPONSE_MESSAGE,
            )
            if cycle != "MONTH" or chain_at < expiration_at:
                raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE)
        object.__setattr__(self, "expiration", expiration)
        object.__setattr__(self, "provider_expiration_cycle", cycle)
        object.__setattr__(self, "expiration_retrieved_at", expiration_at)
        object.__setattr__(self, "chain_retrieved_at", chain_at)


@_dataclass(frozen=True)
class FutuOptionChainContractEvidence:
    """One exact provider chain row, retained without contract selection."""

    provider_identifier: str
    provider_underlying: str
    expiration: _datetime.date
    option_type: str
    strike: _decimal.Decimal
    lot_size: int
    provider_expiration_cycle: str
    provider_standard_type: str
    suspension: bool
    statuses: _Tuple[FutuOptionChainRowStatus, ...]
    retrieved_at: _datetime.datetime

    def __post_init__(self) -> None:
        identifier = _discovery_string(
            self.provider_identifier, _DISCOVERY_CHAIN_RESPONSE_MESSAGE
        )
        provider_underlying = _discovery_string(
            self.provider_underlying, _DISCOVERY_CHAIN_RESPONSE_MESSAGE
        )
        if (
            not provider_underlying.startswith("US.")
            or len(provider_underlying) <= 3
        ):
            raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE)
        expiration = _validate_date("expiration", self.expiration)
        option_type = _canonical_option_type(self.option_type)
        if type(self.strike) is not _decimal.Decimal:
            raise TypeError("strike must be a Decimal")
        strike = _positive_decimal(self.strike, _DISCOVERY_CHAIN_RESPONSE_MESSAGE)
        if type(self.lot_size) is not int or isinstance(self.lot_size, bool):
            raise TypeError("lot_size must be an integer")
        if self.lot_size <= 0:
            raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE)
        cycle = _discovery_string(
            self.provider_expiration_cycle, _DISCOVERY_CHAIN_RESPONSE_MESSAGE
        )
        standard_type = _discovery_string(
            self.provider_standard_type, _DISCOVERY_CHAIN_RESPONSE_MESSAGE
        )
        if type(self.suspension) is not bool:
            raise TypeError("suspension must be a Boolean")
        expected_statuses = _discovery_statuses(
            cycle, standard_type, self.suspension
        )
        if (
            type(self.statuses) is not tuple
            or any(
                type(item) is not FutuOptionChainRowStatus
                for item in self.statuses
            )
            or self.statuses != expected_statuses
        ):
            raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE)
        retrieved_at = _checked_runtime_timestamp(
            "retrieved_at", self.retrieved_at, _DISCOVERY_CHAIN_RESPONSE_MESSAGE
        )
        root, decoded_expiration, decoded_type, decoded_strike = _decode_identifier(
            identifier
        )
        if (
            decoded_expiration != expiration
            or decoded_type != option_type
            or decoded_strike != strike
            or (standard_type == "STANDARD" and root != provider_underlying[3:])
        ):
            raise ValueError(_IDENTIFIER_MESSAGE)
        object.__setattr__(self, "provider_identifier", identifier)
        object.__setattr__(self, "provider_underlying", provider_underlying)
        object.__setattr__(self, "expiration", expiration)
        object.__setattr__(self, "option_type", option_type)
        object.__setattr__(self, "strike", strike)
        object.__setattr__(self, "provider_expiration_cycle", cycle)
        object.__setattr__(self, "provider_standard_type", standard_type)
        object.__setattr__(self, "retrieved_at", retrieved_at)


@_dataclass(frozen=True)
class FutuOptionChainDiscoveryEvidence:
    """All bounded Futu expiration and chain rows for one exact request."""

    discovery_request: _OptionChainDiscoveryRequest
    provider_underlying: str
    expirations: _Tuple[FutuOptionChainExpirationEvidence, ...]
    contracts: _Tuple[FutuOptionChainContractEvidence, ...]

    def __post_init__(self) -> None:
        request = _validate_discovery_request(self.discovery_request)
        expected_underlying = _discovery_provider_underlying(request)
        if (
            type(self.provider_underlying) is not str
            or self.provider_underlying != expected_underlying
        ):
            raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE)
        if type(self.expirations) is not tuple or any(
            type(item) is not FutuOptionChainExpirationEvidence
            for item in self.expirations
        ):
            raise TypeError(
                "expirations must be a tuple of FutuOptionChainExpirationEvidence"
            )
        if type(self.contracts) is not tuple or any(
            type(item) is not FutuOptionChainContractEvidence
            for item in self.contracts
        ):
            raise TypeError(
                "contracts must be a tuple of FutuOptionChainContractEvidence"
            )
        expiration_by_date = {}
        expiration_retrieved_at = None
        previous_chain_retrieved_at = None
        for item in self.expirations:
            try:
                rebuilt_expiration = FutuOptionChainExpirationEvidence(
                    item.expiration,
                    item.provider_expiration_cycle,
                    item.expiration_retrieved_at,
                    item.chain_retrieved_at,
                )
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError(_DISCOVERY_EXPIRATION_RESPONSE_MESSAGE) from error
            if (
                rebuilt_expiration != item
                or item.expiration in expiration_by_date
                or item.expiration < request.minimum_expiration_date
                or item.expiration > request.maximum_expiration_date
            ):
                raise ValueError(_DISCOVERY_EXPIRATION_RESPONSE_MESSAGE)
            if expiration_retrieved_at is None:
                expiration_retrieved_at = item.expiration_retrieved_at
            elif item.expiration_retrieved_at != expiration_retrieved_at:
                raise ValueError(_DISCOVERY_EXPIRATION_RESPONSE_MESSAGE)
            if item.chain_retrieved_at is not None:
                if (
                    previous_chain_retrieved_at is not None
                    and item.chain_retrieved_at < previous_chain_retrieved_at
                ):
                    raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE)
                previous_chain_retrieved_at = item.chain_retrieved_at
            expiration_by_date[item.expiration] = item
        if (
            tuple(sorted(self.expirations, key=lambda item: item.expiration))
            != self.expirations
        ):
            raise ValueError(_DISCOVERY_EXPIRATION_RESPONSE_MESSAGE)
        rebuilt_contracts = []
        for item in self.contracts:
            try:
                rebuilt_contract = FutuOptionChainContractEvidence(
                    item.provider_identifier,
                    item.provider_underlying,
                    item.expiration,
                    item.option_type,
                    item.strike,
                    item.lot_size,
                    item.provider_expiration_cycle,
                    item.provider_standard_type,
                    item.suspension,
                    item.statuses,
                    item.retrieved_at,
                )
            except (AttributeError, TypeError, ValueError) as error:
                raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE) from error
            if rebuilt_contract != item:
                raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE)
            rebuilt_contracts.append(rebuilt_contract)
        expected_contracts = tuple(
            sorted(
                rebuilt_contracts,
                key=lambda item: (
                    item.expiration,
                    item.strike,
                    0 if item.option_type == "call" else 1,
                    item.provider_identifier,
                ),
            )
        )
        if expected_contracts != self.contracts:
            raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE)
        seen_identifiers = set()
        for item in self.contracts:
            expiration_evidence = expiration_by_date.get(item.expiration)
            if (
                item.provider_identifier in seen_identifiers
                or item.provider_underlying != expected_underlying
                or expiration_evidence is None
                or expiration_evidence.provider_expiration_cycle != "MONTH"
                or item.retrieved_at != expiration_evidence.chain_retrieved_at
            ):
                raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE)
            seen_identifiers.add(item.provider_identifier)


def _discovery_expiration_row(row: dict) -> _Tuple[_datetime.date, str]:
    try:
        expiration = _datetime.datetime.strptime(
            row["strike_time"], "%Y-%m-%d"
        ).date()
    except Exception:
        raise ValueError(_DISCOVERY_EXPIRATION_RESPONSE_MESSAGE) from None
    cycle = _discovery_string(
        row["expiration_cycle"], _DISCOVERY_EXPIRATION_RESPONSE_MESSAGE
    )
    return expiration, cycle


def _discovery_contract_row(
    row: dict,
    *,
    provider_underlying: str,
    expected_expiration: _datetime.date,
    retrieved_at: _datetime.datetime,
) -> FutuOptionChainContractEvidence:
    message = _DISCOVERY_CHAIN_RESPONSE_MESSAGE
    try:
        identifier = _discovery_string(row["code"], message)
        owner = _discovery_string(row["stock_owner"], message)
        if owner != provider_underlying:
            raise ValueError(message)
        try:
            expiration = _datetime.datetime.strptime(
                row["strike_time"], "%Y-%m-%d"
            ).date()
        except Exception:
            raise ValueError(message) from None
        if expiration != expected_expiration:
            raise ValueError(message)
        option_type_value = _discovery_string(row["option_type"], message)
        if option_type_value not in {"CALL", "PUT"}:
            raise ValueError(message)
        option_type = option_type_value.lower()
        strike = _positive_decimal(row["strike_price"], message)
        lot_size = _provider_integer(row["lot_size"], message)
        if lot_size <= 0 or type(row["suspension"]) is not bool:
            raise ValueError(message)
        cycle = _discovery_string(row["expiration_cycle"], message)
        standard_type = _discovery_string(row["option_standard_type"], message)
        root, decoded_expiration, decoded_type, decoded_strike = _decode_identifier(
            identifier
        )
        if (
            decoded_expiration != expiration
            or decoded_type != option_type
            or decoded_strike != strike
            or (standard_type == "STANDARD" and root != provider_underlying[3:])
        ):
            raise ValueError(_IDENTIFIER_MESSAGE)
        return FutuOptionChainContractEvidence(
            provider_identifier=identifier,
            provider_underlying=provider_underlying,
            expiration=expiration,
            option_type=option_type,
            strike=strike,
            lot_size=lot_size,
            provider_expiration_cycle=cycle,
            provider_standard_type=standard_type,
            suspension=row["suspension"],
            statuses=_discovery_statuses(cycle, standard_type, row["suspension"]),
            retrieved_at=retrieved_at,
        )
    except (TypeError, ValueError):
        raise
    except Exception:
        raise ValueError(message) from None


def retrieve_futu_option_chain_discovery_evidence(
    quote_context: object,
    *,
    discovery_request: _OptionChainDiscoveryRequest,
) -> FutuOptionChainDiscoveryEvidence:
    """Retrieve bounded provider classifications without selecting a contract."""

    request = _validate_discovery_request(discovery_request)
    try:
        get_expirations = getattr(
            quote_context, "get_option_expiration_date", None
        )
        get_chain = getattr(quote_context, "get_option_chain", None)
    except Exception:
        raise TypeError("quote_context must provide Futu quote methods") from None
    if not callable(get_expirations) or not callable(get_chain):
        raise TypeError("quote_context must provide Futu quote methods")

    provider_underlying = _discovery_provider_underlying(request)
    try:
        ret, table = get_expirations(provider_underlying)
    except Exception:
        raise RuntimeError(_DISCOVERY_EXPIRATION_RETRIEVAL_MESSAGE) from None
    expiration_retrieved_at = _utc_now()
    if ret != 0:
        raise RuntimeError(_DISCOVERY_EXPIRATION_RETRIEVAL_MESSAGE)
    rows = _records(
        table,
        columns=frozenset(("strike_time", "expiration_cycle")),
        message=_DISCOVERY_EXPIRATION_RESPONSE_MESSAGE,
    )
    retained = []
    seen_expirations = set()
    for row in rows:
        expiration, cycle = _discovery_expiration_row(row)
        if not (
            request.minimum_expiration_date
            <= expiration
            <= request.maximum_expiration_date
        ):
            continue
        if expiration in seen_expirations:
            raise ValueError(_DISCOVERY_EXPIRATION_RESPONSE_MESSAGE)
        seen_expirations.add(expiration)
        retained.append((expiration, cycle))
    retained.sort(key=lambda item: item[0])

    expiration_evidence = []
    contracts = []
    seen_identifiers = set()
    chain_columns = frozenset(
        (
            "code",
            "lot_size",
            "option_type",
            "stock_owner",
            "strike_time",
            "strike_price",
            "suspension",
            "expiration_cycle",
            "option_standard_type",
        )
    )
    for expiration, cycle in retained:
        chain_retrieved_at = None
        if cycle == "MONTH":
            try:
                ret, table = get_chain(
                    provider_underlying,
                    start=expiration.isoformat(),
                    end=expiration.isoformat(),
                )
            except Exception:
                raise RuntimeError(_DISCOVERY_CHAIN_RETRIEVAL_MESSAGE) from None
            chain_retrieved_at = _utc_now()
            if ret != 0:
                raise RuntimeError(_DISCOVERY_CHAIN_RETRIEVAL_MESSAGE)
            chain_rows = _records(
                table,
                columns=chain_columns,
                message=_DISCOVERY_CHAIN_RESPONSE_MESSAGE,
            )
            for row in chain_rows:
                contract = _discovery_contract_row(
                    row,
                    provider_underlying=provider_underlying,
                    expected_expiration=expiration,
                    retrieved_at=chain_retrieved_at,
                )
                if contract.provider_identifier in seen_identifiers:
                    raise ValueError(_DISCOVERY_CHAIN_RESPONSE_MESSAGE)
                seen_identifiers.add(contract.provider_identifier)
                contracts.append(contract)
        expiration_evidence.append(
            FutuOptionChainExpirationEvidence(
                expiration=expiration,
                provider_expiration_cycle=cycle,
                expiration_retrieved_at=expiration_retrieved_at,
                chain_retrieved_at=chain_retrieved_at,
            )
        )
    contracts.sort(
        key=lambda item: (
            item.expiration,
            item.strike,
            0 if item.option_type == "call" else 1,
            item.provider_identifier,
        )
    )
    return FutuOptionChainDiscoveryEvidence(
        discovery_request=request,
        provider_underlying=provider_underlying,
        expirations=tuple(expiration_evidence),
        contracts=tuple(contracts),
    )


def _validate_browser_discovery_evidence(
    value: object,
) -> FutuOptionChainDiscoveryEvidence:
    if type(value) is not FutuOptionChainDiscoveryEvidence:
        raise TypeError(
            "discovery_evidence must have exact type "
            "FutuOptionChainDiscoveryEvidence"
        )
    try:
        rebuilt = FutuOptionChainDiscoveryEvidence(
            value.discovery_request,
            value.provider_underlying,
            value.expirations,
            value.contracts,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("discovery_evidence is malformed") from error
    if rebuilt != value:
        raise ValueError("discovery_evidence is not intrinsically valid")
    return value


def _browser_row_is_visible(row: FutuOptionChainContractEvidence) -> bool:
    return (
        row.provider_expiration_cycle == "MONTH"
        and row.provider_standard_type == "STANDARD"
        and not row.suspension
        and row.statuses == (FutuOptionChainRowStatus.ELIGIBLE,)
    )


@_dataclass(frozen=True)
class FutuExactContractBrowser:
    """Neutral navigation over browser-visible exact Futu chain rows."""

    discovery_evidence: FutuOptionChainDiscoveryEvidence

    def __post_init__(self) -> None:
        _validate_browser_discovery_evidence(self.discovery_evidence)

    @property
    def rows(self) -> _Tuple[FutuOptionChainContractEvidence, ...]:
        """Return all and only provider-classified browser-visible rows."""

        return tuple(
            row
            for row in self.discovery_evidence.contracts
            if _browser_row_is_visible(row)
        )


def _validate_exact_contract_browser(value: object) -> FutuExactContractBrowser:
    if type(value) is not FutuExactContractBrowser:
        raise TypeError("browser must have exact type FutuExactContractBrowser")
    try:
        rebuilt = FutuExactContractBrowser(value.discovery_evidence)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("browser is malformed") from error
    if rebuilt != value:
        raise ValueError("browser is not intrinsically valid")
    return value


def _browser_strike_as_float(strike: _decimal.Decimal) -> float:
    try:
        normalized = float(strike)
    except Exception:
        raise ValueError("selected strike cannot be represented exactly") from None
    if (
        not _math.isfinite(normalized)
        or _decimal.Decimal(str(normalized)) != strike
    ):
        raise ValueError("selected strike cannot be represented exactly")
    return normalized


def _browser_contract_order(
    row: FutuOptionChainContractEvidence,
) -> tuple:
    return (
        row.expiration,
        row.strike,
        0 if row.option_type == "call" else 1,
        row.provider_identifier,
    )


def _validate_selected_browser_rows(
    browser: FutuExactContractBrowser,
    selected_contracts: object,
) -> _Tuple[FutuOptionChainContractEvidence, ...]:
    if type(selected_contracts) is not tuple:
        raise TypeError("selected_contracts must have exact type tuple")
    if len(selected_contracts) not in {1, 2}:
        raise ValueError("selected_contracts must contain one or two rows")
    if any(
        type(row) is not FutuOptionChainContractEvidence
        for row in selected_contracts
    ):
        raise TypeError(
            "selected contracts must have exact type "
            "FutuOptionChainContractEvidence"
        )
    visible_rows = browser.rows
    if any(
        not any(row is visible for visible in visible_rows)
        for row in selected_contracts
    ):
        raise ValueError(
            "selected contracts must be retained by identity in browser.rows"
        )
    identifiers = tuple(row.provider_identifier for row in selected_contracts)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("selected contract identifiers must be unique")
    if tuple(sorted(selected_contracts, key=_browser_contract_order)) != (
        selected_contracts
    ):
        raise ValueError("selected_contracts must use neutral browser order")
    if len(selected_contracts) == 2:
        call, put = selected_contracts
        if (
            call.option_type != "call"
            or put.option_type != "put"
            or call.provider_underlying != put.provider_underlying
            or call.expiration != put.expiration
            or call.strike != put.strike
            or call.lot_size != put.lot_size
        ):
            raise ValueError(
                "two selected contracts must form one exact long straddle"
            )
    return selected_contracts


def _expected_selection_structure(
    browser: FutuExactContractBrowser,
    selected_contracts: _Tuple[FutuOptionChainContractEvidence, ...],
    structure: _OptionStructure,
) -> _OptionStructure:
    if type(structure) is not _OptionStructure:
        raise TypeError("structure must have exact type OptionStructure")
    try:
        rebuilt_structure = _OptionStructure(
            structure.legs,
            structure.assumed_portfolio_value,
            structure.expected_holding_days,
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("structure is malformed") from error
    if rebuilt_structure != structure or len(structure.legs) != len(
        selected_contracts
    ):
        raise ValueError("structure does not match selected contracts")
    symbol = browser.discovery_evidence.discovery_request.underlying_key.symbol
    expected_legs = []
    for row, leg in zip(selected_contracts, structure.legs):
        if type(leg) is not _OptionLeg:
            raise TypeError("structure legs must have exact type OptionLeg")
        try:
            expected_leg = _OptionLeg(
                symbol,
                row.option_type,
                _browser_strike_as_float(row.strike),
                row.expiration,
                leg.quantity,
                row.lot_size,
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("structure does not match selected contracts") from error
        if expected_leg != leg:
            raise ValueError("structure does not match selected contracts")
        expected_legs.append(expected_leg)
    expected = _OptionStructure(
        tuple(expected_legs),
        structure.assumed_portfolio_value,
        structure.expected_holding_days,
    )
    if expected != structure:
        raise ValueError("structure does not match selected contracts")
    return structure


@_dataclass(frozen=True)
class FutuExactContractSelection:
    """Explicit human research intent for one exact listed structure."""

    browser: FutuExactContractBrowser
    selected_contracts: _Tuple[FutuOptionChainContractEvidence, ...]
    structure: _OptionStructure

    def __post_init__(self) -> None:
        browser = _validate_exact_contract_browser(self.browser)
        rows = _validate_selected_browser_rows(browser, self.selected_contracts)
        _expected_selection_structure(browser, rows, self.structure)


def create_futu_exact_contract_browser(
    discovery_evidence: FutuOptionChainDiscoveryEvidence,
) -> FutuExactContractBrowser:
    """Create neutral navigation without choosing or qualifying a contract."""

    evidence = _validate_browser_discovery_evidence(discovery_evidence)
    return FutuExactContractBrowser(evidence)


def select_futu_exact_contracts(
    browser: FutuExactContractBrowser,
    *,
    provider_identifiers: _Tuple[str, ...],
    assumed_portfolio_value: float,
    expected_holding_days: int,
    quantity: int = 1,
) -> FutuExactContractSelection:
    """Retain an explicit human selection as unverified research intent."""

    browser = _validate_exact_contract_browser(browser)
    if type(provider_identifiers) is not tuple:
        raise TypeError("provider_identifiers must have exact type tuple")
    if len(provider_identifiers) not in {1, 2}:
        raise ValueError("provider_identifiers must contain one or two values")
    if any(type(value) is not str or not value for value in provider_identifiers):
        raise TypeError("provider identifiers must be nonempty strings")
    if len(set(provider_identifiers)) != len(provider_identifiers):
        raise ValueError("provider identifiers must be unique")
    row_by_identifier = {
        row.provider_identifier: row for row in browser.rows
    }
    if any(identifier not in row_by_identifier for identifier in provider_identifiers):
        raise ValueError("provider identifier is not visible in this browser")
    selected = tuple(
        sorted(
            (row_by_identifier[identifier] for identifier in provider_identifiers),
            key=_browser_contract_order,
        )
    )
    _validate_selected_browser_rows(browser, selected)
    legs = tuple(
        _OptionLeg(
            browser.discovery_evidence.discovery_request.underlying_key.symbol,
            row.option_type,
            _browser_strike_as_float(row.strike),
            row.expiration,
            quantity,
            row.lot_size,
        )
        for row in selected
    )
    structure = _OptionStructure(
        legs,
        assumed_portfolio_value,
        expected_holding_days,
    )
    return FutuExactContractSelection(browser, selected, structure)


def _checked_runtime_timestamp(
    name: str, value: object, message: str
) -> _datetime.datetime:
    try:
        return _normalize_utc_timestamp(name, value)
    except Exception:
        raise ValueError(message) from None


@_dataclass(frozen=True)
class FutuBboEvidence:
    """One exact, atomic provider-native Futu BBO frame."""

    provider_identifier: str
    bid_price: _decimal.Decimal
    ask_price: _decimal.Decimal
    bid_size: int
    ask_size: int
    received_at: _datetime.datetime
    provider_bid_timestamp_value: _Optional[_decimal.Decimal] = None
    provider_ask_timestamp_value: _Optional[_decimal.Decimal] = None

    def __post_init__(self) -> None:
        if type(self.provider_identifier) is not str or not self.provider_identifier:
            raise ValueError(_BBO_RESPONSE_MESSAGE)
        if type(self.bid_price) is not _decimal.Decimal or type(
            self.ask_price
        ) is not _decimal.Decimal:
            raise TypeError("BBO prices must be Decimal values")
        bid = _positive_decimal(self.bid_price, _BBO_RESPONSE_MESSAGE)
        ask = _positive_decimal(self.ask_price, _BBO_RESPONSE_MESSAGE)
        if ask < bid:
            raise ValueError(_BBO_RESPONSE_MESSAGE)
        if type(self.bid_size) is not int or self.bid_size <= 0:
            raise ValueError(_BBO_RESPONSE_MESSAGE)
        if type(self.ask_size) is not int or self.ask_size <= 0:
            raise ValueError(_BBO_RESPONSE_MESSAGE)
        received_at = _checked_runtime_timestamp(
            "received_at", self.received_at, _BBO_RESPONSE_MESSAGE
        )
        for name in (
            "provider_bid_timestamp_value",
            "provider_ask_timestamp_value",
        ):
            value = getattr(self, name)
            if value is not None:
                if type(value) is not _decimal.Decimal:
                    raise TypeError(
                        "provider timestamp values must be Decimal values or None"
                    )
                if not value.is_finite():
                    raise ValueError(_BBO_RESPONSE_MESSAGE)
        object.__setattr__(self, "bid_price", bid)
        object.__setattr__(self, "ask_price", ask)
        object.__setattr__(self, "received_at", received_at)


@_dataclass(frozen=True)
class FutuDirectEntryBboEvidence:
    """Paired provider-native BBO evidence without canonical quote semantics."""

    underlying_key: _UnderlyingKey
    contract_verification: FutuExactOptionContractVerification
    underlying_bbo: FutuBboEvidence
    option_bbo: FutuBboEvidence
    market_state_before: _Tuple[_Tuple[str, str], ...]
    market_state_after: _Tuple[_Tuple[str, str], ...]
    state_before_received_at: _datetime.datetime
    state_after_received_at: _datetime.datetime

    def __post_init__(self) -> None:
        if type(self.underlying_key) is not _UnderlyingKey:
            raise TypeError("underlying_key must be an UnderlyingKey")
        if type(self.contract_verification) is not FutuExactOptionContractVerification:
            raise TypeError(
                "contract_verification must be a "
                "FutuExactOptionContractVerification"
            )
        if type(self.underlying_bbo) is not FutuBboEvidence or type(
            self.option_bbo
        ) is not FutuBboEvidence:
            raise TypeError("BBO evidence must be FutuBboEvidence")
        underlying_identifier = "US." + self.underlying_key.symbol
        if (
            self.contract_verification.contract_reference.contract_key.underlying_key
            != self.underlying_key
            or self.underlying_bbo.provider_identifier != underlying_identifier
            or self.option_bbo.provider_identifier
            != self.contract_verification.provider_identifier
        ):
            raise ValueError(_BBO_RESPONSE_MESSAGE)
        expected = frozenset(
            (underlying_identifier, self.contract_verification.provider_identifier)
        )
        for states in (self.market_state_before, self.market_state_after):
            if (
                type(states) is not tuple
                or len(states) != 2
                or any(
                    type(item) is not tuple
                    or len(item) != 2
                    or type(item[0]) is not str
                    or type(item[1]) is not str
                    or not item[1]
                    for item in states
                )
            ):
                raise ValueError(_BBO_RESPONSE_MESSAGE)
            if frozenset(item[0] for item in states) != expected:
                raise ValueError(_BBO_RESPONSE_MESSAGE)
        before = _checked_runtime_timestamp(
            "state_before_received_at",
            self.state_before_received_at,
            _BBO_RESPONSE_MESSAGE,
        )
        after = _checked_runtime_timestamp(
            "state_after_received_at",
            self.state_after_received_at,
            _BBO_RESPONSE_MESSAGE,
        )
        if (
            before > self.underlying_bbo.received_at
            or before > self.option_bbo.received_at
            or after < self.underlying_bbo.received_at
            or after < self.option_bbo.received_at
        ):
            raise ValueError(_BBO_RESPONSE_MESSAGE)
        object.__setattr__(
            self, "market_state_before", tuple(sorted(self.market_state_before))
        )
        object.__setattr__(
            self, "market_state_after", tuple(sorted(self.market_state_after))
        )
        object.__setattr__(self, "state_before_received_at", before)
        object.__setattr__(self, "state_after_received_at", after)


def _market_states(
    quote_context: object, identifiers: tuple
) -> _Tuple[_Tuple[str, str], ...]:
    try:
        ret, table = quote_context.get_market_state(list(identifiers))
    except Exception:
        raise RuntimeError(_BBO_RETRIEVAL_MESSAGE) from None
    if ret != 0:
        raise RuntimeError(_BBO_RETRIEVAL_MESSAGE)
    rows = _records(
        table,
        columns=frozenset(("code", "market_state")),
        message=_BBO_RESPONSE_MESSAGE,
    )
    selected = tuple(
        (row["code"], row["market_state"])
        for row in rows
        if row["code"] in identifiers
    )
    if (
        len(selected) != len(identifiers)
        or frozenset(item[0] for item in selected) != frozenset(identifiers)
        or any(type(item[1]) is not str or not item[1] for item in selected)
    ):
        raise ValueError(_BBO_RESPONSE_MESSAGE)
    return tuple(sorted(selected))


def _bbo_from_atomic_frame(
    *, data: object, rsp_pb: object, expected: frozenset
) -> _Optional[FutuBboEvidence]:
    if type(data) is not dict or data.get("code") not in expected:
        raise ValueError(_BBO_RESPONSE_MESSAGE)
    try:
        if not rsp_pb.HasField("s2c"):
            raise ValueError
        s2c = rsp_pb.s2c
        bid_present = s2c.HasField("svrRecvTimeBidTimestamp")
        ask_present = s2c.HasField("svrRecvTimeAskTimestamp")
        bid_value = (
            _provider_decimal(s2c.svrRecvTimeBidTimestamp, _BBO_RESPONSE_MESSAGE)
            if bid_present
            else None
        )
        ask_value = (
            _provider_decimal(s2c.svrRecvTimeAskTimestamp, _BBO_RESPONSE_MESSAGE)
            if ask_present
            else None
        )
        bids = data.get("Bid") or []
        asks = data.get("Ask") or []
        if len(bids) < 1 or len(asks) < 1 or len(bids[0]) < 2 or len(asks[0]) < 2:
            raise ValueError
        received_at = _utc_now()
        return FutuBboEvidence(
            provider_identifier=data["code"],
            bid_price=_positive_decimal(bids[0][0], _BBO_RESPONSE_MESSAGE),
            ask_price=_positive_decimal(asks[0][0], _BBO_RESPONSE_MESSAGE),
            bid_size=_provider_integer(bids[0][1], _BBO_RESPONSE_MESSAGE),
            ask_size=_provider_integer(asks[0][1], _BBO_RESPONSE_MESSAGE),
            received_at=received_at,
            provider_bid_timestamp_value=bid_value,
            provider_ask_timestamp_value=ask_value,
        )
    except ValueError:
        raise
    except Exception:
        raise ValueError(_BBO_RESPONSE_MESSAGE) from None


def _capture_order_book_handler(quote_context: object) -> object:
    """Capture the pinned-SDK order-book handler so it can be restored."""

    try:
        handler_context = quote_context._handler_ctx
        table = handler_context._handler_table
        slot = table[3013]
        previous = slot["obj"]
        expected_type = slot["type"]
    except Exception:
        raise TypeError(
            "quote_context must expose the pinned Futu handler boundary"
        ) from None
    if type(slot) is not dict or not isinstance(previous, expected_type):
        raise TypeError(
            "quote_context must expose the pinned Futu handler boundary"
        )
    return previous


def retrieve_futu_direct_entry_bbo_evidence(
    quote_context: object,
    contract_verification: FutuExactOptionContractVerification,
    *,
    timeout_seconds: float = 15.0,
) -> FutuDirectEntryBboEvidence:
    """Consume a dedicated context to collect atomic provider-native BBO."""

    if type(contract_verification) is not FutuExactOptionContractVerification:
        raise TypeError(
            "contract_verification must be a FutuExactOptionContractVerification"
        )
    if isinstance(timeout_seconds, bool) or not isinstance(
        timeout_seconds, _numbers.Real
    ):
        raise TypeError("timeout_seconds must be a number")
    if not _math.isfinite(float(timeout_seconds)) or not 0 < timeout_seconds <= 60:
        raise ValueError("timeout_seconds must be greater than 0 and at most 60")
    try:
        set_handler = getattr(quote_context, "set_handler", None)
        subscribe = getattr(quote_context, "subscribe", None)
        get_state = getattr(quote_context, "get_market_state", None)
        close = getattr(quote_context, "close", None)
    except Exception:
        raise TypeError("quote_context must provide Futu quote methods") from None
    if not all(callable(item) for item in (set_handler, subscribe, get_state, close)):
        raise TypeError("quote_context must provide Futu quote methods")

    sdk = _load_futu_sdk()
    previous_handler = _capture_order_book_handler(quote_context)
    try:
        subscription_record = quote_context._sub_record
        existing_subscriptions = subscription_record.get_sub_list()
    except Exception:
        raise TypeError(
            "quote_context must expose the pinned Futu subscription boundary"
        ) from None
    if (
        type(previous_handler) is not sdk.OrderBookHandlerBase
        or type(existing_subscriptions) is not list
        or existing_subscriptions
    ):
        raise ValueError(
            "quote_context must be a dedicated unsubscribed Futu quote context"
        )
    key = contract_verification.contract_reference.contract_key
    underlying_identifier = "US." + key.underlying_key.symbol
    identifiers = (underlying_identifier, contract_verification.provider_identifier)
    expected = frozenset(identifiers)
    frames = {}
    error = []
    lock = _threading.Lock()
    ready = _threading.Event()

    class _AtomicHandler(sdk.OrderBookHandlerBase):
        def on_recv_rsp(self, rsp_pb):
            try:
                previous_handler.on_recv_rsp(rsp_pb)
                ret, data = super().on_recv_rsp(rsp_pb)
                if ret != sdk.RET_OK:
                    raise ValueError(_BBO_RESPONSE_MESSAGE)
                if type(data) is dict and data.get("code") not in expected:
                    return ret, data
                item = _bbo_from_atomic_frame(
                    data=data, rsp_pb=rsp_pb, expected=expected
                )
                if item is not None:
                    with lock:
                        frames[item.provider_identifier] = item
                        if expected.issubset(frames):
                            ready.set()
                return ret, data
            except Exception:
                with lock:
                    error.append(_BBO_RESPONSE_MESSAGE)
                    ready.set()
                return -1, _BBO_RESPONSE_MESSAGE

    try:
        before = _market_states(quote_context, identifiers)
        before_at = _utc_now()
        handler_result = set_handler(_AtomicHandler())
        if handler_result != sdk.RET_OK:
            raise RuntimeError(_BBO_RETRIEVAL_MESSAGE)
        for identifier in identifiers:
            ret, _ = subscribe(
                [identifier],
                [sdk.SubType.ORDER_BOOK],
                is_first_push=True,
                subscribe_push=True,
            )
            if ret != sdk.RET_OK:
                raise RuntimeError(_BBO_RETRIEVAL_MESSAGE)
        ready.wait(float(timeout_seconds))
        with lock:
            if error or not expected.issubset(frames):
                raise ValueError(_BBO_RESPONSE_MESSAGE)
        after = _market_states(quote_context, identifiers)
        after_at = _utc_now()
    except (TypeError, ValueError, RuntimeError):
        raise
    except Exception:
        raise RuntimeError(_BBO_RETRIEVAL_MESSAGE) from None
    finally:
        try:
            close()
        except Exception:
            error.append(_BBO_RETRIEVAL_MESSAGE)
    if error:
        raise RuntimeError(_BBO_RETRIEVAL_MESSAGE)
    return FutuDirectEntryBboEvidence(
        underlying_key=key.underlying_key,
        contract_verification=contract_verification,
        underlying_bbo=frames[underlying_identifier],
        option_bbo=frames[contract_verification.provider_identifier],
        market_state_before=before,
        market_state_after=after,
        state_before_received_at=before_at,
        state_after_received_at=after_at,
    )


def _validate_history_range(
    begin_date: object,
    end_date: object,
    latest_completed_session_date: object,
    *,
    label: str,
) -> _Tuple[_datetime.date, _datetime.date, _datetime.date]:
    begin = _validate_date("begin_date", begin_date)
    end = _validate_date("end_date", end_date)
    completed = _validate_date(
        "latest_completed_session_date", latest_completed_session_date
    )
    if begin >= end:
        raise ValueError("begin_date must precede end_date")
    if (end - begin).days > 370:
        raise ValueError(f"{label} range must not exceed 370 calendar days")
    if end > completed + _datetime.timedelta(days=1):
        raise ValueError("end_date must not include an incomplete session")
    return begin, end, completed


def _history_request(
    quote_context: object,
    sdk: object,
    identifier: str,
    begin_date: _datetime.date,
    end_date: _datetime.date,
    *,
    retrieval_message: str,
    response_message: str,
) -> tuple:
    try:
        method = getattr(quote_context, "request_history_kline", None)
    except Exception:
        method = None
    if not callable(method):
        raise TypeError("quote_context must provide Futu quote methods")
    try:
        response = method(
            identifier,
            start=begin_date.isoformat(),
            end=(end_date - _datetime.timedelta(days=1)).isoformat(),
            ktype=sdk.KLType.K_DAY,
            autype=sdk.AuType.NONE,
            max_count=1000,
        )
    except Exception:
        raise RuntimeError(retrieval_message) from None
    retrieved_at = _utc_now()
    if not isinstance(response, tuple) or len(response) != 3 or response[0] != sdk.RET_OK:
        raise RuntimeError(retrieval_message)
    rows = _records(
        response[1],
        columns=frozenset(("code", "time_key", "open", "high", "low", "close", "volume")),
        message=response_message,
    )
    return rows, retrieved_at


def _history_ohlc(row: dict, message: str) -> tuple:
    values = tuple(
        _positive_decimal(row[name], message)
        for name in ("open", "high", "low", "close")
    )
    if values[2] > min(values[0], values[3]) or values[1] < max(
        values[0], values[3]
    ) or values[1] < values[2]:
        raise ValueError(message)
    return values


def _bar_source_and_metadata(
    *,
    underlying_key: _UnderlyingKey,
    provider_identifier: str,
    session_date: _datetime.date,
    observed_at: _datetime.datetime,
    retrieved_at: _datetime.datetime,
) -> _NormalizationMetadata:
    material = "\x00".join(
        (
            _DAILY_BAR_NORMALIZATION_VERSION,
            provider_identifier,
            session_date.isoformat(),
            retrieved_at.isoformat(),
        )
    ).encode("utf-8")
    digest = _hashlib.sha256(material).hexdigest()
    source = _SourceReference(
        source_id="futu-underlying-daily-bar-source:" + digest,
        provider_name="Futu OpenAPI",
        dataset_name="historical_kline_unadjusted_daily",
        provider_record_id=provider_identifier + ":" + session_date.isoformat(),
        provider_request_id=None,
        source_symbol=provider_identifier,
        source_uri=None,
        observed_at=observed_at,
        retrieved_at=retrieved_at,
        provider_timezone="America/New_York",
        timestamp_methodology=(
            "Futu time_key interpreted as the America/New_York daily-bar start."
        ),
        origin=_DataOrigin.EXCHANGE_OBSERVED,
        is_delayed=False,
        declared_delay_seconds=None,
        payload_sha256=None,
        revision_number=None,
        provider_correction_id=None,
        quality_flags=(),
    )
    return _NormalizationMetadata(
        record_id="futu-underlying-daily-bar:" + digest,
        source_references=(source,),
        effective_observed_at=observed_at,
        normalized_at=retrieved_at,
        record_origin=_DataOrigin.EXCHANGE_OBSERVED,
        normalization_methodology=(
            "Exact Futu AuType.NONE completed daily OHLCV row normalized "
            "without price adjustment or interpolation."
        ),
        unit_convention="USD per share prices; provider-reported share volume.",
        normalization_version=_DAILY_BAR_NORMALIZATION_VERSION,
        quality_flags=(_NormalizationQualityFlag.SYMBOL_MAPPED,),
    )


def retrieve_futu_underlying_daily_bars(
    quote_context: object,
    *,
    underlying_key: _UnderlyingKey,
    begin_date: _datetime.date,
    end_date: _datetime.date,
    latest_completed_session_date: _datetime.date,
) -> _Tuple[_UnderlyingDailyBarObservation, ...]:
    """Retrieve exact completed unadjusted Futu daily bars in [begin, end)."""

    if type(underlying_key) is not _UnderlyingKey:
        raise TypeError("underlying_key must be an UnderlyingKey")
    begin, end, completed = _validate_history_range(
        begin_date,
        end_date,
        latest_completed_session_date,
        label="daily-bar",
    )
    sdk = _load_futu_sdk()
    identifier = "US." + underlying_key.symbol
    rows, retrieved_at = _history_request(
        quote_context,
        sdk,
        identifier,
        begin,
        end,
        retrieval_message=_BAR_RETRIEVAL_MESSAGE,
        response_message=_BAR_RESPONSE_MESSAGE,
    )
    if not rows:
        raise ValueError(_BAR_RESPONSE_MESSAGE)
    evidence = []
    seen = set()
    for row in rows:
        try:
            if row["code"] != identifier:
                raise ValueError
            observed_at = _parse_eastern_timestamp(row["time_key"], _BAR_RESPONSE_MESSAGE)
            session_date = observed_at.astimezone(_US_EASTERN).date()
            if (
                session_date < begin
                or session_date >= end
                or session_date > completed
                or session_date in seen
                or observed_at > retrieved_at
            ):
                raise ValueError
            prices = _history_ohlc(row, _BAR_RESPONSE_MESSAGE)
            volume = _provider_integer(row["volume"], _BAR_RESPONSE_MESSAGE)
            if volume < 0:
                raise ValueError
            metadata = _bar_source_and_metadata(
                underlying_key=underlying_key,
                provider_identifier=identifier,
                session_date=session_date,
                observed_at=observed_at,
                retrieved_at=retrieved_at,
            )
            evidence.append(
                _UnderlyingDailyBarObservation(
                    underlying_key=underlying_key,
                    session_date=session_date,
                    open_price=prices[0],
                    high_price=prices[1],
                    low_price=prices[2],
                    close_price=prices[3],
                    adjusted_close_price=None,
                    volume=volume,
                    is_session_complete=True,
                    adjustment_methodology=None,
                    metadata=metadata,
                )
            )
            seen.add(session_date)
        except Exception:
            raise ValueError(_BAR_RESPONSE_MESSAGE) from None
    return tuple(sorted(evidence, key=lambda item: item.session_date))


@_dataclass(frozen=True)
class FutuHistoricalOptionBarEvidence:
    """Immutable Futu-native historical daily OHLCV for one exact option."""

    contract_verification: FutuExactOptionContractVerification
    bar_started_at: _datetime.datetime
    session_date: _datetime.date
    open_premium: _decimal.Decimal
    high_premium: _decimal.Decimal
    low_premium: _decimal.Decimal
    close_premium: _decimal.Decimal
    volume: int
    turnover: _Optional[_decimal.Decimal]
    retrieved_at: _datetime.datetime

    def __post_init__(self) -> None:
        if type(self.contract_verification) is not FutuExactOptionContractVerification:
            raise TypeError(
                "contract_verification must be a "
                "FutuExactOptionContractVerification"
            )
        started = _checked_runtime_timestamp(
            "bar_started_at", self.bar_started_at, _OPTION_BAR_RESPONSE_MESSAGE
        )
        if type(self.session_date) is not _datetime.date or started.astimezone(
            _US_EASTERN
        ).date() != self.session_date:
            raise ValueError(_OPTION_BAR_RESPONSE_MESSAGE)
        if any(
            type(value) is not _decimal.Decimal
            for value in (
                self.open_premium,
                self.high_premium,
                self.low_premium,
                self.close_premium,
            )
        ):
            raise TypeError("option-bar premiums must be Decimal values")
        prices = _history_ohlc(
            {
                "open": self.open_premium,
                "high": self.high_premium,
                "low": self.low_premium,
                "close": self.close_premium,
            },
            _OPTION_BAR_RESPONSE_MESSAGE,
        )
        if type(self.volume) is not int or self.volume < 0:
            raise ValueError(_OPTION_BAR_RESPONSE_MESSAGE)
        turnover = None
        if self.turnover is not None:
            if type(self.turnover) is not _decimal.Decimal:
                raise TypeError("turnover must be a Decimal or None")
            turnover = _nonnegative_decimal(
                self.turnover, _OPTION_BAR_RESPONSE_MESSAGE
            )
        retrieved = _checked_runtime_timestamp(
            "retrieved_at", self.retrieved_at, _OPTION_BAR_RESPONSE_MESSAGE
        )
        if started > retrieved:
            raise ValueError(_OPTION_BAR_RESPONSE_MESSAGE)
        for name, value in zip(
            ("open_premium", "high_premium", "low_premium", "close_premium"),
            prices,
        ):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "bar_started_at", started)
        object.__setattr__(self, "turnover", turnover)
        object.__setattr__(self, "retrieved_at", retrieved)


def retrieve_futu_historical_option_bar_evidence(
    quote_context: object,
    contract_verification: FutuExactOptionContractVerification,
    *,
    begin_date: _datetime.date,
    end_date: _datetime.date,
    latest_completed_session_date: _datetime.date,
) -> _Tuple[FutuHistoricalOptionBarEvidence, ...]:
    """Retrieve provider-native completed daily OHLCV for one exact option."""

    if type(contract_verification) is not FutuExactOptionContractVerification:
        raise TypeError(
            "contract_verification must be a FutuExactOptionContractVerification"
        )
    begin, end, completed = _validate_history_range(
        begin_date,
        end_date,
        latest_completed_session_date,
        label="option-bar",
    )
    sdk = _load_futu_sdk()
    rows, retrieved_at = _history_request(
        quote_context,
        sdk,
        contract_verification.provider_identifier,
        begin,
        end,
        retrieval_message=_OPTION_BAR_RETRIEVAL_MESSAGE,
        response_message=_OPTION_BAR_RESPONSE_MESSAGE,
    )
    evidence = []
    seen = set()
    for row in rows:
        try:
            if row["code"] != contract_verification.provider_identifier:
                raise ValueError
            started = _parse_eastern_timestamp(
                row["time_key"], _OPTION_BAR_RESPONSE_MESSAGE
            )
            session_date = started.astimezone(_US_EASTERN).date()
            if (
                session_date < begin
                or session_date >= end
                or session_date > completed
                or session_date in seen
                or started > retrieved_at
            ):
                raise ValueError
            prices = _history_ohlc(row, _OPTION_BAR_RESPONSE_MESSAGE)
            volume = _provider_integer(row["volume"], _OPTION_BAR_RESPONSE_MESSAGE)
            if volume < 0:
                raise ValueError
            turnover = None
            if "turnover" in row and row["turnover"] is not None:
                turnover = _nonnegative_decimal(
                    row["turnover"], _OPTION_BAR_RESPONSE_MESSAGE
                )
            evidence.append(
                FutuHistoricalOptionBarEvidence(
                    contract_verification=contract_verification,
                    bar_started_at=started,
                    session_date=session_date,
                    open_premium=prices[0],
                    high_premium=prices[1],
                    low_premium=prices[2],
                    close_premium=prices[3],
                    volume=volume,
                    turnover=turnover,
                    retrieved_at=retrieved_at,
                )
            )
            seen.add(session_date)
        except Exception:
            raise ValueError(_OPTION_BAR_RESPONSE_MESSAGE) from None
    return tuple(sorted(evidence, key=lambda item: item.bar_started_at))


@_dataclass(frozen=True)
class FutuExactOptionAnalyticsActivityEvidence:
    """Provider-native Futu option activity and unnormalized analytics."""

    contract_verification: FutuExactOptionContractVerification
    volume: int
    open_interest: int
    implied_volatility: _decimal.Decimal
    delta: _decimal.Decimal
    gamma: _decimal.Decimal
    theta: _decimal.Decimal
    vega: _decimal.Decimal
    rho: _decimal.Decimal
    last_trade_at: _Optional[_datetime.datetime]
    retrieved_at: _datetime.datetime

    def __post_init__(self) -> None:
        if type(self.contract_verification) is not FutuExactOptionContractVerification:
            raise TypeError(
                "contract_verification must be a "
                "FutuExactOptionContractVerification"
            )
        if type(self.volume) is not int or self.volume < 0:
            raise ValueError(_ANALYTICS_RESPONSE_MESSAGE)
        if type(self.open_interest) is not int or self.open_interest < 0:
            raise ValueError(_ANALYTICS_RESPONSE_MESSAGE)
        values = (
            self.implied_volatility,
            self.delta,
            self.gamma,
            self.theta,
            self.vega,
            self.rho,
        )
        if any(type(value) is not _decimal.Decimal for value in values):
            raise TypeError("option analytics must be Decimal values")
        iv = _positive_decimal(self.implied_volatility, _ANALYTICS_RESPONSE_MESSAGE)
        delta = _provider_decimal(self.delta, _ANALYTICS_RESPONSE_MESSAGE)
        gamma = _nonnegative_decimal(self.gamma, _ANALYTICS_RESPONSE_MESSAGE)
        theta = _provider_decimal(self.theta, _ANALYTICS_RESPONSE_MESSAGE)
        vega = _nonnegative_decimal(self.vega, _ANALYTICS_RESPONSE_MESSAGE)
        rho = _provider_decimal(self.rho, _ANALYTICS_RESPONSE_MESSAGE)
        if delta < -1 or delta > 1:
            raise ValueError(_ANALYTICS_RESPONSE_MESSAGE)
        retrieved = _checked_runtime_timestamp(
            "retrieved_at", self.retrieved_at, _ANALYTICS_RESPONSE_MESSAGE
        )
        last = None
        if self.last_trade_at is not None:
            last = _checked_runtime_timestamp(
                "last_trade_at", self.last_trade_at, _ANALYTICS_RESPONSE_MESSAGE
            )
            if last > retrieved:
                raise ValueError(_ANALYTICS_RESPONSE_MESSAGE)
        object.__setattr__(self, "implied_volatility", iv)
        object.__setattr__(self, "delta", delta)
        object.__setattr__(self, "gamma", gamma)
        object.__setattr__(self, "theta", theta)
        object.__setattr__(self, "vega", vega)
        object.__setattr__(self, "rho", rho)
        object.__setattr__(self, "last_trade_at", last)
        object.__setattr__(self, "retrieved_at", retrieved)


def retrieve_futu_exact_option_analytics_activity_evidence(
    quote_context: object,
    contract_verification: FutuExactOptionContractVerification,
) -> FutuExactOptionAnalyticsActivityEvidence:
    """Retrieve Futu-native analytics/activity without semantic promotion."""

    if type(contract_verification) is not FutuExactOptionContractVerification:
        raise TypeError(
            "contract_verification must be a FutuExactOptionContractVerification"
        )
    try:
        method = getattr(quote_context, "get_market_snapshot", None)
    except Exception:
        method = None
    if not callable(method):
        raise TypeError("quote_context must provide Futu quote methods")
    try:
        ret, table = method([contract_verification.provider_identifier])
    except Exception:
        raise RuntimeError(_ANALYTICS_RETRIEVAL_MESSAGE) from None
    retrieved_at = _utc_now()
    if ret != 0:
        raise RuntimeError(_ANALYTICS_RETRIEVAL_MESSAGE)
    columns = frozenset(
        (
            "code",
            "volume",
            "option_open_interest",
            "option_implied_volatility",
            "option_delta",
            "option_gamma",
            "option_theta",
            "option_vega",
            "option_rho",
            "update_time",
        )
    )
    rows = _records(table, columns=columns, message=_ANALYTICS_RESPONSE_MESSAGE)
    exact = tuple(
        row
        for row in rows
        if row["code"] == contract_verification.provider_identifier
    )
    if len(exact) != 1:
        raise ValueError(_ANALYTICS_RESPONSE_MESSAGE)
    row = exact[0]
    try:
        volume = _provider_integer(row["volume"], _ANALYTICS_RESPONSE_MESSAGE)
        open_interest = _provider_integer(
            row["option_open_interest"], _ANALYTICS_RESPONSE_MESSAGE
        )
        if volume < 0 or open_interest < 0:
            raise ValueError
        last_trade_at = None
        if row["update_time"] not in (None, "", "N/A"):
            last_trade_at = _parse_eastern_timestamp(
                row["update_time"], _ANALYTICS_RESPONSE_MESSAGE
            )
        return FutuExactOptionAnalyticsActivityEvidence(
            contract_verification=contract_verification,
            volume=volume,
            open_interest=open_interest,
            implied_volatility=_positive_decimal(
                row["option_implied_volatility"], _ANALYTICS_RESPONSE_MESSAGE
            ),
            delta=_provider_decimal(row["option_delta"], _ANALYTICS_RESPONSE_MESSAGE),
            gamma=_nonnegative_decimal(
                row["option_gamma"], _ANALYTICS_RESPONSE_MESSAGE
            ),
            theta=_provider_decimal(row["option_theta"], _ANALYTICS_RESPONSE_MESSAGE),
            vega=_nonnegative_decimal(row["option_vega"], _ANALYTICS_RESPONSE_MESSAGE),
            rho=_provider_decimal(row["option_rho"], _ANALYTICS_RESPONSE_MESSAGE),
            last_trade_at=last_trade_at,
            retrieved_at=retrieved_at,
        )
    except Exception:
        raise ValueError(_ANALYTICS_RESPONSE_MESSAGE) from None
