"""Provider-neutral provenance and identity foundations for market data."""

import datetime
import decimal
import json
import re
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
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
    "MarketDataCategory",
    "MarketDataFreshnessPolicy",
    "FreshnessContext",
    "FreshnessStatus",
    "FreshnessReasonCode",
    "FreshnessAssessment",
    "assess_market_data_freshness",
    "CorrectionSelectionStatus",
    "CorrectionSelectionReasonCode",
    "CorrectionSelection",
    "select_correction_candidate",
    "CalculationQualityFlag",
    "CalculationInputReference",
    "CalculationLineage",
    "canonicalize_lineage_parameters",
    "semantic_observation_key",
    "SelectedFreshMarketDataBinding",
    "bind_selected_fresh_market_data",
    "MarketDataSnapshotTimingReasonCode",
    "MarketDataSnapshotTimingAssessment",
    "assess_market_data_snapshot_timing",
    "MarketDataBindingReference",
    "market_data_binding_reference",
    "resolve_market_data_binding_reference",
    "MarketDataRelationshipGroupKind",
    "MarketDataRelationshipRole",
    "MarketDataRelationshipGroupMember",
    "MarketDataRelationshipGroup",
    "MarketDataRelationshipRequest",
    "MarketDataRelationshipIssueCode",
    "MarketDataRelationshipGroupAssessment",
    "MarketDataRelationshipAssessment",
    "assess_market_data_relationships",
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


def _timedelta_to_decimal_seconds(
    value: datetime.timedelta,
) -> decimal.Decimal:
    """Construct exact Decimal seconds using only integer arithmetic."""

    total_microseconds = (
        ((value.days * 86400) + value.seconds) * 1000000
        + value.microseconds
    )
    sign = 1 if total_microseconds < 0 else 0
    digits = tuple(int(digit) for digit in str(abs(total_microseconds)))
    return decimal.Decimal((sign, digits, -6))


_LINEAGE_DATETIME_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z$"
)


def _validate_no_surrogates(name: str, value: str) -> None:
    """Reject strings that cannot be encoded as strict UTF-8."""

    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError(f"{name} must not contain Unicode surrogates")


def _normalize_exact_utc_datetime(
    name: str, value: object
) -> datetime.datetime:
    """Normalize an exact aware datetime and hide representation overflow."""

    if type(value) is not datetime.datetime:
        raise TypeError(f"{name} must have exact type datetime")
    try:
        offset = value.utcoffset()
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{name} has an invalid timezone offset") from error
    if value.tzinfo is None or offset is None:
        raise ValueError(f"{name} must be timezone-aware")
    try:
        return value.astimezone(datetime.timezone.utc)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"{name} cannot be represented in UTC") from error


def _canonical_datetime_string(value: datetime.datetime) -> str:
    """Serialize one already-normalized UTC datetime canonically."""

    return value.isoformat(timespec="microseconds")[:-6] + "Z"


def _canonical_decimal_string(value: decimal.Decimal) -> str:
    """Serialize one finite Decimal without ambient-context operations."""

    if not value.is_finite():
        raise ValueError("Decimal parameter must be finite")
    normalized = value.copy_abs() if value.is_zero() else value
    return str(normalized)


def _validate_lineage_key(key: object) -> str:
    """Validate one exact, untrimmed canonical mapping key."""

    if type(key) is not str:
        raise TypeError("lineage parameter keys must have exact type str")
    _validate_no_surrogates("lineage parameter key", key)
    if not key or key != key.strip():
        raise ValueError(
            "lineage parameter keys must be non-empty without surrounding whitespace"
        )
    return key


def _canonicalize_lineage_mapping(
    value: dict, depth: int, active_path: set
) -> dict:
    """Convert an exact Python dictionary to a canonical tagged mapping."""

    if depth > 32:
        raise ValueError("lineage parameter container depth must not exceed 32")
    identity = id(value)
    if identity in active_path:
        raise ValueError("lineage parameters must not contain cycles")
    active_path.add(identity)
    try:
        keys = tuple(_validate_lineage_key(key) for key in value.keys())
        entries = []
        for key in sorted(keys):
            entries.append([
                key,
                _canonicalize_lineage_value(value[key], depth, active_path),
            ])
        return {"$map": entries}
    finally:
        active_path.remove(identity)


def _canonicalize_lineage_list(
    value: object, depth: int, active_path: set
) -> dict:
    """Convert one exact list or tuple to a canonical tagged list."""

    if depth > 32:
        raise ValueError("lineage parameter container depth must not exceed 32")
    identity = id(value)
    if identity in active_path:
        raise ValueError("lineage parameters must not contain cycles")
    active_path.add(identity)
    try:
        return {
            "$list": [
                _canonicalize_lineage_value(item, depth, active_path)
                for item in value  # type: ignore[union-attr]
            ]
        }
    finally:
        active_path.remove(identity)


def _canonicalize_lineage_value(
    value: object, container_depth: int, active_path: set
) -> object:
    """Convert one exact supported Python value to the tagged grammar."""

    value_type = type(value)
    if value is None:
        return None
    if value_type is bool or value_type is int:
        return value
    if value_type is str:
        _validate_no_surrogates("lineage string parameter", value)
        return value
    if value_type is decimal.Decimal:
        return {"$decimal": _canonical_decimal_string(value)}
    if value_type is datetime.datetime:
        normalized = _normalize_exact_utc_datetime(
            "lineage datetime parameter", value
        )
        return {"$datetime": _canonical_datetime_string(normalized)}
    if value_type is datetime.date:
        return {"$date": value.isoformat()}
    if value_type is list or value_type is tuple:
        return _canonicalize_lineage_list(
            value, container_depth + 1, active_path
        )
    if value_type is dict:
        return _canonicalize_lineage_mapping(
            value, container_depth + 1, active_path
        )
    raise TypeError(
        f"unsupported lineage parameter type: {value_type.__name__}"
    )


def _serialize_lineage_tree(value: object) -> str:
    """Serialize a validated tagged tree using canonical JSON settings."""

    serialized = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    serialized.encode("utf-8")
    return serialized


def canonicalize_lineage_parameters(parameters: object) -> str:
    """Return deterministic canonical tagged JSON for exact Python inputs."""

    if type(parameters) is not dict:
        raise TypeError("parameters must have exact built-in type dict")
    tree = _canonicalize_lineage_mapping(parameters, 1, set())
    return _serialize_lineage_tree(tree)


def _reject_lineage_json_float(value: str) -> object:
    """Reject JSON floating-point and non-standard numeric constants."""

    raise ValueError(f"lineage parameters JSON does not allow float {value}")


def _lineage_object_from_pairs(pairs: object) -> dict:
    """Construct one JSON object while detecting duplicate object keys."""

    result = {}
    for key, value in pairs:  # type: ignore[union-attr]
        if key in result:
            raise ValueError("lineage parameters JSON has duplicate object keys")
        result[key] = value
    return result


def _parse_lineage_json(value: str) -> object:
    """Parse JSON with duplicate and floating-point rejection."""

    try:
        return json.loads(
            value,
            object_pairs_hook=_lineage_object_from_pairs,
            parse_float=_reject_lineage_json_float,
            parse_constant=_reject_lineage_json_float,
        )
    except json.JSONDecodeError as error:
        raise ValueError("parameters_json must contain valid JSON") from None
    except RecursionError as error:
        raise ValueError("parameters_json exceeds supported depth") from error


def _require_tag_payload_string(tag: str, payload: object) -> str:
    """Require one surrogate-free exact string tag payload."""

    if type(payload) is not str:
        raise ValueError(f"{tag} payload must be a JSON string")
    _validate_no_surrogates(f"{tag} payload", payload)
    return payload


def _validate_lineage_decimal_payload(payload: object) -> None:
    """Require one canonical finite Decimal string."""

    text = _require_tag_payload_string("$decimal", payload)
    try:
        value = decimal.Decimal(text)
    except (decimal.InvalidOperation, ValueError):
        raise ValueError("$decimal payload must parse as Decimal") from None
    if _canonical_decimal_string(value) != text:
        raise ValueError("$decimal payload is not canonical")


def _validate_lineage_date_payload(payload: object) -> None:
    """Require one byte-canonical ISO calendar date."""

    text = _require_tag_payload_string("$date", payload)
    try:
        value = datetime.date.fromisoformat(text)
    except ValueError:
        raise ValueError("$date payload must be an ISO date") from None
    if value.isoformat() != text:
        raise ValueError("$date payload is not canonical")


def _validate_lineage_datetime_payload(payload: object) -> None:
    """Require one byte-canonical six-digit UTC datetime."""

    text = _require_tag_payload_string("$datetime", payload)
    if _LINEAGE_DATETIME_PATTERN.fullmatch(text) is None:
        raise ValueError("$datetime payload is not canonical")
    try:
        value = datetime.datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        raise ValueError("$datetime payload is invalid") from None
    if _canonical_datetime_string(value) != text:
        raise ValueError("$datetime payload is not canonical")


def _validate_lineage_json_map(payload: object, depth: int) -> None:
    """Validate one $map payload at its exact container depth."""

    if depth > 32:
        raise ValueError("lineage parameter container depth must not exceed 32")
    if type(payload) is not list:
        raise ValueError("$map payload must be a JSON array")
    seen = set()
    previous = None
    for entry in payload:
        if type(entry) is not list or len(entry) != 2:
            raise ValueError("every $map entry must be a two-element JSON array")
        key = entry[0]
        if type(key) is not str:
            raise ValueError("every $map key must be a JSON string")
        _validate_no_surrogates("$map key", key)
        if not key or key != key.strip():
            raise ValueError(
                "$map keys must be non-empty without surrounding whitespace"
            )
        if key in seen:
            raise ValueError("$map user keys must not contain duplicates")
        if previous is not None and key <= previous:
            raise ValueError("$map keys must be in strictly increasing order")
        seen.add(key)
        previous = key
        _validate_lineage_json_value(entry[1], depth)


def _validate_lineage_json_list(payload: object, depth: int) -> None:
    """Validate one $list payload at its exact container depth."""

    if depth > 32:
        raise ValueError("lineage parameter container depth must not exceed 32")
    if type(payload) is not list:
        raise ValueError("$list payload must be a JSON array")
    for item in payload:
        _validate_lineage_json_value(item, depth)


def _validate_lineage_json_value(value: object, container_depth: int) -> None:
    """Validate one recursive value in an already-parsed tagged tree."""

    value_type = type(value)
    if value is None or value_type is bool or value_type is int:
        return
    if value_type is str:
        _validate_no_surrogates("lineage JSON string", value)
        return
    if value_type is not dict:
        raise ValueError("lineage JSON values must follow the tagged grammar")
    if len(value) != 1:
        raise ValueError("tagged JSON objects must contain exactly one key")
    tag, payload = next(iter(value.items()))
    _validate_no_surrogates("lineage JSON tag", tag)
    if tag == "$map":
        _validate_lineage_json_map(payload, container_depth + 1)
    elif tag == "$list":
        _validate_lineage_json_list(payload, container_depth + 1)
    elif tag == "$decimal":
        _validate_lineage_decimal_payload(payload)
    elif tag == "$date":
        _validate_lineage_date_payload(payload)
    elif tag == "$datetime":
        _validate_lineage_datetime_payload(payload)
    else:
        raise ValueError(f"unknown lineage JSON tag: {tag}")


def _validate_canonical_lineage_json(value: str) -> None:
    """Validate complete canonical parameters JSON without normalizing it."""

    tree = _parse_lineage_json(value)
    if type(tree) is not dict or tuple(tree.keys()) != ("$map",):
        raise ValueError("parameters_json root must be exactly one $map object")
    _validate_lineage_json_map(tree["$map"], 1)
    if _serialize_lineage_tree(tree) != value:
        raise ValueError("parameters_json must be byte-identical canonical JSON")


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


class MarketDataCategory(str, Enum):
    """Fixed freshness category for one supported normalized record type."""

    QUOTE = "quote"
    ANALYTICS = "analytics"
    ACTIVITY = "activity"
    CONTRACT_REFERENCE = "contract_reference"
    HISTORICAL_BAR = "historical_bar"
    RATE = "rate"
    DIVIDEND = "dividend"


class FreshnessStatus(str, Enum):
    """Deterministic current-eligibility status for normalized market data."""

    FRESH = "fresh"
    STALE = "stale"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


class FreshnessReasonCode(str, Enum):
    """Canonical reasons produced by single-record freshness assessment."""

    RECORD_NORMALIZED_AFTER_EVALUATION = "record_normalized_after_evaluation"
    SOURCE_RETRIEVED_AFTER_EVALUATION = "source_retrieved_after_evaluation"
    SOURCE_OBSERVED_AFTER_EVALUATION = "source_observed_after_evaluation"
    NORMALIZATION_INCOMPLETE = "normalization_incomplete"
    ASSIGNED_TIMESTAMP_NOT_ALLOWED = "assigned_timestamp_not_allowed"
    DELAYED_DATA_NOT_ALLOWED = "delayed_data_not_allowed"
    INDICATIVE_DATA_NOT_ALLOWED = "indicative_data_not_allowed"
    NON_FIRM_DATA_NOT_ALLOWED = "non_firm_data_not_allowed"
    PARTIAL_DATA_NOT_ALLOWED = "partial_data_not_allowed"
    HALTED_SOURCE = "halted_source"
    SOURCE_OBSERVATION_SPAN_EXCEEDED = "source_observation_span_exceeded"
    NON_REGULAR_SESSION_QUOTE = "non_regular_session_quote"
    HISTORICAL_SESSION_INCOMPLETE = "historical_session_incomplete"
    SESSION_DATE_AFTER_LATEST_COMPLETED_SESSION = (
        "session_date_after_latest_completed_session"
    )
    UNKNOWN_MARKET_PHASE = "unknown_market_phase"
    UNKNOWN_QUOTE_SCOPE = "unknown_quote_scope"
    EFFECTIVE_AGE_EXCEEDED = "effective_age_exceeded"
    OLDEST_SOURCE_AGE_EXCEEDED = "oldest_source_age_exceeded"
    RETRIEVAL_LAG_EXCEEDED = "retrieval_lag_exceeded"
    OPEN_INTEREST_SESSION_DATE_GAP_EXCEEDED = (
        "open_interest_session_date_gap_exceeded"
    )
    HISTORICAL_BAR_SESSION_DATE_GAP_EXCEEDED = (
        "historical_bar_session_date_gap_exceeded"
    )
    FRESH_WITHIN_POLICY = "fresh_within_policy"


class MarketDataSnapshotTimingReasonCode(str, Enum):
    """Canonical reasons produced by binding-set temporal assessment."""

    MIXED_FRESHNESS_POLICY = "mixed_freshness_policy"
    MIXED_FRESHNESS_CONTEXT = "mixed_freshness_context"
    EFFECTIVE_TIME_SPAN_EXCEEDED = "effective_time_span_exceeded"
    SOURCE_OBSERVATION_SPAN_EXCEEDED = (
        "source_observation_span_exceeded"
    )


class CorrectionSelectionStatus(str, Enum):
    """Terminal status for deterministic provider-correction selection."""

    SELECTED = "selected"
    AMBIGUOUS = "ambiguous"


class CorrectionSelectionReasonCode(str, Enum):
    """One terminal reason from deterministic correction selection."""

    MISSING_PROVIDER_RECORD_ID = "missing_provider_record_id"
    SOURCE_LINEAGE_MISMATCH = "source_lineage_mismatch"
    CONFLICTING_CORRECTION_IDS_SAME_REVISION = (
        "conflicting_correction_ids_same_revision"
    )
    TIED_REVISION_VECTORS = "tied_revision_vectors"
    INCOMPARABLE_REVISION_VECTORS = "incomparable_revision_vectors"
    ONLY_CANDIDATE_SELECTED = "only_candidate_selected"
    DOMINATING_REVISION_VECTOR_SELECTED = (
        "dominating_revision_vector_selected"
    )


class CalculationQualityFlag(str, Enum):
    """Canonical conditions disclosed for one deterministic calculation."""

    DECIMAL_TO_FLOAT_CONVERTED = "decimal_to_float_converted"
    INTERPOLATED = "interpolated"
    ANNUALIZED = "annualized"
    ADJUSTED_INPUT_USED = "adjusted_input_used"
    CORRECTION_SELECTED = "correction_selected"
    COMPOSITE_INPUT_USED = "composite_input_used"
    ASSUMPTION_APPLIED = "assumption_applied"
    INCOMPLETE_INPUT_USED = "incomplete_input_used"


_INELIGIBLE_FRESHNESS_REASONS = frozenset(tuple(FreshnessReasonCode)[:14])
_UNKNOWN_FRESHNESS_REASONS = frozenset(tuple(FreshnessReasonCode)[14:16])
_STALE_FRESHNESS_REASONS = frozenset(tuple(FreshnessReasonCode)[16:21])

_FRESHNESS_REASON_CATEGORIES = {
    FreshnessReasonCode.NON_REGULAR_SESSION_QUOTE: frozenset({
        MarketDataCategory.QUOTE,
    }),
    FreshnessReasonCode.UNKNOWN_MARKET_PHASE: frozenset({
        MarketDataCategory.QUOTE,
    }),
    FreshnessReasonCode.UNKNOWN_QUOTE_SCOPE: frozenset({
        MarketDataCategory.QUOTE,
    }),
    FreshnessReasonCode.HALTED_SOURCE: frozenset({
        MarketDataCategory.QUOTE,
        MarketDataCategory.ANALYTICS,
    }),
    FreshnessReasonCode.HISTORICAL_SESSION_INCOMPLETE: frozenset({
        MarketDataCategory.HISTORICAL_BAR,
    }),
    FreshnessReasonCode.OPEN_INTEREST_SESSION_DATE_GAP_EXCEEDED: frozenset({
        MarketDataCategory.ACTIVITY,
    }),
    FreshnessReasonCode.HISTORICAL_BAR_SESSION_DATE_GAP_EXCEEDED: frozenset({
        MarketDataCategory.HISTORICAL_BAR,
    }),
    FreshnessReasonCode.SESSION_DATE_AFTER_LATEST_COMPLETED_SESSION: frozenset({
        MarketDataCategory.ACTIVITY,
        MarketDataCategory.HISTORICAL_BAR,
    }),
    FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED: frozenset({
        MarketDataCategory.QUOTE,
        MarketDataCategory.ANALYTICS,
        MarketDataCategory.ACTIVITY,
        MarketDataCategory.CONTRACT_REFERENCE,
        MarketDataCategory.RATE,
        MarketDataCategory.DIVIDEND,
    }),
    FreshnessReasonCode.OLDEST_SOURCE_AGE_EXCEEDED: frozenset({
        MarketDataCategory.QUOTE,
        MarketDataCategory.ANALYTICS,
        MarketDataCategory.ACTIVITY,
        MarketDataCategory.CONTRACT_REFERENCE,
        MarketDataCategory.RATE,
        MarketDataCategory.DIVIDEND,
    }),
}

_NO_SESSION_DATE_GAP_CATEGORIES = frozenset({
    MarketDataCategory.QUOTE,
    MarketDataCategory.ANALYTICS,
    MarketDataCategory.CONTRACT_REFERENCE,
    MarketDataCategory.RATE,
    MarketDataCategory.DIVIDEND,
})

_FUTURE_CHRONOLOGY_REASONS = frozenset({
    FreshnessReasonCode.RECORD_NORMALIZED_AFTER_EVALUATION,
    FreshnessReasonCode.SOURCE_RETRIEVED_AFTER_EVALUATION,
    FreshnessReasonCode.SOURCE_OBSERVED_AFTER_EVALUATION,
})

_AMBIGUOUS_CORRECTION_REASONS = frozenset(
    tuple(CorrectionSelectionReasonCode)[:5]
)
_SELECTED_CORRECTION_REASONS = frozenset(
    tuple(CorrectionSelectionReasonCode)[5:]
)


def _freshness_status_from_reasons(
    reasons: Tuple[FreshnessReasonCode, ...]
) -> FreshnessStatus:
    """Derive status from complete canonical reasons using fixed precedence."""

    selected = set(reasons)
    if selected & _INELIGIBLE_FRESHNESS_REASONS:
        return FreshnessStatus.INELIGIBLE
    if selected & _UNKNOWN_FRESHNESS_REASONS:
        return FreshnessStatus.UNKNOWN
    if selected & _STALE_FRESHNESS_REASONS:
        return FreshnessStatus.STALE
    return FreshnessStatus.FRESH


@dataclass(frozen=True)
class MarketDataFreshnessPolicy:
    """Explicit immutable thresholds for single-record freshness."""

    policy_id: str
    policy_version: str
    maximum_quote_age_seconds: int
    maximum_analytics_age_seconds: int
    maximum_activity_age_seconds: int
    maximum_reference_age_seconds: int
    maximum_rate_age_seconds: int
    maximum_dividend_age_seconds: int
    maximum_retrieval_lag_seconds: int
    maximum_source_observation_span_seconds: int
    maximum_cross_record_skew_seconds: int
    maximum_open_interest_session_date_gap_days: int
    maximum_historical_bar_session_date_gap_days: int
    allow_delayed_data: bool
    allow_indicative_data: bool
    allow_non_firm_data: bool
    allow_partial_data: bool
    allow_assigned_timestamps: bool
    require_regular_session_quotes: bool
    require_completed_historical_sessions: bool

    def __post_init__(self) -> None:
        policy_id = _normalize_required_string("policy_id", self.policy_id)
        policy_version = _normalize_required_string(
            "policy_version", self.policy_version
        )
        threshold_names = (
            "maximum_quote_age_seconds",
            "maximum_analytics_age_seconds",
            "maximum_activity_age_seconds",
            "maximum_reference_age_seconds",
            "maximum_rate_age_seconds",
            "maximum_dividend_age_seconds",
            "maximum_retrieval_lag_seconds",
            "maximum_source_observation_span_seconds",
            "maximum_cross_record_skew_seconds",
            "maximum_open_interest_session_date_gap_days",
            "maximum_historical_bar_session_date_gap_days",
        )
        boolean_names = (
            "allow_delayed_data",
            "allow_indicative_data",
            "allow_non_firm_data",
            "allow_partial_data",
            "allow_assigned_timestamps",
            "require_regular_session_quotes",
            "require_completed_historical_sessions",
        )
        for name in threshold_names:
            _validate_integer(name, getattr(self, name), 0)
        for name in boolean_names:
            _validate_boolean(name, getattr(self, name))
        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(self, "policy_version", policy_version)


@dataclass(frozen=True)
class FreshnessContext:
    """Explicit evaluation time and caller-supplied completed session date."""

    evaluation_at: datetime.datetime
    latest_completed_session_date: datetime.date

    def __post_init__(self) -> None:
        evaluation_at = _normalize_utc_datetime(
            "evaluation_at", self.evaluation_at
        )
        _validate_date_only(
            "latest_completed_session_date", self.latest_completed_session_date
        )
        object.__setattr__(self, "evaluation_at", evaluation_at)


@dataclass(frozen=True)
class FreshnessAssessment:
    """Immutable calculated facts and policy result for one normalized record."""

    record_id: str
    category: MarketDataCategory
    status: FreshnessStatus
    reason_codes: Tuple[FreshnessReasonCode, ...]
    policy_id: str
    policy_version: str
    evaluated_at: datetime.datetime
    effective_age_seconds: decimal.Decimal
    oldest_source_age_seconds: decimal.Decimal
    maximum_retrieval_lag_seconds_observed: decimal.Decimal
    source_observation_span_seconds: decimal.Decimal
    session_date_gap_days: Optional[int]

    def __post_init__(self) -> None:
        record_id = _normalize_required_string("record_id", self.record_id)
        policy_id = _normalize_required_string("policy_id", self.policy_id)
        policy_version = _normalize_required_string(
            "policy_version", self.policy_version
        )
        if not isinstance(self.category, MarketDataCategory):
            raise TypeError("category must be a MarketDataCategory")
        if not isinstance(self.status, FreshnessStatus):
            raise TypeError("status must be a FreshnessStatus")
        reasons = _normalize_enum_flags(
            "reason_codes", self.reason_codes, FreshnessReasonCode
        )
        if not reasons:
            raise ValueError("reason_codes must contain at least one item")
        fresh_reason = FreshnessReasonCode.FRESH_WITHIN_POLICY
        if fresh_reason in reasons and reasons != (fresh_reason,):
            raise ValueError("fresh_within_policy must be the only reason")
        expected_status = _freshness_status_from_reasons(reasons)
        if expected_status is FreshnessStatus.FRESH and reasons != (fresh_reason,):
            raise ValueError("fresh assessments require fresh_within_policy")
        if self.status is not expected_status:
            raise ValueError("status does not agree with reason_codes")

        evaluated_at = _normalize_utc_datetime("evaluated_at", self.evaluated_at)
        effective_age = _normalize_finite_decimal(
            "effective_age_seconds", self.effective_age_seconds
        )
        oldest_source_age = _normalize_finite_decimal(
            "oldest_source_age_seconds", self.oldest_source_age_seconds
        )
        retrieval_lag = _normalize_nonnegative_decimal(
            "maximum_retrieval_lag_seconds_observed",
            self.maximum_retrieval_lag_seconds_observed,
        )
        source_span = _normalize_nonnegative_decimal(
            "source_observation_span_seconds",
            self.source_observation_span_seconds,
        )
        if self.session_date_gap_days is not None and (
            isinstance(self.session_date_gap_days, bool)
            or not isinstance(self.session_date_gap_days, int)
        ):
            raise TypeError("session_date_gap_days must be an integer or None")

        selected_reasons = set(reasons)
        for reason, allowed_categories in _FRESHNESS_REASON_CATEGORIES.items():
            if reason in selected_reasons and self.category not in allowed_categories:
                raise ValueError(
                    f"{reason.value} is incompatible with category {self.category.value}"
                )

        date_gap = self.session_date_gap_days
        future_session_reason = (
            FreshnessReasonCode.SESSION_DATE_AFTER_LATEST_COMPLETED_SESSION
        )
        open_interest_gap_reason = (
            FreshnessReasonCode.OPEN_INTEREST_SESSION_DATE_GAP_EXCEEDED
        )
        historical_bar_gap_reason = (
            FreshnessReasonCode.HISTORICAL_BAR_SESSION_DATE_GAP_EXCEEDED
        )
        historical_incomplete_reason = (
            FreshnessReasonCode.HISTORICAL_SESSION_INCOMPLETE
        )
        if self.category in _NO_SESSION_DATE_GAP_CATEGORIES and date_gap is not None:
            raise ValueError(
                f"{self.category.value} assessments require no session date gap"
            )
        if date_gap is not None and date_gap < 0 and future_session_reason not in selected_reasons:
            raise ValueError("a negative session date gap requires the future-session reason")
        if future_session_reason in selected_reasons and (
            date_gap is None or date_gap >= 0
        ):
            raise ValueError("the future-session reason requires a negative date gap")
        for reason in (open_interest_gap_reason, historical_bar_gap_reason):
            if reason in selected_reasons and (
                date_gap is None or date_gap <= 0
            ):
                raise ValueError(f"{reason.value} requires a positive date gap")
        if (
            historical_incomplete_reason in selected_reasons
            and date_gap is not None
        ):
            raise ValueError("an incomplete historical session requires no date gap")

        if (
            effective_age < 0 or oldest_source_age < 0
        ) and not _FUTURE_CHRONOLOGY_REASONS.issubset(selected_reasons):
            raise ValueError(
                "negative ages require all future chronology reasons"
            )

        effective_age_fraction = Fraction(effective_age)
        oldest_source_age_fraction = Fraction(oldest_source_age)
        source_span_fraction = Fraction(source_span)
        if not (
            oldest_source_age_fraction - source_span_fraction
            <= effective_age_fraction
            <= oldest_source_age_fraction
        ):
            raise ValueError(
                "effective age must lie within the complete source age range"
            )

        object.__setattr__(self, "record_id", record_id)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(self, "policy_version", policy_version)
        object.__setattr__(self, "evaluated_at", evaluated_at)
        object.__setattr__(self, "effective_age_seconds", effective_age)
        object.__setattr__(self, "oldest_source_age_seconds", oldest_source_age)
        object.__setattr__(
            self, "maximum_retrieval_lag_seconds_observed", retrieval_lag
        )
        object.__setattr__(self, "source_observation_span_seconds", source_span)


@dataclass(frozen=True)
class CorrectionSelection:
    """Immutable result of deterministic provider-correction selection."""

    semantic_observation_key: str
    candidate_record_ids: Tuple[str, ...]
    selected_record_id: Optional[str]
    status: CorrectionSelectionStatus
    reason_codes: Tuple[CorrectionSelectionReasonCode, ...]
    rule_id: str
    rule_version: str
    evaluated_at: datetime.datetime

    def __post_init__(self) -> None:
        semantic_key = _normalize_required_string(
            "semantic_observation_key", self.semantic_observation_key
        )
        if not isinstance(self.candidate_record_ids, (tuple, list)):
            raise TypeError("candidate_record_ids must be a tuple or list")
        candidate_ids = tuple(
            _normalize_required_string("candidate_record_id", candidate_id)
            for candidate_id in self.candidate_record_ids
        )
        if not candidate_ids:
            raise ValueError("candidate_record_ids must contain at least one item")
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate_record_ids must not contain duplicates")
        candidate_ids = tuple(sorted(candidate_ids))

        selected_id = _normalize_optional_string(
            "selected_record_id", self.selected_record_id
        )
        if not isinstance(self.status, CorrectionSelectionStatus):
            raise TypeError("status must be a CorrectionSelectionStatus")
        reasons = _normalize_enum_flags(
            "reason_codes", self.reason_codes, CorrectionSelectionReasonCode
        )
        if len(reasons) != 1:
            raise ValueError("reason_codes must contain exactly one item")

        if self.status is CorrectionSelectionStatus.SELECTED:
            if selected_id is None:
                raise ValueError("selected status requires selected_record_id")
            if selected_id not in candidate_ids:
                raise ValueError(
                    "selected_record_id must belong to candidate_record_ids"
                )
            if reasons[0] not in _SELECTED_CORRECTION_REASONS:
                raise ValueError("selected status requires a selection reason")
        else:
            if selected_id is not None:
                raise ValueError(
                    "ambiguous status requires selected_record_id to be None"
                )
            if reasons[0] not in _AMBIGUOUS_CORRECTION_REASONS:
                raise ValueError("ambiguous status requires an ambiguity reason")

        rule_id = _normalize_required_string("rule_id", self.rule_id)
        rule_version = _normalize_required_string(
            "rule_version", self.rule_version
        )
        evaluated_at = _normalize_utc_datetime("evaluated_at", self.evaluated_at)

        object.__setattr__(self, "semantic_observation_key", semantic_key)
        object.__setattr__(self, "candidate_record_ids", candidate_ids)
        object.__setattr__(self, "selected_record_id", selected_id)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "rule_version", rule_version)
        object.__setattr__(self, "evaluated_at", evaluated_at)


def _normalize_lineage_source_ids(values: object) -> Tuple[str, ...]:
    """Normalize the exact tuple/list source-ID constructor boundary."""

    if type(values) is not tuple and type(values) is not list:
        raise TypeError("source_ids must be an exact tuple or list")
    normalized = []
    for value in values:
        if type(value) is not str:
            raise TypeError("every source_ids item must have exact type str")
        source_id = value.strip()
        if not source_id:
            raise ValueError("source_ids items must not be empty")
        normalized.append(source_id)
    if not normalized:
        raise ValueError("source_ids must contain at least one item")
    if len(set(normalized)) != len(normalized):
        raise ValueError("source_ids must not contain duplicates")
    return tuple(sorted(normalized))


def _normalize_calculation_inputs(
    values: object,
) -> Tuple["CalculationInputReference", ...]:
    """Normalize exact calculation-input records into record-ID order."""

    if type(values) is not tuple and type(values) is not list:
        raise TypeError("inputs must be an exact tuple or list")
    normalized = tuple(values)
    if not all(type(item) is CalculationInputReference for item in normalized):
        raise TypeError(
            "every inputs item must have exact type CalculationInputReference"
        )
    if not normalized:
        raise ValueError("inputs must contain at least one item")
    record_ids = tuple(item.record_id for item in normalized)
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("input record IDs must not contain duplicates")
    return tuple(sorted(normalized, key=lambda item: item.record_id))


def _normalize_calculation_quality_flags(
    values: object,
) -> Tuple[CalculationQualityFlag, ...]:
    """Normalize exact calculation flags into declaration order."""

    if type(values) is not tuple and type(values) is not list:
        raise TypeError("quality_flags must be an exact tuple or list")
    normalized = tuple(values)
    if not all(type(item) is CalculationQualityFlag for item in normalized):
        raise TypeError(
            "every quality_flags item must have exact type CalculationQualityFlag"
        )
    if len(set(normalized)) != len(normalized):
        raise ValueError("quality_flags must not contain duplicates")
    selected = set(normalized)
    return tuple(flag for flag in CalculationQualityFlag if flag in selected)


@dataclass(frozen=True)
class CalculationInputReference:
    """Immutable reference to one normalized calculation input version."""

    record_id: str
    normalized_at: datetime.datetime
    source_ids: Tuple[str, ...]

    def __post_init__(self) -> None:
        record_id = _normalize_required_string("record_id", self.record_id)
        normalized_at = _normalize_exact_utc_datetime(
            "normalized_at", self.normalized_at
        )
        source_ids = _normalize_lineage_source_ids(self.source_ids)
        object.__setattr__(self, "record_id", record_id)
        object.__setattr__(self, "normalized_at", normalized_at)
        object.__setattr__(self, "source_ids", source_ids)


@dataclass(frozen=True)
class CalculationLineage:
    """Immutable auditable sidecar for one deterministic calculation."""

    calculation_id: str
    calculation_type: str
    methodology_id: str
    methodology_version: str
    calculated_at: datetime.datetime
    inputs: Tuple[CalculationInputReference, ...]
    parameters_json: str
    quality_flags: Tuple[CalculationQualityFlag, ...]

    def __post_init__(self) -> None:
        calculation_id = _normalize_required_string(
            "calculation_id", self.calculation_id
        )
        calculation_type = _normalize_required_string(
            "calculation_type", self.calculation_type
        )
        methodology_id = _normalize_required_string(
            "methodology_id", self.methodology_id
        )
        methodology_version = _normalize_required_string(
            "methodology_version", self.methodology_version
        )
        calculated_at = _normalize_exact_utc_datetime(
            "calculated_at", self.calculated_at
        )
        inputs = _normalize_calculation_inputs(self.inputs)
        if calculation_id in {item.record_id for item in inputs}:
            raise ValueError("calculation_id must not equal an input record ID")
        if any(calculated_at < item.normalized_at for item in inputs):
            raise ValueError("calculated_at must not precede any input")

        if type(self.parameters_json) is not str:
            raise TypeError("parameters_json must have exact type str")
        parameters_json = self.parameters_json.strip()
        if not parameters_json:
            raise ValueError("parameters_json must not be empty")
        _validate_canonical_lineage_json(parameters_json)
        quality_flags = _normalize_calculation_quality_flags(
            self.quality_flags
        )

        object.__setattr__(self, "calculation_id", calculation_id)
        object.__setattr__(self, "calculation_type", calculation_type)
        object.__setattr__(self, "methodology_id", methodology_id)
        object.__setattr__(self, "methodology_version", methodology_version)
        object.__setattr__(self, "calculated_at", calculated_at)
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(self, "parameters_json", parameters_json)
        object.__setattr__(self, "quality_flags", quality_flags)


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


_SEMANTIC_OBSERVATION_PREFIX = "semantic-observation-v0.1:"


def _semantic_underlying_key(underlying_key: UnderlyingKey) -> dict:
    """Return the exact canonical identity payload for an underlying."""

    return {
        "symbol": underlying_key.symbol,
        "listing_mic": underlying_key.listing_mic,
        "security_type": underlying_key.security_type.value,
        "currency": underlying_key.currency,
    }


def _semantic_option_contract_key(contract_key: OptionContractKey) -> dict:
    """Return the exact canonical identity payload for an option contract."""

    return {
        "underlying_key": _semantic_underlying_key(contract_key.underlying_key),
        "expiration": contract_key.expiration,
        "option_type": contract_key.option_type,
        "strike": contract_key.strike,
        "contract_multiplier": contract_key.contract_multiplier,
        "currency": contract_key.currency,
        "deliverable_id": contract_key.deliverable_id,
    }


def _semantic_observation_payload(record: object) -> dict:
    """Build the exact v0.1 payload for one supported exact record type."""

    record_type = type(record)
    if record_type is UnderlyingQuoteObservation:
        return {
            "record_type": "UnderlyingQuoteObservation",
            "underlying_key": _semantic_underlying_key(record.underlying_key),
            "session_date": record.session_date,
            "effective_observed_at": record.metadata.effective_observed_at,
            "market_phase": record.market_phase.value,
            "quote_scope": record.quote_scope.value,
            "venue_mic": record.venue_mic,
        }
    if record_type is OptionContractReference:
        return {
            "record_type": "OptionContractReference",
            "contract_key": _semantic_option_contract_key(record.contract_key),
        }
    if record_type is OptionQuoteObservation:
        return {
            "record_type": "OptionQuoteObservation",
            "contract_key": _semantic_option_contract_key(record.contract_key),
            "session_date": record.session_date,
            "effective_observed_at": record.metadata.effective_observed_at,
            "market_phase": record.market_phase.value,
            "quote_scope": record.quote_scope.value,
            "venue_mic": record.venue_mic,
        }
    if record_type is OptionVolumeObservation:
        return {
            "record_type": "OptionVolumeObservation",
            "contract_key": _semantic_option_contract_key(record.contract_key),
            "session_date": record.session_date,
            "effective_observed_at": record.metadata.effective_observed_at,
        }
    if record_type is OptionOpenInterestObservation:
        return {
            "record_type": "OptionOpenInterestObservation",
            "contract_key": _semantic_option_contract_key(record.contract_key),
            "open_interest_session_date": record.open_interest_session_date,
        }
    if record_type is OptionImpliedVolatilityObservation:
        return {
            "record_type": "OptionImpliedVolatilityObservation",
            "contract_key": _semantic_option_contract_key(record.contract_key),
            "session_date": record.session_date,
            "effective_observed_at": record.metadata.effective_observed_at,
            "model_name": record.model_name,
            "model_version": record.model_version,
            "rate_input_description": record.rate_input_description,
            "dividend_input_description": record.dividend_input_description,
        }
    if record_type is OptionGreeksObservation:
        return {
            "record_type": "OptionGreeksObservation",
            "contract_key": _semantic_option_contract_key(record.contract_key),
            "session_date": record.session_date,
            "effective_observed_at": record.metadata.effective_observed_at,
            "model_name": record.model_name,
            "model_version": record.model_version,
            "rate_input_description": record.rate_input_description,
            "dividend_input_description": record.dividend_input_description,
        }
    if record_type is UnderlyingDailyBarObservation:
        return {
            "record_type": "UnderlyingDailyBarObservation",
            "underlying_key": _semantic_underlying_key(record.underlying_key),
            "session_date": record.session_date,
        }
    if record_type is RateCurvePointObservation:
        return {
            "record_type": "RateCurvePointObservation",
            "curve_id": record.curve_id,
            "currency": record.currency,
            "tenor_days": record.tenor_days,
            "effective_date": record.effective_date,
            "compounding_convention": record.compounding_convention,
            "day_count_convention": record.day_count_convention,
        }
    if record_type is DividendObservation:
        return {
            "record_type": "DividendObservation",
            "underlying_key": _semantic_underlying_key(record.underlying_key),
            "dividend_type": record.dividend_type,
            "ex_date": record.ex_date,
            "status": record.status.value,
        }
    raise TypeError("record must have an exact supported observation type")


def semantic_observation_key(record: object) -> str:
    """Return the deterministic v0.1 semantic key for one observation."""

    payload = _semantic_observation_payload(record)
    return _SEMANTIC_OBSERVATION_PREFIX + canonicalize_lineage_parameters(payload)


_MARKET_DATA_CATEGORY_BY_RECORD_TYPE = {
    UnderlyingQuoteObservation: MarketDataCategory.QUOTE,
    OptionQuoteObservation: MarketDataCategory.QUOTE,
    OptionImpliedVolatilityObservation: MarketDataCategory.ANALYTICS,
    OptionGreeksObservation: MarketDataCategory.ANALYTICS,
    OptionVolumeObservation: MarketDataCategory.ACTIVITY,
    OptionOpenInterestObservation: MarketDataCategory.ACTIVITY,
    OptionContractReference: MarketDataCategory.CONTRACT_REFERENCE,
    UnderlyingDailyBarObservation: MarketDataCategory.HISTORICAL_BAR,
    RateCurvePointObservation: MarketDataCategory.RATE,
    DividendObservation: MarketDataCategory.DIVIDEND,
}


def _freshness_age_limit(
    category: MarketDataCategory,
    policy: MarketDataFreshnessPolicy,
) -> Optional[int]:
    """Return the category age limit, or None for historical bars."""

    return {
        MarketDataCategory.QUOTE: policy.maximum_quote_age_seconds,
        MarketDataCategory.ANALYTICS: policy.maximum_analytics_age_seconds,
        MarketDataCategory.ACTIVITY: policy.maximum_activity_age_seconds,
        MarketDataCategory.CONTRACT_REFERENCE: (
            policy.maximum_reference_age_seconds
        ),
        MarketDataCategory.HISTORICAL_BAR: None,
        MarketDataCategory.RATE: policy.maximum_rate_age_seconds,
        MarketDataCategory.DIVIDEND: policy.maximum_dividend_age_seconds,
    }[category]


def assess_market_data_freshness(
    record: object,
    policy: MarketDataFreshnessPolicy,
    context: FreshnessContext,
) -> FreshnessAssessment:
    """Assess one exact supported normalized record without external state."""

    category = _MARKET_DATA_CATEGORY_BY_RECORD_TYPE.get(type(record))
    if category is None:
        raise TypeError("record must be a supported normalized market-data record")
    if not isinstance(policy, MarketDataFreshnessPolicy):
        raise TypeError("policy must be a MarketDataFreshnessPolicy")
    if not isinstance(context, FreshnessContext):
        raise TypeError("context must be a FreshnessContext")

    metadata = record.metadata  # type: ignore[attr-defined]
    sources = metadata.source_references
    observed_times = tuple(source.observed_at for source in sources)
    evaluation_at = context.evaluation_at
    effective_age = _timedelta_to_decimal_seconds(
        evaluation_at - metadata.effective_observed_at
    )
    oldest_source_age = _timedelta_to_decimal_seconds(
        evaluation_at - min(observed_times)
    )
    retrieval_lag = max(
        _timedelta_to_decimal_seconds(source.retrieved_at - source.observed_at)
        for source in sources
    )
    source_span = _timedelta_to_decimal_seconds(
        max(observed_times) - min(observed_times)
    )

    session_date_gap_days = None
    if type(record) is OptionOpenInterestObservation:
        session_date_gap_days = (
            context.latest_completed_session_date
            - record.open_interest_session_date  # type: ignore[attr-defined]
        ).days
    elif (
        type(record) is UnderlyingDailyBarObservation
        and record.is_session_complete  # type: ignore[attr-defined]
    ):
        session_date_gap_days = (
            context.latest_completed_session_date
            - record.session_date  # type: ignore[attr-defined]
        ).days

    reasons = set()
    if metadata.normalized_at > evaluation_at:
        reasons.add(
            FreshnessReasonCode.RECORD_NORMALIZED_AFTER_EVALUATION
        )
    if any(source.retrieved_at > evaluation_at for source in sources):
        reasons.add(FreshnessReasonCode.SOURCE_RETRIEVED_AFTER_EVALUATION)
    if any(source.observed_at > evaluation_at for source in sources):
        reasons.add(FreshnessReasonCode.SOURCE_OBSERVED_AFTER_EVALUATION)

    normalization_flags = set(metadata.quality_flags)
    if NormalizationQualityFlag.INCOMPLETE in normalization_flags:
        reasons.add(FreshnessReasonCode.NORMALIZATION_INCOMPLETE)
    if (
        NormalizationQualityFlag.TIMESTAMP_ASSIGNED in normalization_flags
        and not policy.allow_assigned_timestamps
    ):
        reasons.add(FreshnessReasonCode.ASSIGNED_TIMESTAMP_NOT_ALLOWED)

    for source in sources:
        source_flags = set(source.quality_flags)
        if (
            SourceQualityFlag.DELAYED in source_flags
            and not policy.allow_delayed_data
        ):
            reasons.add(FreshnessReasonCode.DELAYED_DATA_NOT_ALLOWED)
        if (
            SourceQualityFlag.INDICATIVE in source_flags
            and not policy.allow_indicative_data
        ):
            reasons.add(FreshnessReasonCode.INDICATIVE_DATA_NOT_ALLOWED)
        if (
            SourceQualityFlag.NON_FIRM in source_flags
            and not policy.allow_non_firm_data
        ):
            reasons.add(FreshnessReasonCode.NON_FIRM_DATA_NOT_ALLOWED)
        if (
            SourceQualityFlag.PARTIAL in source_flags
            and not policy.allow_partial_data
        ):
            reasons.add(FreshnessReasonCode.PARTIAL_DATA_NOT_ALLOWED)
        if (
            SourceQualityFlag.HALTED in source_flags
            and category in {
                MarketDataCategory.QUOTE,
                MarketDataCategory.ANALYTICS,
            }
        ):
            reasons.add(FreshnessReasonCode.HALTED_SOURCE)

    if (
        len(sources) > 1
        and source_span
        > decimal.Decimal(policy.maximum_source_observation_span_seconds)
    ):
        reasons.add(FreshnessReasonCode.SOURCE_OBSERVATION_SPAN_EXCEEDED)

    if category is MarketDataCategory.QUOTE:
        if record.market_phase is MarketPhase.UNKNOWN:  # type: ignore[attr-defined]
            reasons.add(FreshnessReasonCode.UNKNOWN_MARKET_PHASE)
        if record.quote_scope is QuoteScope.UNKNOWN:  # type: ignore[attr-defined]
            reasons.add(FreshnessReasonCode.UNKNOWN_QUOTE_SCOPE)
        if (
            policy.require_regular_session_quotes
            and record.market_phase is not MarketPhase.REGULAR  # type: ignore[attr-defined]
        ):
            reasons.add(FreshnessReasonCode.NON_REGULAR_SESSION_QUOTE)

    if type(record) is UnderlyingDailyBarObservation:
        if (
            policy.require_completed_historical_sessions
            and not record.is_session_complete  # type: ignore[attr-defined]
        ):
            reasons.add(FreshnessReasonCode.HISTORICAL_SESSION_INCOMPLETE)
        if record.is_session_complete:  # type: ignore[attr-defined]
            if record.session_date > context.latest_completed_session_date:  # type: ignore[attr-defined]
                reasons.add(
                    FreshnessReasonCode.SESSION_DATE_AFTER_LATEST_COMPLETED_SESSION
                )
            if (
                session_date_gap_days
                > policy.maximum_historical_bar_session_date_gap_days
            ):
                reasons.add(
                    FreshnessReasonCode.HISTORICAL_BAR_SESSION_DATE_GAP_EXCEEDED
                )

    if type(record) is OptionOpenInterestObservation:
        if (
            record.open_interest_session_date  # type: ignore[attr-defined]
            > context.latest_completed_session_date
        ):
            reasons.add(
                FreshnessReasonCode.SESSION_DATE_AFTER_LATEST_COMPLETED_SESSION
            )
        if (
            session_date_gap_days
            > policy.maximum_open_interest_session_date_gap_days
        ):
            reasons.add(
                FreshnessReasonCode.OPEN_INTEREST_SESSION_DATE_GAP_EXCEEDED
            )

    age_limit = _freshness_age_limit(category, policy)
    if age_limit is not None:
        decimal_age_limit = decimal.Decimal(age_limit)
        if effective_age > decimal_age_limit:
            reasons.add(FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED)
        if oldest_source_age > decimal_age_limit:
            reasons.add(FreshnessReasonCode.OLDEST_SOURCE_AGE_EXCEEDED)
    if retrieval_lag > decimal.Decimal(policy.maximum_retrieval_lag_seconds):
        reasons.add(FreshnessReasonCode.RETRIEVAL_LAG_EXCEEDED)

    if not reasons:
        reasons.add(FreshnessReasonCode.FRESH_WITHIN_POLICY)
    canonical_reasons = tuple(
        reason for reason in FreshnessReasonCode if reason in reasons
    )
    status = _freshness_status_from_reasons(canonical_reasons)
    return FreshnessAssessment(
        record_id=metadata.record_id,
        category=category,
        status=status,
        reason_codes=canonical_reasons,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        evaluated_at=evaluation_at,
        effective_age_seconds=effective_age,
        oldest_source_age_seconds=oldest_source_age,
        maximum_retrieval_lag_seconds_observed=retrieval_lag,
        source_observation_span_seconds=source_span,
        session_date_gap_days=session_date_gap_days,
    )


def _validate_correction_candidates(
    candidates: object,
    evaluated_at: datetime.datetime,
) -> Tuple[NormalizationMetadata, ...]:
    """Validate and presentation-sort exact correction candidates."""

    if not isinstance(candidates, (tuple, list)):
        raise TypeError("candidates must be a tuple or list")
    normalized = tuple(candidates)
    if not normalized:
        raise ValueError("candidates must contain at least one item")
    if not all(
        type(candidate) is NormalizationMetadata for candidate in normalized
    ):
        raise TypeError("every candidate must be an exact NormalizationMetadata")
    record_ids = tuple(candidate.record_id for candidate in normalized)
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("candidates must have unique record IDs")
    if any(candidate.normalized_at > evaluated_at for candidate in normalized):
        raise ValueError("candidates must be normalized by evaluated_at")
    return tuple(sorted(normalized, key=lambda candidate: candidate.record_id))


def _normalized_revision_component(source: SourceReference) -> int:
    """Return the sole normalized revision value used by selection."""

    revision = source.revision_number
    return revision if revision is not None and revision > 0 else 0


def _correction_lineage(
    candidate: NormalizationMetadata,
) -> Tuple[Tuple[Tuple[str, str, str], int, Optional[str]], ...]:
    """Build one candidate's ordered lineage, revision, and identity entries."""

    entries = []
    for source in candidate.source_references:
        provider_record_id = source.provider_record_id
        if provider_record_id is None:
            raise ValueError("correction lineage requires provider_record_id")
        entries.append((
            (
                source.provider_name,
                source.dataset_name,
                provider_record_id,
            ),
            _normalized_revision_component(source),
            source.provider_correction_id,
        ))
    ordered_entries = tuple(sorted(entries, key=lambda entry: entry[0]))
    keys = tuple(entry[0] for entry in ordered_entries)
    if len(set(keys)) != len(keys):
        raise ValueError("a candidate must not contain duplicate lineage keys")
    return ordered_entries


def _has_correction_identity_conflict(
    lineages: Tuple[
        Tuple[Tuple[Tuple[str, str, str], int, Optional[str]], ...], ...
    ],
) -> bool:
    """Check complete candidate groups per lineage and normalized revision."""

    for lineage_index in range(len(lineages[0])):
        identities_by_revision = {}
        for lineage in lineages:
            revision = lineage[lineage_index][1]
            correction_id = lineage[lineage_index][2]
            identities_by_revision.setdefault(revision, set()).add(correction_id)
        if any(
            len(identities) > 1
            for identities in identities_by_revision.values()
        ):
            return True
    return False


def _strictly_dominates(first: Tuple[int, ...], second: Tuple[int, ...]) -> bool:
    """Return whether one equal-lineage revision vector strictly dominates."""

    return all(
        first_component >= second_component
        for first_component, second_component in zip(first, second)
    ) and any(
        first_component > second_component
        for first_component, second_component in zip(first, second)
    )


def select_correction_candidate(
    semantic_observation_key: object,
    candidates: object,
    evaluated_at: object,
    rule_id: object,
    rule_version: object,
) -> CorrectionSelection:
    """Select one deterministic correction candidate without external state."""

    semantic_key = _normalize_required_string(
        "semantic_observation_key", semantic_observation_key
    )
    normalized_evaluated_at = _normalize_utc_datetime(
        "evaluated_at", evaluated_at
    )
    normalized_rule_id = _normalize_required_string("rule_id", rule_id)
    normalized_rule_version = _normalize_required_string(
        "rule_version", rule_version
    )
    normalized_candidates = _validate_correction_candidates(
        candidates, normalized_evaluated_at
    )
    candidate_ids = tuple(
        candidate.record_id for candidate in normalized_candidates
    )

    def result(
        status: CorrectionSelectionStatus,
        reason: CorrectionSelectionReasonCode,
        selected_record_id: Optional[str] = None,
    ) -> CorrectionSelection:
        return CorrectionSelection(
            semantic_observation_key=semantic_key,
            candidate_record_ids=candidate_ids,
            selected_record_id=selected_record_id,
            status=status,
            reason_codes=(reason,),
            rule_id=normalized_rule_id,
            rule_version=normalized_rule_version,
            evaluated_at=normalized_evaluated_at,
        )

    if len(normalized_candidates) == 1:
        return result(
            CorrectionSelectionStatus.SELECTED,
            CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
            normalized_candidates[0].record_id,
        )

    if any(
        source.provider_record_id is None
        for candidate in normalized_candidates
        for source in candidate.source_references
    ):
        return result(
            CorrectionSelectionStatus.AMBIGUOUS,
            CorrectionSelectionReasonCode.MISSING_PROVIDER_RECORD_ID,
        )

    lineages = tuple(
        _correction_lineage(candidate) for candidate in normalized_candidates
    )
    lineage_key_sets = tuple(
        tuple(entry[0] for entry in lineage) for lineage in lineages
    )
    if any(keys != lineage_key_sets[0] for keys in lineage_key_sets[1:]):
        return result(
            CorrectionSelectionStatus.AMBIGUOUS,
            CorrectionSelectionReasonCode.SOURCE_LINEAGE_MISMATCH,
        )

    if _has_correction_identity_conflict(lineages):
        return result(
            CorrectionSelectionStatus.AMBIGUOUS,
            CorrectionSelectionReasonCode.CONFLICTING_CORRECTION_IDS_SAME_REVISION,
        )

    vectors = tuple(
        tuple(entry[1] for entry in lineage) for lineage in lineages
    )
    if all(vector == vectors[0] for vector in vectors[1:]):
        return result(
            CorrectionSelectionStatus.AMBIGUOUS,
            CorrectionSelectionReasonCode.TIED_REVISION_VECTORS,
        )

    dominating_indexes = tuple(
        index
        for index, vector in enumerate(vectors)
        if all(
            index == other_index or _strictly_dominates(vector, other_vector)
            for other_index, other_vector in enumerate(vectors)
        )
    )
    if len(dominating_indexes) == 1:
        selected_index = dominating_indexes[0]
        return result(
            CorrectionSelectionStatus.SELECTED,
            CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,
            normalized_candidates[selected_index].record_id,
        )
    return result(
        CorrectionSelectionStatus.AMBIGUOUS,
        CorrectionSelectionReasonCode.INCOMPARABLE_REVISION_VECTORS,
    )


def _validate_binding_candidate_container(
    name: str,
    candidates: object,
) -> None:
    """Require the binding contract's tuple-or-list candidate boundary."""

    if not isinstance(candidates, (tuple, list)):
        raise TypeError(f"{name} must be a tuple or list")


def _validate_binding_candidate_elements(candidates: object) -> None:
    """Require exact supported normalized record types in caller order."""

    for candidate in candidates:  # type: ignore[union-attr]
        if type(candidate) not in _MARKET_DATA_CATEGORY_BY_RECORD_TYPE:
            raise TypeError(
                "every candidate must have an exact supported normalized "
                "market-data record type"
            )


def _canonicalize_binding_candidates(candidates: object) -> Tuple[object, ...]:
    """Validate collection values and return record-ID canonical order."""

    candidate_tuple = tuple(candidates)  # type: ignore[arg-type]
    if not candidate_tuple:
        raise ValueError("candidate records must contain at least one item")
    record_ids = tuple(
        candidate.metadata.record_id for candidate in candidate_tuple
    )
    if len(set(record_ids)) != len(record_ids):
        raise ValueError("candidate record IDs must not contain duplicates")
    return tuple(
        sorted(
            candidate_tuple,
            key=lambda candidate: candidate.metadata.record_id,
        )
    )


def _derive_binding_semantic_key(candidates: Tuple[object, ...]) -> str:
    """Derive and validate the complete semantic candidate group."""

    keys = tuple(semantic_observation_key(candidate) for candidate in candidates)
    if any(key != keys[0] for key in keys[1:]):
        raise ValueError("candidate records must share one semantic observation key")
    return keys[0]


def _resolve_binding_selected_record(
    candidates: Tuple[object, ...],
    selection: CorrectionSelection,
) -> object:
    """Require selected status and resolve one canonical candidate."""

    if (
        selection.status is not CorrectionSelectionStatus.SELECTED
        or selection.selected_record_id is None
    ):
        raise ValueError("correction selection is ambiguous")
    matches = tuple(
        candidate
        for candidate in candidates
        if candidate.metadata.record_id == selection.selected_record_id
    )
    if len(matches) != 1:
        raise ValueError(
            "correction selection must identify exactly one candidate record"
        )
    return matches[0]


def _validate_binding_chronology(
    selection: CorrectionSelection,
    context: FreshnessContext,
) -> None:
    """Require correction selection no later than freshness evaluation."""

    if selection.evaluated_at > context.evaluation_at:
        raise ValueError(
            "correction selection evaluated_at must not be after freshness "
            "evaluation_at"
        )


def _validate_binding_fresh_only(assessment: FreshnessAssessment) -> None:
    """Require the exact successful freshness terminal result."""

    if not (
        assessment.status is FreshnessStatus.FRESH
        and assessment.reason_codes
        == (FreshnessReasonCode.FRESH_WITHIN_POLICY,)
    ):
        raise ValueError("selected candidate must be fresh within policy")


@dataclass(frozen=True)
class SelectedFreshMarketDataBinding:
    """Immutable proof that one correction-selected record is fresh."""

    candidate_records: Tuple[object, ...]
    correction_selection: CorrectionSelection
    freshness_policy: MarketDataFreshnessPolicy
    freshness_context: FreshnessContext
    freshness_assessment: FreshnessAssessment

    def __post_init__(self) -> None:
        _validate_binding_candidate_container(
            "candidate_records", self.candidate_records
        )
        if type(self.correction_selection) is not CorrectionSelection:
            raise TypeError("correction_selection must be a CorrectionSelection")
        if type(self.freshness_policy) is not MarketDataFreshnessPolicy:
            raise TypeError(
                "freshness_policy must be a MarketDataFreshnessPolicy"
            )
        if type(self.freshness_context) is not FreshnessContext:
            raise TypeError("freshness_context must be a FreshnessContext")
        if type(self.freshness_assessment) is not FreshnessAssessment:
            raise TypeError("freshness_assessment must be a FreshnessAssessment")

        _validate_binding_candidate_elements(self.candidate_records)
        candidates = _canonicalize_binding_candidates(self.candidate_records)
        semantic_key = _derive_binding_semantic_key(candidates)
        expected_selection = select_correction_candidate(
            semantic_key,
            tuple(candidate.metadata for candidate in candidates),
            self.correction_selection.evaluated_at,
            self.correction_selection.rule_id,
            self.correction_selection.rule_version,
        )
        if expected_selection != self.correction_selection:
            raise ValueError(
                "correction_selection does not match authoritative recomputation"
            )
        selected_record = _resolve_binding_selected_record(
            candidates, self.correction_selection
        )
        _validate_binding_chronology(
            self.correction_selection, self.freshness_context
        )
        expected_freshness = assess_market_data_freshness(
            selected_record,
            self.freshness_policy,
            self.freshness_context,
        )
        if expected_freshness != self.freshness_assessment:
            raise ValueError(
                "freshness_assessment does not match authoritative recomputation"
            )
        _validate_binding_fresh_only(self.freshness_assessment)
        object.__setattr__(self, "candidate_records", candidates)

    @property
    def semantic_observation_key(self) -> str:
        """Return the correction proof's semantic observation key."""

        return self.correction_selection.semantic_observation_key

    @property
    def selected_record(self) -> object:
        """Return the exact stored correction-selected candidate."""

        return next(
            candidate
            for candidate in self.candidate_records
            if candidate.metadata.record_id
            == self.correction_selection.selected_record_id
        )


def bind_selected_fresh_market_data(
    candidates: object,
    correction_evaluated_at: object,
    correction_rule_id: object,
    correction_rule_version: object,
    freshness_policy: object,
    freshness_context: object,
) -> SelectedFreshMarketDataBinding:
    """Bind one correction-selected record when it is exactly fresh."""

    _validate_binding_candidate_container("candidates", candidates)
    if type(freshness_policy) is not MarketDataFreshnessPolicy:
        raise TypeError("freshness_policy must be a MarketDataFreshnessPolicy")
    if type(freshness_context) is not FreshnessContext:
        raise TypeError("freshness_context must be a FreshnessContext")

    _validate_binding_candidate_elements(candidates)
    canonical_candidates = _canonicalize_binding_candidates(candidates)
    semantic_key = _derive_binding_semantic_key(canonical_candidates)
    correction_selection = select_correction_candidate(
        semantic_key,
        tuple(candidate.metadata for candidate in canonical_candidates),
        correction_evaluated_at,
        correction_rule_id,
        correction_rule_version,
    )
    selected_record = _resolve_binding_selected_record(
        canonical_candidates, correction_selection
    )
    _validate_binding_chronology(correction_selection, freshness_context)
    freshness_assessment = assess_market_data_freshness(
        selected_record,
        freshness_policy,
        freshness_context,
    )
    _validate_binding_fresh_only(freshness_assessment)
    return SelectedFreshMarketDataBinding(
        candidate_records=canonical_candidates,
        correction_selection=correction_selection,
        freshness_policy=freshness_policy,
        freshness_context=freshness_context,
        freshness_assessment=freshness_assessment,
    )


_SNAPSHOT_TIMING_TEMPORAL_RECORD_TYPES = frozenset({
    UnderlyingQuoteObservation,
    OptionQuoteObservation,
    OptionVolumeObservation,
    OptionImpliedVolatilityObservation,
    OptionGreeksObservation,
})


def _canonicalize_snapshot_timing_bindings(
    bindings: object,
) -> Tuple[SelectedFreshMarketDataBinding, ...]:
    """Validate exact bindings and return the canonical retained tuple."""

    if type(bindings) is not tuple and type(bindings) is not list:
        raise TypeError("bindings must be an exact tuple or list")
    for binding in bindings:
        if type(binding) is not SelectedFreshMarketDataBinding:
            raise TypeError(
                "every bindings item must have exact type "
                "SelectedFreshMarketDataBinding"
            )

    normalized = tuple(bindings)
    if not normalized:
        raise ValueError("bindings must contain at least one item")

    selected_record_ids = tuple(
        binding.selected_record.metadata.record_id
        for binding in normalized
    )
    if len(set(selected_record_ids)) != len(selected_record_ids):
        raise ValueError("selected record IDs must not contain duplicates")

    semantic_keys = tuple(
        binding.semantic_observation_key for binding in normalized
    )
    if len(set(semantic_keys)) != len(semantic_keys):
        raise ValueError(
            "semantic observation keys must not contain duplicates"
        )

    return tuple(sorted(
        normalized,
        key=lambda binding: (
            binding.semantic_observation_key,
            binding.selected_record.metadata.record_id,
        ),
    ))


def _derive_snapshot_timing_state(
    bindings: Tuple[SelectedFreshMarketDataBinding, ...],
) -> Tuple[
    Optional[MarketDataFreshnessPolicy],
    Optional[FreshnessContext],
    Optional[decimal.Decimal],
    Optional[decimal.Decimal],
    Tuple[MarketDataSnapshotTimingReasonCode, ...],
    bool,
]:
    """Derive complete binding-set timing state without external inputs."""

    first = bindings[0]
    common_policy = (
        first.freshness_policy
        if all(
            binding.freshness_policy == first.freshness_policy
            for binding in bindings[1:]
        )
        else None
    )
    common_context = (
        first.freshness_context
        if all(
            binding.freshness_context == first.freshness_context
            for binding in bindings[1:]
        )
        else None
    )

    temporal_records = tuple(
        binding.selected_record
        for binding in bindings
        if type(binding.selected_record)
        in _SNAPSHOT_TIMING_TEMPORAL_RECORD_TYPES
    )
    if temporal_records:
        effective_times = tuple(
            record.metadata.effective_observed_at
            for record in temporal_records
        )
        effective_span = (
            decimal.Decimal("0")
            if len(effective_times) == 1
            else _timedelta_to_decimal_seconds(
                max(effective_times) - min(effective_times)
            )
        )
        source_times = tuple(
            source.observed_at
            for record in temporal_records
            for source in record.metadata.source_references
        )
        source_span = (
            decimal.Decimal("0")
            if len(source_times) == 1
            else _timedelta_to_decimal_seconds(
                max(source_times) - min(source_times)
            )
        )
    else:
        effective_span = None
        source_span = None

    reasons = set()
    if common_policy is None:
        reasons.add(
            MarketDataSnapshotTimingReasonCode.MIXED_FRESHNESS_POLICY
        )
    if common_context is None:
        reasons.add(
            MarketDataSnapshotTimingReasonCode.MIXED_FRESHNESS_CONTEXT
        )
    if common_policy is not None and common_context is not None:
        threshold = decimal.Decimal(
            common_policy.maximum_cross_record_skew_seconds
        )
        if effective_span is not None and effective_span > threshold:
            reasons.add(
                MarketDataSnapshotTimingReasonCode.EFFECTIVE_TIME_SPAN_EXCEEDED
            )
        if source_span is not None and source_span > threshold:
            reasons.add(
                MarketDataSnapshotTimingReasonCode.SOURCE_OBSERVATION_SPAN_EXCEEDED
            )

    canonical_reasons = tuple(
        reason
        for reason in MarketDataSnapshotTimingReasonCode
        if reason in reasons
    )
    return (
        common_policy,
        common_context,
        effective_span,
        source_span,
        canonical_reasons,
        not canonical_reasons,
    )


@dataclass(frozen=True)
class MarketDataSnapshotTimingAssessment:
    """Immutable temporal-coherence assessment for selected/fresh bindings."""

    bindings: Tuple[SelectedFreshMarketDataBinding, ...]

    def __post_init__(self) -> None:
        bindings = _canonicalize_snapshot_timing_bindings(self.bindings)
        object.__setattr__(self, "bindings", bindings)

    @property
    def is_temporally_coherent(self) -> bool:
        """Return whether no temporal-coherence reason applies."""

        return _derive_snapshot_timing_state(self.bindings)[5]

    @property
    def reason_codes(
        self,
    ) -> Tuple[MarketDataSnapshotTimingReasonCode, ...]:
        """Return all applicable reasons in declaration order."""

        return _derive_snapshot_timing_state(self.bindings)[4]

    @property
    def common_freshness_policy(
        self,
    ) -> Optional[MarketDataFreshnessPolicy]:
        """Return the first retained policy when every policy is equal."""

        return _derive_snapshot_timing_state(self.bindings)[0]

    @property
    def common_freshness_context(self) -> Optional[FreshnessContext]:
        """Return the first retained context when every context is equal."""

        return _derive_snapshot_timing_state(self.bindings)[1]

    @property
    def effective_time_span_seconds(self) -> Optional[decimal.Decimal]:
        """Return the exact span across temporal effective times."""

        return _derive_snapshot_timing_state(self.bindings)[2]

    @property
    def source_observation_span_seconds(
        self,
    ) -> Optional[decimal.Decimal]:
        """Return the exact span across all temporal source observations."""

        return _derive_snapshot_timing_state(self.bindings)[3]


def assess_market_data_snapshot_timing(
    bindings: object,
) -> MarketDataSnapshotTimingAssessment:
    """Assess temporal coherence for exact selected/fresh bindings."""

    return MarketDataSnapshotTimingAssessment(bindings=bindings)


@dataclass(frozen=True)
class MarketDataBindingReference:
    """Portable reference to one selected/fresh market-data binding."""

    semantic_observation_key: str
    selected_record_id: str

    def __post_init__(self) -> None:
        if type(self.semantic_observation_key) is not str:
            raise TypeError("semantic_observation_key must be an exact string")
        if type(self.selected_record_id) is not str:
            raise TypeError("selected_record_id must be an exact string")

        semantic_key = self.semantic_observation_key.strip()
        record_id = self.selected_record_id.strip()
        if not semantic_key:
            raise ValueError("semantic_observation_key must not be empty")
        if not record_id:
            raise ValueError("selected_record_id must not be empty")

        object.__setattr__(self, "semantic_observation_key", semantic_key)
        object.__setattr__(self, "selected_record_id", record_id)


def market_data_binding_reference(
    binding: object,
) -> MarketDataBindingReference:
    """Return a portable reference derived from one exact binding."""

    if type(binding) is not SelectedFreshMarketDataBinding:
        raise TypeError(
            "binding must have exact type SelectedFreshMarketDataBinding"
        )
    return MarketDataBindingReference(
        semantic_observation_key=binding.semantic_observation_key,
        selected_record_id=binding.selected_record.metadata.record_id,
    )


def resolve_market_data_binding_reference(
    reference: object,
    timing_assessment: object,
) -> SelectedFreshMarketDataBinding:
    """Resolve one complete binding-reference pair in an exact assessment."""

    if type(reference) is not MarketDataBindingReference:
        raise TypeError(
            "reference must have exact type MarketDataBindingReference"
        )
    if type(timing_assessment) is not MarketDataSnapshotTimingAssessment:
        raise TypeError(
            "timing_assessment must have exact type "
            "MarketDataSnapshotTimingAssessment"
        )

    matches = tuple(
        binding
        for binding in timing_assessment.bindings
        if (
            binding.semantic_observation_key
            == reference.semantic_observation_key
            and binding.selected_record.metadata.record_id
            == reference.selected_record_id
        )
    )
    if len(matches) != 1:
        raise ValueError(
            "reference must resolve to exactly one binding in timing_assessment"
        )
    return matches[0]


class MarketDataRelationshipGroupKind(str, Enum):
    """Closed relationship-group grammar versions."""

    UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1 = (
        "underlying_option_quote_snapshot_v0.1"
    )
    OPTION_QUOTE_ANALYTICS_V0_1 = "option_quote_analytics_v0.1"
    OPTION_ACTIVITY_V0_1 = "option_activity_v0.1"
    OPTION_CONTRACT_REFERENCE_V0_1 = "option_contract_reference_v0.1"


class MarketDataRelationshipRole(str, Enum):
    """Closed roles for explicit market-data relationships."""

    UNDERLYING_QUOTE = "underlying_quote"
    OPTION_QUOTE = "option_quote"
    OPTION_IMPLIED_VOLATILITY = "option_implied_volatility"
    OPTION_GREEKS = "option_greeks"
    OPTION_VOLUME = "option_volume"
    OPTION_OPEN_INTEREST = "option_open_interest"
    OPTION_CONTRACT_REFERENCE = "option_contract_reference"


_RELATIONSHIP_GROUP_KIND_INDEX = {
    kind: index
    for index, kind in enumerate(MarketDataRelationshipGroupKind)
}

_RELATIONSHIP_ROLE_INDEX = {
    role: index
    for index, role in enumerate(MarketDataRelationshipRole)
}

_RELATIONSHIP_GROUP_CARDINALITIES = (
    # UQ       OQ       IV       Greeks   Volume   OI       ContractRef
    ((1, 1), (1, 1), (0, 0), (0, 0), (0, 0), (0, 0), (0, 0)),
    ((0, 0), (1, 1), (0, 1), (0, 1), (0, 0), (0, 0), (0, 0)),
    ((0, 0), (0, 1), (0, 0), (0, 0), (1, 1), (1, 1), (0, 0)),
    ((0, 0), (0, 1), (0, 1), (0, 1), (0, 1), (0, 1), (1, 1)),
)


def _normalize_relationship_group_id(group_id: object) -> str:
    """Require, strip, and return an exact nonempty built-in string."""

    if type(group_id) is not str:
        raise TypeError("group_id must be an exact string")
    normalized = group_id.strip()
    if not normalized:
        raise ValueError("group_id must not be empty")
    return normalized


@dataclass(frozen=True)
class MarketDataRelationshipGroupMember:
    """One explicit role and portable binding reference."""

    role: MarketDataRelationshipRole
    reference: MarketDataBindingReference

    def __post_init__(self) -> None:
        if type(self.role) is not MarketDataRelationshipRole:
            raise TypeError(
                "role must have exact type MarketDataRelationshipRole"
            )
        if type(self.reference) is not MarketDataBindingReference:
            raise TypeError(
                "reference must have exact type MarketDataBindingReference"
            )


def _validate_and_tuple_relationship_members(
    members: object,
) -> Tuple[MarketDataRelationshipGroupMember, ...]:
    """Validate the exact member collection boundary in caller order."""

    if type(members) is not tuple and type(members) is not list:
        raise TypeError("members must be an exact tuple or list")
    for member in members:
        if type(member) is not MarketDataRelationshipGroupMember:
            raise TypeError(
                "every members item must have exact type "
                "MarketDataRelationshipGroupMember"
            )
    return tuple(members)


def _validate_unique_relationship_references(
    members: Tuple[MarketDataRelationshipGroupMember, ...],
) -> None:
    """Reject complete binding-reference duplicates in caller order."""

    seen = set()
    for member in members:
        reference_key = (
            member.reference.semantic_observation_key,
            member.reference.selected_record_id,
        )
        if reference_key in seen:
            raise ValueError("members must not contain a duplicate reference")
        seen.add(reference_key)


def _validate_relationship_group_grammar(
    group_kind: MarketDataRelationshipGroupKind,
    members: Tuple[MarketDataRelationshipGroupMember, ...],
) -> None:
    """Validate role allowance, cardinality, and aggregate grammar."""

    cardinalities = _RELATIONSHIP_GROUP_CARDINALITIES[
        _RELATIONSHIP_GROUP_KIND_INDEX[group_kind]
    ]
    role_counts = tuple(
        sum(member.role is role for member in members)
        for role in MarketDataRelationshipRole
    )

    for role in MarketDataRelationshipRole:
        role_index = _RELATIONSHIP_ROLE_INDEX[role]
        if cardinalities[role_index] == (0, 0) and role_counts[role_index]:
            raise ValueError(
                f"role {role.value} is prohibited for group_kind"
            )

    for role in MarketDataRelationshipRole:
        role_index = _RELATIONSHIP_ROLE_INDEX[role]
        minimum, maximum = cardinalities[role_index]
        if minimum == maximum == 0:
            continue
        count = role_counts[role_index]
        if count < minimum:
            raise ValueError(
                f"role {role.value} violates minimum cardinality {minimum}"
            )
        if count > maximum:
            raise ValueError(
                f"role {role.value} violates maximum cardinality {maximum}"
            )

    if (
        group_kind
        is MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1
    ):
        iv_count = role_counts[_RELATIONSHIP_ROLE_INDEX[
            MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY
        ]]
        greeks_count = role_counts[_RELATIONSHIP_ROLE_INDEX[
            MarketDataRelationshipRole.OPTION_GREEKS
        ]]
        if iv_count + greeks_count < 1:
            raise ValueError(
                "analytics group requires implied volatility or Greeks"
            )
    elif (
        group_kind
        is MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1
    ):
        reference_index = _RELATIONSHIP_ROLE_INDEX[
            MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
        ]
        if sum(role_counts) - role_counts[reference_index] < 1:
            raise ValueError(
                "contract-reference group requires a non-reference role"
            )


def _canonicalize_relationship_group_members(
    members: Tuple[MarketDataRelationshipGroupMember, ...],
) -> Tuple[MarketDataRelationshipGroupMember, ...]:
    """Return exact member objects in canonical relationship order."""

    return tuple(sorted(
        members,
        key=lambda member: (
            _RELATIONSHIP_ROLE_INDEX[member.role],
            member.reference.semantic_observation_key,
            member.reference.selected_record_id,
        ),
    ))


@dataclass(frozen=True)
class MarketDataRelationshipGroup:
    """One validated and canonically ordered relationship group."""

    group_id: str
    group_kind: MarketDataRelationshipGroupKind
    members: Tuple[MarketDataRelationshipGroupMember, ...]

    def __post_init__(self) -> None:
        if type(self.group_id) is not str:
            raise TypeError("group_id must be an exact string")
        if type(self.group_kind) is not MarketDataRelationshipGroupKind:
            raise TypeError(
                "group_kind must have exact type "
                "MarketDataRelationshipGroupKind"
            )
        members = _validate_and_tuple_relationship_members(self.members)
        normalized_group_id = _normalize_relationship_group_id(self.group_id)
        if not members:
            raise ValueError("members must contain at least one item")
        _validate_unique_relationship_references(members)
        _validate_relationship_group_grammar(self.group_kind, members)
        canonical_members = _canonicalize_relationship_group_members(members)
        object.__setattr__(self, "group_id", normalized_group_id)
        object.__setattr__(self, "members", canonical_members)


def _validate_and_tuple_relationship_groups(
    groups: object,
) -> Tuple[MarketDataRelationshipGroup, ...]:
    """Validate the exact group collection boundary in caller order."""

    if type(groups) is not tuple and type(groups) is not list:
        raise TypeError("groups must be an exact tuple or list")
    for group in groups:
        if type(group) is not MarketDataRelationshipGroup:
            raise TypeError(
                "every groups item must have exact type "
                "MarketDataRelationshipGroup"
            )
    return tuple(groups)


def _validate_unique_relationship_group_ids(
    groups: Tuple[MarketDataRelationshipGroup, ...],
) -> None:
    """Reject duplicate normalized group IDs in caller order."""

    seen = set()
    for group in groups:
        if group.group_id in seen:
            raise ValueError("groups must not contain a duplicate group_id")
        seen.add(group.group_id)


def _canonicalize_relationship_request_groups(
    groups: Tuple[MarketDataRelationshipGroup, ...],
) -> Tuple[MarketDataRelationshipGroup, ...]:
    """Return exact group objects ordered only by normalized group ID."""

    return tuple(sorted(groups, key=lambda group: group.group_id))


@dataclass(frozen=True)
class MarketDataRelationshipRequest:
    """One immutable canonical request of explicit relationship groups."""

    groups: Tuple[MarketDataRelationshipGroup, ...]

    def __post_init__(self) -> None:
        groups = _validate_and_tuple_relationship_groups(self.groups)
        if not groups:
            raise ValueError("groups must contain at least one item")
        _validate_unique_relationship_group_ids(groups)
        canonical_groups = _canonicalize_relationship_request_groups(groups)
        object.__setattr__(self, "groups", canonical_groups)


class MarketDataRelationshipIssueCode(str, Enum):
    """Canonical relationship-coherence issues."""

    RESOLVED_RECORD_TYPE_MISMATCH = "resolved_record_type_mismatch"
    UNDERLYING_IDENTITY_MISMATCH = "underlying_identity_mismatch"
    OPTION_CONTRACT_IDENTITY_MISMATCH = (
        "option_contract_identity_mismatch"
    )
    SESSION_DATE_MISMATCH = "session_date_mismatch"
    MARKET_PHASE_MISMATCH = "market_phase_mismatch"
    QUOTE_SCOPE_MISMATCH = "quote_scope_mismatch"
    VENUE_MISMATCH = "venue_mismatch"
    ANALYTICS_METHODOLOGY_MISMATCH = "analytics_methodology_mismatch"
    ACTIVITY_COHERENCE_MISMATCH = "activity_coherence_mismatch"
    CONTRACT_REFERENCE_APPLICABILITY_MISMATCH = (
        "contract_reference_applicability_mismatch"
    )


_RELATIONSHIP_ROLE_RECORD_TYPES = {
    MarketDataRelationshipRole.UNDERLYING_QUOTE: UnderlyingQuoteObservation,
    MarketDataRelationshipRole.OPTION_QUOTE: OptionQuoteObservation,
    MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY: (
        OptionImpliedVolatilityObservation
    ),
    MarketDataRelationshipRole.OPTION_GREEKS: OptionGreeksObservation,
    MarketDataRelationshipRole.OPTION_VOLUME: OptionVolumeObservation,
    MarketDataRelationshipRole.OPTION_OPEN_INTEREST: (
        OptionOpenInterestObservation
    ),
    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE: (
        OptionContractReference
    ),
}


def _validate_relationship_resolved_bindings(
    group: MarketDataRelationshipGroup,
    resolved_bindings: object,
) -> Tuple[SelectedFreshMarketDataBinding, ...]:
    """Validate exact binding types and member-reference alignment."""

    if (
        type(resolved_bindings) is not tuple
        and type(resolved_bindings) is not list
    ):
        raise TypeError("resolved_bindings must be an exact tuple or list")
    for binding in resolved_bindings:
        if type(binding) is not SelectedFreshMarketDataBinding:
            raise TypeError(
                "every resolved_bindings item must have exact type "
                "SelectedFreshMarketDataBinding"
            )
    bindings = tuple(resolved_bindings)
    if len(bindings) != len(group.members):
        raise ValueError(
            "resolved_bindings must have one binding for every group member"
        )
    for member, binding in zip(group.members, bindings):
        if (
            binding.semantic_observation_key
            != member.reference.semantic_observation_key
            or binding.selected_record.metadata.record_id
            != member.reference.selected_record_id
        ):
            raise ValueError(
                "resolved_bindings must match group member references in order"
            )
    return bindings


def _relationship_records_by_role(
    group: MarketDataRelationshipGroup,
    bindings: Tuple[SelectedFreshMarketDataBinding, ...],
) -> dict:
    """Return exact selected records keyed by their declared group roles."""

    return {
        member.role: binding.selected_record
        for member, binding in zip(group.members, bindings)
    }


def _derive_quote_compatibility_issue_codes(
    underlying_quote: UnderlyingQuoteObservation,
    option_quote: OptionQuoteObservation,
) -> Tuple[MarketDataRelationshipIssueCode, ...]:
    """Derive narrow cross-quote phase, scope, and venue issues."""

    issues = set()
    if underlying_quote.market_phase is not option_quote.market_phase:
        issues.add(MarketDataRelationshipIssueCode.MARKET_PHASE_MISMATCH)
    if underlying_quote.quote_scope is not option_quote.quote_scope:
        issues.add(MarketDataRelationshipIssueCode.QUOTE_SCOPE_MISMATCH)
    elif (
        underlying_quote.quote_scope is QuoteScope.VENUE_SPECIFIC
        and underlying_quote.venue_mic != option_quote.venue_mic
    ):
        issues.add(MarketDataRelationshipIssueCode.VENUE_MISMATCH)
    return tuple(
        issue for issue in MarketDataRelationshipIssueCode if issue in issues
    )


def _derive_analytics_methodology_issue_codes(
    implied_volatility: OptionImpliedVolatilityObservation,
    greeks: OptionGreeksObservation,
) -> Tuple[MarketDataRelationshipIssueCode, ...]:
    """Compare one same-contract IV and Greeks methodology declaration."""

    if implied_volatility.contract_key != greeks.contract_key:
        return ()
    iv_methodology = (
        implied_volatility.model_name,
        implied_volatility.model_version,
        implied_volatility.rate_input_description,
        implied_volatility.dividend_input_description,
    )
    greeks_methodology = (
        greeks.model_name,
        greeks.model_version,
        greeks.rate_input_description,
        greeks.dividend_input_description,
    )
    if iv_methodology != greeks_methodology:
        return (
            MarketDataRelationshipIssueCode.ANALYTICS_METHODOLOGY_MISMATCH,
        )
    return ()


def _derive_activity_coherence_issue_codes(
    volume: OptionVolumeObservation,
    open_interest: OptionOpenInterestObservation,
) -> Tuple[MarketDataRelationshipIssueCode, ...]:
    """Evaluate one same-contract volume/open-interest session pairing."""

    if volume.contract_key != open_interest.contract_key:
        return ()
    open_interest_date = open_interest.open_interest_session_date
    if (
        open_interest_date > volume.session_date
        or (
            open_interest_date == volume.session_date
            and not volume.is_session_complete
        )
    ):
        return (MarketDataRelationshipIssueCode.ACTIVITY_COHERENCE_MISMATCH,)
    return ()


def _relationship_observation_session_date(
    role: MarketDataRelationshipRole,
    record: object,
) -> datetime.date:
    """Return the contracted applicability date for one observation role."""

    if role is MarketDataRelationshipRole.OPTION_OPEN_INTEREST:
        return record.open_interest_session_date
    return record.session_date


def _derive_contract_reference_applicability_issue_codes(
    contract_reference: OptionContractReference,
    records: dict,
) -> Tuple[MarketDataRelationshipIssueCode, ...]:
    """Check reference date bounds for identity-matching observations."""

    for role, record in records.items():
        if role is MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE:
            continue
        if record.contract_key != contract_reference.contract_key:
            continue
        observation_date = _relationship_observation_session_date(
            role, record
        )
        if (
            contract_reference.listing_date is not None
            and observation_date < contract_reference.listing_date
        ) or (
            contract_reference.last_trade_date is not None
            and observation_date > contract_reference.last_trade_date
        ):
            return (
                MarketDataRelationshipIssueCode
                .CONTRACT_REFERENCE_APPLICABILITY_MISMATCH,
            )
    return ()


def _derive_relationship_group_issue_codes(
    group: MarketDataRelationshipGroup,
    bindings: Tuple[SelectedFreshMarketDataBinding, ...],
) -> Tuple[MarketDataRelationshipIssueCode, ...]:
    """Derive all applicable 3C.4c through 3C.4e issues in enum order."""

    for member, binding in zip(group.members, bindings):
        if type(binding.selected_record) is not _RELATIONSHIP_ROLE_RECORD_TYPES[
            member.role
        ]:
            return (
                MarketDataRelationshipIssueCode.RESOLVED_RECORD_TYPE_MISMATCH,
            )

    records = _relationship_records_by_role(group, bindings)
    issues = set()
    kind = group.group_kind

    if kind is (
        MarketDataRelationshipGroupKind
        .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
    ):
        underlying_quote = records[
            MarketDataRelationshipRole.UNDERLYING_QUOTE
        ]
        option_quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        if (
            underlying_quote.underlying_key
            != option_quote.contract_key.underlying_key
        ):
            issues.add(
                MarketDataRelationshipIssueCode.UNDERLYING_IDENTITY_MISMATCH
            )
        if underlying_quote.session_date != option_quote.session_date:
            issues.add(MarketDataRelationshipIssueCode.SESSION_DATE_MISMATCH)
        issues.update(_derive_quote_compatibility_issue_codes(
            underlying_quote, option_quote
        ))

    elif kind is MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1:
        option_quote = records[MarketDataRelationshipRole.OPTION_QUOTE]
        analytics_roles = (
            MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
            MarketDataRelationshipRole.OPTION_GREEKS,
        )
        analytics_records = tuple(
            records[role] for role in analytics_roles if role in records
        )
        if any(
            record.contract_key != option_quote.contract_key
            for record in analytics_records
        ):
            issues.add(
                MarketDataRelationshipIssueCode
                .OPTION_CONTRACT_IDENTITY_MISMATCH
            )
        if any(
            record.session_date != option_quote.session_date
            for record in analytics_records
        ):
            issues.add(MarketDataRelationshipIssueCode.SESSION_DATE_MISMATCH)
        implied_volatility = records.get(
            MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY
        )
        greeks = records.get(MarketDataRelationshipRole.OPTION_GREEKS)
        if implied_volatility is not None and greeks is not None:
            issues.update(_derive_analytics_methodology_issue_codes(
                implied_volatility, greeks
            ))

    elif kind is MarketDataRelationshipGroupKind.OPTION_ACTIVITY_V0_1:
        volume = records[MarketDataRelationshipRole.OPTION_VOLUME]
        open_interest = records[
            MarketDataRelationshipRole.OPTION_OPEN_INTEREST
        ]
        option_quote = records.get(MarketDataRelationshipRole.OPTION_QUOTE)
        if (
            open_interest.contract_key != volume.contract_key
            or (
                option_quote is not None
                and option_quote.contract_key != volume.contract_key
            )
        ):
            issues.add(
                MarketDataRelationshipIssueCode
                .OPTION_CONTRACT_IDENTITY_MISMATCH
            )
        if (
            option_quote is not None
            and option_quote.session_date != volume.session_date
        ):
            issues.add(MarketDataRelationshipIssueCode.SESSION_DATE_MISMATCH)
        issues.update(_derive_activity_coherence_issue_codes(
            volume, open_interest
        ))

    else:
        contract_reference = records[
            MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
        ]
        non_reference_records = tuple(
            record
            for role, record in records.items()
            if role is not MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
        )
        if any(
            record.contract_key != contract_reference.contract_key
            for record in non_reference_records
        ):
            issues.add(
                MarketDataRelationshipIssueCode
                .OPTION_CONTRACT_IDENTITY_MISMATCH
            )
        issues.update(
            _derive_contract_reference_applicability_issue_codes(
                contract_reference, records
            )
        )

    return tuple(
        issue for issue in MarketDataRelationshipIssueCode if issue in issues
    )


@dataclass(frozen=True)
class MarketDataRelationshipGroupAssessment:
    """One immutable relationship assessment for a resolved group."""

    group: MarketDataRelationshipGroup
    resolved_bindings: Tuple[SelectedFreshMarketDataBinding, ...]

    def __post_init__(self) -> None:
        if type(self.group) is not MarketDataRelationshipGroup:
            raise TypeError(
                "group must have exact type MarketDataRelationshipGroup"
            )
        bindings = _validate_relationship_resolved_bindings(
            self.group, self.resolved_bindings
        )
        object.__setattr__(self, "resolved_bindings", bindings)

    @property
    def issue_codes(self) -> Tuple[MarketDataRelationshipIssueCode, ...]:
        """Return all applicable issues in declaration order."""

        return _derive_relationship_group_issue_codes(
            self.group, self.resolved_bindings
        )

    @property
    def is_coherent(self) -> bool:
        """Return whether the group has no relationship issue."""

        return not self.issue_codes


def _resolve_relationship_request_bindings(
    request: MarketDataRelationshipRequest,
    timing_assessment: MarketDataSnapshotTimingAssessment,
) -> Tuple[Tuple[SelectedFreshMarketDataBinding, ...], ...]:
    """Resolve every request reference before constructing any result."""

    return tuple(
        tuple(
            resolve_market_data_binding_reference(
                member.reference, timing_assessment
            )
            for member in group.members
        )
        for group in request.groups
    )


def _derive_relationship_group_assessments(
    request: MarketDataRelationshipRequest,
    timing_assessment: MarketDataSnapshotTimingAssessment,
) -> Tuple[MarketDataRelationshipGroupAssessment, ...]:
    """Resolve all groups, then construct canonical group assessments."""

    resolved_groups = _resolve_relationship_request_bindings(
        request, timing_assessment
    )
    return tuple(
        MarketDataRelationshipGroupAssessment(group, bindings)
        for group, bindings in zip(request.groups, resolved_groups)
    )


@dataclass(frozen=True)
class MarketDataRelationshipAssessment:
    """Immutable relationship assessment for one request and timing universe."""

    request: MarketDataRelationshipRequest
    timing_assessment: MarketDataSnapshotTimingAssessment

    def __post_init__(self) -> None:
        if type(self.request) is not MarketDataRelationshipRequest:
            raise TypeError(
                "request must have exact type MarketDataRelationshipRequest"
            )
        if (
            type(self.timing_assessment)
            is not MarketDataSnapshotTimingAssessment
        ):
            raise TypeError(
                "timing_assessment must have exact type "
                "MarketDataSnapshotTimingAssessment"
            )
        _resolve_relationship_request_bindings(
            self.request, self.timing_assessment
        )

    @property
    def group_assessments(
        self,
    ) -> Tuple[MarketDataRelationshipGroupAssessment, ...]:
        """Return group assessments in canonical request order."""

        return _derive_relationship_group_assessments(
            self.request, self.timing_assessment
        )

    @property
    def is_coherent(self) -> bool:
        """Return whether every requested relationship group is coherent."""

        return all(group.is_coherent for group in self.group_assessments)


def assess_market_data_relationships(
    request: object,
    timing_assessment: object,
) -> MarketDataRelationshipAssessment:
    """Assess implemented relationship coherence for one request."""

    return MarketDataRelationshipAssessment(request, timing_assessment)
