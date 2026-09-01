"""Synthetic tests for the bounded Futu provider contract."""

import datetime
import decimal
import logging
import pathlib
import sys
import types
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
from convexity_hunter.market_data import (
    NormalizationQualityFlag,
    OptionContractReference,
    UnderlyingDailyBarObservation,
    UnderlyingKey,
    UnderlyingSecurityType,
)
from convexity_hunter.providers import futu


UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 8, 18, 16, 0, tzinfo=UTC)


class FakeTable:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, *, orient):
        if orient != "records":
            raise AssertionError
        return list(self.rows)


class ContractContext:
    def __init__(self, *, cycle="MONTH", standard="STANDARD"):
        self.identifier = "US.SPY260918C768000"
        self.expirations = [
            {"strike_time": "2026-09-18", "expiration_cycle": cycle}
        ]
        self.chain = [
            {
                "code": self.identifier,
                "lot_size": 100,
                "option_type": "CALL",
                "stock_owner": "US.SPY",
                "strike_time": "2026-09-18",
                "strike_price": 768.0,
                "suspension": False,
                "expiration_cycle": cycle,
                "option_standard_type": standard,
            }
        ]
        self.snapshot = [
            {
                "code": self.identifier,
                "stock_owner": "US.SPY",
                "option_type": "CALL",
                "strike_time": "2026-09-18",
                "option_strike_price": 768.0,
                "option_contract_size": 100,
                "option_area_type": "AMERICAN",
                "option_valid": True,
            }
        ]
        self.calls = []

    def get_option_expiration_date(self, code):
        self.calls.append(("expirations", code))
        return 0, FakeTable(self.expirations)

    def get_option_chain(self, code, **kwargs):
        self.calls.append(("chain", code, kwargs))
        return 0, FakeTable(self.chain)

    def get_market_snapshot(self, codes):
        self.calls.append(("snapshot", codes))
        return 0, FakeTable(self.snapshot)


def underlying():
    return UnderlyingKey(
        symbol="SPY",
        listing_mic="ARCX",
        security_type=UnderlyingSecurityType.ETF,
        currency="USD",
    )


def verification(context=None):
    return futu.verify_futu_monthly_option_contract(
        context or ContractContext(),
        underlying_key=underlying(),
        expiration=datetime.date(2026, 9, 18),
        option_type="call",
        strike=decimal.Decimal("768"),
    )


class PublicBoundaryTests(unittest.TestCase):
    def test_exact_thirty_name_api_and_no_reexports(self):
        self.assertEqual(
            futu.__all__,
            (
                "initialize_futu_quote_context",
                "FutuExactOptionContractVerification",
                "verify_futu_monthly_option_contract",
                "FutuOptionChainRowStatus",
                "FutuOptionChainExpirationEvidence",
                "FutuOptionChainContractEvidence",
                "FutuOptionChainDiscoveryEvidence",
                "retrieve_futu_option_chain_discovery_evidence",
                "FutuExactContractBrowser",
                "FutuExactContractSelection",
                "create_futu_exact_contract_browser",
                "select_futu_exact_contracts",
                "FutuExactContractSelectionVerification",
                "verify_futu_exact_contract_selection",
                "FutuBboEvidence",
                "FutuDirectEntryBboEvidence",
                "retrieve_futu_direct_entry_bbo_evidence",
                "retrieve_futu_underlying_daily_bars",
                "FutuHistoricalOptionBarEvidence",
                "retrieve_futu_historical_option_bar_evidence",
                "FutuExactOptionAnalyticsActivityEvidence",
                "retrieve_futu_exact_option_analytics_activity_evidence",
                "FutuBrowserQuoteAuthority",
                "FutuBrowserQuoteSemanticState",
                "FutuBrowserQuoteAvailability",
                "FutuBrowserQuoteReasonCode",
                "FutuBrowserQuoteEvidence",
                "FutuBrowserQuoteChunkEvidence",
                "FutuBrowserQuoteBatchEvidence",
                "retrieve_futu_browser_quote_batch_evidence",
            ),
        )
        self.assertEqual(
            tuple(name for name in vars(futu) if not name.startswith("_")),
            futu.__all__,
        )
        for name in futu.__all__:
            self.assertFalse(hasattr(convexity_hunter, name))
            self.assertFalse(hasattr(sys.modules["convexity_hunter.providers"], name))

    def test_import_does_not_import_sdk_or_read_credentials(self):
        self.assertNotIn("OpenQuoteContext", futu.__dict__)
        self.assertNotIn("futu", futu.__dict__)
        self.assertNotIn("futu_api_config", " ".join(vars(futu)))


class InitializationTests(unittest.TestCase):
    def test_initializes_only_lazy_sdk_context(self):
        sdk = types.SimpleNamespace(OpenQuoteContext=mock.Mock(return_value="ctx"))
        with mock.patch.object(futu, "_load_futu_sdk", return_value=sdk):
            self.assertEqual(futu.initialize_futu_quote_context(), "ctx")
        sdk.OpenQuoteContext.assert_called_once_with(host="127.0.0.1", port=11111)

    def test_rejects_invalid_endpoint_and_sanitizes_sdk_failure(self):
        for kwargs in ({"host": ""}, {"host": "x\x00y"}, {"port": True}, {"port": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises((TypeError, ValueError)):
                futu.initialize_futu_quote_context(**kwargs)
        secret = "synthetic-secret"
        sdk = types.SimpleNamespace(
            OpenQuoteContext=mock.Mock(side_effect=RuntimeError(secret))
        )
        with mock.patch.object(futu, "_load_futu_sdk", return_value=sdk):
            with self.assertRaisesRegex(RuntimeError, "initialization failed") as raised:
                futu.initialize_futu_quote_context()
        self.assertNotIn(secret, str(raised.exception))

    def test_sdk_loader_sanitizes_import_failure(self):
        with mock.patch.object(
            futu._importlib, "import_module", side_effect=ImportError("secret")
        ):
            with self.assertRaisesRegex(RuntimeError, "SDK is unavailable") as raised:
                futu._load_futu_sdk()
        self.assertNotIn("secret", str(raised.exception))


class ExactContractTests(unittest.TestCase):
    def test_exact_monthly_standard_contract_remains_incomplete(self):
        context = ContractContext()
        result = verification(context)
        self.assertEqual(result.provider_identifier, context.identifier)
        self.assertEqual(result.provider_expiration_cycle, "MONTH")
        self.assertEqual(result.provider_standard_type, "STANDARD")
        self.assertEqual(result.provider_exercise_type, "AMERICAN")
        self.assertIsInstance(result.contract_reference, OptionContractReference)
        key = result.contract_reference.contract_key
        self.assertEqual(key.contract_multiplier, 100)
        self.assertIsNone(key.deliverable_id)
        self.assertIsNone(result.contract_reference.settlement_type)
        self.assertIn(
            NormalizationQualityFlag.INCOMPLETE,
            result.contract_reference.metadata.quality_flags,
        )
        self.assertEqual(
            context.calls[1][2],
            {
                "start": "2026-09-18",
                "end": "2026-09-18",
                "option_type": "CALL",
            },
        )

    def test_weekly_or_nonstandard_contract_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "monthly"):
            verification(ContractContext(cycle="WEEK"))
        with self.assertRaisesRegex(ValueError, "standard"):
            verification(ContractContext(standard="NON_STANDARD"))

    def test_duplicate_and_identity_mismatch_fail_closed(self):
        context = ContractContext()
        context.chain.append(dict(context.chain[0]))
        with self.assertRaisesRegex(ValueError, "exact contract"):
            verification(context)
        context = ContractContext()
        context.chain[0]["code"] = "US.SPY260918C769000"
        with self.assertRaisesRegex(ValueError, "identifier"):
            verification(context)

    def test_snapshot_and_provider_failures_are_sanitized(self):
        context = ContractContext()
        context.snapshot[0]["option_contract_size"] = 50
        with self.assertRaisesRegex(ValueError, "snapshot response"):
            verification(context)

        class BadContext(ContractContext):
            def get_option_chain(self, *args, **kwargs):
                raise RuntimeError("private material")

        with self.assertRaisesRegex(RuntimeError, "chain retrieval failed") as raised:
            verification(BadContext())
        self.assertNotIn("private material", str(raised.exception))


class FakeS2C:
    def __init__(self, bid_timestamp=None, ask_timestamp=None):
        self.svrRecvTimeBidTimestamp = bid_timestamp or 0.0
        self.svrRecvTimeAskTimestamp = ask_timestamp or 0.0
        self._present = {
            "svrRecvTimeBidTimestamp": bid_timestamp is not None,
            "svrRecvTimeAskTimestamp": ask_timestamp is not None,
        }

    def HasField(self, name):
        return self._present.get(name, False)


class FakeRsp:
    def __init__(self, data, bid_timestamp=None, ask_timestamp=None, ret=0):
        self.data = data
        self.ret = ret
        self.s2c = FakeS2C(bid_timestamp, ask_timestamp)

    def HasField(self, name):
        return name == "s2c"


class FakeHandlerBase:
    def __init__(self):
        self.calls = 0

    def on_recv_rsp(self, rsp_pb):
        self.calls += 1
        return rsp_pb.ret, rsp_pb.data


FAKE_SDK = types.SimpleNamespace(
    RET_OK=0,
    OrderBookHandlerBase=FakeHandlerBase,
    SubType=types.SimpleNamespace(ORDER_BOOK="ORDER_BOOK"),
    KLType=types.SimpleNamespace(K_DAY="K_DAY"),
    AuType=types.SimpleNamespace(NONE="NONE"),
)


class BboContext:
    def __init__(
        self,
        option_identifier="US.SPY260918C768000",
        *,
        include_populated_timestamp_values=True,
    ):
        self.option_identifier = option_identifier
        self.include_populated_timestamp_values = include_populated_timestamp_values
        self.handler = None
        self.previous_handler = FakeHandlerBase()
        self._handler_ctx = types.SimpleNamespace(
            _handler_table={
                3013: {"type": FakeHandlerBase, "obj": self.previous_handler}
            }
        )
        self._sub_record = types.SimpleNamespace(get_sub_list=lambda: [])
        self.unsubscribed = False
        self.unsubscribe_calls = []
        self.subscription_result = 0
        self.subscribe_calls = []
        self.unsubscribe_result = 0
        self.close_failure = False
        self.closed = False
        self.state_failure = False

    def get_market_state(self, codes):
        if self.state_failure:
            raise RuntimeError("synthetic state failure")
        return 0, FakeTable(
            [{"code": code, "market_state": "AFTERNOON"} for code in codes]
        )

    def set_handler(self, handler):
        self.handler = handler
        self._handler_ctx._handler_table[3013]["obj"] = handler
        return 0

    def subscribe(self, codes, subtypes, **kwargs):
        self.subscribe_calls.append(tuple(codes))
        if self.subscription_result:
            return self.subscription_result, ""
        timestamp = NOW.timestamp() - 1
        for code in codes:
            self.handler.on_recv_rsp(
                FakeRsp(
                    {"code": code, "Bid": [(1.0, 2)], "Ask": [(1.1, 3)]}
                )
            )
            if self.include_populated_timestamp_values:
                self.handler.on_recv_rsp(
                    FakeRsp(
                        {"code": code, "Bid": [(1.0, 2)], "Ask": [(1.1, 3)]},
                        timestamp,
                        timestamp,
                    )
                )
        return 0, ""

    def unsubscribe(self, codes, subtypes):
        self.unsubscribed = True
        self.unsubscribe_calls.append(tuple(codes))
        return self.unsubscribe_result, ""

    def close(self):
        self.closed = True
        if self.close_failure:
            raise RuntimeError("synthetic close failure")


class BboTests(unittest.TestCase):
    def test_atomic_bbo_retains_opaque_provider_values_without_normalization(self):
        context = BboContext()
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), mock.patch.object(
            futu, "_utc_now", return_value=NOW
        ):
            result = futu.retrieve_futu_direct_entry_bbo_evidence(
                context, verification(), timeout_seconds=1
            )
        self.assertEqual(result.underlying_bbo.provider_identifier, "US.SPY")
        self.assertEqual(result.option_bbo.provider_identifier, context.option_identifier)
        self.assertEqual(
            result.option_bbo.provider_bid_timestamp_value,
            decimal.Decimal(str(NOW.timestamp() - 1)),
        )
        self.assertEqual(result.option_bbo.ask_size, 3)
        self.assertTrue(context.closed)
        self.assertEqual(
            context.subscribe_calls,
            [("US.SPY",), (context.option_identifier,)],
        )
        self.assertEqual(context.previous_handler.calls, 4)
        self.assertNotIn("quote_scope", result.__dataclass_fields__)

    def test_absent_unsupported_timestamp_values_do_not_block_bbo(self):
        context = BboContext(include_populated_timestamp_values=False)
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), mock.patch.object(
            futu, "_utc_now", return_value=NOW
        ):
            result = futu.retrieve_futu_direct_entry_bbo_evidence(
                context, verification(), timeout_seconds=1
            )
        self.assertIsNone(result.underlying_bbo.provider_bid_timestamp_value)
        self.assertIsNone(result.underlying_bbo.provider_ask_timestamp_value)
        self.assertEqual(result.option_bbo.received_at, NOW)

    def test_crossed_invalid_size_or_nonfinite_opaque_value_fails_closed(self):
        for kwargs in (
            {"bid_price": decimal.Decimal("2"), "ask_price": decimal.Decimal("1")},
            {"bid_size": 0},
            {"provider_bid_timestamp_value": decimal.Decimal("NaN")},
        ):
            values = dict(
                provider_identifier="US.SPY",
                bid_price=decimal.Decimal("1"),
                ask_price=decimal.Decimal("1.1"),
                bid_size=1,
                ask_size=1,
                received_at=NOW,
            )
            values.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                futu.FutuBboEvidence(**values)

        opaque = futu.FutuBboEvidence(
            provider_identifier="US.SPY",
            bid_price=decimal.Decimal("1"),
            ask_price=decimal.Decimal("1.1"),
            bid_size=1,
            ask_size=1,
            received_at=NOW,
            provider_bid_timestamp_value=decimal.Decimal("999999999999999"),
            provider_ask_timestamp_value=decimal.Decimal("-7"),
        )
        self.assertEqual(
            opaque.provider_bid_timestamp_value,
            decimal.Decimal("999999999999999"),
        )

    def test_subscription_and_close_failures_are_sanitized(self):
        context = BboContext()
        context.subscription_result = -1
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), mock.patch.object(
            futu, "_utc_now", return_value=NOW
        ):
            with self.assertRaisesRegex(RuntimeError, "BBO retrieval failed"):
                futu.retrieve_futu_direct_entry_bbo_evidence(
                    context, verification(), timeout_seconds=0.01
                )
        self.assertIs(
            context.closed,
            True,
        )
        context = BboContext()
        context.close_failure = True
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), mock.patch.object(
            futu, "_utc_now", return_value=NOW
        ):
            with self.assertRaisesRegex(RuntimeError, "BBO retrieval failed"):
                futu.retrieve_futu_direct_entry_bbo_evidence(
                    context, verification(), timeout_seconds=0.01
                )

    def test_shared_or_custom_handler_context_rejects_before_mutation(self):
        exact = verification()
        context = BboContext()
        context._sub_record = types.SimpleNamespace(
            get_sub_list=lambda: [(["US.OTHER"], ["ORDER_BOOK"], False, False, None)]
        )
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK):
            with self.assertRaisesRegex(ValueError, "dedicated unsubscribed"):
                futu.retrieve_futu_direct_entry_bbo_evidence(context, exact)
        self.assertFalse(context.closed)

    def test_initial_market_state_failure_still_closes_dedicated_context(self):
        context = BboContext()
        context.state_failure = True
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK):
            with self.assertRaisesRegex(RuntimeError, "BBO retrieval failed"):
                futu.retrieve_futu_direct_entry_bbo_evidence(
                    context, verification(), timeout_seconds=0.01
                )
        self.assertTrue(context.closed)

    def test_direct_entry_evidence_rejects_malformed_state_without_index_leak(self):
        exact = verification()
        bbo = futu.FutuBboEvidence(
            provider_identifier="US.SPY",
            bid_price=decimal.Decimal("1"),
            ask_price=decimal.Decimal("1.1"),
            bid_size=1,
            ask_size=1,
            received_at=NOW,
        )
        option_bbo = futu.FutuBboEvidence(
            provider_identifier=exact.provider_identifier,
            bid_price=decimal.Decimal("1"),
            ask_price=decimal.Decimal("1.1"),
            bid_size=1,
            ask_size=1,
            received_at=NOW,
        )
        with self.assertRaisesRegex(ValueError, "BBO response"):
            futu.FutuDirectEntryBboEvidence(
                underlying_key=underlying(),
                contract_verification=exact,
                underlying_bbo=bbo,
                option_bbo=option_bbo,
                market_state_before=((), ("US.SPY", "AFTERNOON")),
                market_state_after=(
                    ("US.SPY", "AFTERNOON"),
                    (exact.provider_identifier, "AFTERNOON"),
                ),
                state_before_received_at=NOW,
                state_after_received_at=NOW,
            )
class HistoryContext:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def request_history_kline(self, identifier, **kwargs):
        self.calls.append((identifier, kwargs))
        return 0, FakeTable(self.rows), None


def history_row(code, day="2026-08-17", **changes):
    row = {
        "code": code,
        "time_key": day + " 00:00:00",
        "open": 640.0,
        "high": 645.0,
        "low": 639.0,
        "close": 644.0,
        "volume": 1000,
        "turnover": 12345.0,
    }
    row.update(changes)
    return row


class HistoryTests(unittest.TestCase):
    def test_underlying_bars_preserve_exclusive_end_and_unadjusted_semantics(self):
        context = HistoryContext([history_row("US.SPY")])
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), mock.patch.object(
            futu, "_utc_now", return_value=NOW
        ):
            result = futu.retrieve_futu_underlying_daily_bars(
                context,
                underlying_key=underlying(),
                begin_date=datetime.date(2026, 8, 17),
                end_date=datetime.date(2026, 8, 18),
                latest_completed_session_date=datetime.date(2026, 8, 17),
            )
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], UnderlyingDailyBarObservation)
        self.assertIsNone(result[0].adjusted_close_price)
        self.assertTrue(result[0].is_session_complete)
        self.assertEqual(context.calls[0][1]["end"], "2026-08-17")
        self.assertEqual(context.calls[0][1]["autype"], "NONE")
        self.assertEqual(result[0].metadata.effective_observed_at.hour, 4)

    def test_underlying_rejects_empty_duplicate_current_and_malformed_rows(self):
        cases = (
            [],
            [history_row("US.SPY"), history_row("US.SPY")],
            [history_row("US.SPY", low=646.0)],
            [history_row("US.WRONG")],
        )
        for rows in cases:
            with self.subTest(rows=rows), mock.patch.object(
                futu, "_load_futu_sdk", return_value=FAKE_SDK
            ), mock.patch.object(futu, "_utc_now", return_value=NOW):
                with self.assertRaisesRegex(ValueError, "daily-bar response"):
                    futu.retrieve_futu_underlying_daily_bars(
                        HistoryContext(rows),
                        underlying_key=underlying(),
                        begin_date=datetime.date(2026, 8, 17),
                        end_date=datetime.date(2026, 8, 18),
                        latest_completed_session_date=datetime.date(2026, 8, 17),
                    )
        with self.assertRaisesRegex(ValueError, "incomplete session"):
            futu.retrieve_futu_underlying_daily_bars(
                HistoryContext([history_row("US.SPY", day="2026-08-18")]),
                underlying_key=underlying(),
                begin_date=datetime.date(2026, 8, 17),
                end_date=datetime.date(2026, 8, 19),
                latest_completed_session_date=datetime.date(2026, 8, 17),
            )

    def test_dst_offsets_are_deterministic(self):
        for day, expected_hour in (("2026-01-05", 5), ("2026-07-06", 4)):
            with self.subTest(day=day), mock.patch.object(
                futu, "_load_futu_sdk", return_value=FAKE_SDK
            ), mock.patch.object(
                futu,
                "_utc_now",
                return_value=datetime.datetime(2026, 8, 18, tzinfo=UTC),
            ):
                value = futu.retrieve_futu_underlying_daily_bars(
                    HistoryContext([history_row("US.SPY", day=day)]),
                    underlying_key=underlying(),
                    begin_date=datetime.date.fromisoformat(day),
                    end_date=datetime.date.fromisoformat(day)
                    + datetime.timedelta(days=1),
                    latest_completed_session_date=datetime.date.fromisoformat(day),
                )[0]
            self.assertEqual(value.metadata.effective_observed_at.hour, expected_hour)

    def test_option_history_is_provider_native_and_empty_is_allowed(self):
        exact = verification()
        context = HistoryContext(
            [history_row(exact.provider_identifier, open=1, high=2, low=0.5, close=1.5)]
        )
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), mock.patch.object(
            futu, "_utc_now", return_value=NOW
        ):
            result = futu.retrieve_futu_historical_option_bar_evidence(
                context,
                exact,
                begin_date=datetime.date(2026, 8, 17),
                end_date=datetime.date(2026, 8, 18),
                latest_completed_session_date=datetime.date(2026, 8, 17),
            )
            empty = futu.retrieve_futu_historical_option_bar_evidence(
                HistoryContext([]),
                exact,
                begin_date=datetime.date(2026, 8, 17),
                end_date=datetime.date(2026, 8, 18),
                latest_completed_session_date=datetime.date(2026, 8, 17),
            )
        self.assertEqual(result[0].turnover, decimal.Decimal("12345.0"))
        self.assertNotIn("open_interest", result[0].__dataclass_fields__)
        self.assertEqual(empty, ())

    def test_history_provider_error_is_sanitized(self):
        class Bad:
            def request_history_kline(self, *args, **kwargs):
                raise RuntimeError("private")

        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK):
            with self.assertRaisesRegex(RuntimeError, "daily-bar retrieval failed") as raised:
                futu.retrieve_futu_underlying_daily_bars(
                    Bad(),
                    underlying_key=underlying(),
                    begin_date=datetime.date(2026, 8, 17),
                    end_date=datetime.date(2026, 8, 18),
                    latest_completed_session_date=datetime.date(2026, 8, 17),
                )
        self.assertNotIn("private", str(raised.exception))


class AnalyticsTests(unittest.TestCase):
    def row(self, **changes):
        row = {
            "code": "US.SPY260918C768000",
            "volume": 10,
            "option_open_interest": 20,
            "option_implied_volatility": 18.5,
            "option_delta": 0.4,
            "option_gamma": 0.01,
            "option_theta": -0.2,
            "option_vega": 0.3,
            "option_rho": 0.1,
            "update_time": "2026-08-18 11:59:00",
        }
        row.update(changes)
        return row

    def test_snapshot_analytics_remain_provider_native(self):
        context = ContractContext()
        context.snapshot = [self.row()]
        with mock.patch.object(futu, "_utc_now", return_value=NOW):
            result = futu.retrieve_futu_exact_option_analytics_activity_evidence(
                context, verification()
            )
        self.assertEqual(result.volume, 10)
        self.assertEqual(result.open_interest, 20)
        self.assertEqual(result.implied_volatility, decimal.Decimal("18.5"))
        self.assertEqual(result.last_trade_at.hour, 15)
        self.assertNotIn("metadata", result.__dataclass_fields__)

    def test_missing_or_invalid_analytics_fail_closed(self):
        for changes in (
            {"option_delta": 2},
            {"option_gamma": -1},
            {"option_implied_volatility": "N/A"},
            {"option_open_interest": -1},
            {"update_time": "not-a-time"},
        ):
            context = ContractContext()
            context.snapshot = [self.row(**changes)]
            with self.subTest(changes=changes), mock.patch.object(
                futu, "_utc_now", return_value=NOW
            ), self.assertRaisesRegex(ValueError, "analytics/activity response"):
                futu.retrieve_futu_exact_option_analytics_activity_evidence(
                    context, verification()
                )


if __name__ == "__main__":
    unittest.main()
