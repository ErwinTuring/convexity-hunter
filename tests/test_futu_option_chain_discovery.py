"""Synthetic tests for bounded Futu option-chain discovery evidence."""

import datetime
import decimal
import pathlib
import sys
import unittest
from dataclasses import fields
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
from convexity_hunter.discovery_entry import create_discovery_entry_handoff
from convexity_hunter.event_intelligence import (
    DistributionChangeMode,
    EventIntelligenceSubmission,
    EventSourceReference,
    EventStatement,
    EventStatementKind,
    EventUnderlyingHypothesis,
    MethodologizedDateRange,
    assess_event_intelligence_submission,
)
from convexity_hunter.market_data import (
    OptionContractReference,
    UnderlyingKey,
    UnderlyingSecurityType,
)
from convexity_hunter.option_chain_discovery import (
    OptionChainDiscoveryRequest,
    create_option_chain_discovery_request,
)
from convexity_hunter.providers import futu


UTC = datetime.timezone.utc
EVALUATION_DATE = datetime.date(2030, 1, 1)
LOWER = datetime.date(2030, 1, 31)
UPPER = datetime.date(2030, 5, 31)


class FakeTable:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, *, orient):
        if orient != "records":
            raise AssertionError
        return list(self.rows)


def make_request() -> OptionChainDiscoveryRequest:
    source = EventSourceReference(
        "source-1",
        "https://www.sec.gov/example",
        "Issuer filing",
        datetime.datetime(2029, 12, 1, tzinfo=UTC),
    )
    fact = EventStatement(
        "fact-1",
        EventStatementKind.OBSERVED_FACT,
        "The source declares a dated event.",
        (source.source_id,),
    )
    interpretation = EventStatement(
        "interpretation-1",
        EventStatementKind.INTERPRETATION,
        "The event may widen the distribution.",
        (),
        (fact.statement_id,),
    )
    window = MethodologizedDateRange(
        EVALUATION_DATE,
        EVALUATION_DATE,
        "Exact event date.",
    )
    hypothesis = EventUnderlyingHypothesis(
        "hypothesis-1",
        UnderlyingKey("ABC", "XNAS", UnderlyingSecurityType.EQUITY, "USD"),
        "A specific commercial outcome may change.",
        DistributionChangeMode.BIDIRECTIONAL_EXPANSION,
        "The future return distribution may widen.",
        window,
        None,
        (interpretation.statement_id,),
        (),
        "Contradictory evidence was reviewed; none was identified.",
        ("The event timing may change.",),
        ("The event is cancelled.",),
    )
    submission = EventIntelligenceSubmission(
        "submission-1",
        "event-1",
        "test-producer",
        "1.0",
        datetime.datetime(2030, 1, 1, tzinfo=UTC),
        "A dated issuer event is expected.",
        window,
        (source,),
        (fact, interpretation),
        (hypothesis,),
    )
    acceptance = assess_event_intelligence_submission(submission)
    handoff = create_discovery_entry_handoff(acceptance, hypothesis)
    return create_option_chain_discovery_request(
        handoff, evaluation_date=EVALUATION_DATE
    )


def expiration_row(date, cycle="MONTH"):
    return {"strike_time": date.isoformat(), "expiration_cycle": cycle}


def identifier(date, option_type, strike, root="ABC"):
    marker = "C" if option_type == "CALL" else "P"
    encoded_strike = int(decimal.Decimal(str(strike)) * 1000)
    return f"US.{root}{date:%y%m%d}{marker}{encoded_strike}"


def chain_row(
    date,
    option_type="CALL",
    strike="100",
    *,
    cycle="MONTH",
    standard="STANDARD",
    suspension=False,
    root=None,
    code=None,
):
    actual_root = root or ("ABC" if standard == "STANDARD" else "ABC1")
    return {
        "code": code or identifier(date, option_type, strike, actual_root),
        "lot_size": 100,
        "option_type": option_type,
        "stock_owner": "US.ABC",
        "strike_time": date.isoformat(),
        "strike_price": decimal.Decimal(str(strike)),
        "suspension": suspension,
        "expiration_cycle": cycle,
        "option_standard_type": standard,
    }


class DiscoveryContext:
    def __init__(self, expirations, chains=None, expiration_ret=0, chain_ret=0):
        self.expirations = expirations
        self.chains = chains or {}
        self.expiration_ret = expiration_ret
        self.chain_ret = chain_ret
        self.calls = []

    def get_option_expiration_date(self, code):
        self.calls.append(("expiration", code))
        return self.expiration_ret, FakeTable(self.expirations)

    def get_option_chain(self, code, *, start, end):
        self.calls.append(("chain", code, start, end))
        return self.chain_ret, FakeTable(self.chains.get(start, ()))

    def get_market_snapshot(self, *args, **kwargs):
        raise AssertionError("snapshot must not be called")

    def subscribe(self, *args, **kwargs):
        raise AssertionError("BBO must not be called")

    def request_history_kline(self, *args, **kwargs):
        raise AssertionError("history must not be called")


class PublicBoundaryTests(unittest.TestCase):
    def test_direct_api_fields_and_no_package_reexports(self):
        self.assertEqual(
            tuple(
                field.name
                for field in fields(futu.FutuOptionChainExpirationEvidence)
            ),
            (
                "expiration",
                "provider_expiration_cycle",
                "expiration_retrieved_at",
                "chain_retrieved_at",
            ),
        )
        self.assertEqual(
            tuple(
                field.name
                for field in fields(futu.FutuOptionChainContractEvidence)
            ),
            (
                "provider_identifier",
                "provider_underlying",
                "expiration",
                "option_type",
                "strike",
                "lot_size",
                "provider_expiration_cycle",
                "provider_standard_type",
                "suspension",
                "statuses",
                "retrieved_at",
            ),
        )
        self.assertEqual(
            tuple(
                field.name
                for field in fields(futu.FutuOptionChainDiscoveryEvidence)
            ),
            (
                "discovery_request",
                "provider_underlying",
                "expirations",
                "contracts",
            ),
        )
        for name in futu.__all__[-5:]:
            self.assertFalse(hasattr(convexity_hunter, name))
            self.assertFalse(
                hasattr(sys.modules["convexity_hunter.providers"], name)
            )


class SuccessfulRetrievalTests(unittest.TestCase):
    def test_inclusive_bounds_nonmonth_retention_calls_and_request_identity(self):
        weekly = datetime.date(2030, 3, 15)
        context = DiscoveryContext(
            [
                expiration_row(datetime.date(2030, 6, 1)),
                expiration_row(UPPER),
                expiration_row(weekly, "WEEK"),
                expiration_row(LOWER),
                expiration_row(datetime.date(2030, 1, 30)),
            ],
            {
                LOWER.isoformat(): [chain_row(LOWER, strike="101")],
                UPPER.isoformat(): [chain_row(UPPER, strike="102")],
            },
        )
        request = make_request()
        times = [
            datetime.datetime(2030, 1, 1, 10, 0, tzinfo=UTC),
            datetime.datetime(2030, 1, 1, 10, 1, tzinfo=UTC),
            datetime.datetime(2030, 1, 1, 10, 2, tzinfo=UTC),
        ]
        with mock.patch.object(futu, "_utc_now", side_effect=times):
            result = futu.retrieve_futu_option_chain_discovery_evidence(
                context, discovery_request=request
            )
        self.assertIs(result.discovery_request, request)
        self.assertEqual(result.provider_underlying, "US.ABC")
        self.assertEqual(
            tuple(item.expiration for item in result.expirations),
            (LOWER, weekly, UPPER),
        )
        self.assertIsNone(result.expirations[1].chain_retrieved_at)
        self.assertEqual(
            context.calls,
            [
                ("expiration", "US.ABC"),
                ("chain", "US.ABC", LOWER.isoformat(), LOWER.isoformat()),
                ("chain", "US.ABC", UPPER.isoformat(), UPPER.isoformat()),
            ],
        )
        self.assertEqual(len(result.contracts), 2)
        self.assertEqual(
            result.contracts[0].retrieved_at,
            result.expirations[0].chain_retrieved_at,
        )

    def test_all_status_combinations_are_retained_in_fixed_order(self):
        expiration = datetime.date(2030, 3, 15)
        rows = []
        expected = []
        index = 0
        for monthly in (True, False):
            for standard in (True, False):
                for suspended in (False, True):
                    index += 1
                    cycle = "MONTH" if monthly else "WEEK"
                    standard_type = "STANDARD" if standard else "NON_STANDARD"
                    rows.append(
                        chain_row(
                            expiration,
                            strike=str(100 + index),
                            cycle=cycle,
                            standard=standard_type,
                            suspension=suspended,
                        )
                    )
                    statuses = []
                    if not monthly:
                        statuses.append(futu.FutuOptionChainRowStatus.NON_MONTHLY)
                    if not standard:
                        statuses.append(futu.FutuOptionChainRowStatus.NON_STANDARD)
                    if suspended:
                        statuses.append(futu.FutuOptionChainRowStatus.SUSPENDED)
                    expected.append(
                        tuple(statuses)
                        or (futu.FutuOptionChainRowStatus.ELIGIBLE,)
                    )
        context = DiscoveryContext(
            [expiration_row(expiration)], {expiration.isoformat(): rows}
        )
        result = futu.retrieve_futu_option_chain_discovery_evidence(
            context, discovery_request=make_request()
        )
        by_strike = {
            item.strike: item.statuses for item in result.contracts
        }
        self.assertEqual(
            tuple(by_strike[decimal.Decimal(100 + i)] for i in range(1, 9)),
            tuple(expected),
        )

    def test_rows_are_canonically_ordered_without_selection(self):
        expiration = datetime.date(2030, 3, 15)
        rows = [
            chain_row(expiration, "PUT", "101"),
            chain_row(expiration, "PUT", "100"),
            chain_row(expiration, "CALL", "100"),
        ]
        context = DiscoveryContext(
            [expiration_row(expiration)], {expiration.isoformat(): rows}
        )
        result = futu.retrieve_futu_option_chain_discovery_evidence(
            context, discovery_request=make_request()
        )
        self.assertEqual(
            tuple((item.strike, item.option_type) for item in result.contracts),
            (
                (decimal.Decimal("100"), "call"),
                (decimal.Decimal("100"), "put"),
                (decimal.Decimal("101"), "put"),
            ),
        )
        self.assertFalse(
            any(
                isinstance(item, OptionContractReference)
                for item in result.contracts
            )
        )
        forbidden = (
            "contract_reference",
            "deliverable_id",
            "settlement_type",
            "delta",
            "quote",
            "costs",
            "liquidity",
        )
        self.assertTrue(
            all(
                not hasattr(item, name)
                for item in result.contracts
                for name in forbidden
            )
        )

    def test_empty_and_nonmonthly_responses_succeed_without_chain_calls(self):
        for rows in (
            [],
            [expiration_row(datetime.date(2030, 1, 30))],
            [expiration_row(datetime.date(2030, 3, 15), "WEEK")],
        ):
            with self.subTest(rows=rows):
                context = DiscoveryContext(rows)
                result = futu.retrieve_futu_option_chain_discovery_evidence(
                    context, discovery_request=make_request()
                )
                self.assertEqual(result.contracts, ())
                self.assertEqual(
                    tuple(call[0] for call in context.calls), ("expiration",)
                )

    def test_distinct_identifiers_with_same_economics_are_retained(self):
        expiration = datetime.date(2030, 3, 15)
        rows = [
            chain_row(expiration, standard="NON_STANDARD", root="ABC1"),
            chain_row(expiration, standard="NON_STANDARD", root="ABC2"),
        ]
        context = DiscoveryContext(
            [expiration_row(expiration)], {expiration.isoformat(): rows}
        )
        result = futu.retrieve_futu_option_chain_discovery_evidence(
            context, discovery_request=make_request()
        )
        self.assertEqual(len(result.contracts), 2)
        self.assertNotEqual(
            result.contracts[0].provider_identifier,
            result.contracts[1].provider_identifier,
        )


class FailureBoundaryTests(unittest.TestCase):
    def test_wrong_request_or_context_fails_controlled(self):
        with self.assertRaises(TypeError):
            futu.retrieve_futu_option_chain_discovery_evidence(
                DiscoveryContext([]), discovery_request=object()
            )
        malformed = object.__new__(OptionChainDiscoveryRequest)
        with self.assertRaises(ValueError):
            futu.retrieve_futu_option_chain_discovery_evidence(
                DiscoveryContext([]), discovery_request=malformed
            )
        with self.assertRaises(TypeError):
            futu.retrieve_futu_option_chain_discovery_evidence(
                object(), discovery_request=make_request()
            )

    def test_duplicate_retained_expiration_and_identifier_fail(self):
        expiration = datetime.date(2030, 3, 15)
        duplicate_expiration = DiscoveryContext(
            [expiration_row(expiration), expiration_row(expiration)]
        )
        with self.assertRaisesRegex(ValueError, "expiration response is invalid"):
            futu.retrieve_futu_option_chain_discovery_evidence(
                duplicate_expiration, discovery_request=make_request()
            )
        row = chain_row(expiration)
        duplicate_identifier = DiscoveryContext(
            [expiration_row(expiration)], {expiration.isoformat(): [row, dict(row)]}
        )
        with self.assertRaisesRegex(ValueError, "chain response is invalid"):
            futu.retrieve_futu_option_chain_discovery_evidence(
                duplicate_identifier, discovery_request=make_request()
            )

    def test_malformed_expiration_tables_and_values_fail(self):
        invalid_rows = (
            [{"strike_time": "2030-03-15"}],
            [expiration_row(datetime.date(2030, 3, 15), "")],
            [{"strike_time": "bad", "expiration_cycle": "MONTH"}],
        )
        for rows in invalid_rows:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                futu.retrieve_futu_option_chain_discovery_evidence(
                    DiscoveryContext(rows), discovery_request=make_request()
                )

    def test_malformed_chain_columns_and_values_fail(self):
        expiration = datetime.date(2030, 3, 15)
        valid = chain_row(expiration)
        cases = []
        for key in valid:
            row = dict(valid)
            row.pop(key)
            cases.append(row)
        replacements = {
            "code": "bad",
            "lot_size": 100.5,
            "option_type": "UNKNOWN",
            "stock_owner": "US.XYZ",
            "strike_time": "2030-03-16",
            "strike_price": decimal.Decimal("NaN"),
            "suspension": 0,
            "expiration_cycle": "",
            "option_standard_type": "",
        }
        extra_replacements = (
            ("lot_size", 0),
            ("lot_size", True),
            ("lot_size", float("inf")),
            ("strike_price", decimal.Decimal("0")),
            ("strike_price", float("inf")),
        )
        for key, value in replacements.items():
            row = dict(valid)
            row[key] = value
            cases.append(row)
        for key, value in extra_replacements:
            row = dict(valid)
            row[key] = value
            cases.append(row)
        for row in cases:
            with self.subTest(row=row), self.assertRaises((TypeError, ValueError)):
                context = DiscoveryContext(
                    [expiration_row(expiration)], {expiration.isoformat(): [row]}
                )
                futu.retrieve_futu_option_chain_discovery_evidence(
                    context, discovery_request=make_request()
                )

    def test_malformed_chain_date_does_not_leak_provider_value(self):
        expiration = datetime.date(2030, 3, 15)
        secret = "synthetic-provider-secret"
        row = chain_row(expiration)
        row["strike_time"] = secret
        context = DiscoveryContext(
            [expiration_row(expiration)], {expiration.isoformat(): [row]}
        )
        with self.assertRaisesRegex(ValueError, "chain response is invalid") as raised:
            futu.retrieve_futu_option_chain_discovery_evidence(
                context, discovery_request=make_request()
            )
        self.assertNotIn(secret, str(raised.exception))

    def test_identifier_economics_and_standard_root_must_agree(self):
        expiration = datetime.date(2030, 3, 15)
        bad_codes = (
            identifier(datetime.date(2030, 3, 16), "CALL", "100"),
            identifier(expiration, "PUT", "100"),
            identifier(expiration, "CALL", "101"),
            identifier(expiration, "CALL", "100", "XYZ"),
        )
        for code in bad_codes:
            with self.subTest(code=code), self.assertRaises(ValueError):
                context = DiscoveryContext(
                    [expiration_row(expiration)],
                    {expiration.isoformat(): [chain_row(expiration, code=code)]},
                )
                futu.retrieve_futu_option_chain_discovery_evidence(
                    context, discovery_request=make_request()
                )

    def test_direct_records_reject_inconsistent_status_or_timestamp(self):
        timestamp = datetime.datetime(2030, 1, 1, tzinfo=UTC)
        with self.assertRaises(ValueError):
            futu.FutuOptionChainExpirationEvidence(
                LOWER, "MONTH", timestamp, None
            )
        with self.assertRaises(ValueError):
            futu.FutuOptionChainContractEvidence(
                identifier(LOWER, "CALL", "100"),
                "US.ABC",
                LOWER,
                "call",
                decimal.Decimal("100"),
                100,
                "MONTH",
                "STANDARD",
                False,
                (futu.FutuOptionChainRowStatus.SUSPENDED,),
                timestamp,
            )
        with self.assertRaises(ValueError):
            futu.FutuOptionChainContractEvidence(
                identifier(LOWER, "CALL", "100"),
                "US.ABC",
                LOWER,
                "call",
                decimal.Decimal("100"),
                100,
                "MONTH",
                "STANDARD",
                False,
                ("eligible",),
                timestamp,
            )

    def test_discovery_result_rejects_constructor_bypassed_nested_records(self):
        request = make_request()
        malformed = object.__new__(futu.FutuOptionChainExpirationEvidence)
        with self.assertRaises(ValueError):
            futu.FutuOptionChainDiscoveryEvidence(
                request, "US.ABC", (malformed,), ()
            )

    def test_discovery_result_rejects_incoherent_response_times(self):
        request = make_request()
        first = datetime.datetime(2030, 1, 1, 10, 0, tzinfo=UTC)
        second = datetime.datetime(2030, 1, 1, 10, 1, tzinfo=UTC)
        lower = futu.FutuOptionChainExpirationEvidence(
            LOWER, "MONTH", first, second
        )
        upper = futu.FutuOptionChainExpirationEvidence(
            UPPER, "MONTH", second, second
        )
        with self.assertRaises(ValueError):
            futu.FutuOptionChainDiscoveryEvidence(
                request, "US.ABC", (lower, upper), ()
            )

        lower = futu.FutuOptionChainExpirationEvidence(
            LOWER, "MONTH", first, second
        )
        upper = futu.FutuOptionChainExpirationEvidence(
            UPPER,
            "MONTH",
            first,
            datetime.datetime(2030, 1, 1, 10, 0, 30, tzinfo=UTC),
        )
        with self.assertRaises(ValueError):
            futu.FutuOptionChainDiscoveryEvidence(
                request, "US.ABC", (lower, upper), ()
            )

    def test_discovery_result_requires_exact_underlying_string(self):
        class EqualitySpoof:
            def __eq__(self, other):
                return other == "US.ABC"

        with self.assertRaises(ValueError):
            futu.FutuOptionChainDiscoveryEvidence(
                make_request(), EqualitySpoof(), (), ()
            )

    def test_provider_failures_are_sanitized(self):
        secret = "synthetic-secret"

        class ExplodingContext(DiscoveryContext):
            def get_option_expiration_date(self, code):
                raise RuntimeError(secret)

        with self.assertRaisesRegex(RuntimeError, "retrieval failed") as raised:
            futu.retrieve_futu_option_chain_discovery_evidence(
                ExplodingContext([]), discovery_request=make_request()
            )
        self.assertNotIn(secret, str(raised.exception))

        expiration = datetime.date(2030, 3, 15)

        class ExplodingChainContext(DiscoveryContext):
            def get_option_chain(self, code, *, start, end):
                raise RuntimeError(secret)

        with self.assertRaisesRegex(RuntimeError, "retrieval failed") as raised:
            futu.retrieve_futu_option_chain_discovery_evidence(
                ExplodingChainContext([expiration_row(expiration)]),
                discovery_request=make_request(),
            )
        self.assertNotIn(secret, str(raised.exception))

    def test_non_success_codes_are_sanitized(self):
        expiration = datetime.date(2030, 3, 15)
        for context in (
            DiscoveryContext([], expiration_ret=-1),
            DiscoveryContext([expiration_row(expiration)], chain_ret=-1),
        ):
            with self.subTest(context=context), self.assertRaises(RuntimeError):
                futu.retrieve_futu_option_chain_discovery_evidence(
                    context, discovery_request=make_request()
                )


if __name__ == "__main__":
    unittest.main()
