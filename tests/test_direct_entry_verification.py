"""Focused contract tests for deterministic direct-entry verification."""

import copy
import dataclasses
import datetime
import decimal
import inspect
import pathlib
import sys
import unittest
from contextlib import ExitStack
from dataclasses import FrozenInstanceError
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
import convexity_hunter.direct_entry_verification as direct_entry_verification
import convexity_hunter.market_data as market_data
import convexity_hunter.market_data_transformations as transformations
from convexity_hunter.evidence import OptionStructure
from convexity_hunter.market_data_transformations import (
    StructureCostsTransformationResult,
    StructureLiquidityTransformationResult,
)
from tests import market_data_fixtures
from tests import test_market_data_transformations as transformation_tests


class _NestedPropertyBomb:
    @property
    def record(self):
        raise AssertionError("record was read before top-level validation")

    @property
    def lineage(self):
        raise AssertionError("lineage was read before top-level validation")


def _bypassed_dataclass(instance, **overrides):
    forged = object.__new__(type(instance))
    for field in dataclasses.fields(instance):
        object.__setattr__(forged, field.name, getattr(instance, field.name))
    for name, value in overrides.items():
        object.__setattr__(forged, name, value)
    return forged


def _reference_for_leg(leg, **overrides):
    key = market_data_fixtures.build_option_contract_key(
        expiration=leg.expiration,
        option_type=leg.option_type,
        strike=decimal.Decimal(str(leg.strike)),
        contract_multiplier=leg.contract_multiplier,
    )
    values = {"contract_key": key}
    values.update(overrides)
    return market_data_fixtures.build_option_contract_reference(**values)


class DirectEntryExactContractVerificationTests(unittest.TestCase):
    def setUp(self):
        self.structure = transformation_tests.make_structure()
        self.references = tuple(
            _reference_for_leg(leg) for leg in self.structure.legs
        )

    def test_result_shape_signature_and_identity_retention(self):
        result_type = (
            direct_entry_verification.DirectEntryExactContractVerification
        )
        self.assertTrue(dataclasses.is_dataclass(result_type))
        self.assertTrue(result_type.__dataclass_params__.frozen)
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(result_type)),
            ("structure", "contract_references"),
        )
        signature = inspect.signature(
            direct_entry_verification.verify_direct_entry_exact_contracts
        )
        self.assertEqual(
            tuple(signature.parameters),
            ("structure", "contract_references"),
        )
        result = direct_entry_verification.verify_direct_entry_exact_contracts(
            self.structure,
            self.references,
        )
        self.assertIs(result.structure, self.structure)
        self.assertIs(result.contract_references, self.references)
        with self.assertRaises(FrozenInstanceError):
            result.structure = self.structure

    def test_exact_top_level_types_and_one_to_one_cardinality(self):
        with self.assertRaisesRegex(TypeError, "exact type OptionStructure"):
            direct_entry_verification.verify_direct_entry_exact_contracts(
                object(), self.references
            )
        with self.assertRaisesRegex(TypeError, "exact type tuple"):
            direct_entry_verification.verify_direct_entry_exact_contracts(
                self.structure, list(self.references)
            )
        with self.assertRaisesRegex(TypeError, "every contract reference"):
            direct_entry_verification.verify_direct_entry_exact_contracts(
                self.structure, (object(),)
            )
        with self.assertRaisesRegex(ValueError, "one-to-one"):
            direct_entry_verification.verify_direct_entry_exact_contracts(
                self.structure, ()
            )

    def test_nested_structure_constructor_bypass_is_rejected(self):
        leg = self.structure.legs[0]
        forged_leg = _bypassed_dataclass(leg, quantity=0)
        forged_structure = _bypassed_dataclass(
            self.structure,
            legs=(forged_leg,),
        )
        with self.assertRaisesRegex(ValueError, "structure is intrinsically invalid"):
            direct_entry_verification.verify_direct_entry_exact_contracts(
                forged_structure,
                self.references,
            )

    def test_every_economic_identity_field_is_fail_closed(self):
        leg = self.structure.legs[0]
        mismatches = (
            {"underlying_key": market_data_fixtures.build_underlying_key(symbol="QQQ")},
            {"expiration": leg.expiration + datetime.timedelta(days=1)},
            {"option_type": "put"},
            {"strike": decimal.Decimal(str(leg.strike + 1))},
            {"contract_multiplier": leg.contract_multiplier + 1},
        )
        for key_overrides in mismatches:
            with self.subTest(key_overrides=key_overrides):
                key_values = {
                    "expiration": leg.expiration,
                    "option_type": leg.option_type,
                    "strike": decimal.Decimal(str(leg.strike)),
                    "contract_multiplier": leg.contract_multiplier,
                }
                key_values.update(key_overrides)
                key = market_data_fixtures.build_option_contract_key(**key_values)
                reference = market_data_fixtures.build_option_contract_reference(
                    contract_key=key
                )
                with self.assertRaisesRegex(ValueError, "does not match"):
                    direct_entry_verification.verify_direct_entry_exact_contracts(
                        self.structure, (reference,)
                    )

    def test_incomplete_reference_remains_eligible_for_identity_only(self):
        reference = self.references[0]
        metadata = dataclasses.replace(
            reference.metadata,
            quality_flags=(market_data.NormalizationQualityFlag.INCOMPLETE,),
        )
        incomplete = dataclasses.replace(
            reference,
            listing_date=None,
            last_trade_date=None,
            exercise_style=None,
            settlement_type=None,
            metadata=metadata,
        )
        result = direct_entry_verification.verify_direct_entry_exact_contracts(
            self.structure,
            (incomplete,),
        )
        self.assertIs(result.contract_references[0], incomplete)
        self.assertIn(
            market_data.NormalizationQualityFlag.INCOMPLETE,
            result.contract_references[0].metadata.quality_flags,
        )

    def test_straddle_requires_leg_order_and_distinct_reference_identity(self):
        structure = transformation_tests.make_structure(("call", "put"))
        references = tuple(
            dataclasses.replace(
                _reference_for_leg(leg),
                metadata=dataclasses.replace(
                    _reference_for_leg(leg).metadata,
                    record_id=f"straddle-reference-{index}",
                ),
            )
            for index, leg in enumerate(structure.legs)
        )
        result = direct_entry_verification.verify_direct_entry_exact_contracts(
            structure,
            references,
        )
        self.assertIs(result.contract_references, references)
        with self.assertRaisesRegex(ValueError, "does not match"):
            direct_entry_verification.verify_direct_entry_exact_contracts(
                structure,
                tuple(reversed(references)),
            )
        duplicate_ids = tuple(
            dataclasses.replace(
                reference,
                metadata=dataclasses.replace(
                    reference.metadata,
                    record_id="duplicate-reference",
                ),
            )
            for reference in references
        )
        with self.assertRaisesRegex(ValueError, "pairwise distinct"):
            direct_entry_verification.verify_direct_entry_exact_contracts(
                structure,
                duplicate_ids,
            )

    def test_rejects_non_provider_source_and_constructor_bypass(self):
        reference = self.references[0]
        bad_source = dataclasses.replace(
            reference.metadata.source_references[0],
            origin=market_data.DataOrigin.EXCHANGE_OBSERVED,
        )
        bad_metadata = _bypassed_dataclass(
            reference.metadata,
            source_references=(bad_source,),
        )
        forged = _bypassed_dataclass(reference, metadata=bad_metadata)
        with self.assertRaises((TypeError, ValueError)):
            direct_entry_verification.DirectEntryExactContractVerification(
                self.structure,
                (forged,),
            )

    def test_recursive_reconstruction_rejects_nested_constructor_bypasses(self):
        reference = self.references[0]
        key = reference.contract_key
        source = reference.metadata.source_references[0]
        forged_underlying = _bypassed_dataclass(
            key.underlying_key,
            currency="EUR",
        )
        forged_key = _bypassed_dataclass(
            key,
            underlying_key=forged_underlying,
            currency="EUR",
        )
        forged_source = _bypassed_dataclass(
            source,
            is_delayed=True,
            declared_delay_seconds=None,
        )
        forged_source_metadata = _bypassed_dataclass(
            reference.metadata,
            source_references=(forged_source,),
        )
        forged_composite_metadata = _bypassed_dataclass(
            reference.metadata,
            record_origin=market_data.DataOrigin.SYSTEM_COMPOSITE,
        )
        forged_values = (
            _bypassed_dataclass(reference, contract_key=forged_key),
            _bypassed_dataclass(reference, metadata=forged_source_metadata),
            _bypassed_dataclass(reference, metadata=forged_composite_metadata),
        )
        for forged in forged_values:
            with self.subTest(forged=forged):
                with self.assertRaisesRegex(ValueError, "intrinsically invalid"):
                    direct_entry_verification.verify_direct_entry_exact_contracts(
                        self.structure,
                        (forged,),
                    )


class DirectEntryResearchReadinessVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.structure = transformation_tests.make_structure()

        costs_structure = transformation_tests.make_structure()
        costs_selection, _, _, _ = transformation_tests.make_cost_selection(
            costs_structure
        )
        cls.costs_result = transformation_tests.transform_costs(
            costs_structure,
            costs_selection,
            calculation_id="direct-entry-costs",
            calculated_at=(
                transformation_tests.CALCULATED_AT
                + datetime.timedelta(seconds=1)
            ),
        )

        liquidity_structure = transformation_tests.make_structure()
        liquidity_selection, _, _ = transformation_tests.make_selection(
            liquidity_structure
        )
        cls.liquidity_result = transformation_tests.transform(
            liquidity_structure,
            liquidity_selection,
        )

        mismatch_structure = transformation_tests.make_structure(("put",))
        mismatch_selection, _, _ = transformation_tests.make_selection(
            mismatch_structure
        )
        cls.mismatched_liquidity_result = transformation_tests.transform(
            mismatch_structure,
            mismatch_selection,
        )

        alternate_date = market_data_fixtures.SESSION_DATE - datetime.timedelta(
            days=1
        )
        with mock.patch.object(
            market_data_fixtures, "SESSION_DATE", alternate_date
        ), mock.patch.object(
            transformation_tests, "SESSION_DATE", alternate_date
        ):
            alternate_structure = transformation_tests.make_structure()
            alternate_selection, _, _ = transformation_tests.make_selection(
                alternate_structure
            )
            cls.alternate_liquidity_result = transformation_tests.transform(
                alternate_structure,
                alternate_selection,
            )

            alternate_mismatch_structure = transformation_tests.make_structure(
                ("put",)
            )
            alternate_mismatch_selection, _, _ = (
                transformation_tests.make_selection(alternate_mismatch_structure)
            )
            cls.alternate_mismatched_liquidity_result = (
                transformation_tests.transform(
                    alternate_mismatch_structure,
                    alternate_mismatch_selection,
                )
            )

    def _constructors(self):
        return (
            direct_entry_verification.DirectEntryResearchReadinessVerification,
            direct_entry_verification.verify_direct_entry_research_readiness,
        )

    def test_public_api_and_frozen_result_shape(self):
        self.assertEqual(
            direct_entry_verification.__all__,
            (
                "DirectEntryExactContractVerification",
                "verify_direct_entry_exact_contracts",
                "DirectEntryResearchReadinessVerification",
                "verify_direct_entry_research_readiness",
            ),
        )
        self.assertEqual(
            tuple(
                name
                for name in direct_entry_verification.__dict__
                if not name.startswith("_")
            ),
            direct_entry_verification.__all__,
        )
        self.assertFalse(
            hasattr(
                convexity_hunter,
                "DirectEntryResearchReadinessVerification",
            )
        )
        self.assertFalse(
            hasattr(convexity_hunter, "verify_direct_entry_research_readiness")
        )

        result_type = direct_entry_verification.DirectEntryResearchReadinessVerification
        self.assertTrue(dataclasses.is_dataclass(result_type))
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(result_type)),
            ("structure", "costs_result", "liquidity_result"),
        )
        self.assertEqual(
            tuple(field.type for field in dataclasses.fields(result_type)),
            (
                OptionStructure,
                StructureCostsTransformationResult,
                StructureLiquidityTransformationResult,
            ),
        )

        signature = inspect.signature(
            direct_entry_verification.verify_direct_entry_research_readiness
        )
        self.assertEqual(
            tuple(signature.parameters),
            ("structure", "costs_result", "liquidity_result"),
        )
        self.assertIs(
            signature.parameters["structure"].annotation,
            OptionStructure,
        )
        self.assertIs(
            signature.parameters["costs_result"].annotation,
            StructureCostsTransformationResult,
        )
        self.assertIs(
            signature.parameters["liquidity_result"].annotation,
            StructureLiquidityTransformationResult,
        )
        self.assertIs(
            signature.return_annotation,
            direct_entry_verification.DirectEntryResearchReadinessVerification,
        )

        result = direct_entry_verification.verify_direct_entry_research_readiness(
            self.structure,
            self.costs_result,
            self.liquidity_result,
        )
        with self.assertRaises(FrozenInstanceError):
            result.structure = self.structure

    def test_success_accepts_independent_equal_values_and_retains_identity(self):
        self.assertIsNot(self.structure, self.costs_result.record.structure)
        self.assertIsNot(self.structure, self.liquidity_result.record.structure)
        self.assertEqual(
            self.costs_result.record.structure,
            self.liquidity_result.record.structure,
        )
        self.assertNotEqual(
            self.costs_result.lineage.calculation_id,
            self.liquidity_result.lineage.calculation_id,
        )
        self.assertNotEqual(
            self.costs_result.lineage.calculated_at,
            self.liquidity_result.lineage.calculated_at,
        )

        result = direct_entry_verification.verify_direct_entry_research_readiness(
            self.structure,
            self.costs_result,
            self.liquidity_result,
        )
        self.assertIs(result.structure, self.structure)
        self.assertIs(result.costs_result, self.costs_result)
        self.assertIs(result.liquidity_result, self.liquidity_result)

    def test_exact_top_level_types_are_checked_before_nested_access(self):
        invalid_arguments = (
            (
                _NestedPropertyBomb(),
                _NestedPropertyBomb(),
                _NestedPropertyBomb(),
                "structure must have exact type OptionStructure",
            ),
            (
                self.structure,
                _NestedPropertyBomb(),
                _NestedPropertyBomb(),
                "costs_result must have exact type",
            ),
            (
                self.structure,
                self.costs_result,
                _NestedPropertyBomb(),
                "liquidity_result must have exact type",
            ),
        )
        for constructor in self._constructors():
            for structure, costs, liquidity, message in invalid_arguments:
                with self.subTest(constructor=constructor, message=message):
                    with self.assertRaisesRegex(TypeError, message):
                        constructor(structure, costs, liquidity)

    def test_subclasses_are_rejected_by_both_public_paths(self):
        class StructureSubclass(OptionStructure):
            pass

        class CostsResultSubclass(StructureCostsTransformationResult):
            pass

        class LiquidityResultSubclass(StructureLiquidityTransformationResult):
            pass

        structure_subclass = StructureSubclass(
            self.structure.legs,
            self.structure.assumed_portfolio_value,
            self.structure.expected_holding_days,
        )
        costs_subclass = CostsResultSubclass(
            self.costs_result.record,
            self.costs_result.lineage,
        )
        liquidity_subclass = LiquidityResultSubclass(
            self.liquidity_result.record,
            self.liquidity_result.lineage,
        )
        cases = (
            (structure_subclass, self.costs_result, self.liquidity_result),
            (self.structure, costs_subclass, self.liquidity_result),
            (self.structure, self.costs_result, liquidity_subclass),
        )
        for constructor in self._constructors():
            for arguments in cases:
                with self.subTest(constructor=constructor):
                    with self.assertRaises(TypeError):
                        constructor(*arguments)

    def test_intrinsic_reconstruction_rejects_bypassed_and_malformed_wrappers(self):
        malformed_costs = _bypassed_dataclass(
            self.costs_result,
            record=object(),
        )
        malformed_liquidity = _bypassed_dataclass(
            self.liquidity_result,
            record=object(),
        )
        bypassed_cost_record = _bypassed_dataclass(
            self.costs_result.record,
            quoted_mid_premium=self.costs_result.record.quoted_mid_premium + 0.01,
        )
        bypassed_costs = _bypassed_dataclass(
            self.costs_result,
            record=bypassed_cost_record,
        )
        bypassed_liquidity_record = _bypassed_dataclass(
            self.liquidity_result.record,
            quoted_bid_value=self.liquidity_result.record.quoted_bid_value + 0.01,
        )
        bypassed_liquidity = _bypassed_dataclass(
            self.liquidity_result,
            record=bypassed_liquidity_record,
        )

        for constructor in self._constructors():
            with self.subTest(constructor=constructor, wrapper="malformed costs"):
                with self.assertRaises((TypeError, ValueError)):
                    constructor(
                        self.structure,
                        malformed_costs,
                        self.liquidity_result,
                    )
            with self.subTest(constructor=constructor, wrapper="malformed liquidity"):
                with self.assertRaises((TypeError, ValueError)):
                    constructor(
                        self.structure,
                        self.costs_result,
                        malformed_liquidity,
                    )
            with self.subTest(constructor=constructor, wrapper="bypassed costs"):
                with self.assertRaises((TypeError, ValueError)):
                    constructor(
                        self.structure,
                        bypassed_costs,
                        self.liquidity_result,
                    )
            with self.subTest(constructor=constructor, wrapper="bypassed liquidity"):
                with self.assertRaises((TypeError, ValueError)):
                    constructor(
                        self.structure,
                        self.costs_result,
                        bypassed_liquidity,
                    )

    def test_validation_precedence_is_top_level_then_costs_then_liquidity(self):
        malformed_costs = _bypassed_dataclass(
            self.costs_result,
            record=object(),
        )
        malformed_liquidity = _bypassed_dataclass(
            self.liquidity_result,
            record=object(),
        )
        for constructor in self._constructors():
            with self.subTest(constructor=constructor):
                with self.assertRaisesRegex(TypeError, "StructureCosts"):
                    constructor(
                        self.structure,
                        malformed_costs,
                        malformed_liquidity,
                    )

                with self.assertRaisesRegex(TypeError, "StructureCosts"):
                    constructor(
                        self.structure,
                        malformed_costs,
                        self.alternate_mismatched_liquidity_result,
                    )

    def test_structure_correspondence_precedes_date_correspondence(self):
        for constructor in self._constructors():
            with self.subTest(constructor=constructor):
                with self.assertRaisesRegex(
                    ValueError,
                    "structure does not match liquidity_result.record.structure",
                ):
                    constructor(
                        self.structure,
                        self.costs_result,
                        self.alternate_mismatched_liquidity_result,
                    )

    def test_structure_and_shared_observation_date_mismatches_are_rejected(self):
        for constructor in self._constructors():
            with self.subTest(constructor=constructor, mismatch="structure"):
                with self.assertRaisesRegex(
                    ValueError,
                    "structure does not match liquidity_result.record.structure",
                ):
                    constructor(
                        self.structure,
                        self.costs_result,
                        self.mismatched_liquidity_result,
                    )
            with self.subTest(constructor=constructor, mismatch="date"):
                with self.assertRaisesRegex(
                    ValueError,
                    "share as_of_date",
                ):
                    constructor(
                        self.structure,
                        self.costs_result,
                        self.alternate_liquidity_result,
                    )

    def test_no_upstream_transformation_or_evidence_acquisition_is_called(self):
        upstream = (
            (market_data, "select_correction_candidate"),
            (market_data, "assess_market_data_freshness"),
            (market_data, "bind_selected_fresh_market_data"),
            (market_data, "assess_market_data_snapshot_timing"),
            (market_data, "assess_market_data_relationships"),
            (market_data, "select_market_data_relationship_assessment"),
            (transformations, "transform_structure_costs"),
            (transformations, "transform_structure_liquidity"),
        )
        with ExitStack() as stack:
            for owner, name in upstream:
                stack.enter_context(
                    mock.patch.object(
                        owner,
                        name,
                        side_effect=AssertionError("upstream call"),
                    )
                )
            result = direct_entry_verification.verify_direct_entry_research_readiness(
                self.structure,
                self.costs_result,
                self.liquidity_result,
            )
        self.assertIs(result.structure, self.structure)

    def test_repeated_verification_is_deterministic_and_does_not_mutate_inputs(self):
        before = copy.deepcopy(
            (self.structure, self.costs_result, self.liquidity_result)
        )
        first = direct_entry_verification.verify_direct_entry_research_readiness(
            self.structure,
            self.costs_result,
            self.liquidity_result,
        )
        second = direct_entry_verification.verify_direct_entry_research_readiness(
            self.structure,
            self.costs_result,
            self.liquidity_result,
        )

        self.assertEqual(first, second)
        self.assertIs(first.structure, second.structure)
        self.assertIs(first.costs_result, second.costs_result)
        self.assertIs(first.liquidity_result, second.liquidity_result)
        self.assertEqual(
            before,
            (self.structure, self.costs_result, self.liquidity_result),
        )


if __name__ == "__main__":
    unittest.main()
