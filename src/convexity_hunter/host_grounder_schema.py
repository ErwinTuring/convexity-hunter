"""Strict parsing for the Host's untrusted model-output envelope."""

import json
import re
from datetime import date, datetime, timezone
from typing import Optional

from .event_intelligence import DistributionChangeMode, ReassessmentBasisKind


class ProducerJsonFormatError(ValueError):
    """Malformed producer JSON; contains no model-provided detail."""


class ProducerClosedShapeError(ValueError):
    """Producer DTO violates a closed object/container shape."""


# Source: https://data.iana.org/time-zones/tzdb/leap-seconds.list, updated
# through IERS Bulletin C. Future unknowns fail closed; update this list explicitly.
_KNOWN_LEAP_SECOND_UTC_DATES = frozenset(
    {
        "1972-06-30",
        "1972-12-31",
        "1973-12-31",
        "1974-12-31",
        "1975-12-31",
        "1976-12-31",
        "1977-12-31",
        "1978-12-31",
        "1979-12-31",
        "1981-06-30",
        "1982-06-30",
        "1983-06-30",
        "1985-06-30",
        "1987-12-31",
        "1989-12-31",
        "1990-12-31",
        "1992-06-30",
        "1993-06-30",
        "1994-06-30",
        "1995-12-31",
        "1997-06-30",
        "1998-12-31",
        "2005-12-31",
        "2008-12-31",
        "2012-06-30",
        "2015-06-30",
        "2016-12-31",
    }
)


def parse_model_output_envelope(
    raw_json: str,
    max_input_bytes: int,
    *,
    max_string_bytes: int,
    max_array_items: int,
) -> dict:
    """Parse and structurally validate one v0.1 model-output envelope.

    String/array limits are required caller inputs because the v0.1 contract
    does not assign values. Distribution modes are checked against the EI enum.
    This function validates only the untrusted DTO; it does not validate source
    receipts, build EI records, or call a model or assessor.
    """

    def require_positive_limit(value: object, name: str) -> None:
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")

    require_positive_limit(max_input_bytes, "max_input_bytes")
    require_positive_limit(max_string_bytes, "max_string_bytes")
    require_positive_limit(max_array_items, "max_array_items")

    if type(raw_json) is not str:
        raise ValueError("raw_json must be a string")
    try:
        encoded_input = raw_json.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("raw_json is not valid UTF-8 text") from exc
    if len(encoded_input) > max_input_bytes:
        raise ValueError("raw_json exceeds max_input_bytes")

    def bounded_string(value: object, label: str, *, nonempty: bool = True) -> str:
        if type(value) is not str:
            raise ValueError(f"{label} must be a string")
        if nonempty and not value:
            raise ValueError(f"{label} must be nonempty")
        try:
            encoded_value = value.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError(f"{label} is not valid UTF-8 text") from exc
        if len(encoded_value) > max_string_bytes:
            raise ValueError(f"{label} exceeds max_string_bytes")
        return value

    def enforce_decoded_string_limits(value: object, label: str = "JSON") -> None:
        if type(value) is str:
            bounded_string(value, label, nonempty=False)
        elif type(value) is list:
            for index, item in enumerate(value):
                enforce_decoded_string_limits(item, f"{label}[{index}]")
        elif type(value) is dict:
            for key, item in value.items():
                bounded_string(key, f"{label} object key", nonempty=False)
                enforce_decoded_string_limits(item, f"{label}.{key}")

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def reject_nonfinite(token: str) -> None:
        raise ValueError(f"non-finite JSON number is not permitted: {token}")

    parsed = json.loads(
        raw_json,
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_nonfinite,
    )
    enforce_decoded_string_limits(parsed)
    if type(parsed) is not dict:
        raise ValueError("model output must be one top-level JSON object")

    def closed_object(value: object, keys: set[str], label: str) -> dict:
        if type(value) is not dict:
            raise ProducerClosedShapeError("producer DTO must be an object")
        actual = set(value)
        missing = keys - actual
        unknown = actual - keys
        if missing:
            raise ProducerClosedShapeError("producer DTO is missing required fields")
        if unknown:
            raise ProducerClosedShapeError("producer DTO contains unknown fields")
        return value

    def bounded_array(value: object, label: str, *, nonempty: bool = False) -> list:
        if type(value) is not list:
            raise ProducerClosedShapeError("producer DTO must be an array")
        if len(value) > max_array_items:
            raise ValueError(f"{label} exceeds max_array_items")
        if nonempty and not value:
            raise ValueError(f"{label} must be nonempty")
        return value

    def string_array(
        value: object, label: str, *, items_nonempty: bool = False
    ) -> list[str]:
        items = bounded_array(value, label)
        for index, item in enumerate(items):
            bounded_string(
                item,
                f"{label}[{index}]",
                nonempty=items_nonempty,
            )
        return items

    def nullable_string(value: object, label: str) -> Optional[str]:
        if value is None:
            return None
        return bounded_string(value, label)

    def strict_date(value: object, label: str) -> str:
        text = bounded_string(value, label)
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text) is None:
            raise ValueError(f"{label} must use YYYY-MM-DD")
        try:
            date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"{label} is not a calendar date") from exc
        return text

    rfc3339_pattern = re.compile(
        r"(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})[Tt]"
        r"(?P<clock>(?:[01][0-9]|2[0-3]):[0-5][0-9]:(?P<second>[0-5][0-9]|60))"
        r"(?:\.[0-9]+)?"
        r"(?P<offset>[Zz]|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
    )

    def strict_rfc3339(value: object, label: str) -> str:
        text = bounded_string(value, label)
        match = rfc3339_pattern.fullmatch(text)
        if match is None:
            raise ValueError(f"{label} must be an aware RFC3339 timestamp")
        # Fractional digits were validated by the regex and are deliberately
        # omitted here for Python 3.9 compatibility; retain them in `text`.
        validation_clock = match.group("clock")
        is_leap_second = match.group("second") == "60"
        if is_leap_second:
            validation_clock = validation_clock[:-2] + "59"
        validation_text = match.group("date") + "T" + validation_clock
        offset = match.group("offset")
        iso_text = validation_text + (
            "+00:00" if offset.lower() == "z" else offset
        )
        try:
            parsed_datetime = datetime.fromisoformat(iso_text)
        except ValueError as exc:
            raise ValueError(f"{label} is not a valid RFC3339 timestamp") from exc
        if parsed_datetime.utcoffset() is None:
            raise ValueError(f"{label} must include a timezone")
        if is_leap_second:
            utc_equivalent = parsed_datetime.astimezone(timezone.utc)
            permitted_leap_position = (
                utc_equivalent.hour == 23
                and utc_equivalent.minute == 59
                and utc_equivalent.date().isoformat() in _KNOWN_LEAP_SECOND_UTC_DATES
            )
            if not permitted_leap_position:
                raise ValueError(f"{label} has an unknown or invalid UTC leap-second date")
        return text

    envelope_keys = {
        "schema_version",
        "stage",
        "request_id",
        "claims",
        "hypotheses",
        "coverage",
        "field_bindings",
    }
    claim_keys = {
        "claim_id",
        "kind",
        "source_id",
        "locator",
        "quote",
        "text",
        "entity_refs",
        "event_date",
        "published_at",
        "dependency_claim_ids",
        "uncertainty",
        "falsification_conditions",
    }
    hypothesis_keys = {
        "hypothesis_id",
        "underlying_symbol",
        "impact_path",
        "distribution_mode",
        "distribution_hypothesis",
        "expected_window",
        "reassessment",
        "supporting_claim_ids",
        "contradicting_claim_ids",
        "contradiction_review",
        "uncertainties",
        "falsification_conditions",
    }
    coverage_keys = {"subquestion_id", "status", "claim_ids", "gap"}
    binding_keys = {
        "field_path",
        "source_id",
        "quote",
        "start",
        "end",
        "semantic_role",
        "status",
    }

    envelope = closed_object(parsed, envelope_keys, "envelope")
    if envelope["schema_version"] != "grounder-output-v0.1":
        raise ValueError("schema_version must be grounder-output-v0.1")
    if envelope["stage"] not in ("discovery", "semantic"):
        raise ValueError("stage must be discovery or semantic")
    bounded_string(envelope["request_id"], "request_id")

    claims = bounded_array(envelope["claims"], "claims")
    hypotheses = bounded_array(envelope["hypotheses"], "hypotheses")
    coverage = bounded_array(envelope["coverage"], "coverage")
    field_bindings = bounded_array(envelope["field_bindings"], "field_bindings")

    for index, raw_claim in enumerate(claims):
        label = f"claims[{index}]"
        claim = closed_object(raw_claim, claim_keys, label)
        for key in ("claim_id", "source_id", "locator", "quote", "text"):
            bounded_string(claim[key], f"{label}.{key}")
        if claim["kind"] not in ("observed_fact", "interpretation"):
            raise ValueError(f"{label}.kind is invalid")
        string_array(claim["entity_refs"], f"{label}.entity_refs", items_nonempty=True)
        if claim["event_date"] is not None:
            strict_date(claim["event_date"], f"{label}.event_date")
        if claim["published_at"] is not None:
            strict_rfc3339(claim["published_at"], f"{label}.published_at")
        for key in (
            "dependency_claim_ids",
            "uncertainty",
            "falsification_conditions",
        ):
            string_array(claim[key], f"{label}.{key}")

    for index, raw_hypothesis in enumerate(hypotheses):
        label = f"hypotheses[{index}]"
        hypothesis = closed_object(raw_hypothesis, hypothesis_keys, label)
        bounded_string(hypothesis["hypothesis_id"], f"{label}.hypothesis_id")
        for key in ("underlying_symbol", "impact_path", "distribution_hypothesis"):
            nullable_string(hypothesis[key], f"{label}.{key}")
        mode = hypothesis["distribution_mode"]
        if mode is not None:
            bounded_string(mode, f"{label}.distribution_mode")
            if mode not in {member.value for member in DistributionChangeMode}:
                raise ValueError(f"{label}.distribution_mode is not an allowed EI mode")

        window = hypothesis["expected_window"]
        if window is not None:
            window = closed_object(
                window,
                {"start_date", "end_date", "methodology"},
                f"{label}.expected_window",
            )
            strict_date(window["start_date"], f"{label}.expected_window.start_date")
            strict_date(window["end_date"], f"{label}.expected_window.end_date")
            bounded_string(window["methodology"], f"{label}.expected_window.methodology")

        reassessment = hypothesis["reassessment"]
        if reassessment is not None:
            reassessment = closed_object(
                reassessment,
                {"reassessment_by", "methodology", "basis_kind", "basis_claim_ids"},
                f"{label}.reassessment",
            )
            strict_date(
                reassessment["reassessment_by"],
                f"{label}.reassessment.reassessment_by",
            )
            bounded_string(reassessment["methodology"], f"{label}.reassessment.methodology")
            basis_kind = bounded_string(
                reassessment["basis_kind"], f"{label}.reassessment.basis_kind"
            )
            if basis_kind not in {member.value for member in ReassessmentBasisKind}:
                raise ValueError(f"{label}.reassessment.basis_kind is invalid")
            string_array(
                reassessment["basis_claim_ids"],
                f"{label}.reassessment.basis_claim_ids",
            )

        for key in ("supporting_claim_ids", "contradicting_claim_ids", "uncertainties", "falsification_conditions"):
            string_array(hypothesis[key], f"{label}.{key}")
        nullable_string(hypothesis["contradiction_review"], f"{label}.contradiction_review")

    for index, raw_coverage in enumerate(coverage):
        label = f"coverage[{index}]"
        item = closed_object(raw_coverage, coverage_keys, label)
        bounded_string(item["subquestion_id"], f"{label}.subquestion_id")
        if item["status"] not in ("supported", "unresolved", "contradicted"):
            raise ValueError(f"{label}.status is invalid")
        string_array(item["claim_ids"], f"{label}.claim_ids")
        nullable_string(item["gap"], f"{label}.gap")

    canonical_index = re.compile(r"(?:0|[1-9][0-9]*)")

    def resolve_index(text: str, size: int, label: str) -> int:
        if canonical_index.fullmatch(text) is None:
            raise ValueError(f"{label} must be a canonical decimal index")
        try:
            value = int(text)
        except ValueError as exc:
            raise ValueError(f"{label} is outside the supported index range") from exc
        if value >= size:
            raise ValueError(f"{label} is out of bounds")
        return value

    def validate_field_path(path: str, role: str, label: str) -> None:
        match = re.fullmatch(
            r"/hypotheses/((?:0|[1-9][0-9]*))/(impact_path|distribution_mode|distribution_hypothesis)",
            path,
        )
        expected_role = None
        terminal: object = None
        if match is not None:
            hypothesis_index = resolve_index(match.group(1), len(hypotheses), f"{label}.field_path index")
            terminal_key = match.group(2)
            expected_role = "hypothesis"
            terminal = hypotheses[hypothesis_index][terminal_key]
        else:
            match = re.fullmatch(r"/claims/((?:0|[1-9][0-9]*))/event_date", path)
            if match is not None:
                claim_index = resolve_index(match.group(1), len(claims), f"{label}.field_path index")
                expected_role = "date"
                terminal = claims[claim_index]["event_date"]
            else:
                match = re.fullmatch(
                    r"/hypotheses/((?:0|[1-9][0-9]*))/expected_window/(start_date|end_date)",
                    path,
                )
                if match is not None:
                    hypothesis_index = resolve_index(match.group(1), len(hypotheses), f"{label}.field_path index")
                    window = hypotheses[hypothesis_index]["expected_window"]
                    expected_role = "date"
                    terminal = None if window is None else window[match.group(2)]
                else:
                    match = re.fullmatch(
                        r"/hypotheses/((?:0|[1-9][0-9]*))/reassessment/reassessment_by",
                        path,
                    )
                    if match is not None:
                        hypothesis_index = resolve_index(match.group(1), len(hypotheses), f"{label}.field_path index")
                        reassessment = hypotheses[hypothesis_index]["reassessment"]
                        expected_role = "date"
                        terminal = None if reassessment is None else reassessment["reassessment_by"]
                    else:
                        match = re.fullmatch(
                            r"/claims/((?:0|[1-9][0-9]*))/entity_refs/((?:0|[1-9][0-9]*))",
                            path,
                        )
                        if match is not None:
                            claim_index = resolve_index(match.group(1), len(claims), f"{label}.field_path claim index")
                            entity_index = resolve_index(
                                match.group(2),
                                len(claims[claim_index]["entity_refs"]),
                                f"{label}.field_path entity index",
                            )
                            expected_role = "entity"
                            terminal = claims[claim_index]["entity_refs"][entity_index]
                        else:
                            match = re.fullmatch(
                                r"/hypotheses/((?:0|[1-9][0-9]*))/underlying_symbol",
                                path,
                            )
                            if match is not None:
                                hypothesis_index = resolve_index(
                                    match.group(1), len(hypotheses), f"{label}.field_path index"
                                )
                                expected_role = "entity"
                                terminal = hypotheses[hypothesis_index]["underlying_symbol"]

        if expected_role is None:
            raise ValueError(f"{label}.field_path is not permitted")
        if role != expected_role:
            raise ValueError(f"{label}.semantic_role does not match field_path")
        if terminal is None or terminal == "":
            raise ValueError(f"{label}.field_path must resolve to a non-null value")

    for index, raw_binding in enumerate(field_bindings):
        label = f"field_bindings[{index}]"
        binding = closed_object(raw_binding, binding_keys, label)
        field_path = bounded_string(binding["field_path"], f"{label}.field_path")
        bounded_string(binding["source_id"], f"{label}.source_id")
        bounded_string(binding["quote"], f"{label}.quote")
        start = binding["start"]
        end = binding["end"]
        if type(start) is not int or start < 0:
            raise ValueError(f"{label}.start must be a nonnegative integer")
        if type(end) is not int or end <= start:
            raise ValueError(f"{label}.end must be greater than start")
        role = binding["semantic_role"]
        if role not in ("hypothesis", "date", "entity"):
            raise ValueError(f"{label}.semantic_role is invalid")
        if binding["status"] not in ("supported", "unresolved", "contradicted"):
            raise ValueError(f"{label}.status is invalid")
        validate_field_path(field_path, role, label)

    return envelope
