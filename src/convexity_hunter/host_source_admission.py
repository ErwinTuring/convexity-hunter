"""Narrow Host-owned HTTPS admission for existing Event source families.

This is deliberately not a crawler. It performs at most five target GETs per
run (redirect requests count), validates every exact target and DNS result,
pins the socket to a validated public address, and parses only the small SEC,
Nasdaq, and Yahoo identity formats already consumed by Host Event.
"""

from __future__ import annotations

import datetime
import hashlib
import html
import http.client
import ipaddress
import json
import math
import os
import queue
import re
import socket
import stat
import ssl
import threading
import time
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlsplit


MAX_SOURCE_ADMISSION_REQUESTS = 5
MAX_SOURCE_ADMISSION_REDIRECTS = 2
_PARSER_METADATA = {
    "sec-edgar-cover-v1": ("sec", "1"),
    "sec-edgar-cover-text-v2": ("sec", "2"),
    "sec-edgar-cover-layout-v3": ("sec", "3"),
    "sec-edgar-cover-layout-v4": ("sec", "4"),
    "sec-issuer-reference-v1": ("sec", "1"),
    "sec-issuer-reference-v2": ("sec", "2"),
    "nasdaq-instrument-v1": ("nasdaq", "1"),
    "yahoo-quote-header-v1": ("yahoo", "1"),
}
_SEC_HOSTS = frozenset(("sec.gov", "www.sec.gov"))
_ALLOWED_HOSTS = _SEC_HOSTS | frozenset(("www.nasdaq.com", "finance.yahoo.com"))
_SEC_USER_AGENT_FILE_ENV = "CONVEXITY_HUNTER_SEC_USER_AGENT_FILE"
_SEC_USER_AGENT_DEFAULT_RELATIVE_PATH = Path(".config") / "convexity-hunter" / "sec-user-agent.txt"
_SEC_USER_AGENT_LEGACY = "ConvexityHunter-SourceAdmission/0.1"
_SEC_USER_AGENT_PREFIX = "ConvexityHunter "
_SEC_CONTACT_EMAIL = re.compile(
    r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+"
    r"(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}\Z",
    re.ASCII,
)
_SOURCE_ADMISSION_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_TICKER = re.compile(r"[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*\Z")
_SEC_REFERENCE_LOCATOR = "https://www.sec.gov/files/company_tickers_exchange.json"
_SEC_REFERENCE_PATH = "/files/company_tickers_exchange.json"
_SEC_REFERENCE_FIELDS = ("cik", "name", "ticker", "exchange")
_SEC_PATH = re.compile(
    r"/Archives/edgar/data/(?P<cik>[0-9]{1,10})/"
    r"(?P<accession>(?:[0-9]{18}|[0-9]{10}-[0-9]{2}-[0-9]{6}))/"
    r"(?P<filename>[A-Za-z0-9][A-Za-z0-9._-]*)\Z"
)
_SEC_HEADER = "| Title of each class | Trading Symbol(s) | Name of each exchange on which registered |"
_SEC_MARKER = "(Exact name of registrant as specified in its charter)"
_SEC_TITLE = "Title of each class"
_SEC_TICKER = "Trading Symbol(s)"
_SEC_EXCHANGE = "Name of each exchange on which registered"
_SEC_ISSUER = re.compile(r"[\x20-\x7e]+\Z")
_SEC_MARKDOWN_UNSAFE = frozenset("\\`*_{}[]#<>|~")
_NASDAQ_HEADING = re.compile(
    r"(?P<issuer>[^\r\n]+) Ordinary Shares \((?P<symbol>[^()]*)\)\Z"
)
_YAHOO_HEADING = re.compile(r"(?P<issuer>[^\r\n]+) \((?P<symbol>[^()]*)\)\Z")
_YAHOO_QUOTE = "NasdaqGS - Delayed Quote•USD"
_BLOCK_TAGS = frozenset(
    ("article", "blockquote", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "p", "section", "tr")
)
_VOID_TAGS = frozenset(("area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"))
_HIDDEN_TAGS = frozenset(("noscript", "script", "style", "template"))
_ASCII_WHITESPACE = " \t\r\n\f"
_HIDDEN_STYLE = re.compile(
    r"[ \t\r\n\f]*(?:display[ \t\r\n\f]*:[ \t\r\n\f]*none|"
    r"visibility[ \t\r\n\f]*:[ \t\r\n\f]*(?:hidden|collapse))"
    r"[ \t\r\n\f]*(?:![ \t\r\n\f]*important[ \t\r\n\f]*)?",
    re.IGNORECASE | re.ASCII,
)
_FAILURE_CODES = frozenset(
    (
        "URL_NOT_ADMISSIBLE",
        "DNS_RESOLUTION_FAILED",
        "DNS_ADDRESS_BLOCKED",
        "TRANSPORT_FAILED",
        "HTTP_STATUS_UNSUPPORTED",
        "REDIRECT_INVALID",
        "REDIRECT_LIMIT",
        "CONTENT_TYPE_UNSUPPORTED",
        "BODY_LIMIT_EXCEEDED",
        "UTF8_DECODE_FAILED",
        "PARSER_UNSUPPORTED",
        "REQUEST_LIMIT_REACHED",
        "SOURCE_ID_COLLISION",
        "DNS_LIMIT_REACHED",
        "ADMISSION_DEADLINE_EXCEEDED",
    )
)


@dataclass(frozen=True, repr=False)
class AdmissionAnchor:
    """Exact raw-response span linked to one parsed-body span."""

    field: str
    raw_start: int
    raw_end: int
    raw_sha256: str
    parsed_start: int
    parsed_end: int

    def __post_init__(self) -> None:
        if (
            type(self.field) is not str
            or not self.field
            or type(self.raw_start) is not int
            or type(self.raw_end) is not int
            or self.raw_start < 0
            or self.raw_end < self.raw_start
            or type(self.parsed_start) is not int
            or type(self.parsed_end) is not int
            or self.parsed_start < 0
            or self.parsed_end < self.parsed_start
            or type(self.raw_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", self.raw_sha256)
        ):
            raise ValueError("admission anchor is invalid")

    def as_dict(self) -> dict:
        return {
            "field": self.field,
            "raw_start": self.raw_start,
            "raw_end": self.raw_end,
            "raw_sha256": self.raw_sha256,
            "parsed_start": self.parsed_start,
            "parsed_end": self.parsed_end,
        }


@dataclass(frozen=True, repr=False)
class SourceAdmission:
    """A successful retrieval plus a source-specific parsed evidence body."""

    source_id: str
    family: str
    initial_locator: str
    final_locator: str
    origin: str
    retrieved_at: datetime.datetime
    content_type: str
    raw_body_sha256: str
    raw_body_bytes: int
    parser_id: str
    parser_version: str
    parsed_body_sha256: str
    parsed_body: str
    raw_anchors: Tuple[AdmissionAnchor, ...]
    parsed_symbol: Optional[str] = None

    def __post_init__(self) -> None:
        if (
            type(self.source_id) is not str
            or not self.source_id.startswith("host-admission-")
            or self.family not in ("sec", "nasdaq", "yahoo")
            or type(self.initial_locator) is not str
            or type(self.final_locator) is not str
            or type(self.origin) is not str
            or type(self.retrieved_at) is not datetime.datetime
            or self.retrieved_at.tzinfo is None
            or self.retrieved_at.utcoffset() is None
            or type(self.content_type) is not str
            or type(self.raw_body_bytes) is not int
            or self.raw_body_bytes <= 0
            or type(self.parser_id) is not str
            or type(self.parser_version) is not str
            or type(self.parsed_body) is not str
            or not self.parsed_body
            or type(self.raw_anchors) is not tuple
            or any(type(anchor) is not AdmissionAnchor for anchor in self.raw_anchors)
            or type(self.raw_body_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", self.raw_body_sha256)
            or type(self.parsed_body_sha256) is not str
            or hashlib.sha256(self.parsed_body.encode("utf-8")).hexdigest()
            != self.parsed_body_sha256
            or (
                self.parsed_symbol is not None
                and (type(self.parsed_symbol) is not str or not _TICKER.fullmatch(self.parsed_symbol))
            )
        ):
            raise ValueError("source admission record is invalid")

    def provenance(self) -> dict:
        """Return the non-secret lineage projection used in listing references."""
        return {
            "initial_locator": self.initial_locator,
            "final_locator": self.final_locator,
            "origin": self.origin,
            "retrieved_at": self.retrieved_at.astimezone(datetime.timezone.utc).isoformat(),
            "content_type": self.content_type,
            "raw_body_sha256": self.raw_body_sha256,
            "raw_body_bytes": self.raw_body_bytes,
            "parser_id": self.parser_id,
            "parser_version": self.parser_version,
            "parsed_body_sha256": self.parsed_body_sha256,
            "raw_anchors": [anchor.as_dict() for anchor in self.raw_anchors],
        }

    def __repr__(self) -> str:
        return "SourceAdmission(<redacted>)"


@dataclass(frozen=True, repr=False)
class AdmissionFailure:
    """Closed failure code; deliberately contains no URL, body, or exception."""

    code: str

    def __post_init__(self) -> None:
        if type(self.code) is not str or self.code not in _FAILURE_CODES:
            raise ValueError("admission failure code is invalid")

    def __repr__(self) -> str:
        return "AdmissionFailure({})".format(self.code)


@dataclass(frozen=True, repr=False)
class AdmissionBatch:
    admissions: Tuple[SourceAdmission, ...]
    failures: Tuple[AdmissionFailure, ...]
    request_count: int
    response_bytes: int

    def __post_init__(self) -> None:
        if (
            type(self.admissions) is not tuple
            or any(type(item) is not SourceAdmission for item in self.admissions)
            or type(self.failures) is not tuple
            or any(type(item) is not AdmissionFailure for item in self.failures)
            or type(self.request_count) is not int
            or not 0 <= self.request_count <= MAX_SOURCE_ADMISSION_REQUESTS
            or type(self.response_bytes) is not int
            or self.response_bytes < 0
        ):
            raise ValueError("admission batch is invalid")

    def __repr__(self) -> str:
        return "AdmissionBatch(admissions={}, failures={}, request_count={}, response_bytes={})".format(
            len(self.admissions), len(self.failures), self.request_count, self.response_bytes
        )


@dataclass(frozen=True, repr=False)
class _ParsedPage:
    body: str
    parser_id: str
    anchors: Tuple[AdmissionAnchor, ...]
    symbol: Optional[str]


@dataclass(frozen=True, repr=False)
class _Reply:
    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True, repr=False)
class _TextChunk:
    text: str
    raw_start: int
    raw_end: int
    table_id: Optional[int]


@dataclass(frozen=True, repr=False)
class _Heading:
    level: int
    text: str
    raw_start: int
    raw_end: int


class _BoundedHTML(HTMLParser):
    """Collect only text, tables, and headings needed by the three parsers."""

    def __init__(self, source: str):
        super().__init__(convert_charrefs=False)
        self._source = source
        self._line_starts = [0]
        self._line_starts.extend(index + 1 for index, char in enumerate(source) if char == "\n")
        self.chunks = []
        self.tables = []
        self.headings = []
        self._table_stack = []
        self._row = None
        self._cell = None
        self._heading = None
        self._hidden_stack = []

    def _offset(self) -> int:
        line, column = self.getpos()
        if line < 1 or line > len(self._line_starts):
            return len(self._source)
        return min(len(self._source), self._line_starts[line - 1] + column)

    def _append_text(self, text: str, raw_start: int, raw_end: int) -> None:
        if not text:
            return
        table_id = self._table_stack[-1] if self._table_stack else None
        self.chunks.append(_TextChunk(text, raw_start, raw_end, table_id))
        if self._cell is not None:
            self._cell["chunks"].append((text, raw_start, raw_end))
        if self._heading is not None:
            self._heading["chunks"].append((text, raw_start, raw_end))

    def _boundary(self, *, paragraph: bool = False) -> None:
        self._append_text("\n\n" if paragraph else "\n", self._offset(), self._offset())

    def handle_starttag(self, tag, attrs):
        tag = tag.casefold()
        if self._hidden_stack:
            if tag not in _VOID_TAGS:
                self._hidden_stack.append(tag)
            return
        hidden = tag in _HIDDEN_TAGS or any(
            name == "hidden"
            or (name == "aria-hidden" and value is not None
                and value.strip(_ASCII_WHITESPACE).lower() == "true")
            or (name == "style" and value is not None
                and any(_HIDDEN_STYLE.fullmatch(part) for part in value.split(";")))
            for name, value in attrs
        )
        if hidden:
            if tag not in _VOID_TAGS:
                self._hidden_stack.append(tag)
            return
        if tag in _BLOCK_TAGS:
            self._boundary()
        if tag == "table":
            table = {"rows": [], "raw_start": self._offset(), "raw_end": None}
            self.tables.append(table)
            self._table_stack.append(len(self.tables) - 1)
        elif tag == "tr" and self._table_stack:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = {"chunks": [], "tag": tag}
        elif re.fullmatch(r"h[1-6]", tag):
            self._heading = {"level": int(tag[1]), "chunks": [], "raw_start": self._offset()}

    def handle_endtag(self, tag):
        tag = tag.casefold()
        if self._hidden_stack:
            for index in range(len(self._hidden_stack) - 1, -1, -1):
                if self._hidden_stack[index] == tag:
                    del self._hidden_stack[index:]
                    break
            return
        offset = self._offset()
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(self._cell)
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table_stack:
            self.tables[self._table_stack[-1]]["rows"].append(self._row)
            self._row = None
        elif tag == "table" and self._table_stack:
            table_id = self._table_stack.pop()
            self.tables[table_id]["raw_end"] = offset
        elif re.fullmatch(r"h[1-6]", tag) and self._heading is not None:
            parts = self._heading["chunks"]
            text = "".join(item[0] for item in parts)
            starts = [item[1] for item in parts]
            ends = [item[2] for item in parts]
            if text:
                self.headings.append(
                    _Heading(
                        self._heading["level"],
                        text,
                        min(starts),
                        max(ends),
                    )
                )
            self._heading = None
        if tag in _BLOCK_TAGS:
            self._boundary(paragraph=tag == "p")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.casefold() not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if self._hidden_stack:
            return
        start = self._offset()
        self._append_text(data, start, start + len(data))

    def handle_entityref(self, name):
        if self._hidden_stack:
            return
        start = self._offset()
        raw = "&{};".format(name)
        self._append_text(html.unescape(raw), start, min(len(self._source), start + len(raw)))

    def handle_charref(self, name):
        if self._hidden_stack:
            return
        start = self._offset()
        raw = "&#{};".format(name)
        self._append_text(html.unescape(raw), start, min(len(self._source), start + len(raw)))

    def result(self) -> "_BoundedHTML":
        self.feed(self._source)
        self.close()
        if self._table_stack or self._row is not None or self._cell is not None or self._heading is not None:
            raise ValueError("incomplete HTML structure")
        return self


def _source_offset_hash(raw: str, start: int, end: int) -> str:
    return hashlib.sha256(raw[start:end].encode("utf-8", errors="strict")).hexdigest()


def _json_object_without_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_json_constant(_value):
    raise ValueError("non-finite JSON number")


def _strict_json_float(value):
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number")
    return parsed


def _json_skip_whitespace(source: str, offset: int) -> int:
    while offset < len(source) and source[offset] in " \t\r\n":
        offset += 1
    return offset


def _json_array_item_spans(source: str, array_start: int):
    """Locate exact JSON array-item tokens after strict decoding has succeeded."""
    decoder = json.JSONDecoder()
    if array_start >= len(source) or source[array_start] != "[":
        raise ValueError("JSON data member is not an array")
    offset = _json_skip_whitespace(source, array_start + 1)
    spans = []
    if offset < len(source) and source[offset] == "]":
        return tuple(spans)
    while offset < len(source):
        start = offset
        _value, end = decoder.raw_decode(source, start)
        spans.append((start, end))
        offset = _json_skip_whitespace(source, end)
        if offset < len(source) and source[offset] == ",":
            offset = _json_skip_whitespace(source, offset + 1)
            continue
        if offset < len(source) and source[offset] == "]":
            return tuple(spans)
        raise ValueError("malformed JSON array")
    raise ValueError("unterminated JSON array")


def _sec_reference_data_spans(source: str):
    """Return data-row token spans from a strictly decoded root object."""
    decoder = json.JSONDecoder()
    offset = _json_skip_whitespace(source, 0)
    if offset >= len(source) or source[offset] != "{":
        raise ValueError("JSON root is not an object")
    offset = _json_skip_whitespace(source, offset + 1)
    while offset < len(source):
        key, key_end = decoder.raw_decode(source, offset)
        if type(key) is not str:
            raise ValueError("JSON object key is not a string")
        offset = _json_skip_whitespace(source, key_end)
        if offset >= len(source) or source[offset] != ":":
            raise ValueError("malformed JSON object")
        value_start = _json_skip_whitespace(source, offset + 1)
        _value, value_end = decoder.raw_decode(source, value_start)
        if key == "data":
            return _json_array_item_spans(source, value_start)
        offset = _json_skip_whitespace(source, value_end)
        if offset < len(source) and source[offset] == ",":
            offset = _json_skip_whitespace(source, offset + 1)
            continue
        if offset < len(source) and source[offset] == "}":
            break
        raise ValueError("malformed JSON object")
    raise ValueError("JSON data member is missing")


def _sec_reference_string_is_safe(value: object, *, nonempty: bool = False) -> bool:
    if type(value) is not str or (nonempty and not value):
        return False
    offset = 0
    while offset < len(value):
        character = value[offset]
        codepoint = ord(character)
        if unicodedata.category(character) == "Cc":
            return False
        if 0xD800 <= codepoint <= 0xDBFF:
            if offset + 1 >= len(value) or not 0xDC00 <= ord(value[offset + 1]) <= 0xDFFF:
                return False
            offset += 2
            continue
        if 0xDC00 <= codepoint <= 0xDFFF:
            return False
        offset += 1
    return True


def _decode_sec_reference_document(source: str):
    """Strictly decode and structurally validate every SEC reference row."""
    root = json.loads(
        source,
        object_pairs_hook=_json_object_without_duplicate_keys,
        parse_constant=_reject_json_constant,
        parse_float=_strict_json_float,
    )
    if (
        type(root) is not dict
        or tuple(root.keys()) != ("fields", "data")
        or type(root["fields"]) is not list
        or tuple(root["fields"]) != _SEC_REFERENCE_FIELDS
        or type(root["data"]) is not list
    ):
        raise ValueError("SEC reference root schema is unsupported")
    row_spans = _sec_reference_data_spans(source)
    if len(row_spans) != len(root["data"]):
        raise ValueError("SEC reference row spans do not match data")
    for row in root["data"]:
        if (
            type(row) is not list
            or len(row) != 4
            or type(row[0]) is not int
            or not 0 < row[0] < 10**10
            or not _sec_reference_string_is_safe(row[1], nonempty=True)
            or not _sec_reference_string_is_safe(row[2], nonempty=True)
            or _TICKER.fullmatch(row[2]) is None
            or (
                row[3] is not None
                and not _sec_reference_string_is_safe(row[3])
            )
        ):
            raise ValueError("SEC reference row is unsupported")
    return root["data"], row_spans


def _decode_sec_reference_document_v2(source: str):
    """Strictly decode the reference envelope and row shapes, not background semantics."""
    root = json.loads(
        source,
        object_pairs_hook=_json_object_without_duplicate_keys,
        parse_constant=_reject_json_constant,
        parse_float=_strict_json_float,
    )
    if (
        type(root) is not dict
        or tuple(root.keys()) != ("fields", "data")
        or type(root["fields"]) is not list
        or tuple(root["fields"]) != _SEC_REFERENCE_FIELDS
        or type(root["data"]) is not list
    ):
        raise ValueError("SEC reference root schema is unsupported")
    row_spans = _sec_reference_data_spans(source)
    if len(row_spans) != len(root["data"]) or any(
        type(row) is not list or len(row) != 4 for row in root["data"]
    ):
        raise ValueError("SEC reference row structure is unsupported")
    return root["data"], row_spans


def _sec_reference_byte_offsets(source: str, character_offsets):
    wanted = set(character_offsets)
    offsets = {}
    byte_offset = 0
    for character_offset, character in enumerate(source):
        if character_offset in wanted:
            offsets[character_offset] = byte_offset
        byte_offset += len(character.encode("utf-8"))
    if len(source) in wanted:
        offsets[len(source)] = byte_offset
    if len(offsets) != len(wanted):
        raise ValueError("SEC reference row span is out of bounds")
    return offsets


def _sec_reference_selected_page(source, selected_symbols, selected, parser_id):
    byte_offsets = _sec_reference_byte_offsets(
        source,
        (
            offset
            for ticker in selected_symbols
            for offset in selected[ticker][0]
        ),
    )
    wrapper_prefix = '{"fields":["cik","name","ticker","exchange"],"data":['
    row_tokens = []
    anchors = []
    parsed_offset = len(wrapper_prefix)
    for symbol in selected_symbols:
        (raw_start, raw_end), _row = selected[symbol]
        token = source[raw_start:raw_end]
        token_bytes = token.encode("utf-8")
        if row_tokens:
            parsed_offset += 1
        parsed_start = parsed_offset
        parsed_end = parsed_start + len(token)
        anchors.append(
            AdmissionAnchor(
                "sec_issuer_reference.data." + symbol,
                byte_offsets[raw_start],
                byte_offsets[raw_end],
                hashlib.sha256(token_bytes).hexdigest(),
                parsed_start,
                parsed_end,
            )
        )
        row_tokens.append(token)
        parsed_offset = parsed_end
    body = wrapper_prefix + ",".join(row_tokens) + "]}"
    return _ParsedPage(body, parser_id, tuple(anchors), None)


def _sec_issuer_reference_json(source: str, selected_symbols: Tuple[str, ...]) -> Optional["_ParsedPage"]:
    try:
        rows, row_spans = _decode_sec_reference_document(source)
        requested = set(selected_symbols)
        selected = {}
        for index, row in enumerate(rows):
            ticker = row[2]
            if ticker not in requested:
                continue
            if ticker in selected or type(row[3]) is not str or not row[3]:
                return None
            selected[ticker] = (row_spans[index], row)
        if set(selected) != requested:
            return None
        return _sec_reference_selected_page(
            source, selected_symbols, selected, "sec-issuer-reference-v1"
        )
    except (ValueError, TypeError, RecursionError, UnicodeEncodeError):
        return None


def _sec_issuer_reference_json_v2(
    source: str, selected_symbols: Tuple[str, ...]
) -> Optional["_ParsedPage"]:
    try:
        rows, row_spans = _decode_sec_reference_document_v2(source)
        requested = set(selected_symbols)
        selected = {}
        for index, row in enumerate(rows):
            ticker = row[2]
            if type(ticker) is not str or ticker not in requested:
                continue
            if (
                ticker in selected
                or type(row[0]) is not int
                or not 0 < row[0] < 10**10
                or not _sec_reference_string_is_safe(row[1], nonempty=True)
                or ticker != ticker.upper()
                or _TICKER.fullmatch(ticker) is None
                or not _sec_reference_string_is_safe(row[3], nonempty=True)
            ):
                return None
            selected[ticker] = (row_spans[index], row)
        if set(selected) != requested:
            return None
        return _sec_reference_selected_page(
            source, selected_symbols, selected, "sec-issuer-reference-v2"
        )
    except (ValueError, TypeError, RecursionError, UnicodeEncodeError):
        return None


def _anchor(field: str, raw: str, raw_start: int, raw_end: int, parsed_start: int, parsed_end: int) -> AdmissionAnchor:
    return AdmissionAnchor(
        field,
        raw_start,
        raw_end,
        _source_offset_hash(raw, raw_start, raw_end),
        parsed_start,
        parsed_end,
    )


def _family_target(locator: object):
    """Return strict family/path identity, without resolving a host."""
    if (
        type(locator) is not str
        or not locator
        or locator != locator.strip()
        or not locator.isascii()
        or any(ord(char) <= 0x20 or ord(char) == 0x7F for char in locator)
        or "?" in locator
        or "#" in locator
        or "\\" in locator
    ):
        return None
    try:
        parsed = urlsplit(locator)
        port = parsed.port
    except ValueError:
        return None
    host = parsed.hostname
    if (
        parsed.scheme != "https"
        or host not in _ALLOWED_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.netloc not in (host, host + ":443")
        or parsed.query
        or parsed.fragment
        or not parsed.path.isascii()
        or "%" in parsed.path
        or "//" in parsed.path
        or any(segment in (".", "..") for segment in parsed.path.split("/"))
    ):
        return None
    if host in _SEC_HOSTS:
        match = _SEC_PATH.fullmatch(parsed.path)
        if match is None:
            return None
        accession = match.group("accession")
        return ("sec", parsed, (match.group("cik"), accession, match.group("filename")))
    if host == "www.nasdaq.com":
        match = re.fullmatch(
            r"/market-activity/stocks/(?P<symbol>[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)(?:/(?P<subpage>[A-Za-z0-9-]+))?",
            parsed.path,
        )
        if match is None:
            return None
        return ("nasdaq", parsed, (match.group("symbol").upper(), parsed.path))
    if host == "finance.yahoo.com":
        match = re.fullmatch(r"/quote/(?P<symbol>[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)/", parsed.path)
        if match is None:
            return None
        return ("yahoo", parsed, (match.group("symbol").upper(), parsed.path))
    return None


def _sec_reference_target(locator: object):
    """Recognize only the explicitly selected SEC issuer-reference endpoint."""
    if (
        type(locator) is not str
        or locator != _SEC_REFERENCE_LOCATOR
        or not locator.isascii()
    ):
        return None
    try:
        parsed = urlsplit(locator)
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.sec.gov"
        or parsed.hostname != "www.sec.gov"
        or parsed.path != _SEC_REFERENCE_PATH
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return ("sec-reference", parsed, (_SEC_REFERENCE_PATH,))


def _same_target(initial, current) -> bool:
    if initial[0] != current[0]:
        return False
    if initial[0] == "sec-reference":
        return initial[1].netloc == current[1].netloc and initial[1].path == current[1].path
    if initial[0] == "sec":
        # Host aliases may differ, but a redirect may not switch filing.
        return initial[2] == current[2] and initial[1].path == current[1].path
    return initial[2] == current[2]


def _source_id_for_locator(locator: str) -> str:
    return "host-admission-" + hashlib.sha256(locator.encode("ascii")).hexdigest()[:24]


def _sec_reference_record_is_consistent(
    value: SourceAdmission, expected_symbols: Optional[Tuple[str, ...]] = None
) -> bool:
    try:
        rows, row_spans = _decode_sec_reference_document(value.parsed_body)
        if not rows or any(type(row[3]) is not str or not row[3] for row in rows):
            return False
        tickers = [row[2] for row in rows]
        if any(ticker != ticker.upper() for ticker in tickers) or len(set(tickers)) != len(tickers):
            return False
        if expected_symbols is not None and tuple(tickers) != expected_symbols:
            return False
        row_tokens = [value.parsed_body[start:end] for start, end in row_spans]
        expected_body = (
            '{"fields":["cik","name","ticker","exchange"],"data":['
            + ",".join(row_tokens)
            + "]}"
        )
        if value.parsed_body != expected_body or len(value.raw_anchors) != len(rows):
            return False
        raw_spans = []
        for row, (parsed_start, parsed_end), token, anchor in zip(
            rows, row_spans, row_tokens, value.raw_anchors
        ):
            token_bytes = token.encode("utf-8")
            if (
                anchor.field != "sec_issuer_reference.data." + row[2]
                or anchor.parsed_start != parsed_start
                or anchor.parsed_end != parsed_end
                or anchor.raw_end - anchor.raw_start != len(token_bytes)
                or anchor.raw_sha256 != hashlib.sha256(token_bytes).hexdigest()
            ):
                return False
            raw_spans.append((anchor.raw_start, anchor.raw_end))
        ordered_raw_spans = sorted(raw_spans)
        if any(
            start < previous_end
            for (_previous_start, previous_end), (start, _end) in zip(
                ordered_raw_spans, ordered_raw_spans[1:]
            )
        ):
            return False
        return True
    except (AttributeError, TypeError, ValueError, RecursionError, UnicodeEncodeError):
        return False


def _sec_reference_record_snapshot(value: object):
    if type(value) is not SourceAdmission or type(value.raw_anchors) is not tuple:
        return None
    record_strings = (
        value.source_id, value.family, value.initial_locator, value.final_locator,
        value.origin, value.content_type, value.raw_body_sha256, value.parser_id,
        value.parser_version, value.parsed_body_sha256, value.parsed_body,
    )
    if any(type(item) is not str for item in record_strings):
        return None
    if type(value.retrieved_at) is not datetime.datetime or type(value.raw_body_bytes) is not int:
        return None
    if value.parsed_symbol is not None and type(value.parsed_symbol) is not str:
        return None
    anchors = []
    for anchor in value.raw_anchors:
        if type(anchor) is not AdmissionAnchor:
            return None
        fields = (
            anchor.field, anchor.raw_start, anchor.raw_end, anchor.raw_sha256,
            anchor.parsed_start, anchor.parsed_end,
        )
        if (
            type(anchor.field) is not str
            or type(anchor.raw_start) is not int
            or type(anchor.raw_end) is not int
            or type(anchor.raw_sha256) is not str
            or type(anchor.parsed_start) is not int
            or type(anchor.parsed_end) is not int
        ):
            return None
        anchors.append(fields)
    return record_strings[:5] + (
        value.retrieved_at, value.content_type, value.raw_body_sha256,
        value.raw_body_bytes, value.parser_id, value.parser_version,
        value.parsed_body_sha256, value.parsed_body, tuple(anchors),
        value.parsed_symbol,
    )


def _revalidate_source_admission(
    value: object,
    *,
    max_raw_bytes: int,
    max_parsed_bytes: int,
    _sec_reference_issuance_receipt=None,
) -> Optional[SourceAdmission]:
    """Recheck a client result before the immutable source registry is built."""
    if type(value) is not SourceAdmission:
        return None
    try:
        anchors = tuple(
            AdmissionAnchor(
                anchor.field,
                anchor.raw_start,
                anchor.raw_end,
                anchor.raw_sha256,
                anchor.parsed_start,
                anchor.parsed_end,
            )
            for anchor in value.raw_anchors
        )
        checked = SourceAdmission(
            source_id=value.source_id,
            family=value.family,
            initial_locator=value.initial_locator,
            final_locator=value.final_locator,
            origin=value.origin,
            retrieved_at=value.retrieved_at,
            content_type=value.content_type,
            raw_body_sha256=value.raw_body_sha256,
            raw_body_bytes=value.raw_body_bytes,
            parser_id=value.parser_id,
            parser_version=value.parser_version,
            parsed_body_sha256=value.parsed_body_sha256,
            parsed_body=value.parsed_body,
            raw_anchors=anchors,
            parsed_symbol=value.parsed_symbol,
        )
        is_sec_reference = checked.parser_id in (
            "sec-issuer-reference-v1",
            "sec-issuer-reference-v2",
        )
        receipt_symbols = None
        if is_sec_reference:
            if (
                type(_sec_reference_issuance_receipt) is not tuple
                or len(_sec_reference_issuance_receipt) != 2
                or type(_sec_reference_issuance_receipt[0]) is not tuple
                or type(_sec_reference_issuance_receipt[1]) is not tuple
                or _sec_reference_record_snapshot(checked) != _sec_reference_issuance_receipt[1]
            ):
                return None
            receipt_symbols = _sec_reference_issuance_receipt[0]
        initial = (
            _sec_reference_target(checked.initial_locator)
            if is_sec_reference
            else _family_target(checked.initial_locator)
        )
        final = (
            _sec_reference_target(checked.final_locator)
            if is_sec_reference
            else _family_target(checked.final_locator)
        )
        parser_metadata = _PARSER_METADATA.get(checked.parser_id)
        expected_family = "sec" if is_sec_reference else (initial[0] if initial is not None else None)
        expected_content_type = "application/json" if is_sec_reference else "text/html"
        if (
            initial is None
            or final is None
            or not _same_target(initial, final)
            or checked.family != expected_family
            or checked.source_id != _source_id_for_locator(checked.initial_locator)
            or checked.origin != "https://{}".format(final[1].hostname)
            or checked.content_type != expected_content_type
            or parser_metadata != (checked.family, checked.parser_version)
            or checked.raw_body_bytes > max_raw_bytes
            or len(checked.parsed_body.encode("utf-8")) > max_parsed_bytes
            or any(
                anchor.raw_end > checked.raw_body_bytes
                or anchor.parsed_end > len(checked.parsed_body)
                for anchor in anchors
            )
            or (
                is_sec_reference
                and (
                    checked.parsed_symbol is not None
                    or not _sec_reference_record_is_consistent(checked, receipt_symbols)
                )
            )
            or (
                not is_sec_reference
                and checked.family == "sec"
                and (
                    checked.parsed_symbol is None
                    or checked.parsed_symbol != checked.parsed_symbol.upper()
                )
            )
            or (
                not is_sec_reference
                and checked.family != "sec"
                and (
                    checked.parsed_symbol != initial[2][0]
                    or checked.parsed_symbol != checked.parsed_symbol.upper()
                )
            )
        ):
            return None
        return checked
    except (AttributeError, TypeError, ValueError, UnicodeEncodeError):
        return None


def _safe_addresses(
    host: str,
    resolver: Callable[[str, int], Sequence[str]],
    *,
    timeout_seconds: float,
    deadline: float,
    monotonic: Callable[[], float],
) -> Tuple[str, ...]:
    values = _bounded_daemon_call(
        lambda: tuple(resolver(host, 443)),
        timeout_seconds=timeout_seconds,
        deadline=deadline,
        monotonic=monotonic,
        timeout_code="DNS_RESOLUTION_FAILED",
        thread_name="host-admission-dns",
    )
    if not values:
        raise _AdmissionProblem("DNS_RESOLUTION_FAILED")
    normalized = []
    for value in values:
        try:
            address = ipaddress.ip_address(value)
        except (TypeError, ValueError):
            raise _AdmissionProblem("DNS_RESOLUTION_FAILED") from None
        if not address.is_global or address.is_multicast or address.is_unspecified:
            raise _AdmissionProblem("DNS_ADDRESS_BLOCKED")
        normalized.append(str(address))
    return tuple(dict.fromkeys(normalized))


def _bounded_daemon_call(
    function: Callable[[], object],
    *,
    timeout_seconds: float,
    deadline: float,
    monotonic: Callable[[], float],
    timeout_code: str,
    thread_name: str,
):
    completed = queue.Queue(maxsize=1)

    def run() -> None:
        try:
            result = (True, function())
        except Exception:
            result = (False, None)
        try:
            completed.put_nowait(result)
        except queue.Full:
            pass

    try:
        threading.Thread(target=run, name=thread_name, daemon=True).start()
        succeeded, value = completed.get(timeout=timeout_seconds)
    except queue.Empty:
        if deadline - monotonic() <= 0:
            raise _AdmissionProblem("ADMISSION_DEADLINE_EXCEEDED") from None
        raise _AdmissionProblem(timeout_code) from None
    except _AdmissionProblem:
        raise
    except Exception:
        raise _AdmissionProblem(timeout_code) from None
    if not succeeded:
        raise _AdmissionProblem(timeout_code)
    return value


class _AdmissionProblem(Exception):
    def __init__(self, code: str):
        self.code = code if code in _FAILURE_CODES else "TRANSPORT_FAILED"


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to one pinned address while TLS still verifies the origin host."""

    def __init__(self, host: str, address: str, timeout: float):
        super().__init__(host, port=443, timeout=timeout, context=ssl.create_default_context())
        self._pinned_address = address
        self._aborted = threading.Event()

    def abort(self) -> None:
        self._aborted.set()
        active_socket = self.sock
        if active_socket is not None:
            try:
                active_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                active_socket.close()
            except OSError:
                pass

    def connect(self) -> None:
        if self._tunnel_host:
            raise OSError("tunnels are not supported")
        raw_socket = socket.create_connection(
            (self._pinned_address, self.port), self.timeout
        )
        if self._aborted.is_set():
            raw_socket.close()
            raise TimeoutError("source admission deadline expired")
        self.sock = raw_socket
        try:
            tls_socket = self._context.wrap_socket(
                raw_socket,
                server_hostname=self.host,
                do_handshake_on_connect=False,
            )
            self.sock = tls_socket
            tls_socket.settimeout(self.timeout)
            if self._aborted.is_set():
                self.abort()
                raise TimeoutError("source admission deadline expired")
            tls_socket.do_handshake()
        except BaseException:
            active_socket = self.sock
            self.sock = None
            if active_socket is not None:
                try:
                    active_socket.close()
                except OSError:
                    pass
            raise


def _default_resolver(host: str, port: int) -> Tuple[str, ...]:
    records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return tuple(record[4][0] for record in records)


def _content_type(headers: Mapping[str, str], *, allow_json: bool = False) -> Optional[str]:
    values = [value for key, value in headers.items() if key.casefold() == "content-type"]
    if len(values) != 1 or type(values[0]) is not str:
        return None
    pieces = [part.strip() for part in values[0].split(";")]
    media_type = pieces[0].casefold()
    allowed_media_types = ("text/html", "text/plain", "application/json") if allow_json else ("text/html", "text/plain")
    if media_type not in allowed_media_types:
        return None
    charsets = []
    for piece in pieces[1:]:
        if "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        if key.strip().casefold() == "charset":
            charsets.append(value.strip().strip('"').casefold())
    if len(charsets) > 1 or (charsets and charsets[0] not in ("utf-8", "utf8")):
        return None
    return media_type


def _header(headers: Mapping[str, str], name: str) -> Optional[str]:
    values = [value for key, value in headers.items() if key.casefold() == name.casefold()]
    return values[0] if len(values) == 1 and type(values[0]) is str else None


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _sec_user_agent() -> str:
    """Read an optional private SEC contact header only when a SEC GET is made."""
    configured_path = os.environ.get(_SEC_USER_AGENT_FILE_ENV)
    if configured_path is None:
        path = Path.home() / _SEC_USER_AGENT_DEFAULT_RELATIVE_PATH
    else:
        path = Path(configured_path)
        if not configured_path or not path.is_absolute():
            raise _AdmissionProblem("TRANSPORT_FAILED")

    try:
        lexical_path = Path(os.path.abspath(path))
        if _path_is_within(lexical_path, _SOURCE_ADMISSION_REPOSITORY_ROOT):
            raise _AdmissionProblem("TRANSPORT_FAILED")
        resolved_path = path.resolve(strict=True)
    except FileNotFoundError:
        return _SEC_USER_AGENT_LEGACY
    except _AdmissionProblem:
        raise
    except Exception:
        raise _AdmissionProblem("TRANSPORT_FAILED") from None
    if _path_is_within(resolved_path, _SOURCE_ADMISSION_REPOSITORY_ROOT):
        raise _AdmissionProblem("TRANSPORT_FAILED")

    descriptor = None
    try:
        descriptor = os.open(
            resolved_path,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        metadata = os.fstat(descriptor)
        getuid = getattr(os, "getuid", None)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or getuid is None
            or metadata.st_uid != getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise _AdmissionProblem("TRANSPORT_FAILED")
        with os.fdopen(descriptor, "rb") as source_file:
            descriptor = None
            raw = source_file.read(258)
    except FileNotFoundError:
        return _SEC_USER_AGENT_LEGACY
    except _AdmissionProblem:
        raise
    except Exception:
        raise _AdmissionProblem("TRANSPORT_FAILED") from None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass

    if raw.endswith(b"\n"):
        raw = raw[:-1]
    if (
        not raw
        or len(raw) > 256
        or any(byte < 0x20 or byte > 0x7E for byte in raw)
    ):
        raise _AdmissionProblem("TRANSPORT_FAILED")
    try:
        user_agent = raw.decode("ascii")
    except UnicodeDecodeError:
        raise _AdmissionProblem("TRANSPORT_FAILED") from None
    if not user_agent.startswith(_SEC_USER_AGENT_PREFIX):
        raise _AdmissionProblem("TRANSPORT_FAILED")
    email = user_agent[len(_SEC_USER_AGENT_PREFIX) :]
    if (
        len(email) > 254
        or not _SEC_CONTACT_EMAIL.fullmatch(email)
        or len(email.partition("@")[0]) > 64
        or len(email.partition("@")[2]) > 253
    ):
        raise _AdmissionProblem("TRANSPORT_FAILED")
    return user_agent


def _fetch_response(
    locator: str,
    address: str,
    timeout: float,
    max_bytes: int,
) -> _Reply:
    parsed = urlsplit(locator)
    user_agent = _SEC_USER_AGENT_LEGACY
    if parsed.hostname is not None and parsed.hostname.casefold() in _SEC_HOSTS:
        user_agent = _sec_user_agent()
    connection = _PinnedHTTPSConnection(parsed.hostname, address, timeout)
    watchdog = threading.Timer(timeout, connection.abort)
    watchdog.daemon = True
    watchdog.start()
    try:
        connection.request(
            "GET",
            parsed.path,
            headers={
                "Host": parsed.hostname,
                "User-Agent": user_agent,
                "Accept": "text/html, text/plain;q=0.9",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        response = connection.getresponse()
        headers = {}
        for key, value in response.getheaders():
            normalized_key = key.casefold()
            if normalized_key in headers:
                headers[normalized_key] = headers[normalized_key] + "\n" + value
            else:
                headers[normalized_key] = value
        status = response.status
        if status in (301, 302, 303, 307, 308):
            return _Reply(status, headers, b"")
        if status != 200:
            return _Reply(status, headers, b"")
        content_length = _header(headers, "Content-Length")
        if content_length is not None:
            if not re.fullmatch(r"[0-9]+", content_length) or int(content_length) > max_bytes:
                return _Reply(status, headers, b"\x00" * (max_bytes + 1))
        content_encoding = _header(headers, "Content-Encoding")
        if content_encoding not in (None, "", "identity"):
            return _Reply(status, headers, b"\x00" * (max_bytes + 1))
        body = response.read(max_bytes + 1)
        return _Reply(status, headers, body)
    finally:
        watchdog.cancel()
        watchdog.join(timeout=0.1)
        connection.close()


def _cell_text(cell: dict) -> str:
    return "".join(part[0] for part in cell["chunks"])


def _sec_cover_cell_safety_text(cell: dict) -> str:
    return "".join(
        " " if raw_start == raw_end and text in ("\n", "\n\n") else text
        for text, raw_start, raw_end in cell["chunks"]
    )


def _ascii_space(value: str) -> str:
    return re.sub(r"[ \t\r\n\f\v]+", " ", value).strip(" \t\r\n\f\v")


def _issuer_valid(value: str) -> bool:
    return bool(value and _SEC_ISSUER.fullmatch(value) and not any(ch in value for ch in "<>[]{}|`*_#"))


def _sec_cover_text_safe(value: str) -> bool:
    if type(value) is not str or any(not (0x20 <= ord(char) <= 0x7E) for char in value):
        return False
    normalized = _ascii_space(value)
    return bool(
        normalized
        and len(normalized) <= 256
        and not any(char in _SEC_MARKDOWN_UNSAFE for char in normalized)
    )


def _sec_cover_layout_v4_fold(value: str) -> Optional[str]:
    """Fold only declared SEC v4 cover whitespace; preserve all other controls as rejection."""
    if type(value) is not str:
        return None
    value = value.replace("\u00a0", " ")
    if any(
        (ord(char) < 0x20 and char not in "\t\r\n")
        or 0x7F <= ord(char) <= 0x9F
        for char in value
    ):
        return None
    return re.sub(r"[ \t\r\n]+", " ", value).strip(" ")


def _sec_cover_layout_v3_fold(value: str) -> str:
    return _ascii_space(value.replace("\u00a0", " "))


def _sec_cover_layout_table(parser, fold, *, safe_before_fold):
    """Apply the shared, narrow v3/v4 SEC cover-table grammar."""
    expected = tuple(value.casefold() for value in (_SEC_TITLE, _SEC_TICKER, _SEC_EXCHANGE))
    candidates = []
    for table_id, table in enumerate(parser.tables):
        rows = table["rows"]
        if not rows:
            continue
        width = len(rows[0])
        header = tuple(
            fold(_sec_cover_cell_safety_text(cell).replace("\u00a0", " "))
            for cell in rows[0]
        )
        if any(value is None for value in header):
            continue
        projected = tuple(value.lower() if value.isascii() else value for value in header if value)
        if projected == expected:
            candidates.append((table_id, rows, width, header))
    if len(candidates) != 1:
        return None
    table_id, rows, width, header = candidates[0]
    if width not in (3, 5) or len(rows) != 2 or any(len(row) != width for row in rows):
        return None

    field_indices = (0, 1, 2) if width == 3 else (0, 2, 4)
    spacer_indices = () if width == 3 else (1, 3)
    if tuple(index for index, value in enumerate(header) if value) != field_indices:
        return None
    for row in rows:
        for index in spacer_indices:
            spacer = fold(_sec_cover_cell_safety_text(row[index]).replace("\u00a0", " "))
            if spacer is None or spacer:
                return None

    raw_fields = tuple(
        _sec_cover_cell_safety_text(rows[1][index]).replace("\u00a0", " ")
        for index in field_indices
    )
    values = tuple(fold(value) for value in raw_fields)
    if any(value is None for value in values):
        return None
    fields_to_check = raw_fields if safe_before_fold else values
    if not _sec_cover_text_safe(fields_to_check[0]) or not _sec_cover_text_safe(fields_to_check[2]):
        return None
    if not _TICKER.fullmatch(values[1]) or values[1] != values[1].upper():
        return None
    return table_id, rows, field_indices, values


def _table_cell_span(cell: dict):
    chunks = cell["chunks"]
    if not chunks:
        return None
    return min(item[1] for item in chunks), max(item[2] for item in chunks)


def _sec_layout_render_cover(
    source, parser, table_id, rows, field_indices, row, *, visible_parts=None
):
    """Shared v3/v4 cover projection; parsing policy remains version-specific."""
    if visible_parts is None:
        visible_parts = _render_chunks(
            source, _visible_chunks(parser, (table_id,))
        )
    visible_body, visible_anchors = visible_parts
    table_text = "\n".join(
        (
            _SEC_HEADER,
            "| --- | --- | --- |",
            "| {} | {} | {} |".format(*row),
        )
    )
    body = visible_body.rstrip("\n") + "\n" + table_text + "\n"
    anchors = list(visible_anchors)
    table_start = len(visible_body.rstrip("\n")) + 1
    for row_index, field_values in (
        (0, (_SEC_TITLE, _SEC_TICKER, _SEC_EXCHANGE)),
        (1, row),
    ):
        for column, (field, physical_index) in enumerate(zip(field_values, field_indices)):
            span = _table_cell_span(rows[row_index][physical_index])
            if span is None:
                return None
            if row_index == 0:
                parsed_start = table_start + _SEC_HEADER.index(field)
                parsed_end = parsed_start + len(field)
                anchor_field = "sec_cover.header.{}".format(column)
            else:
                table_row_start = table_start + len(_SEC_HEADER) + 1 + len(
                    "| --- | --- | --- |\n"
                )
                parsed_start = table_row_start + 2 + sum(
                    len(value) + 3 for value in row[:column]
                )
                parsed_end = parsed_start + len(field)
                anchor_field = "sec_cover.value.{}".format(column)
            anchors.append(
                _anchor(anchor_field, source, span[0], span[1], parsed_start, parsed_end)
            )
    if len(anchors) > 2048:
        return None
    return body, anchors, visible_body, visible_anchors


def _visible_chunks(parser: _BoundedHTML, excluded_table_ids=()):
    excluded = frozenset(excluded_table_ids)
    result = []
    for chunk in parser.chunks:
        if chunk.table_id in excluded:
            continue
        text = chunk.text
        if text == "\n" and result and result[-1][0].endswith("\n"):
            continue
        if text:
            result.append((text, chunk.raw_start, chunk.raw_end))
    return result


def _render_chunks(raw: str, chunks, excluded_raw_ranges=()):
    excluded = tuple(excluded_raw_ranges)
    pieces = []
    anchors = []
    position = 0
    for text, raw_start, raw_end in chunks:
        if raw_start == raw_end:
            if text == "\n" and pieces and pieces[-1].endswith("\n"):
                continue
            start = position
            pieces.append(text)
            position += len(text)
            continue
        if any(raw_start < end and raw_end > start for start, end in excluded):
            continue
        parsed_start = position
        pieces.append(text)
        position += len(text)
        anchors.append(
            _anchor("visible_text", raw, raw_start, raw_end, parsed_start, position)
        )
    return "".join(pieces), anchors


def _sec_html(source: str) -> Optional[_ParsedPage]:
    parser = _BoundedHTML(source).result()
    marker_lines = []
    rendered_all, _ = _render_chunks(source, _visible_chunks(parser))
    lines = rendered_all.splitlines()
    for index, line in enumerate(lines):
        if line.strip(" \t") == _SEC_MARKER:
            marker_lines.append(index)
    if len(marker_lines) != 1:
        return None
    marker_index = marker_lines[0]
    issuer_index = marker_index - 1
    while issuer_index >= 0 and not lines[issuer_index].strip(" \t"):
        issuer_index -= 1
    if issuer_index < 0:
        return None
    issuer = _ascii_space(lines[issuer_index])
    if not _issuer_valid(issuer):
        return None

    expected = tuple(value.casefold() for value in (_SEC_TITLE, _SEC_TICKER, _SEC_EXCHANGE))
    candidate_tables = []
    for table_id, table in enumerate(parser.tables):
        rows = table["rows"]
        if not rows or any(len(row) != 3 for row in rows):
            continue
        labels = tuple(_ascii_space(_cell_text(cell)).casefold() for cell in rows[0])
        if labels == expected:
            candidate_tables.append((table_id, table, rows))
    if len(candidate_tables) != 1:
        return None
    table_id, table, rows = candidate_tables[0]
    if len(rows) != 2:
        return None
    raw_row = tuple(_cell_text(cell) for cell in rows[1])
    row = tuple(_ascii_space(value) for value in raw_row)
    title, symbol, exchange = row
    if not _TICKER.fullmatch(symbol) or symbol != symbol.upper():
        return None
    if (
        title == "Ordinary shares, no par value"
        and exchange == "The Nasdaq Stock Market LLC"
    ):
        parser_id = "sec-edgar-cover-v1"
    else:
        if not _sec_cover_text_safe(_sec_cover_cell_safety_text(rows[1][0])) or not _sec_cover_text_safe(
            _sec_cover_cell_safety_text(rows[1][2])
        ):
            return None
        parser_id = "sec-edgar-cover-text-v2"

    # The source's registrant marker and name remain verbatim parsed text. Only
    # the actual HTML cover-table cells are rendered into the existing narrow
    # Markdown grammar; the raw-to-parsed anchors identify every consumed cell.
    table_range = (table["raw_start"], table["raw_end"] or len(source))
    visible_chunks = _visible_chunks(parser, (table_id,))
    visible_body, visible_anchors = _render_chunks(source, visible_chunks)
    if visible_body.count(_SEC_MARKER) != 1:
        return None
    table_text = "\n".join(
        (
            _SEC_HEADER,
            "| --- | --- | --- |",
            "| {} | {} | {} |".format(title, symbol, exchange),
        )
    )
    body = visible_body.rstrip("\n") + "\n" + table_text + "\n"
    anchors = list(visible_anchors)
    table_start = len(visible_body.rstrip("\n")) + 1
    for row_index, field_values in ((0, (_SEC_TITLE, _SEC_TICKER, _SEC_EXCHANGE)), (1, row)):
        for column, (field, cell) in enumerate(zip(field_values, rows[row_index])):
            span = _table_cell_span(cell)
            if span is None:
                return None
            if row_index == 0:
                parsed_start = table_start + _SEC_HEADER.index(field)
                parsed_end = parsed_start + len(field)
                anchor_field = "sec_cover.header.{}".format(column)
            else:
                table_row_start = table_start + len(_SEC_HEADER) + 1 + len("| --- | --- | --- |\n")
                parsed_start = table_row_start + 2 + sum(len(value) + 3 for value in row[:column])
                parsed_end = parsed_start + len(field)
                anchor_field = "sec_cover.value.{}".format(column)
            anchors.append(
                _anchor(anchor_field, source, span[0], span[1], parsed_start, parsed_end)
            )

    # The parser consumed the explicit issuer marker/name as well as the table.
    # Locate their raw text nodes and bind them to their exact parsed positions.
    for line_index, field in ((issuer_index, "sec_cover.registrant"), (marker_index, "sec_cover.registrant_marker")):
        target = lines[line_index].strip(" \t")
        if not target:
            continue
        matching = [
            chunk
            for chunk in parser.chunks
            if chunk.raw_start != chunk.raw_end and chunk.text.strip(" \t\r\n") == target
        ]
        if len(matching) == 1:
            chunk = matching[0]
            parsed_start = body.find(target)
            if parsed_start >= 0:
                anchors.append(
                    _anchor(field, source, chunk.raw_start, chunk.raw_end, parsed_start, parsed_start + len(target))
                )
    if len(anchors) > 2048:
        return None
    return _ParsedPage(body, parser_id, tuple(anchors), symbol.upper())


def _sec_cover_layout_v3(source: str) -> Optional[_ParsedPage]:
    """Parse the narrowly supported SEC cover layout with empty spacer cells."""
    parser = _BoundedHTML(source).result()
    rendered_all, _ = _render_chunks(source, _visible_chunks(parser))
    lines = rendered_all.splitlines()
    normalized_lines = [
        _ascii_space(line.replace("\u00a0", " ")) for line in lines
    ]
    marker_matches = [
        index for index, line in enumerate(normalized_lines) if line == _SEC_MARKER
    ]
    if len(marker_matches) != 1:
        return None
    marker_index = marker_matches[0]
    issuer_index = marker_index - 1
    while issuer_index >= 0 and not normalized_lines[issuer_index]:
        issuer_index -= 1
    if issuer_index < 0 or not _issuer_valid(normalized_lines[issuer_index]):
        return None

    cover_table = _sec_cover_layout_table(
        parser, _sec_cover_layout_v3_fold, safe_before_fold=True
    )
    if cover_table is None:
        return None
    table_id, rows, field_indices, row = cover_table
    _title, symbol, _exchange = row

    visible_parts = _render_chunks(
        source, _visible_chunks(parser, (table_id,))
    )
    visible_body, _visible_anchors = visible_parts
    visible_lines = visible_body.splitlines()
    if sum(
        _ascii_space(line.replace("\u00a0", " ")) == _SEC_MARKER
        for line in visible_lines
    ) != 1:
        return None
    projection = _sec_layout_render_cover(
        source, parser, table_id, rows, field_indices, row, visible_parts=visible_parts
    )
    if projection is None:
        return None
    body, anchors, visible_body, visible_anchors = projection

    visible_lines = visible_body.splitlines()
    visible_offsets = []
    visible_offset = 0
    for rendered_line in visible_body.splitlines(keepends=True):
        visible_offsets.append(visible_offset)
        visible_offset += len(rendered_line)
    visible_normalized_lines = [
        _ascii_space(line.replace("\u00a0", " ")) for line in visible_lines
    ]
    visible_markers = [
        index
        for index, line in enumerate(visible_normalized_lines)
        if line == _SEC_MARKER
    ]
    if len(visible_markers) != 1:
        return None
    visible_marker_index = visible_markers[0]
    visible_issuer_index = visible_marker_index - 1
    while visible_issuer_index >= 0 and not visible_normalized_lines[visible_issuer_index]:
        visible_issuer_index -= 1
    if visible_issuer_index < 0:
        return None
    for line_index, field in (
        (visible_issuer_index, "sec_cover.registrant"),
        (visible_marker_index, "sec_cover.registrant_marker"),
    ):
        line = visible_lines[line_index]
        target = line.strip(" \t")
        if not target:
            continue
        target_start = visible_offsets[line_index] + len(line) - len(line.lstrip(" \t"))
        target_end = target_start + len(target)
        matching = [
            anchor
            for anchor in visible_anchors
            if anchor.parsed_start < target_end and anchor.parsed_end > target_start
        ]
        if matching:
            anchors.append(
                _anchor(
                    field,
                    source,
                    min(anchor.raw_start for anchor in matching),
                    max(anchor.raw_end for anchor in matching),
                    target_start,
                    target_end,
                )
            )
    if len(anchors) > 2048:
        return None
    return _ParsedPage(body, "sec-edgar-cover-layout-v3", tuple(anchors), symbol)


class _SecCoverSemanticHTML(_BoundedHTML):
    """Collect visible SEC block text without treating pretty-print lines as blocks."""

    _SEGMENT_BLOCKS = _BLOCK_TAGS - frozenset(("br",))

    def __init__(self, source):
        super().__init__(source)
        self.semantic_segments = []
        self._semantic_chunks = []
        self._semantic_inline_break = False

    def _finish_semantic_segment(self):
        if self._semantic_chunks:
            self.semantic_segments.append(
                {
                    "text": "".join(chunk[0] for chunk in self._semantic_chunks),
                    "chunks": tuple(self._semantic_chunks),
                    "outside_table": all(chunk[3] is None for chunk in self._semantic_chunks),
                    "inline_break": self._semantic_inline_break,
                }
            )
        self._semantic_chunks = []
        self._semantic_inline_break = False

    @staticmethod
    def _hidden_start(tag, attrs):
        return tag in _HIDDEN_TAGS or any(
            name == "hidden"
            or (name == "aria-hidden" and value is not None
                and value.strip(_ASCII_WHITESPACE).lower() == "true")
            or (name == "style" and value is not None
                and any(_HIDDEN_STYLE.fullmatch(part) for part in value.split(";")))
            for name, value in attrs
        )

    def _append_text(self, text, raw_start, raw_end):
        super()._append_text(text, raw_start, raw_end)
        if self._hidden_stack or not text:
            return
        if raw_start == raw_end:
            if self._semantic_chunks and text in ("\n", "\n\n"):
                self._semantic_inline_break = True
            return
        table_id = self._table_stack[-1] if self._table_stack else None
        self._semantic_chunks.append((text, raw_start, raw_end, table_id))

    def handle_starttag(self, tag, attrs):
        normalized_tag = tag.casefold()
        if (
            not self._hidden_stack
            and normalized_tag in self._SEGMENT_BLOCKS
            and not self._hidden_start(normalized_tag, attrs)
        ):
            self._finish_semantic_segment()
        super().handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        normalized_tag = tag.casefold()
        if not self._hidden_stack and normalized_tag in self._SEGMENT_BLOCKS:
            self._finish_semantic_segment()
        super().handle_endtag(tag)

    def result(self):
        super().result()
        self._finish_semantic_segment()
        return self


def _sec_semantic_segment_anchor(source, field, segment, visible_anchors):
    mapped = []
    for _text, raw_start, raw_end, table_id in segment["chunks"]:
        if table_id is not None:
            return None
        matching = [
            anchor for anchor in visible_anchors
            if anchor.raw_start == raw_start and anchor.raw_end == raw_end
        ]
        if len(matching) != 1:
            return None
        mapped.append(matching[0])
    if not mapped:
        return None
    return _anchor(
        field,
        source,
        min(item.raw_start for item in mapped),
        max(item.raw_end for item in mapped),
        min(item.parsed_start for item in mapped),
        max(item.parsed_end for item in mapped),
    )


def _sec_cover_layout_v4(source: str) -> Optional[_ParsedPage]:
    """Parse v4's narrow cover grammar using complete visible semantic segments."""
    parser = _SecCoverSemanticHTML(source).result()
    marker_matches = [
        index
        for index, segment in enumerate(parser.semantic_segments)
        if segment["outside_table"]
        and not segment["inline_break"]
        and _sec_cover_layout_v4_fold(segment["text"]) == _SEC_MARKER
    ]
    if len(marker_matches) != 1:
        return None
    marker_index = marker_matches[0]

    issuer_index = marker_index - 1
    while issuer_index >= 0:
        issuer_segment = parser.semantic_segments[issuer_index]
        issuer_value = _sec_cover_layout_v4_fold(issuer_segment["text"])
        if issuer_value != "":
            break
        issuer_index -= 1
    if issuer_index < 0:
        return None
    issuer_segment = parser.semantic_segments[issuer_index]
    issuer_value = _sec_cover_layout_v4_fold(issuer_segment["text"])
    if (
        not issuer_segment["outside_table"]
        or issuer_segment["inline_break"]
        or issuer_value is None
        or not _issuer_valid(issuer_value)
    ):
        return None

    cover_table = _sec_cover_layout_table(
        parser, _sec_cover_layout_v4_fold, safe_before_fold=False
    )
    if cover_table is None:
        return None
    table_id, rows, field_indices, row_values = cover_table
    _title, symbol, _exchange = row_values

    projection = _sec_layout_render_cover(
        source, parser, table_id, rows, field_indices, row_values
    )
    if projection is None:
        return None
    body, anchors, _visible_body, visible_anchors = projection
    for index, field in (
        (issuer_index, "sec_cover.registrant"),
        (marker_index, "sec_cover.registrant_marker"),
    ):
        anchor = _sec_semantic_segment_anchor(
            source, field, parser.semantic_segments[index], visible_anchors
        )
        if anchor is None:
            return None
        anchors.append(anchor)
    if len(anchors) > 2048:
        return None
    return _ParsedPage(body, "sec-edgar-cover-layout-v4", tuple(anchors), symbol)


def _nasdaq_html(source: str, target_symbol: str) -> Optional[_ParsedPage]:
    parser = _BoundedHTML(source).result()
    candidates = []
    for heading in parser.headings:
        text = _ascii_space(heading.text)
        match = _NASDAQ_HEADING.fullmatch(text)
        if match is not None and _TICKER.fullmatch(match.group("symbol")):
            candidates.append((heading, text, match))
    if len(candidates) != 1:
        return None
    heading, text, match = candidates[0]
    issuer = _ascii_space(match.group("issuer"))
    symbol = match.group("symbol")
    if not _issuer_valid(issuer) or symbol.upper() != target_symbol:
        return None
    body = "#" * heading.level + " " + text + "\n"
    prefix = "#" * heading.level + " "
    anchor = _anchor(
        "nasdaq.instrument_heading",
        source,
        heading.raw_start,
        heading.raw_end,
        len(prefix),
        len(body.rstrip("\n")),
    )
    return _ParsedPage(body, "nasdaq-instrument-v1", (anchor,), symbol.upper())


def _yahoo_html(source: str, target_symbol: str) -> Optional[_ParsedPage]:
    parser = _BoundedHTML(source).result()
    visible, _anchors = _render_chunks(source, _visible_chunks(parser))
    visible_lines = [(line, start, end) for line, start, end in _line_spans(visible)]
    quote_candidates = [
        (line, start, end)
        for line, start, end in visible_lines
        if "quote" in line.casefold()
    ]
    heading_candidates = []
    for heading in parser.headings:
        text = _ascii_space(heading.text)
        match = _YAHOO_HEADING.fullmatch(text)
        if match is not None and _TICKER.fullmatch(match.group("symbol")):
            heading_candidates.append((heading, text, match))
    if len(quote_candidates) != 1 or len(heading_candidates) != 1:
        return None
    quote, _quote_start, _quote_end = quote_candidates[0]
    heading, text, match = heading_candidates[0]
    issuer = _ascii_space(match.group("issuer"))
    symbol = match.group("symbol")
    if quote != _YAHOO_QUOTE or not _issuer_valid(issuer) or symbol.upper() != target_symbol:
        return None
    if visible.find(quote) > visible.find(text):
        return None
    body = quote + "\n\n# " + text + "\n"
    quote_pos = body.find(quote)
    heading_pos = body.rfind("# " + text)
    # Anchor exact source text nodes; the spans may include inline HTML tags.
    quote_raw = _visible_text_raw_span(parser, quote)
    if quote_raw is None:
        return None
    anchors = (
        _anchor("yahoo.quote_denomination", source, quote_raw[0], quote_raw[1], quote_pos, quote_pos + len(quote)),
        _anchor("yahoo.instrument_heading", source, heading.raw_start, heading.raw_end, heading_pos + 2, heading_pos + 2 + len(text)),
    )
    return _ParsedPage(body, "yahoo-quote-header-v1", anchors, symbol.upper())


def _line_spans(body: str):
    offset = 0
    for line in body.splitlines(keepends=True):
        end = offset + len(line.rstrip("\r\n"))
        yield line.rstrip("\r\n"), offset, end
        offset += len(line)
    if body and not body.endswith(("\n", "\r")) and offset == 0:
        yield body, 0, len(body)


def _visible_text_raw_span(parser: _BoundedHTML, text: str):
    chunks = [chunk for chunk in parser.chunks if chunk.raw_start != chunk.raw_end]
    visible = "".join(chunk.text for chunk in chunks)
    start = visible.find(text)
    if start < 0 or visible.find(text, start + 1) >= 0:
        return None
    end = start + len(text)
    position = 0
    spans = []
    for chunk in chunks:
        next_position = position + len(chunk.text)
        if position < end and next_position > start:
            spans.append((chunk.raw_start, chunk.raw_end))
        position = next_position
    return (min(item[0] for item in spans), max(item[1] for item in spans)) if spans else None


def _parse_page(
    family: str,
    body: str,
    target_symbol: Optional[str],
    content_type: str,
    *,
    sec_reference_symbols: Optional[Tuple[str, ...]] = None,
) -> Optional[_ParsedPage]:
    try:
        if sec_reference_symbols is not None:
            if family != "sec" or content_type != "application/json":
                return None
            return _sec_issuer_reference_json_v2(body, sec_reference_symbols)
        if content_type != "text/html":
            return None
        if family == "sec":
            parsed = _sec_html(body)
            if parsed is not None:
                return parsed
            parsed = _sec_cover_layout_v3(body)
            return parsed if parsed is not None else _sec_cover_layout_v4(body)
        if family == "nasdaq":
            return None if target_symbol is None else _nasdaq_html(body, target_symbol)
        if family == "yahoo":
            return None if target_symbol is None else _yahoo_html(body, target_symbol)
    except (ValueError, RecursionError):
        return None
    return None


class _SourceAdmissionClient:
    """Per-run bounded retrieval client; underscore-prefixed by design."""

    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_response_bytes: int,
        byte_budget: int,
        _transport: Optional[Callable] = None,
        _resolver: Optional[Callable[[str, int], Sequence[str]]] = None,
        _clock: Optional[Callable[[], datetime.datetime]] = None,
        _monotonic: Optional[Callable[[], float]] = None,
    ):
        if type(timeout_seconds) not in (int, float) or timeout_seconds <= 0:
            raise ValueError("timeout must be positive")
        if type(max_response_bytes) is not int or max_response_bytes <= 0:
            raise ValueError("max response bytes must be positive")
        if type(byte_budget) is not int or byte_budget < 0:
            raise ValueError("byte budget must be nonnegative")
        if _transport is not None and (_resolver is None or not callable(_resolver)):
            raise ValueError("synthetic transport requires a synthetic resolver")
        if _transport is not None and not callable(_transport):
            raise TypeError("synthetic transport must be callable")
        if _clock is not None and not callable(_clock):
            raise TypeError("clock must be callable")
        if _monotonic is not None and not callable(_monotonic):
            raise TypeError("monotonic clock must be callable")
        self._timeout = float(timeout_seconds)
        self._max_response_bytes = max_response_bytes
        self._byte_budget = byte_budget
        self._transport = _transport
        self._resolver = _resolver or _default_resolver
        self._clock = _clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        self._monotonic = _monotonic or time.monotonic
        self._request_count = 0
        self._dns_count = 0
        self._response_bytes = 0
        self._sec_reference_issuance_receipt = None

    def admit_candidates(self, locators: Sequence[str]) -> AdmissionBatch:
        if not isinstance(locators, (tuple, list)):
            raise TypeError("candidate locators must be a sequence")
        deadline = self._monotonic() + self._timeout * MAX_SOURCE_ADMISSION_REQUESTS
        candidates = []
        seen = set()
        failures = []
        for locator in locators:
            target = _family_target(locator)
            if target is None:
                continue
            if locator in seen:
                continue
            seen.add(locator)
            candidates.append((locator, target))

        # Give an explicit SEC cover row the opportunity to authorize only its
        # own ticker's two bounded identity supplements before other candidates.
        candidates.sort(key=lambda item: (0 if item[1][0] == "sec" else 1, locators.index(item[0])))
        admissions = []
        attempted = set()
        admitted_symbols = set()
        for locator, target in candidates:
            if self._request_count >= MAX_SOURCE_ADMISSION_REQUESTS:
                failures.append(AdmissionFailure("REQUEST_LIMIT_REACHED"))
                break
            if locator in attempted:
                continue
            attempted.add(locator)
            result, failure = self._admit_one(locator, target, deadline)
            if failure is not None:
                failures.append(failure)
                continue
            admissions.append(result)
            if (
                target[0] == "sec"
                and result.parser_id == "sec-edgar-cover-v1"
                and result.parsed_symbol
            ):
                admitted_symbols.add(result.parsed_symbol)
                supplements = (
                    "https://www.nasdaq.com/market-activity/stocks/{}".format(result.parsed_symbol.lower()),
                    "https://finance.yahoo.com/quote/{}/".format(result.parsed_symbol),
                )
                for supplement in supplements:
                    supplement_target = _family_target(supplement)
                    if supplement_target is None:
                        continue
                    if any(
                        old_target[0] == supplement_target[0]
                        and old_target[2][0] == result.parsed_symbol
                        for _old_locator, old_target in candidates
                    ):
                        continue
                    if self._request_count >= MAX_SOURCE_ADMISSION_REQUESTS:
                        break
                    if supplement in attempted:
                        continue
                    attempted.add(supplement)
                    supplemental, supplement_failure = self._admit_one(
                        supplement, supplement_target, deadline
                    )
                    if supplement_failure is not None:
                        failures.append(supplement_failure)
                    else:
                        admissions.append(supplemental)
        return AdmissionBatch(
            tuple(admissions), tuple(failures), self._request_count, self._response_bytes
        )

    def admit_sec_reference(self, symbols: Tuple[str, ...]) -> AdmissionBatch:
        """Admit only explicitly selected rows from the SEC issuer reference."""
        self._sec_reference_issuance_receipt = None
        if type(symbols) is not tuple:
            raise TypeError("SEC reference symbols must be an exact tuple")
        if not symbols or any(
            type(symbol) is not str
            or _TICKER.fullmatch(symbol) is None
            or symbol != symbol.upper()
            for symbol in symbols
        ):
            raise ValueError("SEC reference symbols must be nonempty canonical uppercase tickers")
        if len(set(symbols)) != len(symbols):
            raise ValueError("SEC reference symbols must be unique")
        target = _sec_reference_target(_SEC_REFERENCE_LOCATOR)
        deadline = self._monotonic() + self._timeout * MAX_SOURCE_ADMISSION_REQUESTS
        admission, failure = self._admit_one(
            _SEC_REFERENCE_LOCATOR,
            target,
            deadline,
            sec_reference_symbols=symbols,
        )
        return AdmissionBatch(
            (admission,) if admission is not None else (),
            (failure,) if failure is not None else (),
            self._request_count,
            self._response_bytes,
        )

    def _revalidate_sec_reference(
        self, record: object, symbols: Tuple[str, ...], *, max_parsed_bytes: int
    ) -> Optional[SourceAdmission]:
        receipt = self._sec_reference_issuance_receipt
        if (
            type(receipt) is not tuple
            or len(receipt) != 2
            or type(receipt[0]) is not tuple
            or type(receipt[1]) is not tuple
            or type(symbols) is not tuple
            or symbols != receipt[0]
            or _sec_reference_record_snapshot(record) != receipt[1]
        ):
            return None
        return _revalidate_source_admission(
            record,
            max_raw_bytes=record.raw_body_bytes,
            max_parsed_bytes=max_parsed_bytes,
            _sec_reference_issuance_receipt=receipt,
        )

    def _one_get(
        self, locator: str, address: str, timeout: float, max_bytes: int
    ) -> _Reply:
        if self._transport is not None:
            reply = self._transport(locator, address, timeout, max_bytes)
            if type(reply) is not _Reply:
                raise _AdmissionProblem("TRANSPORT_FAILED")
            return reply
        return _fetch_response(locator, address, timeout, max_bytes)

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise _AdmissionProblem("ADMISSION_DEADLINE_EXCEEDED")
        return remaining

    def _request(
        self,
        locator: str,
        initial_target,
        deadline: float,
        *,
        sec_reference_symbols: Optional[Tuple[str, ...]] = None,
    ):
        is_sec_reference = sec_reference_symbols is not None
        if is_sec_reference and initial_target[0] != "sec-reference":
            raise _AdmissionProblem("URL_NOT_ADMISSIBLE")

        def target_for(current_locator):
            return (
                _sec_reference_target(current_locator)
                if is_sec_reference
                else _family_target(current_locator)
            )

        current = locator
        redirects = 0
        while True:
            remaining = self._remaining(deadline)
            if self._request_count >= MAX_SOURCE_ADMISSION_REQUESTS:
                raise _AdmissionProblem("REQUEST_LIMIT_REACHED")
            current_target = target_for(current)
            if current_target is None or not _same_target(initial_target, current_target):
                raise _AdmissionProblem("REDIRECT_INVALID")
            if self._dns_count >= MAX_SOURCE_ADMISSION_REQUESTS:
                raise _AdmissionProblem("DNS_LIMIT_REACHED")
            self._dns_count += 1
            host = current_target[1].hostname
            addresses = _safe_addresses(
                host,
                self._resolver,
                timeout_seconds=min(self._timeout, remaining),
                deadline=deadline,
                monotonic=self._monotonic,
            )
            remaining = self._remaining(deadline)
            remaining_bytes = self._byte_budget - self._response_bytes
            cap = min(self._max_response_bytes, remaining_bytes)
            if cap <= 0:
                raise _AdmissionProblem("BODY_LIMIT_EXCEEDED")
            self._request_count += 1
            try:
                reply = self._one_get(
                    current, addresses[0], min(self._timeout, remaining), cap
                )
            except _AdmissionProblem:
                raise
            except (OSError, http.client.HTTPException, ssl.SSLError, TimeoutError):
                if deadline - self._monotonic() <= 0:
                    raise _AdmissionProblem("ADMISSION_DEADLINE_EXCEEDED") from None
                raise _AdmissionProblem("TRANSPORT_FAILED") from None
            except Exception:
                if deadline - self._monotonic() <= 0:
                    raise _AdmissionProblem("ADMISSION_DEADLINE_EXCEEDED") from None
                raise _AdmissionProblem("TRANSPORT_FAILED") from None
            self._remaining(deadline)
            if type(reply.status) is not int or not isinstance(reply.headers, Mapping) or type(reply.body) is not bytes:
                raise _AdmissionProblem("TRANSPORT_FAILED")
            if reply.status in (301, 302, 303, 307, 308):
                if redirects >= MAX_SOURCE_ADMISSION_REDIRECTS:
                    raise _AdmissionProblem("REDIRECT_LIMIT")
                location = _header(reply.headers, "Location")
                if not location:
                    raise _AdmissionProblem("REDIRECT_INVALID")
                next_locator = urljoin(current, location)
                next_target = target_for(next_locator)
                if next_target is None or not _same_target(initial_target, next_target):
                    raise _AdmissionProblem("REDIRECT_INVALID")
                current = next_locator
                redirects += 1
                continue
            if reply.status != 200:
                raise _AdmissionProblem("HTTP_STATUS_UNSUPPORTED")
            if len(reply.body) > cap:
                self._response_bytes += cap + 1
                raise _AdmissionProblem("BODY_LIMIT_EXCEEDED")
            self._response_bytes += len(reply.body)
            content_type = _content_type(reply.headers, allow_json=is_sec_reference)
            if content_type is None:
                raise _AdmissionProblem("CONTENT_TYPE_UNSUPPORTED")
            if is_sec_reference and content_type != "application/json":
                raise _AdmissionProblem("CONTENT_TYPE_UNSUPPORTED")
            content_encoding = _header(reply.headers, "Content-Encoding")
            if content_encoding not in (None, "", "identity"):
                raise _AdmissionProblem("CONTENT_TYPE_UNSUPPORTED")
            try:
                decoded = reply.body.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                raise _AdmissionProblem("UTF8_DECODE_FAILED") from None
            parsed = _parse_page(
                "sec" if is_sec_reference else initial_target[0],
                decoded,
                initial_target[2][0]
                if not is_sec_reference and initial_target[0] != "sec"
                else None,
                content_type,
                sec_reference_symbols=sec_reference_symbols,
            )
            if parsed is None:
                raise _AdmissionProblem("PARSER_UNSUPPORTED")
            self._remaining(deadline)
            return current, initial_target, content_type, reply.body, parsed

    def _admit_one(
        self,
        initial_locator: str,
        target,
        deadline: float,
        *,
        sec_reference_symbols: Optional[Tuple[str, ...]] = None,
    ):
        try:
            final_locator, _target, content_type, raw_body, parsed = self._request(
                initial_locator,
                target,
                deadline,
                sec_reference_symbols=sec_reference_symbols,
            )
            self._remaining(deadline)
            now = self._clock()
            if type(now) is not datetime.datetime or now.tzinfo is None or now.utcoffset() is None:
                raise _AdmissionProblem("TRANSPORT_FAILED")
            final_target = (
                _sec_reference_target(final_locator)
                if sec_reference_symbols is not None
                else _family_target(final_locator)
            )
            family = "sec" if sec_reference_symbols is not None else final_target[0]
            final_url = final_target[1]
            parser_metadata = _PARSER_METADATA.get(parsed.parser_id)
            if parser_metadata is None or parser_metadata[0] != family:
                raise _AdmissionProblem("PARSER_UNSUPPORTED")
            source_id = _source_id_for_locator(initial_locator)
            admission = SourceAdmission(
                source_id=source_id,
                family=family,
                initial_locator=initial_locator,
                final_locator=final_locator,
                origin="https://{}".format(final_url.hostname),
                retrieved_at=now.astimezone(datetime.timezone.utc),
                content_type=content_type,
                raw_body_sha256=hashlib.sha256(raw_body).hexdigest(),
                raw_body_bytes=len(raw_body),
                parser_id=parsed.parser_id,
                parser_version=parser_metadata[1],
                parsed_body_sha256=hashlib.sha256(parsed.body.encode("utf-8")).hexdigest(),
                parsed_body=parsed.body,
                raw_anchors=parsed.anchors,
                parsed_symbol=parsed.symbol,
            )
            if sec_reference_symbols is not None:
                snapshot = _sec_reference_record_snapshot(admission)
                if snapshot is None:
                    raise _AdmissionProblem("PARSER_UNSUPPORTED")
                self._sec_reference_issuance_receipt = (
                    sec_reference_symbols,
                    snapshot,
                )
            return admission, None
        except _AdmissionProblem as error:
            return None, AdmissionFailure(error.code)
        except Exception:
            return None, AdmissionFailure("TRANSPORT_FAILED")


def _create_source_admission_client(
    *, timeout_seconds: float, max_response_bytes: int, byte_budget: int
) -> _SourceAdmissionClient:
    """Private factory kept separate so fixture drivers can patch it offline."""
    return _SourceAdmissionClient(
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        byte_budget=byte_budget,
    )
