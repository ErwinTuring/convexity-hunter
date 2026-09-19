"""Small Futu adapters used by the current Core application.

The application keeps provider calls behind this module.  The adapters retain
the provider's immutable verification/browser/quote records; they do not
create a second contract or quote model.  Direct entry deliberately uses one
option ``get_order_book`` call and does not require an underlying BBO.
"""

import datetime as _datetime
import decimal as _decimal
import math as _math
from dataclasses import dataclass as _dataclass
from enum import Enum as _Enum
from typing import Callable as _Callable
from typing import Optional as _Optional

from .market_data import UnderlyingKey as _UnderlyingKey
from .market_data import UnderlyingSecurityType as _UnderlyingSecurityType
from .option_chain_discovery import OptionChainDiscoveryRequest
from .providers import futu as _futu


__all__ = (
    "NativeQuoteAuthority",
    "FutuNativeDirectAskReceipt",
    "FutuNativeDirectAskEvidence",
    "FutuMarketBridge",
    "discover_futu_browser",
    "verify_futu_browser_row",
    "retrieve_futu_browser_quote_batch",
    "retrieve_futu_native_direct_ask_evidence",
)


class NativeQuoteAuthority(str, _Enum):
    """The only authority claimed by a direct native ask in this phase."""

    INDICATIVE_ONLY = "indicative_only"


@_dataclass(frozen=True)
class FutuNativeDirectAskReceipt:
    """Sanitized receipt for one exact-option native order-book operation."""

    operation: str
    provider_identifier: str
    received_at: _datetime.datetime

    def __post_init__(self) -> None:
        if self.operation != "get_order_book":
            raise ValueError("operation must be get_order_book")
        _require_nonblank("provider_identifier", self.provider_identifier)
        if type(self.received_at) is not _datetime.datetime:
            raise TypeError("received_at must be a datetime")
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")
        object.__setattr__(
            self, "received_at", self.received_at.astimezone(_datetime.timezone.utc)
        )


def _require_nonblank(name: str, value: object) -> str:
    if type(value) is not str or not value.strip():
        raise TypeError(f"{name} must be a non-empty string")
    return value


def _validate_optional_ask(value: object) -> _Optional[_decimal.Decimal]:
    if value is None:
        return None
    if type(value) is not _decimal.Decimal:
        raise TypeError("ask_per_underlying_unit must be a Decimal or None")
    if not value.is_finite() or value <= 0:
        raise ValueError("ask_per_underlying_unit must be finite and positive")
    return value


def _validate_optional_size(value: object) -> _Optional[int]:
    if value is None:
        return None
    if type(value) is not int or isinstance(value, bool) or value <= 0:
        raise ValueError("ask_size must be a positive integer or None")
    return value


@_dataclass(frozen=True)
class FutuNativeDirectAskEvidence:
    """One exact-option native ask result without broader quote semantics.

    ``receipt`` is retained as returned by the SDK adapter.  It is evidence of
    the provider operation, not a timestamp/session/freshness assertion.
    """

    provider_identifier: str
    ask_per_underlying_unit: _Optional[_decimal.Decimal]
    ask_size: _Optional[int]
    receipt: FutuNativeDirectAskReceipt
    quote_authority: NativeQuoteAuthority
    reason_code: object = None

    def __post_init__(self) -> None:
        identifier = _require_nonblank("provider_identifier", self.provider_identifier)
        ask = _validate_optional_ask(self.ask_per_underlying_unit)
        size = _validate_optional_size(self.ask_size)
        if type(self.receipt) is not FutuNativeDirectAskReceipt:
            raise TypeError("receipt must be FutuNativeDirectAskReceipt")
        if type(self.quote_authority) is not NativeQuoteAuthority:
            raise TypeError("quote_authority must be NativeQuoteAuthority")
        if (ask is None) != (size is None):
            raise ValueError("ask and ask_size must be present or absent together")
        object.__setattr__(self, "provider_identifier", identifier)

    @property
    def ask_price(self) -> _Optional[_decimal.Decimal]:
        """Compatibility spelling for the provider's ask price."""

        return self.ask_per_underlying_unit

    @property
    def authority(self) -> NativeQuoteAuthority:
        return self.quote_authority


def _validate_timeout(timeout_seconds: object) -> float:
    if isinstance(timeout_seconds, bool) or not isinstance(
        timeout_seconds, (int, float)
    ):
        raise TypeError("timeout_seconds must be a number")
    timeout = float(timeout_seconds)
    if not _math.isfinite(timeout) or timeout <= 0 or timeout > 60:
        raise ValueError("timeout_seconds must be greater than 0 and at most 60")
    return timeout


def discover_futu_browser(
    quote_context: object,
    discovery_request: OptionChainDiscoveryRequest,
):
    """Run the existing bounded chain discovery and create its neutral Browser."""

    evidence = _futu.retrieve_futu_option_chain_discovery_evidence(
        quote_context, discovery_request=discovery_request
    )
    return _futu.create_futu_exact_contract_browser(evidence)


def verify_futu_browser_row(
    quote_context: object,
    discovery_request: OptionChainDiscoveryRequest,
    row: object,
):
    """Verify one retained Browser row using the existing exact Futu call."""

    if type(row) is not _futu.FutuOptionChainContractEvidence:
        raise TypeError("row must be a FutuOptionChainContractEvidence")
    return _futu.verify_futu_monthly_option_contract(
        quote_context,
        underlying_key=discovery_request.underlying_key,
        expiration=row.expiration,
        option_type=row.option_type,
        strike=row.strike,
    )


def retrieve_futu_browser_quote_batch(
    quote_context: object,
    browser: object,
    *,
    timeout_seconds: object,
):
    """Retrieve exactly one existing provider quote batch for one Browser."""

    _validate_timeout(timeout_seconds)
    return _futu.retrieve_futu_browser_quote_batch_evidence(
        quote_context, browser, timeout_seconds=float(timeout_seconds)
    )


def _as_order_book_frame(data: object, provider_identifier: str) -> dict:
    """Accept only the SDK's native order-book dictionary shape."""

    if type(data) is not dict or data.get("code") != provider_identifier:
        raise ValueError("Futu native order-book response is invalid")
    # The option-only operation consumes the ask side.  Bid is optional and
    # is inspected only for the crossed-market diagnostic.
    if "Ask" not in data:
        raise ValueError("Futu native order-book response is invalid")
    return data


def _subscribe_exact_option_order_book(
    quote_context: object, provider_identifier: str
) -> None:
    subscribe = getattr(quote_context, "subscribe", None)
    if not callable(subscribe):
        raise TypeError("quote_context must provide subscribe")
    sdk = _futu._load_futu_sdk()
    try:
        response = subscribe(
            [provider_identifier],
            [sdk.SubType.ORDER_BOOK],
            subscribe_push=False,
        )
    except Exception:
        raise RuntimeError(
            "Futu native direct option order-book subscription failed"
        ) from None
    if (
        type(response) is not tuple
        or len(response) != 2
        or response[0] != sdk.RET_OK
    ):
        raise RuntimeError(
            "Futu native direct option order-book subscription failed"
        )


def retrieve_futu_native_direct_ask_evidence(
    quote_context: object,
    contract_verification: object,
    *,
    timeout_seconds: object,
) -> FutuNativeDirectAskEvidence:
    """Subscribe one exact option, then fetch one native ask.

    Missing or malformed ask-side data is retained as unavailable evidence so
    the Core can classify the case as data-insufficient.  A failed operation
    itself raises and is handled by the application as a blocked direct branch.
    """

    _validate_timeout(timeout_seconds)
    if type(contract_verification) is not _futu.FutuExactOptionContractVerification:
        raise TypeError(
            "contract_verification must be a FutuExactOptionContractVerification"
        )
    identifier = contract_verification.provider_identifier
    get_order_book = getattr(quote_context, "get_order_book", None)
    if not callable(get_order_book):
        raise TypeError("quote_context must provide get_order_book")
    _subscribe_exact_option_order_book(quote_context, identifier)
    try:
        response = get_order_book(identifier, num=1)
    except Exception:
        raise RuntimeError("Futu native direct option ask retrieval failed") from None
    if type(response) is not tuple or len(response) != 2:
        raise ValueError("Futu native order-book response is invalid")
    ret, data = response
    if ret != 0:
        raise RuntimeError("Futu native direct option ask retrieval failed")
    receipt = FutuNativeDirectAskReceipt(
        operation="get_order_book",
        provider_identifier=identifier,
        received_at=_datetime.datetime.now(_datetime.timezone.utc),
    )
    try:
        frame = _as_order_book_frame(data, identifier)
        ask, ask_size, reason, malformed = _futu._browser_side_from_frame(
            frame, "Ask"
        )
        if malformed:
            reason = _futu.FutuBrowserQuoteReasonCode.MALFORMED_FRAME
            ask = None
            ask_size = None
        elif reason is not None:
            ask = None
            ask_size = None
        elif ask_size is not None:
            # Reuse the provider's exact integer rule, including integer-valued
            # positive float sizes supplied by the SDK.
            ask_size = _futu._provider_integer(
                ask_size, "Futu native order-book response is invalid"
            )
        # Ask validation is authoritative.  Only a complete, valid bid is
        # used for the optional crossed-market diagnostic; a missing/invalid
        # bid never erases an otherwise valid indicative ask.
        if ask is not None and ask_size is not None:
            bid, _bid_size, bid_reason, bid_malformed = _futu._browser_side_from_frame(
                frame, "Bid"
            )
            if bid_malformed:
                reason = _futu.FutuBrowserQuoteReasonCode.MALFORMED_FRAME
                ask = None
                ask_size = None
            elif bid_reason is not None:
                reason = bid_reason
            elif bid is not None and bid > ask:
                reason = _futu.FutuBrowserQuoteReasonCode.CROSSED_MARKET
                ask = None
                ask_size = None
        return FutuNativeDirectAskEvidence(
            provider_identifier=identifier,
            ask_per_underlying_unit=ask,
            ask_size=ask_size,
            receipt=receipt,
            quote_authority=NativeQuoteAuthority.INDICATIVE_ONLY,
            reason_code=reason,
        )
    except (TypeError, ValueError):
        raise ValueError("Futu native order-book response is invalid") from None


def _core_leg_underlying_key(leg: object) -> _UnderlyingKey:
    from .core_research import CoreLeg

    if type(leg) is not CoreLeg:
        raise TypeError("leg must be a CoreLeg")
    return _UnderlyingKey(
        symbol=leg.underlying,
        listing_mic=None,
        security_type=_UnderlyingSecurityType.EQUITY,
        currency=leg.currency,
    )


def _verify_futu_core_leg(quote_context: object, leg: object):
    from .core_research import CoreOptionType

    underlying_key = _core_leg_underlying_key(leg)
    if type(leg.option_type) is not CoreOptionType:
        raise TypeError("leg option_type must be CoreOptionType")
    option_type = "call" if leg.option_type is CoreOptionType.CALL else "put"
    return _futu.verify_futu_monthly_option_contract(
        quote_context,
        underlying_key=underlying_key,
        expiration=leg.expiration,
        option_type=option_type,
        strike=leg.strike,
    )


def _close_owned_context(quote_context: object) -> None:
    close = getattr(quote_context, "close", None)
    if not callable(close):
        raise TypeError("quote_context must provide close")
    try:
        close()
    except Exception:
        raise RuntimeError("Futu quote context close failed") from None


@_dataclass(frozen=True)
class FutuMarketBridge:
    """Minimal default bridge over existing provider calls.

    A new context is requested for each operation.  The application calls
    ``quote_browser`` once per Browser and never retries an operation failure.
    """

    quote_context_factory: _Callable[[], object]

    def __post_init__(self) -> None:
        if not callable(self.quote_context_factory):
            raise TypeError("quote_context_factory must be callable")

    def discover_browser(self, discovery_request: OptionChainDiscoveryRequest):
        quote_context = self.quote_context_factory()
        try:
            return discover_futu_browser(quote_context, discovery_request)
        finally:
            _close_owned_context(quote_context)

    def verify_browser_row(
        self, discovery_request: OptionChainDiscoveryRequest, row: object
    ):
        quote_context = self.quote_context_factory()
        try:
            return verify_futu_browser_row(quote_context, discovery_request, row)
        finally:
            _close_owned_context(quote_context)

    def quote_browser(self, browser: object, *, timeout_seconds: object):
        return retrieve_futu_browser_quote_batch(
            self.quote_context_factory(), browser, timeout_seconds=timeout_seconds
        )

    def verify_exact_leg(self, leg: object):
        """Verify one CoreLeg without requiring legacy economic inputs."""

        quote_context = self.quote_context_factory()
        try:
            return _verify_futu_core_leg(quote_context, leg)
        finally:
            _close_owned_context(quote_context)

    def quote_direct(self, verification: object, *, timeout_seconds: object):
        """Retrieve one exact option ask; this bridge owns and closes context."""

        _validate_timeout(timeout_seconds)
        if type(verification) is not _futu.FutuExactOptionContractVerification:
            raise TypeError(
                "verification must be a FutuExactOptionContractVerification"
            )
        quote_context = self.quote_context_factory()
        try:
            return retrieve_futu_native_direct_ask_evidence(
                quote_context,
                verification,
                timeout_seconds=float(timeout_seconds),
            )
        finally:
            _close_owned_context(quote_context)
