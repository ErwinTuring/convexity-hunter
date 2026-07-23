"""Contract tests for Milestone 3C.7a exact-structure liquidity."""

import dataclasses
import datetime
import decimal
import enum
import inspect
import pathlib
import sys
import unittest
from contextlib import ExitStack, contextmanager
from dataclasses import FrozenInstanceError
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
import convexity_hunter.market_data as market_data
import convexity_hunter.market_data_transformations as transformations
from convexity_hunter.evidence import OptionLeg, OptionStructure
from convexity_hunter.market_data import (
    CalculationLineage,
    CalculationQualityFlag,
    CorrectionSelection,
    CorrectionSelectionReasonCode,
    CorrectionSelectionStatus,
    DataOrigin,
    FreshnessAssessment,
    FreshnessContext,
    FreshnessReasonCode,
    FreshnessStatus,
    MarketDataBindingReference,
    MarketDataCategory,
    MarketDataFreshnessPolicy,
    MarketDataRelationshipAssessment,
    MarketDataRelationshipGroup,
    MarketDataRelationshipGroupKind,
    MarketDataRelationshipRequest,
    MarketDataRelationshipRole,
    MarketDataRelationshipSelection,
    MarketDataSelectionStatus,
    NormalizationQualityFlag,
    OptionQuoteObservation,
    OptionOpenInterestObservation,
    OptionVolumeObservation,
    SelectedFreshMarketDataBinding,
    SourceQualityFlag,
    assess_market_data_relationships,
    assess_market_data_snapshot_timing,
    select_market_data_relationship_assessment,
)
from convexity_hunter.market_data_transformations import (
    StructureLiquidityTransformationResult,
    transform_structure_liquidity,
)
from convexity_hunter.report import StructureLiquidity
from tests.market_data_fixtures import (
    CALCULATED_AT,
    EXPIRATION,
    SESSION_DATE,
    build_normalization_metadata,
    build_option_contract_key,
    build_source_reference,
)
from tests.test_market_data import (
    build_relationship_binding,
    build_resolved_relationship_group,
)


def make_structure(option_types=("call",), quantity=1, multiplier=100):
    return OptionStructure(
        tuple(
            OptionLeg(
                "SPY",
                option_type,
                100.0,
                EXPIRATION,
                quantity,
                multiplier,
            )
            for option_type in option_types
        ),
        assumed_portfolio_value=100000.0,
        expected_holding_days=14,
    )


def make_selection(
    structure,
    *,
    bid=("1.25", "2.00"),
    ask=("1.50", "2.50"),
    volume=(40, 30),
    open_interest=(80, 70),
    contracts=None,
):
    groups = []
    all_bindings = []
    bindings_by_group = []
    for index, leg in enumerate(structure.legs):
        label = leg.option_type
        contract = (
            build_option_contract_key(
                option_type=leg.option_type,
                strike=decimal.Decimal(str(leg.strike)),
                contract_multiplier=leg.contract_multiplier,
                expiration=leg.expiration,
            )
            if contracts is None
            else contracts[index]
        )
        bindings = {
            MarketDataRelationshipRole.OPTION_QUOTE: (
                build_relationship_binding(
                    MarketDataRelationshipRole.OPTION_QUOTE,
                    f"liquidity-{label}-quote",
                    contract_key=contract,
                    bid_premium=decimal.Decimal(bid[index]),
                    ask_premium=decimal.Decimal(ask[index]),
                    session_date=SESSION_DATE,
                )
            ),
            MarketDataRelationshipRole.OPTION_VOLUME: (
                build_relationship_binding(
                    MarketDataRelationshipRole.OPTION_VOLUME,
                    f"liquidity-{label}-volume",
                    contract_key=contract,
                    cumulative_volume=volume[index],
                    is_session_complete=True,
                    session_date=SESSION_DATE,
                )
            ),
            MarketDataRelationshipRole.OPTION_OPEN_INTEREST: (
                build_relationship_binding(
                    MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                    f"liquidity-{label}-open-interest",
                    contract_key=contract,
                    open_interest=open_interest[index],
                    open_interest_session_date=SESSION_DATE,
                )
            ),
        }
        group, aligned = build_resolved_relationship_group(
            f"activity-{label}",
            MarketDataRelationshipGroupKind.OPTION_ACTIVITY_V0_1,
            bindings,
        )
        groups.append(group)
        all_bindings.extend(aligned)
        bindings_by_group.append(bindings)
    assessment = assess_market_data_relationships(
        MarketDataRelationshipRequest(tuple(groups)),
        assess_market_data_snapshot_timing(tuple(all_bindings)),
    )
    return (
        select_market_data_relationship_assessment((assessment,)),
        assessment,
        tuple(bindings_by_group),
    )


def transform(structure, selection):
    return transform_structure_liquidity(
        " calculation-3c7a ",
        structure,
        selection,
        CALCULATED_AT,
    )


@contextmanager
def force_selected(assessment):
    with mock.patch.object(
        MarketDataRelationshipSelection,
        "status",
        new=property(lambda _self: MarketDataSelectionStatus.SELECTED),
    ), mock.patch.object(
        MarketDataRelationshipSelection,
        "selected_candidate",
        new=property(lambda _self: assessment),
    ):
        yield


@contextmanager
def changed(target, name, value):
    original = getattr(target, name)
    object.__setattr__(target, name, value)
    try:
        yield
    finally:
        object.__setattr__(target, name, original)


class PublicSurfaceTests(unittest.TestCase):
    def test_exact_surface_signature_fields_and_frozen_result(self):
        self.assertEqual(
            transformations.__all__,
            (
                "StructureLiquidityTransformationResult",
                "transform_structure_liquidity",
            ),
        )
        self.assertEqual(len(market_data.__all__), 64)
        self.assertFalse(
            hasattr(convexity_hunter, "transform_structure_liquidity")
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                StructureLiquidityTransformationResult
            )),
            ("record", "lineage"),
        )
        signature = inspect.signature(transform_structure_liquidity)
        self.assertEqual(
            tuple(signature.parameters),
            (
                "calculation_id",
                "structure",
                "relationship_selection",
                "calculated_at",
            ),
        )
        self.assertTrue(all(
            parameter.annotation is object
            for parameter in signature.parameters.values()
        ))
        self.assertIs(
            signature.return_annotation,
            StructureLiquidityTransformationResult,
        )
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        result = transform(structure, selection)
        with self.assertRaises(FrozenInstanceError):
            result.record = result.record

    def test_direct_result_construction_is_exact_type_structural_only(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        result = transform(structure, selection)
        self.assertIs(
            StructureLiquidityTransformationResult(
                result.record, result.lineage
            ).record,
            result.record,
        )

        class LiquiditySubclass(StructureLiquidity):
            pass

        class LineageSubclass(CalculationLineage):
            pass

        with self.assertRaises(TypeError):
            StructureLiquidityTransformationResult(object(), result.lineage)
        with self.assertRaises(TypeError):
            StructureLiquidityTransformationResult(result.record, object())
        liquidity_subclass = LiquiditySubclass(
            result.record.structure,
            result.record.as_of_date,
            result.record.quoted_bid_value,
            result.record.quoted_ask_value,
            result.record.minimum_leg_open_interest,
            result.record.minimum_leg_daily_volume,
            result.record.quote_methodology,
        )
        lineage_subclass = LineageSubclass(
            result.lineage.calculation_id,
            result.lineage.calculation_type,
            result.lineage.methodology_id,
            result.lineage.methodology_version,
            result.lineage.calculated_at,
            result.lineage.inputs,
            result.lineage.parameters_json,
            result.lineage.quality_flags,
        )
        with self.assertRaises(TypeError):
            StructureLiquidityTransformationResult(
                liquidity_subclass, result.lineage
            )
        with self.assertRaises(TypeError):
            StructureLiquidityTransformationResult(
                result.record, lineage_subclass
            )


class SuccessfulCalculationTests(unittest.TestCase):
    def test_one_leg_call_and_put_literal_values_zeros_and_identity(self):
        for option_type in ("call", "put"):
            with self.subTest(option_type=option_type):
                structure = make_structure((option_type,), quantity=2)
                selection, _, _ = make_selection(
                    structure,
                    bid=("0", "2"),
                    ask=("1.50", "2"),
                    volume=(0, 30),
                    open_interest=(0, 70),
                )
                result = transform(structure, selection)
                self.assertIs(result.record.structure, structure)
                self.assertEqual(result.record.as_of_date, SESSION_DATE)
                self.assertEqual(result.record.quoted_bid_value, 0.0)
                self.assertEqual(result.record.quoted_ask_value, 300.0)
                self.assertEqual(result.record.minimum_leg_daily_volume, 0)
                self.assertEqual(result.record.minimum_leg_open_interest, 0)

    def test_two_leg_straddle_exact_sum_scaling_and_unscaled_minima(self):
        structure = make_structure(("put", "call"), quantity=3, multiplier=25)
        selection, _, _ = make_selection(structure)
        result = transform(structure, selection)
        self.assertEqual(result.record.quoted_bid_value, 243.75)
        self.assertEqual(result.record.quoted_ask_value, 300.0)
        self.assertEqual(result.record.minimum_leg_daily_volume, 30)
        self.assertEqual(result.record.minimum_leg_open_interest, 70)

    def test_group_and_leg_permutations_have_invariant_values_and_parameters(self):
        first = make_structure(("call", "put"))
        second = make_structure(("put", "call"))
        first_selection, _, _ = make_selection(first)
        second_selection, _, _ = make_selection(
            second,
            bid=("2.00", "1.25"),
            ask=("2.50", "1.50"),
            volume=(30, 40),
            open_interest=(70, 80),
        )
        first_result = transform(first, first_selection)
        second_result = transform(second, second_selection)
        self.assertEqual(
            (
                first_result.record.quoted_bid_value,
                first_result.record.quoted_ask_value,
                first_result.record.minimum_leg_daily_volume,
                first_result.record.minimum_leg_open_interest,
            ),
            (325.0, 400.0, 30, 70),
        )
        self.assertEqual(first_result.lineage.parameters_json,
                         second_result.lineage.parameters_json)
        self.assertEqual(
            tuple(item.record_id for item in first_result.lineage.inputs),
            tuple(sorted(item.record_id for item in first_result.lineage.inputs)),
        )


class BoundaryAndProofTests(unittest.TestCase):
    def test_top_level_exact_types_and_precedence(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)

        class StringSubclass(str):
            pass

        class StructureSubclass(OptionStructure):
            pass

        class SelectionSubclass(MarketDataRelationshipSelection):
            pass

        class DatetimeSubclass(datetime.datetime):
            pass

        invalid_calls = (
            ((object(), structure, selection, CALCULATED_AT), TypeError),
            ((StringSubclass("x"), structure, selection, CALCULATED_AT), TypeError),
            ((" ", structure, selection, CALCULATED_AT), ValueError),
            (("x", object(), selection, CALCULATED_AT), TypeError),
            (("x", StructureSubclass(structure.legs, 1.0, 1),
              selection, CALCULATED_AT), TypeError),
            (("x", structure, object(), CALCULATED_AT), TypeError),
            (("x", structure, SelectionSubclass(selection.candidates),
              CALCULATED_AT), TypeError),
            (("x", structure, selection, object()), TypeError),
            (("x", structure, selection,
              DatetimeSubclass(2030, 1, 2)), TypeError),
            (("x", structure, selection,
              datetime.datetime(2030, 1, 2)), ValueError),
        )
        for arguments, error in invalid_calls:
            with self.subTest(arguments=tuple(type(x).__name__ for x in arguments)):
                with self.assertRaises(error):
                    transform_structure_liquidity(*arguments)

    def test_every_nonselected_status_stops_before_candidate_access(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        for status in tuple(MarketDataSelectionStatus)[1:]:
            with self.subTest(status=status):
                with mock.patch.object(
                    MarketDataRelationshipSelection,
                    "status",
                    new=property(lambda _self, value=status: value),
                ), mock.patch.object(
                    MarketDataRelationshipSelection,
                    "selected_candidate",
                    new=property(lambda _self: (_ for _ in ()).throw(
                        AssertionError("selected candidate accessed")
                    )),
                ):
                    with self.assertRaises(ValueError):
                        transform(structure, selection)

    def test_missing_candidate_and_group_shape_failures(self):
        structure = make_structure()
        selection, assessment, _ = make_selection(structure)
        with mock.patch.object(
            MarketDataRelationshipSelection,
            "status",
            new=property(lambda _self: MarketDataSelectionStatus.SELECTED),
        ), mock.patch.object(
            MarketDataRelationshipSelection,
            "selected_candidate",
            new=property(lambda _self: None),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)

        original = assessment.request
        extra = MarketDataRelationshipRequest(
            original.groups + (
                dataclasses.replace(original.groups[0], group_id="extra"),
            )
        )
        object.__setattr__(assessment, "request", extra)
        try:
            with mock.patch.object(
                MarketDataRelationshipSelection,
                "status",
                new=property(lambda _self: MarketDataSelectionStatus.SELECTED),
            ), mock.patch.object(
                MarketDataRelationshipSelection,
                "selected_candidate",
                new=property(lambda _self: assessment),
            ):
                with self.assertRaises(ValueError):
                    transform(structure, selection)
        finally:
            object.__setattr__(assessment, "request", original)

    def test_wrong_group_kind_missing_role_and_unreferenced_binding(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        group = assessment.request.groups[0]
        original_kind = group.group_kind
        object.__setattr__(
            group,
            "group_kind",
            MarketDataRelationshipGroupKind.OPTION_QUOTE_ANALYTICS_V0_1,
        )
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(group, "group_kind", original_kind)

        original_members = group.members
        object.__setattr__(group, "members", original_members[:-1])
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(group, "members", original_members)

        timing = assessment.timing_assessment
        original_bindings = timing.bindings
        object.__setattr__(timing, "bindings", original_bindings + (
            bindings[0][MarketDataRelationshipRole.OPTION_QUOTE],
        ))
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(timing, "bindings", original_bindings)

    def test_proof_layer_functions_are_never_called(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        names = (
            "select_correction_candidate",
            "assess_market_data_freshness",
            "bind_selected_fresh_market_data",
            "assess_market_data_snapshot_timing",
            "assess_market_data_relationships",
            "select_market_data_relationship_assessment",
            "assess_market_data_historical_series",
        )
        patches = [
            mock.patch.object(
                market_data,
                name,
                side_effect=AssertionError(f"{name} called"),
            )
            for name in names
        ]
        for patch in patches:
            patch.start()
        try:
            self.assertEqual(transform(structure, selection).record.quoted_bid_value,
                             125.0)
        finally:
            for patch in reversed(patches):
                patch.stop()


class CorrespondenceSessionAndLineageTests(unittest.TestCase):
    def test_every_contract_identity_component_is_required(self):
        structure = make_structure()
        base = build_option_contract_key()
        alternatives = (
            dataclasses.replace(
                base,
                underlying_key=dataclasses.replace(
                    base.underlying_key, symbol="QQQ"
                ),
            ),
            dataclasses.replace(base, option_type="put"),
            dataclasses.replace(
                base, expiration=EXPIRATION + datetime.timedelta(days=1)
            ),
            dataclasses.replace(base, strike=decimal.Decimal("101")),
            dataclasses.replace(base, contract_multiplier=50),
        )
        for contract in alternatives:
            with self.subTest(contract=contract):
                selection, _, _ = make_selection(
                    structure, contracts=(contract,)
                )
                with self.assertRaises(ValueError):
                    transform(structure, selection)

    def test_duplicate_group_leg_mixed_session_and_incomplete_volume_rejected(self):
        structure = make_structure(("call", "put"))
        selection, assessment, bindings = make_selection(structure)
        second_records = tuple(
            bindings[1][role].selected_record
            for role in (
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_VOLUME,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
            )
        )
        original_contracts = tuple(record.contract_key for record in second_records)
        call_contract = bindings[0][
            MarketDataRelationshipRole.OPTION_QUOTE
        ].selected_record.contract_key
        for record in second_records:
            object.__setattr__(record, "contract_key", call_contract)
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            for record, contract in zip(second_records, original_contracts):
                object.__setattr__(record, "contract_key", contract)

        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        volume = bindings[0][MarketDataRelationshipRole.OPTION_VOLUME].selected_record
        original_date = volume.session_date
        object.__setattr__(
            volume, "session_date", SESSION_DATE + datetime.timedelta(days=1)
        )
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(volume, "session_date", original_date)
        object.__setattr__(volume, "is_session_complete", False)
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(volume, "is_session_complete", True)

    def test_duplicate_consumed_record_id_rejected(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE].selected_record
        volume_binding = bindings[0][MarketDataRelationshipRole.OPTION_VOLUME]
        volume = volume_binding.selected_record
        original = volume.metadata
        original_selected_id = volume_binding.correction_selection.selected_record_id
        group = assessment.request.groups[0]
        volume_member = next(
            member for member in group.members
            if member.role is MarketDataRelationshipRole.OPTION_VOLUME
        )
        original_reference_id = volume_member.reference.selected_record_id
        object.__setattr__(
            volume,
            "metadata",
            dataclasses.replace(
                original, record_id=quote.metadata.record_id
            ),
        )
        object.__setattr__(
            volume_binding.correction_selection,
            "selected_record_id",
            quote.metadata.record_id,
        )
        object.__setattr__(
            volume_member.reference,
            "selected_record_id",
            quote.metadata.record_id,
        )
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(volume, "metadata", original)
            object.__setattr__(
                volume_binding.correction_selection,
                "selected_record_id",
                original_selected_id,
            )
            object.__setattr__(
                volume_member.reference,
                "selected_record_id",
                original_reference_id,
            )

    def test_lineage_exact_fields_inputs_parameters_and_default_flags(self):
        structure = make_structure()
        selection, _, bindings = make_selection(structure)
        result = transform(structure, selection)
        lineage = result.lineage
        self.assertEqual(lineage.calculation_id, "calculation-3c7a")
        self.assertEqual(lineage.calculation_type, "structure_liquidity")
        self.assertEqual(lineage.methodology_id, "exact-structure-liquidity")
        self.assertEqual(lineage.methodology_version, "v0.1")
        self.assertEqual(lineage.calculated_at, CALCULATED_AT)
        self.assertEqual(
            lineage.quality_flags,
            (CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,),
        )
        expected_records = tuple(
            bindings[0][role].selected_record
            for role in (
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_VOLUME,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
            )
        )
        self.assertEqual(
            tuple(item.record_id for item in lineage.inputs),
            tuple(sorted(record.metadata.record_id for record in expected_records)),
        )
        for item in lineage.inputs:
            record = next(
                record for record in expected_records
                if record.metadata.record_id == item.record_id
            )
            self.assertEqual(item.normalized_at, record.metadata.normalized_at)
            self.assertEqual(
                item.source_ids,
                tuple(source.source_id
                      for source in record.metadata.source_references),
            )
        self.assertEqual(
            lineage.parameters_json,
            '{"$map":[["activity_count_unit","contracts"],'
            '["leg_correspondence",{"$list":[{"$map":['
            '["contract_multiplier",100],["currency","USD"],'
            '["deliverable_id",null],["expiration",{"$date":"2030-03-15"}],'
            '["open_interest_record_id","liquidity-call-open-interest"],'
            '["option_type","call"],["quantity",1],'
            '["quote_record_id","liquidity-call-quote"],'
            '["strike",{"$decimal":"100.0"}],'
            '["underlying",{"$map":[["currency","USD"],'
            '["listing_mic","ARCX"],["security_type","etf"],'
            '["symbol","SPY"]]}],'
            '["volume_record_id","liquidity-call-volume"]]}]}],'
            '["minimum_leg_rule",'
            '"minimum_unscaled_contract_count_across_legs"],'
            '["position_value_rule",'
            '"sum(premium_per_underlying_unit*quantity*contract_multiplier)"],'
            '["position_value_unit","usd"],'
            '["premium_input_unit","usd_per_underlying_unit"]]}',
        )

    def test_all_authorized_quality_flags_and_prohibited_flags(self):
        structure = make_structure()
        selection, _, bindings = make_selection(structure)
        records = tuple(
            bindings[0][role].selected_record
            for role in (
                MarketDataRelationshipRole.OPTION_QUOTE,
                MarketDataRelationshipRole.OPTION_VOLUME,
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
            )
        )
        originals = tuple(record.metadata for record in records)
        partial_source = dataclasses.replace(
            originals[2].source_references[0],
            quality_flags=(SourceQualityFlag.PARTIAL,),
        )
        composite_sources = (
            dataclasses.replace(
                originals[1].source_references[0], source_id="composite-a"
            ),
            dataclasses.replace(
                originals[1].source_references[0],
                source_id="composite-b",
                provider_record_id="composite-record-b",
                provider_request_id="composite-request-b",
                source_uri="synthetic://composite/b",
            ),
        )
        changed = (
            dataclasses.replace(
                originals[0],
                quality_flags=(NormalizationQualityFlag.INTERPOLATED,),
            ),
            build_normalization_metadata(
                composite_sources,
                record_id=originals[1].record_id,
                effective_observed_at=originals[1].effective_observed_at,
                normalized_at=originals[1].normalized_at,
                record_origin=DataOrigin.SYSTEM_COMPOSITE,
                quality_flags=(NormalizationQualityFlag.COMPOSITE_SOURCE,),
            ),
            dataclasses.replace(
                originals[2], source_references=(partial_source,)
            ),
        )
        for record, metadata in zip(records, changed):
            object.__setattr__(record, "metadata", metadata)
        try:
            flags = transform(structure, selection).lineage.quality_flags
            self.assertEqual(
                flags,
                (
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                    CalculationQualityFlag.INTERPOLATED,
                    CalculationQualityFlag.COMPOSITE_INPUT_USED,
                    CalculationQualityFlag.INCOMPLETE_INPUT_USED,
                ),
            )
            self.assertNotIn(CalculationQualityFlag.ANNUALIZED, flags)
            self.assertNotIn(CalculationQualityFlag.ADJUSTED_INPUT_USED, flags)
            self.assertNotIn(CalculationQualityFlag.ASSUMPTION_APPLIED, flags)
        finally:
            for record, metadata in zip(records, originals):
                object.__setattr__(record, "metadata", metadata)

    def test_calculated_at_chronology_is_enforced(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        with self.assertRaises(ValueError):
            transform_structure_liquidity(
                "calculation",
                structure,
                selection,
                datetime.datetime(2029, 1, 1, tzinfo=datetime.timezone.utc),
            )

    def test_calculation_id_collision_and_discarded_candidate_exclusion(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote_binding = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        selected = quote_binding.selected_record
        discarded = dataclasses.replace(
            selected,
            metadata=dataclasses.replace(
                selected.metadata, record_id="discarded-not-consumed"
            ),
        )
        object.__setattr__(
            quote_binding, "candidate_records", (discarded, selected)
        )
        object.__setattr__(
            quote_binding.correction_selection,
            "candidate_record_ids",
            tuple(sorted((
                discarded.metadata.record_id,
                selected.metadata.record_id,
            ))),
        )
        object.__setattr__(
            quote_binding.correction_selection,
            "reason_codes",
            (
                CorrectionSelectionReasonCode
                .DOMINATING_REVISION_VECTOR_SELECTED,
            ),
        )
        with force_selected(assessment):
            result = transform(structure, selection)
        self.assertNotIn(
            discarded.metadata.record_id,
            tuple(item.record_id for item in result.lineage.inputs),
        )
        with force_selected(assessment), self.assertRaises(ValueError):
            transform_structure_liquidity(
                selected.metadata.record_id,
                structure,
                selection,
                CALCULATED_AT,
            )

    def test_session_after_expiration_missing_value_and_float_overflow_rejected(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE].selected_record
        volume = bindings[0][MarketDataRelationshipRole.OPTION_VOLUME].selected_record
        original_quote_date = quote.session_date
        original_volume_date = volume.session_date
        after_expiration = EXPIRATION + datetime.timedelta(days=1)
        object.__setattr__(quote, "session_date", after_expiration)
        object.__setattr__(volume, "session_date", after_expiration)
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(quote, "session_date", original_quote_date)
            object.__setattr__(volume, "session_date", original_volume_date)

        original_volume = volume.cumulative_volume
        object.__setattr__(volume, "cumulative_volume", None)
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(volume, "cumulative_volume", original_volume)

        original_bid = quote.bid_premium
        original_ask = quote.ask_premium
        object.__setattr__(quote, "bid_premium", decimal.Decimal("1e10000"))
        object.__setattr__(quote, "ask_premium", decimal.Decimal("2e10000"))
        try:
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
        finally:
            object.__setattr__(quote, "bid_premium", original_bid)
            object.__setattr__(quote, "ask_premium", original_ask)

    def test_dominating_revision_reason_adds_correction_flag_in_enum_order(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        correction = bindings[0][
            MarketDataRelationshipRole.OPTION_QUOTE
        ].correction_selection
        binding = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        selected_record = binding.selected_record
        discarded_record = dataclasses.replace(
            selected_record,
            metadata=dataclasses.replace(
                selected_record.metadata,
                record_id="discarded-correction-candidate",
            ),
        )
        original_reasons = correction.reason_codes
        original_candidate_ids = correction.candidate_record_ids
        original_candidates = binding.candidate_records
        object.__setattr__(
            binding,
            "candidate_records",
            (discarded_record, selected_record),
        )
        object.__setattr__(
            correction,
            "candidate_record_ids",
            tuple(sorted((
                discarded_record.metadata.record_id,
                selected_record.metadata.record_id,
            ))),
        )
        object.__setattr__(
            correction,
            "reason_codes",
            (
                CorrectionSelectionReasonCode
                .DOMINATING_REVISION_VECTOR_SELECTED,
            ),
        )
        try:
            with force_selected(assessment):
                flags = transform(structure, selection).lineage.quality_flags
            self.assertEqual(
                flags,
                (
                    CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
                    CalculationQualityFlag.CORRECTION_SELECTED,
                ),
            )
        finally:
            object.__setattr__(correction, "reason_codes", original_reasons)
            object.__setattr__(
                correction, "candidate_record_ids", original_candidate_ids
            )
            object.__setattr__(
                binding, "candidate_records", original_candidates
            )


class CorrectedProofIntegrityTests(unittest.TestCase):
    def _one_leg(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        return structure, selection, assessment, bindings[0]

    def _assert_proof_rejected(self, mutate):
        structure, selection, assessment, bindings = self._one_leg()
        mutate(assessment, bindings)
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_match_structure_legs",
            side_effect=AssertionError("leg correspondence reached"),
        ):
            with self.assertRaises((TypeError, ValueError)):
                transform(structure, selection)

    def test_correction_terminal_and_candidate_universe_matrix(self):
        def correction(bindings):
            return bindings[
                MarketDataRelationshipRole.OPTION_QUOTE
            ].correction_selection

        mutations = {
            "ambiguous_status": lambda _a, b: object.__setattr__(
                correction(b), "status", CorrectionSelectionStatus.AMBIGUOUS
            ),
            "missing_selected_id": lambda _a, b: object.__setattr__(
                correction(b), "selected_record_id", None
            ),
            "incompatible_reason": lambda _a, b: object.__setattr__(
                correction(b),
                "reason_codes",
                (CorrectionSelectionReasonCode.MISSING_PROVIDER_RECORD_ID,),
            ),
            "multiple_reasons": lambda _a, b: object.__setattr__(
                correction(b),
                "reason_codes",
                (
                    CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
                    CorrectionSelectionReasonCode
                    .DOMINATING_REVISION_VECTOR_SELECTED,
                ),
            ),
            "candidate_id_tuple_mismatch": lambda _a, b: object.__setattr__(
                correction(b),
                "candidate_record_ids",
                ("foreign-candidate",),
            ),
            "selected_id_absent": lambda _a, b: (
                object.__setattr__(
                    correction(b),
                    "candidate_record_ids",
                    tuple(sorted((
                        correction(b).selected_record_id,
                        "absent-candidate",
                    ))),
                )
            ),
            "correction_semantic_key": lambda _a, b: object.__setattr__(
                correction(b), "semantic_observation_key", "forged-semantic"
            ),
            "correction_chronology": lambda _a, b: object.__setattr__(
                correction(b),
                "evaluated_at",
                b[
                    MarketDataRelationshipRole.OPTION_QUOTE
                ].freshness_context.evaluation_at
                + datetime.timedelta(microseconds=1),
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self._assert_proof_rejected(mutation)

    def test_candidate_count_duplicate_and_identity_matrix(self):
        def add_candidate(_assessment, bindings, duplicate_id=False):
            binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
            selected = binding.selected_record
            record_id = (
                selected.metadata.record_id
                if duplicate_id
                else "discarded-quote-candidate"
            )
            discarded = dataclasses.replace(
                selected,
                metadata=dataclasses.replace(
                    selected.metadata, record_id=record_id
                ),
            )
            object.__setattr__(
                binding, "candidate_records", (discarded, selected)
            )
            object.__setattr__(
                binding.correction_selection,
                "candidate_record_ids",
                tuple(sorted((
                    record_id, selected.metadata.record_id
                ))),
            )

        with self.subTest(name="only_candidate_with_multiple"):
            self._assert_proof_rejected(add_candidate)
        with self.subTest(name="duplicate_candidate_ids"):
            self._assert_proof_rejected(
                lambda a, b: add_candidate(a, b, duplicate_id=True)
            )
        with self.subTest(name="dominating_with_one"):
            self._assert_proof_rejected(
                lambda _a, b: object.__setattr__(
                    b[
                        MarketDataRelationshipRole.OPTION_QUOTE
                    ].correction_selection,
                    "reason_codes",
                    (
                        CorrectionSelectionReasonCode
                        .DOMINATING_REVISION_VECTOR_SELECTED,
                    ),
                )
            )

        structure, selection, assessment, bindings = self._one_leg()
        binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
        entries = transformations._resolve_selected_objects(
            assessment.request.groups,
            assessment.timing_assessment.bindings,
        )
        forged = dataclasses.replace(entries[0][3])
        forged_entries = ((entries[0][0], entries[0][1], binding, forged),) + entries[1:]
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_resolve_selected_objects",
            return_value=forged_entries,
        ), mock.patch.object(
            transformations,
            "_match_structure_legs",
            side_effect=AssertionError("leg correspondence reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)

    def test_freshness_terminal_correspondence_and_regime_matrix(self):
        def freshness(bindings):
            return bindings[
                MarketDataRelationshipRole.OPTION_QUOTE
            ].freshness_assessment

        mutations = {
            "stale": lambda _a, b: object.__setattr__(
                freshness(b), "status", FreshnessStatus.STALE
            ),
            "unknown": lambda _a, b: object.__setattr__(
                freshness(b), "status", FreshnessStatus.UNKNOWN
            ),
            "ineligible": lambda _a, b: object.__setattr__(
                freshness(b), "status", FreshnessStatus.INELIGIBLE
            ),
            "wrong_reason": lambda _a, b: object.__setattr__(
                freshness(b),
                "reason_codes",
                (FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,),
            ),
            "wrong_category": lambda _a, b: object.__setattr__(
                freshness(b), "category", MarketDataCategory.ACTIVITY
            ),
            "record_id": lambda _a, b: object.__setattr__(
                freshness(b), "record_id", "wrong-record"
            ),
            "policy_id": lambda _a, b: object.__setattr__(
                freshness(b), "policy_id", "wrong-policy"
            ),
            "policy_version": lambda _a, b: object.__setattr__(
                freshness(b), "policy_version", "wrong-version"
            ),
            "evaluated_at": lambda _a, b: object.__setattr__(
                freshness(b),
                "evaluated_at",
                freshness(b).evaluated_at + datetime.timedelta(microseconds=1),
            ),
            "policy_type": lambda _a, b: object.__setattr__(
                b[MarketDataRelationshipRole.OPTION_QUOTE],
                "freshness_policy",
                object(),
            ),
            "context_type": lambda _a, b: object.__setattr__(
                b[MarketDataRelationshipRole.OPTION_QUOTE],
                "freshness_context",
                object(),
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self._assert_proof_rejected(mutation)

        class FreshnessSubclass(FreshnessAssessment):
            pass

        def subclass_mutation(_assessment, bindings):
            binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
            source = binding.freshness_assessment
            subclass = FreshnessSubclass(
                *(getattr(source, field.name)
                  for field in dataclasses.fields(FreshnessAssessment))
            )
            object.__setattr__(binding, "freshness_assessment", subclass)

        self._assert_proof_rejected(subclass_mutation)

    def test_semantic_and_reference_integrity_matrix(self):
        def quote_parts(assessment, bindings):
            binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
            member = next(
                member
                for member in assessment.request.groups[0].members
                if member.role is MarketDataRelationshipRole.OPTION_QUOTE
            )
            return binding, member

        mutations = {
            "reference_semantic": lambda a, b: object.__setattr__(
                quote_parts(a, b)[1].reference,
                "semantic_observation_key",
                "forged-reference",
            ),
            "coordinated_semantic_forgery": lambda a, b: (
                object.__setattr__(
                    quote_parts(a, b)[0].correction_selection,
                    "semantic_observation_key",
                    "coordinated-forgery",
                ),
                object.__setattr__(
                    quote_parts(a, b)[1].reference,
                    "semantic_observation_key",
                    "coordinated-forgery",
                ),
            ),
            "reference_selected_id": lambda a, b: object.__setattr__(
                quote_parts(a, b)[1].reference,
                "selected_record_id",
                "outside-timing-assessment",
            ),
        }
        for name, mutation in mutations.items():
            with self.subTest(name=name):
                self._assert_proof_rejected(mutation)

        def actual_record_semantic(_assessment, bindings):
            binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
            record = binding.selected_record
            object.__setattr__(
                record,
                "contract_key",
                dataclasses.replace(
                    record.contract_key, strike=decimal.Decimal("101")
                ),
            )

        self._assert_proof_rejected(actual_record_semantic)

        def candidate_semantic(_assessment, bindings):
            binding = bindings[MarketDataRelationshipRole.OPTION_QUOTE]
            selected = binding.selected_record
            discarded = dataclasses.replace(
                selected,
                contract_key=dataclasses.replace(
                    selected.contract_key, strike=decimal.Decimal("101")
                ),
                metadata=dataclasses.replace(
                    selected.metadata, record_id="semantic-mismatch-candidate"
                ),
            )
            object.__setattr__(
                binding, "candidate_records", (discarded, selected)
            )
            object.__setattr__(
                binding.correction_selection,
                "candidate_record_ids",
                tuple(sorted((
                    discarded.metadata.record_id,
                    selected.metadata.record_id,
                ))),
            )
            object.__setattr__(
                binding.correction_selection,
                "reason_codes",
                (
                    CorrectionSelectionReasonCode
                    .DOMINATING_REVISION_VECTOR_SELECTED,
                ),
            )

        self._assert_proof_rejected(candidate_semantic)

    def test_exact_sidecar_types_are_structural_prerequisites(self):
        sidecars = (
            ("correction_selection", CorrectionSelection),
            ("freshness_assessment", FreshnessAssessment),
            ("freshness_policy", MarketDataFreshnessPolicy),
            ("freshness_context", FreshnessContext),
        )
        for field_name, field_type in sidecars:
            for raw in (False, True):
                with self.subTest(field_name=field_name, raw=raw):
                    structure, selection, assessment, bindings = (
                        self._one_leg()
                    )
                    binding = bindings[
                        MarketDataRelationshipRole.OPTION_QUOTE
                    ]
                    if raw:
                        forged = object()
                    else:
                        class SidecarSubclass(field_type):
                            pass

                        source = getattr(binding, field_name)
                        forged = SidecarSubclass(
                            *(getattr(source, field.name)
                              for field in dataclasses.fields(field_type))
                        )
                    object.__setattr__(binding, field_name, forged)
                    with force_selected(assessment), mock.patch.object(
                        transformations,
                        "_resolve_selected_objects",
                        side_effect=AssertionError(
                            "selected resolution reached"
                        ),
                    ):
                        with self.assertRaises(TypeError):
                            transform(structure, selection)

    def test_unreferenced_reused_and_duplicate_selected_bindings(self):
        def extra_binding(assessment, bindings):
            timing = assessment.timing_assessment
            object.__setattr__(
                timing,
                "bindings",
                timing.bindings
                + (bindings[MarketDataRelationshipRole.OPTION_QUOTE],),
            )

        self._assert_proof_rejected(extra_binding)

        structure = make_structure(("call", "put"))
        selection, assessment, groups = make_selection(structure)
        first_quote = groups[0][MarketDataRelationshipRole.OPTION_QUOTE]
        second_member = next(
            member
            for member in assessment.request.groups[1].members
            if member.role is MarketDataRelationshipRole.OPTION_QUOTE
        )
        object.__setattr__(
            second_member.reference,
            "selected_record_id",
            first_quote.correction_selection.selected_record_id,
        )
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_match_structure_legs",
            side_effect=AssertionError("leg correspondence reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)


class CorrectedGlobalPrecedenceTests(unittest.TestCase):
    def test_early_phase_failures_poison_every_immediate_successor(self):
        structure = make_structure()
        selection, assessment, _bindings = make_selection(structure)
        scenarios = (
            (
                (object(), structure, selection, CALCULATED_AT),
                "_validate_structure",
                TypeError,
            ),
            (
                ("id", object(), selection, CALCULATED_AT),
                "_validate_relationship_selection",
                TypeError,
            ),
            (
                ("id", structure, object(), CALCULATED_AT),
                "_normalize_calculated_at",
                TypeError,
            ),
            (
                (
                    "id",
                    structure,
                    selection,
                    datetime.datetime(2030, 1, 2),
                ),
                "_validate_selection_status",
                ValueError,
            ),
        )
        for arguments, later, error in scenarios:
            with self.subTest(later=later), mock.patch.object(
                transformations,
                later,
                side_effect=AssertionError(f"{later} reached"),
            ):
                with self.assertRaises(error):
                    transform_structure_liquidity(*arguments)

        with mock.patch.object(
            transformations,
            "_validate_selection_status",
            side_effect=ValueError("not selected"),
        ), mock.patch.object(
            transformations,
            "_resolve_selected_candidate",
            side_effect=AssertionError("candidate reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_resolve_selected_candidate",
            side_effect=ValueError("missing candidate"),
        ), mock.patch.object(
            transformations,
            "_validate_selected_shape",
            side_effect=AssertionError("shape reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_validate_selected_shape",
            side_effect=ValueError("shape"),
        ), mock.patch.object(
            transformations,
            "_resolve_selected_objects",
            side_effect=AssertionError("resolution reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_resolve_selected_objects",
            side_effect=ValueError("resolution"),
        ), mock.patch.object(
            transformations,
            "_validate_selected_record_types",
            side_effect=AssertionError("type pass reached"),
        ):
            with self.assertRaises(ValueError):
                transform(structure, selection)

    def test_structural_types_and_cardinality_precede_selected_object_access(self):
        mutations = []

        def add(name, callback, error):
            mutations.append((name, callback, error))

        add(
            "extra_group",
            lambda assessment: object.__setattr__(
                assessment.request,
                "groups",
                assessment.request.groups
                + (dataclasses.replace(
                    assessment.request.groups[0], group_id="extra"
                ),),
            ),
            ValueError,
        )
        add(
            "repeated_role",
            lambda assessment: object.__setattr__(
                assessment.request.groups[0].members[1],
                "role",
                MarketDataRelationshipRole.OPTION_QUOTE,
            ),
            ValueError,
        )
        add(
            "wrong_reference",
            lambda assessment: object.__setattr__(
                assessment.request.groups[0].members[0],
                "reference",
                object(),
            ),
            TypeError,
        )
        add(
            "wrong_binding",
            lambda assessment: object.__setattr__(
                assessment.timing_assessment,
                "bindings",
                (object(),)
                + assessment.timing_assessment.bindings[1:],
            ),
            TypeError,
        )
        add(
            "reference_subclass",
            lambda assessment: object.__setattr__(
                assessment.request.groups[0].members[0],
                "reference",
                type(
                    "ReferenceSubclass",
                    (MarketDataBindingReference,),
                    {},
                )(
                    assessment.request.groups[0]
                    .members[0].reference.semantic_observation_key,
                    assessment.request.groups[0]
                    .members[0].reference.selected_record_id,
                ),
            ),
            TypeError,
        )
        add(
            "binding_subclass",
            lambda assessment: object.__setattr__(
                assessment.timing_assessment,
                "bindings",
                (
                    type(
                        "BindingSubclass",
                        (SelectedFreshMarketDataBinding,),
                        {},
                    )(
                        assessment.timing_assessment.bindings[0]
                        .candidate_records,
                        assessment.timing_assessment.bindings[0]
                        .correction_selection,
                        assessment.timing_assessment.bindings[0]
                        .freshness_policy,
                        assessment.timing_assessment.bindings[0]
                        .freshness_context,
                        assessment.timing_assessment.bindings[0]
                        .freshness_assessment,
                    ),
                )
                + assessment.timing_assessment.bindings[1:],
            ),
            TypeError,
        )
        for name, mutation, error in mutations:
            with self.subTest(name=name):
                structure = make_structure()
                selection, assessment, _bindings = make_selection(structure)
                mutation(assessment)
                with force_selected(assessment), mock.patch.object(
                    transformations,
                    "_resolve_selected_objects",
                    side_effect=AssertionError("selected object accessed"),
                ):
                    with self.assertRaises(error):
                        transform(structure, selection)

    def test_same_binding_wrong_type_precedes_forged_semantic_and_freshness(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote_binding = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        volume_record = bindings[0][
            MarketDataRelationshipRole.OPTION_VOLUME
        ].selected_record
        wrong_record = dataclasses.replace(
            volume_record,
            metadata=dataclasses.replace(
                volume_record.metadata,
                record_id=quote_binding.correction_selection.selected_record_id,
            ),
        )
        object.__setattr__(quote_binding, "candidate_records", (wrong_record,))
        object.__setattr__(
            quote_binding.correction_selection,
            "semantic_observation_key",
            "forged-semantic",
        )
        object.__setattr__(
            quote_binding.freshness_assessment,
            "status",
            FreshnessStatus.STALE,
        )
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_validate_proof_integrity",
            side_effect=AssertionError("proof integrity reached"),
        ):
            with self.assertRaises(TypeError):
                transform(structure, selection)

    def test_cross_binding_integrity_poison_loses_to_later_wrong_type_permutations(self):
        for reversed_groups in (False, True):
            for reversed_bindings in (False, True):
                with self.subTest(
                    reversed_groups=reversed_groups,
                    reversed_bindings=reversed_bindings,
                ):
                    self._run_cross_binding_permutation(
                        reversed_groups, reversed_bindings
                    )

    def _run_cross_binding_permutation(
        self,
        reversed_groups,
        reversed_bindings,
    ):
        structure = make_structure(("call", "put"))
        selection, assessment, bindings = make_selection(structure)
        first = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        object.__setattr__(
            first.freshness_assessment,
            "status",
            FreshnessStatus.STALE,
        )
        later = bindings[1][
            MarketDataRelationshipRole.OPTION_OPEN_INTEREST
        ]
        wrong = dataclasses.replace(
            bindings[1][
                MarketDataRelationshipRole.OPTION_VOLUME
            ].selected_record,
            metadata=dataclasses.replace(
                bindings[1][
                    MarketDataRelationshipRole.OPTION_VOLUME
                ].selected_record.metadata,
                record_id=later.correction_selection.selected_record_id,
            ),
        )
        object.__setattr__(later, "candidate_records", (wrong,))
        if reversed_groups:
            object.__setattr__(
                assessment.request,
                "groups",
                tuple(reversed(assessment.request.groups)),
            )
        if reversed_bindings:
            object.__setattr__(
                assessment.timing_assessment,
                "bindings",
                tuple(reversed(assessment.timing_assessment.bindings)),
            )
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_validate_proof_integrity",
            side_effect=AssertionError("proof integrity reached"),
        ):
            with self.assertRaises(TypeError):
                transform(structure, selection)

    def test_selected_record_subclass_is_rejected_before_integrity(self):
        class QuoteSubclass(OptionQuoteObservation):
            pass

        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        binding = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE]
        source = binding.selected_record
        subclass = QuoteSubclass(
            *(getattr(source, field.name)
              for field in dataclasses.fields(OptionQuoteObservation))
        )
        object.__setattr__(binding, "candidate_records", (subclass,))
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_validate_proof_integrity",
            side_effect=AssertionError("proof integrity reached"),
        ):
            with self.assertRaises(TypeError):
                transform(structure, selection)


class SecondReviewProofExactnessTests(unittest.TestCase):
    def _fixture(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        group_bindings = bindings[0]
        quote_binding = group_bindings[
            MarketDataRelationshipRole.OPTION_QUOTE
        ]
        quote_member = next(
            member
            for member in assessment.request.groups[0].members
            if member.role is MarketDataRelationshipRole.OPTION_QUOTE
        )
        return (
            structure,
            selection,
            assessment,
            group_bindings,
            quote_binding,
            quote_member,
        )

    def test_wrong_correction_sidecar_types_fail_shape_without_id_access(self):
        class PoisonCorrection:
            @property
            def selected_record_id(self):
                raise AssertionError("wrong correction sidecar accessed")

        for value in (PoisonCorrection(), object()):
            with self.subTest(value=type(value).__name__):
                (
                    structure,
                    selection,
                    assessment,
                    _bindings,
                    quote_binding,
                    _member,
                ) = self._fixture()
                object.__setattr__(
                    quote_binding, "correction_selection", value
                )
                with force_selected(assessment), mock.patch.object(
                    transformations,
                    "_resolve_selected_objects",
                    side_effect=AssertionError("selected resolution reached"),
                ):
                    with self.assertRaises(TypeError):
                        transform(structure, selection)

        class CorrectionSubclass(CorrectionSelection):
            pass

        (
            structure,
            selection,
            assessment,
            _bindings,
            quote_binding,
            _member,
        ) = self._fixture()
        source = quote_binding.correction_selection
        subclass = CorrectionSubclass(
            *(getattr(source, field.name)
              for field in dataclasses.fields(CorrectionSelection))
        )
        object.__setattr__(quote_binding, "correction_selection", subclass)
        with force_selected(assessment), mock.patch.object(
            transformations,
            "_resolve_selected_objects",
            side_effect=AssertionError("selected resolution reached"),
        ):
            with self.assertRaises(TypeError):
                transform(structure, selection)

    def test_exact_correction_reason_values_reject_strings_and_foreign_enums(self):
        class ForeignCorrectionReason(str, enum.Enum):
            ONLY = "only_candidate_selected"

        class StringSubclass(str):
            pass

        values = (
            ("only_candidate_selected",),
            ("dominating_revision_vector_selected",),
            ("foreign_reason",),
            (ForeignCorrectionReason.ONLY,),
            (StringSubclass("only_candidate_selected"),),
            [
                CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED
            ],
            (
                CorrectionSelectionReasonCode.ONLY_CANDIDATE_SELECTED,
                CorrectionSelectionReasonCode
                .DOMINATING_REVISION_VECTOR_SELECTED,
            ),
        )
        for reasons in values:
            with self.subTest(reasons=reasons):
                (
                    structure,
                    selection,
                    assessment,
                    _bindings,
                    quote_binding,
                    _member,
                ) = self._fixture()
                object.__setattr__(
                    quote_binding.correction_selection,
                    "reason_codes",
                    reasons,
                )
                with force_selected(assessment), self.assertRaises(ValueError):
                    transform(structure, selection)

    def test_exact_freshness_reason_category_and_status_values(self):
        class ForeignFreshnessReason(str, enum.Enum):
            FRESH = "fresh_within_policy"

        class ForeignCategory(str, enum.Enum):
            QUOTE = "quote"

        malformed = (
            ("reason", ("fresh_within_policy",)),
            ("reason", ("foreign_reason",)),
            ("reason", (ForeignFreshnessReason.FRESH,)),
            ("reason", (FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,)),
            ("reason", [FreshnessReasonCode.FRESH_WITHIN_POLICY]),
            (
                "reason",
                (
                    FreshnessReasonCode.FRESH_WITHIN_POLICY,
                    FreshnessReasonCode.EFFECTIVE_AGE_EXCEEDED,
                ),
            ),
            ("category", "quote"),
            ("category", ForeignCategory.QUOTE),
            ("status", "fresh"),
        )
        for field, value in malformed:
            with self.subTest(field=field, value=value):
                (
                    structure,
                    selection,
                    assessment,
                    _bindings,
                    quote_binding,
                    _member,
                ) = self._fixture()
                target_field = "reason_codes" if field == "reason" else field
                object.__setattr__(
                    quote_binding.freshness_assessment,
                    target_field,
                    value,
                )
                with force_selected(assessment), self.assertRaises(ValueError):
                    transform(structure, selection)

    def test_coordinated_malformed_retained_ids_never_pass(self):
        class StringSubclass(str):
            pass

        malformed = (
            ("", ValueError),
            ("   ", ValueError),
            (" id", ValueError),
            ("id ", ValueError),
            (StringSubclass("id"), TypeError),
            (7, TypeError),
        )
        for value, error in malformed:
            with self.subTest(value=repr(value)):
                (
                    structure,
                    selection,
                    assessment,
                    _bindings,
                    quote_binding,
                    quote_member,
                ) = self._fixture()
                record = quote_binding.selected_record
                object.__setattr__(
                    record.metadata,
                    "record_id",
                    value,
                )
                object.__setattr__(
                    quote_binding.correction_selection,
                    "candidate_record_ids",
                    (value,),
                )
                object.__setattr__(
                    quote_binding.correction_selection,
                    "selected_record_id",
                    value,
                )
                object.__setattr__(
                    quote_binding.freshness_assessment,
                    "record_id",
                    value,
                )
                object.__setattr__(
                    quote_member.reference,
                    "selected_record_id",
                    value,
                )
                with force_selected(assessment), mock.patch.object(
                    transformations,
                    "_match_structure_legs",
                    side_effect=AssertionError("correspondence reached"),
                ):
                    with self.assertRaises(error):
                        transform(structure, selection)

    def test_each_role_specific_selected_record_subclass_is_rejected_globally(self):
        cases = (
            (
                MarketDataRelationshipRole.OPTION_QUOTE,
                OptionQuoteObservation,
            ),
            (
                MarketDataRelationshipRole.OPTION_VOLUME,
                OptionVolumeObservation,
            ),
            (
                MarketDataRelationshipRole.OPTION_OPEN_INTEREST,
                OptionOpenInterestObservation,
            ),
        )
        for role, record_type in cases:
            with self.subTest(role=role):
                (
                    structure,
                    selection,
                    assessment,
                    bindings,
                    _quote_binding,
                    _member,
                ) = self._fixture()
                binding = bindings[role]
                source = binding.selected_record
                subclass_type = type(
                    f"{record_type.__name__}Subclass",
                    (record_type,),
                    {},
                )
                subclass = subclass_type(
                    *(getattr(source, field.name)
                      for field in dataclasses.fields(record_type))
                )
                object.__setattr__(binding, "candidate_records", (subclass,))
                with force_selected(assessment), mock.patch.object(
                    transformations,
                    "_validate_proof_integrity",
                    side_effect=AssertionError("proof integrity reached"),
                ):
                    with self.assertRaises(TypeError):
                        transform(structure, selection)


class CorrectedDecimalContextTests(unittest.TestCase):
    def _assert_context_unchanged(self, ambient, before):
        self.assertEqual(ambient.prec, before.prec)
        self.assertEqual(ambient.rounding, before.rounding)
        self.assertEqual(ambient.Emin, before.Emin)
        self.assertEqual(ambient.Emax, before.Emax)
        self.assertEqual(ambient.capitals, before.capitals)
        self.assertEqual(ambient.clamp, before.clamp)
        self.assertEqual(dict(ambient.traps), dict(before.traps))
        self.assertEqual(dict(ambient.flags), dict(before.flags))

    @contextmanager
    def _record_phases(self, phases):
        with ExitStack() as stack:
            for phase, helper_name in (
                CorrectedPhaseSequenceTests.PHASE_HELPERS
            ):
                original = getattr(transformations, helper_name)

                def wrapper(
                    *args,
                    _phase=phase,
                    _original=original,
                    **kwargs,
                ):
                    if not phases or phases[-1] != _phase:
                        phases.append(_phase)
                    return _original(*args, **kwargs)

                stack.enter_context(mock.patch.object(
                    transformations, helper_name, wrapper
                ))
            yield

    def test_exact_results_are_invariant_under_adversarial_ambient_contexts(self):
        structure = make_structure(
            ("call", "put"), quantity=999, multiplier=1000
        )
        selection, _, _ = make_selection(
            structure,
            bid=("9.9900", "0.010"),
            ask=("10.0100", "0.020"),
        )
        cases = (
            (2, decimal.ROUND_FLOOR, False),
            (6, decimal.ROUND_CEILING, False),
            (28, decimal.ROUND_HALF_UP, False),
            (2, decimal.ROUND_DOWN, True),
        )
        for precision, rounding, trap in cases:
            with self.subTest(
                precision=precision, rounding=rounding, trap=trap
            ), decimal.localcontext() as ambient:
                ambient.prec = precision
                ambient.rounding = rounding
                ambient.traps[decimal.Inexact] = trap
                ambient.traps[decimal.Rounded] = trap
                before = ambient.copy()
                result = transform(structure, selection)
                self.assertEqual(result.record.quoted_bid_value, 9990000.0)
                self.assertEqual(result.record.quoted_ask_value, 10019970.0)
                self.assertEqual(ambient.prec, before.prec)
                self.assertEqual(ambient.rounding, before.rounding)
                self.assertEqual(ambient.Emin, before.Emin)
                self.assertEqual(ambient.Emax, before.Emax)
                self.assertEqual(ambient.clamp, before.clamp)
                self.assertEqual(dict(ambient.traps), dict(before.traps))
                self.assertEqual(dict(ambient.flags), dict(before.flags))

    def test_reviewed_one_leg_reproduction_survives_precision_two(self):
        structure = make_structure()
        selection, _, _ = make_selection(
            structure, bid=("1.25", "2"), ask=("1.50", "2")
        )
        with decimal.localcontext() as ambient:
            ambient.prec = 2
            ambient.traps[decimal.Inexact] = True
            ambient.traps[decimal.Rounded] = True
            result = transform(structure, selection)
        self.assertEqual(result.record.quoted_bid_value, 125.0)
        self.assertEqual(result.record.quoted_ask_value, 150.0)

    def test_ambient_context_is_unchanged_on_failure(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE].selected_record
        object.__setattr__(quote, "bid_premium", decimal.Decimal("1e10000"))
        object.__setattr__(quote, "ask_premium", decimal.Decimal("2e10000"))
        with decimal.localcontext() as ambient:
            ambient.prec = 2
            ambient.rounding = decimal.ROUND_FLOOR
            ambient.traps[decimal.Inexact] = True
            ambient.traps[decimal.Rounded] = True
            before = ambient.copy()
            with force_selected(assessment), self.assertRaises(ValueError):
                transform(structure, selection)
            self.assertEqual(ambient.prec, before.prec)
            self.assertEqual(ambient.rounding, before.rounding)
            self.assertEqual(dict(ambient.traps), dict(before.traps))
            self.assertEqual(dict(ambient.flags), dict(before.flags))

    def test_upper_exponent_failures_are_value_errors_in_all_caller_contexts(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        quote = bindings[0][MarketDataRelationshipRole.OPTION_QUOTE].selected_record
        object.__setattr__(
            quote,
            "bid_premium",
            decimal.Decimal("1e999999999999999999"),
        )
        object.__setattr__(
            quote,
            "ask_premium",
            decimal.Decimal("2e999999999999999999"),
        )
        cases = (
            (2, decimal.ROUND_FLOOR),
            (6, decimal.ROUND_CEILING),
            (28, decimal.ROUND_DOWN),
        )
        for precision, rounding in cases:
            with self.subTest(
                precision=precision, rounding=rounding
            ), decimal.localcontext() as ambient:
                phases = []
                ambient.prec = precision
                ambient.rounding = rounding
                ambient.traps[decimal.Inexact] = True
                ambient.traps[decimal.Rounded] = True
                ambient.traps[decimal.Overflow] = True
                before = ambient.copy()
                with force_selected(assessment), ExitStack() as stack:
                    for phase, helper_name in (
                        CorrectedPhaseSequenceTests.PHASE_HELPERS
                    ):
                        original = getattr(transformations, helper_name)

                        def wrapper(
                            *args,
                            _phase=phase,
                            _original=original,
                            **kwargs,
                        ):
                            if not phases or phases[-1] != _phase:
                                phases.append(_phase)
                            return _original(*args, **kwargs)

                        stack.enter_context(mock.patch.object(
                            transformations, helper_name, wrapper
                        ))
                    with self.assertRaises(ValueError) as raised:
                        transform(structure, selection)
                self.assertNotIsInstance(
                    raised.exception, decimal.DecimalException
                )
                self.assertIn(
                    "Decimal aggregation", str(raised.exception)
                )
                self.assertEqual(ambient.prec, before.prec)
                self.assertEqual(ambient.rounding, before.rounding)
                self.assertEqual(dict(ambient.traps), dict(before.traps))
                self.assertEqual(dict(ambient.flags), dict(before.flags))
                self.assertEqual(
                    tuple(phases),
                    tuple(
                        phase
                        for phase, _helper_name in (
                            CorrectedPhaseSequenceTests.PHASE_HELPERS
                        )[:14]
                    ),
                )

    def test_lower_exponent_representability_and_rejection_are_deterministic(self):
        representable = decimal.Decimal(
            (0, (1,), decimal.MIN_EMIN)
        )
        exact = transformations._exact_scaled_sum(((representable, 100),))
        self.assertEqual(
            exact.as_tuple(),
            decimal.Decimal(
                (0, (1, 0, 0), decimal.MIN_EMIN)
            ).as_tuple(),
        )

        unrepresentable = decimal.Decimal(
            (0, (1,), decimal.MIN_EMIN - 20)
        )
        for precision in (2, 6, 28):
            with self.subTest(precision=precision), decimal.localcontext() as ambient:
                ambient.prec = precision
                ambient.traps[decimal.Inexact] = True
                ambient.traps[decimal.Rounded] = True
                ambient.traps[decimal.Overflow] = True
                before = ambient.copy()
                with self.assertRaises(ValueError) as raised:
                    transformations._exact_scaled_sum(
                        ((unrepresentable, 100),)
                    )
                self.assertNotIsInstance(
                    raised.exception, decimal.DecimalException
                )
                self.assertEqual(ambient.prec, before.prec)
                self.assertEqual(dict(ambient.traps), dict(before.traps))
                self.assertEqual(dict(ambient.flags), dict(before.flags))

    def test_max_emax_coefficient_carry_matrix_is_exact_and_context_isolated(self):
        one = decimal.Decimal((0, (1,), decimal.MAX_EMAX))
        nine = decimal.Decimal((0, (9,), decimal.MAX_EMAX))
        lower = decimal.Decimal((0, (1,), decimal.MAX_EMAX - 1))
        cases = (
            (
                "two_terms",
                ((one, 1), (one, 1)),
                decimal.Decimal((0, (2,), decimal.MAX_EMAX)),
            ),
            (
                "several_terms",
                tuple((one, 1) for _index in range(8)),
                decimal.Decimal((0, (8,), decimal.MAX_EMAX)),
            ),
            (
                "different_exponents",
                ((one, 1), (lower, 1)),
                decimal.Decimal((0, (1, 1), decimal.MAX_EMAX - 1)),
            ),
        )
        caller_contexts = (
            (2, decimal.ROUND_FLOOR),
            (6, decimal.ROUND_CEILING),
            (28, decimal.ROUND_DOWN),
        )
        for precision, rounding in caller_contexts:
            with self.subTest(
                precision=precision, rounding=rounding
            ), decimal.localcontext() as ambient:
                ambient.prec = precision
                ambient.rounding = rounding
                ambient.traps[decimal.Inexact] = True
                ambient.traps[decimal.Rounded] = True
                ambient.traps[decimal.Overflow] = True
                before = ambient.copy()
                for name, terms, expected in cases:
                    with self.subTest(name=name):
                        result = transformations._exact_scaled_sum(terms)
                        self.assertEqual(result.as_tuple(), expected.as_tuple())
                        self._assert_context_unchanged(ambient, before)
                with self.assertRaises(ValueError) as raised:
                    transformations._exact_scaled_sum(
                        ((nine, 1), (one, 1))
                    )
                self.assertNotIsInstance(
                    raised.exception, decimal.DecimalException
                )
                self.assertIsInstance(
                    raised.exception.__cause__, decimal.DecimalException
                )
                self._assert_context_unchanged(ambient, before)

    def test_public_upper_boundary_reaches_float_and_actual_sum_overflow_does_not(self):
        one = decimal.Decimal((0, (1,), decimal.MAX_EMAX))
        two = decimal.Decimal((0, (2,), decimal.MAX_EMAX))
        nine = decimal.Decimal((0, (9,), decimal.MAX_EMAX))
        nine_point_one = decimal.Decimal(
            (0, (9, 1), decimal.MAX_EMAX - 1)
        )
        expected_bid = decimal.Decimal(
            (0, (2,), decimal.MAX_EMAX)
        )
        expected_ask = decimal.Decimal(
            (0, (4,), decimal.MAX_EMAX)
        )
        expected_prefix = tuple(
            phase
            for phase, _helper_name in (
                CorrectedPhaseSequenceTests.PHASE_HELPERS
            )
        )

        structure = make_structure(
            ("call", "put"), quantity=1, multiplier=1
        )
        selection, assessment, _bindings = make_selection(
            structure,
            bid=(one, one),
            ask=(two, two),
        )
        phases = []

        def reject_float_boundary(bid_value, ask_value):
            if not phases or phases[-1] != "float_boundary":
                phases.append("float_boundary")
            self.assertEqual(
                (bid_value.as_tuple(), ask_value.as_tuple()),
                (
                    expected_bid.as_tuple(),
                    expected_ask.as_tuple(),
                ),
            )
            raise ValueError("position values must be finite floats")

        with force_selected(assessment), self._record_phases(phases), (
            mock.patch.object(
                transformations,
                "_convert_position_values",
                side_effect=reject_float_boundary,
            )
        ), self.assertRaises(ValueError) as raised:
            transform(structure, selection)
        self.assertNotIsInstance(raised.exception, decimal.DecimalException)
        self.assertEqual(tuple(phases), expected_prefix[:15])

        overflow_selection, overflow_assessment, _bindings = make_selection(
            structure,
            bid=(nine, one),
            ask=(nine_point_one, two),
        )
        phases = []
        with force_selected(overflow_assessment), self._record_phases(phases), (
            mock.patch.object(
                transformations,
                "_convert_position_values",
                side_effect=AssertionError("float boundary reached"),
            )
        ), self.assertRaises(ValueError) as raised:
            transform(structure, overflow_selection)
        self.assertNotIsInstance(raised.exception, decimal.DecimalException)
        self.assertIsInstance(
            raised.exception.__cause__, decimal.DecimalException
        )
        self.assertEqual(tuple(phases), expected_prefix[:14])


class CorrectedPhaseSequenceTests(unittest.TestCase):
    PHASE_HELPERS = (
        ("calculation_id", "_validate_calculation_id"),
        ("structure", "_validate_structure"),
        ("relationship_selection", "_validate_relationship_selection"),
        ("calculated_at", "_normalize_calculated_at"),
        ("selection_status", "_validate_selection_status"),
        ("selected_candidate", "_resolve_selected_candidate"),
        ("shape", "_validate_selected_shape"),
        ("selected_resolution", "_resolve_selected_objects"),
        ("selected_record_types", "_validate_selected_record_types"),
        ("proof_integrity", "_validate_proof_integrity"),
        ("leg_correspondence", "_match_structure_legs"),
        ("contract_session", "_validate_contract_sessions"),
        ("required_values", "_validate_required_values"),
        ("decimal_aggregation", "_aggregate_decimal_values"),
        ("float_boundary", "_convert_position_values"),
        ("research_record", "_construct_research_record"),
        ("input_references", "_construct_input_references"),
        ("parameters", "_construct_parameters"),
        ("quality_flags", "_derive_quality_flags"),
        ("lineage", "_construct_lineage"),
        ("result", "_construct_result"),
    )

    def test_success_has_exact_literal_21_phase_sequence(self):
        structure = make_structure()
        selection, _, _ = make_selection(structure)
        phases = []
        with ExitStack() as stack:
            for phase, helper_name in self.PHASE_HELPERS:
                original = getattr(transformations, helper_name)

                def wrapper(*args, _phase=phase, _original=original, **kwargs):
                    if not phases or phases[-1] != _phase:
                        phases.append(_phase)
                    return _original(*args, **kwargs)

                stack.enter_context(mock.patch.object(
                    transformations, helper_name, side_effect=wrapper
                ))
            transform(structure, selection)
        expected = tuple(phase for phase, _helper in self.PHASE_HELPERS)
        self.assertEqual(tuple(phases), expected)
        mutations = (
            expected[:-1],
            expected[:8] + expected[9:],
            expected[:8] + (expected[7],) + expected[8:],
            expected + ("trailing",),
        )
        for mutated in mutations:
            with self.subTest(mutated=mutated):
                self.assertNotEqual(mutated, expected)

    def test_each_late_failure_poison_protects_the_next_phase(self):
        structure = make_structure()
        selection, assessment, bindings = make_selection(structure)
        scenarios = (
            ("_validate_proof_integrity", ValueError("proof"),
             "_match_structure_legs"),
            ("_match_structure_legs", ValueError("leg"),
             "_validate_contract_sessions"),
            ("_validate_contract_sessions", ValueError("session"),
             "_validate_required_values"),
            ("_validate_required_values", ValueError("values"),
             "_aggregate_decimal_values"),
            ("_aggregate_decimal_values", decimal.Inexact(),
             "_convert_position_values"),
            ("_convert_position_values", ValueError("float"),
             "_construct_research_record"),
            ("_construct_research_record", ValueError("record"),
             "_construct_input_references"),
            ("_construct_input_references", ValueError("inputs"),
             "_construct_parameters"),
            ("_construct_parameters", ValueError("parameters"),
             "_derive_quality_flags"),
            ("_derive_quality_flags", ValueError("flags"),
             "_construct_lineage"),
            ("_construct_lineage", ValueError("lineage"),
             "_construct_result"),
        )
        for failing, error, later in scenarios:
            with self.subTest(failing=failing), force_selected(assessment):
                with mock.patch.object(
                    transformations, failing, side_effect=error
                ), mock.patch.object(
                    transformations,
                    later,
                    side_effect=AssertionError(f"{later} reached"),
                ):
                    with self.assertRaises(type(error)):
                        transform(structure, selection)


if __name__ == "__main__":
    unittest.main()
