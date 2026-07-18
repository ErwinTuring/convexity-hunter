"""Tests for Milestone 3A.1 market-data provenance and identity records."""

import dataclasses
import datetime
import decimal
import os
import pathlib
import subprocess
import sys
import unittest
from dataclasses import FrozenInstanceError

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter.market_data as market_data
from convexity_hunter.market_data import (
    DataOrigin,
    DividendStatus,
    MarketPhase,
    NormalizationMetadata,
    NormalizationQualityFlag,
    OptionContractKey,
    OptionContractReference,
    OptionOpenInterestObservation,
    OptionQuoteObservation,
    OptionVolumeObservation,
    QuoteScope,
    SourceQualityFlag,
    SourceReference,
    UnderlyingKey,
    UnderlyingQuoteObservation,
    UnderlyingSecurityType,
)
from tests.market_data_fixtures import (
    NON_UTC_OBSERVED_AT,
    NON_UTC_RETRIEVED_AT,
    NORMALIZED_AT,
    OBSERVED_AT,
    RETRIEVED_AT,
    UTC,
    build_normalization_metadata,
    build_option_contract_key,
    build_option_contract_reference,
    build_option_open_interest_observation,
    build_option_quote_observation,
    build_option_volume_observation,
    build_source_reference,
    build_underlying_key,
    build_underlying_quote_observation,
)


def build_metadata_for_origin(origin: DataOrigin) -> NormalizationMetadata:
    """Build deterministic metadata for one allowed normalized-record origin."""

    if origin is DataOrigin.SYSTEM_COMPOSITE:
        first = build_source_reference(source_id="composite-source-a")
        second = build_source_reference(
            source_id="composite-source-b",
            provider_record_id="record-002",
            observed_at=OBSERVED_AT + datetime.timedelta(seconds=1),
            retrieved_at=RETRIEVED_AT,
        )
        return build_normalization_metadata(
            [first, second],
            effective_observed_at=second.observed_at,
            record_origin=origin,
            quality_flags=(NormalizationQualityFlag.COMPOSITE_SOURCE,),
        )
    source_origin = (
        DataOrigin.PROVIDER_REFERENCE
        if origin is DataOrigin.PROVIDER_REFERENCE
        else origin
    )
    source = build_source_reference(origin=source_origin)
    return build_normalization_metadata([source], record_origin=origin)


def build_locked_metadata(multiple_sources: bool = False) -> NormalizationMetadata:
    """Build deterministic metadata with at least one locked source."""

    locked = build_source_reference(
        source_id="locked-source",
        quality_flags=(SourceQualityFlag.LOCKED,),
    )
    if not multiple_sources:
        return build_normalization_metadata([locked])
    other = build_source_reference(
        source_id="other-source",
        provider_record_id="record-002",
        observed_at=OBSERVED_AT + datetime.timedelta(seconds=1),
        retrieved_at=RETRIEVED_AT,
    )
    return build_normalization_metadata(
        [other, locked], effective_observed_at=other.observed_at
    )


class PublicSurfaceTests(unittest.TestCase):
    def test_exact_all_and_public_names_exist(self) -> None:
        expected = (
            "DataOrigin",
            "SourceQualityFlag",
            "NormalizationQualityFlag",
            "MarketPhase",
            "QuoteScope",
            "UnderlyingSecurityType",
            "DividendStatus",
            "SourceReference",
            "NormalizationMetadata",
            "UnderlyingKey",
            "OptionContractKey",
            "UnderlyingQuoteObservation",
            "OptionContractReference",
            "OptionQuoteObservation",
            "OptionVolumeObservation",
            "OptionOpenInterestObservation",
        )
        self.assertEqual(market_data.__all__, expected)
        self.assertTrue(all(hasattr(market_data, name) for name in expected))

    def test_later_milestone_types_do_not_exist(self) -> None:
        later_types = (
            "OptionImpliedVolatilityObservation",
            "OptionGreeksObservation",
            "UnderlyingDailyBarObservation",
            "RateCurvePointObservation",
            "DividendObservation",
            "MarketDataFreshnessPolicy",
            "FreshnessContext",
            "FreshnessAssessment",
            "CalculationLineage",
        )
        self.assertTrue(all(not hasattr(market_data, name) for name in later_types))

    def test_exact_dataclass_field_order(self) -> None:
        expected = {
            SourceReference: (
                "source_id", "provider_name", "dataset_name",
                "provider_record_id", "provider_request_id", "source_symbol",
                "source_uri", "observed_at", "retrieved_at",
                "provider_timezone", "timestamp_methodology", "origin",
                "is_delayed", "declared_delay_seconds", "payload_sha256",
                "revision_number", "provider_correction_id", "quality_flags",
            ),
            NormalizationMetadata: (
                "record_id", "source_references", "effective_observed_at",
                "normalized_at", "record_origin", "normalization_methodology",
                "unit_convention", "normalization_version", "quality_flags",
            ),
            UnderlyingKey: (
                "symbol", "listing_mic", "security_type", "currency",
            ),
            OptionContractKey: (
                "underlying_key", "expiration", "option_type", "strike",
                "contract_multiplier", "currency", "deliverable_id",
            ),
            UnderlyingQuoteObservation: (
                "underlying_key", "session_date", "bid_price", "ask_price",
                "last_price", "bid_size", "ask_size", "market_phase",
                "quote_scope", "venue_mic", "metadata",
            ),
            OptionContractReference: (
                "contract_key", "listing_date", "last_trade_date",
                "exercise_style", "settlement_type", "metadata",
            ),
            OptionQuoteObservation: (
                "contract_key", "session_date", "bid_premium", "ask_premium",
                "bid_size", "ask_size", "market_phase", "quote_scope",
                "venue_mic", "metadata",
            ),
            OptionVolumeObservation: (
                "contract_key", "session_date", "cumulative_volume",
                "is_session_complete", "metadata",
            ),
            OptionOpenInterestObservation: (
                "contract_key", "open_interest_session_date", "open_interest",
                "metadata",
            ),
        }
        for record, names in expected.items():
            with self.subTest(record=record.__name__):
                self.assertEqual(
                    tuple(field.name for field in dataclasses.fields(record)), names
                )


class EnumContractTests(unittest.TestCase):
    EXPECTED = {
        DataOrigin: (
            "exchange_observed", "provider_calculated", "provider_reference",
            "system_composite",
        ),
        SourceQualityFlag: (
            "delayed", "indicative", "non_firm", "locked", "halted",
            "after_hours", "corrected", "provider_estimated", "partial",
            "unknown_condition",
        ),
        NormalizationQualityFlag: (
            "unit_converted", "symbol_mapped", "contract_adjusted",
            "composite_source", "interpolated", "timestamp_assigned",
            "incomplete",
        ),
        MarketPhase: (
            "pre_market", "regular", "post_market", "closed", "unknown",
        ),
        QuoteScope: (
            "consolidated", "venue_specific", "provider_composite", "unknown",
        ),
        UnderlyingSecurityType: ("equity", "etf"),
        DividendStatus: ("forecast", "announced", "historical"),
    }

    def test_exact_values_order_string_behavior_and_uniqueness(self) -> None:
        for enum_type, expected in self.EXPECTED.items():
            with self.subTest(enum=enum_type.__name__):
                members = tuple(enum_type)
                self.assertEqual(tuple(member.value for member in members), expected)
                self.assertEqual(len(expected), len(set(expected)))
                self.assertTrue(all(isinstance(member, str) for member in members))


class SourceReferenceValidTests(unittest.TestCase):
    def test_valid_default_equality_hash_and_determinism(self) -> None:
        first = build_source_reference()
        second = build_source_reference()
        self.assertEqual(first, second)
        self.assertEqual(hash(first), hash(second))
        self.assertNotIn("0x", repr(first))

    def test_strings_are_trimmed_without_case_changes(self) -> None:
        source = build_source_reference(
            source_id=" id ", provider_name=" Provider Name ",
            dataset_name=" Data Set ", provider_record_id=" Record-X ",
            provider_request_id=" Request-X ", source_symbol=" spy ",
            source_uri=" synthetic://Value ", provider_timezone=" UTC ",
            timestamp_methodology=" Exact Source Time ",
        )
        self.assertEqual(source.source_id, "id")
        self.assertEqual(source.provider_name, "Provider Name")
        self.assertEqual(source.source_symbol, "spy")
        self.assertEqual(source.timestamp_methodology, "Exact Source Time")

    def test_non_utc_times_normalize_to_utc(self) -> None:
        source = build_source_reference(
            observed_at=NON_UTC_OBSERVED_AT,
            retrieved_at=NON_UTC_RETRIEVED_AT,
        )
        self.assertEqual(source.observed_at, OBSERVED_AT)
        self.assertEqual(source.retrieved_at, RETRIEVED_AT)
        self.assertEqual(source.observed_at.utcoffset(), datetime.timedelta(0))

    def test_quality_flag_list_normalizes_to_tuple_and_declaration_order(self) -> None:
        source = build_source_reference(
            quality_flags=[SourceQualityFlag.LOCKED, SourceQualityFlag.NON_FIRM]
        )
        self.assertEqual(
            source.quality_flags,
            (SourceQualityFlag.NON_FIRM, SourceQualityFlag.LOCKED),
        )

    def test_empty_flags_and_zero_or_none_revision_are_valid(self) -> None:
        self.assertEqual(build_source_reference().quality_flags, ())
        self.assertEqual(build_source_reference(revision_number=0).revision_number, 0)

    def test_frozen(self) -> None:
        source = build_source_reference()
        with self.assertRaises(FrozenInstanceError):
            source.source_id = "changed"  # type: ignore[misc]


class SourceReferenceInvalidTests(unittest.TestCase):
    def test_required_string_types_and_empty_values(self) -> None:
        for field in (
            "source_id", "provider_name", "dataset_name", "timestamp_methodology"
        ):
            with self.subTest(field=field, case="type"):
                with self.assertRaises(TypeError):
                    build_source_reference(**{field: 1})
            with self.subTest(field=field, case="empty"):
                with self.assertRaises(ValueError):
                    build_source_reference(**{field: "   "})

    def test_optional_strings_reject_empty_and_wrong_types(self) -> None:
        fields = (
            "provider_record_id", "provider_request_id", "source_symbol",
            "source_uri", "provider_timezone", "payload_sha256",
            "provider_correction_id",
        )
        for field in fields:
            with self.subTest(field=field, case="empty"):
                with self.assertRaises(ValueError):
                    build_source_reference(**{field: " "})
            with self.subTest(field=field, case="type"):
                with self.assertRaises(TypeError):
                    build_source_reference(**{field: 1})

    def test_origin_type_and_system_composite_rejected(self) -> None:
        with self.assertRaises(TypeError):
            build_source_reference(origin="exchange_observed")
        with self.assertRaises(ValueError):
            build_source_reference(origin=DataOrigin.SYSTEM_COMPOSITE)

    def test_timestamp_types_awareness_and_order(self) -> None:
        naive = datetime.datetime(2030, 1, 2, 15, 30)
        for field in ("observed_at", "retrieved_at"):
            with self.subTest(field=field, case="type"):
                with self.assertRaises(TypeError):
                    build_source_reference(**{field: OBSERVED_AT.date()})
            with self.subTest(field=field, case="naive"):
                with self.assertRaises(ValueError):
                    build_source_reference(**{field: naive})
        with self.assertRaises(ValueError):
            build_source_reference(
                observed_at=RETRIEVED_AT, retrieved_at=OBSERVED_AT
            )

    def test_is_delayed_requires_boolean(self) -> None:
        for value in (0, 1, "false", None):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    build_source_reference(is_delayed=value)


class DelayInvariantTests(unittest.TestCase):
    def test_valid_delayed_source(self) -> None:
        source = build_source_reference(
            is_delayed=True,
            declared_delay_seconds=900,
            quality_flags=(SourceQualityFlag.DELAYED,),
        )
        self.assertTrue(source.is_delayed)

    def test_invalid_delay_combinations(self) -> None:
        cases = (
            {"is_delayed": True, "declared_delay_seconds": None,
             "quality_flags": (SourceQualityFlag.DELAYED,)},
            {"is_delayed": True, "declared_delay_seconds": 0,
             "quality_flags": (SourceQualityFlag.DELAYED,)},
            {"is_delayed": True, "declared_delay_seconds": 10,
             "quality_flags": ()},
            {"is_delayed": False, "declared_delay_seconds": 10,
             "quality_flags": ()},
            {"is_delayed": False, "declared_delay_seconds": None,
             "quality_flags": (SourceQualityFlag.DELAYED,)},
        )
        for values in cases:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    build_source_reference(**values)

    def test_boolean_delay_seconds_rejected(self) -> None:
        with self.assertRaises(TypeError):
            build_source_reference(
                is_delayed=True,
                declared_delay_seconds=True,
                quality_flags=(SourceQualityFlag.DELAYED,),
            )


class HashAndCorrectionTests(unittest.TestCase):
    def test_valid_hash(self) -> None:
        self.assertEqual(build_source_reference().payload_sha256, "a" * 64)

    def test_invalid_hashes(self) -> None:
        for value in ("a" * 63, "a" * 65, "A" * 64, "g" * 64):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    build_source_reference(payload_sha256=value)

    def test_revision_type_and_range(self) -> None:
        with self.assertRaises(ValueError):
            build_source_reference(revision_number=-1)
        with self.assertRaises(TypeError):
            build_source_reference(revision_number=True)

    def test_positive_revision_with_corrected_flag_is_valid(self) -> None:
        source = build_source_reference(
            revision_number=1,
            quality_flags=(SourceQualityFlag.CORRECTED,),
        )
        self.assertEqual(source.revision_number, 1)

    def test_correction_id_with_corrected_flag_is_valid_and_trimmed(self) -> None:
        source = build_source_reference(
            provider_correction_id=" correction-1 ",
            quality_flags=(SourceQualityFlag.CORRECTED,),
        )
        self.assertEqual(source.provider_correction_id, "correction-1")

    def test_bidirectional_correction_invariants(self) -> None:
        cases = (
            {"revision_number": 1, "quality_flags": ()},
            {"provider_correction_id": "correction-1", "quality_flags": ()},
            {"quality_flags": (SourceQualityFlag.CORRECTED,)},
        )
        for values in cases:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    build_source_reference(**values)

    def test_correction_id_must_differ_after_whitespace_normalization(self) -> None:
        for field in ("provider_record_id", "provider_request_id"):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    build_source_reference(
                        **{
                            field: " same-id ",
                            "provider_correction_id": "same-id",
                            "quality_flags": (SourceQualityFlag.CORRECTED,),
                        }
                    )


class FlagValidationTests(unittest.TestCase):
    def test_source_flags_reject_set_wrong_type_and_duplicates(self) -> None:
        invalid = (
            {SourceQualityFlag.INDICATIVE},
            (NormalizationQualityFlag.INCOMPLETE,),
            (SourceQualityFlag.INDICATIVE, SourceQualityFlag.INDICATIVE),
        )
        for flags in invalid:
            with self.subTest(flags=flags):
                with self.assertRaises((TypeError, ValueError)):
                    build_source_reference(quality_flags=flags)

    def test_normalization_flags_reject_set_wrong_type_and_duplicates(self) -> None:
        invalid = (
            {NormalizationQualityFlag.INCOMPLETE},
            (SourceQualityFlag.PARTIAL,),
            (
                NormalizationQualityFlag.INCOMPLETE,
                NormalizationQualityFlag.INCOMPLETE,
            ),
        )
        for flags in invalid:
            with self.subTest(flags=flags):
                with self.assertRaises((TypeError, ValueError)):
                    build_normalization_metadata(quality_flags=flags)

    def test_normalization_flags_use_declaration_not_alphabetical_order(self) -> None:
        metadata = build_normalization_metadata(
            quality_flags=[
                NormalizationQualityFlag.INCOMPLETE,
                NormalizationQualityFlag.SYMBOL_MAPPED,
                NormalizationQualityFlag.UNIT_CONVERTED,
            ]
        )
        self.assertEqual(
            metadata.quality_flags,
            (
                NormalizationQualityFlag.UNIT_CONVERTED,
                NormalizationQualityFlag.SYMBOL_MAPPED,
                NormalizationQualityFlag.INCOMPLETE,
            ),
        )


class NormalizationMetadataTests(unittest.TestCase):
    def _multi_sources(self) -> tuple:
        first = build_source_reference(source_id="source-b")
        second = build_source_reference(
            source_id="source-a",
            provider_record_id="record-002",
            observed_at=OBSERVED_AT + datetime.timedelta(seconds=1),
            retrieved_at=RETRIEVED_AT,
        )
        return first, second

    def test_valid_single_source_hash_equality_and_frozen(self) -> None:
        first = build_normalization_metadata()
        second = build_normalization_metadata()
        self.assertEqual(first, second)
        self.assertEqual(hash(first), hash(second))
        with self.assertRaises(FrozenInstanceError):
            first.record_id = "changed"  # type: ignore[misc]

    def test_sources_normalize_to_tuple_and_source_id_order(self) -> None:
        first, second = self._multi_sources()
        metadata = build_normalization_metadata(
            sources=[first, second],
            effective_observed_at=second.observed_at,
        )
        self.assertEqual(
            tuple(source.source_id for source in metadata.source_references),
            ("source-a", "source-b"),
        )

    def test_reversed_sources_produce_equal_records(self) -> None:
        first, second = self._multi_sources()
        values = {
            "effective_observed_at": second.observed_at,
            "normalized_at": NORMALIZED_AT,
        }
        self.assertEqual(
            build_normalization_metadata([first, second], **values),
            build_normalization_metadata([second, first], **values),
        )

    def test_non_utc_times_normalize_to_utc(self) -> None:
        source = build_source_reference(
            observed_at=NON_UTC_OBSERVED_AT,
            retrieved_at=NON_UTC_RETRIEVED_AT,
        )
        metadata = build_normalization_metadata(
            [source],
            effective_observed_at=NON_UTC_OBSERVED_AT,
            normalized_at=datetime.datetime(
                2030, 1, 2, 10, 30, 3,
                tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
            ),
        )
        self.assertEqual(metadata.effective_observed_at, OBSERVED_AT)
        self.assertEqual(metadata.normalized_at.utcoffset(), datetime.timedelta(0))

    def test_valid_system_composite(self) -> None:
        first, second = self._multi_sources()
        metadata = build_normalization_metadata(
            [first, second],
            effective_observed_at=second.observed_at,
            record_origin=DataOrigin.SYSTEM_COMPOSITE,
            quality_flags=(NormalizationQualityFlag.COMPOSITE_SOURCE,),
        )
        self.assertIs(metadata.record_origin, DataOrigin.SYSTEM_COMPOSITE)

    def test_source_collection_and_items(self) -> None:
        with self.assertRaises(ValueError):
            build_normalization_metadata([])
        with self.assertRaises(TypeError):
            build_normalization_metadata("source")
        with self.assertRaises(TypeError):
            build_normalization_metadata([build_source_reference(), "source"])

    def test_duplicate_source_ids_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_normalization_metadata(
                [build_source_reference(), build_source_reference()]
            )

    def test_required_strings_rejected(self) -> None:
        for field in (
            "record_id", "normalization_methodology", "unit_convention",
            "normalization_version",
        ):
            with self.subTest(field=field, case="empty"):
                with self.assertRaises(ValueError):
                    build_normalization_metadata(**{field: " "})
            with self.subTest(field=field, case="type"):
                with self.assertRaises(TypeError):
                    build_normalization_metadata(**{field: 1})

    def test_record_origin_validation(self) -> None:
        with self.assertRaises(TypeError):
            build_normalization_metadata(record_origin="exchange_observed")
        with self.assertRaises(ValueError):
            build_normalization_metadata(record_origin=DataOrigin.SYSTEM_COMPOSITE)
        first, second = self._multi_sources()
        with self.assertRaises(ValueError):
            build_normalization_metadata(
                [first, second],
                effective_observed_at=second.observed_at,
                record_origin=DataOrigin.SYSTEM_COMPOSITE,
            )

    def test_effective_time_rules(self) -> None:
        source = build_source_reference()
        with self.assertRaises(ValueError):
            build_normalization_metadata(
                [source],
                effective_observed_at=source.observed_at + datetime.timedelta(seconds=1),
            )
        first, second = self._multi_sources()
        earliest = min(first.observed_at, second.observed_at)
        latest = max(first.observed_at, second.observed_at)
        for effective in (
            earliest - datetime.timedelta(microseconds=1),
            latest + datetime.timedelta(microseconds=1),
        ):
            with self.subTest(effective=effective):
                with self.assertRaises(ValueError):
                    build_normalization_metadata(
                        [first, second], effective_observed_at=effective
                    )

    def test_normalized_time_rules(self) -> None:
        source = build_source_reference()
        with self.assertRaises(ValueError):
            build_normalization_metadata(
                [source], normalized_at=source.observed_at - datetime.timedelta(seconds=1)
            )
        late_retrieval = build_source_reference(
            retrieved_at=NORMALIZED_AT + datetime.timedelta(seconds=1)
        )
        with self.assertRaises(ValueError):
            build_normalization_metadata([late_retrieval])

    def test_naive_and_non_datetime_times_rejected(self) -> None:
        naive = datetime.datetime(2030, 1, 2, 15, 30)
        for field in ("effective_observed_at", "normalized_at"):
            with self.subTest(field=field, case="naive"):
                with self.assertRaises(ValueError):
                    build_normalization_metadata(**{field: naive})
            with self.subTest(field=field, case="type"):
                with self.assertRaises(TypeError):
                    build_normalization_metadata(**{field: OBSERVED_AT.date()})


class UnderlyingKeyTests(unittest.TestCase):
    def test_valid_equity_etf_normalization_hash_and_frozen(self) -> None:
        equity = build_underlying_key(
            symbol=" aapl ", listing_mic=" xnas ",
            security_type=UnderlyingSecurityType.EQUITY, currency=" usd ",
        )
        etf = build_underlying_key()
        self.assertEqual((equity.symbol, equity.listing_mic, equity.currency),
                         ("AAPL", "XNAS", "USD"))
        self.assertEqual(etf.security_type, UnderlyingSecurityType.ETF)
        self.assertEqual(hash(etf), hash(build_underlying_key()))
        with self.assertRaises(FrozenInstanceError):
            etf.symbol = "QQQ"  # type: ignore[misc]

    def test_none_listing_mic_valid(self) -> None:
        self.assertIsNone(build_underlying_key(listing_mic=None).listing_mic)

    def test_invalid_fields(self) -> None:
        cases = (
            ("symbol", " ", ValueError),
            ("symbol", 1, TypeError),
            ("listing_mic", " ", ValueError),
            ("listing_mic", 1, TypeError),
            ("security_type", "etf", TypeError),
            ("currency", 1, TypeError),
            ("currency", "EUR", ValueError),
        )
        for field, value, error in cases:
            with self.subTest(field=field, value=value):
                with self.assertRaises(error):
                    build_underlying_key(**{field: value})


class OptionContractKeyTests(unittest.TestCase):
    def test_valid_call_put_normalization_and_precision(self) -> None:
        call = build_option_contract_key(
            option_type=" CALL ", currency=" usd ",
            strike=decimal.Decimal("500.125000"),
        )
        put = build_option_contract_key(option_type="put")
        self.assertEqual(call.option_type, "call")
        self.assertEqual(put.option_type, "put")
        self.assertEqual(call.currency, "USD")
        self.assertEqual(call.strike.as_tuple().exponent, -6)

    def test_standard_and_adjusted_identities(self) -> None:
        self.assertIsNone(build_option_contract_key().deliverable_id)
        adjusted = build_option_contract_key(deliverable_id=" adjusted-001 ")
        self.assertEqual(adjusted.deliverable_id, "adjusted-001")

    def test_frozen_hashable_and_deterministic(self) -> None:
        contract = build_option_contract_key()
        self.assertEqual(contract, build_option_contract_key())
        self.assertEqual(hash(contract), hash(build_option_contract_key()))
        self.assertNotIn("0x", repr(contract))
        with self.assertRaises(FrozenInstanceError):
            contract.currency = "EUR"  # type: ignore[misc]

    def test_underlying_expiration_and_option_type_validation(self) -> None:
        with self.assertRaises(TypeError):
            build_option_contract_key(underlying_key="SPY")
        with self.assertRaises(TypeError):
            build_option_contract_key(
                expiration=datetime.datetime(2030, 3, 15, tzinfo=UTC)
            )
        with self.assertRaises(TypeError):
            build_option_contract_key(option_type=1)
        with self.assertRaises(ValueError):
            build_option_contract_key(option_type="straddle")

    def test_strike_requires_positive_finite_decimal(self) -> None:
        invalid = (
            decimal.Decimal("0"), decimal.Decimal("-1"),
            decimal.Decimal("NaN"), decimal.Decimal("Infinity"),
            decimal.Decimal("-Infinity"), 1.0, 1, True, "1.0",
        )
        for value in invalid:
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    build_option_contract_key(strike=value)

    def test_multiplier_validation_and_no_100_assumption(self) -> None:
        self.assertEqual(
            build_option_contract_key(contract_multiplier=10).contract_multiplier, 10
        )
        for value in (0, -1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    build_option_contract_key(contract_multiplier=value)
        with self.assertRaises(TypeError):
            build_option_contract_key(contract_multiplier=True)

    def test_currency_and_deliverable_validation(self) -> None:
        with self.assertRaises(ValueError):
            build_option_contract_key(currency="EUR")
        with self.assertRaises(ValueError):
            build_option_contract_key(deliverable_id=" ")
        with self.assertRaises(TypeError):
            build_option_contract_key(deliverable_id=1)


class UnderlyingQuoteObservationTests(unittest.TestCase):
    def test_valid_defaults_optional_values_and_determinism(self) -> None:
        quote = build_underlying_quote_observation()
        self.assertEqual(quote, build_underlying_quote_observation())
        self.assertEqual(hash(quote), hash(build_underlying_quote_observation()))
        self.assertEqual(quote.market_phase, MarketPhase.REGULAR)
        self.assertEqual(quote.quote_scope, QuoteScope.CONSOLIDATED)
        self.assertIsNone(quote.venue_mic)
        self.assertIsNone(
            build_underlying_quote_observation(last_price=None).last_price
        )
        optional = build_underlying_quote_observation(
            bid_size=None, ask_size=None
        )
        self.assertIsNone(optional.bid_size)
        self.assertIsNone(optional.ask_size)

    def test_zero_negative_zero_and_precision(self) -> None:
        zero = build_underlying_quote_observation(
            bid_price=decimal.Decimal("0"), ask_price=decimal.Decimal("1")
        )
        negative_zero = build_underlying_quote_observation(
            bid_price=decimal.Decimal("-0.00"), ask_price=decimal.Decimal("1.00")
        )
        precise = build_underlying_quote_observation(
            bid_price=decimal.Decimal("1.123400"),
            ask_price=decimal.Decimal("1.123500"),
        )
        self.assertEqual(zero.bid_price, decimal.Decimal("0"))
        self.assertFalse(negative_zero.bid_price.is_signed())
        self.assertEqual(negative_zero.bid_price.as_tuple().exponent, -2)
        self.assertEqual(precise.bid_price.as_tuple().exponent, -6)

    def test_valid_quote_scopes_and_venue_normalization(self) -> None:
        venue = build_underlying_quote_observation(
            quote_scope=QuoteScope.VENUE_SPECIFIC, venue_mic=" xnas "
        )
        self.assertEqual(venue.venue_mic, "XNAS")
        for scope in (
            QuoteScope.CONSOLIDATED,
            QuoteScope.PROVIDER_COMPOSITE,
            QuoteScope.UNKNOWN,
        ):
            with self.subTest(scope=scope):
                self.assertIsNone(
                    build_underlying_quote_observation(
                        quote_scope=scope, venue_mic=None
                    ).venue_mic
                )

    def test_valid_locked_quote_frozen_and_hashable(self) -> None:
        quote = build_underlying_quote_observation(
            bid_price=decimal.Decimal("500.00"),
            ask_price=decimal.Decimal("500.00"),
            metadata=build_locked_metadata(),
        )
        self.assertEqual(quote.bid_price, quote.ask_price)
        hash(quote)
        with self.assertRaises(FrozenInstanceError):
            quote.bid_price = decimal.Decimal("1")  # type: ignore[misc]

    def test_invalid_identity_date_enums_metadata_and_origin(self) -> None:
        cases = (
            ({"underlying_key": "SPY"}, TypeError),
            ({"session_date": datetime.datetime(2030, 1, 2)}, TypeError),
            ({"session_date": "2030-01-02"}, TypeError),
            ({"market_phase": "regular"}, TypeError),
            ({"quote_scope": "consolidated"}, TypeError),
            ({"metadata": "metadata"}, TypeError),
            ({"metadata": build_metadata_for_origin(DataOrigin.PROVIDER_REFERENCE)},
             ValueError),
        )
        for values, error in cases:
            with self.subTest(values=values):
                with self.assertRaises(error):
                    build_underlying_quote_observation(**values)

    def test_invalid_price_types_nonfinite_and_ranges(self) -> None:
        for field in ("bid_price", "ask_price"):
            for value in (1.0, 1, True, "1", decimal.Decimal("NaN"),
                          decimal.Decimal("Infinity"), decimal.Decimal("-Infinity")):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        build_underlying_quote_observation(**{field: value})
        for values in (
            {"bid_price": decimal.Decimal("-0.01")},
            {"ask_price": decimal.Decimal("0")},
            {"ask_price": decimal.Decimal("-1")},
            {"bid_price": decimal.Decimal("2"), "ask_price": decimal.Decimal("1")},
            {"bid_price": decimal.Decimal("1"), "ask_price": decimal.Decimal("1")},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    build_underlying_quote_observation(**values)

    def test_invalid_last_price(self) -> None:
        for value in (decimal.Decimal("0"), decimal.Decimal("-1"),
                      decimal.Decimal("NaN"), 1.0, 1, True, "1"):
            with self.subTest(value=value):
                with self.assertRaises((TypeError, ValueError)):
                    build_underlying_quote_observation(last_price=value)

    def test_invalid_sizes(self) -> None:
        for field in ("bid_size", "ask_size"):
            for value in (-1, True, 1.0, "1"):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        build_underlying_quote_observation(**{field: value})

    def test_invalid_scope_venue_combinations(self) -> None:
        cases = (
            {"quote_scope": QuoteScope.VENUE_SPECIFIC, "venue_mic": None},
            {"quote_scope": QuoteScope.CONSOLIDATED, "venue_mic": "XNAS"},
            {"quote_scope": QuoteScope.PROVIDER_COMPOSITE, "venue_mic": "XNAS"},
            {"quote_scope": QuoteScope.UNKNOWN, "venue_mic": "XNAS"},
            {"quote_scope": QuoteScope.VENUE_SPECIFIC, "venue_mic": " "},
            {"quote_scope": QuoteScope.VENUE_SPECIFIC, "venue_mic": 1},
        )
        for values in cases:
            with self.subTest(values=values):
                with self.assertRaises((TypeError, ValueError)):
                    build_underlying_quote_observation(**values)


class OptionContractReferenceTests(unittest.TestCase):
    def test_valid_full_optional_and_string_normalization(self) -> None:
        reference = build_option_contract_reference(
            exercise_style=" American Style ", settlement_type=" Physical Delivery "
        )
        self.assertEqual(reference.exercise_style, "American Style")
        self.assertEqual(reference.settlement_type, "Physical Delivery")
        empty = build_option_contract_reference(
            listing_date=None, last_trade_date=None,
            exercise_style=None, settlement_type=None,
        )
        self.assertIsNone(empty.listing_date)
        self.assertIsNone(empty.exercise_style)
        self.assertEqual(reference.metadata.record_origin, DataOrigin.PROVIDER_REFERENCE)

    def test_valid_system_composite_frozen_hashable_and_deterministic(self) -> None:
        reference = build_option_contract_reference(
            metadata=build_metadata_for_origin(DataOrigin.SYSTEM_COMPOSITE)
        )
        self.assertEqual(reference, build_option_contract_reference(
            metadata=build_metadata_for_origin(DataOrigin.SYSTEM_COMPOSITE)
        ))
        hash(reference)
        with self.assertRaises(FrozenInstanceError):
            reference.exercise_style = "Changed"  # type: ignore[misc]

    def test_invalid_contract_dates_and_chronology(self) -> None:
        expiration = build_option_contract_key().expiration
        cases = (
            ({"contract_key": "contract"}, TypeError),
            ({"listing_date": datetime.datetime(2029, 1, 1)}, TypeError),
            ({"last_trade_date": datetime.datetime(2030, 1, 1)}, TypeError),
            ({"listing_date": expiration + datetime.timedelta(days=1)}, ValueError),
            ({"last_trade_date": expiration + datetime.timedelta(days=1)}, ValueError),
            ({"listing_date": datetime.date(2030, 3, 14),
              "last_trade_date": datetime.date(2030, 3, 13)}, ValueError),
        )
        for values, error in cases:
            with self.subTest(values=values):
                with self.assertRaises(error):
                    build_option_contract_reference(**values)

    def test_invalid_optional_strings_and_metadata_origins(self) -> None:
        for field in ("exercise_style", "settlement_type"):
            for value in (" ", 1):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        build_option_contract_reference(**{field: value})
        with self.assertRaises(TypeError):
            build_option_contract_reference(metadata="metadata")
        for origin in (
            DataOrigin.EXCHANGE_OBSERVED, DataOrigin.PROVIDER_CALCULATED
        ):
            with self.subTest(origin=origin):
                with self.assertRaises(ValueError):
                    build_option_contract_reference(
                        metadata=build_metadata_for_origin(origin)
                    )

    def test_no_provider_symbol_or_venue_fields(self) -> None:
        names = tuple(field.name for field in dataclasses.fields(OptionContractReference))
        self.assertNotIn("provider_contract_symbol", names)
        self.assertNotIn("venue_mic", names)


class OptionQuoteObservationTests(unittest.TestCase):
    def test_valid_defaults_optional_sizes_and_precision(self) -> None:
        quote = build_option_quote_observation()
        self.assertEqual(quote, build_option_quote_observation())
        optional = build_option_quote_observation(bid_size=None, ask_size=None)
        self.assertIsNone(optional.bid_size)
        precise = build_option_quote_observation(
            bid_premium=decimal.Decimal("10.250000"),
            ask_premium=decimal.Decimal("10.350000"),
        )
        self.assertEqual(precise.bid_premium.as_tuple().exponent, -6)

    def test_zero_negative_zero_scopes_and_locked_quote(self) -> None:
        zero = build_option_quote_observation(
            bid_premium=decimal.Decimal("-0.00"),
            ask_premium=decimal.Decimal("1.00"),
        )
        self.assertFalse(zero.bid_premium.is_signed())
        self.assertEqual(zero.bid_premium.as_tuple().exponent, -2)
        venue = build_option_quote_observation(
            quote_scope=QuoteScope.VENUE_SPECIFIC, venue_mic=" xnas "
        )
        self.assertEqual(venue.venue_mic, "XNAS")
        for scope in (QuoteScope.CONSOLIDATED,
                      QuoteScope.PROVIDER_COMPOSITE, QuoteScope.UNKNOWN):
            self.assertIsNone(build_option_quote_observation(
                quote_scope=scope, venue_mic=None
            ).venue_mic)
        locked = build_option_quote_observation(
            bid_premium=decimal.Decimal("10.30"),
            ask_premium=decimal.Decimal("10.30"),
            metadata=build_locked_metadata(),
        )
        self.assertEqual(locked.bid_premium, locked.ask_premium)
        hash(locked)

    def test_invalid_identity_date_enums_metadata_and_origin(self) -> None:
        cases = (
            ({"contract_key": "contract"}, TypeError),
            ({"session_date": datetime.datetime(2030, 1, 2)}, TypeError),
            ({"session_date": "2030-01-02"}, TypeError),
            ({"market_phase": "regular"}, TypeError),
            ({"quote_scope": "consolidated"}, TypeError),
            ({"metadata": "metadata"}, TypeError),
            ({"metadata": build_metadata_for_origin(DataOrigin.PROVIDER_REFERENCE)},
             ValueError),
        )
        for values, error in cases:
            with self.subTest(values=values):
                with self.assertRaises(error):
                    build_option_quote_observation(**values)

    def test_invalid_premiums_sizes_and_scope_venue(self) -> None:
        for field in ("bid_premium", "ask_premium"):
            for value in (1.0, 1, True, "1", decimal.Decimal("NaN"),
                          decimal.Decimal("Infinity"), decimal.Decimal("-Infinity")):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        build_option_quote_observation(**{field: value})
        for values in (
            {"bid_premium": decimal.Decimal("-0.01")},
            {"ask_premium": decimal.Decimal("0")},
            {"ask_premium": decimal.Decimal("-1")},
            {"bid_premium": decimal.Decimal("2"),
             "ask_premium": decimal.Decimal("1")},
            {"bid_premium": decimal.Decimal("1"),
             "ask_premium": decimal.Decimal("1")},
            {"quote_scope": QuoteScope.VENUE_SPECIFIC, "venue_mic": None},
            {"quote_scope": QuoteScope.CONSOLIDATED, "venue_mic": "XNAS"},
            {"quote_scope": QuoteScope.PROVIDER_COMPOSITE, "venue_mic": "XNAS"},
            {"quote_scope": QuoteScope.UNKNOWN, "venue_mic": "XNAS"},
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    build_option_quote_observation(**values)
        for values in (
            {"quote_scope": QuoteScope.VENUE_SPECIFIC, "venue_mic": " "},
            {"quote_scope": QuoteScope.VENUE_SPECIFIC, "venue_mic": 1},
        ):
            with self.subTest(values=values):
                with self.assertRaises((TypeError, ValueError)):
                    build_option_quote_observation(**values)
        for field in ("bid_size", "ask_size"):
            for value in (-1, True, 1.0, "1"):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        build_option_quote_observation(**{field: value})

    def test_frozen(self) -> None:
        quote = build_option_quote_observation()
        with self.assertRaises(FrozenInstanceError):
            quote.bid_premium = decimal.Decimal("1")  # type: ignore[misc]


class OptionActivityObservationTests(unittest.TestCase):
    def test_volume_valid_incomplete_complete_zero_frozen_hashable(self) -> None:
        incomplete = build_option_volume_observation()
        complete = build_option_volume_observation(is_session_complete=True)
        zero = build_option_volume_observation(cumulative_volume=0)
        self.assertFalse(incomplete.is_session_complete)
        self.assertTrue(complete.is_session_complete)
        self.assertEqual(zero.cumulative_volume, 0)
        hash(incomplete)
        with self.assertRaises(FrozenInstanceError):
            incomplete.cumulative_volume = 1  # type: ignore[misc]

    def test_volume_completion_is_only_the_supplied_value(self) -> None:
        observation = build_option_volume_observation(
            is_session_complete=False,
            metadata=build_normalization_metadata(
                effective_observed_at=OBSERVED_AT,
                normalized_at=NORMALIZED_AT,
            ),
        )
        self.assertFalse(observation.is_session_complete)

    def test_volume_invalid_values(self) -> None:
        cases = (
            ({"contract_key": "contract"}, TypeError),
            ({"session_date": datetime.datetime(2030, 1, 2)}, TypeError),
            ({"session_date": "2030-01-02"}, TypeError),
            ({"cumulative_volume": -1}, ValueError),
            ({"cumulative_volume": True}, TypeError),
            ({"cumulative_volume": 1.0}, TypeError),
            ({"is_session_complete": 1}, TypeError),
            ({"metadata": "metadata"}, TypeError),
            ({"metadata": build_metadata_for_origin(DataOrigin.PROVIDER_REFERENCE)},
             ValueError),
        )
        for values, error in cases:
            with self.subTest(values=values):
                with self.assertRaises(error):
                    build_option_volume_observation(**values)

    def test_open_interest_valid_positive_zero_date_independence_and_frozen(self) -> None:
        positive = build_option_open_interest_observation()
        zero = build_option_open_interest_observation(open_interest=0)
        independent = build_option_open_interest_observation(
            open_interest_session_date=datetime.date(2029, 12, 20)
        )
        self.assertGreater(positive.open_interest, 0)
        self.assertEqual(zero.open_interest, 0)
        self.assertNotEqual(
            independent.open_interest_session_date,
            independent.metadata.effective_observed_at.date(),
        )
        hash(positive)
        with self.assertRaises(FrozenInstanceError):
            positive.open_interest = 1  # type: ignore[misc]

    def test_open_interest_invalid_values(self) -> None:
        cases = (
            ({"contract_key": "contract"}, TypeError),
            ({"open_interest_session_date": datetime.datetime(2030, 1, 1)},
             TypeError),
            ({"open_interest_session_date": "2030-01-01"}, TypeError),
            ({"open_interest": -1}, ValueError),
            ({"open_interest": True}, TypeError),
            ({"open_interest": 1.0}, TypeError),
            ({"metadata": "metadata"}, TypeError),
            ({"metadata": build_metadata_for_origin(DataOrigin.PROVIDER_REFERENCE)},
             ValueError),
        )
        for values, error in cases:
            with self.subTest(values=values):
                with self.assertRaises(error):
                    build_option_open_interest_observation(**values)


class ObservationOriginAndLockedSourceTests(unittest.TestCase):
    MARKET_BUILDERS = (
        build_underlying_quote_observation,
        build_option_quote_observation,
        build_option_volume_observation,
        build_option_open_interest_observation,
    )

    def test_allowed_and_rejected_market_observation_origins(self) -> None:
        for builder in self.MARKET_BUILDERS:
            for origin in (
                DataOrigin.EXCHANGE_OBSERVED,
                DataOrigin.PROVIDER_CALCULATED,
                DataOrigin.SYSTEM_COMPOSITE,
            ):
                with self.subTest(builder=builder.__name__, origin=origin):
                    result = builder(metadata=build_metadata_for_origin(origin))
                    self.assertEqual(result.metadata.record_origin, origin)
            with self.subTest(builder=builder.__name__, origin="provider_reference"):
                with self.assertRaises(ValueError):
                    builder(
                        metadata=build_metadata_for_origin(
                            DataOrigin.PROVIDER_REFERENCE
                        )
                    )

    def test_contract_reference_allowed_and_rejected_origins(self) -> None:
        for origin in (DataOrigin.PROVIDER_REFERENCE, DataOrigin.SYSTEM_COMPOSITE):
            reference = build_option_contract_reference(
                metadata=build_metadata_for_origin(origin)
            )
            self.assertEqual(reference.metadata.record_origin, origin)
        for origin in (
            DataOrigin.EXCHANGE_OBSERVED, DataOrigin.PROVIDER_CALCULATED
        ):
            with self.assertRaises(ValueError):
                build_option_contract_reference(
                    metadata=build_metadata_for_origin(origin)
                )

    def test_locked_source_rules_for_both_quote_types(self) -> None:
        quote_specs = (
            (build_underlying_quote_observation, "bid_price", "ask_price"),
            (build_option_quote_observation, "bid_premium", "ask_premium"),
        )
        for builder, bid_name, ask_name in quote_specs:
            equal = {bid_name: decimal.Decimal("1"),
                     ask_name: decimal.Decimal("1")}
            with self.subTest(builder=builder.__name__, case="one-source"):
                builder(metadata=build_locked_metadata(), **equal)
            with self.subTest(builder=builder.__name__, case="multi-source"):
                builder(metadata=build_locked_metadata(True), **equal)
            with self.subTest(builder=builder.__name__, case="missing-flag"):
                with self.assertRaises(ValueError):
                    builder(**equal)
            with self.subTest(builder=builder.__name__, case="crossed-locked"):
                with self.assertRaises(ValueError):
                    builder(
                        metadata=build_locked_metadata(),
                        **{bid_name: decimal.Decimal("2"),
                           ask_name: decimal.Decimal("1")},
                    )
            with self.subTest(builder=builder.__name__, case="nonlocked-result"):
                builder(
                    metadata=build_locked_metadata(True),
                    **{bid_name: decimal.Decimal("1"),
                       ask_name: decimal.Decimal("2")},
                )


class NoDerivedAnalyticsAndMutationTests(unittest.TestCase):
    RECORDS = (
        UnderlyingQuoteObservation,
        OptionContractReference,
        OptionQuoteObservation,
        OptionVolumeObservation,
        OptionOpenInterestObservation,
    )
    FORBIDDEN = {
        "midpoint", "spread", "relative_spread", "spread_percentage",
        "contract_value", "total_position_value", "minimum_leg_volume",
        "minimum_leg_open_interest", "liquidity", "freshness", "eligibility",
        "score", "state", "recommendation",
    }

    def test_no_derived_fields_or_public_properties(self) -> None:
        for record in self.RECORDS:
            with self.subTest(record=record.__name__):
                field_names = {field.name for field in dataclasses.fields(record)}
                self.assertTrue(field_names.isdisjoint(self.FORBIDDEN))
                self.assertTrue(all(not hasattr(record, name) for name in self.FORBIDDEN))

    def test_builders_are_deterministic_and_repr_has_no_memory_address(self) -> None:
        builders = (
            build_underlying_quote_observation,
            build_option_contract_reference,
            build_option_quote_observation,
            build_option_volume_observation,
            build_option_open_interest_observation,
        )
        for builder in builders:
            with self.subTest(builder=builder.__name__):
                first = builder()
                self.assertEqual(first, builder())
                self.assertNotIn("0x", repr(first))
                hash(first)

    def test_construction_and_repr_do_not_mutate_inputs(self) -> None:
        metadata = build_normalization_metadata()
        underlying = build_underlying_key()
        contract = build_option_contract_key()
        before = (metadata, underlying, contract, repr(metadata), repr(contract))
        quote = build_underlying_quote_observation(
            metadata=metadata, underlying_key=underlying
        )
        option_quote = build_option_quote_observation(
            metadata=metadata, contract_key=contract
        )
        repr(quote)
        repr(option_quote)
        self.assertEqual(before, (metadata, underlying, contract,
                                  repr(metadata), repr(contract)))


class ImportAndDeterminismTests(unittest.TestCase):
    def test_clean_import_has_no_later_layer_or_network_modules(self) -> None:
        script = """
import sys
import convexity_hunter.market_data
blocked = (
    'convexity_hunter.scanner', 'convexity_hunter.report',
    'convexity_hunter.evidence', 'requests', 'urllib.request', 'socket',
)
assert all(name not in sys.modules for name in blocked)
print('clean market-data import passed')
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(ROOT), env=env, text=True, capture_output=True, check=True,
        )
        self.assertEqual(completed.stdout.strip(), "clean market-data import passed")

    def test_fixture_output_is_fixed(self) -> None:
        self.assertEqual(build_source_reference(), build_source_reference())
        self.assertEqual(
            build_normalization_metadata(), build_normalization_metadata()
        )
        self.assertEqual(build_underlying_key(), build_underlying_key())
        self.assertEqual(build_option_contract_key(), build_option_contract_key())


if __name__ == "__main__":
    unittest.main()
