"""Tests for Milestone 3A.1 market-data provenance and identity records."""

import ast
import dataclasses
import collections
import datetime
import decimal
import inspect
import itertools
import json
import locale
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
    CalculationInputReference,
    CalculationLineage,
    CalculationQualityFlag,
    CorrectionSelection,
    CorrectionSelectionReasonCode,
    CorrectionSelectionStatus,
    DataOrigin,
    DividendObservation,
    DividendStatus,
    FreshnessAssessment,
    FreshnessContext,
    FreshnessReasonCode,
    FreshnessStatus,
    MarketPhase,
    MarketDataCategory,
    MarketDataBindingReference,
    MarketDataFreshnessPolicy,
    MarketDataRelationshipGroup,
    MarketDataRelationshipGroupKind,
    MarketDataRelationshipGroupMember,
    MarketDataRelationshipRequest,
    MarketDataRelationshipRole,
    MarketDataSnapshotTimingAssessment,
    MarketDataSnapshotTimingReasonCode,
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
    SelectedFreshMarketDataBinding,
    SourceQualityFlag,
    SourceReference,
    UnderlyingKey,
    UnderlyingDailyBarObservation,
    UnderlyingQuoteObservation,
    UnderlyingSecurityType,
    assess_market_data_freshness,
    assess_market_data_snapshot_timing,
    bind_selected_fresh_market_data,
    canonicalize_lineage_parameters,
    market_data_binding_reference,
    resolve_market_data_binding_reference,
    semantic_observation_key,
    select_correction_candidate,
)
from tests.market_data_fixtures import (
    CALCULATED_AT,
    EVALUATION_AT,
    NON_UTC_OBSERVED_AT,
    NON_UTC_RETRIEVED_AT,
    NORMALIZED_AT,
    OBSERVED_AT,
    RETRIEVED_AT,
    SESSION_DATE,
    UTC,
    build_correction_candidate,
    build_correction_quote_observation,
    build_correction_selection,
    build_correction_source,
    build_calculation_input_reference,
    build_calculation_lineage,
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
    build_provider_variant_metadata,
    build_rate_curve_point_observation,
    build_source_reference,
    build_underlying_key,
    build_underlying_daily_bar_observation,
    build_underlying_quote_observation,
    correction_selection_values,
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


def build_revision_candidate(
    record_id: str,
    revisions: tuple,
    correction_ids: object = None,
    **overrides: object,
) -> NormalizationMetadata:
    """Build a candidate with one fixed source per revision-vector component."""

    identities = (
        (None,) * len(revisions) if correction_ids is None else correction_ids
    )
    sources = tuple(
        build_correction_source(
            lineage_name=chr(ord("a") + index),
            revision_number=revision,
            provider_correction_id=identities[index],
        )
        for index, revision in enumerate(revisions)
    )
    return build_correction_candidate(record_id, sources, **overrides)


def select_corrections(candidates: object, **overrides: object) -> CorrectionSelection:
    """Call correction selection with fixed explicit rule inputs."""

    values = {
        "semantic_observation_key": "SPY consolidated quote",
        "candidates": candidates,
        "evaluated_at": EVALUATION_AT,
        "rule_id": "provider-correction-selection",
        "rule_version": "v0.1",
    }
    values.update(overrides)
    return select_correction_candidate(**values)


def bind_fresh_candidates(
    candidates: object,
    **overrides: object,
) -> SelectedFreshMarketDataBinding:
    """Bind fixed candidates under explicit synthetic correction context."""

    values = {
        "candidates": candidates,
        "correction_evaluated_at": EVALUATION_AT,
        "correction_rule_id": "provider-correction-selection",
        "correction_rule_version": "v0.1",
        "freshness_policy": build_freshness_policy(),
        "freshness_context": build_freshness_context(),
    }
    values.update(overrides)
    return bind_selected_fresh_market_data(**values)


def reconstruct_binding(
    binding: SelectedFreshMarketDataBinding,
    **overrides: object,
) -> SelectedFreshMarketDataBinding:
    """Directly reconstruct one binding with selected field overrides."""

    values = {
        "candidate_records": binding.candidate_records,
        "correction_selection": binding.correction_selection,
        "freshness_policy": binding.freshness_policy,
        "freshness_context": binding.freshness_context,
        "freshness_assessment": binding.freshness_assessment,
    }
    values.update(overrides)
    return SelectedFreshMarketDataBinding(**values)


def build_timed_record(
    builder: object,
    record_id: str,
    observed_offsets: tuple = (datetime.timedelta(0),),
    effective_offset: object = None,
    system_composite: bool = False,
    **record_overrides: object,
) -> object:
    """Build one deterministic record with controlled timing metadata."""

    record = builder(**record_overrides)  # type: ignore[operator]
    source_origin = record.metadata.source_references[0].origin
    sources = tuple(
        build_source_reference(
            source_id=f"{record_id}-source-{index}",
            provider_record_id=f"{record_id}-provider-record-{index}",
            provider_request_id=f"{record_id}-request-{index}",
            source_uri=f"synthetic://snapshot-timing/{record_id}/{index}",
            observed_at=OBSERVED_AT + offset,
            retrieved_at=(
                OBSERVED_AT + offset + datetime.timedelta(microseconds=1)
            ),
            origin=source_origin,
        )
        for index, offset in enumerate(observed_offsets)
    )
    selected_effective_offset = (
        observed_offsets[0]
        if effective_offset is None
        else effective_offset
    )
    metadata = build_normalization_metadata(
        sources,
        record_id=record_id,
        effective_observed_at=OBSERVED_AT + selected_effective_offset,
        normalized_at=(
            max(source.retrieved_at for source in sources)
            + datetime.timedelta(microseconds=1)
        ),
        record_origin=(
            DataOrigin.SYSTEM_COMPOSITE
            if system_composite
            else record.metadata.record_origin
        ),
        quality_flags=(
            (NormalizationQualityFlag.COMPOSITE_SOURCE,)
            if system_composite
            else ()
        ),
    )
    return dataclasses.replace(record, metadata=metadata)


def build_timing_binding(
    record: object,
    policy: object = None,
    context: object = None,
) -> SelectedFreshMarketDataBinding:
    """Bind one controlled record for snapshot-timing tests."""

    return bind_fresh_candidates(
        (record,),
        freshness_policy=(
            build_freshness_policy() if policy is None else policy
        ),
        freshness_context=(
            build_freshness_context() if context is None else context
        ),
    )


def build_relationship_reference(
    label: str = "reference",
    semantic_key: object = None,
    record_id: object = None,
) -> MarketDataBindingReference:
    """Build one portable opaque reference for relationship tests."""

    return MarketDataBindingReference(
        (
            f"semantic-observation-v0.1:synthetic-{label}"
            if semantic_key is None
            else semantic_key
        ),
        f"synthetic-{label}-record" if record_id is None else record_id,
    )


def build_relationship_member(
    role: MarketDataRelationshipRole,
    label: str = "reference",
    reference: object = None,
) -> MarketDataRelationshipGroupMember:
    """Build one explicit role/reference member."""

    return MarketDataRelationshipGroupMember(
        role,
        build_relationship_reference(label) if reference is None else reference,
    )


def build_relationship_group(
    group_id: str = "relationship-group",
    group_kind: MarketDataRelationshipGroupKind = (
        MarketDataRelationshipGroupKind
        .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
    ),
    members: object = None,
) -> MarketDataRelationshipGroup:
    """Build one valid explicit relationship group."""

    normalized_members = (
        (
            build_relationship_member(
                MarketDataRelationshipRole.UNDERLYING_QUOTE,
                "underlying-quote",
            ),
            build_relationship_member(
                MarketDataRelationshipRole.OPTION_QUOTE,
                "option-quote",
            ),
        )
        if members is None
        else members
    )
    return MarketDataRelationshipGroup(
        group_id,
        group_kind,
        normalized_members,
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
            "CorrectionSelectionStatus",
            "CorrectionSelectionReasonCode",
            "CorrectionSelection",
            "select_correction_candidate",
            "CalculationQualityFlag",
            "CalculationInputReference",
            "CalculationLineage",
            "canonicalize_lineage_parameters",
            "semantic_observation_key",
            "SelectedFreshMarketDataBinding",
            "bind_selected_fresh_market_data",
            "MarketDataSnapshotTimingReasonCode",
            "MarketDataSnapshotTimingAssessment",
            "assess_market_data_snapshot_timing",
            "MarketDataBindingReference",
            "market_data_binding_reference",
            "resolve_market_data_binding_reference",
            "MarketDataRelationshipGroupKind",
            "MarketDataRelationshipRole",
            "MarketDataRelationshipGroupMember",
            "MarketDataRelationshipGroup",
            "MarketDataRelationshipRequest",
        )
        self.assertEqual(market_data.__all__, expected)
        self.assertEqual(len(market_data.__all__), 50)
        self.assertTrue(all(hasattr(market_data, name) for name in expected))

    def test_later_milestone_types_do_not_exist(self) -> None:
        later_types = (
            "SemanticObservationKey",
            "MarketDataSnapshot",
            "MarketDataSnapshotTimingStatus",
            "MarketDataSnapshotPolicy",
            "ValidatedMarketDataSnapshot",
            "transform_market_data",
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
            CorrectionSelection: (
                "semantic_observation_key", "candidate_record_ids",
                "selected_record_id", "status", "reason_codes", "rule_id",
                "rule_version", "evaluated_at",
            ),
            SelectedFreshMarketDataBinding: (
                "candidate_records", "correction_selection",
                "freshness_policy", "freshness_context",
                "freshness_assessment",
            ),
            MarketDataSnapshotTimingAssessment: ("bindings",),
            CalculationInputReference: (
                "record_id", "normalized_at", "source_ids",
            ),
            CalculationLineage: (
                "calculation_id", "calculation_type", "methodology_id",
                "methodology_version", "calculated_at", "inputs",
                "parameters_json", "quality_flags",
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
        MarketDataSnapshotTimingReasonCode: (
            "mixed_freshness_policy", "mixed_freshness_context",
            "effective_time_span_exceeded",
            "source_observation_span_exceeded",
        ),
        CorrectionSelectionStatus: ("selected", "ambiguous"),
        CorrectionSelectionReasonCode: (
            "missing_provider_record_id", "source_lineage_mismatch",
            "conflicting_correction_ids_same_revision",
            "tied_revision_vectors", "incomparable_revision_vectors",
            "only_candidate_selected", "dominating_revision_vector_selected",
        ),
        CalculationQualityFlag: (
            "decimal_to_float_converted", "interpolated", "annualized",
            "adjusted_input_used", "correction_selected",
            "composite_input_used", "assumption_applied",
            "incomplete_input_used",
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


class CorrectionSelectionConstructorTests(unittest.TestCase):
    def test_canonical_normalization_frozen_hashable_and_deterministic(self) -> None:
        result = build_correction_selection(
            semantic_observation_key="  SPY quote  ",
            candidate_record_ids=[" candidate-b ", "candidate-a"],
            selected_record_id=" candidate-b ",
            rule_id=" correction-rule ",
            rule_version=" v1 ",
            evaluated_at=datetime.datetime(
                2030, 1, 2, 10, 31,
                tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
            ),
        )
        self.assertEqual(result.semantic_observation_key, "SPY quote")
        self.assertEqual(
            result.candidate_record_ids, ("candidate-a", "candidate-b")
        )
        self.assertEqual(result.selected_record_id, "candidate-b")
        self.assertEqual((result.rule_id, result.rule_version),
                         ("correction-rule", "v1"))
        self.assertEqual(result.evaluated_at, EVALUATION_AT)
        self.assertEqual(result, build_correction_selection(
            semantic_observation_key="SPY quote",
            candidate_record_ids=("candidate-a", "candidate-b"),
            selected_record_id="candidate-b",
            rule_id="correction-rule", rule_version="v1",
        ))
        self.assertEqual(hash(result), hash(result))
        with self.assertRaises(FrozenInstanceError):
            result.status = CorrectionSelectionStatus.AMBIGUOUS  # type: ignore[misc]

    def test_candidate_id_collection_and_membership_validation(self) -> None:
        invalid = (
            ({"candidate_record_ids": "candidate-001"}, TypeError),
            ({"candidate_record_ids": ("candidate-001", object())}, TypeError),
            ({"candidate_record_ids": ()}, ValueError),
            ({"candidate_record_ids": ("candidate-001", " candidate-001 ")},
             ValueError),
            ({"candidate_record_ids": (" ",)}, ValueError),
            ({"selected_record_id": "candidate-outside"}, ValueError),
            ({"selected_record_id": None}, ValueError),
        )
        for overrides, error in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaises(error):
                    CorrectionSelection(**correction_selection_values(**overrides))

    def test_status_selected_id_and_reason_compatibility(self) -> None:
        ambiguous = build_correction_selection(
            selected_record_id=None,
            status=CorrectionSelectionStatus.AMBIGUOUS,
            reason_codes=[CorrectionSelectionReasonCode.TIED_REVISION_VECTORS],
        )
        self.assertEqual(
            ambiguous.reason_codes,
            (CorrectionSelectionReasonCode.TIED_REVISION_VECTORS,),
        )
        invalid = (
            {"status": object()},
            {"reason_codes": "only_candidate_selected"},
            {"reason_codes": (object(),)},
            {"reason_codes": ()},
            {"reason_codes": (
                CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
                CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,
            )},
            {"reason_codes": (
                CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
                CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
            )},
            {"reason_codes": (
                CorrectionSelectionReasonCode.TIED_REVISION_VECTORS,
            )},
            {
                "selected_record_id": None,
                "status": CorrectionSelectionStatus.AMBIGUOUS,
                "reason_codes": (
                    CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
                ),
            },
            {
                "selected_record_id": "candidate-001",
                "status": CorrectionSelectionStatus.AMBIGUOUS,
                "reason_codes": (
                    CorrectionSelectionReasonCode.TIED_REVISION_VECTORS,
                ),
            },
        )
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                with self.assertRaises((TypeError, ValueError)):
                    CorrectionSelection(**correction_selection_values(**overrides))

    def test_string_and_evaluation_time_validation(self) -> None:
        for field in ("semantic_observation_key", "rule_id", "rule_version"):
            for value in (object(), " "):
                with self.subTest(field=field, value=value):
                    with self.assertRaises((TypeError, ValueError)):
                        CorrectionSelection(**correction_selection_values(
                            **{field: value}
                        ))
        with self.assertRaises(ValueError):
            build_correction_selection(
                evaluated_at=datetime.datetime(2030, 1, 2, 15, 31)
            )


class CorrectionSelectionInputTests(unittest.TestCase):
    def test_tuple_and_list_are_accepted_and_order_is_presentation_only(self) -> None:
        first = build_revision_candidate("candidate-z", (0,))
        second = build_revision_candidate("candidate-a", (1,))
        tuple_result = select_corrections((first, second))
        list_result = select_corrections([second, first])
        self.assertEqual(tuple_result, list_result)
        self.assertEqual(
            tuple_result.candidate_record_ids, ("candidate-a", "candidate-z")
        )
        self.assertEqual(tuple_result.selected_record_id, "candidate-a")

    def test_invalid_candidate_collections_and_duplicate_ids(self) -> None:
        candidate = build_correction_candidate()
        for value in ((item for item in (candidate,)), {candidate}, object()):
            with self.subTest(value=type(value)):
                with self.assertRaises(TypeError):
                    select_corrections(value)
        with self.assertRaises(ValueError):
            select_corrections(())
        with self.assertRaises(TypeError):
            select_corrections((object(),))
        with self.assertRaises(ValueError):
            select_corrections((candidate, candidate))

    def test_normalization_metadata_subclass_is_rejected(self) -> None:
        class MetadataSubclass(NormalizationMetadata):
            pass

        candidate = build_correction_candidate()
        subclass = MetadataSubclass(**{
            field.name: getattr(candidate, field.name)
            for field in dataclasses.fields(candidate)
        })
        with self.assertRaises(TypeError):
            select_corrections((subclass,))

    def test_future_normalization_rejected_and_equality_accepted(self) -> None:
        at_evaluation = build_correction_candidate(
            normalized_at=EVALUATION_AT
        )
        self.assertEqual(
            select_corrections((at_evaluation,)).selected_record_id,
            at_evaluation.record_id,
        )
        future = build_correction_candidate(
            normalized_at=EVALUATION_AT + datetime.timedelta(microseconds=1)
        )
        with self.assertRaises(ValueError):
            select_corrections((future,))


class CorrectionSelectionTerminalTests(unittest.TestCase):
    def assert_reason(
        self,
        result: CorrectionSelection,
        reason: CorrectionSelectionReasonCode,
    ) -> None:
        self.assertEqual(result.reason_codes, (reason,))

    def test_only_candidate_selected_without_provider_record_id(self) -> None:
        source = build_correction_source(provider_record_id=None)
        candidate = build_correction_candidate(sources=(source,))
        result = select_corrections((candidate,))
        self.assertEqual(result.status, CorrectionSelectionStatus.SELECTED)
        self.assertEqual(result.selected_record_id, candidate.record_id)
        self.assert_reason(
            result, CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED
        )

    def test_missing_provider_id_precedes_lineage_validation(self) -> None:
        missing_a = build_correction_source(
            provider_record_id=None, source_id="missing-a"
        )
        missing_b = build_correction_source(
            provider_record_id=None, source_id="missing-b"
        )
        first = build_correction_candidate(
            "candidate-a", (missing_a, missing_b)
        )
        second = build_revision_candidate("candidate-b", (0,))
        result = select_corrections((first, second))
        self.assert_reason(
            result, CorrectionSelectionReasonCode.MISSING_PROVIDER_RECORD_ID
        )

    def test_duplicate_lineage_key_raises(self) -> None:
        first_source = build_correction_source(source_id="duplicate-a")
        second_source = build_correction_source(
            source_id="duplicate-b", revision_number=1
        )
        duplicate = build_correction_candidate(
            "candidate-a", (first_source, second_source)
        )
        other = build_revision_candidate("candidate-b", (1,))
        with self.assertRaises(ValueError):
            select_corrections((duplicate, other))

    def test_source_lineage_mismatch(self) -> None:
        first = build_revision_candidate("candidate-a", (1,))
        different_source = build_correction_source(
            lineage_name="b", revision_number=2
        )
        second = build_correction_candidate(
            "candidate-b", (different_source,)
        )
        result = select_corrections((first, second))
        self.assert_reason(
            result, CorrectionSelectionReasonCode.SOURCE_LINEAGE_MISMATCH
        )

    def test_every_terminal_reason_path(self) -> None:
        conflict = select_corrections((
            build_revision_candidate("a", (1,), ("A",)),
            build_revision_candidate("b", (1,), ("B",)),
        ))
        tied = select_corrections((
            build_revision_candidate("a", (2, 2)),
            build_revision_candidate("b", (2, 2)),
        ))
        dominating = select_corrections((
            build_revision_candidate("a", (2, 1)),
            build_revision_candidate("b", (1, 1)),
        ))
        incomparable = select_corrections((
            build_revision_candidate("a", (2, 1)),
            build_revision_candidate("b", (1, 2)),
        ))
        expected = (
            (conflict, CorrectionSelectionReasonCode.CONFLICTING_CORRECTION_IDS_SAME_REVISION),
            (tied, CorrectionSelectionReasonCode.TIED_REVISION_VECTORS),
            (dominating, CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED),
            (incomparable, CorrectionSelectionReasonCode.INCOMPARABLE_REVISION_VECTORS),
        )
        for result, reason in expected:
            with self.subTest(reason=reason):
                self.assert_reason(result, reason)


class CorrectionRevisionAndDominanceTests(unittest.TestCase):
    def test_normalized_revision_identity_regressions(self) -> None:
        cases = (
            ((None, None), (0, None),
             CorrectionSelectionReasonCode.TIED_REVISION_VECTORS, None),
            ((None, None), (0, "A"),
             CorrectionSelectionReasonCode.CONFLICTING_CORRECTION_IDS_SAME_REVISION,
             None),
            ((0, "A"), (0, "A"),
             CorrectionSelectionReasonCode.TIED_REVISION_VECTORS, None),
            ((1, "A"), (1, "B"),
             CorrectionSelectionReasonCode.CONFLICTING_CORRECTION_IDS_SAME_REVISION,
             None),
            ((1, "A"), (2, "B"),
             CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,
             "candidate-b"),
        )
        for first_values, second_values, reason, selected_id in cases:
            with self.subTest(first=first_values, second=second_values):
                first = build_revision_candidate(
                    "candidate-a", (first_values[0],), (first_values[1],)
                )
                second = build_revision_candidate(
                    "candidate-b", (second_values[0],), (second_values[1],)
                )
                result = select_corrections((first, second))
                self.assertEqual(result.reason_codes, (reason,))
                self.assertEqual(result.selected_record_id, selected_id)

    def test_documented_two_candidate_dominance_vectors(self) -> None:
        cases = (
            ((0,), (1,), "candidate-b"),
            ((1, 1), (2, 1), "candidate-b"),
            ((2, 1), (1, 2), None),
            ((2, 2), (2, 2), None),
            ((0, 0), (0, 1), "candidate-b"),
            ((3, 1, 2), (2, 1, 2), "candidate-a"),
            ((3, 0), (2, 4), None),
        )
        for first_vector, second_vector, selected_id in cases:
            with self.subTest(first=first_vector, second=second_vector):
                result = select_corrections((
                    build_revision_candidate("candidate-a", first_vector),
                    build_revision_candidate("candidate-b", second_vector),
                ))
                self.assertEqual(result.selected_record_id, selected_id)
                if first_vector == second_vector:
                    expected = CorrectionSelectionReasonCode.TIED_REVISION_VECTORS
                elif selected_id is None:
                    expected = (
                        CorrectionSelectionReasonCode.INCOMPARABLE_REVISION_VECTORS
                    )
                else:
                    expected = (
                        CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED
                    )
                self.assertEqual(result.reason_codes, (expected,))

    def test_three_candidate_dominance_incomparable_maxima_and_tie(self) -> None:
        dominating = select_corrections((
            build_revision_candidate("a", (3, 3)),
            build_revision_candidate("b", (2, 3)),
            build_revision_candidate("c", (3, 1)),
        ))
        self.assertEqual(dominating.selected_record_id, "a")

        incomparable = select_corrections((
            build_revision_candidate("a", (3, 2)),
            build_revision_candidate("b", (2, 3)),
            build_revision_candidate("c", (1, 1)),
        ))
        self.assertEqual(
            incomparable.reason_codes,
            (CorrectionSelectionReasonCode.INCOMPARABLE_REVISION_VECTORS,),
        )

        tied = select_corrections(tuple(
            build_revision_candidate(record_id, (2, 2))
            for record_id in ("a", "b", "c")
        ))
        self.assertEqual(
            tied.reason_codes,
            (CorrectionSelectionReasonCode.TIED_REVISION_VECTORS,),
        )


class CorrectionMultiSourceAndDeterminismTests(unittest.TestCase):
    def test_complete_group_identity_conflict_is_order_independent(self) -> None:
        candidates = (
            build_revision_candidate("a", (1, 2), ("A", "X")),
            build_revision_candidate("b", (1, 2), ("A", "X")),
            build_revision_candidate("c", (1, 2), ("B", "X")),
        )
        for permutation in itertools.permutations(candidates):
            result = select_corrections(permutation)
            self.assertEqual(
                result.reason_codes,
                (CorrectionSelectionReasonCode.CONFLICTING_CORRECTION_IDS_SAME_REVISION,),
            )

    def test_identity_is_per_lineage_and_normalized_revision(self) -> None:
        first = build_revision_candidate("a", (1, 1), ("A", "same"))
        same_revision_conflict = build_revision_candidate(
            "b", (2, 1), ("B", "different")
        )
        result = select_corrections((first, same_revision_conflict))
        self.assertEqual(
            result.reason_codes,
            (CorrectionSelectionReasonCode.CONFLICTING_CORRECTION_IDS_SAME_REVISION,),
        )

        different_revisions = build_revision_candidate(
            "b", (2, 2), ("B", "different")
        )
        ordered = select_corrections((first, different_revisions))
        self.assertEqual(ordered.selected_record_id, "b")

    def test_source_storage_order_does_not_change_vector_order(self) -> None:
        first_sources = (
            build_correction_source("a", 1, source_id="z-source"),
            build_correction_source("b", 2, source_id="a-source"),
        )
        second_sources = (
            build_correction_source("b", 2, source_id="z-source"),
            build_correction_source("a", 2, source_id="a-source"),
        )
        first = build_correction_candidate("first", first_sources)
        second = build_correction_candidate("second", second_sources)
        result = select_corrections((first, second))
        self.assertEqual(result.selected_record_id, "second")

    def test_excluded_fields_do_not_order_corrections_or_mutate_inputs(self) -> None:
        low_source = build_correction_source(
            "a", 1, "Z", source_id="zzz-source",
            provider_request_id="zzz-request", payload_sha256="f" * 64,
            observed_at=OBSERVED_AT + datetime.timedelta(seconds=4),
            retrieved_at=OBSERVED_AT + datetime.timedelta(seconds=5),
        )
        high_source = build_correction_source(
            "a", 2, "A", source_id="aaa-source",
            provider_request_id="aaa-request", payload_sha256="0" * 64,
            observed_at=OBSERVED_AT + datetime.timedelta(seconds=1),
        )
        low = build_correction_candidate(
            "zzz-record", (low_source,),
            normalized_at=NORMALIZED_AT + datetime.timedelta(seconds=7),
        )
        high = build_correction_candidate("aaa-record", (high_source,))
        candidates = [low, high]
        before = (tuple(candidates), tuple(map(repr, candidates)))
        first = select_corrections(candidates)
        second = select_corrections(list(reversed(candidates)))
        self.assertEqual(first, second)
        self.assertEqual(first.selected_record_id, "aaa-record")
        self.assertEqual(before, (tuple(candidates), tuple(map(repr, candidates))))


class LineageCanonicalValueTests(unittest.TestCase):
    def test_complete_supported_scalar_and_container_grammar(self) -> None:
        parameters = {
            "none": None,
            "bool": True,
            "int": 7,
            "str": "text",
            "decimal": decimal.Decimal("0.20"),
            "date": datetime.date(2026, 7, 18),
            "datetime": datetime.datetime(
                2026, 7, 18, 19, tzinfo=datetime.timezone.utc
            ),
            "list": [1, False],
            "tuple": (1, False),
            "dict": {"nested": "value"},
        }
        result = canonicalize_lineage_parameters(parameters)
        self.assertIn('"$decimal":"0.20"', result)
        self.assertIn('"$date":"2026-07-18"', result)
        self.assertIn('"$datetime":"2026-07-18T19:00:00.000000Z"', result)
        self.assertEqual(
            canonicalize_lineage_parameters({"value": [1, False]}),
            canonicalize_lineage_parameters({"value": (1, False)}),
        )

    def test_empty_map_map_order_and_list_order(self) -> None:
        self.assertEqual(canonicalize_lineage_parameters({}), '{"$map":[]}')
        first = {"z": 1, "a": 2, "😀": 3}
        second = {"😀": 3, "a": 2, "z": 1}
        self.assertEqual(
            canonicalize_lineage_parameters(first),
            canonicalize_lineage_parameters(second),
        )
        self.assertIn('[["a",2],["z",1],["😀",3]]',
                      canonicalize_lineage_parameters(first))
        self.assertNotEqual(
            canonicalize_lineage_parameters({"x": [1, 2]}),
            canonicalize_lineage_parameters({"x": [2, 1]}),
        )

    def test_decimal_precision_zero_exponent_and_context_independence(self) -> None:
        values = (
            ("0.20", "0.20"), ("-0", "0"), ("-0.00", "0.00"),
            ("0E+2", "0E+2"), ("1.25E-7", "1.25E-7"),
            ("1E+999999", "1E+999999"), ("1E-999999", "1E-999999"),
        )
        for source, expected in values:
            outputs = []
            for precision in (1, 2, 28, 50):
                with decimal.localcontext() as context:
                    context.prec = precision
                    outputs.append(canonicalize_lineage_parameters({
                        "value": decimal.Decimal(source),
                    }))
            self.assertEqual(len(set(outputs)), 1)
            self.assertIn(f'"$decimal":"{expected}"', outputs[0])

    def test_nonfinite_decimals_raise_value_error(self) -> None:
        for value in ("NaN", "sNaN", "Infinity", "-Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    canonicalize_lineage_parameters({
                        "value": decimal.Decimal(value),
                    })

    def test_datetime_utc_conversion_rollover_and_six_digits(self) -> None:
        non_utc = datetime.datetime(
            2026, 7, 19, 0, 30, 0, 123456,
            tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)),
        )
        result = canonicalize_lineage_parameters({"value": non_utc})
        self.assertIn("2026-07-18T19:00:00.123456Z", result)
        zero = canonicalize_lineage_parameters({
            "value": datetime.datetime(2026, 7, 18, tzinfo=UTC),
        })
        self.assertIn("2026-07-18T00:00:00.000000Z", zero)

    def test_datetime_naive_and_utc_overflow_raise_value_error(self) -> None:
        lower = datetime.datetime(
            1, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=1))
        )
        upper = datetime.datetime(
            9999, 12, 31, 23, 59, 59,
            tzinfo=datetime.timezone(datetime.timedelta(hours=-1)),
        )
        for value in (datetime.datetime(2026, 7, 18), lower, upper):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    canonicalize_lineage_parameters({"value": value})

    def test_malformed_timezone_type_error_is_public_value_error(self) -> None:
        class InvalidOffsetTimezone(datetime.tzinfo):
            def utcoffset(self, value: object) -> object:
                return "invalid-offset"

        malformed = datetime.datetime(
            2030, 1, 2, 15, 30, tzinfo=InvalidOffsetTimezone()
        )
        with self.assertRaises(TypeError):
            malformed.utcoffset()

        boundaries = (
            lambda: build_calculation_input_reference(
                normalized_at=malformed
            ),
            lambda: canonicalize_lineage_parameters({"value": malformed}),
            lambda: build_calculation_lineage(calculated_at=malformed),
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary.__code__.co_firstlineno):
                with self.assertRaises(ValueError):
                    boundary()

    def test_unicode_scalars_valid_and_surrogates_rejected(self) -> None:
        canonical = canonicalize_lineage_parameters({"emoji": "😀", "汉字": "值"})
        canonical.encode("utf-8")
        self.assertIn("😀", canonical)
        for parameters in ({"value": "\ud800"}, {"\udfff": "value"}):
            with self.assertRaises(ValueError):
                canonicalize_lineage_parameters(parameters)


class LineageExactTypeBoundaryTests(unittest.TestCase):
    def test_root_rejects_broader_mapping_and_iterable_types(self) -> None:
        class DictSubclass(dict):
            pass

        class CustomMapping(collections.abc.Mapping):
            def __getitem__(self, key: object) -> object:
                return {"a": 1}[key]  # type: ignore[index]

            def __iter__(self):
                return iter(("a",))

            def __len__(self) -> int:
                return 1

        values = (
            DictSubclass(), collections.UserDict(), CustomMapping(),
            (("a", 1),), (item for item in (1,)), [], None,
        )
        for value in values:
            with self.subTest(value=type(value)):
                with self.assertRaises(TypeError):
                    canonicalize_lineage_parameters(value)

    def test_nested_dict_subclass_and_supported_subclasses_rejected(self) -> None:
        class DictSubclass(dict):
            pass

        class StrSubclass(str):
            pass

        class IntSubclass(int):
            pass

        class ListSubclass(list):
            pass

        class TupleSubclass(tuple):
            pass

        class DateSubclass(datetime.date):
            pass

        class DatetimeSubclass(datetime.datetime):
            pass

        values = (
            DictSubclass(), StrSubclass("x"), IntSubclass(1),
            ListSubclass(), TupleSubclass(), DateSubclass(2026, 7, 18),
            DatetimeSubclass(2026, 7, 18, tzinfo=UTC),
            SourceQualityFlag.DELAYED,
        )
        for value in values:
            with self.subTest(value=type(value)):
                with self.assertRaises(TypeError):
                    canonicalize_lineage_parameters({"value": value})

    def test_all_documented_unsupported_categories_raise_type_error(self) -> None:
        values = (
            1.0, b"x", bytearray(b"x"), {1}, frozenset((1,)), object(),
            range(2), (item for item in (1,)),
        )
        for value in values:
            with self.subTest(value=type(value)):
                with self.assertRaises(TypeError):
                    canonicalize_lineage_parameters({"value": value})

    def test_mapping_key_exact_type_and_value_rules(self) -> None:
        class StrSubclass(str):
            pass

        for key in (1, StrSubclass("key")):
            with self.subTest(key=key):
                with self.assertRaises(TypeError):
                    canonicalize_lineage_parameters({key: 1})
        for key in ("", " ", " key", "key "):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    canonicalize_lineage_parameters({key: 1})


class LineageDepthAndCycleTests(unittest.TestCase):
    @staticmethod
    def nested_parameters(list_count: int, leaf: object = 0) -> dict:
        value = leaf
        for _ in range(list_count):
            value = [value]
        return {"value": value}

    def test_depth_32_valid_33_invalid_and_scalar_tag_not_counted(self) -> None:
        depth_32 = self.nested_parameters(31)
        scalar_at_32 = self.nested_parameters(31, decimal.Decimal("1.20"))
        canonicalize_lineage_parameters(depth_32)
        canonicalize_lineage_parameters(scalar_at_32)
        with self.assertRaises(ValueError):
            canonicalize_lineage_parameters(self.nested_parameters(32))

    def test_json_validation_uses_same_depth_rule(self) -> None:
        depth_32 = canonicalize_lineage_parameters(self.nested_parameters(31))
        build_calculation_lineage(parameters_json=depth_32)
        scalar_at_32 = canonicalize_lineage_parameters(
            self.nested_parameters(31, decimal.Decimal("1.20"))
        )
        build_calculation_lineage(parameters_json=scalar_at_32)
        value = "0"
        for _ in range(32):
            value = '{"$list":[' + value + "]}"
        depth_33 = '{"$map":[["value",' + value + ']]}'
        with self.assertRaises(ValueError):
            build_calculation_lineage(parameters_json=depth_33)

    def test_direct_and_indirect_cycles_rejected(self) -> None:
        direct_list = []
        direct_list.append(direct_list)
        direct_dict = {}
        direct_dict["self"] = direct_dict
        indirect_list = []
        indirect_dict = {"list": indirect_list}
        indirect_list.append(indirect_dict)
        tuple_list = []
        tuple_value = (tuple_list,)
        tuple_list.append(tuple_value)
        for value in (direct_list, direct_dict, indirect_list, tuple_value):
            with self.subTest(value=type(value)):
                with self.assertRaises(ValueError):
                    canonicalize_lineage_parameters({"value": value})

    def test_shared_noncyclic_reference_is_valid(self) -> None:
        shared = [decimal.Decimal("1.20")]
        result = canonicalize_lineage_parameters({"a": shared, "b": shared})
        self.assertEqual(result.count('"$decimal":"1.20"'), 2)


class LineageJsonValidationTests(unittest.TestCase):
    def assert_invalid_json(self, value: str) -> None:
        with self.assertRaises(ValueError) as context:
            build_calculation_lineage(parameters_json=value)
        self.assertNotEqual(type(context.exception).__name__, "JSONDecodeError")

    def test_duplicate_object_and_map_user_keys_are_separate_failures(self) -> None:
        self.assert_invalid_json('{"$map":[],"$map":[]}')
        self.assert_invalid_json('{"$map":[["a",1],["a",2]]}')

    def test_map_order_keys_and_entries_are_strict(self) -> None:
        values = (
            '{"$map":[["b",1],["a",2]]}',
            '{"$map":[["",1]]}',
            '{"$map":[[" a",1]]}',
            '{"$map":[[1,1]]}',
            '{"$map":[["a"]]}',
            '{"$map":[["a",1,2]]}',
        )
        for value in values:
            with self.subTest(value=value):
                self.assert_invalid_json(value)

    def test_unknown_multi_untagged_and_malformed_tags_rejected(self) -> None:
        values = (
            '{"$map":[["x",{"$unknown":[]}]]}',
            '{"$map":[["x",{"$list":[],"$map":[]}]]}',
            '{"$map":[["x",{"plain":1}]]}',
            '{"$map":[["x",[]]]}',
            '{"$map":{}}',
            '{"$list":[]}',
        )
        for value in values:
            with self.subTest(value=value):
                self.assert_invalid_json(value)

    def test_float_malformed_json_and_noncanonical_formatting_rejected(self) -> None:
        values = (
            '{"$map":[["x",1.0]]}',
            '{"$map":[["x",NaN]]}',
            '{"$map":[',
            '{ "$map": [] }',
            '{"$map":[["x",-0]]}',
            '{"$map":[["x","\\u0061"]]}',
        )
        for value in values:
            with self.subTest(value=value):
                self.assert_invalid_json(value)

    def test_noncanonical_tagged_scalar_strings_rejected(self) -> None:
        values = (
            '{"$map":[["x",{"$decimal":"-0.00"}]]}',
            '{"$map":[["x",{"$decimal":"01.250"}]]}',
            '{"$map":[["x",{"$date":"2026-7-18"}]]}',
            '{"$map":[["x",{"$datetime":"2026-07-18T19:00:00Z"}]]}',
            '{"$map":[["x",{"$datetime":"2026-07-18T19:00:00.000000+00:00"}]]}',
        )
        for value in values:
            with self.subTest(value=value):
                self.assert_invalid_json(value)

    def test_surrogate_from_json_and_outer_whitespace_behavior(self) -> None:
        self.assert_invalid_json('{"$map":[["x","\\ud800"]]}')
        canonical = canonicalize_lineage_parameters({"x": "😀"})
        lineage = build_calculation_lineage(
            parameters_json=" \n" + canonical + "\t "
        )
        self.assertEqual(lineage.parameters_json, canonical)


class CalculationInputReferenceTests(unittest.TestCase):
    def test_normalization_sorting_utc_hash_and_frozen(self) -> None:
        non_utc = datetime.datetime(
            2030, 1, 2, 10, 30, 3,
            tzinfo=datetime.timezone(datetime.timedelta(hours=-5)),
        )
        reference = build_calculation_input_reference(
            record_id=" normalized ", normalized_at=non_utc,
            source_ids=[" z-source ", "a-source"],
        )
        self.assertEqual(reference.record_id, "normalized")
        self.assertEqual(reference.normalized_at, NORMALIZED_AT)
        self.assertEqual(reference.source_ids, ("a-source", "z-source"))
        hash(reference)
        with self.assertRaises(FrozenInstanceError):
            reference.record_id = "changed"  # type: ignore[misc]

    def test_source_id_container_element_empty_and_duplicate_boundaries(self) -> None:
        class ListSubclass(list):
            pass

        class StrSubclass(str):
            pass

        for value in ((), [], (item for item in ("a",)), {"a"}, ListSubclass(["a"])):
            expected = ValueError if type(value) in (tuple, list) else TypeError
            with self.subTest(value=type(value)):
                with self.assertRaises(expected):
                    build_calculation_input_reference(source_ids=value)
        for value in ((1,), (StrSubclass("a"),)):
            with self.assertRaises(TypeError):
                build_calculation_input_reference(source_ids=value)
        for value in ((" ",), ("a", " a ")):
            with self.assertRaises(ValueError):
                build_calculation_input_reference(source_ids=value)

    def test_datetime_exact_type_awareness_and_overflow(self) -> None:
        class DatetimeSubclass(datetime.datetime):
            pass

        values = (
            datetime.datetime(2030, 1, 2),
            datetime.date(2030, 1, 2),
            DatetimeSubclass(2030, 1, 2, tzinfo=UTC),
            datetime.datetime(
                1, 1, 1,
                tzinfo=datetime.timezone(datetime.timedelta(hours=1)),
            ),
        )
        for value in values:
            expected = TypeError if type(value) is not datetime.datetime else ValueError
            with self.subTest(value=type(value)):
                with self.assertRaises(expected):
                    build_calculation_input_reference(normalized_at=value)


class CalculationLineageTests(unittest.TestCase):
    def test_input_flag_string_normalization_hash_and_frozen(self) -> None:
        second = build_calculation_input_reference("input-b")
        first = build_calculation_input_reference("input-a")
        lineage = build_calculation_lineage(
            calculation_id=" calculation ", calculation_type=" type ",
            methodology_id=" method ", methodology_version=" v1 ",
            inputs=[second, first],
            quality_flags=[
                CalculationQualityFlag.INCOMPLETE_INPUT_USED,
                CalculationQualityFlag.INTERPOLATED,
            ],
        )
        self.assertEqual(lineage.calculation_id, "calculation")
        self.assertEqual(
            tuple(item.record_id for item in lineage.inputs),
            ("input-a", "input-b"),
        )
        self.assertEqual(lineage.quality_flags, (
            CalculationQualityFlag.INTERPOLATED,
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
        ))
        hash(lineage)
        with self.assertRaises(FrozenInstanceError):
            lineage.calculation_id = "changed"  # type: ignore[misc]

    def test_empty_flags_valid_and_duplicate_or_wrong_flags_rejected(self) -> None:
        self.assertEqual(build_calculation_lineage(quality_flags=[]).quality_flags, ())
        with self.assertRaises(ValueError):
            build_calculation_lineage(quality_flags=[
                CalculationQualityFlag.ANNUALIZED,
                CalculationQualityFlag.ANNUALIZED,
            ])
        for value in ({CalculationQualityFlag.ANNUALIZED},
                      (SourceQualityFlag.DELAYED,)):
            with self.assertRaises(TypeError):
                build_calculation_lineage(quality_flags=value)

    def test_inputs_exact_container_record_type_and_uniqueness(self) -> None:
        @dataclasses.dataclass(frozen=True)
        class ReferenceSubclass(CalculationInputReference):
            pass

        base = build_calculation_input_reference()
        subclass = ReferenceSubclass(
            base.record_id, base.normalized_at, base.source_ids
        )
        for value in ({base}, (item for item in (base,)), (object(),), (subclass,)):
            with self.subTest(value=type(value)):
                with self.assertRaises(TypeError):
                    build_calculation_lineage(inputs=value)
        with self.assertRaises(ValueError):
            build_calculation_lineage(inputs=[])
        with self.assertRaises(ValueError):
            build_calculation_lineage(inputs=[base, base])

    def test_id_collision_and_chronology_equality_and_failure(self) -> None:
        input_reference = build_calculation_input_reference("input-a")
        equality = build_calculation_lineage(
            calculated_at=input_reference.normalized_at,
            inputs=(input_reference,),
        )
        self.assertEqual(equality.calculated_at, input_reference.normalized_at)
        with self.assertRaises(ValueError):
            build_calculation_lineage(
                calculation_id="input-a", inputs=(input_reference,)
            )
        with self.assertRaises(ValueError):
            build_calculation_lineage(
                calculated_at=input_reference.normalized_at
                - datetime.timedelta(microseconds=1),
                inputs=(input_reference,),
            )

    def test_calculated_at_exact_type_naive_and_overflow(self) -> None:
        class DatetimeSubclass(datetime.datetime):
            pass

        values = (
            datetime.date(2030, 1, 2),
            DatetimeSubclass(2030, 1, 2, tzinfo=UTC),
            datetime.datetime(2030, 1, 2),
            datetime.datetime(
                9999, 12, 31, 23, 59, 59,
                tzinfo=datetime.timezone(datetime.timedelta(hours=-1)),
            ),
        )
        for value in values:
            expected = TypeError if type(value) is not datetime.datetime else ValueError
            with self.subTest(value=type(value)):
                with self.assertRaises(expected):
                    build_calculation_lineage(calculated_at=value)

    def test_parameters_json_exact_string_and_canonical_requirement(self) -> None:
        class StrSubclass(str):
            pass

        for value in (1, StrSubclass('{"$map":[]}')):
            with self.assertRaises(TypeError):
                build_calculation_lineage(parameters_json=value)
        for value in ("", " ", "{}", '{"$map": [ ]}'):
            with self.assertRaises(ValueError):
                build_calculation_lineage(parameters_json=value)


class SemanticObservationIdentityTests(unittest.TestCase):
    PREFIX = "semantic-observation-v0.1:"

    @staticmethod
    def tagged_map(value: object) -> dict:
        return dict(value["$map"])  # type: ignore[index]

    @classmethod
    def decoded_payload(cls, record: object) -> dict:
        key = semantic_observation_key(record)
        return cls.tagged_map(json.loads(key[len(cls.PREFIX):]))

    @staticmethod
    def metadata_with_effective_time(
        record: object, effective_at: datetime.datetime
    ) -> NormalizationMetadata:
        metadata = record.metadata  # type: ignore[attr-defined]
        source = dataclasses.replace(
            metadata.source_references[0], observed_at=effective_at
        )
        return dataclasses.replace(
            metadata,
            record_id=metadata.record_id + "-later",
            source_references=(source,),
            effective_observed_at=effective_at,
        )

    def test_all_ten_exact_types_tokens_and_payload_schemas(self) -> None:
        cases = (
            (build_underlying_quote_observation(), "UnderlyingQuoteObservation", {
                "record_type", "underlying_key", "session_date",
                "effective_observed_at", "market_phase", "quote_scope",
                "venue_mic",
            }),
            (build_option_contract_reference(), "OptionContractReference", {
                "record_type", "contract_key",
            }),
            (build_option_quote_observation(), "OptionQuoteObservation", {
                "record_type", "contract_key", "session_date",
                "effective_observed_at", "market_phase", "quote_scope",
                "venue_mic",
            }),
            (build_option_volume_observation(), "OptionVolumeObservation", {
                "record_type", "contract_key", "session_date",
                "effective_observed_at",
            }),
            (build_option_open_interest_observation(),
             "OptionOpenInterestObservation", {
                 "record_type", "contract_key", "open_interest_session_date",
             }),
            (build_option_implied_volatility_observation(),
             "OptionImpliedVolatilityObservation", {
                 "record_type", "contract_key", "session_date",
                 "effective_observed_at", "model_name", "model_version",
                 "rate_input_description", "dividend_input_description",
             }),
            (build_option_greeks_observation(), "OptionGreeksObservation", {
                "record_type", "contract_key", "session_date",
                "effective_observed_at", "model_name", "model_version",
                "rate_input_description", "dividend_input_description",
            }),
            (build_underlying_daily_bar_observation(),
             "UnderlyingDailyBarObservation", {
                 "record_type", "underlying_key", "session_date",
             }),
            (build_rate_curve_point_observation(),
             "RateCurvePointObservation", {
                 "record_type", "curve_id", "currency", "tenor_days",
                 "effective_date", "compounding_convention",
                 "day_count_convention",
             }),
            (build_dividend_observation(), "DividendObservation", {
                "record_type", "underlying_key", "dividend_type", "ex_date",
                "status",
            }),
        )
        self.assertEqual(len(cases), 10)
        for record, token, expected_fields in cases:
            with self.subTest(record_type=token):
                key = semantic_observation_key(record)
                self.assertIs(type(key), str)
                self.assertTrue(key.startswith(self.PREFIX))
                self.assertEqual(key, semantic_observation_key(record))
                payload = self.decoded_payload(record)
                self.assertEqual(payload["record_type"], token)
                self.assertEqual(set(payload), expected_fields)

    def test_literal_golden_keys_lock_nested_schema_order_null_and_decimal(self) -> None:
        quote_expected = (
            'semantic-observation-v0.1:{"$map":['
            '["effective_observed_at",{"$datetime":"2030-01-02T15:30:00.000000Z"}],'
            '["market_phase","regular"],["quote_scope","consolidated"],'
            '["record_type","UnderlyingQuoteObservation"],'
            '["session_date",{"$date":"2030-01-02"}],'
            '["underlying_key",{"$map":[["currency","USD"],'
            '["listing_mic","ARCX"],["security_type","etf"],'
            '["symbol","SPY"]]}],["venue_mic",null]]}'
        )
        contract_expected = (
            'semantic-observation-v0.1:{"$map":[["contract_key",{"$map":['
            '["contract_multiplier",100],["currency","USD"],'
            '["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],'
            '["option_type","call"],["strike",{"$decimal":"500.1250"}],'
            '["underlying_key",{"$map":[["currency","USD"],'
            '["listing_mic","ARCX"],["security_type","etf"],'
            '["symbol","SPY"]]}]]}],["record_type",'
            '"OptionContractReference"]]}'
        )
        self.assertEqual(
            semantic_observation_key(build_underlying_quote_observation()),
            quote_expected,
        )
        self.assertEqual(
            semantic_observation_key(build_option_contract_reference()),
            contract_expected,
        )

    def test_nested_null_model_null_decimal_and_non_utc_datetime_encoding(self) -> None:
        underlying = build_underlying_key(listing_mic=None)
        contract = build_option_contract_key(
            underlying_key=underlying,
            strike=decimal.Decimal("500.1250"),
            deliverable_id=None,
        )
        reference_key = semantic_observation_key(
            build_option_contract_reference(contract_key=contract)
        )
        self.assertIn('["listing_mic",null]', reference_key)
        self.assertIn('["deliverable_id",null]', reference_key)
        self.assertIn('{"$decimal":"500.1250"}', reference_key)
        exponent_contract = build_option_contract_key(
            strike=decimal.Decimal("5.001250E+8")
        )
        exponent_key = semantic_observation_key(
            build_option_contract_reference(contract_key=exponent_contract)
        )
        self.assertIn('{"$decimal":"5.001250E+8"}', exponent_key)

        iv_key = semantic_observation_key(
            build_option_implied_volatility_observation(model_version=None)
        )
        self.assertIn('["model_version",null]', iv_key)

        non_utc = datetime.timezone(datetime.timedelta(hours=-5))
        observed_at = datetime.datetime(
            2030, 1, 2, 10, 30, 0, 123456, tzinfo=non_utc
        )
        source = build_source_reference(
            observed_at=observed_at,
            retrieved_at=observed_at + datetime.timedelta(seconds=2),
        )
        metadata = build_normalization_metadata((source,))
        key = semantic_observation_key(
            build_underlying_quote_observation(metadata=metadata)
        )
        self.assertIn(
            '{"$datetime":"2030-01-02T15:30:00.123456Z"}', key
        )

    def test_canonical_payload_order_is_insertion_independent(self) -> None:
        first = {
            "record_type": "Synthetic",
            "underlying_key": {"symbol": "SPY", "listing_mic": None},
        }
        second = {
            "underlying_key": {"listing_mic": None, "symbol": "SPY"},
            "record_type": "Synthetic",
        }
        self.assertEqual(
            self.PREFIX + canonicalize_lineage_parameters(first),
            self.PREFIX + canonicalize_lineage_parameters(second),
        )

    def test_exact_type_boundary_rejects_unsupported_and_subclass_values(self) -> None:
        base = build_underlying_quote_observation()

        @dataclasses.dataclass(frozen=True)
        class QuoteSubclass(UnderlyingQuoteObservation):
            pass

        subclass = QuoteSubclass(**{
            field.name: getattr(base, field.name)
            for field in dataclasses.fields(UnderlyingQuoteObservation)
        })
        unsupported = (
            object(), base.metadata, base.underlying_key,
            build_option_contract_key(), base.metadata.source_references[0],
            subclass,
        )
        for value in unsupported:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(TypeError):
                    semantic_observation_key(value)

    def test_excluded_value_state_and_reference_corrections_keep_key(self) -> None:
        greek_base = build_option_greeks_observation(
            delta=decimal.Decimal("0.50"), gamma=None, theta=None, vega=None,
            theta_day_basis=None,
        )
        cases = (
            (build_underlying_quote_observation(),
             build_underlying_quote_observation(
                 bid_price=decimal.Decimal("499.90"),
                 ask_price=decimal.Decimal("500.10"))),
            (build_option_contract_reference(),
             build_option_contract_reference(
                 exercise_style="European", settlement_type="Cash")),
            (build_option_volume_observation(),
             build_option_volume_observation(
                 cumulative_volume=1500, is_session_complete=True)),
            (build_option_open_interest_observation(),
             build_option_open_interest_observation(open_interest=6000)),
            (build_option_implied_volatility_observation(),
             build_option_implied_volatility_observation(
                 implied_volatility=decimal.Decimal("0.225"))),
            (greek_base, dataclasses.replace(
                greek_base, gamma=decimal.Decimal("0.02"))),
            (build_underlying_daily_bar_observation(),
             build_underlying_daily_bar_observation(
                 open_price=decimal.Decimal("499"),
                 high_price=decimal.Decimal("503"),
                 low_price=decimal.Decimal("498"),
                 close_price=decimal.Decimal("502"),
                 adjusted_close_price=decimal.Decimal("501.5"),
                 volume=76000000,
                 adjustment_methodology="Corrected total-return adjustment")),
            (build_rate_curve_point_observation(),
             build_rate_curve_point_observation(
                 annualized_rate=decimal.Decimal("0.043"))),
            (build_dividend_observation(),
             build_dividend_observation(
                 payment_date=datetime.date(2030, 3, 2),
                 cash_amount=decimal.Decimal("1.80"))),
        )
        for original, correction in cases:
            with self.subTest(record_type=type(original).__name__):
                before = repr(original)
                self.assertEqual(
                    semantic_observation_key(original),
                    semantic_observation_key(correction),
                )
                self.assertEqual(repr(original), before)

    def test_provider_provenance_revision_and_correction_are_key_neutral(self) -> None:
        first = build_underlying_quote_observation(
            metadata=build_provider_variant_metadata("a", "provider-a-quote")
        )
        corrected = build_underlying_quote_observation(
            metadata=build_provider_variant_metadata("b", "provider-b-quote")
        )
        self.assertNotEqual(
            first.metadata.source_references[0].provider_name,
            corrected.metadata.source_references[0].provider_name,
        )
        self.assertEqual(
            corrected.metadata.source_references[0].revision_number, 7
        )
        self.assertEqual(
            semantic_observation_key(first),
            semantic_observation_key(corrected),
        )

    def test_effective_time_participates_for_exactly_five_types(self) -> None:
        included = (
            build_underlying_quote_observation(),
            build_option_quote_observation(),
            build_option_volume_observation(),
            build_option_implied_volatility_observation(),
            build_option_greeks_observation(),
        )
        excluded = (
            build_option_contract_reference(),
            build_option_open_interest_observation(),
            build_underlying_daily_bar_observation(),
            build_rate_curve_point_observation(),
            build_dividend_observation(),
        )
        later = OBSERVED_AT + datetime.timedelta(microseconds=1)
        for record in included + excluded:
            changed = dataclasses.replace(
                record, metadata=self.metadata_with_effective_time(record, later)
            )
            keys_equal = (
                semantic_observation_key(record)
                == semantic_observation_key(changed)
            )
            with self.subTest(record_type=type(record).__name__):
                self.assertEqual(keys_equal, record in excluded)

    def test_identity_field_changes_produce_different_keys(self) -> None:
        quote = build_underlying_quote_observation()
        option_quote = build_option_quote_observation()
        iv = build_option_implied_volatility_observation()
        greeks = build_option_greeks_observation()
        rate = build_rate_curve_point_observation()
        dividend = build_dividend_observation()
        venue_quote = build_option_quote_observation(
            quote_scope=QuoteScope.VENUE_SPECIFIC, venue_mic="XNAS"
        )
        cases = (
            (quote, build_underlying_quote_observation(
                underlying_key=build_underlying_key(symbol="QQQ"))),
            (build_option_contract_reference(), build_option_contract_reference(
                contract_key=build_option_contract_key(
                    expiration=datetime.date(2030, 4, 19)))),
            (quote, build_underlying_quote_observation(
                market_phase=MarketPhase.PRE_MARKET)),
            (option_quote, venue_quote),
            (build_option_volume_observation(), dataclasses.replace(
                build_option_volume_observation(),
                metadata=self.metadata_with_effective_time(
                    build_option_volume_observation(),
                    OBSERVED_AT + datetime.timedelta(microseconds=1)))),
            (build_option_open_interest_observation(),
             build_option_open_interest_observation(
                 open_interest_session_date=datetime.date(2029, 12, 31))),
            (iv, dataclasses.replace(iv, model_name="Other model")),
            (iv, dataclasses.replace(iv, model_version=None)),
            (iv, dataclasses.replace(
                iv, rate_input_description="Other rate input")),
            (greeks, dataclasses.replace(
                greeks, dividend_input_description="Other dividend input")),
            (build_underlying_daily_bar_observation(),
             build_underlying_daily_bar_observation(
                 session_date=datetime.date(2030, 1, 3))),
            (rate, dataclasses.replace(rate, curve_id="USD-OTHER-OIS")),
            (rate, dataclasses.replace(rate, tenor_days=60)),
            (rate, dataclasses.replace(
                rate, effective_date=datetime.date(2030, 1, 3))),
            (rate, dataclasses.replace(
                rate, compounding_convention="Simple")),
            (rate, dataclasses.replace(
                rate, day_count_convention="Actual/360")),
            (dividend, dataclasses.replace(
                dividend, ex_date=datetime.date(2030, 2, 16))),
            (dividend, dataclasses.replace(
                dividend, dividend_type="Special Cash")),
            (dividend, dataclasses.replace(
                dividend, status=DividendStatus.HISTORICAL)),
        )
        for original, changed in cases:
            with self.subTest(record_type=type(original).__name__):
                self.assertNotEqual(
                    semantic_observation_key(original),
                    semantic_observation_key(changed),
                )


class SelectedFreshBindingSurfaceAndCandidateTests(unittest.TestCase):
    def test_exact_function_signature_fields_properties_and_frozen_behavior(
        self,
    ) -> None:
        signature = inspect.signature(bind_selected_fresh_market_data)
        self.assertEqual(
            tuple(signature.parameters),
            (
                "candidates", "correction_evaluated_at",
                "correction_rule_id", "correction_rule_version",
                "freshness_policy", "freshness_context",
            ),
        )
        self.assertTrue(all(
            parameter.default is inspect.Parameter.empty
            for parameter in signature.parameters.values()
        ))
        self.assertIs(signature.return_annotation, SelectedFreshMarketDataBinding)

        binding = bind_fresh_candidates((build_underlying_quote_observation(),))
        fields = tuple(
            field.name for field in dataclasses.fields(binding)
        )
        self.assertEqual(fields, (
            "candidate_records", "correction_selection", "freshness_policy",
            "freshness_context", "freshness_assessment",
        ))
        self.assertNotIn("semantic_observation_key", fields)
        self.assertNotIn("selected_record", fields)
        self.assertEqual(
            binding.semantic_observation_key,
            binding.correction_selection.semantic_observation_key,
        )
        self.assertIs(binding.selected_record, binding.candidate_records[0])
        with self.assertRaises(FrozenInstanceError):
            binding.freshness_context = build_freshness_context()  # type: ignore[misc]

    def test_all_ten_exact_normalized_record_types_are_supported(self) -> None:
        records = (
            build_underlying_quote_observation(),
            build_option_contract_reference(),
            build_option_quote_observation(),
            build_option_volume_observation(),
            build_option_open_interest_observation(),
            build_option_implied_volatility_observation(),
            build_option_greeks_observation(),
            build_underlying_daily_bar_observation(),
            build_rate_curve_point_observation(),
            build_dividend_observation(),
        )
        self.assertEqual(len(records), 10)
        for record in records:
            with self.subTest(record_type=type(record).__name__):
                binding = bind_fresh_candidates((record,))
                self.assertIs(binding.selected_record, record)

    def test_tuple_and_list_are_accepted_canonicalized_and_equal(self) -> None:
        older = build_correction_quote_observation("candidate-z", (1, 1))
        newer = build_correction_quote_observation("candidate-a", (2, 1))
        tuple_binding = bind_fresh_candidates((older, newer))
        list_binding = bind_fresh_candidates([newer, older])
        self.assertIs(type(list_binding.candidate_records), tuple)
        self.assertEqual(
            tuple(record.metadata.record_id for record in list_binding.candidate_records),
            ("candidate-a", "candidate-z"),
        )
        self.assertEqual(tuple_binding, list_binding)
        self.assertIs(list_binding.selected_record, newer)

    def test_wrong_container_empty_duplicate_and_mixed_groups_are_rejected(
        self,
    ) -> None:
        record = build_underlying_quote_observation()
        with self.assertRaisesRegex(TypeError, "tuple or list"):
            bind_fresh_candidates({record})
        binding = bind_fresh_candidates((record,))
        with self.assertRaisesRegex(TypeError, "tuple or list"):
            reconstruct_binding(binding, candidate_records={record})
        with self.assertRaisesRegex(ValueError, "at least one"):
            bind_fresh_candidates(())
        with self.assertRaisesRegex(ValueError, "duplicates"):
            bind_fresh_candidates((record, record))
        option_quote = build_option_quote_observation()
        option_quote = dataclasses.replace(
            option_quote,
            metadata=dataclasses.replace(
                option_quote.metadata, record_id="option-quote-mixed"
            ),
        )
        with self.assertRaisesRegex(ValueError, "semantic observation key"):
            bind_fresh_candidates((record, option_quote))

    def test_unsupported_element_and_supported_record_subclass_are_rejected(
        self,
    ) -> None:
        with self.assertRaisesRegex(TypeError, "exact supported"):
            bind_fresh_candidates((object(),))

        class UnderlyingQuoteSubclass(UnderlyingQuoteObservation):
            pass

        base = build_underlying_quote_observation()
        subclass = UnderlyingQuoteSubclass(**{
            field.name: getattr(base, field.name)
            for field in dataclasses.fields(base)
        })
        with self.assertRaisesRegex(TypeError, "exact supported"):
            bind_fresh_candidates((subclass,))

    def test_public_policy_context_and_direct_sidecars_require_exact_types(
        self,
    ) -> None:
        class PolicySubclass(MarketDataFreshnessPolicy):
            pass

        class ContextSubclass(FreshnessContext):
            pass

        policy = build_freshness_policy()
        context = build_freshness_context()
        policy_subclass = PolicySubclass(**{
            field.name: getattr(policy, field.name)
            for field in dataclasses.fields(policy)
        })
        context_subclass = ContextSubclass(**{
            field.name: getattr(context, field.name)
            for field in dataclasses.fields(context)
        })
        record = build_underlying_quote_observation()
        with self.assertRaises(TypeError):
            bind_fresh_candidates((record,), freshness_policy=policy_subclass)
        with self.assertRaises(TypeError):
            bind_fresh_candidates((record,), freshness_context=context_subclass)

        binding = bind_fresh_candidates((record,))
        exact_type_cases = (
            ("correction_selection", binding.correction_selection),
            ("freshness_policy", binding.freshness_policy),
            ("freshness_context", binding.freshness_context),
            ("freshness_assessment", binding.freshness_assessment),
        )
        for field_name, value in exact_type_cases:
            subclass_type = type(
                f"{type(value).__name__}Subclass", (type(value),), {}
            )
            subclass_value = subclass_type(**{
                field.name: getattr(value, field.name)
                for field in dataclasses.fields(value)
            })
            with self.subTest(field=field_name), self.assertRaises(TypeError):
                reconstruct_binding(binding, **{field_name: subclass_value})


class SelectedFreshBindingCorrectionTests(unittest.TestCase):
    def test_one_candidate_uses_explicit_selector(self) -> None:
        record = build_underlying_quote_observation()
        binding = bind_fresh_candidates((record,))
        self.assertIs(
            binding.correction_selection.status,
            CorrectionSelectionStatus.SELECTED,
        )
        self.assertEqual(
            binding.correction_selection.reason_codes,
            (CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,),
        )
        self.assertEqual(
            binding.correction_selection.candidate_record_ids,
            (record.metadata.record_id,),
        )

    def test_dominating_revision_selects_exact_canonical_candidate(self) -> None:
        older = build_correction_quote_observation("candidate-z", (1, 1))
        newer = build_correction_quote_observation("candidate-a", (2, 1))
        binding = bind_fresh_candidates((older, newer))
        self.assertEqual(
            binding.correction_selection.reason_codes,
            (CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,),
        )
        self.assertEqual(
            binding.correction_selection.selected_record_id,
            "candidate-a",
        )
        self.assertIs(binding.selected_record, newer)
        self.assertIs(binding.selected_record, binding.candidate_records[0])

    def test_all_required_ambiguous_groups_raise_value_error(self) -> None:
        cases = {
            "missing-provider-id": (
                build_correction_quote_observation(
                    "a", (1,), source_overrides=({"provider_record_id": None},)
                ),
                build_correction_quote_observation("b", (2,)),
            ),
            "lineage-mismatch": (
                build_correction_quote_observation(
                    "a", (1,), lineage_names=("a",)
                ),
                build_correction_quote_observation(
                    "b", (2,), lineage_names=("b",)
                ),
            ),
            "tied": (
                build_correction_quote_observation("a", (2,)),
                build_correction_quote_observation("b", (2,)),
            ),
            "incomparable": (
                build_correction_quote_observation("a", (2, 1)),
                build_correction_quote_observation("b", (1, 2)),
            ),
        }
        for name, candidates in cases.items():
            with self.subTest(case=name), self.assertRaisesRegex(
                ValueError, "ambiguous"
            ):
                bind_fresh_candidates(candidates)

        tied_candidates = cases["tied"]
        semantic_key = semantic_observation_key(tied_candidates[0])
        ambiguous = select_correction_candidate(
            semantic_key,
            tuple(candidate.metadata for candidate in tied_candidates),
            EVALUATION_AT,
            "provider-correction-selection",
            "v0.1",
        )
        assessment = assess_market_data_freshness(
            tied_candidates[0],
            build_freshness_policy(),
            build_freshness_context(),
        )
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            SelectedFreshMarketDataBinding(
                candidate_records=tied_candidates,
                correction_selection=ambiguous,
                freshness_policy=build_freshness_policy(),
                freshness_context=build_freshness_context(),
                freshness_assessment=assessment,
            )

    def test_direct_constructor_rejects_all_derivable_selection_mismatches(
        self,
    ) -> None:
        baseline = bind_fresh_candidates((build_underlying_quote_observation(),))
        selection = baseline.correction_selection
        multi = bind_fresh_candidates((
            build_correction_quote_observation("a", (1, 1)),
            build_correction_quote_observation("b", (2, 1)),
        ))
        cases = (
            (baseline, dataclasses.replace(
                selection, semantic_observation_key="other semantic key"
            )),
            (baseline, dataclasses.replace(
                selection,
                candidate_record_ids=("other-record",),
                selected_record_id="other-record",
            )),
            (multi, dataclasses.replace(
                multi.correction_selection, selected_record_id="a"
            )),
            (baseline, dataclasses.replace(
                selection,
                selected_record_id=None,
                status=CorrectionSelectionStatus.AMBIGUOUS,
                reason_codes=(
                    CorrectionSelectionReasonCode.MISSING_PROVIDER_RECORD_ID,
                ),
            )),
            (baseline, dataclasses.replace(
                selection,
                reason_codes=(
                    CorrectionSelectionReasonCode.DOMINATING_REVISION_VECTOR_SELECTED,
                ),
            )),
        )
        labels = (
            "semantic-key", "candidate-ids", "selected-id", "status", "reason"
        )
        for label, (binding, forged) in zip(labels, cases):
            with self.subTest(field=label), self.assertRaisesRegex(
                ValueError, "correction_selection does not match"
            ):
                reconstruct_binding(binding, correction_selection=forged)

    def test_valid_alternative_correction_contexts_are_valid_and_unequal(
        self,
    ) -> None:
        record = build_underlying_quote_observation()
        baseline = bind_fresh_candidates((record,))
        alternatives = (
            bind_fresh_candidates(
                (record,), correction_rule_id="alternate-correction-rule"
            ),
            bind_fresh_candidates(
                (record,), correction_rule_version="v0.2"
            ),
            bind_fresh_candidates(
                (record,),
                correction_evaluated_at=(
                    NORMALIZED_AT + datetime.timedelta(seconds=1)
                ),
            ),
        )
        for alternative in alternatives:
            with self.subTest(selection=alternative.correction_selection):
                self.assertNotEqual(alternative, baseline)
                self.assertIs(alternative.selected_record, record)
                direct = reconstruct_binding(
                    alternative, candidate_records=[record]
                )
                self.assertEqual(direct, alternative)

    def test_invalid_correction_context_uses_existing_taxonomy(self) -> None:
        record = build_underlying_quote_observation()
        value_errors = (
            {"correction_rule_id": ""},
            {"correction_rule_version": " "},
            {"correction_evaluated_at": datetime.datetime(2030, 1, 2, 15, 31)},
            {"correction_evaluated_at": NORMALIZED_AT - datetime.timedelta(seconds=1)},
        )
        type_errors = (
            {"correction_rule_id": 1},
            {"correction_rule_version": object()},
        )
        for overrides in value_errors:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                bind_fresh_candidates((record,), **overrides)
        for overrides in type_errors:
            with self.subTest(overrides=overrides), self.assertRaises(TypeError):
                bind_fresh_candidates((record,), **overrides)


class SelectedFreshBindingFreshnessAndChronologyTests(unittest.TestCase):
    def test_fresh_quote_retains_complete_exact_assessment(self) -> None:
        record = build_underlying_quote_observation()
        policy = build_freshness_policy()
        context = build_freshness_context()
        binding = bind_fresh_candidates(
            (record,), freshness_policy=policy, freshness_context=context
        )
        expected = assess_market_data_freshness(record, policy, context)
        self.assertIs(binding.freshness_policy, policy)
        self.assertIs(binding.freshness_context, context)
        self.assertEqual(binding.freshness_assessment, expected)
        self.assertEqual(expected.effective_age_seconds, decimal.Decimal("60"))
        self.assertEqual(expected.oldest_source_age_seconds, decimal.Decimal("60"))
        self.assertEqual(
            expected.maximum_retrieval_lag_seconds_observed,
            decimal.Decimal("2"),
        )
        self.assertEqual(
            expected.source_observation_span_seconds, decimal.Decimal("0")
        )

    def test_stale_ineligible_and_unknown_results_are_rejected(self) -> None:
        cases = (
            (
                "stale",
                build_underlying_quote_observation(),
                build_freshness_policy(maximum_quote_age_seconds=59),
            ),
            (
                "ineligible",
                build_underlying_quote_observation(
                    market_phase=MarketPhase.PRE_MARKET
                ),
                build_freshness_policy(),
            ),
            (
                "unknown",
                build_underlying_quote_observation(
                    market_phase=MarketPhase.UNKNOWN
                ),
                build_freshness_policy(require_regular_session_quotes=False),
            ),
        )
        for name, record, policy in cases:
            assessment = assess_market_data_freshness(
                record, policy, build_freshness_context()
            )
            with self.subTest(status=name):
                self.assertEqual(assessment.status.value, name)
                with self.assertRaisesRegex(ValueError, "fresh within policy"):
                    bind_fresh_candidates((record,), freshness_policy=policy)

        stale_record = cases[0][1]
        stale_policy = cases[0][2]
        stale_context = build_freshness_context()
        stale_selection = select_correction_candidate(
            semantic_observation_key(stale_record),
            (stale_record.metadata,),
            EVALUATION_AT,
            "provider-correction-selection",
            "v0.1",
        )
        stale_assessment = assess_market_data_freshness(
            stale_record, stale_policy, stale_context
        )
        with self.assertRaisesRegex(ValueError, "fresh within policy"):
            SelectedFreshMarketDataBinding(
                candidate_records=(stale_record,),
                correction_selection=stale_selection,
                freshness_policy=stale_policy,
                freshness_context=stale_context,
                freshness_assessment=stale_assessment,
            )

    def test_date_based_record_retains_session_date_gap(self) -> None:
        record = build_option_open_interest_observation(
            open_interest_session_date=SESSION_DATE - datetime.timedelta(days=1)
        )
        binding = bind_fresh_candidates((record,))
        self.assertEqual(binding.freshness_assessment.session_date_gap_days, 1)
        self.assertIs(binding.freshness_assessment.status, FreshnessStatus.FRESH)

    def test_selection_chronology_before_equal_after_and_before_normalization(
        self,
    ) -> None:
        record = build_underlying_quote_observation()
        before = bind_fresh_candidates(
            (record,),
            correction_evaluated_at=NORMALIZED_AT + datetime.timedelta(seconds=1),
        )
        equal = bind_fresh_candidates((record,))
        self.assertLess(
            before.correction_selection.evaluated_at,
            before.freshness_context.evaluation_at,
        )
        self.assertEqual(
            equal.correction_selection.evaluated_at,
            equal.freshness_context.evaluation_at,
        )
        with self.assertRaisesRegex(ValueError, "must not be after"):
            bind_fresh_candidates(
                (record,),
                correction_evaluated_at=EVALUATION_AT + datetime.timedelta(seconds=1),
            )
        with self.assertRaisesRegex(ValueError, "normalized by evaluated_at"):
            bind_fresh_candidates(
                (record,),
                correction_evaluated_at=NORMALIZED_AT - datetime.timedelta(seconds=1),
            )

    def test_direct_constructor_rejects_every_freshness_field_mismatch(
        self,
    ) -> None:
        binding = bind_fresh_candidates((build_underlying_quote_observation(),))
        assessment = binding.freshness_assessment
        forged_assessments = {
            "record_id": dataclasses.replace(assessment, record_id="other-record"),
            "category": dataclasses.replace(
                assessment, category=MarketDataCategory.ANALYTICS
            ),
            "status/reasons": dataclasses.replace(
                assessment,
                status=FreshnessStatus.STALE,
                reason_codes=(FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,),
            ),
            "policy_id": dataclasses.replace(assessment, policy_id="other-policy"),
            "policy_version": dataclasses.replace(
                assessment, policy_version="v2"
            ),
            "evaluated_at": dataclasses.replace(
                assessment,
                evaluated_at=assessment.evaluated_at + datetime.timedelta(seconds=1),
            ),
            "effective_age_seconds": dataclasses.replace(
                assessment,
                effective_age_seconds=decimal.Decimal("61"),
                oldest_source_age_seconds=decimal.Decimal("61"),
            ),
            "oldest_source_age_seconds": dataclasses.replace(
                assessment,
                effective_age_seconds=decimal.Decimal("59"),
                oldest_source_age_seconds=decimal.Decimal("59"),
            ),
            "maximum_retrieval_lag_seconds_observed": dataclasses.replace(
                assessment,
                maximum_retrieval_lag_seconds_observed=decimal.Decimal("3"),
            ),
            "source_observation_span_seconds": dataclasses.replace(
                assessment,
                source_observation_span_seconds=decimal.Decimal("1"),
            ),
        }
        for field_name, forged in forged_assessments.items():
            with self.subTest(field=field_name), self.assertRaisesRegex(
                ValueError, "freshness_assessment does not match"
            ):
                reconstruct_binding(binding, freshness_assessment=forged)

        open_interest = bind_fresh_candidates(
            (build_option_open_interest_observation(),)
        )
        forged_gap = dataclasses.replace(
            open_interest.freshness_assessment, session_date_gap_days=2
        )
        with self.assertRaisesRegex(ValueError, "freshness_assessment does not match"):
            reconstruct_binding(
                open_interest, freshness_assessment=forged_gap
            )

    def test_public_function_and_direct_constructor_are_equivalent(self) -> None:
        first = build_correction_quote_observation("z", (1, 1))
        second = build_correction_quote_observation("a", (2, 1))
        public = bind_fresh_candidates((first, second))
        direct = SelectedFreshMarketDataBinding(
            candidate_records=[second, first],
            correction_selection=public.correction_selection,
            freshness_policy=public.freshness_policy,
            freshness_context=public.freshness_context,
            freshness_assessment=public.freshness_assessment,
        )
        self.assertEqual(direct, public)
        self.assertIs(direct.correction_selection, public.correction_selection)
        self.assertIs(direct.freshness_assessment, public.freshness_assessment)


class SelectedFreshBindingPrecedenceTests(unittest.TestCase):
    def test_public_top_level_and_element_precedence(self) -> None:
        context = build_freshness_context()
        with self.assertRaisesRegex(TypeError, "freshness_policy"):
            bind_selected_fresh_market_data(
                [], EVALUATION_AT, object(), object(), object(), context
            )
        with self.assertRaisesRegex(TypeError, "exact supported"):
            bind_selected_fresh_market_data(
                [object(), object()],
                EVALUATION_AT,
                object(),
                object(),
                build_freshness_policy(),
                context,
            )
        with self.assertRaisesRegex(TypeError, "rule_id must be a string"):
            bind_fresh_candidates(
                (build_underlying_quote_observation(),),
                correction_rule_id=object(),
            )

    def test_direct_top_level_chronology_and_freshness_precedence(self) -> None:
        with self.assertRaisesRegex(TypeError, "correction_selection"):
            SelectedFreshMarketDataBinding([], object(), object(), object(), object())

        baseline = bind_fresh_candidates((build_underlying_quote_observation(),))
        late_at = EVALUATION_AT + datetime.timedelta(seconds=1)
        late_selection = select_correction_candidate(
            baseline.semantic_observation_key,
            tuple(record.metadata for record in baseline.candidate_records),
            late_at,
            baseline.correction_selection.rule_id,
            baseline.correction_selection.rule_version,
        )
        forged_freshness = dataclasses.replace(
            baseline.freshness_assessment, record_id="forged-record"
        )
        with self.assertRaisesRegex(ValueError, "must not be after"):
            reconstruct_binding(
                baseline,
                correction_selection=late_selection,
                freshness_assessment=forged_freshness,
            )

        nonfresh_mismatch = dataclasses.replace(
            baseline.freshness_assessment,
            status=FreshnessStatus.STALE,
            reason_codes=(FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,),
        )
        with self.assertRaisesRegex(
            ValueError, "freshness_assessment does not match"
        ):
            reconstruct_binding(
                baseline, freshness_assessment=nonfresh_mismatch
            )


class SnapshotTimingSurfaceAndValidationTests(unittest.TestCase):
    def test_signature_fields_properties_and_frozen_behavior(self) -> None:
        signature = inspect.signature(assess_market_data_snapshot_timing)
        self.assertEqual(tuple(signature.parameters), ("bindings",))
        self.assertIs(
            signature.parameters["bindings"].annotation, object
        )
        self.assertIs(
            signature.return_annotation,
            MarketDataSnapshotTimingAssessment,
        )
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(
                    MarketDataSnapshotTimingAssessment
                )
            ),
            ("bindings",),
        )
        property_names = (
            "is_temporally_coherent",
            "reason_codes",
            "common_freshness_policy",
            "common_freshness_context",
            "effective_time_span_seconds",
            "source_observation_span_seconds",
        )
        self.assertTrue(all(
            isinstance(
                getattr(MarketDataSnapshotTimingAssessment, name), property
            )
            for name in property_names
        ))
        binding = build_timing_binding(
            build_underlying_quote_observation()
        )
        assessment = assess_market_data_snapshot_timing((binding,))
        with self.assertRaises(FrozenInstanceError):
            assessment.bindings = ()  # type: ignore[misc]

    def test_exact_tuple_and_list_succeed(self) -> None:
        binding = build_timing_binding(
            build_underlying_quote_observation()
        )
        tuple_result = assess_market_data_snapshot_timing((binding,))
        list_input = [binding]
        list_result = assess_market_data_snapshot_timing(list_input)
        self.assertEqual(tuple_result, list_result)
        self.assertIs(type(tuple_result.bindings), tuple)
        self.assertIs(type(list_result.bindings), tuple)
        self.assertIs(tuple_result.bindings[0], binding)
        self.assertIs(list_result.bindings[0], binding)
        self.assertEqual(list_input, [binding])

    def test_container_subclasses_and_other_containers_are_rejected(self) -> None:
        binding = build_timing_binding(
            build_underlying_quote_observation()
        )

        class TupleSubclass(tuple):
            pass

        class ListSubclass(list):
            pass

        class CustomSequence:
            def __iter__(self):
                return iter((binding,))

        cases = (
            TupleSubclass((binding,)),
            ListSubclass([binding]),
            (item for item in (binding,)),
            {binding.selected_record.metadata.record_id},
            CustomSequence(),
        )
        for value in cases:
            with self.subTest(container=type(value).__name__):
                with self.assertRaisesRegex(TypeError, "exact tuple or list"):
                    assess_market_data_snapshot_timing(value)

    def test_element_subclass_raw_record_and_objects_are_rejected(self) -> None:
        binding = build_timing_binding(
            build_underlying_quote_observation()
        )

        class BindingSubclass(SelectedFreshMarketDataBinding):
            pass

        subclass = BindingSubclass(**{
            field.name: getattr(binding, field.name)
            for field in dataclasses.fields(binding)
        })
        cases = (
            subclass,
            build_underlying_quote_observation(),
            object(),
        )
        for value in cases:
            with self.subTest(element=type(value).__name__):
                with self.assertRaisesRegex(
                    TypeError, "exact type SelectedFreshMarketDataBinding"
                ):
                    assess_market_data_snapshot_timing((value,))

        with self.assertRaisesRegex(
            TypeError, "exact type SelectedFreshMarketDataBinding"
        ):
            assess_market_data_snapshot_timing((object(), binding))

    def test_empty_inputs_follow_element_then_value_precedence(self) -> None:
        for value in ((), []):
            with self.subTest(container=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "at least one"):
                    assess_market_data_snapshot_timing(value)
        with self.assertRaises(TypeError):
            assess_market_data_snapshot_timing([object(), object()])

    def test_duplicate_rules_and_selected_id_precedence(self) -> None:
        repeated = build_timing_binding(
            build_timed_record(
                build_underlying_quote_observation, "repeated", (datetime.timedelta(0),)
            )
        )
        with self.assertRaisesRegex(ValueError, "selected record IDs"):
            assess_market_data_snapshot_timing((repeated, repeated))

        same_key_first = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "same-key-a",
            (datetime.timedelta(0),),
        ))
        same_key_second = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "same-key-b",
            (datetime.timedelta(0),),
        ))
        self.assertNotEqual(
            same_key_first.selected_record.metadata.record_id,
            same_key_second.selected_record.metadata.record_id,
        )
        with self.assertRaisesRegex(ValueError, "semantic observation keys"):
            assess_market_data_snapshot_timing((
                same_key_first, same_key_second,
            ))

        duplicate_id_first = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "duplicate-id",
            (datetime.timedelta(0),),
        ))
        duplicate_id_second = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "duplicate-id",
            (datetime.timedelta(microseconds=1),),
        ))
        self.assertNotEqual(
            duplicate_id_first.semantic_observation_key,
            duplicate_id_second.semantic_observation_key,
        )
        with self.assertRaisesRegex(ValueError, "selected record IDs"):
            assess_market_data_snapshot_timing((
                duplicate_id_first, duplicate_id_second,
            ))

        simultaneous_first = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "simultaneous-id",
            (datetime.timedelta(0),),
        ))
        simultaneous_second = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "simultaneous-id",
            (datetime.timedelta(0),),
        ))
        self.assertEqual(
            simultaneous_first.semantic_observation_key,
            simultaneous_second.semantic_observation_key,
        )
        with self.assertRaisesRegex(ValueError, "selected record IDs"):
            assess_market_data_snapshot_timing((
                simultaneous_first, simultaneous_second,
            ))


class SnapshotTimingCanonicalIdentityTests(unittest.TestCase):
    def test_canonical_order_permutation_equality_and_identity(self) -> None:
        first = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "canonical-z",
            (datetime.timedelta(0),),
        ))
        second = build_timing_binding(build_timed_record(
            build_option_volume_observation,
            "canonical-a",
            (datetime.timedelta(seconds=1),),
        ))
        supplied = [second, first]
        expected = tuple(sorted(
            supplied,
            key=lambda binding: (
                binding.semantic_observation_key,
                binding.selected_record.metadata.record_id,
            ),
        ))
        public = assess_market_data_snapshot_timing(supplied)
        permuted = assess_market_data_snapshot_timing((first, second))
        self.assertEqual(public, permuted)
        self.assertEqual(supplied, [second, first])
        for actual, original in zip(public.bindings, expected):
            self.assertIs(actual, original)
            self.assertIs(actual.selected_record, original.selected_record)
            self.assertIs(actual.freshness_policy, original.freshness_policy)
            self.assertIs(actual.freshness_context, original.freshness_context)
            self.assertIs(
                actual.correction_selection, original.correction_selection
            )
            self.assertIs(
                actual.freshness_assessment, original.freshness_assessment
            )

    def test_direct_and_public_construction_are_equivalent(self) -> None:
        first = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "direct-a",
            (datetime.timedelta(0),),
        ))
        second = build_timing_binding(build_timed_record(
            build_option_quote_observation,
            "direct-b",
            (datetime.timedelta(seconds=1),),
        ))
        public = assess_market_data_snapshot_timing([second, first])
        direct = MarketDataSnapshotTimingAssessment(
            bindings=(first, second)
        )
        self.assertEqual(public, direct)
        self.assertTrue(all(
            any(retained is original for original in (first, second))
            for retained in direct.bindings
        ))

    def test_same_record_type_with_different_semantic_keys_is_valid(self) -> None:
        bindings = tuple(
            build_timing_binding(build_timed_record(
                build_underlying_quote_observation,
                f"same-type-{index}",
                (datetime.timedelta(microseconds=index),),
            ))
            for index in (0, 1)
        )
        assessment = assess_market_data_snapshot_timing(bindings)
        self.assertEqual(len(assessment.bindings), 2)
        self.assertTrue(assessment.is_temporally_coherent)


class SnapshotTimingPolicyContextTests(unittest.TestCase):
    def test_common_equal_artifacts_return_first_canonical_objects(self) -> None:
        policies = (build_freshness_policy(), build_freshness_policy())
        contexts = (build_freshness_context(), build_freshness_context())
        self.assertIsNot(policies[0], policies[1])
        self.assertIsNot(contexts[0], contexts[1])
        bindings = (
            build_timing_binding(build_timed_record(
                build_underlying_quote_observation,
                "equal-artifact-a",
                (datetime.timedelta(0),),
            ), policies[0], contexts[0]),
            build_timing_binding(build_timed_record(
                build_option_volume_observation,
                "equal-artifact-b",
                (datetime.timedelta(seconds=1),),
            ), policies[1], contexts[1]),
        )
        assessment = assess_market_data_snapshot_timing(bindings)
        self.assertIs(
            assessment.common_freshness_policy,
            assessment.bindings[0].freshness_policy,
        )
        self.assertIs(
            assessment.common_freshness_context,
            assessment.bindings[0].freshness_context,
        )

    def test_mixed_policy_uses_complete_structural_equality(self) -> None:
        context = build_freshness_context()
        policies = (
            build_freshness_policy(maximum_cross_record_skew_seconds=10),
            build_freshness_policy(maximum_cross_record_skew_seconds=11),
        )
        bindings = (
            build_timing_binding(build_timed_record(
                build_underlying_quote_observation,
                "mixed-policy-a",
                (datetime.timedelta(0),),
            ), policies[0], context),
            build_timing_binding(build_timed_record(
                build_option_volume_observation,
                "mixed-policy-b",
                (datetime.timedelta(seconds=12),),
            ), policies[1], context),
        )
        assessment = assess_market_data_snapshot_timing(bindings)
        self.assertIsNone(assessment.common_freshness_policy)
        self.assertIs(assessment.common_freshness_context, context)
        self.assertEqual(
            assessment.effective_time_span_seconds, decimal.Decimal("12")
        )
        self.assertEqual(
            assessment.source_observation_span_seconds,
            decimal.Decimal("12"),
        )
        self.assertEqual(assessment.reason_codes, (
            MarketDataSnapshotTimingReasonCode.MIXED_FRESHNESS_POLICY,
        ))

    def test_mixed_context_covers_both_complete_fields(self) -> None:
        policy = build_freshness_policy()
        base = build_freshness_context()
        contexts = (
            dataclasses.replace(
                base,
                evaluation_at=base.evaluation_at + datetime.timedelta(seconds=1),
            ),
            dataclasses.replace(
                base,
                latest_completed_session_date=(
                    base.latest_completed_session_date
                    + datetime.timedelta(days=1)
                ),
            ),
        )
        for label, changed in zip(("evaluation", "session"), contexts):
            bindings = (
                build_timing_binding(build_timed_record(
                    build_underlying_quote_observation,
                    f"mixed-context-{label}-a",
                    (datetime.timedelta(0),),
                ), policy, base),
                build_timing_binding(build_timed_record(
                    build_option_volume_observation,
                    f"mixed-context-{label}-b",
                    (datetime.timedelta(seconds=12),),
                ), policy, changed),
            )
            assessment = assess_market_data_snapshot_timing(bindings)
            with self.subTest(field=label):
                self.assertIs(assessment.common_freshness_policy, policy)
                self.assertIsNone(assessment.common_freshness_context)
                self.assertEqual(assessment.reason_codes, (
                    MarketDataSnapshotTimingReasonCode.MIXED_FRESHNESS_CONTEXT,
                ))
                self.assertEqual(
                    assessment.effective_time_span_seconds,
                    decimal.Decimal("12"),
                )

    def test_both_mixed_reasons_are_ordered_and_suppress_thresholds(self) -> None:
        first_policy = build_freshness_policy(
            maximum_cross_record_skew_seconds=1
        )
        second_policy = build_freshness_policy(
            maximum_cross_record_skew_seconds=2
        )
        first_context = build_freshness_context()
        second_context = dataclasses.replace(
            first_context,
            evaluation_at=(
                first_context.evaluation_at + datetime.timedelta(seconds=1)
            ),
        )
        bindings = (
            build_timing_binding(build_timed_record(
                build_underlying_quote_observation,
                "both-mixed-a",
                (datetime.timedelta(0),),
            ), first_policy, first_context),
            build_timing_binding(build_timed_record(
                build_option_volume_observation,
                "both-mixed-b",
                (datetime.timedelta(seconds=20),),
            ), second_policy, second_context),
        )
        assessment = assess_market_data_snapshot_timing(bindings)
        self.assertEqual(assessment.reason_codes, (
            MarketDataSnapshotTimingReasonCode.MIXED_FRESHNESS_POLICY,
            MarketDataSnapshotTimingReasonCode.MIXED_FRESHNESS_CONTEXT,
        ))
        self.assertEqual(len(set(assessment.reason_codes)), 2)
        self.assertFalse(assessment.is_temporally_coherent)
        self.assertEqual(
            assessment.source_observation_span_seconds,
            decimal.Decimal("20"),
        )


class SnapshotTimingParticipantAndMetricTests(unittest.TestCase):
    INCLUDED_BUILDERS = (
        build_underlying_quote_observation,
        build_option_quote_observation,
        build_option_volume_observation,
        build_option_implied_volatility_observation,
        build_option_greeks_observation,
    )
    EXCLUDED_BUILDERS = (
        build_option_contract_reference,
        build_option_open_interest_observation,
        build_underlying_daily_bar_observation,
        build_rate_curve_point_observation,
        build_dividend_observation,
    )

    def test_each_included_type_contributes_effective_and_all_source_times(
        self,
    ) -> None:
        for index, builder in enumerate(self.INCLUDED_BUILDERS):
            record = build_timed_record(
                builder,
                f"included-{index}",
                (
                    datetime.timedelta(0),
                    datetime.timedelta(microseconds=1),
                ),
                effective_offset=datetime.timedelta(0),
            )
            assessment = assess_market_data_snapshot_timing((
                build_timing_binding(record),
            ))
            with self.subTest(record_type=type(record).__name__):
                self.assertEqual(
                    assessment.effective_time_span_seconds,
                    decimal.Decimal("0"),
                )
                self.assertEqual(
                    assessment.source_observation_span_seconds,
                    decimal.Decimal("0.000001"),
                )

    def test_each_excluded_type_is_retained_but_contributes_no_times(
        self,
    ) -> None:
        for index, builder in enumerate(self.EXCLUDED_BUILDERS):
            record = build_timed_record(
                builder,
                f"excluded-{index}",
                (
                    datetime.timedelta(seconds=-1),
                    datetime.timedelta(0),
                ),
                effective_offset=datetime.timedelta(0),
            )
            binding = build_timing_binding(record)
            assessment = assess_market_data_snapshot_timing((binding,))
            with self.subTest(record_type=type(record).__name__):
                self.assertIs(assessment.bindings[0], binding)
                self.assertIsNone(assessment.effective_time_span_seconds)
                self.assertIsNone(
                    assessment.source_observation_span_seconds
                )
                self.assertTrue(assessment.is_temporally_coherent)

    def test_multiple_participants_are_microsecond_exact_and_permutation_safe(
        self,
    ) -> None:
        first = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "microsecond-a",
            (datetime.timedelta(0),),
        ))
        second = build_timing_binding(build_timed_record(
            build_option_volume_observation,
            "microsecond-b",
            (datetime.timedelta(seconds=2, microseconds=3),),
        ))
        forward = assess_market_data_snapshot_timing((first, second))
        reverse = assess_market_data_snapshot_timing((second, first))
        self.assertEqual(forward, reverse)
        self.assertEqual(
            forward.effective_time_span_seconds,
            decimal.Decimal("2.000003"),
        )
        self.assertEqual(
            forward.source_observation_span_seconds,
            decimal.Decimal("2.000003"),
        )
        self.assertEqual(
            forward.effective_time_span_seconds.as_tuple().exponent, -6
        )

    def test_system_composite_and_old_source_are_fully_included(self) -> None:
        policy = build_freshness_policy(
            maximum_quote_age_seconds=100,
            maximum_source_observation_span_seconds=30,
            maximum_cross_record_skew_seconds=10,
        )
        record = build_timed_record(
            build_underlying_quote_observation,
            "system-composite",
            (
                datetime.timedelta(seconds=-20),
                datetime.timedelta(0),
            ),
            effective_offset=datetime.timedelta(0),
            system_composite=True,
        )
        assessment = assess_market_data_snapshot_timing((
            build_timing_binding(record, policy),
        ))
        self.assertEqual(
            assessment.effective_time_span_seconds, decimal.Decimal("0")
        )
        self.assertEqual(
            assessment.source_observation_span_seconds,
            decimal.Decimal("20"),
        )
        self.assertEqual(assessment.reason_codes, (
            MarketDataSnapshotTimingReasonCode
            .SOURCE_OBSERVATION_SPAN_EXCEEDED,
        ))

    def test_excluded_old_sources_do_not_widen_participant_metrics(self) -> None:
        participant = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "included-current",
            (datetime.timedelta(0),),
        ))
        excluded = build_timing_binding(build_timed_record(
            build_option_contract_reference,
            "excluded-old",
            (datetime.timedelta(seconds=-20),),
        ))
        assessment = assess_market_data_snapshot_timing((
            participant, excluded,
        ))
        self.assertEqual(
            assessment.effective_time_span_seconds, decimal.Decimal("0")
        )
        self.assertEqual(
            assessment.source_observation_span_seconds,
            decimal.Decimal("0"),
        )


class SnapshotTimingThresholdAndReasonTests(unittest.TestCase):
    def _two_single_source_assessment(
        self, span: datetime.timedelta, threshold: int
    ) -> MarketDataSnapshotTimingAssessment:
        policy = build_freshness_policy(
            maximum_cross_record_skew_seconds=threshold
        )
        context = build_freshness_context()
        bindings = (
            build_timing_binding(build_timed_record(
                build_underlying_quote_observation,
                f"threshold-a-{span}",
                (datetime.timedelta(0),),
            ), policy, context),
            build_timing_binding(build_timed_record(
                build_option_volume_observation,
                f"threshold-b-{span}",
                (span,),
            ), policy, context),
        )
        return assess_market_data_snapshot_timing(bindings)

    def test_below_and_equal_threshold_are_coherent(self) -> None:
        for label, span in (
            ("below", datetime.timedelta(seconds=9, microseconds=999999)),
            ("equal", datetime.timedelta(seconds=10)),
        ):
            assessment = self._two_single_source_assessment(span, 10)
            with self.subTest(boundary=label):
                self.assertEqual(assessment.reason_codes, ())
                self.assertTrue(assessment.is_temporally_coherent)

    def test_source_only_exceeded_is_valid_incoherence(self) -> None:
        policy = build_freshness_policy(
            maximum_source_observation_span_seconds=20,
            maximum_cross_record_skew_seconds=10,
        )
        record = build_timed_record(
            build_underlying_quote_observation,
            "source-only",
            (
                datetime.timedelta(0),
                datetime.timedelta(seconds=12),
            ),
            effective_offset=datetime.timedelta(seconds=6),
        )
        assessment = assess_market_data_snapshot_timing((
            build_timing_binding(record, policy),
        ))
        self.assertIsInstance(
            assessment, MarketDataSnapshotTimingAssessment
        )
        self.assertEqual(assessment.reason_codes, (
            MarketDataSnapshotTimingReasonCode
            .SOURCE_OBSERVATION_SPAN_EXCEEDED,
        ))
        self.assertFalse(assessment.is_temporally_coherent)

    def test_effective_exceeded_implies_source_exceeded_for_valid_records(
        self,
    ) -> None:
        assessment = self._two_single_source_assessment(
            datetime.timedelta(seconds=11), 10
        )
        self.assertGreaterEqual(
            assessment.source_observation_span_seconds,
            assessment.effective_time_span_seconds,
        )
        self.assertEqual(assessment.reason_codes, (
            MarketDataSnapshotTimingReasonCode.EFFECTIVE_TIME_SPAN_EXCEEDED,
            MarketDataSnapshotTimingReasonCode
            .SOURCE_OBSERVATION_SPAN_EXCEEDED,
        ))
        self.assertEqual(len(set(assessment.reason_codes)), 2)

    def test_none_metrics_have_empty_reasons(self) -> None:
        bindings = (
            build_timing_binding(build_option_contract_reference()),
            build_timing_binding(build_rate_curve_point_observation()),
        )
        assessment = assess_market_data_snapshot_timing(bindings)
        self.assertIsNone(assessment.effective_time_span_seconds)
        self.assertIsNone(assessment.source_observation_span_seconds)
        self.assertEqual(assessment.reason_codes, ())
        self.assertTrue(assessment.is_temporally_coherent)

    def test_reason_order_is_declaration_order_not_alphabetical(self) -> None:
        assessment = self._two_single_source_assessment(
            datetime.timedelta(seconds=11), 10
        )
        values = tuple(reason.value for reason in assessment.reason_codes)
        self.assertEqual(values, (
            "effective_time_span_exceeded",
            "source_observation_span_exceeded",
        ))
        self.assertNotEqual(values, tuple(sorted(values, reverse=True)))


class SnapshotTimingLocalePurityAndScopeTests(unittest.TestCase):
    def test_locale_sensitive_ordering_is_never_called(self) -> None:
        first = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "locale-Z",
            (datetime.timedelta(0),),
        ))
        second = build_timing_binding(build_timed_record(
            build_option_volume_observation,
            "locale-a",
            (datetime.timedelta(seconds=11),),
        ))
        original = locale.strxfrm
        locale.strxfrm = lambda value: (_ for _ in ()).throw(
            AssertionError(value)
        )
        try:
            forward = assess_market_data_snapshot_timing((first, second))
            reverse = assess_market_data_snapshot_timing((second, first))
            self.assertEqual(forward, reverse)
            self.assertEqual(
                forward.effective_time_span_seconds,
                decimal.Decimal("11"),
            )
            self.assertEqual(
                tuple(forward.reason_codes),
                tuple(MarketDataSnapshotTimingReasonCode)[2:],
            )
        finally:
            locale.strxfrm = original

    def test_new_implementation_has_no_external_or_float_dependency(self) -> None:
        source = "\n".join((
            inspect.getsource(
                market_data._canonicalize_snapshot_timing_bindings
            ),
            inspect.getsource(market_data._derive_snapshot_timing_state),
            inspect.getsource(MarketDataSnapshotTimingAssessment),
            inspect.getsource(assess_market_data_snapshot_timing),
        ))
        prohibited = (
            "total_seconds(", "datetime.now", "date.today", "locale.",
            "random.", "os.environ", "open(", "requests", "socket",
            "provider", "CalculationLineage(", "CandidateResearchRecord(",
        )
        for token in prohibited:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_economically_unrelated_bindings_can_be_temporally_coherent(
        self,
    ) -> None:
        underlying = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "unrelated-underlying",
            (datetime.timedelta(0),),
        ))
        unrelated_contract = build_option_contract_key(
            underlying_key=build_underlying_key(symbol="QQQ")
        )
        option = build_timing_binding(build_timed_record(
            build_option_quote_observation,
            "unrelated-option",
            (datetime.timedelta(0),),
            contract_key=unrelated_contract,
        ))
        assessment = assess_market_data_snapshot_timing((
            underlying, option,
        ))
        self.assertTrue(assessment.is_temporally_coherent)
        self.assertEqual(assessment.reason_codes, ())


class BindingReferenceSurfaceAndConstructorTests(unittest.TestCase):
    EXPECTED_3C3_PUBLIC_NAMES = (
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
        "CorrectionSelectionStatus",
        "CorrectionSelectionReasonCode",
        "CorrectionSelection",
        "select_correction_candidate",
        "CalculationQualityFlag",
        "CalculationInputReference",
        "CalculationLineage",
        "canonicalize_lineage_parameters",
        "semantic_observation_key",
        "SelectedFreshMarketDataBinding",
        "bind_selected_fresh_market_data",
        "MarketDataSnapshotTimingReasonCode",
        "MarketDataSnapshotTimingAssessment",
        "assess_market_data_snapshot_timing",
    )

    def test_public_surface_signatures_fields_and_exclusions(self) -> None:
        additions = (
            "MarketDataBindingReference",
            "market_data_binding_reference",
            "resolve_market_data_binding_reference",
        )
        self.assertEqual(
            market_data.__all__[:42], self.EXPECTED_3C3_PUBLIC_NAMES
        )
        self.assertEqual(market_data.__all__[42:45], additions)
        self.assertEqual(len(market_data.__all__), 50)
        self.assertTrue(all(hasattr(market_data, name) for name in additions))

        factory_signature = inspect.signature(market_data_binding_reference)
        self.assertEqual(tuple(factory_signature.parameters), ("binding",))
        self.assertIs(factory_signature.parameters["binding"].annotation, object)
        self.assertIs(
            factory_signature.return_annotation, MarketDataBindingReference
        )
        resolver_signature = inspect.signature(
            resolve_market_data_binding_reference
        )
        self.assertEqual(
            tuple(resolver_signature.parameters),
            ("reference", "timing_assessment"),
        )
        self.assertTrue(all(
            parameter.annotation is object
            and parameter.default is inspect.Parameter.empty
            for parameter in resolver_signature.parameters.values()
        ))
        self.assertIs(
            resolver_signature.return_annotation,
            SelectedFreshMarketDataBinding,
        )
        self.assertEqual(
            tuple(
                field.name
                for field in dataclasses.fields(MarketDataBindingReference)
            ),
            ("semantic_observation_key", "selected_record_id"),
        )
        unauthorized = (
            "MarketDataRelationshipAssessment",
            "MarketDataRelationshipStatus",
            "MarketDataRelationshipIssue",
        )
        self.assertTrue(all(
            not hasattr(market_data, name) for name in unauthorized
        ))

    def test_constructor_normalizes_boundaries_and_preserves_content(self) -> None:
        cases = (
            ("Key", "Record", "Key", "Record"),
            (" \t\nKey\r ", "\n record-1\t", "Key", "record-1"),
            (
                "\u00a0\u2003Key\u2003\u00a0",
                "\u2003record-2\u00a0",
                "Key",
                "record-2",
            ),
            ("A B", "Record ID", "A B", "Record ID"),
            ("MiXeD", "Case-ID", "MiXeD", "Case-ID"),
        )
        for semantic_key, record_id, expected_key, expected_id in cases:
            with self.subTest(semantic_key=semantic_key, record_id=record_id):
                reference = MarketDataBindingReference(semantic_key, record_id)
                self.assertEqual(reference.semantic_observation_key, expected_key)
                self.assertEqual(reference.selected_record_id, expected_id)

        composed = MarketDataBindingReference("é", "record")
        decomposed = MarketDataBindingReference("e\u0301", "record")
        self.assertNotEqual(composed.semantic_observation_key,
                            decomposed.semantic_observation_key)

    def test_constructor_rejects_ascii_and_unicode_whitespace_only(self) -> None:
        for value in (" \t\n\r", "\u00a0\u2003"):
            with self.subTest(field="semantic", value=repr(value)):
                with self.assertRaises(ValueError):
                    MarketDataBindingReference(value, "record")
            with self.subTest(field="record", value=repr(value)):
                with self.assertRaises(ValueError):
                    MarketDataBindingReference("key", value)

    def test_constructor_requires_exact_builtin_strings(self) -> None:
        class StringSubclass(str):
            pass

        cases = (
            (StringSubclass("key"), "record", "semantic_observation_key"),
            (object(), "record", "semantic_observation_key"),
            ("key", StringSubclass("record"), "selected_record_id"),
            ("key", object(), "selected_record_id"),
        )
        for semantic_key, record_id, expected_field in cases:
            with self.subTest(field=expected_field):
                with self.assertRaisesRegex(TypeError, expected_field):
                    MarketDataBindingReference(semantic_key, record_id)

    def test_constructor_validation_precedence(self) -> None:
        with self.assertRaisesRegex(TypeError, "semantic_observation_key"):
            MarketDataBindingReference(object(), object())
        with self.assertRaisesRegex(TypeError, "selected_record_id"):
            MarketDataBindingReference("   ", object())
        with self.assertRaisesRegex(ValueError, "semantic_observation_key"):
            MarketDataBindingReference("   ", "\t")

    def test_constructor_is_frozen_and_structurally_equal(self) -> None:
        first = MarketDataBindingReference(" key ", " record ")
        second = MarketDataBindingReference("key", "record")
        self.assertEqual(first, second)
        with self.assertRaises(FrozenInstanceError):
            first.selected_record_id = "other"  # type: ignore[misc]


class BindingReferenceFactoryTests(unittest.TestCase):
    def test_factory_matches_direct_construction_without_mutation(self) -> None:
        binding = build_timing_binding(build_underlying_quote_observation())
        before = repr(binding)
        nested = (
            binding.selected_record,
            binding.candidate_records,
            binding.freshness_policy,
            binding.freshness_context,
            binding.correction_selection,
            binding.freshness_assessment,
        )
        reference = market_data_binding_reference(binding)
        direct = MarketDataBindingReference(
            binding.semantic_observation_key,
            binding.selected_record.metadata.record_id,
        )
        self.assertEqual(reference, direct)
        self.assertEqual(repr(binding), before)
        retained = (
            binding.selected_record,
            binding.candidate_records,
            binding.freshness_policy,
            binding.freshness_context,
            binding.correction_selection,
            binding.freshness_assessment,
        )
        for original, after in zip(nested, retained):
            self.assertIs(after, original)

    def test_factory_rejects_binding_subclass(self) -> None:
        binding = build_timing_binding(build_underlying_quote_observation())

        class BindingSubclass(SelectedFreshMarketDataBinding):
            pass

        subclass = BindingSubclass(**{
            field.name: getattr(binding, field.name)
            for field in dataclasses.fields(binding)
        })
        with self.assertRaisesRegex(TypeError, "exact type"):
            market_data_binding_reference(subclass)

    def test_factory_rejects_all_other_object_kinds(self) -> None:
        binding = build_timing_binding(build_underlying_quote_observation())
        assessment = assess_market_data_snapshot_timing((binding,))
        reference = MarketDataBindingReference("key", "record")
        cases = (
            build_underlying_quote_observation(),
            assessment,
            reference,
            object(),
        )
        for value in cases:
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(TypeError):
                    market_data_binding_reference(value)


class BindingReferenceResolverTests(unittest.TestCase):
    def test_exact_argument_types_subclasses_precedence_and_no_early_access(
        self,
    ) -> None:
        binding = build_timing_binding(build_underlying_quote_observation())
        assessment = assess_market_data_snapshot_timing((binding,))
        reference = market_data_binding_reference(binding)

        class ReferenceSubclass(MarketDataBindingReference):
            pass

        class AssessmentSubclass(MarketDataSnapshotTimingAssessment):
            pass

        reference_subclass = ReferenceSubclass(
            reference.semantic_observation_key, reference.selected_record_id
        )
        assessment_subclass = AssessmentSubclass(assessment.bindings)
        with self.assertRaisesRegex(TypeError, "reference"):
            resolve_market_data_binding_reference(
                reference_subclass, assessment
            )
        with self.assertRaisesRegex(TypeError, "timing_assessment"):
            resolve_market_data_binding_reference(
                reference, assessment_subclass
            )
        with self.assertRaisesRegex(TypeError, "reference"):
            resolve_market_data_binding_reference(object(), object())

        class BindingsTrap:
            @property
            def bindings(self):
                raise AssertionError("bindings accessed before exact type check")

        with self.assertRaisesRegex(TypeError, "timing_assessment"):
            resolve_market_data_binding_reference(reference, BindingsTrap())

    def test_known_pair_returns_exact_outer_and_nested_objects(self) -> None:
        first = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "identity-a",
            (datetime.timedelta(0),),
        ))
        second = build_timing_binding(build_timed_record(
            build_option_volume_observation,
            "identity-b",
            (datetime.timedelta(seconds=1),),
        ))
        assessment = assess_market_data_snapshot_timing((second, first))
        before_bindings = assessment.bindings
        target = assessment.bindings[1]
        reference = market_data_binding_reference(target)
        resolved = resolve_market_data_binding_reference(reference, assessment)
        self.assertIs(resolved, target)
        self.assertIs(assessment.bindings, before_bindings)
        self.assertIs(resolved.selected_record, target.selected_record)
        self.assertIs(resolved.candidate_records, target.candidate_records)
        self.assertIs(resolved.freshness_policy, target.freshness_policy)
        self.assertIs(resolved.freshness_context, target.freshness_context)
        self.assertIs(
            resolved.correction_selection, target.correction_selection
        )
        self.assertIs(
            resolved.freshness_assessment, target.freshness_assessment
        )

    def test_unknown_stale_and_forged_pairs_raise_value_error(self) -> None:
        binding = build_timing_binding(build_underlying_quote_observation())
        assessment = assess_market_data_snapshot_timing((binding,))
        key = binding.semantic_observation_key
        record_id = binding.selected_record.metadata.record_id
        stale_binding = build_timing_binding(build_timed_record(
            build_option_volume_observation,
            "stale-record",
            (datetime.timedelta(seconds=1),),
        ))
        cases = {
            "unknown-key": MarketDataBindingReference("unknown", record_id),
            "unknown-id": MarketDataBindingReference(key, "unknown"),
            "both-unknown": MarketDataBindingReference("unknown", "unknown"),
            "stale": market_data_binding_reference(stale_binding),
            "forged": MarketDataBindingReference(key, "forged-record"),
        }
        for label, reference in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(ValueError):
                    resolve_market_data_binding_reference(
                        reference, assessment
                    )

    def test_cross_paired_reference_is_rejected(self) -> None:
        first = build_timing_binding(build_timed_record(
            build_underlying_quote_observation,
            "cross-pair-a",
            (datetime.timedelta(0),),
        ))
        second = build_timing_binding(build_timed_record(
            build_option_volume_observation,
            "cross-pair-b",
            (datetime.timedelta(seconds=1),),
        ))
        assessment = assess_market_data_snapshot_timing((first, second))
        cross_pair = MarketDataBindingReference(
            first.semantic_observation_key,
            second.selected_record.metadata.record_id,
        )
        with self.assertRaises(ValueError):
            resolve_market_data_binding_reference(cross_pair, assessment)

    def test_cross_assessment_present_and_absent_behavior(self) -> None:
        first_record = build_timed_record(
            build_underlying_quote_observation,
            "portable-pair",
            (datetime.timedelta(0),),
        )
        second_record = build_timed_record(
            build_underlying_quote_observation,
            "portable-pair",
            (datetime.timedelta(0),),
        )
        binding_a = build_timing_binding(first_record)
        binding_b = build_timing_binding(second_record)
        assessment_a = assess_market_data_snapshot_timing((binding_a,))
        assessment_b = assess_market_data_snapshot_timing((binding_b,))
        self.assertIsNot(binding_a, binding_b)
        reference = market_data_binding_reference(assessment_a.bindings[0])
        self.assertIs(
            resolve_market_data_binding_reference(reference, assessment_b),
            assessment_b.bindings[0],
        )

        absent = assess_market_data_snapshot_timing((
            build_timing_binding(build_timed_record(
                build_option_volume_observation,
                "absent-pair",
                (datetime.timedelta(seconds=1),),
            )),
        ))
        with self.assertRaises(ValueError):
            resolve_market_data_binding_reference(reference, absent)

    def test_resolution_accepts_all_temporal_coherence_outcomes(self) -> None:
        policy = build_freshness_policy()
        context = build_freshness_context()
        coherent = assess_market_data_snapshot_timing((
            build_timing_binding(build_timed_record(
                build_underlying_quote_observation,
                "coherent",
                (datetime.timedelta(0),),
            ), policy, context),
        ))
        mixed_policy = assess_market_data_snapshot_timing((
            build_timing_binding(build_timed_record(
                build_underlying_quote_observation,
                "mixed-policy-a",
                (datetime.timedelta(0),),
            ), build_freshness_policy(maximum_cross_record_skew_seconds=10), context),
            build_timing_binding(build_timed_record(
                build_option_volume_observation,
                "mixed-policy-b",
                (datetime.timedelta(seconds=1),),
            ), build_freshness_policy(maximum_cross_record_skew_seconds=11), context),
        ))
        changed_context = dataclasses.replace(
            context,
            evaluation_at=context.evaluation_at + datetime.timedelta(seconds=1),
        )
        mixed_context = assess_market_data_snapshot_timing((
            build_timing_binding(build_timed_record(
                build_underlying_quote_observation,
                "mixed-context-a",
                (datetime.timedelta(0),),
            ), policy, context),
            build_timing_binding(build_timed_record(
                build_option_volume_observation,
                "mixed-context-b",
                (datetime.timedelta(seconds=1),),
            ), policy, changed_context),
        ))
        skew_policy = build_freshness_policy(
            maximum_cross_record_skew_seconds=10
        )
        skew = assess_market_data_snapshot_timing((
            build_timing_binding(build_timed_record(
                build_underlying_quote_observation,
                "skew-a",
                (datetime.timedelta(0),),
            ), skew_policy, context),
            build_timing_binding(build_timed_record(
                build_option_volume_observation,
                "skew-b",
                (datetime.timedelta(seconds=11),),
            ), skew_policy, context),
        ))
        self.assertTrue(coherent.is_temporally_coherent)
        self.assertFalse(mixed_policy.is_temporally_coherent)
        self.assertFalse(mixed_context.is_temporally_coherent)
        self.assertFalse(skew.is_temporally_coherent)
        for assessment in (coherent, mixed_policy, mixed_context, skew):
            target = assessment.bindings[0]
            with self.subTest(reasons=assessment.reason_codes):
                self.assertIs(
                    resolve_market_data_binding_reference(
                        market_data_binding_reference(target), assessment
                    ),
                    target,
                )

    def test_resolver_never_accesses_derived_timing_properties(self) -> None:
        binding = build_timing_binding(build_underlying_quote_observation())
        assessment = assess_market_data_snapshot_timing((binding,))
        reference = market_data_binding_reference(binding)
        property_names = (
            "is_temporally_coherent",
            "reason_codes",
            "common_freshness_policy",
            "common_freshness_context",
            "effective_time_span_seconds",
            "source_observation_span_seconds",
        )
        originals = {
            name: getattr(MarketDataSnapshotTimingAssessment, name)
            for name in property_names
        }

        def fail_on_access(_assessment):
            raise AssertionError("derived timing property was accessed")

        try:
            for name in property_names:
                setattr(
                    MarketDataSnapshotTimingAssessment,
                    name,
                    property(fail_on_access),
                )
            self.assertIs(
                resolve_market_data_binding_reference(reference, assessment),
                binding,
            )
        finally:
            for name, descriptor in originals.items():
                setattr(
                    MarketDataSnapshotTimingAssessment, name, descriptor
                )


class BindingReferencePurityTests(unittest.TestCase):
    def test_locale_transformations_are_never_called(self) -> None:
        binding = build_timing_binding(build_underlying_quote_observation())
        assessment = assess_market_data_snapshot_timing((binding,))
        original_strxfrm = locale.strxfrm
        original_strcoll = locale.strcoll

        def fail(value):
            raise AssertionError(value)

        locale.strxfrm = fail
        locale.strcoll = lambda first, second: fail((first, second))
        try:
            reference = MarketDataBindingReference(
                " \u2003Key\u00a0 ", " record "
            )
            self.assertEqual(reference.semantic_observation_key, "Key")
            exact_reference = market_data_binding_reference(binding)
            self.assertIs(
                resolve_market_data_binding_reference(
                    exact_reference, assessment
                ),
                binding,
            )
        finally:
            locale.strxfrm = original_strxfrm
            locale.strcoll = original_strcoll

    def test_implementation_has_no_external_or_later_layer_dependency(self) -> None:
        source = "\n".join((
            inspect.getsource(MarketDataBindingReference),
            inspect.getsource(market_data_binding_reference),
            inspect.getsource(resolve_market_data_binding_reference),
        ))
        prohibited = (
            "semantic_observation_key(",
            "select_correction_candidate(",
            "assess_market_data_freshness(",
            "assess_market_data_snapshot_timing(",
            "_derive_snapshot_timing_state(",
            "datetime.now",
            "date.today",
            "locale.",
            "unicodedata.",
            "random.",
            "os.environ",
            "pathlib.",
            "open(",
            "requests",
            "socket",
            "provider SDK",
            "registry",
            "MarketDataRelationship",
            "CalculationLineage(",
            "CandidateResearchRecord(",
        )
        for token in prohibited:
            with self.subTest(token=token):
                self.assertNotIn(token, source)


class RelationshipSurfaceAndEnumTests(unittest.TestCase):
    def test_public_surface_has_exact_prefix_suffix_and_count(self) -> None:
        expected_prefix = (
            BindingReferenceSurfaceAndConstructorTests
            .EXPECTED_3C3_PUBLIC_NAMES
        ) + (
            "MarketDataBindingReference",
            "market_data_binding_reference",
            "resolve_market_data_binding_reference",
        )
        expected_suffix = (
            "MarketDataRelationshipGroupKind",
            "MarketDataRelationshipRole",
            "MarketDataRelationshipGroupMember",
            "MarketDataRelationshipGroup",
            "MarketDataRelationshipRequest",
        )
        self.assertEqual(market_data.__all__[:45], expected_prefix)
        self.assertEqual(market_data.__all__[45:], expected_suffix)
        self.assertEqual(len(market_data.__all__), 50)
        self.assertTrue(all(
            hasattr(market_data, name) for name in expected_suffix
        ))

    def test_enums_have_exact_declaration_order_and_values(self) -> None:
        self.assertEqual(
            tuple(MarketDataRelationshipGroupKind),
            (
                MarketDataRelationshipGroupKind
                .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1,
                MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
                MarketDataRelationshipGroupKind.OPTION_ACTIVITY_V0_1,
                MarketDataRelationshipGroupKind
                .OPTION_CONTRACT_REFERENCE_V0_1,
            ),
        )
        self.assertEqual(
            tuple(kind.value for kind in MarketDataRelationshipGroupKind),
            (
                "underlying_option_quote_snapshot_v0.1",
                "option_quote_analytics_v0.1",
                "option_activity_v0.1",
                "option_contract_reference_v0.1",
            ),
        )
        self.assertEqual(
            tuple(role.value for role in MarketDataRelationshipRole),
            (
                "underlying_quote",
                "option_quote",
                "option_implied_volatility",
                "option_greeks",
                "option_volume",
                "option_open_interest",
                "option_contract_reference",
            ),
        )

    def test_dataclass_fields_frozen_behavior_and_structural_equality(self) -> None:
        expected_fields = {
            MarketDataRelationshipGroupMember: ("role", "reference"),
            MarketDataRelationshipGroup: ("group_id", "group_kind", "members"),
            MarketDataRelationshipRequest: ("groups",),
        }
        for artifact, names in expected_fields.items():
            with self.subTest(artifact=artifact.__name__):
                self.assertEqual(
                    tuple(field.name for field in dataclasses.fields(artifact)),
                    names,
                )
        first_group = build_relationship_group()
        second_group = build_relationship_group()
        self.assertEqual(first_group, second_group)
        first_request = MarketDataRelationshipRequest((first_group,))
        second_request = MarketDataRelationshipRequest((second_group,))
        self.assertEqual(first_request, second_request)
        with self.assertRaises(FrozenInstanceError):
            first_group.group_id = "changed"  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            first_request.groups = ()  # type: ignore[misc]

    def test_no_unauthorized_public_or_later_artifacts_exist(self) -> None:
        unauthorized = (
            "MarketDataRelationshipResolver",
            "resolve_market_data_relationships",
            "MarketDataRelationshipPolicy",
            "MarketDataRelationshipStatus",
            "MarketDataRelationshipReasonCode",
            "MarketDataRelationshipIssue",
            "MarketDataRelationshipAssessment",
            "MarketDataRelationshipResult",
            "MarketDataRelationshipSelection",
        )
        self.assertTrue(all(
            not hasattr(market_data, name) for name in unauthorized
        ))
        self.assertNotIn("request_id", {
            field.name
            for field in dataclasses.fields(MarketDataRelationshipRequest)
        })

        source_path = ROOT / "src" / "convexity_hunter" / "market_data.py"
        module = ast.parse(source_path.read_text(encoding="utf-8"))
        resolver_index = next(
            index
            for index, node in enumerate(module.body)
            if isinstance(node, ast.FunctionDef)
            and node.name == "resolve_market_data_binding_reference"
        )
        definitions = tuple(
            node
            for node in module.body[resolver_index + 1:]
            if isinstance(
                node,
                (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            )
        )
        expected_public_definitions = {
            "MarketDataRelationshipGroupKind",
            "MarketDataRelationshipRole",
            "MarketDataRelationshipGroupMember",
            "MarketDataRelationshipGroup",
            "MarketDataRelationshipRequest",
        }
        self.assertEqual(
            {
                node.name
                for node in definitions
                if not node.name.startswith("_")
            },
            expected_public_definitions,
        )
        self.assertTrue(all(
            node.name in expected_public_definitions
            or node.name.startswith("_")
            for node in definitions
        ))


class RelationshipMemberTests(unittest.TestCase):
    def test_member_retains_identity_is_frozen_and_structurally_equal(self) -> None:
        role = MarketDataRelationshipRole.OPTION_QUOTE
        reference = build_relationship_reference("member")
        member = MarketDataRelationshipGroupMember(role, reference)
        equal = MarketDataRelationshipGroupMember(
            role,
            build_relationship_reference("member"),
        )
        self.assertIs(member.role, role)
        self.assertIs(member.reference, reference)
        self.assertEqual(member, equal)
        with self.assertRaises(FrozenInstanceError):
            member.role = MarketDataRelationshipRole.OPTION_GREEKS  # type: ignore[misc]

    def test_member_requires_exact_role_and_reference_types(self) -> None:
        class ForeignRole(str, market_data.Enum):
            OPTION_QUOTE = "option_quote"

        reference = build_relationship_reference("exact-member")

        class ReferenceSubclass(MarketDataBindingReference):
            pass

        reference_subclass = ReferenceSubclass(
            reference.semantic_observation_key,
            reference.selected_record_id,
        )
        for role in (ForeignRole.OPTION_QUOTE, "option_quote", object()):
            with self.subTest(role=role):
                with self.assertRaisesRegex(TypeError, "role"):
                    MarketDataRelationshipGroupMember(role, reference)
        for invalid in (reference_subclass, object(), "reference"):
            with self.subTest(reference_type=type(invalid).__name__):
                with self.assertRaisesRegex(TypeError, "reference"):
                    MarketDataRelationshipGroupMember(
                        MarketDataRelationshipRole.OPTION_QUOTE,
                        invalid,
                    )

    def test_member_role_error_precedes_reference_error(self) -> None:
        with self.assertRaisesRegex(TypeError, "role"):
            MarketDataRelationshipGroupMember(object(), object())


class RelationshipGroupGrammarTests(unittest.TestCase):
    def test_group_id_exact_string_strip_and_unicode_behavior(self) -> None:
        cases = (
            (" \tGroup ID\n ", "Group ID"),
            ("\u00a0\u2003Unicode ID\u2003", "Unicode ID"),
            ("Internal  Space", "Internal  Space"),
            ("MiXeD", "MiXeD"),
            ("组-é", "组-é"),
        )
        for supplied, expected in cases:
            with self.subTest(supplied=repr(supplied)):
                self.assertEqual(
                    build_relationship_group(supplied).group_id,
                    expected,
                )
        self.assertNotEqual(
            build_relationship_group("é").group_id,
            build_relationship_group("e\u0301").group_id,
        )
        for value in (" \t\n", "\u00a0\u2003"):
            with self.subTest(empty=repr(value)):
                with self.assertRaisesRegex(ValueError, "group_id"):
                    build_relationship_group(value)

        class StringSubclass(str):
            pass

        with self.assertRaisesRegex(TypeError, "group_id"):
            build_relationship_group(StringSubclass("group"))

    def test_member_collection_exact_boundaries_and_elements(self) -> None:
        members = list(build_relationship_group().members)
        self.assertEqual(build_relationship_group(members=members).members,
                         tuple(members))
        self.assertEqual(build_relationship_group(members=tuple(members)).members,
                         tuple(members))

        class TupleSubclass(tuple):
            pass

        class ListSubclass(list):
            pass

        class ArbitraryIterable:
            def __iter__(self):
                return iter(members)

        class ForeignKind(str, market_data.Enum):
            SNAPSHOT = "underlying_option_quote_snapshot_v0.1"

        for invalid_kind in (
            ForeignKind.SNAPSHOT,
            "underlying_option_quote_snapshot_v0.1",
            object(),
        ):
            with self.subTest(group_kind=invalid_kind):
                with self.assertRaisesRegex(TypeError, "group_kind"):
                    build_relationship_group(group_kind=invalid_kind)

        invalid_containers = (
            TupleSubclass(members),
            ListSubclass(members),
            (member for member in members),
            set(members),
            {"member": members[0]},
            ArbitraryIterable(),
        )
        for invalid in invalid_containers:
            with self.subTest(container=type(invalid).__name__):
                with self.assertRaisesRegex(TypeError, "members"):
                    build_relationship_group(members=invalid)
        with self.assertRaisesRegex(TypeError, "members item"):
            build_relationship_group(members=(members[0], object()))

        class MemberSubclass(MarketDataRelationshipGroupMember):
            pass

        base = members[0]
        subclass = MemberSubclass(base.role, base.reference)
        with self.assertRaisesRegex(TypeError, "members item"):
            build_relationship_group(members=(subclass, members[1]))

    def test_snapshot_and_analytics_valid_forms(self) -> None:
        snapshot = build_relationship_group()
        self.assertEqual(
            tuple(member.role for member in snapshot.members),
            (
                MarketDataRelationshipRole.UNDERLYING_QUOTE,
                MarketDataRelationshipRole.OPTION_QUOTE,
            ),
        )
        analytics_kind = (
            MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1
        )
        valid_role_sets = (
            (
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
            ),
            (
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_GREEKS,
            ),
            (
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
                MarketDataRelationshipRole.OPTION_GREEKS,
            ),
        )
        for case_index, roles in enumerate(valid_role_sets):
            with self.subTest(roles=roles):
                members = tuple(
                    build_relationship_member(role, f"analytics-{case_index}-{i}")
                    for i, role in enumerate(reversed(roles))
                )
                group = build_relationship_group(
                    f"analytics-{case_index}", analytics_kind, members
                )
                self.assertEqual(
                    tuple(member.role for member in group.members), roles
                )

    def test_activity_valid_forms_and_canonical_order(self) -> None:
        kind = MarketDataRelationshipGroupKind.OPTION_ACTIVITY_V0_1
        valid_role_sets = (
            (
                MarketDataRelationshipRole.OPTION_VOLUME,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
            ),
            (
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_VOLUME,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
            ),
        )
        for case_index, roles in enumerate(valid_role_sets):
            members = tuple(
                build_relationship_member(role, f"activity-{case_index}-{i}")
                for i, role in enumerate(reversed(roles))
            )
            group = build_relationship_group(
                f"activity-{case_index}", kind, members
            )
            self.assertEqual(
                tuple(member.role for member in group.members), roles
            )

    def test_contract_reference_valid_optional_role_forms(self) -> None:
        kind = (
            MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1
        )
        optional_roles = (
            MarketDataRelationshipRole.OPTION_QUOTE,
            MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
            MarketDataRelationshipRole.OPTION_GREEKS,
            MarketDataRelationshipRole.OPTION_VOLUME,
            MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
        )
        contract_role = MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE
        subset_count = 0
        for subset_size in range(1, len(optional_roles) + 1):
            for selected_roles in itertools.combinations(
                optional_roles, subset_size
            ):
                subset_count += 1
                supplied_members = tuple(
                    build_relationship_member(
                        role,
                        f"contract-{subset_size}-{subset_count}-{index}",
                    )
                    for index, role in enumerate(
                        tuple(reversed(selected_roles)) + (contract_role,)
                    )
                )
                expected_roles = tuple(
                    role
                    for role in MarketDataRelationshipRole
                    if role in selected_roles or role is contract_role
                )
                expected_members = tuple(
                    next(
                        member
                        for member in supplied_members
                        if member.role is role
                    )
                    for role in expected_roles
                )
                with self.subTest(selected_roles=selected_roles):
                    group = build_relationship_group(
                        f"contract-subset-{subset_count}",
                        kind,
                        supplied_members,
                    )
                    self.assertEqual(
                        tuple(member.role for member in group.members),
                        expected_roles,
                    )
                    self.assertEqual(len(group.members), subset_size + 1)
                    for stored, supplied in zip(
                        group.members, expected_members
                    ):
                        self.assertIs(stored, supplied)
        self.assertEqual(subset_count, 31)

    def test_every_prohibited_role_is_rejected_for_each_kind(self) -> None:
        allowed_roles = {
            MarketDataRelationshipGroupKind
            .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1: {
                MarketDataRelationshipRole.UNDERLYING_QUOTE,
                MarketDataRelationshipRole.OPTION_QUOTE,
            },
            MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1: {
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
                MarketDataRelationshipRole.OPTION_GREEKS,
            },
            MarketDataRelationshipGroupKind.OPTION_ACTIVITY_V0_1: {
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_VOLUME,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
            },
            MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1: {
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
                MarketDataRelationshipRole.OPTION_GREEKS,
                MarketDataRelationshipRole.OPTION_VOLUME,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
            },
        }
        for kind, allowed in allowed_roles.items():
            for role in MarketDataRelationshipRole:
                if role in allowed:
                    continue
                with self.subTest(kind=kind, role=role):
                    with self.assertRaisesRegex(ValueError, "prohibited"):
                        build_relationship_group(
                            "prohibited",
                            kind,
                            (build_relationship_member(role, "prohibited"),),
                        )

    def test_required_and_singular_cardinalities_are_enforced(self) -> None:
        snapshot_kind = (
            MarketDataRelationshipGroupKind
            .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1
        )
        analytics_kind = (
            MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1
        )
        activity_kind = MarketDataRelationshipGroupKind.OPTION_ACTIVITY_V0_1
        contract_kind = (
            MarketDataRelationshipGroupKind.OPTION_CONTRACT_REFERENCE_V0_1
        )
        missing_cases = (
            (snapshot_kind, (MarketDataRelationshipRole.OPTION_QUOTE,)),
            (snapshot_kind, (MarketDataRelationshipRole.UNDERLYING_QUOTE,)),
            (analytics_kind, (MarketDataRelationshipRole.OPTION_GREEKS,)),
            (activity_kind, (MarketDataRelationshipRole.OPTION_OPEN_INTEREST,)),
            (activity_kind, (MarketDataRelationshipRole.OPTION_VOLUME,)),
            (contract_kind, (MarketDataRelationshipRole.OPTION_QUOTE,)),
        )
        for case_index, (kind, roles) in enumerate(missing_cases):
            with self.subTest(kind=kind, roles=roles):
                with self.assertRaisesRegex(ValueError, "minimum"):
                    build_relationship_group(
                        f"missing-{case_index}",
                        kind,
                        tuple(
                            build_relationship_member(role, f"missing-{case_index}-{i}")
                            for i, role in enumerate(roles)
                        ),
                    )

        maximum_one_cases = (
            (
                snapshot_kind,
                MarketDataRelationshipRole.UNDERLYING_QUOTE,
                (
                    MarketDataRelationshipRole.UNDERLYING_QUOTE,
                    MarketDataRelationshipRole.OPTION_QUOTE,
                ),
            ),
            (
                snapshot_kind,
                MarketDataRelationshipRole.OPTION_QUOTE,
                (
                    MarketDataRelationshipRole.UNDERLYING_QUOTE,
                    MarketDataRelationshipRole.OPTION_QUOTE,
                ),
            ),
            (
                analytics_kind,
                MarketDataRelationshipRole.OPTION_QUOTE,
                (
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
                ),
            ),
            (
                analytics_kind,
                MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
                (
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
                ),
            ),
            (
                analytics_kind,
                MarketDataRelationshipRole.OPTION_GREEKS,
                (
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    MarketDataRelationshipRole.OPTION_GREEKS,
                ),
            ),
            (
                activity_kind,
                MarketDataRelationshipRole.OPTION_QUOTE,
                (
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    MarketDataRelationshipRole.OPTION_VOLUME,
                    MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                ),
            ),
            (
                activity_kind,
                MarketDataRelationshipRole.OPTION_VOLUME,
                (
                    MarketDataRelationshipRole.OPTION_VOLUME,
                    MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                ),
            ),
            (
                activity_kind,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                (
                    MarketDataRelationshipRole.OPTION_VOLUME,
                    MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                ),
            ),
            (
                contract_kind,
                MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                (
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                ),
            ),
            (
                contract_kind,
                MarketDataRelationshipRole.OPTION_QUOTE,
                (
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                ),
            ),
            (
                contract_kind,
                MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
                (
                    MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
                    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                ),
            ),
            (
                contract_kind,
                MarketDataRelationshipRole.OPTION_GREEKS,
                (
                    MarketDataRelationshipRole.OPTION_GREEKS,
                    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                ),
            ),
            (
                contract_kind,
                MarketDataRelationshipRole.OPTION_VOLUME,
                (
                    MarketDataRelationshipRole.OPTION_VOLUME,
                    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                ),
            ),
            (
                contract_kind,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                (
                    MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                ),
            ),
        )
        self.assertEqual(len(maximum_one_cases), 14)
        for case_index, (kind, target_role, valid_roles) in enumerate(
            maximum_one_cases
        ):
            roles = valid_roles + (target_role,)
            with self.subTest(kind=kind, target_role=target_role):
                with self.assertRaisesRegex(
                    ValueError,
                    f"{target_role.value}.*maximum",
                ):
                    build_relationship_group(
                        f"maximum-one-{case_index}",
                        kind,
                        tuple(
                            build_relationship_member(
                                role,
                                f"maximum-one-{case_index}-{i}",
                            )
                            for i, role in enumerate(roles)
                        ),
                    )

    def test_aggregate_constraints_are_enforced(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "implied volatility or Greeks"
        ):
            build_relationship_group(
                "analytics-aggregate",
                MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
                (build_relationship_member(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    "analytics-quote",
                ),),
            )
        with self.assertRaisesRegex(ValueError, "non-reference role"):
            build_relationship_group(
                "contract-aggregate",
                MarketDataRelationshipGroupKind
                .OPTION_CONTRACT_REFERENCE_V0_1,
                (build_relationship_member(
                    MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                    "contract-reference",
                ),),
            )


class RelationshipGroupDuplicateAndCanonicalizationTests(unittest.TestCase):
    def test_complete_reference_duplicates_are_rejected_across_roles(self) -> None:
        reference = build_relationship_reference("duplicate")
        structurally_equal = MarketDataBindingReference(
            reference.semantic_observation_key,
            reference.selected_record_id,
        )
        cases = (
            (
                build_relationship_member(
                    MarketDataRelationshipRole.UNDERLYING_QUOTE,
                    reference=reference,
                ),
                build_relationship_member(
                    MarketDataRelationshipRole.UNDERLYING_QUOTE,
                    reference=reference,
                ),
            ),
            (
                build_relationship_member(
                    MarketDataRelationshipRole.UNDERLYING_QUOTE,
                    reference=reference,
                ),
                build_relationship_member(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    reference=reference,
                ),
            ),
            (
                build_relationship_member(
                    MarketDataRelationshipRole.UNDERLYING_QUOTE,
                    reference=reference,
                ),
                build_relationship_member(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    reference=structurally_equal,
                ),
            ),
        )
        for members in cases:
            with self.subTest(roles=tuple(member.role for member in members)):
                with self.assertRaisesRegex(ValueError, "duplicate reference"):
                    build_relationship_group(members=members)

    def test_partial_reference_matches_are_distinct_then_cardinality_applies(self) -> None:
        same_key = "semantic-observation-v0.1:same"
        same_id = "same-record"
        pairs = (
            (
                build_relationship_reference(
                    "a", semantic_key=same_key, record_id="record-a"
                ),
                build_relationship_reference(
                    "b", semantic_key=same_key, record_id="record-b"
                ),
            ),
            (
                build_relationship_reference(
                    "c", semantic_key="key-c", record_id=same_id
                ),
                build_relationship_reference(
                    "d", semantic_key="key-d", record_id=same_id
                ),
            ),
        )
        for first, second in pairs:
            with self.subTest(first=first, second=second):
                with self.assertRaisesRegex(ValueError, "maximum"):
                    build_relationship_group(members=(
                        build_relationship_member(
                            MarketDataRelationshipRole.UNDERLYING_QUOTE,
                            reference=first,
                        ),
                        build_relationship_member(
                            MarketDataRelationshipRole.UNDERLYING_QUOTE,
                            reference=second,
                        ),
                        build_relationship_member(
                            MarketDataRelationshipRole.OPTION_QUOTE,
                            "distinct-option",
                        ),
                    ))

    def test_member_order_is_canonical_and_caller_order_independent(self) -> None:
        underlying = build_relationship_member(
            MarketDataRelationshipRole.UNDERLYING_QUOTE, "canonical-underlying"
        )
        option = build_relationship_member(
            MarketDataRelationshipRole.OPTION_QUOTE, "canonical-option"
        )
        forward = build_relationship_group(members=(underlying, option))
        reverse = build_relationship_group(members=(option, underlying))
        self.assertEqual(forward, reverse)
        self.assertEqual(forward.members, (underlying, option))
        self.assertIs(reverse.members[0], underlying)
        self.assertIs(reverse.members[1], option)

    def test_private_member_sort_key_uses_secondary_and_tertiary_strings(self) -> None:
        role = MarketDataRelationshipRole.OPTION_QUOTE
        members = (
            build_relationship_member(
                role,
                reference=build_relationship_reference(
                    "z", semantic_key="key-z", record_id="record-a"
                ),
            ),
            build_relationship_member(
                role,
                reference=build_relationship_reference(
                    "a2", semantic_key="key-a", record_id="record-z"
                ),
            ),
            build_relationship_member(
                role,
                reference=build_relationship_reference(
                    "a1", semantic_key="key-a", record_id="record-a"
                ),
            ),
        )
        canonical = market_data._canonicalize_relationship_group_members(
            members
        )
        self.assertEqual(
            tuple(
                (
                    member.reference.semantic_observation_key,
                    member.reference.selected_record_id,
                )
                for member in canonical
            ),
            (
                ("key-a", "record-a"),
                ("key-a", "record-z"),
                ("key-z", "record-a"),
            ),
        )

    def test_canonicalization_is_locale_free_nonmutating_and_retains_identity(self) -> None:
        underlying = build_relationship_member(
            MarketDataRelationshipRole.UNDERLYING_QUOTE,
            reference=build_relationship_reference(
                "unicode-z", semantic_key="é", record_id="z"
            ),
        )
        option = build_relationship_member(
            MarketDataRelationshipRole.OPTION_QUOTE,
            reference=build_relationship_reference(
                "unicode-a", semantic_key="e\u0301", record_id="a"
            ),
        )
        supplied = [option, underlying]
        before = tuple(supplied)
        original_strxfrm = locale.strxfrm
        original_strcoll = locale.strcoll

        def fail(value):
            raise AssertionError(value)

        locale.strxfrm = fail
        locale.strcoll = lambda first, second: fail((first, second))
        try:
            group = build_relationship_group(members=supplied)
        finally:
            locale.strxfrm = original_strxfrm
            locale.strcoll = original_strcoll
        self.assertEqual(tuple(supplied), before)
        self.assertIs(group.members[0], underlying)
        self.assertIs(group.members[0].reference, underlying.reference)
        self.assertIs(group.group_kind,
                      MarketDataRelationshipGroupKind
                      .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1)


class RelationshipRequestTests(unittest.TestCase):
    def test_request_exact_collection_boundaries_elements_and_empty(self) -> None:
        group = build_relationship_group()
        self.assertIs(MarketDataRelationshipRequest([group]).groups[0], group)
        self.assertIs(MarketDataRelationshipRequest((group,)).groups[0], group)

        class TupleSubclass(tuple):
            pass

        class ListSubclass(list):
            pass

        class ArbitraryIterable:
            def __iter__(self):
                return iter((group,))

        invalid = (
            TupleSubclass((group,)),
            ListSubclass((group,)),
            (item for item in (group,)),
            {group},
            {"group": group},
            ArbitraryIterable(),
        )
        for value in invalid:
            with self.subTest(container=type(value).__name__):
                with self.assertRaisesRegex(TypeError, "groups"):
                    MarketDataRelationshipRequest(value)
        with self.assertRaisesRegex(ValueError, "at least one"):
            MarketDataRelationshipRequest(())
        with self.assertRaisesRegex(TypeError, "groups item"):
            MarketDataRelationshipRequest((object(),))

        class GroupSubclass(MarketDataRelationshipGroup):
            pass

        subclass = GroupSubclass(group.group_id, group.group_kind, group.members)
        with self.assertRaisesRegex(TypeError, "groups item"):
            MarketDataRelationshipRequest((subclass,))

    def test_duplicate_normalized_group_ids_are_rejected(self) -> None:
        first = build_relationship_group("duplicate-id")
        second = build_relationship_group("  duplicate-id  ")
        with self.assertRaisesRegex(ValueError, "duplicate group_id"):
            MarketDataRelationshipRequest((first, second))

    def test_request_order_is_group_id_only_nonmutating_and_identity_retaining(self) -> None:
        code_point_first = build_relationship_group("e\u0301")
        code_point_second = build_relationship_group("é")
        ascii_group = build_relationship_group("A")
        supplied = [code_point_second, ascii_group, code_point_first]
        before = tuple(supplied)
        expected_ids = ("A", "e\u0301", "é")
        expected_by_id = {group.group_id: group for group in supplied}
        original_strxfrm = locale.strxfrm
        original_strcoll = locale.strcoll

        def fail(value):
            raise AssertionError(value)

        locale.strxfrm = fail
        locale.strcoll = lambda first, second: fail((first, second))
        try:
            request = MarketDataRelationshipRequest(supplied)
            reverse_request = MarketDataRelationshipRequest(
                tuple(reversed(supplied))
            )
            self.assertEqual(tuple(supplied), before)
            self.assertEqual(
                tuple(group.group_id for group in request.groups),
                expected_ids,
            )
            for group in request.groups:
                self.assertIs(group, expected_by_id[group.group_id])
            self.assertEqual(request, reverse_request)
        finally:
            locale.strxfrm = original_strxfrm
            locale.strcoll = original_strcoll

    def test_reference_reuse_and_identical_contents_under_distinct_ids_allowed(self) -> None:
        underlying = build_relationship_member(
            MarketDataRelationshipRole.UNDERLYING_QUOTE, "shared-underlying"
        )
        option = build_relationship_member(
            MarketDataRelationshipRole.OPTION_QUOTE, "shared-option"
        )
        first = build_relationship_group("first", members=(underlying, option))
        second = build_relationship_group("second", members=(underlying, option))
        request = MarketDataRelationshipRequest((second, first))
        self.assertEqual(tuple(group.group_id for group in request.groups),
                         ("first", "second"))
        self.assertIs(request.groups[0].members[0].reference,
                      request.groups[1].members[0].reference)


class RelationshipValidationPrecedenceTests(unittest.TestCase):
    def test_member_and_initial_group_type_precedence(self) -> None:
        with self.assertRaisesRegex(TypeError, "role"):
            MarketDataRelationshipGroupMember(object(), object())
        with self.assertRaisesRegex(TypeError, "group_id"):
            MarketDataRelationshipGroup(object(), object(), object())
        with self.assertRaisesRegex(TypeError, "group_kind"):
            MarketDataRelationshipGroup("group", object(), object())
        with self.assertRaisesRegex(TypeError, "members"):
            MarketDataRelationshipGroup(
                "group",
                MarketDataRelationshipGroupKind
                .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1,
                object(),
            )
        with self.assertRaisesRegex(TypeError, "members item"):
            MarketDataRelationshipGroup(
                "   ",
                MarketDataRelationshipGroupKind
                .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1,
                (object(),),
            )

    def test_group_value_duplicate_prohibition_and_cardinality_precedence(self) -> None:
        with self.assertRaisesRegex(ValueError, "group_id"):
            MarketDataRelationshipGroup(
                "   ",
                MarketDataRelationshipGroupKind
                .UNDERLYING_OPTION_QUOTE_SNAPSHOT_V0_1,
                (),
            )
        duplicate = build_relationship_reference("precedence-duplicate")
        with self.assertRaisesRegex(ValueError, "duplicate reference"):
            build_relationship_group(members=(
                build_relationship_member(
                    MarketDataRelationshipRole.OPTION_GREEKS,
                    reference=duplicate,
                ),
                build_relationship_member(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    reference=duplicate,
                ),
            ))
        with self.assertRaisesRegex(ValueError, "prohibited"):
            build_relationship_group(members=(
                build_relationship_member(
                    MarketDataRelationshipRole.OPTION_GREEKS,
                    "precedence-prohibited",
                ),
                build_relationship_member(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    "precedence-quote-a",
                ),
                build_relationship_member(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    "precedence-quote-b",
                ),
            ))

    def test_declaration_aggregate_and_request_precedence(self) -> None:
        with self.assertRaisesRegex(ValueError, "underlying_quote.*minimum"):
            build_relationship_group(members=(
                build_relationship_member(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    "precedence-option-a",
                ),
                build_relationship_member(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    "precedence-option-b",
                ),
            ))
        with self.assertRaisesRegex(ValueError, "option_quote.*minimum"):
            build_relationship_group(
                "analytics-precedence",
                MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
                (build_relationship_member(
                    MarketDataRelationshipRole.OPTION_IMPLIED_VOLATILITY,
                    "analytics-precedence-iv",
                ),),
            )
        with self.assertRaisesRegex(
            ValueError, "implied volatility or Greeks"
        ):
            build_relationship_group(
                "aggregate-last",
                MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
                (build_relationship_member(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    "aggregate-last-quote",
                ),),
            )
        with self.assertRaisesRegex(ValueError, "option_quote.*maximum"):
            build_relationship_group(
                "analytics-cardinality-before-aggregate",
                MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
                (
                    build_relationship_member(
                        MarketDataRelationshipRole.OPTION_QUOTE,
                        "analytics-quote-first",
                    ),
                    build_relationship_member(
                        MarketDataRelationshipRole.OPTION_QUOTE,
                        "analytics-quote-second",
                    ),
                ),
            )
        with self.assertRaisesRegex(
            ValueError, "option_contract_reference.*maximum"
        ):
            build_relationship_group(
                "contract-cardinality-before-aggregate",
                MarketDataRelationshipGroupKind
                .OPTION_CONTRACT_REFERENCE_V0_1,
                (
                    build_relationship_member(
                        MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                        "contract-reference-first",
                    ),
                    build_relationship_member(
                        MarketDataRelationshipRole.OPTION_CONTRACT_REFERENCE,
                        "contract-reference-second",
                    ),
                ),
            )
        with self.assertRaisesRegex(TypeError, "groups"):
            MarketDataRelationshipRequest(object())
        with self.assertRaisesRegex(TypeError, "groups item"):
            MarketDataRelationshipRequest((object(),))

        original_duplicate = market_data._validate_unique_relationship_group_ids
        original_canonicalize = (
            market_data._canonicalize_relationship_request_groups
        )
        try:
            market_data._validate_unique_relationship_group_ids = (
                lambda groups: (_ for _ in ()).throw(
                    AssertionError("duplicate check reached")
                )
            )
            with self.assertRaisesRegex(ValueError, "at least one"):
                MarketDataRelationshipRequest(())
        finally:
            market_data._validate_unique_relationship_group_ids = original_duplicate

        duplicate_a = build_relationship_group("duplicate-before-sort")
        duplicate_b = build_relationship_group(" duplicate-before-sort ")
        try:
            market_data._canonicalize_relationship_request_groups = (
                lambda groups: (_ for _ in ()).throw(
                    AssertionError("canonical sorting reached")
                )
            )
            with self.assertRaisesRegex(ValueError, "duplicate group_id"):
                MarketDataRelationshipRequest((duplicate_a, duplicate_b))
        finally:
            market_data._canonicalize_relationship_request_groups = (
                original_canonicalize
            )


class RelationshipPurityAndScopeTests(unittest.TestCase):
    def test_construction_never_calls_resolution_or_semantic_identity(self) -> None:
        original_resolver = market_data.resolve_market_data_binding_reference
        original_semantic_key = market_data.semantic_observation_key

        def fail(*args, **kwargs):
            raise AssertionError((args, kwargs))

        try:
            market_data.resolve_market_data_binding_reference = fail
            market_data.semantic_observation_key = fail
            group = build_relationship_group()
            request = MarketDataRelationshipRequest((group,))
            self.assertIs(request.groups[0], group)
        finally:
            market_data.resolve_market_data_binding_reference = original_resolver
            market_data.semantic_observation_key = original_semantic_key

    def test_construction_never_accesses_timing_properties_or_records(self) -> None:
        property_names = (
            "is_temporally_coherent",
            "reason_codes",
            "common_freshness_policy",
            "common_freshness_context",
            "effective_time_span_seconds",
            "source_observation_span_seconds",
        )
        originals = {
            name: getattr(MarketDataSnapshotTimingAssessment, name)
            for name in property_names
        }

        def fail_on_access(_assessment):
            raise AssertionError("timing property accessed")

        try:
            for name in property_names:
                setattr(
                    MarketDataSnapshotTimingAssessment,
                    name,
                    property(fail_on_access),
                )
            group = build_relationship_group()
            self.assertEqual(len(MarketDataRelationshipRequest((group,)).groups), 1)
        finally:
            for name, descriptor in originals.items():
                setattr(MarketDataSnapshotTimingAssessment, name, descriptor)

        source = "\n".join((
            inspect.getsource(MarketDataRelationshipGroupMember),
            inspect.getsource(market_data._validate_relationship_group_grammar),
            inspect.getsource(MarketDataRelationshipGroup),
            inspect.getsource(MarketDataRelationshipRequest),
        ))
        prohibited = (
            "resolve_market_data_binding_reference(",
            "semantic_observation_key(",
            "MarketDataSnapshotTimingAssessment",
            ".selected_record",
            "UnderlyingQuoteObservation",
            "OptionQuoteObservation",
            "RateCurvePointObservation",
            "DividendObservation",
            "CalculationLineage(",
        )
        for token in prohibited:
            with self.subTest(token=token):
                self.assertNotIn(token, source)

    def test_no_downstream_rate_dividend_selection_or_external_api(self) -> None:
        self.assertTrue(all(
            "RATE" not in role.name and "DIVIDEND" not in role.name
            for role in MarketDataRelationshipRole
        ))
        self.assertTrue(all(
            "RATE" not in kind.name and "DIVIDEND" not in kind.name
            for kind in MarketDataRelationshipGroupKind
        ))
        unauthorized = (
            "resolve_market_data_relationships",
            "assess_market_data_relationships",
            "select_market_data_relationships",
            "MarketDataRelationshipAssessment",
            "MarketDataRelationshipStatus",
            "MarketDataRelationshipReasonCode",
            "MarketDataRelationshipIssue",
            "MarketDataRelationshipResult",
            "MarketDataRelationshipSelection",
        )
        self.assertTrue(all(
            not hasattr(market_data, name) for name in unauthorized
        ))


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
        self.assertEqual(build_correction_source(), build_correction_source())
        self.assertEqual(build_correction_candidate(), build_correction_candidate())
        self.assertEqual(
            build_correction_quote_observation(),
            build_correction_quote_observation(),
        )
        self.assertEqual(
            build_calculation_input_reference(),
            build_calculation_input_reference(),
        )
        self.assertEqual(build_calculation_lineage(), build_calculation_lineage())


if __name__ == "__main__":
    unittest.main()
