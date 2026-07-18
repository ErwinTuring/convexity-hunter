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
    DividendObservation,
    DividendStatus,
    FreshnessAssessment,
    FreshnessContext,
    FreshnessReasonCode,
    FreshnessStatus,
    MarketPhase,
    MarketDataCategory,
    MarketDataFreshnessPolicy,
    NormalizationMetadata,
    NormalizationQualityFlag,
    OptionContractKey,
    OptionContractReference,
    OptionGreeksObservation,
    OptionImpliedVolatilityObservation,
    OptionOpenInterestObservation,
    OptionQuoteObservation,
    OptionVolumeObservation,
    QuoteScope,
    RateCurvePointObservation,
    SourceQualityFlag,
    SourceReference,
    UnderlyingKey,
    UnderlyingDailyBarObservation,
    UnderlyingQuoteObservation,
    UnderlyingSecurityType,
    assess_market_data_freshness,
)
from tests.market_data_fixtures import (
    EVALUATION_AT,
    NON_UTC_OBSERVED_AT,
    NON_UTC_RETRIEVED_AT,
    NORMALIZED_AT,
    OBSERVED_AT,
    RETRIEVED_AT,
    UTC,
    build_normalization_metadata,
    build_dividend_observation,
    build_freshness_context,
    build_freshness_policy,
    build_option_contract_key,
    build_option_contract_reference,
    build_option_greeks_observation,
    build_option_implied_volatility_observation,
    build_option_open_interest_observation,
    build_option_quote_observation,
    build_option_volume_observation,
    build_rate_curve_point_observation,
    build_source_reference,
    build_underlying_key,
    build_underlying_daily_bar_observation,
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
            "OptionImpliedVolatilityObservation",
            "OptionGreeksObservation",
            "UnderlyingDailyBarObservation",
            "RateCurvePointObservation",
            "DividendObservation",
            "MarketDataCategory",
            "MarketDataFreshnessPolicy",
            "FreshnessContext",
            "FreshnessStatus",
            "FreshnessReasonCode",
            "FreshnessAssessment",
            "assess_market_data_freshness",
        )
        self.assertEqual(market_data.__all__, expected)
        self.assertTrue(all(hasattr(market_data, name) for name in expected))

    def test_later_milestone_types_do_not_exist(self) -> None:
        later_types = (
            "CorrectionSelectionStatus",
            "CorrectionSelectionReasonCode",
            "CorrectionSelection",
            "select_correction_candidate",
            "CalculationQualityFlag",
            "CalculationInputReference",
            "CalculationLineage",
            "canonicalize_lineage_parameters",
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
            OptionImpliedVolatilityObservation: (
                "contract_key", "session_date", "implied_volatility",
                "model_name", "model_version", "rate_input_description",
                "dividend_input_description", "metadata",
            ),
            OptionGreeksObservation: (
                "contract_key", "session_date", "delta", "gamma", "theta",
                "vega", "theta_day_basis", "model_name", "model_version",
                "rate_input_description", "dividend_input_description",
                "metadata",
            ),
            UnderlyingDailyBarObservation: (
                "underlying_key", "session_date", "open_price", "high_price",
                "low_price", "close_price", "adjusted_close_price", "volume",
                "is_session_complete", "adjustment_methodology", "metadata",
            ),
            RateCurvePointObservation: (
                "curve_id", "currency", "tenor_days", "annualized_rate",
                "compounding_convention", "day_count_convention",
                "effective_date", "metadata",
            ),
            DividendObservation: (
                "underlying_key", "dividend_type", "ex_date", "payment_date",
                "cash_amount", "annualized_yield", "currency", "status",
                "metadata",
            ),
            MarketDataFreshnessPolicy: (
                "policy_id", "policy_version", "maximum_quote_age_seconds",
                "maximum_analytics_age_seconds", "maximum_activity_age_seconds",
                "maximum_reference_age_seconds", "maximum_rate_age_seconds",
                "maximum_dividend_age_seconds", "maximum_retrieval_lag_seconds",
                "maximum_source_observation_span_seconds",
                "maximum_cross_record_skew_seconds",
                "maximum_open_interest_session_date_gap_days",
                "maximum_historical_bar_session_date_gap_days",
                "allow_delayed_data", "allow_indicative_data",
                "allow_non_firm_data", "allow_partial_data",
                "allow_assigned_timestamps", "require_regular_session_quotes",
                "require_completed_historical_sessions",
            ),
            FreshnessContext: (
                "evaluation_at", "latest_completed_session_date",
            ),
            FreshnessAssessment: (
                "record_id", "category", "status", "reason_codes",
                "policy_id", "policy_version", "evaluated_at",
                "effective_age_seconds", "oldest_source_age_seconds",
                "maximum_retrieval_lag_seconds_observed",
                "source_observation_span_seconds", "session_date_gap_days",
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
        MarketDataCategory: (
            "quote", "analytics", "activity", "contract_reference",
            "historical_bar", "rate", "dividend",
        ),
        FreshnessStatus: ("fresh", "stale", "ineligible", "unknown"),
        FreshnessReasonCode: (
            "record_normalized_after_evaluation",
            "source_retrieved_after_evaluation",
            "source_observed_after_evaluation",
            "normalization_incomplete", "assigned_timestamp_not_allowed",
            "delayed_data_not_allowed", "indicative_data_not_allowed",
            "non_firm_data_not_allowed", "partial_data_not_allowed",
            "halted_source", "source_observation_span_exceeded",
            "non_regular_session_quote", "historical_session_incomplete",
            "session_date_after_latest_completed_session",
            "unknown_market_phase", "unknown_quote_scope",
            "effective_age_exceeded", "oldest_source_age_exceeded",
            "retrieval_lag_exceeded",
            "open_interest_session_date_gap_exceeded",
            "historical_bar_session_date_gap_exceeded",
            "fresh_within_policy",
        ),
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


class OptionImpliedVolatilityObservationTests(unittest.TestCase):
    def test_valid_normalization_precision_origins_frozen_and_deterministic(self) -> None:
        observation = build_option_implied_volatility_observation(
            implied_volatility=decimal.Decimal("0.2012500"),
            model_name=" Synthetic Model ", model_version=None,
            rate_input_description=" Rate Input ",
            dividend_input_description=" Dividend Input ",
        )
        self.assertEqual(observation.model_name, "Synthetic Model")
        self.assertIsNone(observation.model_version)
        self.assertEqual(observation.rate_input_description, "Rate Input")
        self.assertEqual(observation.implied_volatility.as_tuple().exponent, -7)
        self.assertEqual(observation, build_option_implied_volatility_observation(
            implied_volatility=decimal.Decimal("0.2012500"),
            model_name=" Synthetic Model ", model_version=None,
            rate_input_description=" Rate Input ",
            dividend_input_description=" Dividend Input ",
        ))
        composite = build_option_implied_volatility_observation(
            metadata=build_metadata_for_origin(DataOrigin.SYSTEM_COMPOSITE)
        )
        self.assertEqual(composite.metadata.record_origin, DataOrigin.SYSTEM_COMPOSITE)
        hash(observation)
        with self.assertRaises(FrozenInstanceError):
            observation.model_name = "changed"  # type: ignore[misc]

    def test_invalid_identity_iv_strings_metadata_and_origins(self) -> None:
        cases = (
            ({"contract_key": "contract"}, TypeError),
            ({"session_date": datetime.datetime(2030, 1, 2)}, TypeError),
            ({"session_date": "2030-01-02"}, TypeError),
            ({"implied_volatility": decimal.Decimal("0")}, ValueError),
            ({"implied_volatility": decimal.Decimal("-0.1")}, ValueError),
            ({"metadata": "metadata"}, TypeError),
        )
        for values, error in cases:
            with self.subTest(values=values):
                with self.assertRaises(error):
                    build_option_implied_volatility_observation(**values)
        for value in (1.0, 1, True, "0.2", decimal.Decimal("NaN"),
                      decimal.Decimal("Infinity"), decimal.Decimal("-Infinity")):
            with self.subTest(iv=value):
                with self.assertRaises((TypeError, ValueError)):
                    build_option_implied_volatility_observation(
                        implied_volatility=value
                    )
        for field in (
            "model_name", "rate_input_description", "dividend_input_description"
        ):
            for value in (" ", 1):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        build_option_implied_volatility_observation(**{field: value})
        for value in (" ", 1):
            with self.assertRaises((TypeError, ValueError)):
                build_option_implied_volatility_observation(model_version=value)
        for origin in (DataOrigin.EXCHANGE_OBSERVED, DataOrigin.PROVIDER_REFERENCE):
            with self.assertRaises(ValueError):
                build_option_implied_volatility_observation(
                    metadata=build_metadata_for_origin(origin)
                )


class OptionGreeksObservationTests(unittest.TestCase):
    def test_valid_optional_values_signs_zero_and_origins(self) -> None:
        default = build_option_greeks_observation()
        hash(default)
        for field in ("delta", "gamma", "theta", "vega"):
            values = {name: None for name in ("delta", "gamma", "theta", "vega")}
            values[field] = decimal.Decimal("-0.00" if field != "theta" else "0.00")
            values["theta_day_basis"] = " Calendar Day " if field == "theta" else None
            with self.subTest(field=field):
                observation = build_option_greeks_observation(**values)
                self.assertFalse(getattr(observation, field).is_signed())
                if field == "theta":
                    self.assertEqual(observation.theta_day_basis, "Calendar Day")
        unusual = build_option_greeks_observation(
            delta=decimal.Decimal("2"), gamma=decimal.Decimal("-1"),
            theta=None, vega=decimal.Decimal("-3"), theta_day_basis=None,
            model_version=None,
        )
        self.assertEqual(unusual.delta, decimal.Decimal("2"))
        self.assertIsNone(unusual.model_version)
        composite = build_option_greeks_observation(
            metadata=build_metadata_for_origin(DataOrigin.SYSTEM_COMPOSITE)
        )
        self.assertEqual(composite.metadata.record_origin, DataOrigin.SYSTEM_COMPOSITE)
        with self.assertRaises(FrozenInstanceError):
            default.delta = decimal.Decimal("0")  # type: ignore[misc]

    def test_invalid_greeks_theta_basis_strings_identity_and_origins(self) -> None:
        with self.assertRaises(ValueError):
            build_option_greeks_observation(
                delta=None, gamma=None, theta=None, vega=None,
                theta_day_basis=None,
            )
        for field in ("delta", "gamma", "theta", "vega"):
            for value in (1.0, 1, True, "1", decimal.Decimal("NaN"),
                          decimal.Decimal("Infinity"), decimal.Decimal("-Infinity")):
                values = {field: value}
                if field == "theta":
                    values["theta_day_basis"] = "Calendar Day"
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        build_option_greeks_observation(**values)
        with self.assertRaises((TypeError, ValueError)):
            build_option_greeks_observation(theta=decimal.Decimal("-1"),
                                             theta_day_basis=None)
        with self.assertRaises(ValueError):
            build_option_greeks_observation(theta=None, theta_day_basis="Daily")
        with self.assertRaises(ValueError):
            build_option_greeks_observation(theta=decimal.Decimal("-1"),
                                             theta_day_basis=" ")
        for field in (
            "model_name", "rate_input_description", "dividend_input_description"
        ):
            for value in (" ", 1):
                with self.assertRaises((TypeError, ValueError)):
                    build_option_greeks_observation(**{field: value})
        for values, error in (
            ({"model_version": " "}, ValueError),
            ({"model_version": 1}, TypeError),
            ({"contract_key": "contract"}, TypeError),
            ({"session_date": datetime.datetime(2030, 1, 2)}, TypeError),
            ({"session_date": "2030-01-02"}, TypeError),
            ({"metadata": "metadata"}, TypeError),
        ):
            with self.assertRaises(error):
                build_option_greeks_observation(**values)
        for origin in (DataOrigin.EXCHANGE_OBSERVED, DataOrigin.PROVIDER_REFERENCE):
            with self.assertRaises(ValueError):
                build_option_greeks_observation(
                    metadata=build_metadata_for_origin(origin)
                )


class UnderlyingDailyBarObservationTests(unittest.TestCase):
    def test_valid_variants_precision_origins_frozen_and_adjustment_independence(self) -> None:
        adjusted = build_underlying_daily_bar_observation(
            open_price=decimal.Decimal("498.250000"),
            adjusted_close_price=decimal.Decimal("600.0000"),
        )
        self.assertEqual(adjusted.open_price.as_tuple().exponent, -6)
        self.assertGreater(adjusted.adjusted_close_price, adjusted.high_price)
        raw = build_underlying_daily_bar_observation(
            adjusted_close_price=None, adjustment_methodology=None,
            is_session_complete=False, volume=0,
        )
        self.assertIsNone(raw.adjusted_close_price)
        self.assertFalse(raw.is_session_complete)
        self.assertEqual(raw.volume, 0)
        for origin in (
            DataOrigin.EXCHANGE_OBSERVED, DataOrigin.PROVIDER_CALCULATED,
            DataOrigin.SYSTEM_COMPOSITE,
        ):
            bar = build_underlying_daily_bar_observation(
                metadata=build_metadata_for_origin(origin)
            )
            self.assertEqual(bar.metadata.record_origin, origin)
        hash(adjusted)
        with self.assertRaises(FrozenInstanceError):
            adjusted.volume = 1  # type: ignore[misc]

    def test_invalid_identity_prices_ohlc_adjustment_volume_and_metadata(self) -> None:
        for values, error in (
            ({"underlying_key": "SPY"}, TypeError),
            ({"session_date": datetime.datetime(2030, 1, 2)}, TypeError),
            ({"session_date": "2030-01-02"}, TypeError),
            ({"metadata": "metadata"}, TypeError),
            ({"metadata": build_metadata_for_origin(DataOrigin.PROVIDER_REFERENCE)},
             ValueError),
        ):
            with self.assertRaises(error):
                build_underlying_daily_bar_observation(**values)
        for field in ("open_price", "high_price", "low_price", "close_price"):
            for value in (1.0, 1, True, "1", decimal.Decimal("0"),
                          decimal.Decimal("-1"), decimal.Decimal("NaN"),
                          decimal.Decimal("Infinity"), decimal.Decimal("-Infinity")):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        build_underlying_daily_bar_observation(**{field: value})
        for values in (
            {"low_price": decimal.Decimal("499")},
            {"low_price": decimal.Decimal("502")},
            {"high_price": decimal.Decimal("499")},
            {"high_price": decimal.Decimal("500")},
            {"low_price": decimal.Decimal("503"),
             "high_price": decimal.Decimal("502")},
        ):
            with self.assertRaises(ValueError):
                build_underlying_daily_bar_observation(**values)
        for value in (decimal.Decimal("0"), decimal.Decimal("-1"),
                      decimal.Decimal("NaN"), 1.0, 1, True, "1"):
            with self.assertRaises((TypeError, ValueError)):
                build_underlying_daily_bar_observation(adjusted_close_price=value)
        for values in (
            {"adjusted_close_price": decimal.Decimal("500"),
             "adjustment_methodology": None},
            {"adjusted_close_price": None,
             "adjustment_methodology": "Method"},
            {"adjusted_close_price": decimal.Decimal("500"),
             "adjustment_methodology": " "},
        ):
            with self.assertRaises(ValueError):
                build_underlying_daily_bar_observation(**values)
        for values, error in (
            ({"volume": -1}, ValueError), ({"volume": True}, TypeError),
            ({"volume": 1.0}, TypeError), ({"is_session_complete": 1}, TypeError),
        ):
            with self.assertRaises(error):
                build_underlying_daily_bar_observation(**values)


class RateCurvePointObservationTests(unittest.TestCase):
    def test_valid_rates_normalization_origins_frozen_and_deterministic(self) -> None:
        for rate in (decimal.Decimal("0.01"), decimal.Decimal("0"),
                     decimal.Decimal("-0.01"), decimal.Decimal("-0.000")):
            point = build_rate_curve_point_observation(
                curve_id=" Curve A ", currency=" usd ", annualized_rate=rate,
                compounding_convention=" Continuous ",
                day_count_convention=" Actual/365 ",
            )
            self.assertEqual(point.curve_id, "Curve A")
            self.assertEqual(point.currency, "USD")
            self.assertFalse(point.annualized_rate.is_signed() and
                             point.annualized_rate.is_zero())
        for origin in (
            DataOrigin.PROVIDER_CALCULATED, DataOrigin.PROVIDER_REFERENCE,
            DataOrigin.SYSTEM_COMPOSITE,
        ):
            point = build_rate_curve_point_observation(
                metadata=build_metadata_for_origin(origin)
            )
            self.assertEqual(point.metadata.record_origin, origin)
        point = build_rate_curve_point_observation()
        self.assertEqual(point, build_rate_curve_point_observation())
        hash(point)
        with self.assertRaises(FrozenInstanceError):
            point.tenor_days = 1  # type: ignore[misc]

    def test_invalid_fields_and_origin(self) -> None:
        for field in ("curve_id", "compounding_convention", "day_count_convention"):
            for value in (" ", 1):
                with self.assertRaises((TypeError, ValueError)):
                    build_rate_curve_point_observation(**{field: value})
        for values, error in (
            ({"currency": "EUR"}, ValueError), ({"currency": 1}, TypeError),
            ({"tenor_days": 0}, ValueError), ({"tenor_days": -1}, ValueError),
            ({"tenor_days": True}, TypeError), ({"tenor_days": 1.0}, TypeError),
            ({"effective_date": datetime.datetime(2030, 1, 2)}, TypeError),
            ({"effective_date": "2030-01-02"}, TypeError),
            ({"metadata": "metadata"}, TypeError),
            ({"metadata": build_metadata_for_origin(DataOrigin.EXCHANGE_OBSERVED)},
             ValueError),
        ):
            with self.assertRaises(error):
                build_rate_curve_point_observation(**values)
        for value in (1.0, 1, True, "0.01", decimal.Decimal("NaN"),
                      decimal.Decimal("Infinity"), decimal.Decimal("-Infinity")):
            with self.assertRaises((TypeError, ValueError)):
                build_rate_curve_point_observation(annualized_rate=value)


class DividendObservationTests(unittest.TestCase):
    def test_valid_status_value_combinations_normalization_and_frozen(self) -> None:
        announced = build_dividend_observation(
            dividend_type=" Regular Cash ", currency=" usd ", payment_date=None,
            cash_amount=decimal.Decimal("-0.000"), annualized_yield=None,
        )
        self.assertEqual(announced.dividend_type, "Regular Cash")
        self.assertEqual(announced.currency, "USD")
        self.assertFalse(announced.cash_amount.is_signed())
        yield_only = build_dividend_observation(
            cash_amount=None, annualized_yield=decimal.Decimal("0")
        )
        self.assertIsNone(yield_only.cash_amount)
        both = build_dividend_observation()
        self.assertIsNotNone(both.cash_amount)
        status_origins = (
            (DividendStatus.FORECAST, DataOrigin.PROVIDER_CALCULATED),
            (DividendStatus.ANNOUNCED, DataOrigin.PROVIDER_REFERENCE),
            (DividendStatus.HISTORICAL, DataOrigin.PROVIDER_REFERENCE),
        )
        for status, origin in status_origins:
            observation = build_dividend_observation(
                status=status, metadata=build_metadata_for_origin(origin)
            )
            self.assertEqual(observation.status, status)
            composite = build_dividend_observation(
                status=status,
                metadata=build_metadata_for_origin(DataOrigin.SYSTEM_COMPOSITE),
            )
            self.assertEqual(composite.metadata.record_origin,
                             DataOrigin.SYSTEM_COMPOSITE)
        hash(announced)
        with self.assertRaises(FrozenInstanceError):
            announced.status = DividendStatus.HISTORICAL  # type: ignore[misc]

    def test_invalid_fields_values_and_status_origins(self) -> None:
        for values, error in (
            ({"underlying_key": "SPY"}, TypeError),
            ({"dividend_type": " "}, ValueError),
            ({"dividend_type": 1}, TypeError),
            ({"ex_date": datetime.datetime(2030, 1, 2)}, TypeError),
            ({"payment_date": datetime.datetime(2030, 1, 2)}, TypeError),
            ({"ex_date": "2030-01-02"}, TypeError),
            ({"payment_date": "2030-03-01"}, TypeError),
            ({"cash_amount": None, "annualized_yield": None}, ValueError),
            ({"currency": "EUR"}, ValueError),
            ({"status": "announced"}, TypeError),
            ({"metadata": "metadata"}, TypeError),
        ):
            with self.assertRaises(error):
                build_dividend_observation(**values)
        for field in ("cash_amount", "annualized_yield"):
            for value in (decimal.Decimal("-0.01"), 1.0, 1, True, "0.01",
                          decimal.Decimal("NaN"), decimal.Decimal("Infinity"),
                          decimal.Decimal("-Infinity")):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        build_dividend_observation(**{field: value})
        rejected = (
            (DividendStatus.FORECAST, DataOrigin.EXCHANGE_OBSERVED),
            (DividendStatus.FORECAST, DataOrigin.PROVIDER_REFERENCE),
            (DividendStatus.ANNOUNCED, DataOrigin.EXCHANGE_OBSERVED),
            (DividendStatus.ANNOUNCED, DataOrigin.PROVIDER_CALCULATED),
            (DividendStatus.HISTORICAL, DataOrigin.EXCHANGE_OBSERVED),
            (DividendStatus.HISTORICAL, DataOrigin.PROVIDER_CALCULATED),
        )
        for status, origin in rejected:
            with self.subTest(status=status, origin=origin):
                with self.assertRaises(ValueError):
                    build_dividend_observation(
                        status=status, metadata=build_metadata_for_origin(origin)
                    )


class Milestone3A3OriginBoundaryTests(unittest.TestCase):
    def test_every_origin_combination(self) -> None:
        all_origins = tuple(DataOrigin)
        cases = (
            (build_option_implied_volatility_observation,
             {DataOrigin.PROVIDER_CALCULATED, DataOrigin.SYSTEM_COMPOSITE}),
            (build_option_greeks_observation,
             {DataOrigin.PROVIDER_CALCULATED, DataOrigin.SYSTEM_COMPOSITE}),
            (build_underlying_daily_bar_observation,
             {DataOrigin.EXCHANGE_OBSERVED, DataOrigin.PROVIDER_CALCULATED,
              DataOrigin.SYSTEM_COMPOSITE}),
            (build_rate_curve_point_observation,
             {DataOrigin.PROVIDER_CALCULATED, DataOrigin.PROVIDER_REFERENCE,
              DataOrigin.SYSTEM_COMPOSITE}),
        )
        for builder, allowed in cases:
            for origin in all_origins:
                with self.subTest(builder=builder.__name__, origin=origin):
                    if origin in allowed:
                        builder(metadata=build_metadata_for_origin(origin))
                    else:
                        with self.assertRaises(ValueError):
                            builder(metadata=build_metadata_for_origin(origin))
        dividend_allowed = {
            DividendStatus.FORECAST: {
                DataOrigin.PROVIDER_CALCULATED, DataOrigin.SYSTEM_COMPOSITE,
            },
            DividendStatus.ANNOUNCED: {
                DataOrigin.PROVIDER_REFERENCE, DataOrigin.SYSTEM_COMPOSITE,
            },
            DividendStatus.HISTORICAL: {
                DataOrigin.PROVIDER_REFERENCE, DataOrigin.SYSTEM_COMPOSITE,
            },
        }
        for status, allowed in dividend_allowed.items():
            for origin in all_origins:
                with self.subTest(status=status, origin=origin):
                    if origin in allowed:
                        build_dividend_observation(
                            status=status, metadata=build_metadata_for_origin(origin)
                        )
                    else:
                        with self.assertRaises(ValueError):
                            build_dividend_observation(
                                status=status,
                                metadata=build_metadata_for_origin(origin),
                            )


class NoDerivedAnalyticsAndMutationTests(unittest.TestCase):
    RECORDS = (
        UnderlyingQuoteObservation,
        OptionContractReference,
        OptionQuoteObservation,
        OptionVolumeObservation,
        OptionOpenInterestObservation,
        OptionImpliedVolatilityObservation,
        OptionGreeksObservation,
        UnderlyingDailyBarObservation,
        RateCurvePointObservation,
        DividendObservation,
    )
    FORBIDDEN = {
        "midpoint", "spread", "relative_spread", "spread_percentage",
        "contract_value", "total_position_value", "minimum_leg_volume",
        "minimum_leg_open_interest", "liquidity", "freshness", "eligibility",
        "score", "state", "recommendation", "atm_status", "iv_percentile",
        "historical_median", "realized_volatility", "skew", "curvature",
        "theoretical_price", "discount_factor", "forward_rate",
        "adjusted_return", "simple_return", "log_return", "return",
        "dividend_growth", "dividend_present_value",
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
            build_option_implied_volatility_observation,
            build_option_greeks_observation,
            build_underlying_daily_bar_observation,
            build_rate_curve_point_observation,
            build_dividend_observation,
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
        iv_metadata = build_metadata_for_origin(DataOrigin.PROVIDER_CALCULATED)
        reference_metadata = build_metadata_for_origin(DataOrigin.PROVIDER_REFERENCE)
        iv = build_option_implied_volatility_observation(
            metadata=iv_metadata, contract_key=contract
        )
        bar = build_underlying_daily_bar_observation(
            metadata=metadata, underlying_key=underlying
        )
        dividend = build_dividend_observation(
            metadata=reference_metadata, underlying_key=underlying
        )
        repr(quote)
        repr(option_quote)
        repr(iv)
        repr(bar)
        repr(dividend)
        self.assertEqual(before, (metadata, underlying, contract,
                                  repr(metadata), repr(contract)))


def freshness_assessment_values(**overrides: object) -> dict:
    """Return direct-construction values for a synthetic fresh assessment."""

    values = {
        "record_id": " record-1 ",
        "category": MarketDataCategory.QUOTE,
        "status": FreshnessStatus.FRESH,
        "reason_codes": (FreshnessReasonCode.FRESH_WITHIN_POLICY,),
        "policy_id": " policy-1 ",
        "policy_version": " v1 ",
        "evaluated_at": EVALUATION_AT,
        "effective_age_seconds": decimal.Decimal("1.000001"),
        "oldest_source_age_seconds": decimal.Decimal("1.000002"),
        "maximum_retrieval_lag_seconds_observed": decimal.Decimal("0.000001"),
        "source_observation_span_seconds": decimal.Decimal("0.000001"),
        "session_date_gap_days": None,
    }
    values.update(overrides)
    return values


class FreshnessPolicyAndContextTests(unittest.TestCase):
    THRESHOLDS = (
        "maximum_quote_age_seconds",
        "maximum_analytics_age_seconds",
        "maximum_activity_age_seconds",
        "maximum_reference_age_seconds",
        "maximum_rate_age_seconds",
        "maximum_dividend_age_seconds",
        "maximum_retrieval_lag_seconds",
        "maximum_source_observation_span_seconds",
        "maximum_cross_record_skew_seconds",
        "maximum_open_interest_session_date_gap_days",
        "maximum_historical_bar_session_date_gap_days",
    )
    SWITCHES = (
        "allow_delayed_data", "allow_indicative_data", "allow_non_firm_data",
        "allow_partial_data", "allow_assigned_timestamps",
        "require_regular_session_quotes",
        "require_completed_historical_sessions",
    )

    def test_policy_normalizes_identity_and_is_frozen_hashable(self) -> None:
        policy = build_freshness_policy(policy_id=" policy ", policy_version=" v1 ")
        self.assertEqual((policy.policy_id, policy.policy_version), ("policy", "v1"))
        hash(policy)
        with self.assertRaises(FrozenInstanceError):
            policy.policy_id = "changed"  # type: ignore[misc]

    def test_policy_rejects_invalid_identity_thresholds_and_switches(self) -> None:
        for name in ("policy_id", "policy_version"):
            for value, error in ((" ", ValueError), (1, TypeError)):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(error):
                        build_freshness_policy(**{name: value})
        for name in self.THRESHOLDS:
            for value, error in ((True, TypeError), (1.5, TypeError), (-1, ValueError)):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(error):
                        build_freshness_policy(**{name: value})
        for name in self.SWITCHES:
            for value in (0, 1, "true", None):
                with self.subTest(name=name, value=value):
                    with self.assertRaises(TypeError):
                        build_freshness_policy(**{name: value})

    def test_context_normalizes_utc_and_is_frozen_hashable(self) -> None:
        non_utc = datetime.datetime(
            2030, 1, 2, 10, 31,
            tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
        )
        context = build_freshness_context(evaluation_at=non_utc)
        self.assertEqual(context.evaluation_at, EVALUATION_AT)
        self.assertIs(context.evaluation_at.tzinfo, UTC)
        hash(context)
        with self.assertRaises(FrozenInstanceError):
            context.evaluation_at = EVALUATION_AT  # type: ignore[misc]

    def test_context_rejects_naive_time_and_non_date(self) -> None:
        with self.assertRaises(ValueError):
            build_freshness_context(evaluation_at=datetime.datetime(2030, 1, 2))
        for value in (
            datetime.datetime(2030, 1, 2, tzinfo=UTC), "2030-01-02", None,
        ):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    build_freshness_context(latest_completed_session_date=value)

    def test_cross_record_skew_is_stored_but_unused(self) -> None:
        record = build_underlying_quote_observation()
        context = build_freshness_context()
        first = assess_market_data_freshness(
            record,
            build_freshness_policy(maximum_cross_record_skew_seconds=0),
            context,
        )
        second = assess_market_data_freshness(
            record,
            build_freshness_policy(maximum_cross_record_skew_seconds=999999),
            context,
        )
        self.assertEqual(
            dataclasses.replace(first, policy_id=second.policy_id), second
        )


class FreshnessCategoryAndMetricTests(unittest.TestCase):
    def test_exact_ten_record_category_mapping(self) -> None:
        expected = (
            (build_underlying_quote_observation, MarketDataCategory.QUOTE),
            (build_option_quote_observation, MarketDataCategory.QUOTE),
            (build_option_implied_volatility_observation,
             MarketDataCategory.ANALYTICS),
            (build_option_greeks_observation, MarketDataCategory.ANALYTICS),
            (build_option_volume_observation, MarketDataCategory.ACTIVITY),
            (build_option_open_interest_observation, MarketDataCategory.ACTIVITY),
            (build_option_contract_reference,
             MarketDataCategory.CONTRACT_REFERENCE),
            (build_underlying_daily_bar_observation,
             MarketDataCategory.HISTORICAL_BAR),
            (build_rate_curve_point_observation, MarketDataCategory.RATE),
            (build_dividend_observation, MarketDataCategory.DIVIDEND),
        )
        categories = []
        for builder, category in expected:
            with self.subTest(builder=builder.__name__):
                result = assess_market_data_freshness(
                    builder(), build_freshness_policy(), build_freshness_context()
                )
                self.assertIs(result.category, category)
                categories.append(result.category)
        self.assertEqual(len(expected), 10)
        self.assertEqual(set(categories), set(MarketDataCategory))

    def test_unsupported_excluded_and_subclass_types_raise(self) -> None:
        excluded = (
            object(), build_source_reference(), build_normalization_metadata(),
            build_underlying_key(), build_option_contract_key(),
        )
        policy = build_freshness_policy()
        context = build_freshness_context()
        for value in excluded:
            with self.subTest(type=type(value).__name__):
                with self.assertRaises(TypeError):
                    assess_market_data_freshness(value, policy, context)

        class QuoteSubclass(UnderlyingQuoteObservation):
            pass

        base = build_underlying_quote_observation()
        subclass = QuoteSubclass(**{
            field.name: getattr(base, field.name) for field in dataclasses.fields(base)
        })
        with self.assertRaises(TypeError):
            assess_market_data_freshness(subclass, policy, context)

    def test_evaluator_validates_policy_and_context_types(self) -> None:
        quote = build_underlying_quote_observation()
        with self.assertRaises(TypeError):
            assess_market_data_freshness(quote, object(), build_freshness_context())  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            assess_market_data_freshness(quote, build_freshness_policy(), object())  # type: ignore[arg-type]

    def test_exact_positive_zero_negative_and_microsecond_metrics(self) -> None:
        evaluation = EVALUATION_AT
        cases = (
            (evaluation - datetime.timedelta(seconds=1, microseconds=1),
             decimal.Decimal("1.000001")),
            (evaluation, decimal.Decimal("0")),
            (evaluation + datetime.timedelta(microseconds=1),
             decimal.Decimal("-0.000001")),
        )
        for observed_at, expected_age in cases:
            retrieved_at = observed_at + datetime.timedelta(microseconds=1)
            normalized_at = max(retrieved_at, evaluation - datetime.timedelta(seconds=1))
            source = build_source_reference(
                observed_at=observed_at, retrieved_at=retrieved_at,
            )
            metadata = build_normalization_metadata(
                [source], normalized_at=normalized_at,
            )
            result = assess_market_data_freshness(
                build_underlying_quote_observation(metadata=metadata),
                build_freshness_policy(maximum_quote_age_seconds=2),
                build_freshness_context(),
            )
            with self.subTest(expected_age=expected_age):
                self.assertEqual(result.effective_age_seconds, expected_age)
                self.assertEqual(result.oldest_source_age_seconds, expected_age)
                self.assertEqual(
                    result.maximum_retrieval_lag_seconds_observed,
                    decimal.Decimal("0.000001"),
                )

    def test_age_threshold_is_inclusive_and_microsecond_over_is_stale(self) -> None:
        at_limit = assess_market_data_freshness(
            build_underlying_quote_observation(), build_freshness_policy(),
            build_freshness_context(),
        )
        self.assertIs(at_limit.status, FreshnessStatus.FRESH)
        observed_at = OBSERVED_AT - datetime.timedelta(microseconds=1)
        source = build_source_reference(
            observed_at=observed_at,
            retrieved_at=RETRIEVED_AT - datetime.timedelta(microseconds=1),
        )
        metadata = build_normalization_metadata([source])
        over = assess_market_data_freshness(
            build_underlying_quote_observation(metadata=metadata),
            build_freshness_policy(), build_freshness_context(),
        )
        self.assertIs(over.status, FreshnessStatus.STALE)
        self.assertIn(FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,
                      over.reason_codes)


class DecimalContextIndependenceTests(unittest.TestCase):
    def test_metrics_and_status_are_independent_of_decimal_context(self) -> None:
        evaluation = EVALUATION_AT

        def single_source_quote(
            observed_at: datetime.datetime,
            retrieved_at: datetime.datetime,
            normalized_at: datetime.datetime,
        ) -> UnderlyingQuoteObservation:
            source = build_source_reference(
                observed_at=observed_at, retrieved_at=retrieved_at,
            )
            return build_underlying_quote_observation(
                metadata=build_normalization_metadata(
                    [source], normalized_at=normalized_at,
                )
            )

        age_over = single_source_quote(
            evaluation - datetime.timedelta(seconds=1, microseconds=1),
            evaluation - datetime.timedelta(seconds=1),
            evaluation,
        )
        positive_microsecond = single_source_quote(
            evaluation - datetime.timedelta(microseconds=1),
            evaluation - datetime.timedelta(microseconds=1),
            evaluation,
        )
        negative_microsecond = single_source_quote(
            evaluation + datetime.timedelta(microseconds=1),
            evaluation + datetime.timedelta(microseconds=1),
            evaluation + datetime.timedelta(microseconds=1),
        )
        negative_normalized_day = single_source_quote(
            evaluation + datetime.timedelta(days=1, microseconds=1),
            evaluation + datetime.timedelta(days=1, microseconds=1),
            evaluation + datetime.timedelta(days=1, microseconds=1),
        )

        first_observed = evaluation - datetime.timedelta(seconds=2)
        second_observed = first_observed + datetime.timedelta(
            seconds=1, microseconds=1
        )
        first = build_source_reference(
            source_id="context-span-a", observed_at=first_observed,
            retrieved_at=first_observed,
        )
        second = build_source_reference(
            source_id="context-span-b", provider_record_id="context-span-b",
            observed_at=second_observed, retrieved_at=second_observed,
        )
        span_quote = build_underlying_quote_observation(
            metadata=build_normalization_metadata(
                [first, second], effective_observed_at=second_observed,
                normalized_at=evaluation,
            )
        )

        lag_observed = evaluation - datetime.timedelta(seconds=2)
        lag_retrieved = lag_observed + datetime.timedelta(
            seconds=1, microseconds=1
        )
        lag_quote = single_source_quote(
            lag_observed, lag_retrieved, evaluation,
        )

        cases = (
            (age_over, build_freshness_policy(maximum_quote_age_seconds=1)),
            (positive_microsecond,
             build_freshness_policy(maximum_quote_age_seconds=1)),
            (negative_microsecond,
             build_freshness_policy(maximum_quote_age_seconds=1)),
            (negative_normalized_day,
             build_freshness_policy(maximum_quote_age_seconds=1)),
            (span_quote, build_freshness_policy(
                maximum_quote_age_seconds=10,
                maximum_source_observation_span_seconds=1,
            )),
            (lag_quote, build_freshness_policy(
                maximum_quote_age_seconds=10,
                maximum_retrieval_lag_seconds=1,
            )),
        )
        settings = (
            (1, decimal.ROUND_DOWN),
            (3, decimal.ROUND_UP),
            (6, decimal.ROUND_HALF_EVEN),
            (28, decimal.ROUND_FLOOR),
        )
        results = []
        original_context = decimal.getcontext()
        original_settings = (
            original_context.prec, original_context.rounding,
            original_context.Emin, original_context.Emax,
            original_context.capitals, original_context.clamp,
            original_context.flags.copy(), original_context.traps.copy(),
        )
        for precision, rounding in settings:
            with decimal.localcontext() as context:
                context.prec = precision
                context.rounding = rounding
                results.append(tuple(
                    assess_market_data_freshness(
                        record, policy, build_freshness_context()
                    )
                    for record, policy in cases
                ))
        restored_context = decimal.getcontext()
        self.assertIs(restored_context, original_context)
        self.assertEqual((
            restored_context.prec, restored_context.rounding,
            restored_context.Emin, restored_context.Emax,
            restored_context.capitals, restored_context.clamp,
            restored_context.flags.copy(), restored_context.traps.copy(),
        ), original_settings)
        self.assertTrue(all(result == results[0] for result in results[1:]))

        baseline = results[0]
        self.assertIs(baseline[0].status, FreshnessStatus.STALE)
        self.assertEqual(baseline[0].effective_age_seconds,
                         decimal.Decimal("1.000001"))
        self.assertEqual(baseline[1].effective_age_seconds,
                         decimal.Decimal("0.000001"))
        self.assertEqual(baseline[2].effective_age_seconds,
                         decimal.Decimal("-0.000001"))
        self.assertEqual(baseline[3].effective_age_seconds,
                         decimal.Decimal("-86400.000001"))
        self.assertEqual(baseline[4].source_observation_span_seconds,
                         decimal.Decimal("1.000001"))
        self.assertEqual(
            baseline[5].maximum_retrieval_lag_seconds_observed,
            decimal.Decimal("1.000001"),
        )


class FreshnessCategoryThresholdTests(unittest.TestCase):
    THRESHOLD_FIELDS = (
        "maximum_quote_age_seconds",
        "maximum_analytics_age_seconds",
        "maximum_activity_age_seconds",
        "maximum_reference_age_seconds",
        "maximum_rate_age_seconds",
        "maximum_dividend_age_seconds",
    )
    CASES = (
        (build_underlying_quote_observation, "maximum_quote_age_seconds"),
        (build_option_implied_volatility_observation,
         "maximum_analytics_age_seconds"),
        (build_option_volume_observation, "maximum_activity_age_seconds"),
        (build_option_contract_reference, "maximum_reference_age_seconds"),
        (build_rate_curve_point_observation, "maximum_rate_age_seconds"),
        (build_dividend_observation, "maximum_dividend_age_seconds"),
    )

    def _sentinel_thresholds(self) -> dict:
        return {
            name: 1000 + index
            for index, name in enumerate(self.THRESHOLD_FIELDS, start=1)
        }

    def test_each_category_uses_only_its_distinct_age_threshold(self) -> None:
        age_reasons = {
            FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,
            FreshnessReasonCode.OLDEST_SOURCE_AGE_EXCEEDED,
        }
        for builder, intended_field in self.CASES:
            stale_thresholds = self._sentinel_thresholds()
            stale_thresholds[intended_field] = 59
            stale = assess_market_data_freshness(
                builder(), build_freshness_policy(**stale_thresholds),
                build_freshness_context(),
            )
            with self.subTest(builder=builder.__name__, boundary="over"):
                self.assertTrue(age_reasons.issubset(stale.reason_codes))

            equal_thresholds = self._sentinel_thresholds()
            equal_thresholds[intended_field] = 60
            equal = assess_market_data_freshness(
                builder(), build_freshness_policy(**equal_thresholds),
                build_freshness_context(),
            )
            with self.subTest(builder=builder.__name__, boundary="equal"):
                self.assertTrue(age_reasons.isdisjoint(equal.reason_codes))

    def test_historical_bar_ignores_age_fields_but_not_source_rules(self) -> None:
        first = build_source_reference(source_id="bar-source-a")
        second_observed = OBSERVED_AT + datetime.timedelta(
            seconds=2, microseconds=1
        )
        second = build_source_reference(
            source_id="bar-source-b", provider_record_id="bar-source-b",
            observed_at=second_observed,
            retrieved_at=second_observed + datetime.timedelta(microseconds=1),
        )
        metadata = build_normalization_metadata(
            [first, second], effective_observed_at=second_observed,
            normalized_at=second.retrieved_at,
        )
        policy_values = {name: 0 for name in self.THRESHOLD_FIELDS}
        result = assess_market_data_freshness(
            build_underlying_daily_bar_observation(metadata=metadata),
            build_freshness_policy(
                **policy_values,
                maximum_retrieval_lag_seconds=0,
                maximum_source_observation_span_seconds=0,
            ),
            build_freshness_context(),
        )
        self.assertNotIn(FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,
                         result.reason_codes)
        self.assertNotIn(FreshnessReasonCode.OLDEST_SOURCE_AGE_EXCEEDED,
                         result.reason_codes)
        self.assertIn(FreshnessReasonCode.RETRIEVAL_LAG_EXCEEDED,
                      result.reason_codes)
        self.assertIn(FreshnessReasonCode.SOURCE_OBSERVATION_SPAN_EXCEEDED,
                      result.reason_codes)


class FreshnessSourceAndReasonTests(unittest.TestCase):
    def _quote_with_flags(
        self, flags: tuple, *, delayed: bool = False
    ) -> UnderlyingQuoteObservation:
        source = build_source_reference(
            quality_flags=flags, is_delayed=delayed,
            declared_delay_seconds=15 if delayed else None,
        )
        return build_underlying_quote_observation(
            metadata=build_normalization_metadata([source])
        )

    def test_normalization_and_source_quality_reasons(self) -> None:
        cases = (
            (
                build_underlying_quote_observation(metadata=build_normalization_metadata(
                    quality_flags=(NormalizationQualityFlag.INCOMPLETE,))),
                build_freshness_policy(),
                FreshnessReasonCode.NORMALIZATION_INCOMPLETE,
            ),
            (
                build_underlying_quote_observation(metadata=build_normalization_metadata(
                    quality_flags=(NormalizationQualityFlag.TIMESTAMP_ASSIGNED,))),
                build_freshness_policy(),
                FreshnessReasonCode.ASSIGNED_TIMESTAMP_NOT_ALLOWED,
            ),
            (self._quote_with_flags((SourceQualityFlag.DELAYED,), delayed=True),
             build_freshness_policy(),
             FreshnessReasonCode.DELAYED_DATA_NOT_ALLOWED),
            (self._quote_with_flags((SourceQualityFlag.INDICATIVE,)),
             build_freshness_policy(),
             FreshnessReasonCode.INDICATIVE_DATA_NOT_ALLOWED),
            (self._quote_with_flags((SourceQualityFlag.NON_FIRM,)),
             build_freshness_policy(),
             FreshnessReasonCode.NON_FIRM_DATA_NOT_ALLOWED),
            (self._quote_with_flags((SourceQualityFlag.PARTIAL,)),
             build_freshness_policy(),
             FreshnessReasonCode.PARTIAL_DATA_NOT_ALLOWED),
        )
        for record, policy, reason in cases:
            with self.subTest(reason=reason.value):
                result = assess_market_data_freshness(
                    record, policy, build_freshness_context()
                )
                self.assertIn(reason, result.reason_codes)
                self.assertIs(result.status, FreshnessStatus.INELIGIBLE)

    def test_allowed_quality_switches_suppress_only_policy_reasons(self) -> None:
        record = self._quote_with_flags(
            (SourceQualityFlag.DELAYED, SourceQualityFlag.INDICATIVE,
             SourceQualityFlag.NON_FIRM, SourceQualityFlag.PARTIAL), delayed=True,
        )
        result = assess_market_data_freshness(
            record,
            build_freshness_policy(
                allow_delayed_data=True, allow_indicative_data=True,
                allow_non_firm_data=True, allow_partial_data=True,
            ),
            build_freshness_context(),
        )
        self.assertEqual(result.reason_codes,
                         (FreshnessReasonCode.FRESH_WITHIN_POLICY,))

        assigned = build_underlying_quote_observation(
            metadata=build_normalization_metadata(
                quality_flags=(NormalizationQualityFlag.TIMESTAMP_ASSIGNED,)
            )
        )
        assigned_result = assess_market_data_freshness(
            assigned, build_freshness_policy(allow_assigned_timestamps=True),
            build_freshness_context(),
        )
        self.assertEqual(assigned_result.reason_codes,
                         (FreshnessReasonCode.FRESH_WITHIN_POLICY,))

    def test_all_chronology_reasons_are_collected(self) -> None:
        observed = EVALUATION_AT + datetime.timedelta(seconds=1)
        retrieved = EVALUATION_AT + datetime.timedelta(seconds=2)
        source = build_source_reference(observed_at=observed, retrieved_at=retrieved)
        metadata = build_normalization_metadata(
            [source], normalized_at=EVALUATION_AT + datetime.timedelta(seconds=3)
        )
        result = assess_market_data_freshness(
            build_underlying_quote_observation(metadata=metadata),
            build_freshness_policy(maximum_quote_age_seconds=0),
            build_freshness_context(),
        )
        self.assertEqual(result.reason_codes[:3], (
            FreshnessReasonCode.RECORD_NORMALIZED_AFTER_EVALUATION,
            FreshnessReasonCode.SOURCE_RETRIEVED_AFTER_EVALUATION,
            FreshnessReasonCode.SOURCE_OBSERVED_AFTER_EVALUATION,
        ))
        self.assertEqual(result.effective_age_seconds, decimal.Decimal("-1"))

    def test_normalized_after_evaluation_can_apply_independently(self) -> None:
        metadata = build_normalization_metadata(
            normalized_at=EVALUATION_AT + datetime.timedelta(microseconds=1)
        )
        result = assess_market_data_freshness(
            build_underlying_quote_observation(metadata=metadata),
            build_freshness_policy(), build_freshness_context(),
        )
        self.assertIn(FreshnessReasonCode.RECORD_NORMALIZED_AFTER_EVALUATION,
                      result.reason_codes)

    def test_every_source_age_lag_quality_and_span_participates(self) -> None:
        old_observed = EVALUATION_AT - datetime.timedelta(seconds=70)
        old = build_source_reference(
            source_id="old", observed_at=old_observed,
            retrieved_at=old_observed + datetime.timedelta(seconds=6),
            quality_flags=(SourceQualityFlag.INDICATIVE,),
        )
        recent_observed = EVALUATION_AT - datetime.timedelta(seconds=10)
        recent = build_source_reference(
            source_id="recent", provider_record_id="record-2",
            observed_at=recent_observed,
            retrieved_at=recent_observed + datetime.timedelta(seconds=1),
        )
        metadata = build_normalization_metadata(
            [old, recent], effective_observed_at=recent_observed,
            normalized_at=EVALUATION_AT - datetime.timedelta(seconds=1),
        )
        before = (metadata, metadata.source_references,
                  tuple(source.quality_flags for source in metadata.source_references))
        result = assess_market_data_freshness(
            build_underlying_quote_observation(metadata=metadata),
            build_freshness_policy(), build_freshness_context(),
        )
        self.assertEqual(result.effective_age_seconds, decimal.Decimal("10"))
        self.assertEqual(result.oldest_source_age_seconds, decimal.Decimal("70"))
        self.assertEqual(result.maximum_retrieval_lag_seconds_observed,
                         decimal.Decimal("6"))
        self.assertEqual(result.source_observation_span_seconds,
                         decimal.Decimal("60"))
        for reason in (
            FreshnessReasonCode.INDICATIVE_DATA_NOT_ALLOWED,
            FreshnessReasonCode.SOURCE_OBSERVATION_SPAN_EXCEEDED,
            FreshnessReasonCode.OLDEST_SOURCE_AGE_EXCEEDED,
            FreshnessReasonCode.RETRIEVAL_LAG_EXCEEDED,
        ):
            self.assertIn(reason, result.reason_codes)
        self.assertEqual(before, (
            metadata, metadata.source_references,
            tuple(source.quality_flags for source in metadata.source_references),
        ))

    def test_source_span_threshold_is_inclusive(self) -> None:
        first = build_source_reference(source_id="a")
        second = build_source_reference(
            source_id="b", provider_record_id="record-b",
            observed_at=OBSERVED_AT + datetime.timedelta(seconds=2),
            retrieved_at=RETRIEVED_AT + datetime.timedelta(seconds=1),
        )
        metadata = build_normalization_metadata(
            [first, second], effective_observed_at=second.observed_at,
        )
        result = assess_market_data_freshness(
            build_underlying_quote_observation(metadata=metadata),
            build_freshness_policy(), build_freshness_context(),
        )
        self.assertNotIn(FreshnessReasonCode.SOURCE_OBSERVATION_SPAN_EXCEEDED,
                         result.reason_codes)


class FreshnessCategorySpecificTests(unittest.TestCase):
    def test_halted_applies_only_to_quote_and_analytics(self) -> None:
        builders = (
            (build_underlying_quote_observation, True),
            (build_option_quote_observation, True),
            (build_option_implied_volatility_observation, True),
            (build_option_greeks_observation, True),
            (build_option_volume_observation, False),
            (build_option_open_interest_observation, False),
            (build_option_contract_reference, False),
            (build_underlying_daily_bar_observation, False),
            (build_rate_curve_point_observation, False),
            (build_dividend_observation, False),
        )
        for builder, expected in builders:
            base = builder()
            source = dataclasses.replace(
                base.metadata.source_references[0],
                quality_flags=(SourceQualityFlag.HALTED,),
            )
            metadata = dataclasses.replace(base.metadata, source_references=(source,))
            result = assess_market_data_freshness(
                dataclasses.replace(base, metadata=metadata),
                build_freshness_policy(), build_freshness_context(),
            )
            with self.subTest(builder=builder.__name__):
                self.assertEqual(
                    FreshnessReasonCode.HALTED_SOURCE in result.reason_codes,
                    expected,
                )

    def test_quote_unknowns_regular_requirement_and_after_hours_independence(self) -> None:
        unknown = assess_market_data_freshness(
            build_underlying_quote_observation(
                market_phase=MarketPhase.UNKNOWN, quote_scope=QuoteScope.UNKNOWN,
            ),
            build_freshness_policy(require_regular_session_quotes=False),
            build_freshness_context(),
        )
        self.assertIs(unknown.status, FreshnessStatus.UNKNOWN)
        self.assertIn(FreshnessReasonCode.UNKNOWN_MARKET_PHASE,
                      unknown.reason_codes)
        self.assertIn(FreshnessReasonCode.UNKNOWN_QUOTE_SCOPE,
                      unknown.reason_codes)
        required = assess_market_data_freshness(
            build_underlying_quote_observation(market_phase=MarketPhase.CLOSED),
            build_freshness_policy(), build_freshness_context(),
        )
        self.assertIn(FreshnessReasonCode.NON_REGULAR_SESSION_QUOTE,
                      required.reason_codes)
        after_hours_source = build_source_reference(
            quality_flags=(SourceQualityFlag.AFTER_HOURS,)
        )
        independent = assess_market_data_freshness(
            build_underlying_quote_observation(
                metadata=build_normalization_metadata([after_hours_source])
            ), build_freshness_policy(), build_freshness_context(),
        )
        self.assertIs(independent.status, FreshnessStatus.FRESH)

    def test_historical_bar_date_gap_rules(self) -> None:
        context = build_freshness_context()
        cases = (
            (build_underlying_daily_bar_observation(), build_freshness_policy(),
             0, FreshnessStatus.FRESH, None),
            (build_underlying_daily_bar_observation(
                session_date=datetime.date(2029, 12, 27)),
             build_freshness_policy(), 6, FreshnessStatus.STALE,
             FreshnessReasonCode.HISTORICAL_BAR_SESSION_DATE_GAP_EXCEEDED),
            (build_underlying_daily_bar_observation(
                session_date=datetime.date(2030, 1, 3)),
             build_freshness_policy(), -1, FreshnessStatus.INELIGIBLE,
             FreshnessReasonCode.SESSION_DATE_AFTER_LATEST_COMPLETED_SESSION),
            (build_underlying_daily_bar_observation(is_session_complete=False),
             build_freshness_policy(), None, FreshnessStatus.INELIGIBLE,
             FreshnessReasonCode.HISTORICAL_SESSION_INCOMPLETE),
            (build_underlying_daily_bar_observation(is_session_complete=False),
             build_freshness_policy(require_completed_historical_sessions=False),
             None, FreshnessStatus.FRESH, None),
        )
        for record, policy, gap, status, reason in cases:
            result = assess_market_data_freshness(record, policy, context)
            with self.subTest(gap=gap, status=status.value):
                self.assertEqual(result.session_date_gap_days, gap)
                self.assertIs(result.status, status)
                if reason is not None:
                    self.assertIn(reason, result.reason_codes)

    def test_future_incomplete_bar_has_no_date_gap_or_future_reason(self) -> None:
        future_incomplete = build_underlying_daily_bar_observation(
            session_date=datetime.date(2030, 1, 3),
            is_session_complete=False,
        )
        stale_gap_reason = (
            FreshnessReasonCode.HISTORICAL_BAR_SESSION_DATE_GAP_EXCEEDED
        )
        future_reason = (
            FreshnessReasonCode.SESSION_DATE_AFTER_LATEST_COMPLETED_SESSION
        )

        required = assess_market_data_freshness(
            future_incomplete, build_freshness_policy(
                require_completed_historical_sessions=True,
                maximum_historical_bar_session_date_gap_days=0,
            ), build_freshness_context(),
        )
        self.assertIsNone(required.session_date_gap_days)
        self.assertIn(FreshnessReasonCode.HISTORICAL_SESSION_INCOMPLETE,
                      required.reason_codes)
        self.assertNotIn(future_reason, required.reason_codes)
        self.assertNotIn(stale_gap_reason, required.reason_codes)

        permitted = assess_market_data_freshness(
            future_incomplete, build_freshness_policy(
                require_completed_historical_sessions=False,
                maximum_historical_bar_session_date_gap_days=0,
            ), build_freshness_context(),
        )
        self.assertIsNone(permitted.session_date_gap_days)
        self.assertNotIn(FreshnessReasonCode.HISTORICAL_SESSION_INCOMPLETE,
                         permitted.reason_codes)
        self.assertNotIn(future_reason, permitted.reason_codes)
        self.assertNotIn(stale_gap_reason, permitted.reason_codes)

    def test_open_interest_positive_zero_negative_and_thresholds(self) -> None:
        cases = (
            (datetime.date(2030, 1, 1), 1, 1, FreshnessStatus.FRESH, None),
            (datetime.date(2030, 1, 2), 0, 0, FreshnessStatus.FRESH, None),
            (datetime.date(2030, 1, 3), 0, -1, FreshnessStatus.INELIGIBLE,
             FreshnessReasonCode.SESSION_DATE_AFTER_LATEST_COMPLETED_SESSION),
            (datetime.date(2029, 12, 30), 3, 3, FreshnessStatus.FRESH, None),
            (datetime.date(2029, 12, 29), 3, 4, FreshnessStatus.STALE,
             FreshnessReasonCode.OPEN_INTEREST_SESSION_DATE_GAP_EXCEEDED),
        )
        for date_value, maximum, gap, status, reason in cases:
            result = assess_market_data_freshness(
                build_option_open_interest_observation(
                    open_interest_session_date=date_value),
                build_freshness_policy(
                    maximum_open_interest_session_date_gap_days=maximum),
                build_freshness_context(),
            )
            with self.subTest(date=date_value):
                self.assertEqual(result.session_date_gap_days, gap)
                self.assertIs(result.status, status)
                if reason is not None:
                    self.assertIn(reason, result.reason_codes)

    def test_non_applicable_records_have_no_date_gap(self) -> None:
        builders = (
            build_underlying_quote_observation, build_option_quote_observation,
            build_option_implied_volatility_observation,
            build_option_greeks_observation, build_option_volume_observation,
            build_option_contract_reference, build_rate_curve_point_observation,
            build_dividend_observation,
        )
        for builder in builders:
            self.assertIsNone(assess_market_data_freshness(
                builder(), build_freshness_policy(), build_freshness_context()
            ).session_date_gap_days)


class FreshnessStatusAndAssessmentTests(unittest.TestCase):
    def test_mixed_reason_precedence_and_canonical_retention(self) -> None:
        metadata = build_normalization_metadata(
            quality_flags=(NormalizationQualityFlag.INCOMPLETE,)
        )
        result = assess_market_data_freshness(
            build_underlying_quote_observation(
                metadata=metadata, market_phase=MarketPhase.UNKNOWN,
                quote_scope=QuoteScope.UNKNOWN,
            ),
            build_freshness_policy(maximum_quote_age_seconds=0),
            build_freshness_context(),
        )
        self.assertIs(result.status, FreshnessStatus.INELIGIBLE)
        self.assertEqual(result.reason_codes, tuple(
            reason for reason in FreshnessReasonCode if reason in {
                FreshnessReasonCode.NORMALIZATION_INCOMPLETE,
                FreshnessReasonCode.NON_REGULAR_SESSION_QUOTE,
                FreshnessReasonCode.UNKNOWN_MARKET_PHASE,
                FreshnessReasonCode.UNKNOWN_QUOTE_SCOPE,
                FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,
                FreshnessReasonCode.OLDEST_SOURCE_AGE_EXCEEDED,
            }
        ))
        unknown_stale = assess_market_data_freshness(
            build_underlying_quote_observation(quote_scope=QuoteScope.UNKNOWN),
            build_freshness_policy(
                maximum_quote_age_seconds=0,
                require_regular_session_quotes=False,
            ), build_freshness_context(),
        )
        self.assertIs(unknown_stale.status, FreshnessStatus.UNKNOWN)
        self.assertIn(FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,
                      unknown_stale.reason_codes)

    def test_direct_assessment_reason_normalization_and_identity(self) -> None:
        assessment = FreshnessAssessment(**freshness_assessment_values(
            status=FreshnessStatus.INELIGIBLE,
            reason_codes=[
                FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,
                FreshnessReasonCode.NORMALIZATION_INCOMPLETE,
            ],
        ))
        self.assertEqual(assessment.reason_codes, (
            FreshnessReasonCode.NORMALIZATION_INCOMPLETE,
            FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,
        ))
        self.assertEqual((assessment.record_id, assessment.policy_id,
                          assessment.policy_version),
                         ("record-1", "policy-1", "v1"))
        hash(assessment)
        with self.assertRaises(FrozenInstanceError):
            assessment.status = FreshnessStatus.FRESH  # type: ignore[misc]

    def test_direct_assessment_rejects_invalid_reasons_and_status(self) -> None:
        invalid_cases = (
            ({"reason_codes": ()}, ValueError),
            ({"reason_codes": (
                FreshnessReasonCode.FRESH_WITHIN_POLICY,
                FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED)}, ValueError),
            ({"reason_codes": (
                FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,
                FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED),
              "status": FreshnessStatus.STALE}, ValueError),
            ({"reason_codes": ("effective_age_exceeded",),
              "status": FreshnessStatus.STALE}, TypeError),
            ({"reason_codes": (FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,),
              "status": FreshnessStatus.FRESH}, ValueError),
        )
        for overrides, error in invalid_cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(error):
                    FreshnessAssessment(**freshness_assessment_values(**overrides))

    def test_direct_assessment_metric_time_and_gap_validation(self) -> None:
        for name in (
            "effective_age_seconds", "oldest_source_age_seconds",
            "maximum_retrieval_lag_seconds_observed",
            "source_observation_span_seconds",
        ):
            for value in (1, decimal.Decimal("NaN"), decimal.Decimal("Infinity")):
                with self.subTest(name=name, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        FreshnessAssessment(**freshness_assessment_values(
                            **{name: value}))
        for name in (
            "maximum_retrieval_lag_seconds_observed",
            "source_observation_span_seconds",
        ):
            with self.assertRaises(ValueError):
                FreshnessAssessment(**freshness_assessment_values(
                    **{name: decimal.Decimal("-0.000001")}))
        for gap in (True, 1.5, "1"):
            with self.assertRaises(TypeError):
                FreshnessAssessment(**freshness_assessment_values(
                    session_date_gap_days=gap))
        with self.assertRaises(ValueError):
            FreshnessAssessment(**freshness_assessment_values(
                evaluated_at=datetime.datetime(2030, 1, 2)))

    def test_direct_assessment_rejects_category_and_metric_contradictions(self) -> None:
        cases = (
            {"session_date_gap_days": 1},
            {
                "category": MarketDataCategory.RATE,
                "status": FreshnessStatus.UNKNOWN,
                "reason_codes": (FreshnessReasonCode.UNKNOWN_MARKET_PHASE,),
            },
            {
                "category": MarketDataCategory.HISTORICAL_BAR,
                "status": FreshnessStatus.STALE,
                "reason_codes": (FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,),
            },
            {
                "category": MarketDataCategory.ACTIVITY,
                "session_date_gap_days": -1,
            },
            {
                "effective_age_seconds": decimal.Decimal("-0.000001"),
                "oldest_source_age_seconds": decimal.Decimal("0"),
                "source_observation_span_seconds": decimal.Decimal("0.000001"),
            },
            {
                "status": FreshnessStatus.INELIGIBLE,
                "reason_codes": (FreshnessReasonCode.NORMALIZATION_INCOMPLETE,),
                "effective_age_seconds": decimal.Decimal("-1"),
                "oldest_source_age_seconds": decimal.Decimal("-1"),
                "source_observation_span_seconds": decimal.Decimal("0"),
            },
            {
                "effective_age_seconds": decimal.Decimal("2"),
                "oldest_source_age_seconds": decimal.Decimal("1"),
                "source_observation_span_seconds": decimal.Decimal("1"),
            },
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    FreshnessAssessment(**freshness_assessment_values(**overrides))

    def test_direct_assessment_accepts_enforceably_consistent_boundaries(self) -> None:
        chronology_reasons = [
            FreshnessReasonCode.SOURCE_OBSERVED_AFTER_EVALUATION,
            FreshnessReasonCode.RECORD_NORMALIZED_AFTER_EVALUATION,
            FreshnessReasonCode.SOURCE_RETRIEVED_AFTER_EVALUATION,
        ]
        negative = FreshnessAssessment(**freshness_assessment_values(
            status=FreshnessStatus.INELIGIBLE,
            reason_codes=chronology_reasons,
            effective_age_seconds=decimal.Decimal("-1"),
            oldest_source_age_seconds=decimal.Decimal("-0.5"),
            source_observation_span_seconds=decimal.Decimal("0.5"),
        ))
        self.assertEqual(negative.reason_codes, (
            FreshnessReasonCode.RECORD_NORMALIZED_AFTER_EVALUATION,
            FreshnessReasonCode.SOURCE_RETRIEVED_AFTER_EVALUATION,
            FreshnessReasonCode.SOURCE_OBSERVED_AFTER_EVALUATION,
        ))

        activity_without_gap = FreshnessAssessment(**freshness_assessment_values(
            category=MarketDataCategory.ACTIVITY,
        ))
        self.assertIsNone(activity_without_gap.session_date_gap_days)

        incomplete_bar = FreshnessAssessment(**freshness_assessment_values(
            category=MarketDataCategory.HISTORICAL_BAR,
            status=FreshnessStatus.INELIGIBLE,
            reason_codes=(FreshnessReasonCode.HISTORICAL_SESSION_INCOMPLETE,),
            session_date_gap_days=None,
        ))
        self.assertIsNone(incomplete_bar.session_date_gap_days)

        completed_bar = FreshnessAssessment(**freshness_assessment_values(
            category=MarketDataCategory.HISTORICAL_BAR,
            session_date_gap_days=1,
        ))
        self.assertEqual(completed_bar.session_date_gap_days, 1)

    def test_deterministic_assessment_and_no_input_mutation(self) -> None:
        record = build_underlying_quote_observation()
        policy = build_freshness_policy()
        context = build_freshness_context()
        before = (record, policy, context, repr(record), repr(policy), repr(context))
        first = assess_market_data_freshness(record, policy, context)
        second = assess_market_data_freshness(record, policy, context)
        self.assertEqual(first, second)
        self.assertEqual(first.reason_codes,
                         (FreshnessReasonCode.FRESH_WITHIN_POLICY,))
        self.assertEqual(before,
                         (record, policy, context, repr(record), repr(policy),
                          repr(context)))

    def test_every_reason_code_is_exercised(self) -> None:
        seen = {FreshnessReasonCode.FRESH_WITHIN_POLICY}
        future_observed = EVALUATION_AT + datetime.timedelta(seconds=1)
        future_source = build_source_reference(
            observed_at=future_observed,
            retrieved_at=future_observed + datetime.timedelta(seconds=1),
        )
        records = [
            (build_underlying_quote_observation(metadata=build_normalization_metadata(
                [future_source], normalized_at=future_observed
                + datetime.timedelta(seconds=1))), build_freshness_policy()),
            (build_underlying_quote_observation(metadata=build_normalization_metadata(
                quality_flags=(NormalizationQualityFlag.INCOMPLETE,
                               NormalizationQualityFlag.TIMESTAMP_ASSIGNED))),
             build_freshness_policy()),
            (build_underlying_quote_observation(
                market_phase=MarketPhase.UNKNOWN, quote_scope=QuoteScope.UNKNOWN),
             build_freshness_policy(maximum_quote_age_seconds=0)),
            (build_underlying_daily_bar_observation(
                is_session_complete=False), build_freshness_policy()),
            (build_underlying_daily_bar_observation(
                session_date=datetime.date(2030, 1, 3)),
             build_freshness_policy()),
            (build_underlying_daily_bar_observation(
                session_date=datetime.date(2029, 12, 1)),
             build_freshness_policy()),
            (build_option_open_interest_observation(
                open_interest_session_date=datetime.date(2029, 12, 1)),
             build_freshness_policy()),
        ]
        all_flags = (
            SourceQualityFlag.DELAYED, SourceQualityFlag.INDICATIVE,
            SourceQualityFlag.NON_FIRM, SourceQualityFlag.PARTIAL,
            SourceQualityFlag.HALTED,
        )
        flagged_source = build_source_reference(
            quality_flags=all_flags, is_delayed=True, declared_delay_seconds=15,
            retrieved_at=OBSERVED_AT + datetime.timedelta(seconds=6),
        )
        flagged_metadata = build_normalization_metadata(
            [flagged_source], normalized_at=OBSERVED_AT + datetime.timedelta(seconds=6)
        )
        records.append((build_underlying_quote_observation(
            metadata=flagged_metadata), build_freshness_policy()))
        first = build_source_reference(source_id="span-a")
        second = build_source_reference(
            source_id="span-b", provider_record_id="span-b",
            observed_at=OBSERVED_AT + datetime.timedelta(seconds=3),
            retrieved_at=OBSERVED_AT + datetime.timedelta(seconds=4),
        )
        records.append((build_underlying_quote_observation(
            metadata=build_normalization_metadata(
                [first, second], effective_observed_at=second.observed_at,
                normalized_at=OBSERVED_AT + datetime.timedelta(seconds=4))),
            build_freshness_policy()))
        for record, policy in records:
            seen.update(assess_market_data_freshness(
                record, policy, build_freshness_context()).reason_codes)
        self.assertEqual(seen, set(FreshnessReasonCode))


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
