"""Deterministic tests for probability-free Browser discrimination."""

import datetime
import decimal
import inspect
import pathlib
import sys
import threading
import types
import unittest
from dataclasses import fields, replace
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
from convexity_hunter import candidate_assembly
from convexity_hunter import convexity_discrimination as discrimination
from convexity_hunter.discovery_entry import create_discovery_entry_handoff
from convexity_hunter.event_intelligence import (
    DistributionChangeMode,
    EventIntelligenceSubmission,
    EventSourceReference,
    EventStatement,
    EventStatementKind,
    EventUnderlyingHypothesis,
    HypothesisReassessment,
    MethodologizedDateRange,
    ReassessmentBasisKind,
    assess_event_intelligence_submission,
)
from convexity_hunter.market_data import (
    DataOrigin,
    NormalizationMetadata,
    NormalizationQualityFlag,
    SourceReference,
    UnderlyingDailyBarObservation,
    UnderlyingKey,
    UnderlyingSecurityType,
)
from convexity_hunter.market_data_transformations import ExactRational
from convexity_hunter.option_chain_discovery import (
    HypothesisMaturityAlignment,
    OptionMaturityAuthority,
    create_option_chain_discovery_request,
)
from convexity_hunter.providers import futu


UTC = datetime.timezone.utc
EVALUATION_DATE = datetime.date(2030, 1, 1)
NOW = datetime.datetime(2030, 1, 1, 16, 0, tzinfo=UTC)


def make_request(mode, *, symbol="NDAQ"):
    source = EventSourceReference(
        "source-1",
        "https://www.sec.gov/example",
        "Issuer filing",
        datetime.datetime(2029, 12, 31, tzinfo=UTC),
    )
    fact = EventStatement(
        "fact-1",
        EventStatementKind.OBSERVED_FACT,
        "The filing declares a structural change.",
        (source.source_id,),
    )
    interpretation = EventStatement(
        "interpretation-1",
        EventStatementKind.INTERPRETATION,
        "The change may alter the outcome distribution.",
        (),
        (fact.statement_id,),
    )
    reassessment_date = datetime.date(2030, 1, 10)
    reassessment = HypothesisReassessment(
        reassessment_date,
        "caller-research-policy-assumption:"
        f"{reassessment_date.isoformat()}:Review the evidence before continued research.",
        ReassessmentBasisKind.CALLER_RESEARCH_POLICY_ASSUMPTION,
        (interpretation.statement_id,),
    )
    event_range = MethodologizedDateRange(
        EVALUATION_DATE, EVALUATION_DATE, "Observed publication date."
    )
    underlying = UnderlyingKey(
        symbol, "XNAS", UnderlyingSecurityType.EQUITY, "USD"
    )
    hypothesis = EventUnderlyingHypothesis(
        "hypothesis-1",
        underlying,
        "A structural narrative may alter possible outcomes.",
        mode,
        "The future return distribution may change.",
        None,
        reassessment,
        (interpretation.statement_id,),
        (),
        "Contradictory evidence was reviewed; none was identified.",
        ("The structural interpretation may be wrong.",),
        ("The disclosed change is reversed.",),
    )
    submission = EventIntelligenceSubmission(
        "submission-1",
        "event-1",
        "test-producer",
        "1.0",
        NOW,
        "A structural change was disclosed.",
        event_range,
        (source,),
        (fact, interpretation),
        (hypothesis,),
    )
    acceptance = assess_event_intelligence_submission(submission)
    handoff = create_discovery_entry_handoff(acceptance, hypothesis)
    return create_option_chain_discovery_request(
        handoff,
        evaluation_date=EVALUATION_DATE,
        maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
    )


def option_identifier(symbol, expiration, option_type, strike):
    marker = "C" if option_type == "call" else "P"
    encoded = int(decimal.Decimal(str(strike)) * 1000)
    return f"US.{symbol}{expiration:%y%m%d}{marker}{encoded}"


def make_browser(
    mode=DistributionChangeMode.BIDIRECTIONAL_EXPANSION,
    *,
    symbol="NDAQ",
    expirations=(datetime.date(2030, 3, 15),),
    strikes=(decimal.Decimal("100"),),
    option_types=("call", "put"),
):
    request = make_request(mode, symbol=symbol)
    expiration_retrieved = NOW
    expiration_rows = []
    contracts = []
    for offset, expiration in enumerate(expirations, start=1):
        chain_time = NOW + datetime.timedelta(minutes=offset)
        expiration_rows.append(futu.FutuOptionChainExpirationEvidence(
            expiration, "MONTH", expiration_retrieved, chain_time
        ))
        for strike in strikes:
            for option_type in option_types:
                contracts.append(futu.FutuOptionChainContractEvidence(
                    option_identifier(symbol, expiration, option_type, strike),
                    "US." + symbol,
                    expiration,
                    option_type,
                    strike,
                    100,
                    "MONTH",
                    "STANDARD",
                    False,
                    (futu.FutuOptionChainRowStatus.ELIGIBLE,),
                    chain_time,
                ))
    evidence = futu.FutuOptionChainDiscoveryEvidence(
        request,
        "US." + symbol,
        tuple(expiration_rows),
        tuple(contracts),
    )
    return futu.create_futu_exact_contract_browser(evidence)


def quote_for(row, chunk_index, *, bid="1", ask="2", bid_size=10, ask_size=20):
    if bid is None:
        return futu.FutuBrowserQuoteEvidence(
            row,
            chunk_index,
            futu.FutuBrowserQuoteAvailability.ASK_SIDE_AVAILABLE,
            None,
            decimal.Decimal(ask),
            None,
            ask_size,
            NOW,
            None,
            None,
            (futu.FutuBrowserQuoteReasonCode.BID_ABSENT,),
        )
    return futu.FutuBrowserQuoteEvidence(
        row,
        chunk_index,
        futu.FutuBrowserQuoteAvailability.TWO_SIDED_AVAILABLE,
        decimal.Decimal(bid),
        decimal.Decimal(ask),
        bid_size,
        ask_size,
        NOW,
        None,
        None,
        (),
    )


def make_quote_batch(browser, quote_factory=quote_for):
    chunks = []
    expiration_order = tuple(dict.fromkeys(row.expiration for row in browser.rows))
    for chunk_index, expiration in enumerate(expiration_order):
        rows = tuple(row for row in browser.rows if row.expiration == expiration)
        quotes = tuple(quote_factory(row, chunk_index) for row in rows)
        chunks.append(futu.FutuBrowserQuoteChunkEvidence(
            chunk_index, expiration, rows, quotes, NOW, NOW
        ))
    return futu.FutuBrowserQuoteBatchEvidence(browser, tuple(chunks))


def make_bar(browser, session_date, close="100", *, complete=True, record_suffix="1"):
    observed = datetime.datetime.combine(
        session_date, datetime.time(21, 0), tzinfo=UTC
    )
    retrieved = observed + datetime.timedelta(minutes=1)
    source = SourceReference(
        "source-" + record_suffix,
        "Futu OpenAPI",
        "historical_kline_unadjusted_daily",
        "US." + browser.discovery_evidence.discovery_request.underlying_key.symbol
        + ":" + session_date.isoformat(),
        None,
        "US." + browser.discovery_evidence.discovery_request.underlying_key.symbol,
        None,
        observed,
        retrieved,
        "America/New_York",
        "Synthetic completed session close.",
        DataOrigin.EXCHANGE_OBSERVED,
        False,
        None,
        None,
        None,
        None,
        (),
    )
    metadata = NormalizationMetadata(
        "bar-" + record_suffix,
        (source,),
        observed,
        retrieved,
        DataOrigin.EXCHANGE_OBSERVED,
        "Exact synthetic Futu daily bar.",
        "USD per share.",
        "futu-underlying-daily-bar-v0.1",
        (NormalizationQualityFlag.SYMBOL_MAPPED,),
    )
    value = decimal.Decimal(close)
    return UnderlyingDailyBarObservation(
        browser.discovery_evidence.discovery_request.underlying_key,
        session_date,
        value,
        value,
        value,
        value,
        None,
        1000,
        complete,
        None,
        metadata,
    )


class FakeS2C:
    def __init__(self):
        self.svrRecvTimeBidTimestamp = 0
        self.svrRecvTimeAskTimestamp = 0

    def HasField(self, name):
        return False


class FakeRsp:
    def __init__(self, data, ret=0):
        self.data = data
        self.ret = ret
        self.s2c = FakeS2C()

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
)


class BrowserQuoteContext:
    def __init__(self, frames=None, *, subscription_failures=(), extra=None):
        self.frames = frames or {}
        self.subscription_failures = set(subscription_failures)
        self.extra = extra
        self.previous_handler = FakeHandlerBase()
        self._handler_ctx = types.SimpleNamespace(
            _handler_table={3013: {"type": FakeHandlerBase, "obj": self.previous_handler}}
        )
        self._sub_record = types.SimpleNamespace(get_sub_list=lambda: [])
        self.handler = None
        self.subscribe_calls = []
        self.closed = False

    def set_handler(self, handler):
        self.handler = handler
        self._handler_ctx._handler_table[3013]["obj"] = handler
        return 0

    def subscribe(self, codes, subtypes, **kwargs):
        index = len(self.subscribe_calls)
        self.subscribe_calls.append((tuple(codes), tuple(subtypes), kwargs))
        if index in self.subscription_failures:
            return 1, "synthetic private failure"
        for code in codes:
            frame = self.frames.get(code)
            if frame is not None:
                self.handler.on_recv_rsp(FakeRsp(frame))
                self.handler.on_recv_rsp(FakeRsp(frame))
        if self.extra is not None:
            self.handler.on_recv_rsp(FakeRsp(self.extra))
        return 0, ""

    def close(self):
        self.closed = True


class PublicContractTests(unittest.TestCase):
    def test_exact_direct_api_counts_fields_and_no_root_exports(self):
        self.assertEqual(len(futu.__all__), 30)
        self.assertEqual(len(discrimination.__all__), 19)
        self.assertEqual(
            discrimination.__all__,
            (
                "ComparisonPayoffGrammar",
                "ComparisonCoverageReasonCode",
                "IndicativeMetricStatus",
                "IndicativeMetricUnavailableReason",
                "PayoffGeometryAuthority",
                "ExactDeliverableVerification",
                "ReferencePriceBasis",
                "TemporalAlignmentState",
                "PayoffBranch",
                "ComparisonStructure",
                "NonComparisonBrowserRow",
                "DiscriminationReferencePrice",
                "IndicativePremiumToReferenceRatio",
                "ConditionalPayoffMultipleHurdle",
                "ConvexityResponsePoint",
                "IndicativeRelativeSpread",
                "ComparisonStructureDiscrimination",
                "ProbabilityFreeConvexityDiscriminationResult",
                "discriminate_probability_free_convexity",
            ),
        )
        for name in discrimination.__all__:
            self.assertFalse(hasattr(convexity_hunter, name))
        self.assertEqual(
            tuple(field.name for field in fields(discrimination.ComparisonStructure)),
            ("grammar", "rows"),
        )
        forbidden = {"rank", "score", "selected", "recommendation", "candidate"}
        for item in (
            discrimination.ComparisonStructure,
            discrimination.ComparisonStructureDiscrimination,
            discrimination.ProbabilityFreeConvexityDiscriminationResult,
        ):
            self.assertFalse(forbidden & set(item.__dataclass_fields__))
        self.assertEqual(
            tuple(inspect.signature(discrimination.discriminate_probability_free_convexity).parameters),
            ("browser", "quote_batch", "underlying_daily_bars", "latest_completed_session_date"),
        )

    def test_frozen_enum_order_and_authority_properties(self):
        self.assertEqual(
            tuple(item.name for item in futu.FutuBrowserQuoteAvailability),
            ("ASK_SIDE_AVAILABLE", "TWO_SIDED_AVAILABLE", "UNAVAILABLE"),
        )
        browser = make_browser()
        batch = make_quote_batch(browser)
        self.assertEqual(batch.schema_version, "futu-browser-provider-native-quote-batch-v0.1")
        self.assertIs(batch.authority, futu.FutuBrowserQuoteAuthority.INDICATIVE_ONLY)
        self.assertIs(batch.event_time, futu.FutuBrowserQuoteSemanticState.UNAVAILABLE)
        self.assertIs(batch.freshness, futu.FutuBrowserQuoteSemanticState.NOT_ESTABLISHED)
        self.assertIs(batch.quote_scope, futu.FutuBrowserQuoteSemanticState.UNASSIGNED)
        self.assertIs(batch.executable_price_claim, futu.FutuBrowserQuoteSemanticState.NONE)


class ProviderQuoteBatchTests(unittest.TestCase):
    def test_callbacks_are_serialized_before_provider_parsing(self):
        browser = make_browser(option_types=("call",))
        row = browser.rows[0]
        entered = threading.Event()
        release = threading.Event()

        class BlockingHandlerBase:
            def on_recv_rsp(self, rsp_pb):
                if rsp_pb.data["Bid"][0][0] == 1:
                    entered.set()
                    release.wait(1)
                return rsp_pb.ret, rsp_pb.data

        sdk = types.SimpleNamespace(
            RET_OK=0,
            OrderBookHandlerBase=BlockingHandlerBase,
            SubType=types.SimpleNamespace(ORDER_BOOK="ORDER_BOOK"),
        )

        class ConcurrentContext:
            def __init__(self):
                previous = BlockingHandlerBase()
                self._handler_ctx = types.SimpleNamespace(
                    _handler_table={3013: {"type": BlockingHandlerBase, "obj": previous}}
                )
                self._sub_record = types.SimpleNamespace(get_sub_list=lambda: [])
                self.handler = None
                self.closed = False

            def set_handler(self, handler):
                self.handler = handler
                return 0

            def subscribe(self, codes, subtypes, **kwargs):
                first = FakeRsp({
                    "code": row.provider_identifier,
                    "Bid": [(1, 10)],
                    "Ask": [(2, 10)],
                })
                second = FakeRsp({
                    "code": row.provider_identifier,
                    "Bid": [(3, 10)],
                    "Ask": [(4, 10)],
                })
                first_thread = threading.Thread(
                    target=self.handler.on_recv_rsp, args=(first,)
                )
                second_thread = threading.Thread(
                    target=self.handler.on_recv_rsp, args=(second,)
                )
                first_thread.start()
                self.assert_entered = entered.wait(1)
                second_thread.start()
                release.set()
                first_thread.join(1)
                second_thread.join(1)
                return 0, ""

            def close(self):
                self.closed = True

        context = ConcurrentContext()
        with mock.patch.object(futu, "_load_futu_sdk", return_value=sdk), \
                mock.patch.object(futu, "_utc_now", return_value=NOW):
            batch = futu.retrieve_futu_browser_quote_batch_evidence(
                context, browser, timeout_seconds=0.01
            )
        self.assertTrue(context.assert_entered)
        self.assertEqual(batch.quotes[0].bid_price, decimal.Decimal("1"))
        self.assertEqual(batch.quotes[0].ask_price, decimal.Decimal("2"))

    def test_malformed_envelope_close_precedence_and_provider_redaction(self):
        browser = make_browser(option_types=("call",))

        class MissingEnvelopeContext(BrowserQuoteContext):
            def subscribe(self, codes, subtypes, **kwargs):
                frame = {
                    "code": codes[0], "Bid": [(1, 1)], "Ask": [(2, 1)]
                }
                response = FakeRsp(frame)
                response.HasField = lambda name: False
                self.handler.on_recv_rsp(response)
                return 0, ""

        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), \
                mock.patch.object(futu, "_utc_now", return_value=NOW):
            with self.assertRaisesRegex(ValueError, "response is invalid"):
                futu.retrieve_futu_browser_quote_batch_evidence(
                    MissingEnvelopeContext(), browser, timeout_seconds=0.001
                )

        class FailingCloseContext(BrowserQuoteContext):
            def close(self):
                self.handler.on_recv_rsp(FakeRsp({
                    "code": "US.UNEXPECTED", "Bid": [(1, 1)], "Ask": [(2, 1)]
                }))
                raise RuntimeError("provider-close-secret")

        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), \
                mock.patch.object(futu, "_utc_now", return_value=NOW):
            with self.assertRaisesRegex(
                RuntimeError, "Futu Browser quote-batch retrieval failed"
            ) as caught:
                futu.retrieve_futu_browser_quote_batch_evidence(
                    FailingCloseContext(), browser, timeout_seconds=0.001
                )
        self.assertNotIn("secret", str(caught.exception))

        context = BrowserQuoteContext()
        context.set_handler = mock.Mock(side_effect=RuntimeError("provider-secret"))
        context.close = mock.Mock(side_effect=RuntimeError("close-secret"))
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK):
            with self.assertRaisesRegex(
                RuntimeError, "Futu Browser quote-batch retrieval failed"
            ) as caught:
                futu.retrieve_futu_browser_quote_batch_evidence(context, browser)
        self.assertNotIn("secret", str(caught.exception))
        context.close.assert_called_once_with()

    def test_synchronous_frames_chunk_by_expiration_and_preserve_every_row(self):
        browser = make_browser(
            expirations=(datetime.date(2030, 3, 15), datetime.date(2030, 4, 19)),
            strikes=(decimal.Decimal("90"), decimal.Decimal("100")),
        )
        frames = {
            row.provider_identifier: {
                "code": row.provider_identifier,
                "Bid": [(1, 10)],
                "Ask": [(2, 20)],
            }
            for row in browser.rows
        }
        context = BrowserQuoteContext(frames)
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), mock.patch.object(futu, "_utc_now", return_value=NOW):
            batch = futu.retrieve_futu_browser_quote_batch_evidence(
                context, browser, timeout_seconds=0.01
            )
        self.assertTrue(context.closed)
        self.assertEqual(len(context.subscribe_calls), 2)
        self.assertEqual(len(batch.quotes), len(browser.rows))
        self.assertTrue(all(
            quote.browser_row is row
            for quote, row in zip(batch.quotes, browser.rows)
        ))
        self.assertTrue(all(
            quote.availability is futu.FutuBrowserQuoteAvailability.TWO_SIDED_AVAILABLE
            for quote in batch.quotes
        ))

    def test_missing_frame_and_subscription_failure_keep_rows(self):
        browser = make_browser(
            expirations=(datetime.date(2030, 3, 15), datetime.date(2030, 4, 19)),
        )
        first = browser.rows[0]
        frames = {
            first.provider_identifier: {
                "code": first.provider_identifier,
                "Bid": [],
                "Ask": [(2, 20)],
            }
        }
        context = BrowserQuoteContext(frames, subscription_failures=(1,))
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), mock.patch.object(futu, "_utc_now", return_value=NOW):
            batch = futu.retrieve_futu_browser_quote_batch_evidence(
                context, browser, timeout_seconds=0.001
            )
        self.assertEqual(len(batch.quotes), len(browser.rows))
        self.assertIs(
            batch.quotes[0].availability,
            futu.FutuBrowserQuoteAvailability.ASK_SIDE_AVAILABLE,
        )
        self.assertIn(
            futu.FutuBrowserQuoteReasonCode.NO_FRAME_RECEIVED,
            batch.quotes[1].reason_codes,
        )
        self.assertTrue(all(
            quote.reason_codes == (futu.FutuBrowserQuoteReasonCode.SUBSCRIPTION_FAILED,)
            for quote in batch.chunks[1].quotes
        ))

    def test_unexpected_identifier_and_constructor_coverage_fail_closed(self):
        browser = make_browser()
        context = BrowserQuoteContext(
            extra={"code": "US.UNEXPECTED", "Bid": [(1, 1)], "Ask": [(2, 1)]}
        )
        with mock.patch.object(futu, "_load_futu_sdk", return_value=FAKE_SDK), mock.patch.object(futu, "_utc_now", return_value=NOW):
            with self.assertRaisesRegex(ValueError, "response is invalid"):
                futu.retrieve_futu_browser_quote_batch_evidence(
                    context, browser, timeout_seconds=0.001
                )
        batch = make_quote_batch(browser)
        malformed = object.__new__(futu.FutuBrowserQuoteBatchEvidence)
        object.__setattr__(malformed, "browser", browser)
        object.__setattr__(malformed, "chunks", (batch.chunks[0], batch.chunks[0]))
        with self.assertRaises(ValueError):
            futu.FutuBrowserQuoteBatchEvidence.__post_init__(malformed)

        forged_quote = object.__new__(futu.FutuBrowserQuoteEvidence)
        for name, value in batch.quotes[0].__dict__.items():
            object.__setattr__(forged_quote, name, value)
        object.__setattr__(forged_quote, "reason_codes", (
            futu.FutuBrowserQuoteReasonCode.BID_ABSENT,
        ))
        forged_chunk = object.__new__(futu.FutuBrowserQuoteChunkEvidence)
        for name, value in batch.chunks[0].__dict__.items():
            object.__setattr__(forged_chunk, name, value)
        object.__setattr__(
            forged_chunk,
            "quotes",
            (forged_quote,) + batch.chunks[0].quotes[1:],
        )
        with self.assertRaises(ValueError):
            futu.FutuBrowserQuoteBatchEvidence(browser, (forged_chunk,))

        noncanonical_quote = object.__new__(futu.FutuBrowserQuoteEvidence)
        for name, value in batch.quotes[0].__dict__.items():
            object.__setattr__(noncanonical_quote, name, value)
        object.__setattr__(
            noncanonical_quote,
            "received_at",
            NOW.astimezone(datetime.timezone(datetime.timedelta(hours=8))),
        )
        noncanonical_chunk = object.__new__(futu.FutuBrowserQuoteChunkEvidence)
        for name, value in batch.chunks[0].__dict__.items():
            object.__setattr__(noncanonical_chunk, name, value)
        object.__setattr__(
            noncanonical_chunk,
            "quotes",
            (noncanonical_quote,) + batch.chunks[0].quotes[1:],
        )
        with self.assertRaises(ValueError):
            futu.FutuBrowserQuoteBatchEvidence(browser, (noncanonical_chunk,))

        noncanonical_times = object.__new__(futu.FutuBrowserQuoteChunkEvidence)
        for name, value in batch.chunks[0].__dict__.items():
            object.__setattr__(noncanonical_times, name, value)
        plus_eight = datetime.timezone(datetime.timedelta(hours=8))
        object.__setattr__(noncanonical_times, "started_at", NOW.astimezone(plus_eight))
        object.__setattr__(noncanonical_times, "completed_at", NOW.astimezone(plus_eight))
        with self.assertRaises(ValueError):
            futu.FutuBrowserQuoteBatchEvidence(browser, (noncanonical_times,))

        missing_batch = object.__new__(futu.FutuBrowserQuoteBatchEvidence)
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            futu.FutuBrowserQuoteBatchEvidence.__post_init__(missing_batch)

    def test_side_precedence_zero_absent_crossed_locked_and_malformed(self):
        row = make_browser().rows[0]
        cases = (
            ({"code": row.provider_identifier, "Bid": [(0, 1)], "Ask": [(2, 1)]}, futu.FutuBrowserQuoteAvailability.ASK_SIDE_AVAILABLE, futu.FutuBrowserQuoteReasonCode.BID_NONPOSITIVE),
            ({"code": row.provider_identifier, "Ask": [(2, 1)]}, futu.FutuBrowserQuoteAvailability.ASK_SIDE_AVAILABLE, futu.FutuBrowserQuoteReasonCode.BID_ABSENT),
            ({"code": row.provider_identifier, "Bid": [(1, 1)]}, futu.FutuBrowserQuoteAvailability.UNAVAILABLE, futu.FutuBrowserQuoteReasonCode.ASK_ABSENT),
            ({"code": row.provider_identifier, "Bid": [(1, 1)], "Ask": [(0, 1)]}, futu.FutuBrowserQuoteAvailability.UNAVAILABLE, futu.FutuBrowserQuoteReasonCode.ASK_NONPOSITIVE),
            ({"code": row.provider_identifier, "Bid": [(3, 1)], "Ask": [(2, 1)]}, futu.FutuBrowserQuoteAvailability.UNAVAILABLE, futu.FutuBrowserQuoteReasonCode.CROSSED_MARKET),
            ({"code": row.provider_identifier, "Bid": [(2, 1)], "Ask": [(2, 1)]}, futu.FutuBrowserQuoteAvailability.TWO_SIDED_AVAILABLE, None),
            ({"code": row.provider_identifier, "Bid": [(1, "bad")], "Ask": [(2, 1)]}, futu.FutuBrowserQuoteAvailability.ASK_SIDE_AVAILABLE, futu.FutuBrowserQuoteReasonCode.BID_SIZE_INVALID),
            ({"code": row.provider_identifier, "Bid": [(1, 1)], "Ask": [(2, "bad")]}, futu.FutuBrowserQuoteAvailability.UNAVAILABLE, futu.FutuBrowserQuoteReasonCode.ASK_SIZE_INVALID),
            ({"code": row.provider_identifier, "Bid": [(1, 10.0)], "Ask": [(2, 1)]}, futu.FutuBrowserQuoteAvailability.ASK_SIDE_AVAILABLE, futu.FutuBrowserQuoteReasonCode.BID_SIZE_INVALID),
            ({"code": row.provider_identifier, "Bid": [(1, 1)], "Ask": [(2, 10.0)]}, futu.FutuBrowserQuoteAvailability.UNAVAILABLE, futu.FutuBrowserQuoteReasonCode.ASK_SIZE_INVALID),
            ({"code": row.provider_identifier, "Bid": "bad", "Ask": [(2, 1)]}, futu.FutuBrowserQuoteAvailability.UNAVAILABLE, futu.FutuBrowserQuoteReasonCode.MALFORMED_FRAME),
        )
        with mock.patch.object(futu, "_utc_now", return_value=NOW):
            for frame, availability, reason in cases:
                with self.subTest(reason=reason):
                    quote = futu._browser_quote_from_atomic_frame(
                        data=frame, rsp_pb=FakeRsp(frame), row=row, chunk_index=0
                    )
                    self.assertIs(quote.availability, availability)
                    self.assertEqual(quote.reason_codes, () if reason is None else (reason,))


class DiscriminationBehaviorTests(unittest.TestCase):
    def result(self, browser, batch=None, bars=None, latest=datetime.date(2029, 12, 31)):
        batch = batch or make_quote_batch(browser)
        bars = bars or (make_bar(browser, latest),)
        return discrimination.discriminate_probability_free_convexity(
            browser,
            batch,
            bars,
            latest_completed_session_date=latest,
        )

    def test_all_five_distribution_modes_are_exhaustive(self):
        expected = {
            DistributionChangeMode.BIDIRECTIONAL_EXPANSION: (1, 0, "LONG_STRADDLE"),
            DistributionChangeMode.EVENT_DIRECTIONAL_UP: (1, 1, "LONG_CALL"),
            DistributionChangeMode.EXTREME_TAIL_UP: (1, 1, "LONG_CALL"),
            DistributionChangeMode.EVENT_DIRECTIONAL_DOWN: (1, 1, "LONG_PUT"),
            DistributionChangeMode.EXTREME_TAIL_DOWN: (1, 1, "LONG_PUT"),
        }
        for mode, (comparisons, noncomparisons, grammar) in expected.items():
            with self.subTest(mode=mode):
                result = self.result(make_browser(mode))
                self.assertEqual(len(result.comparisons), comparisons)
                self.assertEqual(len(result.non_comparison_rows), noncomparisons)
                self.assertEqual(result.comparisons[0].structure.grammar.name, grammar)

    def test_ndaq_162_rows_become_exactly_81_neutral_straddles(self):
        expirations = (
            datetime.date(2030, 3, 15),
            datetime.date(2030, 4, 19),
            datetime.date(2030, 5, 17),
        )
        strikes = tuple(decimal.Decimal(50 + index) for index in range(27))
        browser = make_browser(expirations=expirations, strikes=strikes)
        result = self.result(browser)
        self.assertEqual(len(browser.rows), 162)
        self.assertEqual(len(result.comparisons), 81)
        self.assertEqual(len(result.non_comparison_rows), 0)
        self.assertEqual(
            sum(len(item.structure.rows) for item in result.comparisons), 162
        )
        self.assertIs(
            result.hypothesis_maturity_alignment,
            HypothesisMaturityAlignment.NOT_ESTABLISHED,
        )

    def test_zero_or_absent_bid_preserves_ask_geometry_but_not_spread(self):
        browser = make_browser()

        def quotes(row, chunk_index):
            if row.option_type == "call":
                return futu.FutuBrowserQuoteEvidence(
                    row, chunk_index,
                    futu.FutuBrowserQuoteAvailability.ASK_SIDE_AVAILABLE,
                    None, decimal.Decimal("2"), None, 10, NOW, None, None,
                    (futu.FutuBrowserQuoteReasonCode.BID_NONPOSITIVE,),
                )
            return quote_for(row, chunk_index, bid=None, ask="3")

        result = self.result(browser, make_quote_batch(browser, quotes))
        item = result.comparisons[0]
        self.assertIs(item.premium_to_reference.status, discrimination.IndicativeMetricStatus.AVAILABLE)
        self.assertTrue(all(point.status is discrimination.IndicativeMetricStatus.AVAILABLE for point in item.response_ladder))
        self.assertIs(item.indicative_relative_spread.status, discrimination.IndicativeMetricStatus.UNAVAILABLE)

    def test_one_missing_straddle_ask_keeps_structure_with_unavailable_geometry(self):
        browser = make_browser()

        def quotes(row, chunk_index):
            if row.option_type == "put":
                return futu.FutuBrowserQuoteEvidence(
                    row, chunk_index,
                    futu.FutuBrowserQuoteAvailability.UNAVAILABLE,
                    None, None, None, None, NOW, None, None,
                    (futu.FutuBrowserQuoteReasonCode.ASK_ABSENT,),
                )
            return quote_for(row, chunk_index)

        item = self.result(browser, make_quote_batch(browser, quotes)).comparisons[0]
        self.assertIs(item.premium_to_reference.status, discrimination.IndicativeMetricStatus.UNAVAILABLE)
        self.assertEqual(
            item.premium_to_reference.unavailable_reasons,
            (discrimination.IndicativeMetricUnavailableReason.STRADDLE_LEG_ASK_UNAVAILABLE,),
        )
        self.assertEqual(len(item.payoff_multiple_hurdles), 8)
        self.assertEqual(len(item.response_ladder), 9)

    def test_exact_hurdle_ladder_and_spread_goldens(self):
        browser = make_browser(
            mode=DistributionChangeMode.EVENT_DIRECTIONAL_UP,
            option_types=("call",),
        )
        result = self.result(browser)
        item = result.comparisons[0]
        self.assertEqual(
            item.premium_to_reference.ratio_to_reference,
            ExactRational(1, 50),
        )
        self.assertEqual(
            tuple(h.terminal_underlying_price for h in item.payoff_multiple_hurdles),
            (ExactRational(102, 1), ExactRational(104, 1), ExactRational(110, 1), ExactRational(120, 1)),
        )
        self.assertEqual(
            item.response_ladder[-1].gross_expiration_response_multiple,
            ExactRational(25, 1),
        )
        self.assertEqual(item.indicative_relative_spread.relative_spread, ExactRational(2, 3))
        self.assertIs(
            result.quote_reference_temporal_alignment,
            discrimination.TemporalAlignmentState.NOT_ESTABLISHED,
        )
        self.assertIs(
            result.exact_deliverable_verification,
            discrimination.ExactDeliverableVerification.NOT_ESTABLISHED,
        )

    def test_negative_put_threshold_is_explicitly_unavailable(self):
        browser = make_browser(
            mode=DistributionChangeMode.EVENT_DIRECTIONAL_DOWN,
            strikes=(decimal.Decimal("5"),),
            option_types=("put",),
        )
        batch = make_quote_batch(
            browser, lambda row, index: quote_for(row, index, bid="9", ask="10")
        )
        hurdles = self.result(browser, batch).comparisons[0].payoff_multiple_hurdles
        self.assertIs(hurdles[0].status, discrimination.IndicativeMetricStatus.UNAVAILABLE)
        self.assertEqual(
            hurdles[0].unavailable_reasons,
            (discrimination.IndicativeMetricUnavailableReason.NEGATIVE_UNDERLYING_THRESHOLD,),
        )


class ReferenceAndIsolationTests(unittest.TestCase):
    def test_reference_must_be_unique_latest_complete_exact_futu_bar(self):
        browser = make_browser()
        batch = make_quote_batch(browser)
        older = make_bar(browser, datetime.date(2029, 12, 30), record_suffix="old")
        latest = make_bar(browser, datetime.date(2029, 12, 31), record_suffix="latest")
        with self.assertRaisesRegex(ValueError, "not latest"):
            discrimination.discriminate_probability_free_convexity(
                browser, batch, (older, latest),
                latest_completed_session_date=older.session_date,
            )
        with self.assertRaisesRegex(ValueError, "unique"):
            discrimination.discriminate_probability_free_convexity(
                browser, batch, (latest, replace(latest, metadata=replace(latest.metadata, record_id="duplicate"))),
                latest_completed_session_date=latest.session_date,
            )
        with self.assertRaisesRegex(ValueError, "exceeds evaluation"):
            discrimination.discriminate_probability_free_convexity(
                browser, batch, (latest,),
                latest_completed_session_date=EVALUATION_DATE + datetime.timedelta(days=1),
            )
        adjusted = replace(
            latest,
            adjusted_close_price=latest.close_price,
            adjustment_methodology="synthetic adjustment",
        )
        with self.assertRaisesRegex(ValueError, "identity or provenance"):
            discrimination.discriminate_probability_free_convexity(
                browser, batch, (adjusted,),
                latest_completed_session_date=latest.session_date,
            )
        incomplete_flag = replace(
            latest,
            metadata=replace(
                latest.metadata,
                quality_flags=(
                    NormalizationQualityFlag.SYMBOL_MAPPED,
                    NormalizationQualityFlag.INCOMPLETE,
                ),
            ),
        )
        with self.assertRaisesRegex(ValueError, "identity or provenance"):
            discrimination.discriminate_probability_free_convexity(
                browser, batch, (incomplete_flag,),
                latest_completed_session_date=latest.session_date,
            )

    def test_wrong_identity_provenance_and_batch_identity_fail_closed(self):
        browser = make_browser()
        batch = make_quote_batch(browser)
        bar = make_bar(browser, datetime.date(2029, 12, 31))
        wrong_source = replace(
            bar.metadata.source_references[0], provider_name="Other Provider"
        )
        wrong_bar = replace(
            bar,
            metadata=replace(bar.metadata, source_references=(wrong_source,)),
        )
        with self.assertRaisesRegex(ValueError, "provenance"):
            discrimination.discriminate_probability_free_convexity(
                browser, batch, (wrong_bar,),
                latest_completed_session_date=bar.session_date,
            )
        other_browser = make_browser(symbol="OTHER")
        with self.assertRaisesRegex(ValueError, "exact Browser"):
            discrimination.discriminate_probability_free_convexity(
                other_browser, batch, (bar,),
                latest_completed_session_date=bar.session_date,
            )

    def test_formal_artifact_and_missing_reason_boundaries_remain_closed(self):
        browser = make_browser()
        result = discrimination.discriminate_probability_free_convexity(
            browser,
            make_quote_batch(browser),
            (make_bar(browser, datetime.date(2029, 12, 31)),),
            latest_completed_session_date=datetime.date(2029, 12, 31),
        )
        values = (result,) + (None,) * 6
        with self.assertRaises(TypeError):
            candidate_assembly._require_outer_artifact_types(values)
        self.assertEqual(
            set(candidate_assembly._ARTIFACT_TYPES),
            {
                candidate_assembly.VolatilityEnvironmentTransformationResult,
                candidate_assembly.TailPricingTransformationResult,
                candidate_assembly.StructureLiquidityTransformationResult,
                candidate_assembly.StructureCostsTransformationResult,
                candidate_assembly.ScenarioValuationTransformationResult,
                candidate_assembly.ExpirationPayoffThresholdTransformationResult,
                candidate_assembly.StructureAffordabilityAssessmentResult,
            },
        )
        from convexity_hunter.scanner import ScreeningReasonCode
        self.assertEqual(
            tuple(
                item.value
                for item in ScreeningReasonCode
                if item.value.startswith("missing_")
            ),
            (
                "missing_costs",
                "missing_liquidity",
                "missing_volatility_environment",
                "missing_structure_expiration_tail_slice",
                "missing_target_move_scenario",
                "missing_volatility_crush_scenario",
            ),
        )

    def test_result_constructor_rejects_equal_but_nonidentical_quote(self):
        browser = make_browser()
        batch = make_quote_batch(browser)
        result = discrimination.discriminate_probability_free_convexity(
            browser,
            batch,
            (make_bar(browser, datetime.date(2029, 12, 31)),),
            latest_completed_session_date=datetime.date(2029, 12, 31),
        )
        first = result.comparisons[0]
        cloned_quote = replace(first.quote_evidence[0])
        forged_comparison = replace(
            first,
            quote_evidence=(cloned_quote,) + first.quote_evidence[1:],
        )
        with self.assertRaisesRegex(ValueError, "quote identity"):
            discrimination.ProbabilityFreeConvexityDiscriminationResult(
                result.browser,
                result.quote_batch,
                result.reference_price,
                (forged_comparison,) + result.comparisons[1:],
                result.non_comparison_rows,
            )

    def test_missing_quote_batch_fields_fail_closed(self):
        browser = make_browser()
        malformed = object.__new__(futu.FutuBrowserQuoteBatchEvidence)
        with self.assertRaisesRegex(ValueError, "quote_batch is malformed"):
            discrimination.discriminate_probability_free_convexity(
                browser,
                malformed,
                (make_bar(browser, datetime.date(2029, 12, 31)),),
                latest_completed_session_date=datetime.date(2029, 12, 31),
            )
        malformed_result = object.__new__(
            discrimination.ProbabilityFreeConvexityDiscriminationResult
        )
        with self.assertRaisesRegex(ValueError, "result is malformed"):
            discrimination.ProbabilityFreeConvexityDiscriminationResult.__post_init__(
                malformed_result
            )


if __name__ == "__main__":
    unittest.main()
