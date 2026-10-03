"""Strict JSON adapter from user-declared Direct legs into existing Core."""

from __future__ import annotations

import datetime
import decimal
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from .core_application import CoreDirectResult, CoreOperationalBounds, run_direct_core
from .core_research import (
    CoreAskAuthority,
    CoreLeg,
    CoreOptionType,
    CoreProvenance,
    CoreStructure,
)
from .host_profile import STANDARD_RESEARCH_PROFILE, create_core_research_policy
from .option_chain_discovery import OptionMaturityAuthority
from .providers.futu import _decode_identifier


SCHEMA_VERSION = "host-direct-input-v0.1"
_TOP_LEVEL_FIELDS = frozenset(("schema_version", "evaluation_date", "structure", "legs"))
_LEG_FIELDS = frozenset(
    (
        "provider_identifier",
        "underlying",
        "currency",
        "option_type",
        "strike",
        "expiration",
        "quantity",
        "contract_multiplier",
    )
)
_STRUCTURE_KINDS = frozenset(("LONG_CALL", "LONG_PUT", "LONG_STRADDLE"))
_OPTION_TYPES = frozenset(("CALL", "PUT"))
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z", re.ASCII)
_DECIMAL_RE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z", re.ASCII)
_SYMBOL_RE = re.compile(r"[A-Z0-9][A-Z0-9._-]{0,63}\Z", re.ASCII)
_FUTU_ID_RE = re.compile(
    r"US\.[A-Z0-9][A-Z0-9._-]*[0-9]{6}[CP][0-9]+\Z", re.ASCII
)


class HostDirectInputError(ValueError):
    """The exact host-direct-input-v0.1 JSON schema or value is invalid."""


class HostDirectBoundsError(ValueError):
    """Direct execution violates the caller's explicit operational bounds."""


@dataclass(frozen=True)
class ParsedDirectInput:
    evaluation_date: datetime.date
    structure: CoreStructure


@dataclass(frozen=True)
class _ParsedLeg:
    provider_identifier: str
    underlying: str
    currency: str
    option_type: CoreOptionType
    strike: decimal.Decimal
    expiration: datetime.date
    quantity: int
    contract_multiplier: int


class _DuplicateJSONKey(ValueError):
    pass


def _unique_object(pairs: list[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey()
        result[key] = value
    return result


def _reject_json_constant(_value: str) -> None:
    raise ValueError("non-finite JSON constant")


def _reject_json_float(_value: str) -> None:
    # All schema decimals are strings. Numeric JSON floats, including 1e999,
    # are unnecessary and may be non-finite.
    raise ValueError("JSON floating-point values are not accepted")


def _parse_document(raw_input: str) -> Dict[str, Any]:
    if type(raw_input) is not str:
        raise HostDirectInputError("input must be UTF-8 JSON text")
    try:
        raw_input.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise HostDirectInputError("input must be UTF-8 JSON text") from None
    if raw_input.lstrip().startswith(chr(96) * 3):
        raise HostDirectInputError("code fences are not accepted")
    try:
        value = json.loads(
            raw_input,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
            parse_float=_reject_json_float,
        )
    except (json.JSONDecodeError, _DuplicateJSONKey, RecursionError, ValueError):
        raise HostDirectInputError(
            "input is not valid host-direct-input-v0.1 JSON"
        ) from None
    if type(value) is not dict or set(value) != _TOP_LEVEL_FIELDS:
        raise HostDirectInputError("top-level fields do not match the schema")
    if (
        type(value["schema_version"]) is not str
        or value["schema_version"] != SCHEMA_VERSION
    ):
        raise HostDirectInputError("schema_version is unsupported")
    return value


def _parse_date(name: str, value: Any) -> datetime.date:
    if type(value) is not str or _DATE_RE.fullmatch(value) is None:
        raise HostDirectInputError("{} must be a strict ISO date".format(name))
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError:
        raise HostDirectInputError(
            "{} must be a strict ISO date".format(name)
        ) from None
    if parsed.isoformat() != value:
        raise HostDirectInputError("{} must be a strict ISO date".format(name))
    return parsed


def _parse_decimal(name: str, value: Any) -> decimal.Decimal:
    if type(value) is not str or _DECIMAL_RE.fullmatch(value) is None:
        raise HostDirectInputError(
            "{} must be an exact positive decimal string".format(name)
        )
    try:
        parsed = decimal.Decimal(value)
    except decimal.InvalidOperation:
        raise HostDirectInputError(
            "{} must be an exact positive decimal string".format(name)
        ) from None
    if not parsed.is_finite() or parsed <= 0:
        raise HostDirectInputError(
            "{} must be an exact positive decimal string".format(name)
        )
    return parsed


def _parse_leg(value: Any) -> _ParsedLeg:
    if type(value) is not dict or set(value) != _LEG_FIELDS:
        raise HostDirectInputError("leg fields do not match the schema")

    provider_identifier = value["provider_identifier"]
    underlying = value["underlying"]
    currency = value["currency"]
    option_type = value["option_type"]
    if (
        type(provider_identifier) is not str
        or not provider_identifier.isascii()
        or _FUTU_ID_RE.fullmatch(provider_identifier) is None
    ):
        raise HostDirectInputError("provider_identifier is invalid")
    if type(underlying) is not str or _SYMBOL_RE.fullmatch(underlying) is None:
        raise HostDirectInputError("underlying is invalid")
    if type(currency) is not str or currency != "USD":
        raise HostDirectInputError("currency is unsupported")
    if type(option_type) is not str or option_type not in _OPTION_TYPES:
        raise HostDirectInputError("option_type is invalid")

    strike = _parse_decimal("strike", value["strike"])
    expiration = _parse_date("expiration", value["expiration"])
    quantity = value["quantity"]
    contract_multiplier = value["contract_multiplier"]
    if type(quantity) is not int or quantity <= 0:
        raise HostDirectInputError("quantity must be an exact positive integer")
    if type(contract_multiplier) is not int or contract_multiplier <= 0:
        raise HostDirectInputError(
            "contract_multiplier must be an explicit positive integer"
        )

    # This parser is pure and does not open a provider context. Core performs
    # the authoritative verification against every declared CoreLeg identity.
    try:
        root, identifier_expiration, identifier_type, identifier_strike = (
            _decode_identifier(provider_identifier)
        )
    except Exception:
        raise HostDirectInputError("provider_identifier is invalid") from None
    if (
        root != underlying
        or identifier_expiration != expiration
        or identifier_type != option_type.lower()
        or identifier_strike != strike
    ):
        raise HostDirectInputError(
            "provider_identifier does not match the declared leg identity"
        )

    return _ParsedLeg(
        provider_identifier=provider_identifier,
        underlying=underlying,
        currency=currency,
        option_type=CoreOptionType[option_type],
        strike=strike,
        expiration=expiration,
        quantity=quantity,
        contract_multiplier=contract_multiplier,
    )


def parse_direct_input(raw_input: str) -> ParsedDirectInput:
    """Parse the closed Direct schema and construct a source-neutral Core shape."""

    document = _parse_document(raw_input)
    evaluation_date = _parse_date("evaluation_date", document["evaluation_date"])
    structure_kind = document["structure"]
    if type(structure_kind) is not str or structure_kind not in _STRUCTURE_KINDS:
        raise HostDirectInputError("structure is unsupported")
    raw_legs = document["legs"]
    if type(raw_legs) is not list:
        raise HostDirectInputError("legs must be an array")
    parsed_legs = tuple(_parse_leg(value) for value in raw_legs)
    if len({leg.provider_identifier for leg in parsed_legs}) != len(parsed_legs):
        raise HostDirectInputError("provider identifiers must be unique")

    if structure_kind == "LONG_CALL":
        valid_shape = (
            len(parsed_legs) == 1
            and parsed_legs[0].option_type is CoreOptionType.CALL
        )
    elif structure_kind == "LONG_PUT":
        valid_shape = (
            len(parsed_legs) == 1
            and parsed_legs[0].option_type is CoreOptionType.PUT
        )
    else:
        valid_shape = (
            len(parsed_legs) == 2
            and {leg.option_type for leg in parsed_legs}
            == {CoreOptionType.CALL, CoreOptionType.PUT}
        )
        if valid_shape:
            first, second = parsed_legs
            valid_shape = all(
                getattr(first, field) == getattr(second, field)
                for field in (
                    "underlying",
                    "currency",
                    "strike",
                    "expiration",
                    "quantity",
                    "contract_multiplier",
                )
            )
    if not valid_shape:
        raise HostDirectInputError("legs do not match the declared structure")

    provenance = CoreProvenance(
        source_reference=None,
        description=(
            "User-declared host-direct-input-v0.1; no source reference supplied."
        ),
    )
    try:
        legs = tuple(
            CoreLeg(
                leg_id=leg.provider_identifier,
                underlying=leg.underlying,
                currency=leg.currency,
                option_type=leg.option_type,
                strike=leg.strike,
                expiration=leg.expiration,
                quantity=leg.quantity,
                # Required user expectation only; exact verification is
                # authoritative for the provider's multiplier.
                contract_multiplier=leg.contract_multiplier,
                ask_per_underlying_unit=None,
                ask_authority=CoreAskAuthority.INDICATIVE_ONLY,
                description="User-declared exact contract terms; ask not supplied.",
                provenance=provenance,
            )
            for leg in parsed_legs
        )
        structure = CoreStructure(
            legs=legs,
            description="User-declared {} shape.".format(structure_kind),
            provenance=provenance,
        )
    except (TypeError, ValueError):
        raise HostDirectInputError("declared Core structure is invalid") from None
    return ParsedDirectInput(evaluation_date=evaluation_date, structure=structure)


def run_direct_input(
    raw_input: str,
    *,
    bounds: CoreOperationalBounds,
    exact_provider_bridge: object,
    direct_quote_evidence: object = None,
) -> CoreDirectResult:
    """Run parsed user terms through the existing exact-verification Core path."""

    parsed = parse_direct_input(raw_input)
    if type(bounds) is not CoreOperationalBounds:
        raise HostDirectBoundsError("bounds must be CoreOperationalBounds")
    if bounds.max_cases < 1:
        raise HostDirectBoundsError("max_cases must permit at least one Direct case")
    policy = create_core_research_policy(
        profile=STANDARD_RESEARCH_PROFILE,
        evaluation_date=parsed.evaluation_date,
        maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
        bounds=bounds,
    )
    return run_direct_core(
        parsed.structure,
        exact_provider_bridge=exact_provider_bridge,
        direct_quote_evidence=direct_quote_evidence,
        policy=policy,
    )


__all__ = (
    "HostDirectBoundsError",
    "HostDirectInputError",
    "ParsedDirectInput",
    "parse_direct_input",
    "run_direct_input",
)
