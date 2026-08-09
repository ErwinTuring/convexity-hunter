"""Bounded direct access to the U.S. Treasury daily par-yield curve."""

import csv as _csv
import datetime as _datetime
import decimal as _decimal
import hashlib as _hashlib
import io as _io
import urllib.error as _urllib_error
import urllib.request as _urllib_request
from typing import Dict as _Dict
from typing import List as _List
from typing import Tuple as _Tuple
from zoneinfo import ZoneInfo as _ZoneInfo

from convexity_hunter.market_data import (
    DataOrigin as _DataOrigin,
    NormalizationMetadata as _NormalizationMetadata,
    NormalizationQualityFlag as _NormalizationQualityFlag,
    RateCurvePointObservation as _RateCurvePointObservation,
    SourceQualityFlag as _SourceQualityFlag,
    SourceReference as _SourceReference,
)


__all__ = ("retrieve_us_treasury_daily_par_yield_curve",)


_NORMALIZATION_VERSION = "us-treasury-daily-par-yield-v0.1"
_OFFICIAL_ENDPOINT = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv"
    "/{year}/all"
    "?_format=csv&field_tdr_date_value={year}&page=&type=daily_treasury_yield_curve"
)
_USER_AGENT = "ConvexityHunter/0.1"
_REQUEST_TIMEOUT_SECONDS = 10.0
_MAX_RESPONSE_BYTES = 1024 * 1024
_EASTERN = _ZoneInfo("America/New_York")
_REQUIRED_COLUMNS = (
    "Date",
    "1 Mo",
    "1.5 Month",
    "2 Mo",
    "3 Mo",
    "4 Mo",
    "6 Mo",
)
_TENOR_DEFINITIONS = (
    ("1 Mo", 30),
    ("1.5 Month", 45),
    ("2 Mo", 60),
    ("3 Mo", 90),
    ("4 Mo", 120),
    ("6 Mo", 180),
)

_RETRIEVAL_ERROR = "U.S. Treasury curve retrieval failed"
_RESPONSE_ERROR = "U.S. Treasury curve response is invalid"
_BODY_SIZE_ERROR = "U.S. Treasury curve response exceeds 1 MiB"
_DATE_ROW_ERROR = (
    "U.S. Treasury curve response does not contain exactly one requested "
    "effective-date row"
)
_RATE_ERROR = "U.S. Treasury curve response contains invalid rate values"
_NORMALIZATION_ERROR = "U.S. Treasury curve normalization failed"

_TIMESTAMP_METHODOLOGY = (
    "Assigned nominal 3:30 PM America/New_York on the Treasury effective date "
    "from the official methodology; not an exact trade, quote, publication, "
    "or retrieval timestamp."
)
_NORMALIZATION_METHODOLOGY = (
    "Treasury percentage strings are parsed as Decimal and divided by exact "
    "Decimal('100'); provider labels use the fixed 30/45/60/90/120/180-day "
    "normalization mapping; provider-native nominal bond-equivalent par-yield "
    "semantics are preserved; 3:30 PM America/New_York is assigned because "
    "the CSV supplies only the effective date."
)
_UNIT_CONVENTION = (
    "Annualized decimal rate after exact Treasury percentage-to-decimal "
    "conversion; tenor_days are the fixed Convexity Hunter mapping for the "
    "named Treasury maturities."
)


def _utc_now() -> _datetime.datetime:
    return _datetime.datetime.now(_datetime.timezone.utc)


def _request_uri(effective_date: _datetime.date) -> str:
    year = str(effective_date.year)
    return _OFFICIAL_ENDPOINT.format(year=year)


class _NoRedirectHandler(_urllib_request.HTTPRedirectHandler):
    """Fail on a redirect instead of allowing urllib to issue another GET."""

    def redirect_request(
        self,
        request: _urllib_request.Request,
        response: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> object:
        raise _urllib_error.HTTPError(
            request.full_url,
            code,
            "redirects are disabled",
            headers,
            response,
        )


def _urlopen(request: _urllib_request.Request, *, timeout: float) -> object:
    opener = _urllib_request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def _validate_transport_response(response: object, request_uri: str) -> None:
    try:
        status = getattr(response, "status", None)
        if status is None:
            getcode = getattr(response, "getcode", None)
            status = getcode() if callable(getcode) else None
        if status is not None and (
            isinstance(status, bool)
            or not isinstance(status, int)
            or status < 200
            or status >= 300
        ):
            raise RuntimeError(_RETRIEVAL_ERROR)

        geturl = getattr(response, "geturl", None)
        if callable(geturl):
            response_uri = geturl()
            if response_uri and response_uri != request_uri:
                raise RuntimeError(_RETRIEVAL_ERROR)
    except RuntimeError:
        raise
    except Exception:
        raise RuntimeError(_RETRIEVAL_ERROR) from None


def _retrieve_body(request_uri: str) -> _Tuple[bytes, _datetime.datetime]:
    request = _urllib_request.Request(
        request_uri,
        headers={"User-Agent": _USER_AGENT},
        method="GET",
    )
    try:
        response = _urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS)
        try:
            _validate_transport_response(response, request_uri)
            body = response.read(_MAX_RESPONSE_BYTES + 1)  # type: ignore[attr-defined]
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
    except Exception:
        raise RuntimeError(_RETRIEVAL_ERROR) from None

    if type(body) is not bytes:
        raise ValueError(_RESPONSE_ERROR)
    if len(body) > _MAX_RESPONSE_BYTES:
        raise ValueError(_BODY_SIZE_ERROR)
    return body, _utc_now()


def _parse_rate(raw_value: str) -> _decimal.Decimal:
    try:
        if type(raw_value) is not str:
            raise ValueError(_RATE_ERROR)
        text = raw_value.strip()
        if not text:
            raise ValueError(_RATE_ERROR)
        percentage = _decimal.Decimal(text)
        if not percentage.is_finite():
            raise ValueError(_RATE_ERROR)

        # Dividing by 100 only shifts a finite Decimal's exponent by -2.
        # Constructing from the tuple bypasses ambient precision and exponent
        # bounds, so tiny finite values cannot underflow to zero.
        sign, digits, exponent = percentage.as_tuple()
        normalized = _decimal.Decimal((sign, digits, exponent - 2))
        if not normalized.is_finite():
            raise ValueError(_RATE_ERROR)
        return normalized
    except Exception:
        raise ValueError(_RATE_ERROR) from None


def _parse_selected_rates(
    body: bytes, effective_date: _datetime.date
) -> _Dict[str, _decimal.Decimal]:
    try:
        text = body.decode("utf-8-sig")
        rows = list(_csv.reader(_io.StringIO(text, newline=""), strict=True))
    except Exception:
        raise ValueError(_RESPONSE_ERROR) from None

    if not rows:
        raise ValueError(_RESPONSE_ERROR)
    header = rows[0]
    if len(header) != len(set(header)):
        raise ValueError(_RESPONSE_ERROR)
    if any(header.count(column) != 1 for column in _REQUIRED_COLUMNS):
        raise ValueError(_RESPONSE_ERROR)

    positions = {column: header.index(column) for column in _REQUIRED_COLUMNS}
    expected_date = effective_date.strftime("%m/%d/%Y")
    matching_rows = []
    date_position = positions["Date"]
    for row in rows[1:]:
        if len(row) > date_position and row[date_position] == expected_date:
            matching_rows.append(row)
    if len(matching_rows) != 1:
        raise ValueError(_DATE_ROW_ERROR)

    selected_row = matching_rows[0]
    rates = {}
    for label, _ in _TENOR_DEFINITIONS:
        position = positions[label]
        if position >= len(selected_row):
            raise ValueError(_RATE_ERROR)
        rates[label] = _parse_rate(selected_row[position])
    return rates


def _assigned_observation_time(effective_date: _datetime.date) -> _datetime.datetime:
    local_time = _datetime.datetime.combine(
        effective_date,
        _datetime.time(15, 30),
        tzinfo=_EASTERN,
    )
    return local_time.astimezone(_datetime.timezone.utc)


def _stable_identity(
    prefix: str,
    effective_date: _datetime.date,
    label: str,
    response_digest: str,
) -> str:
    return ":".join(
        (
            prefix,
            _NORMALIZATION_VERSION,
            response_digest,
            effective_date.isoformat(),
            label,
        )
    )


def _build_observations(
    effective_date: _datetime.date,
    rates: _Dict[str, _decimal.Decimal],
    response_digest: str,
    request_uri: str,
    retrieved_at: _datetime.datetime,
) -> _Tuple[_RateCurvePointObservation, ...]:
    observed_at = _assigned_observation_time(effective_date)
    normalized_at = _utc_now()
    observations: _List[_RateCurvePointObservation] = []
    try:
        for label, tenor_days in _TENOR_DEFINITIONS:
            source_id = _stable_identity(
                "us-treasury-source", effective_date, label, response_digest
            )
            record_id = _stable_identity(
                "us-treasury-rate", effective_date, label, response_digest
            )
            source = _SourceReference(
                source_id=source_id,
                provider_name="U.S. Department of the Treasury",
                dataset_name="Daily Treasury Par Yield Curve Rates",
                provider_record_id=effective_date.isoformat() + ":" + label,
                provider_request_id=None,
                source_symbol=None,
                source_uri=request_uri,
                observed_at=observed_at,
                retrieved_at=retrieved_at,
                provider_timezone="America/New_York",
                timestamp_methodology=_TIMESTAMP_METHODOLOGY,
                origin=_DataOrigin.PROVIDER_CALCULATED,
                is_delayed=False,
                declared_delay_seconds=None,
                payload_sha256=response_digest,
                revision_number=None,
                provider_correction_id=None,
                quality_flags=(
                    _SourceQualityFlag.INDICATIVE,
                    _SourceQualityFlag.NON_FIRM,
                ),
            )
            metadata = _NormalizationMetadata(
                record_id=record_id,
                source_references=(source,),
                effective_observed_at=observed_at,
                normalized_at=normalized_at,
                record_origin=_DataOrigin.PROVIDER_CALCULATED,
                normalization_methodology=_NORMALIZATION_METHODOLOGY,
                unit_convention=_UNIT_CONVENTION,
                normalization_version=_NORMALIZATION_VERSION,
                quality_flags=(
                    _NormalizationQualityFlag.UNIT_CONVERTED,
                    _NormalizationQualityFlag.TIMESTAMP_ASSIGNED,
                ),
            )
            observations.append(
                _RateCurvePointObservation(
                    curve_id="USD-US-TREASURY-DAILY-PAR-YIELD",
                    currency="USD",
                    tenor_days=tenor_days,
                    annualized_rate=rates[label],
                    compounding_convention=(
                        "Bond-equivalent yield; simple annualized with "
                        "semiannual interest convention"
                    ),
                    day_count_convention="Actual days; 365- or 366-day year",
                    effective_date=effective_date,
                    metadata=metadata,
                )
            )
    except Exception:
        raise ValueError(_NORMALIZATION_ERROR) from None
    return tuple(observations)


def retrieve_us_treasury_daily_par_yield_curve(
    *, effective_date: _datetime.date
) -> _Tuple[_RateCurvePointObservation, ...]:
    """Retrieve one exact-date, six-point U.S. Treasury par-yield curve."""

    if type(effective_date) is not _datetime.date:
        raise TypeError("effective_date must be an exact datetime.date")

    request_uri = _request_uri(effective_date)
    body, retrieved_at = _retrieve_body(request_uri)
    rates = _parse_selected_rates(body, effective_date)
    response_digest = _hashlib.sha256(body).hexdigest()
    return _build_observations(
        effective_date,
        rates,
        response_digest,
        request_uri,
        retrieved_at,
    )
