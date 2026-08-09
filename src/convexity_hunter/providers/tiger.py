"""Bounded Tiger OpenAPI runtime and exact-contract verification."""

import datetime as _datetime
import decimal as _decimal
import hashlib as _hashlib
import logging as _logging
import numbers as _numbers
import os as _os
import re as _re
import stat as _stat
from dataclasses import dataclass as _dataclass
from pathlib import Path as _Path
from zoneinfo import ZoneInfo as _ZoneInfo
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Tuple as _Tuple
from typing import Type as _Type

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
    "resolve_tiger_config_path",
    "initialize_tiger_quote_client",
    "TigerExactOptionContractVerification",
    "TigerExactOptionQuoteEvidence",
    "verify_tiger_monthly_option_contract",
    "retrieve_tiger_exact_option_quote_evidence",
    "retrieve_tiger_underlying_daily_bars",
    "TigerHistoricalDividendEvidence",
    "retrieve_tiger_historical_dividend_evidence",
)


_CONFIG_ENVIRONMENT_VARIABLE = "CONVEXITY_HUNTER_TIGER_CONFIG"
_DEFAULT_CONFIG_RELATIVE_PATH = _Path(
    ".config/tigeropen/tiger_openapi_config.properties"
)
_TOKEN_FILENAME = "tiger_openapi_token.properties"
_UNSUPPORTED_SDK_ENVIRONMENT_PREFIX = "TIGEROPEN_"

_NOT_FOUND_MESSAGE = (
    "Tiger OpenAPI configuration was not found. Place Tiger's official "
    "tiger_openapi_config.properties at "
    "~/.config/tigeropen/tiger_openapi_config.properties or set "
    "CONVEXITY_HUNTER_TIGER_CONFIG to an absolute local file path."
)
_INVALID_PATH_MESSAGE = "Tiger OpenAPI configuration path is invalid."
_NON_REGULAR_MESSAGE = "Tiger OpenAPI configuration must be a regular file."
_REPOSITORY_MESSAGE = (
    "Tiger OpenAPI configuration must be outside the repository worktree."
)
_PERMISSION_MESSAGE = (
    "Tiger OpenAPI configuration must be owner-readable and private to the "
    "current user."
)
_SDK_ENVIRONMENT_MESSAGE = (
    "Tiger SDK environment configuration is unsupported; use only "
    "CONVEXITY_HUNTER_TIGER_CONFIG as a local path override."
)
_SDK_UNAVAILABLE_MESSAGE = (
    "Tiger OpenAPI SDK is unavailable. Install convexity-hunter[tiger]."
)
_SDK_INITIALIZATION_MESSAGE = "Tiger OpenAPI client initialization failed."
_EXPIRATION_RETRIEVAL_MESSAGE = "Tiger option-expiration retrieval failed."
_CHAIN_RETRIEVAL_MESSAGE = "Tiger option-chain retrieval failed."
_EXPIRATION_TABLE_MESSAGE = "Tiger option-expiration response is invalid."
_CHAIN_TABLE_MESSAGE = "Tiger option-chain response is invalid."
_EXPIRATION_MATCH_MESSAGE = (
    "Tiger option-expiration response must contain exactly one exact match."
)
_MONTHLY_MESSAGE = "Tiger does not classify the exact expiration as monthly."
_CHAIN_MATCH_MESSAGE = (
    "Tiger option-chain response must contain exactly one exact contract match."
)
_IDENTIFIER_MESSAGE = "Tiger option identifier is inconsistent."
_MULTIPLIER_MESSAGE = "Tiger option multiplier is invalid."
_PERMISSION_RETRIEVAL_MESSAGE = "Tiger quote-permission retrieval failed."
_PERMISSION_RESPONSE_MESSAGE = "Tiger quote-permission response is invalid."
_PERMISSION_MATCH_MESSAGE = (
    "Tiger quote-permission response must contain exactly one usOptionQuote entry."
)
_PERMISSION_INACTIVE_MESSAGE = "Tiger usOptionQuote permission is not active."
_QUOTE_RESPONSE_MESSAGE = "Tiger exact option quote response is invalid."
_QUOTE_MATCH_MESSAGE = (
    "Tiger option-chain response must contain exactly one verified contract row."
)
_BAR_RETRIEVAL_MESSAGE = "Tiger underlying daily-bar retrieval failed."
_BAR_RESPONSE_MESSAGE = "Tiger underlying daily-bar response is invalid."
_BAR_PAIRING_MESSAGE = "Tiger NR and BR daily-bar series do not pair exactly."
_DIVIDEND_RETRIEVAL_MESSAGE = (
    "Tiger historical-dividend retrieval failed."
)
_DIVIDEND_RESPONSE_MESSAGE = (
    "Tiger historical-dividend response is invalid."
)
_DIVIDEND_DUPLICATE_MESSAGE = (
    "Tiger historical-dividend response contains duplicate rows."
)

_EXPIRATION_COLUMNS = frozenset(("symbol", "date", "timestamp", "period_tag"))
_CHAIN_COLUMNS = frozenset(
    ("identifier", "symbol", "expiry", "strike", "put_call", "multiplier")
)
_QUOTE_COLUMNS = _CHAIN_COLUMNS | frozenset(
    ("bid_price", "ask_price", "bid_size", "ask_size")
)
_BAR_COLUMNS = frozenset(("symbol", "time", "open", "high", "low", "close", "volume"))
_DIVIDEND_COLUMNS = (
    "symbol",
    "action_type",
    "amount",
    "currency",
    "announced_date",
    "execute_date",
    "record_date",
    "pay_date",
    "market",
    "exchange",
)
_DIVIDEND_COLUMN_SET = frozenset(_DIVIDEND_COLUMNS)
_TIGER_NORMALIZATION_VERSION = "tiger-option-contract-v0.1"
_TIGER_DAILY_BAR_NORMALIZATION_VERSION = "tiger-underlying-daily-bar-v0.1"
_US_EASTERN = _ZoneInfo("America/New_York")


def _home_directory() -> _Path:
    return _Path.home()


def _repository_root() -> _Optional[_Path]:
    module_path = _Path(__file__).resolve()
    for candidate in module_path.parents:
        if (candidate / ".git").exists():
            return candidate.resolve()
    return None


def _has_unsupported_sdk_environment() -> bool:
    return any(
        name.startswith(_UNSUPPORTED_SDK_ENVIRONMENT_PREFIX)
        for name in _os.environ
    )


def _canonical_path(raw_path: str) -> _Path:
    if not raw_path or not raw_path.strip():
        raise ValueError(_INVALID_PATH_MESSAGE)
    try:
        expanded = _Path(raw_path).expanduser()
        if not expanded.is_absolute():
            raise ValueError(_INVALID_PATH_MESSAGE)
        return expanded.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        raise ValueError(_INVALID_PATH_MESSAGE) from None


def _is_within(path: _Path, directory: _Path) -> bool:
    try:
        return _os.path.commonpath((str(path), str(directory))) == str(directory)
    except ValueError:
        return False


def _validate_external_file(
    path: _Path,
    *,
    missing_allowed: bool,
) -> _Optional[_Path]:
    try:
        canonical = path.resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        raise ValueError(_INVALID_PATH_MESSAGE) from None
    repository_root = _repository_root()
    if repository_root is not None and _is_within(canonical, repository_root):
        raise ValueError(_REPOSITORY_MESSAGE)

    try:
        file_stat = canonical.stat()
    except FileNotFoundError:
        if missing_allowed:
            return None
        raise FileNotFoundError(_NOT_FOUND_MESSAGE) from None
    except OSError:
        raise ValueError(_INVALID_PATH_MESSAGE) from None

    if not _stat.S_ISREG(file_stat.st_mode):
        raise ValueError(_NON_REGULAR_MESSAGE)

    if _os.name == "posix":
        mode = _stat.S_IMODE(file_stat.st_mode)
        owner_readable = bool(mode & _stat.S_IRUSR)
        unsafe_bits = mode & (
            _stat.S_IXUSR | _stat.S_IRWXG | _stat.S_IRWXO
        )
        if (
            file_stat.st_uid != _os.getuid()
            or not owner_readable
            or unsafe_bits
        ):
            raise ValueError(_PERMISSION_MESSAGE)

    return canonical


def _validate_adjacent_token_file(config_path: _Path) -> None:
    token_path = config_path.with_name(_TOKEN_FILENAME)
    _validate_external_file(token_path, missing_allowed=True)


def resolve_tiger_config_path() -> _Path:
    """Resolve one private external Tiger provider configuration path."""

    if _has_unsupported_sdk_environment():
        raise RuntimeError(_SDK_ENVIRONMENT_MESSAGE)

    if _CONFIG_ENVIRONMENT_VARIABLE in _os.environ:
        raw_path = _os.environ[_CONFIG_ENVIRONMENT_VARIABLE]
    else:
        raw_path = str(_home_directory() / _DEFAULT_CONFIG_RELATIVE_PATH)

    config_path = _validate_external_file(
        _canonical_path(raw_path),
        missing_allowed=False,
    )
    if config_path is None:  # pragma: no cover - excluded by missing_allowed
        raise FileNotFoundError(_NOT_FOUND_MESSAGE)
    _validate_adjacent_token_file(config_path)
    return config_path


def _load_tiger_sdk() -> _Tuple[_Type[object], _Type[object]]:
    try:
        from tigeropen.quote.quote_client import QuoteClient
        from tigeropen.tiger_open_config import TigerOpenClientConfig
    except Exception:
        raise RuntimeError(_SDK_UNAVAILABLE_MESSAGE) from None
    return TigerOpenClientConfig, QuoteClient


class _DiscardRootLogFilter(_logging.Filter):
    def filter(self, record: _logging.LogRecord) -> bool:
        return False


def _construct_client_config(config_type: _Type[object], config_path: _Path) -> object:
    root_logger = _logging.getLogger()
    discard_filter = _DiscardRootLogFilter()
    root_logger.addFilter(discard_filter)
    try:
        return config_type(
            props_path=str(config_path),
            enable_dynamic_domain=False,
        )
    finally:
        root_logger.removeFilter(discard_filter)


def _discard_logger() -> _logging.Logger:
    logger = _logging.Logger(
        "convexity_hunter.tigeropen.runtime",
        level=_logging.CRITICAL + 1,
    )
    logger.addHandler(_logging.NullHandler())
    logger.propagate = False
    return logger


def initialize_tiger_quote_client() -> object:
    """Construct a local Tiger QuoteClient without network or permission grab."""

    config_path = resolve_tiger_config_path()
    config_type, quote_client_type = _load_tiger_sdk()
    try:
        client_config = _construct_client_config(config_type, config_path)
        if not all(
            bool(getattr(client_config, field, None))
            for field in ("tiger_id", "account", "private_key")
        ):
            raise ValueError("required Tiger configuration fields are absent")
        setattr(client_config, "token_refresh_duration", 0)
        setattr(client_config, "log_path", None)
        setattr(client_config, "log_level", None)
        return quote_client_type(
            client_config,
            logger=_discard_logger(),
            is_grab_permission=False,
        )
    except Exception:
        raise RuntimeError(_SDK_INITIALIZATION_MESSAGE) from None


def _utc_now() -> _datetime.datetime:
    return _datetime.datetime.now(_datetime.timezone.utc)


def _canonical_option_type(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("option_type must be a string")
    normalized = value.strip().lower()
    if normalized not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")
    return normalized


def _validate_expiration(value: object) -> _datetime.date:
    if isinstance(value, _datetime.datetime) or not isinstance(
        value, _datetime.date
    ):
        raise TypeError("expiration must be a date without a time component")
    return value


def _validate_strike(value: object) -> _decimal.Decimal:
    if not isinstance(value, _decimal.Decimal):
        raise TypeError("strike must be a Decimal")
    if not value.is_finite() or value <= 0:
        raise ValueError("strike must be finite and greater than 0")
    return value


def _provider_integer(value: object, message: str) -> int:
    try:
        if isinstance(value, bool) or not isinstance(value, _numbers.Integral):
            raise ValueError(message)
        normalized = int(value)
    except Exception:
        raise ValueError(message) from None
    if normalized <= 0:
        raise ValueError(message)
    return normalized


def _provider_decimal(value: object) -> _decimal.Decimal:
    if isinstance(value, bool):
        raise ValueError(_CHAIN_TABLE_MESSAGE)
    try:
        normalized = _decimal.Decimal(str(value))
    except Exception:
        raise ValueError(_CHAIN_TABLE_MESSAGE) from None
    if not normalized.is_finite() or normalized <= 0:
        raise ValueError(_CHAIN_TABLE_MESSAGE)
    return normalized


def _provider_quote_decimal(
    value: object,
    *,
    allow_zero: bool,
) -> _decimal.Decimal:
    if isinstance(value, bool):
        raise ValueError(_QUOTE_RESPONSE_MESSAGE)
    try:
        normalized = _decimal.Decimal(str(value))
    except Exception:
        raise ValueError(_QUOTE_RESPONSE_MESSAGE) from None
    if not normalized.is_finite():
        raise ValueError(_QUOTE_RESPONSE_MESSAGE)
    if normalized < 0 or (not allow_zero and normalized == 0):
        raise ValueError(_QUOTE_RESPONSE_MESSAGE)
    return normalized


def _provider_optional_size(value: object) -> _Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(_QUOTE_RESPONSE_MESSAGE)
    try:
        text = str(value)
        if text == "<NA>":
            return None
        normalized = _decimal.Decimal(text)
    except Exception:
        raise ValueError(_QUOTE_RESPONSE_MESSAGE) from None
    if not normalized.is_finite():
        if normalized.is_nan():
            return None
        raise ValueError(_QUOTE_RESPONSE_MESSAGE)
    if normalized < 0 or normalized != normalized.to_integral_value():
        raise ValueError(_QUOTE_RESPONSE_MESSAGE)
    return int(normalized)


def _bar_decimal(value: object) -> _decimal.Decimal:
    if isinstance(value, bool):
        raise ValueError(_BAR_RESPONSE_MESSAGE)
    try:
        normalized = _decimal.Decimal(str(value))
    except Exception:
        raise ValueError(_BAR_RESPONSE_MESSAGE) from None
    if not normalized.is_finite() or normalized <= 0:
        raise ValueError(_BAR_RESPONSE_MESSAGE)
    return normalized


def _bar_volume(value: object) -> int:
    try:
        if isinstance(value, bool) or not isinstance(value, _numbers.Integral):
            normalized = _decimal.Decimal(str(value))
            if (
                not normalized.is_finite()
                or normalized < 0
                or normalized != normalized.to_integral_value()
            ):
                raise ValueError(_BAR_RESPONSE_MESSAGE)
            return int(normalized)
        normalized_integer = int(value)
    except Exception:
        raise ValueError(_BAR_RESPONSE_MESSAGE) from None
    if normalized_integer < 0:
        raise ValueError(_BAR_RESPONSE_MESSAGE)
    return normalized_integer


def _bar_ohlc(row: dict) -> _Tuple[_decimal.Decimal, ...]:
    prices = tuple(
        _bar_decimal(row[name]) for name in ("open", "high", "low", "close")
    )
    open_price, high_price, low_price, close_price = prices
    if (
        low_price > min(open_price, close_price)
        or high_price < max(open_price, close_price)
        or high_price < low_price
    ):
        raise ValueError(_BAR_RESPONSE_MESSAGE)
    return prices


def _provider_bar_datetime(value: object) -> _Tuple[int, _datetime.datetime]:
    timestamp = _provider_integer(value, _BAR_RESPONSE_MESSAGE)
    try:
        observed_at = _datetime.datetime(
            1970, 1, 1, tzinfo=_datetime.timezone.utc
        ) + _datetime.timedelta(milliseconds=timestamp)
    except (OverflowError, ValueError):
        raise ValueError(_BAR_RESPONSE_MESSAGE) from None
    return timestamp, observed_at


def _permission_expiry(value: object) -> int:
    try:
        if isinstance(value, bool) or not isinstance(value, _numbers.Integral):
            raise ValueError(_PERMISSION_RESPONSE_MESSAGE)
        normalized = int(value)
    except Exception:
        raise ValueError(_PERMISSION_RESPONSE_MESSAGE) from None
    if normalized != -1 and normalized <= 0:
        raise ValueError(_PERMISSION_RESPONSE_MESSAGE)
    return normalized


def _normalize_utc_runtime_timestamp(
    name: str,
    value: object,
) -> _datetime.datetime:
    if type(value) is not _datetime.datetime:
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(_datetime.timezone.utc)


def _unix_milliseconds(value: _datetime.datetime) -> int:
    epoch = _datetime.datetime(1970, 1, 1, tzinfo=_datetime.timezone.utc)
    delta = value - epoch
    microseconds = (
        delta.days * 86_400_000_000
        + delta.seconds * 1_000_000
        + delta.microseconds
    )
    return microseconds // 1000


def _table_records(table: object, *, columns: frozenset, message: str) -> tuple:
    try:
        to_dict = getattr(table, "to_dict", None)
        if not callable(to_dict):
            raise ValueError(message)
        records = to_dict("records")
        if not isinstance(records, (list, tuple)):
            raise ValueError(message)
        copied = []
        for record in records:
            if not isinstance(record, _Mapping) or not columns.issubset(
                record.keys()
            ):
                raise ValueError(message)
            copied.append({name: record[name] for name in columns})
        return tuple(copied)
    except Exception:
        raise ValueError(message) from None


def _decode_tiger_identifier(
    identifier: object,
) -> _Tuple[str, _datetime.date, str, _decimal.Decimal]:
    if type(identifier) is not str or identifier != identifier.strip():
        raise ValueError(_IDENTIFIER_MESSAGE)
    if len(identifier) != 21:
        raise ValueError(_IDENTIFIER_MESSAGE)
    root_field = identifier[:6]
    root = root_field.rstrip(" ")
    if (
        not root
        or root_field != root.ljust(6, " ")
        or _re.fullmatch(r"[A-Z0-9.\-]{1,6}", root) is None
    ):
        raise ValueError(_IDENTIFIER_MESSAGE)
    suffix = identifier[6:]
    match = _re.fullmatch(r"(\d{6})([CP])(\d{8})", suffix)
    if match is None:
        raise ValueError(_IDENTIFIER_MESSAGE)
    date_text, direction, strike_text = match.groups()
    try:
        expiration = _datetime.date(
            2000 + int(date_text[0:2]),
            int(date_text[2:4]),
            int(date_text[4:6]),
        )
    except ValueError:
        raise ValueError(_IDENTIFIER_MESSAGE) from None
    option_type = "call" if direction == "C" else "put"
    strike = _decimal.Decimal(strike_text) / _decimal.Decimal("1000")
    if strike <= 0:
        raise ValueError(_IDENTIFIER_MESSAGE)
    return root, expiration, option_type, strike


@_dataclass(frozen=True)
class TigerExactOptionContractVerification:
    """Verified Tiger monthly evidence for one exact normalized contract."""

    provider_identifier: str
    provider_period_tag: str
    provider_expiration_timestamp_ms: int
    contract_reference: _OptionContractReference

    def __post_init__(self) -> None:
        if self.provider_period_tag != "m":
            raise ValueError(_MONTHLY_MESSAGE)
        timestamp = _provider_integer(
            self.provider_expiration_timestamp_ms,
            _EXPIRATION_TABLE_MESSAGE,
        )
        if not isinstance(self.contract_reference, _OptionContractReference):
            raise TypeError(
                "contract_reference must be an OptionContractReference"
            )
        root, expiration, option_type, strike = _decode_tiger_identifier(
            self.provider_identifier
        )
        key = self.contract_reference.contract_key
        if (
            root != key.underlying_key.symbol
            or expiration != key.expiration
            or option_type != key.option_type
            or strike != key.strike
        ):
            raise ValueError(_IDENTIFIER_MESSAGE)
        metadata = self.contract_reference.metadata
        sources = {
            source.dataset_name: source for source in metadata.source_references
        }
        if (
            metadata.record_origin is not _DataOrigin.PROVIDER_REFERENCE
            or metadata.normalization_version != _TIGER_NORMALIZATION_VERSION
            or len(metadata.source_references) != 2
            or set(sources) != {"option_expirations", "option_chain"}
        ):
            raise ValueError(_IDENTIFIER_MESSAGE)
        expiration_source = sources["option_expirations"]
        chain_source = sources["option_chain"]
        if (
            expiration_source.provider_name != "Tiger OpenAPI"
            or expiration_source.origin is not _DataOrigin.PROVIDER_REFERENCE
            or expiration_source.provider_record_id
            != key.underlying_key.symbol + ":" + key.expiration.isoformat()
            or expiration_source.source_symbol != key.underlying_key.symbol
            or chain_source.provider_name != "Tiger OpenAPI"
            or chain_source.origin is not _DataOrigin.PROVIDER_REFERENCE
            or chain_source.provider_record_id != self.provider_identifier
            or chain_source.source_symbol != self.provider_identifier
        ):
            raise ValueError(_IDENTIFIER_MESSAGE)
        expiration_source_id, chain_source_id, record_id = _provenance_ids(
            self.provider_identifier,
            expiration_source.retrieved_at,
            chain_source.retrieved_at,
        )
        if (
            expiration_source.source_id != expiration_source_id
            or expiration_source.observed_at != expiration_source.retrieved_at
            or chain_source.source_id != chain_source_id
            or chain_source.observed_at != chain_source.retrieved_at
            or metadata.record_id != record_id
            or metadata.effective_observed_at != chain_source.retrieved_at
        ):
            raise ValueError(_IDENTIFIER_MESSAGE)
        object.__setattr__(self, "provider_expiration_timestamp_ms", timestamp)


@_dataclass(frozen=True)
class TigerExactOptionQuoteEvidence:
    """Transient Tiger bid/ask evidence without invented session semantics."""

    contract_verification: TigerExactOptionContractVerification
    bid_premium: _decimal.Decimal
    ask_premium: _decimal.Decimal
    bid_size: _Optional[int]
    ask_size: _Optional[int]
    permission_expire_at_ms: int
    permission_received_at: _datetime.datetime
    quote_received_at: _datetime.datetime

    def __post_init__(self) -> None:
        if type(self.contract_verification) is not TigerExactOptionContractVerification:
            raise TypeError(
                "contract_verification must be a "
                "TigerExactOptionContractVerification"
            )
        if type(self.bid_premium) is not _decimal.Decimal:
            raise TypeError("bid_premium must be a Decimal")
        if type(self.ask_premium) is not _decimal.Decimal:
            raise TypeError("ask_premium must be a Decimal")
        if not self.bid_premium.is_finite() or self.bid_premium < 0:
            raise ValueError("bid_premium must be finite and nonnegative")
        if not self.ask_premium.is_finite() or self.ask_premium <= 0:
            raise ValueError("ask_premium must be finite and greater than 0")
        if self.ask_premium < self.bid_premium:
            raise ValueError("ask_premium must not be below bid_premium")
        for name in ("bid_size", "ask_size"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not int
                or value < 0
            ):
                raise ValueError(f"{name} must be a nonnegative integer or None")
        if type(self.permission_expire_at_ms) is not int:
            raise TypeError("permission_expire_at_ms must be an integer")
        permission_expiry = _permission_expiry(self.permission_expire_at_ms)
        permission_received = _normalize_utc_runtime_timestamp(
            "permission_received_at",
            self.permission_received_at,
        )
        quote_received = _normalize_utc_runtime_timestamp(
            "quote_received_at",
            self.quote_received_at,
        )
        if quote_received < permission_received:
            raise ValueError(
                "quote_received_at must not precede permission_received_at"
            )
        if (
            permission_expiry != -1
            and permission_expiry <= _unix_milliseconds(quote_received)
        ):
            raise ValueError(_PERMISSION_INACTIVE_MESSAGE)
        object.__setattr__(self, "permission_expire_at_ms", permission_expiry)
        object.__setattr__(self, "permission_received_at", permission_received)
        object.__setattr__(self, "quote_received_at", quote_received)


def _provenance_ids(
    provider_identifier: str,
    expiration_retrieved_at: _datetime.datetime,
    chain_retrieved_at: _datetime.datetime,
) -> _Tuple[str, str, str]:
    expiration_timestamp = expiration_retrieved_at.isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")
    chain_timestamp = chain_retrieved_at.isoformat(
        timespec="microseconds"
    ).replace(
        "+00:00",
        "Z",
    )
    material = (
        _TIGER_NORMALIZATION_VERSION
        + "\x00"
        + provider_identifier
        + "\x00"
        + expiration_timestamp
        + "\x00"
        + chain_timestamp
    ).encode("utf-8")
    digest = _hashlib.sha256(material).hexdigest()
    return (
        "tiger-option-expirations:" + digest,
        "tiger-option-chain:" + digest,
        "tiger-option-contract:" + digest,
    )


def _build_contract_reference(
    *,
    underlying_key: _UnderlyingKey,
    expiration: _datetime.date,
    option_type: str,
    strike: _decimal.Decimal,
    multiplier: int,
    provider_identifier: str,
    expiration_retrieved_at: _datetime.datetime,
    chain_retrieved_at: _datetime.datetime,
    normalized_at: _datetime.datetime,
) -> _OptionContractReference:
    expiration_source_id, chain_source_id, record_id = _provenance_ids(
        provider_identifier,
        expiration_retrieved_at,
        chain_retrieved_at,
    )
    expiration_source = _SourceReference(
        source_id=expiration_source_id,
        provider_name="Tiger OpenAPI",
        dataset_name="option_expirations",
        provider_record_id=(
            underlying_key.symbol + ":" + expiration.isoformat()
        ),
        provider_request_id=None,
        source_symbol=underlying_key.symbol,
        source_uri=None,
        observed_at=expiration_retrieved_at,
        retrieved_at=expiration_retrieved_at,
        provider_timezone=None,
        timestamp_methodology=(
            "Tiger supplied no observation timestamp for expiration "
            "classification; adapter receipt time is assigned."
        ),
        origin=_DataOrigin.PROVIDER_REFERENCE,
        is_delayed=False,
        declared_delay_seconds=None,
        payload_sha256=None,
        revision_number=None,
        provider_correction_id=None,
        quality_flags=(),
    )
    chain_source = _SourceReference(
        source_id=chain_source_id,
        provider_name="Tiger OpenAPI",
        dataset_name="option_chain",
        provider_record_id=provider_identifier,
        provider_request_id=None,
        source_symbol=provider_identifier,
        source_uri=None,
        observed_at=chain_retrieved_at,
        retrieved_at=chain_retrieved_at,
        provider_timezone=None,
        timestamp_methodology=(
            "Tiger supplied no observation timestamp for option contract "
            "terms; adapter receipt time is assigned."
        ),
        origin=_DataOrigin.PROVIDER_REFERENCE,
        is_delayed=False,
        declared_delay_seconds=None,
        payload_sha256=None,
        revision_number=None,
        provider_correction_id=None,
        quality_flags=(),
    )
    metadata = _NormalizationMetadata(
        record_id=record_id,
        source_references=(expiration_source, chain_source),
        effective_observed_at=chain_retrieved_at,
        normalized_at=normalized_at,
        record_origin=_DataOrigin.PROVIDER_REFERENCE,
        normalization_methodology=(
            "Exact Tiger option-chain row normalized after provider monthly "
            "classification; identifier and multiplier are provider supplied, "
            "and no provider contract-term observation timestamp was supplied."
        ),
        unit_convention=(
            "Strike is USD per underlying unit; contract multiplier is "
            "provider supplied."
        ),
        normalization_version=_TIGER_NORMALIZATION_VERSION,
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
        exercise_style=None,
        settlement_type=None,
        metadata=metadata,
    )


def verify_tiger_monthly_option_contract(
    quote_client: object,
    *,
    underlying_key: _UnderlyingKey,
    expiration: _datetime.date,
    option_type: str,
    strike: _decimal.Decimal,
) -> TigerExactOptionContractVerification:
    """Verify one caller-specified exact Tiger monthly option contract."""

    if not isinstance(underlying_key, _UnderlyingKey):
        raise TypeError("underlying_key must be an UnderlyingKey")
    expiration = _validate_expiration(expiration)
    option_type = _canonical_option_type(option_type)
    strike = _validate_strike(strike)

    try:
        get_expirations = getattr(quote_client, "get_option_expirations", None)
        get_chain = getattr(quote_client, "get_option_chain", None)
    except Exception:
        raise TypeError("quote_client must provide Tiger quote methods") from None
    if not callable(get_expirations) or not callable(get_chain):
        raise TypeError("quote_client must provide Tiger quote methods")

    try:
        expiration_table = get_expirations(
            underlying_key.symbol,
            market="US",
        )
    except Exception:
        raise RuntimeError(_EXPIRATION_RETRIEVAL_MESSAGE) from None
    expiration_retrieved_at = _utc_now()
    expiration_rows = _table_records(
        expiration_table,
        columns=_EXPIRATION_COLUMNS,
        message=_EXPIRATION_TABLE_MESSAGE,
    )
    expiration_text = expiration.isoformat()
    normalized_expirations = []
    for row in expiration_rows:
        symbol = row["symbol"]
        date_text = row["date"]
        if not isinstance(symbol, str) or not isinstance(date_text, str):
            raise ValueError(_EXPIRATION_TABLE_MESSAGE)
        normalized_expirations.append((row, symbol, date_text))
    exact_expirations = tuple(
        row
        for row in normalized_expirations
        if row[1] == underlying_key.symbol and row[2] == expiration_text
    )
    if len(exact_expirations) != 1:
        raise ValueError(_EXPIRATION_MATCH_MESSAGE)
    expiration_row = exact_expirations[0][0]
    if not isinstance(expiration_row["period_tag"], str):
        raise ValueError(_MONTHLY_MESSAGE)
    if expiration_row["period_tag"] != "m":
        raise ValueError(_MONTHLY_MESSAGE)
    expiration_timestamp = _provider_integer(
        expiration_row["timestamp"],
        _EXPIRATION_TABLE_MESSAGE,
    )

    try:
        chain_table = get_chain(
            underlying_key.symbol,
            expiration_text,
            return_greek_value=False,
            market="US",
        )
    except Exception:
        raise RuntimeError(_CHAIN_RETRIEVAL_MESSAGE) from None
    chain_retrieved_at = _utc_now()
    chain_rows = _table_records(
        chain_table,
        columns=_CHAIN_COLUMNS,
        message=_CHAIN_TABLE_MESSAGE,
    )

    normalized_rows = []
    for row in chain_rows:
        symbol = row["symbol"]
        put_call = row["put_call"]
        if not isinstance(symbol, str) or not isinstance(put_call, str):
            raise ValueError(_CHAIN_TABLE_MESSAGE)
        expiry = _provider_integer(row["expiry"], _CHAIN_TABLE_MESSAGE)
        row_strike = _provider_decimal(row["strike"])
        if put_call not in {"CALL", "PUT"}:
            raise ValueError(_CHAIN_TABLE_MESSAGE)
        normalized_rows.append(
            (row, symbol, expiry, row_strike, put_call.lower())
        )

    expected_put_call = "call" if option_type == "call" else "put"
    exact_chain_rows = tuple(
        row
        for row in normalized_rows
        if row[1] == underlying_key.symbol
        and row[2] == expiration_timestamp
        and row[3] == strike
        and row[4] == expected_put_call
    )
    if len(exact_chain_rows) != 1:
        raise ValueError(_CHAIN_MATCH_MESSAGE)

    chain_row = exact_chain_rows[0][0]
    provider_identifier = chain_row["identifier"]
    root, decoded_expiration, decoded_type, decoded_strike = (
        _decode_tiger_identifier(provider_identifier)
    )
    if (
        root != underlying_key.symbol
        or decoded_expiration != expiration
        or decoded_type != option_type
        or decoded_strike != strike
    ):
        raise ValueError(_IDENTIFIER_MESSAGE)
    multiplier = _provider_integer(
        chain_row["multiplier"],
        _MULTIPLIER_MESSAGE,
    )
    normalized_at = _utc_now()

    contract_reference = _build_contract_reference(
        underlying_key=underlying_key,
        expiration=expiration,
        option_type=option_type,
        strike=strike,
        multiplier=multiplier,
        provider_identifier=provider_identifier,
        expiration_retrieved_at=expiration_retrieved_at,
        chain_retrieved_at=chain_retrieved_at,
        normalized_at=normalized_at,
    )
    return TigerExactOptionContractVerification(
        provider_identifier=provider_identifier,
        provider_period_tag="m",
        provider_expiration_timestamp_ms=expiration_timestamp,
        contract_reference=contract_reference,
    )


def retrieve_tiger_exact_option_quote_evidence(
    quote_client: object,
    contract_verification: TigerExactOptionContractVerification,
) -> TigerExactOptionQuoteEvidence:
    """Retrieve entitled bid/ask evidence without inventing quote sessions."""

    if type(contract_verification) is not TigerExactOptionContractVerification:
        raise TypeError(
            "contract_verification must be a "
            "TigerExactOptionContractVerification"
        )
    try:
        get_permission = getattr(quote_client, "get_quote_permission", None)
    except Exception:
        raise TypeError("quote_client must provide Tiger quote methods") from None
    if not callable(get_permission):
        raise TypeError("quote_client must provide Tiger quote methods")
    try:
        permission_response = get_permission()
    except Exception:
        raise RuntimeError(_PERMISSION_RETRIEVAL_MESSAGE) from None
    permission_received_at = _utc_now()

    try:
        if not isinstance(permission_response, (list, tuple)):
            raise ValueError(_PERMISSION_RESPONSE_MESSAGE)
        permissions = []
        for entry in permission_response:
            if not isinstance(entry, _Mapping):
                raise ValueError(_PERMISSION_RESPONSE_MESSAGE)
            name = entry["name"]
            expire_at = _permission_expiry(entry["expire_at"])
            if type(name) is not str:
                raise ValueError(_PERMISSION_RESPONSE_MESSAGE)
            permissions.append((name, expire_at))
    except Exception:
        raise ValueError(_PERMISSION_RESPONSE_MESSAGE) from None

    option_permissions = tuple(
        permission for permission in permissions if permission[0] == "usOptionQuote"
    )
    if len(option_permissions) != 1:
        raise ValueError(_PERMISSION_MATCH_MESSAGE)
    permission_expire_at = option_permissions[0][1]
    if (
        permission_expire_at != -1
        and permission_expire_at <= _unix_milliseconds(permission_received_at)
    ):
        raise ValueError(_PERMISSION_INACTIVE_MESSAGE)

    try:
        get_chain = getattr(quote_client, "get_option_chain", None)
    except Exception:
        raise TypeError("quote_client must provide Tiger quote methods") from None
    if not callable(get_chain):
        raise TypeError("quote_client must provide Tiger quote methods")
    key = contract_verification.contract_reference.contract_key
    try:
        chain_table = get_chain(
            key.underlying_key.symbol,
            key.expiration.isoformat(),
            return_greek_value=False,
            market="US",
        )
    except Exception:
        raise RuntimeError(_CHAIN_RETRIEVAL_MESSAGE) from None
    quote_received_at = _utc_now()
    chain_rows = _table_records(
        chain_table,
        columns=_QUOTE_COLUMNS,
        message=_QUOTE_RESPONSE_MESSAGE,
    )
    exact_rows = []
    for row in chain_rows:
        identifier = row["identifier"]
        symbol = row["symbol"]
        put_call = row["put_call"]
        if not all(type(value) is str for value in (identifier, symbol, put_call)):
            raise ValueError(_QUOTE_RESPONSE_MESSAGE)
        expiry = _provider_integer(row["expiry"], _QUOTE_RESPONSE_MESSAGE)
        strike = _provider_decimal(row["strike"])
        multiplier = _provider_integer(row["multiplier"], _QUOTE_RESPONSE_MESSAGE)
        if put_call not in {"CALL", "PUT"}:
            raise ValueError(_QUOTE_RESPONSE_MESSAGE)
        if (
            identifier == contract_verification.provider_identifier
            and symbol == key.underlying_key.symbol
            and expiry == contract_verification.provider_expiration_timestamp_ms
            and strike == key.strike
            and put_call.lower() == key.option_type
            and multiplier == key.contract_multiplier
        ):
            exact_rows.append(row)
    if len(exact_rows) != 1:
        raise ValueError(_QUOTE_MATCH_MESSAGE)

    exact_row = exact_rows[0]
    bid = _provider_quote_decimal(exact_row["bid_price"], allow_zero=True)
    ask = _provider_quote_decimal(exact_row["ask_price"], allow_zero=False)
    if ask < bid:
        raise ValueError(_QUOTE_RESPONSE_MESSAGE)
    bid_size = _provider_optional_size(exact_row["bid_size"])
    ask_size = _provider_optional_size(exact_row["ask_size"])
    if (
        permission_expire_at != -1
        and permission_expire_at <= _unix_milliseconds(quote_received_at)
    ):
        raise ValueError(_PERMISSION_INACTIVE_MESSAGE)
    return TigerExactOptionQuoteEvidence(
        contract_verification=contract_verification,
        bid_premium=bid,
        ask_premium=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        permission_expire_at_ms=permission_expire_at,
        permission_received_at=permission_received_at,
        quote_received_at=quote_received_at,
    )


def retrieve_tiger_underlying_daily_bars(
    quote_client: object,
    *,
    underlying_key: _UnderlyingKey,
    begin_date: _datetime.date,
    end_date: _datetime.date,
    latest_completed_session_date: _datetime.date,
) -> _Tuple[_UnderlyingDailyBarObservation, ...]:
    """Retrieve paired Tiger NR/BR daily bars for completed US sessions."""

    if type(underlying_key) is not _UnderlyingKey:
        raise TypeError("underlying_key must be an UnderlyingKey")
    begin_date = _validate_expiration(begin_date)
    end_date = _validate_expiration(end_date)
    latest_completed_session_date = _validate_expiration(
        latest_completed_session_date
    )
    if begin_date >= end_date:
        raise ValueError("begin_date must precede end_date")
    if (end_date - begin_date).days > 370:
        raise ValueError("daily-bar range must not exceed 370 calendar days")
    if end_date > latest_completed_session_date + _datetime.timedelta(days=1):
        raise ValueError("end_date must not include an incomplete session")
    try:
        get_bars = getattr(quote_client, "get_bars_by_page", None)
    except Exception:
        raise TypeError("quote_client must provide Tiger quote methods") from None
    if not callable(get_bars):
        raise TypeError("quote_client must provide Tiger quote methods")

    common = {
        "symbol": underlying_key.symbol,
        "period": "day",
        "begin_time": begin_date.isoformat(),
        "end_time": end_date.isoformat(),
        "total": 1000,
        "page_size": 1000,
        "time_interval": 0,
        "trade_session": None,
        "with_fundamental": False,
        "sec_type": None,
    }

    def normalize(rows: tuple) -> dict:
        normalized = {}
        timestamps = set()
        for row in rows:
            if type(row["symbol"]) is not str or row["symbol"] != underlying_key.symbol:
                raise ValueError(_BAR_RESPONSE_MESSAGE)
            timestamp, observed_at = _provider_bar_datetime(row["time"])
            session_date = observed_at.astimezone(_US_EASTERN).date()
            if (
                session_date < begin_date
                or session_date >= end_date
                or session_date > latest_completed_session_date
                or session_date in normalized
                or timestamp in timestamps
            ):
                raise ValueError(_BAR_RESPONSE_MESSAGE)
            prices = _bar_ohlc(row)
            volume = _bar_volume(row["volume"])
            normalized[session_date] = (
                timestamp,
                observed_at,
                prices,
                volume,
            )
            timestamps.add(timestamp)
        return normalized

    try:
        nr_table = get_bars(right="nr", **common)
    except Exception:
        raise RuntimeError(_BAR_RETRIEVAL_MESSAGE) from None
    nr_retrieved_at = _utc_now()
    nr_rows = _table_records(
        nr_table,
        columns=_BAR_COLUMNS,
        message=_BAR_RESPONSE_MESSAGE,
    )
    nr = normalize(nr_rows)
    if not nr:
        raise ValueError(_BAR_RESPONSE_MESSAGE)

    try:
        br_table = get_bars(right="br", **common)
    except Exception:
        raise RuntimeError(_BAR_RETRIEVAL_MESSAGE) from None
    br_retrieved_at = _utc_now()
    br_rows = _table_records(
        br_table,
        columns=_BAR_COLUMNS,
        message=_BAR_RESPONSE_MESSAGE,
    )
    br = normalize(br_rows)
    if not br or set(nr) != set(br):
        raise ValueError(_BAR_PAIRING_MESSAGE)
    if any(nr[date][0] != br[date][0] for date in nr):
        raise ValueError(_BAR_PAIRING_MESSAGE)
    normalized_at = _utc_now()

    observations = []
    for session_date in sorted(nr):
        timestamp, observed_at, nr_prices, volume = nr[session_date]
        _, _, br_prices, _ = br[session_date]
        material = (
            _TIGER_DAILY_BAR_NORMALIZATION_VERSION
            + "\x00"
            + underlying_key.symbol
            + "\x00"
            + str(timestamp)
            + "\x00"
            + nr_retrieved_at.isoformat()
            + "\x00"
            + br_retrieved_at.isoformat()
        ).encode("utf-8")
        digest = _hashlib.sha256(material).hexdigest()
        sources = (
            _SourceReference(
                source_id="tiger-underlying-bars-nr:" + digest,
                provider_name="Tiger OpenAPI",
                dataset_name="underlying_daily_bars_nr",
                provider_record_id=(underlying_key.symbol + ":" + str(timestamp) + ":nr"),
                provider_request_id=None,
                source_symbol=underlying_key.symbol,
                source_uri=None,
                observed_at=observed_at,
                retrieved_at=nr_retrieved_at,
                provider_timezone="America/New_York",
                timestamp_methodology=(
                    "Tiger daily-bar millisecond session marker; not asserted "
                    "to be the exchange close time."
                ),
                origin=_DataOrigin.EXCHANGE_OBSERVED,
                is_delayed=False,
                declared_delay_seconds=None,
                payload_sha256=None,
                revision_number=None,
                provider_correction_id=None,
                quality_flags=(),
            ),
            _SourceReference(
                source_id="tiger-underlying-bars-br:" + digest,
                provider_name="Tiger OpenAPI",
                dataset_name="underlying_daily_bars_br",
                provider_record_id=(underlying_key.symbol + ":" + str(timestamp) + ":br"),
                provider_request_id=None,
                source_symbol=underlying_key.symbol,
                source_uri=None,
                observed_at=observed_at,
                retrieved_at=br_retrieved_at,
                provider_timezone="America/New_York",
                timestamp_methodology=(
                    "Tiger daily-bar millisecond session marker; not asserted "
                    "to be the exchange close time."
                ),
                origin=_DataOrigin.PROVIDER_CALCULATED,
                is_delayed=False,
                declared_delay_seconds=None,
                payload_sha256=None,
                revision_number=None,
                provider_correction_id=None,
                quality_flags=(),
            ),
        )
        metadata = _NormalizationMetadata(
            record_id="tiger-underlying-daily-bar:" + digest,
            source_references=sources,
            effective_observed_at=observed_at,
            normalized_at=normalized_at,
            record_origin=_DataOrigin.SYSTEM_COMPOSITE,
            normalization_methodology=(
                "Tiger NR supplied unadjusted OHLC and volume; Tiger BR "
                "supplied the forward-adjusted close for the exact session."
            ),
            unit_convention="USD per share prices; volume in shares.",
            normalization_version=_TIGER_DAILY_BAR_NORMALIZATION_VERSION,
            quality_flags=(_NormalizationQualityFlag.COMPOSITE_SOURCE,),
        )
        observations.append(
            _UnderlyingDailyBarObservation(
                underlying_key=underlying_key,
                session_date=session_date,
                open_price=nr_prices[0],
                high_price=nr_prices[1],
                low_price=nr_prices[2],
                close_price=nr_prices[3],
                adjusted_close_price=br_prices[3],
                volume=volume,
                is_session_complete=True,
                adjustment_methodology=(
                    "Tiger QuoteRight.BR forward-adjusted close paired with "
                    "Tiger QuoteRight.NR unadjusted OHLC and volume."
                ),
                metadata=metadata,
            )
        )
    return tuple(observations)


def _parse_dividend_date(
    name: str,
    value: object,
    *,
    optional: bool,
) -> _Optional[_datetime.date]:
    if value is None:
        if optional:
            return None
        raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
    if type(value) is not str:
        raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
    try:
        parsed = _datetime.date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(_DIVIDEND_RESPONSE_MESSAGE) from None
    if parsed.isoformat() != value:
        raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
    return parsed


def _validate_dividend_date(
    name: str,
    value: object,
    *,
    optional: bool,
) -> _Optional[_datetime.date]:
    if value is None:
        if optional:
            return None
        raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
    if type(value) is not _datetime.date:
        raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
    return value


def _dividend_amount(value: object) -> _decimal.Decimal:
    if isinstance(value, bool):
        raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
    try:
        normalized = _decimal.Decimal(str(value))
    except Exception:
        raise ValueError(_DIVIDEND_RESPONSE_MESSAGE) from None
    if not normalized.is_finite() or normalized < 0:
        raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
    return normalized


def _dividend_table_records(table: object) -> tuple:
    if table is None:
        return ()
    try:
        to_dict = getattr(table, "to_dict", None)
        if not callable(to_dict):
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        records = to_dict("records")
        if not isinstance(records, (list, tuple)):
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        if not records:
            return ()
        copied = []
        for record in records:
            if not isinstance(record, _Mapping):
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            if set(record.keys()) != _DIVIDEND_COLUMN_SET:
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            copied.append(tuple(record[name] for name in _DIVIDEND_COLUMNS))
        return tuple(copied)
    except Exception:
        raise ValueError(_DIVIDEND_RESPONSE_MESSAGE) from None


def _dividend_sort_date(
    value: _Optional[_datetime.date],
) -> _Tuple[int, _datetime.date]:
    if value is None:
        return (0, _datetime.date.min)
    return (1, value)


@_dataclass(frozen=True)
class TigerHistoricalDividendEvidence:
    """Immutable Tiger-native evidence for one historical dividend row."""

    underlying_key: _UnderlyingKey
    action_type: str
    provider_amount: _decimal.Decimal
    currency: str
    announced_date: _Optional[_datetime.date]
    execute_date: _datetime.date
    record_date: _Optional[_datetime.date]
    pay_date: _Optional[_datetime.date]
    market: str
    exchange: str
    retrieved_at: _datetime.datetime

    def __post_init__(self) -> None:
        if type(self.underlying_key) is not _UnderlyingKey:
            raise TypeError("underlying_key must be an UnderlyingKey")
        if type(self.action_type) is not str or self.action_type != "DIVIDEND":
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        if type(self.provider_amount) is not _decimal.Decimal:
            raise TypeError("provider_amount must be a Decimal")
        if not self.provider_amount.is_finite() or self.provider_amount < 0:
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        if type(self.currency) is not str:
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        if self.currency != self.underlying_key.currency:
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        announced_date = _validate_dividend_date(
            "announced_date", self.announced_date, optional=True
        )
        execute_date = _validate_dividend_date(
            "execute_date", self.execute_date, optional=False
        )
        record_date = _validate_dividend_date(
            "record_date", self.record_date, optional=True
        )
        pay_date = _validate_dividend_date(
            "pay_date", self.pay_date, optional=True
        )
        if type(self.market) is not str or self.market != "US":
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        if type(self.exchange) is not str or not self.exchange.strip():
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        if announced_date is not None and announced_date > execute_date:
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        if record_date is not None and record_date < execute_date:
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        if pay_date is not None and pay_date < execute_date:
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
        retrieved_at = _normalize_utc_runtime_timestamp(
            "retrieved_at", self.retrieved_at
        )
        object.__setattr__(self, "announced_date", announced_date)
        object.__setattr__(self, "execute_date", execute_date)
        object.__setattr__(self, "record_date", record_date)
        object.__setattr__(self, "pay_date", pay_date)
        object.__setattr__(self, "retrieved_at", retrieved_at)


def retrieve_tiger_historical_dividend_evidence(
    quote_client: object,
    *,
    underlying_key: _UnderlyingKey,
    begin_date: _datetime.date,
    end_date: _datetime.date,
    latest_completed_date: _datetime.date,
) -> _Tuple[TigerHistoricalDividendEvidence, ...]:
    """Retrieve one bounded, provider-native Tiger dividend response."""

    if type(underlying_key) is not _UnderlyingKey:
        raise TypeError("underlying_key must be an UnderlyingKey")
    for name, value in (
        ("begin_date", begin_date),
        ("end_date", end_date),
        ("latest_completed_date", latest_completed_date),
    ):
        if type(value) is not _datetime.date:
            raise TypeError(f"{name} must be a date without a time component")
    if begin_date > end_date:
        raise ValueError("begin_date must not follow end_date")
    if (end_date - begin_date).days > 370:
        raise ValueError("dividend range must not exceed 370 calendar days")
    if end_date > latest_completed_date:
        raise ValueError(
            "end_date must not follow latest_completed_date"
        )

    try:
        get_dividend = getattr(quote_client, "get_corporate_dividend", None)
    except Exception:
        raise TypeError("quote_client must provide Tiger quote methods") from None
    if not callable(get_dividend):
        raise TypeError("quote_client must provide Tiger quote methods")

    try:
        table = get_dividend(
            [underlying_key.symbol],
            "US",
            begin_date.isoformat(),
            end_date.isoformat(),
            timezone="US/Eastern",
        )
    except Exception:
        raise RuntimeError(_DIVIDEND_RETRIEVAL_MESSAGE) from None
    retrieved_at = _normalize_utc_runtime_timestamp("retrieved_at", _utc_now())
    rows = _dividend_table_records(table)
    if not rows:
        return ()

    evidence = []
    for row in rows:
        try:
            (
                symbol,
                action_type,
                amount,
                currency,
                announced_date,
                execute_date,
                record_date,
                pay_date,
                market,
                exchange,
            ) = row
            if type(symbol) is not str or symbol != underlying_key.symbol:
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            if type(action_type) is not str or action_type != "DIVIDEND":
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            if type(currency) is not str or currency != underlying_key.currency:
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            if type(market) is not str or market != "US":
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            if type(exchange) is not str or not exchange.strip():
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            normalized_announced = _parse_dividend_date(
                "announced_date", announced_date, optional=True
            )
            normalized_execute = _parse_dividend_date(
                "execute_date", execute_date, optional=False
            )
            normalized_record = _parse_dividend_date(
                "record_date", record_date, optional=True
            )
            normalized_pay = _parse_dividend_date(
                "pay_date", pay_date, optional=True
            )
            if (
                normalized_execute < begin_date
                or normalized_execute > end_date
                or normalized_execute > latest_completed_date
            ):
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            if (
                normalized_announced is not None
                and normalized_announced > normalized_execute
            ):
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            if (
                normalized_record is not None
                and normalized_record < normalized_execute
            ):
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            if normalized_pay is not None and normalized_pay < normalized_execute:
                raise ValueError(_DIVIDEND_RESPONSE_MESSAGE)
            evidence.append(
                TigerHistoricalDividendEvidence(
                    underlying_key=underlying_key,
                    action_type=action_type,
                    provider_amount=_dividend_amount(amount),
                    currency=currency,
                    announced_date=normalized_announced,
                    execute_date=normalized_execute,
                    record_date=normalized_record,
                    pay_date=normalized_pay,
                    market=market,
                    exchange=exchange,
                    retrieved_at=retrieved_at,
                )
            )
        except Exception:
            raise ValueError(_DIVIDEND_RESPONSE_MESSAGE) from None

    seen = set()
    for item in evidence:
        duplicate_key = (
            item.underlying_key.symbol,
            item.action_type,
            item.provider_amount.as_tuple(),
            item.currency,
            item.announced_date,
            item.execute_date,
            item.record_date,
            item.pay_date,
            item.market,
            item.exchange,
        )
        if duplicate_key in seen:
            raise ValueError(_DIVIDEND_DUPLICATE_MESSAGE)
        seen.add(duplicate_key)

    return tuple(
        sorted(
            evidence,
            key=lambda item: (
                item.execute_date,
                _dividend_sort_date(item.announced_date),
                _dividend_sort_date(item.record_date),
                _dividend_sort_date(item.pay_date),
                item.action_type,
                item.provider_amount,
                item.provider_amount.as_tuple(),
                item.currency,
                item.market,
                item.exchange,
            ),
        )
    )
