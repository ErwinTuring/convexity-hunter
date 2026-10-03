"""Closed JSON codec for the current typed Core research result."""

import dataclasses
import datetime
import decimal
import json
from enum import Enum
from fractions import Fraction

from . import core_research as core
from .market_data import DataOrigin, SourceQualityFlag, SourceReference
from .market_data_transformations import (
    TailPricingTransformationResult,
    VolatilityEnvironmentTransformationResult,
)


VERSION = "host-core-result-v0.1"

_DATACLASSES = (
    SourceReference,
    core.CoreProvenance,
    core.CoreLeg,
    core.CoreStructure,
    core.CorePayoffModel,
    core.CoreCostComponent,
    core.CoreCostLedger,
    core.CoreRiskRepeatPolicy,
    core.CoreSensitivityPoint,
    core.CoreSensitivity,
    core.CoreReviewedEnhancements,
    core.CoreResearchRequest,
    core.CoreHurdle,
    core.CoreGeometry,
    core.CoreCashLedgerView,
    core.CoreBudgetStress,
    core.CoreSensitivityResultPoint,
    core.CoreSensitivityResult,
    core.CoreResearchResult,
)
_ENUMS = (
    DataOrigin,
    SourceQualityFlag,
    core.CoreOptionType,
    core.CoreAskAuthority,
    core.CorePayoffAuthority,
    core.CoreCostComponentStatus,
    core.CoreDisposition,
    core.CoreGeometryStatus,
    core.CoreHurdleSide,
    core.CoreHurdleStatus,
    core.CoreBudgetStatus,
    core.CoreReasonCode,
)
_TYPE_TAGS = {
    cls: ("market_data." if cls is SourceReference else "core_research.")
    + cls.__name__
    for cls in _DATACLASSES
}
_TAG_TYPES = {tag: cls for cls, tag in _TYPE_TAGS.items()}
_ENUM_TAGS = {cls: cls.__module__.rsplit(".", 1)[-1] + "." + cls.__name__ for cls in _ENUMS}
_TAG_ENUMS = {tag: cls for cls, tag in _ENUM_TAGS.items()}
_RESULT_OMIT = frozenset(("request",))


def _keys(value, expected):
    if type(value) is not dict:
        raise TypeError("snapshot records must be dictionaries")
    if set(value) != set(expected):
        raise ValueError("snapshot record has unknown or missing fields")


def _encode_datetime(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive datetimes are not supported")
    if type(value.tzinfo) is not datetime.timezone:
        raise TypeError("datetime timezone must be a fixed datetime.timezone")
    return {
        "$datetime": value.isoformat(),
        "tzname": value.tzname(),
        "fold": value.fold,
    }


def _encode_value(value):
    value_type = type(value)
    if value is None or value_type in (str, bool, int):
        return value
    if value_type in _ENUM_TAGS:
        return {"$enum": _ENUM_TAGS[value_type], "value": value.value}
    if value_type is decimal.Decimal:
        if not value.is_finite():
            raise ValueError("non-finite Decimal values are not supported")
        return {"$decimal": str(value)}
    if value_type is Fraction:
        return {"$fraction": [value.numerator, value.denominator]}
    if value_type is datetime.datetime:
        return _encode_datetime(value)
    if value_type is datetime.date:
        return {"$date": value.isoformat()}
    if value_type is tuple:
        return {"$tuple": [_encode_value(item) for item in value]}
    if value_type in (
        VolatilityEnvironmentTransformationResult,
        TailPricingTransformationResult,
    ):
        raise TypeError("reviewed volatility/tail artifacts are unsupported by v0.1")
    if value_type in _TYPE_TAGS:
        fields = {field.name: _encode_value(getattr(value, field.name))
                  for field in dataclasses.fields(value)}
        return {"$type": _TYPE_TAGS[value_type], **fields}
    raise TypeError("unsupported Core snapshot payload type: " + value_type.__name__)


def _decode_datetime(value):
    _keys(value, ("$datetime", "tzname", "fold"))
    text, name, fold = value["$datetime"], value["tzname"], value["fold"]
    if type(text) is not str or type(name) is not str:
        raise TypeError("datetime fields must be strings")
    if type(fold) is not int or fold not in (0, 1):
        raise TypeError("datetime fold must be integer 0 or 1")
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError("invalid datetime snapshot") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("snapshot datetimes must be timezone-aware")
    if parsed.isoformat() != text:
        raise ValueError("datetime snapshot must use canonical ISO format")
    result = parsed.replace(
        tzinfo=datetime.timezone(parsed.utcoffset(), name), fold=fold
    )
    if result.tzname() != name:
        raise ValueError("datetime timezone name did not round-trip")
    return result


def _decode_value(value):
    value_type = type(value)
    if value is None or value_type in (str, bool, int):
        return value
    if value_type is not dict:
        raise TypeError("unsupported JSON snapshot value")
    if "$type" in value:
        tag = value["$type"]
        if type(tag) is not str or tag not in _TAG_TYPES:
            raise ValueError("unknown Core snapshot type tag")
        cls = _TAG_TYPES[tag]
        field_names = tuple(field.name for field in dataclasses.fields(cls))
        _keys(value, ("$type",) + field_names)
        return cls(**{
            name: _decode_value(value[name]) for name in field_names
        })
    if "$enum" in value:
        _keys(value, ("$enum", "value"))
        tag, raw = value["$enum"], value["value"]
        if type(tag) is not str or tag not in _TAG_ENUMS:
            raise ValueError("unknown Core snapshot enum tag")
        if type(raw) is not str:
            raise TypeError("enum value must be a string")
        try:
            return _TAG_ENUMS[tag](raw)
        except ValueError as error:
            raise ValueError("unknown value for Core snapshot enum") from error
    if "$decimal" in value:
        _keys(value, ("$decimal",))
        raw = value["$decimal"]
        if type(raw) is not str:
            raise TypeError("Decimal snapshot value must be a string")
        try:
            result = decimal.Decimal(raw)
        except decimal.InvalidOperation as error:
            raise ValueError("invalid Decimal snapshot value") from error
        if not result.is_finite() or str(result) != raw:
            raise ValueError("Decimal snapshot value must be finite and canonical")
        return result
    if "$fraction" in value:
        _keys(value, ("$fraction",))
        pair = value["$fraction"]
        if type(pair) is not list or len(pair) != 2:
            raise TypeError("Fraction snapshot value must be a pair")
        numerator, denominator = pair
        if type(numerator) is not int or type(denominator) is not int:
            raise TypeError("Fraction numerator and denominator must be integers")
        result = Fraction(numerator, denominator)
        if (result.numerator, result.denominator) != (numerator, denominator):
            raise ValueError("Fraction snapshot value must be reduced and canonical")
        return result
    if "$datetime" in value:
        return _decode_datetime(value)
    if "$date" in value:
        _keys(value, ("$date",))
        raw = value["$date"]
        if type(raw) is not str:
            raise TypeError("date snapshot value must be a string")
        try:
            result = datetime.date.fromisoformat(raw)
        except ValueError as error:
            raise ValueError("invalid date snapshot value") from error
        if result.isoformat() != raw:
            raise ValueError("date snapshot value must use canonical ISO format")
        return result
    if "$tuple" in value:
        _keys(value, ("$tuple",))
        items = value["$tuple"]
        if type(items) is not list:
            raise TypeError("tuple snapshot items must be an array")
        return tuple(_decode_value(item) for item in items)
    raise ValueError("unknown Core snapshot tag")


def _encode_result_fields(result):
    return {
        "$type": _TYPE_TAGS[core.CoreResearchResult],
        **{
            field.name: _encode_value(getattr(result, field.name))
            for field in dataclasses.fields(result)
            if field.name not in _RESULT_OMIT
        },
    }


def _same_snapshot_tree(left, right):
    options = {
        "ensure_ascii": False,
        "allow_nan": False,
        "sort_keys": True,
        "separators": (",", ":"),
    }
    return json.dumps(left, **options) == json.dumps(right, **options)


def _validate_result(result):
    if type(result) is not core.CoreResearchResult:
        raise TypeError("result must have exact type CoreResearchResult")
    expected = core.evaluate_core_research(result.request)
    if not _same_snapshot_tree(
        _encode_result_fields(result), _encode_result_fields(expected)
    ):
        raise ValueError("CoreResearchResult does not match deterministic evaluation")
    return expected


def encode_core_result(result):
    """Encode one current Core result as a strict JSON-native snapshot."""

    _validate_result(result)
    request = _encode_value(result.request)
    result_fields = _encode_result_fields(result)
    # Validate every retained request value, including unsupported artifacts.
    return {"version": VERSION, "request": request, "result": result_fields}


def decode_core_result(snapshot):
    """Decode and verify a v0.1 Core snapshot without loading external types."""

    _keys(snapshot, ("version", "request", "result"))
    if type(snapshot["version"]) is not str or snapshot["version"] != VERSION:
        raise ValueError("unsupported Host Core snapshot version")
    request = _decode_value(snapshot["request"])
    if type(request) is not core.CoreResearchRequest:
        raise TypeError("snapshot request must be CoreResearchRequest")
    result_tree = snapshot["result"]
    result_fields = tuple(
        field.name for field in dataclasses.fields(core.CoreResearchResult)
        if field.name not in _RESULT_OMIT
    )
    _keys(result_tree, ("$type",) + result_fields)
    if result_tree["$type"] != _TYPE_TAGS[core.CoreResearchResult]:
        raise ValueError("snapshot result must be CoreResearchResult")
    decoded_fields = {
        name: _decode_value(result_tree[name]) for name in result_fields
    }
    if _encode_value(decoded_fields["reviewed_enhancements"]) != _encode_value(
        request.reviewed_enhancements
    ):
        raise ValueError("stored reviewed enhancements do not match the request")
    decoded_result = core.CoreResearchResult(
        request=request,
        **{
            name: (request.reviewed_enhancements if name == "reviewed_enhancements"
                   else value)
            for name, value in decoded_fields.items()
        },
    )
    expected = core.evaluate_core_research(request)
    if not _same_snapshot_tree(
        _encode_result_fields(decoded_result), _encode_result_fields(expected)
    ):
        raise ValueError("stored Core result does not match deterministic evaluation")
    return decoded_result
