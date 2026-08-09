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
    UnderlyingKey as _UnderlyingKey,
)


__all__ = (
    "resolve_tiger_config_path",
    "initialize_tiger_quote_client",
    "TigerExactOptionContractVerification",
    "verify_tiger_monthly_option_contract",
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

_EXPIRATION_COLUMNS = frozenset(("symbol", "date", "timestamp", "period_tag"))
_CHAIN_COLUMNS = frozenset(
    ("identifier", "symbol", "expiry", "strike", "put_call", "multiplier")
)
_TIGER_NORMALIZATION_VERSION = "tiger-option-contract-v0.1"


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
    if isinstance(value, bool) or not isinstance(value, _numbers.Integral):
        raise ValueError(message)
    normalized = int(value)
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
    if not isinstance(identifier, str) or identifier != identifier.strip():
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
