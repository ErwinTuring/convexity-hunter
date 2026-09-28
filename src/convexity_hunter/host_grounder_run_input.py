"""Pure construction and binding checks for an immutable Event run input."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Tuple

from .event_entry import UserEventInput


__all__ = (
    "HostGrounderRunInputBounds",
    "HostGrounderSubquestion",
    "HostGrounderRunInput",
    "validate_host_context_binding",
    "validate_ordered_coverage_ids",
)


def _positive_int(value: object, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("{} must be a positive integer".format(name))
    return value


def _bounded_text(value: object, name: str, max_string_bytes: int) -> str:
    if type(value) is not str or not value:
        raise ValueError("{} must be a nonempty string".format(name))
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ValueError("{} is not valid UTF-8".format(name)) from exc
    if len(encoded) > max_string_bytes:
        raise ValueError("{} exceeds max_string_bytes".format(name))
    return value


@dataclass(frozen=True)
class HostGrounderRunInputBounds:
    """Explicit Host-configured limits; no default or model-selected values."""

    max_run_input_bytes: int
    max_string_bytes: int
    max_array_items: int

    def __post_init__(self) -> None:
        _positive_int(self.max_run_input_bytes, "max_run_input_bytes")
        _positive_int(self.max_string_bytes, "max_string_bytes")
        _positive_int(self.max_array_items, "max_array_items")


@dataclass(frozen=True)
class HostGrounderSubquestion:
    subquestion_id: str
    text: str

    def __post_init__(self) -> None:
        if type(self.subquestion_id) is not str or not self.subquestion_id:
            raise ValueError("subquestion_id must be a nonempty string")
        if type(self.text) is not str or not self.text:
            raise ValueError("subquestion text must be a nonempty string")
        try:
            self.subquestion_id.encode("utf-8", errors="strict")
            self.text.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("subquestion values must be valid UTF-8") from exc


@dataclass(frozen=True)
class HostGrounderRunInput:
    """One immutable Event run record with literal canonical bytes and digest."""

    run_id: str
    user_input: UserEventInput
    subquestions: Tuple[HostGrounderSubquestion, ...]
    bounds: HostGrounderRunInputBounds
    canonical_json: str = field(init=False)
    canonical_bytes: bytes = field(init=False, repr=False)
    canonical_input_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if type(self.bounds) is not HostGrounderRunInputBounds:
            raise TypeError("bounds must be HostGrounderRunInputBounds")
        bounds = self.bounds
        _bounded_text(self.run_id, "run_id", bounds.max_string_bytes)

        if type(self.user_input) is not UserEventInput:
            raise TypeError("user_input must be exactly UserEventInput")
        UserEventInput.__post_init__(self.user_input)

        if type(self.subquestions) is not tuple:
            raise TypeError("subquestions must be a tuple")
        if not self.subquestions:
            raise ValueError("Event run input requires at least one subquestion")
        if len(self.subquestions) > bounds.max_array_items:
            raise ValueError("subquestions exceeds max_array_items")

        _bounded_text(self.user_input.description, "description", bounds.max_string_bytes)
        for name, values in (
            ("provisional_symbols", self.user_input.provisional_symbols),
            ("source_locators", self.user_input.source_locators),
        ):
            if len(values) > bounds.max_array_items:
                raise ValueError("{} exceeds max_array_items".format(name))
            for index, value in enumerate(values):
                _bounded_text(value, "{}[{}]".format(name, index), bounds.max_string_bytes)

        seen_ids = set()
        for index, item in enumerate(self.subquestions):
            if type(item) is not HostGrounderSubquestion:
                raise TypeError("subquestions must contain HostGrounderSubquestion records")
            subquestion_id = _bounded_text(
                item.subquestion_id,
                "subquestions[{}].subquestion_id".format(index),
                bounds.max_string_bytes,
            )
            _bounded_text(
                item.text,
                "subquestions[{}].text".format(index),
                bounds.max_string_bytes,
            )
            if subquestion_id in seen_ids:
                raise ValueError("subquestion IDs must be unique")
            seen_ids.add(subquestion_id)

        event_date = self.user_input.event_date
        if event_date is not None and type(event_date) is not date:
            raise TypeError("event_date must be exactly date or None")
        event_date_text = None if event_date is None else event_date.isoformat()
        if event_date_text is not None:
            _bounded_text(event_date_text, "event_date", bounds.max_string_bytes)

        payload = {
            "mode": "event",
            "schema_version": "host-grounder-run-input-v0.1",
            "subquestions": [
                {"subquestion_id": item.subquestion_id, "text": item.text}
                for item in self.subquestions
            ],
            "user_input": {
                "description": self.user_input.description,
                "event_date": event_date_text,
                "provisional_symbols": list(self.user_input.provisional_symbols),
                "source_locators": list(self.user_input.source_locators),
            },
        }
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        try:
            canonical_bytes = canonical_json.encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError("canonical run input is not valid UTF-8") from exc
        if len(canonical_bytes) > bounds.max_run_input_bytes:
            raise ValueError("canonical run input exceeds max_run_input_bytes")

        object.__setattr__(self, "canonical_json", canonical_json)
        object.__setattr__(self, "canonical_bytes", canonical_bytes)
        object.__setattr__(
            self, "canonical_input_hash", hashlib.sha256(canonical_bytes).hexdigest()
        )

    @property
    def subquestion_ids(self) -> Tuple[str, ...]:
        return tuple(item.subquestion_id for item in self.subquestions)


def validate_host_context_binding(
    run_input: HostGrounderRunInput,
    *,
    context_run_id: object,
    context_raw_input: object,
    context_canonical_input_hash: object,
) -> None:
    """Fail closed unless context identity, object identity, and digest match."""
    if type(run_input) is not HostGrounderRunInput:
        raise TypeError("run_input must be HostGrounderRunInput")
    if type(context_run_id) is not str or context_run_id != run_input.run_id:
        raise ValueError("context run_id does not match run input")
    if context_raw_input is not run_input.user_input:
        raise ValueError("context raw_input is not the registered UserEventInput object")
    if (
        type(context_canonical_input_hash) is not str
        or context_canonical_input_hash != run_input.canonical_input_hash
    ):
        raise ValueError("context canonical_input_hash does not match run input")


def validate_ordered_coverage_ids(
    run_input: HostGrounderRunInput, coverage_ids: Tuple[str, ...]
) -> None:
    """Require the complete predeclared subquestion ID sequence, exactly ordered."""
    if type(run_input) is not HostGrounderRunInput:
        raise TypeError("run_input must be HostGrounderRunInput")
    if type(coverage_ids) is not tuple:
        raise TypeError("coverage_ids must be a tuple")
    if len(coverage_ids) > run_input.bounds.max_array_items:
        raise ValueError("coverage_ids exceeds max_array_items")
    seen_ids = set()
    for index, value in enumerate(coverage_ids):
        coverage_id = _bounded_text(
            value,
            "coverage_ids[{}]".format(index),
            run_input.bounds.max_string_bytes,
        )
        if coverage_id in seen_ids:
            raise ValueError("coverage IDs must be unique")
        seen_ids.add(coverage_id)
    if coverage_ids != run_input.subquestion_ids:
        raise ValueError("coverage IDs do not match the predeclared ordered plan")
