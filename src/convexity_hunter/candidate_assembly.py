"""Deterministic assembly of reviewed artifacts into a candidate record."""

import datetime
import decimal
import math
from dataclasses import dataclass
from typing import Optional

from . import market_data_transformations as _transformations
from . import risk_assessment as _risk
from .evidence import (
    CandidateState,
    ClassifiedEvidence,
    OptionLeg,
    OptionStructure,
)
from .market_data import (
    CalculationInputReference,
    CalculationLineage,
    CalculationQualityFlag,
    canonicalize_lineage_parameters,
)
from .market_data_transformations import (
    ExpirationPayoffThresholdTransformationResult,
    ScenarioValuationTransformationResult,
    StructureCostsTransformationResult,
    StructureLiquidityTransformationResult,
    TailPricingTransformationResult,
    VolatilityEnvironmentTransformationResult,
)
from .report import CandidateResearchRecord
from .risk_assessment import (
    AffordabilityStatus,
    StructureAffordabilityAssessmentResult,
)


__all__ = (
    "CandidateResearchRecordAssemblyResult",
    "assemble_candidate_research_record",
)


_CALCULATION_TYPE = "candidate_research_record_assembly"
_METHODOLOGY_ID = "reviewed-artifact-candidate-research-record-assembly"
_METHODOLOGY_VERSION = "v0.1"
_PARAMETER_KEYS = {
    "schema_version",
    "output_architecture",
    "caller_inputs",
    "candidate_record",
    "volatility_environment_result",
    "tail_pricing_result",
    "structure_liquidity_result",
    "structure_costs_result",
    "scenario_valuation_result",
    "expiration_payoff_threshold_result",
    "structure_affordability_result",
    "assembly_rules",
}

_ARTIFACT_FIELDS = (
    "volatility_environment_result",
    "tail_pricing_result",
    "structure_liquidity_result",
    "structure_costs_result",
    "scenario_valuation_result",
    "expiration_payoff_threshold_result",
    "structure_affordability_result",
)
_ARTIFACT_TYPES = (
    VolatilityEnvironmentTransformationResult,
    TailPricingTransformationResult,
    StructureLiquidityTransformationResult,
    StructureCostsTransformationResult,
    ScenarioValuationTransformationResult,
    ExpirationPayoffThresholdTransformationResult,
    StructureAffordabilityAssessmentResult,
)

_ASSEMBLY_RULES = {
    "state_completeness": {
        "investigate": {
            "artifact_cardinality": {"minimum": 7, "maximum": 7},
            "incomplete_input_treatment":
                "reject_any_direct_incomplete_input_used",
            "affordability_requirement": ("affordable", "not_affordable"),
            "state_change_prohibited": True,
        },
        "watch": {
            "artifact_cardinality": {"minimum": 0, "maximum": 7},
            "incomplete_input_treatment": "allowed",
            "affordability_requirement": (),
            "state_change_prohibited": True,
        },
        "reject": {
            "artifact_cardinality": {"minimum": 0, "maximum": 7},
            "incomplete_input_treatment": "allowed",
            "affordability_requirement": (),
            "state_change_prohibited": True,
        },
        "data_insufficient": {
            "artifact_cardinality": {"minimum": 0, "maximum": 7},
            "incomplete_input_treatment": "allowed",
            "affordability_requirement": (),
            "state_change_prohibited": True,
        },
    },
    "missing_data": {
        "investigate": {
            "empty_allowed": True,
            "nonempty_required_when": (),
            "assembler_generates_descriptions": False,
            "semantic_correspondence_to_individual_missing_artifacts_required":
                False,
        },
        "watch": {
            "empty_allowed": True,
            "nonempty_required_when": (
                "any_artifact_absent",
                "any_direct_artifact_has_incomplete_input_used",
            ),
            "assembler_generates_descriptions": False,
            "semantic_correspondence_to_individual_missing_artifacts_required":
                False,
        },
        "reject": {
            "empty_allowed": True,
            "nonempty_required_when": (
                "any_artifact_absent",
                "any_direct_artifact_has_incomplete_input_used",
            ),
            "assembler_generates_descriptions": False,
            "semantic_correspondence_to_individual_missing_artifacts_required":
                False,
        },
        "data_insufficient": {
            "empty_allowed": False,
            "nonempty_required_when": ("always",),
            "assembler_generates_descriptions": False,
            "semantic_correspondence_to_individual_missing_artifacts_required":
                False,
        },
    },
    "dependency_closure": {
        "tail_pricing_result": ("volatility_environment_result",),
        "scenario_valuation_result": (
            "volatility_environment_result",
            "tail_pricing_result",
            "structure_costs_result",
        ),
        "expiration_payoff_threshold_result": (
            "structure_costs_result",
        ),
        "structure_affordability_result": ("structure_costs_result",),
    },
    "shared_dependency_identity": {
        "tail_to_volatility": {
            "dependent_field": "tail_pricing_result",
            "supplied_direct_dependency_field":
                "volatility_environment_result",
            "comparison_dimensions": (
                "wrapper_type", "record_or_records", "lineage"
            ),
        },
        "scenario_to_tail": {
            "dependent_field": "scenario_valuation_result",
            "supplied_direct_dependency_field": "tail_pricing_result",
            "comparison_dimensions": (
                "wrapper_type", "record_or_records", "lineage"
            ),
        },
        "scenario_to_costs": {
            "dependent_field": "scenario_valuation_result",
            "supplied_direct_dependency_field": "structure_costs_result",
            "comparison_dimensions": (
                "wrapper_type", "record_or_records", "lineage"
            ),
        },
        "expiration_to_costs": {
            "dependent_field": "expiration_payoff_threshold_result",
            "supplied_direct_dependency_field": "structure_costs_result",
            "comparison_dimensions": (
                "wrapper_type", "record_or_records", "lineage"
            ),
        },
        "affordability_to_costs": {
            "dependent_field": "structure_affordability_result",
            "supplied_direct_dependency_field": "structure_costs_result",
            "comparison_dimensions": (
                "wrapper_type", "record_or_records", "lineage"
            ),
        },
    },
    "candidate_record_mapping": {
        "volatility_environment": "volatility_environment_result.record",
        "tail_pricing_slices": "tail_pricing_result.records",
        "costs": "structure_costs_result.record",
        "liquidity": "structure_liquidity_result.record",
        "scenario_results": "scenario_valuation_result.records",
        "sidecar_only": (
            "expiration_payoff_threshold_result",
            "structure_affordability_result",
        ),
    },
    "normalized_input_union": {
        "zero_artifacts": (),
        "deduplication": ("record_id", "normalized_at", "source_ids"),
        "conflicting_overlap": (
            "reject_same_record_id_with_different_normalized_at",
            "reject_same_record_id_with_different_source_ids",
        ),
        "ordering": "record_id",
        "caller_values": (
            "candidate_id", "state", "state_rationale", "as_of_date",
            "hypothesis", "structure", "evidence",
            "falsification_conditions", "missing_data",
            "false_positive_reasons", "ai_interpretation",
            "human_review_questions",
        ),
    },
    "quality_flag_derivation": {
        "upstream_union": _ARTIFACT_FIELDS,
        "artifact_absence": "incomplete_input_used",
        "upstream_incomplete": "included_by_upstream_union",
        "ordering": tuple(flag.value for flag in CalculationQualityFlag),
        "non_causes": (
            "candidate_id", "state", "state_rationale", "as_of_date",
            "hypothesis", "structure", "evidence",
            "falsification_conditions", "missing_data",
            "false_positive_reasons", "ai_interpretation",
            "human_review_questions",
        ),
    },
    "calculation_id_closure": {
        "direct_dependencies": {
            "fields": _ARTIFACT_FIELDS,
            "constraint": "pairwise_distinct_and_disjoint_from_assembly",
        },
        "nested_dependencies": {
            "roots": _ARTIFACT_FIELDS,
            "traversal": "recursive_verified_dependency_disclosures",
            "collection_order":
                "first_occurrence_depth_first_by_direct_field_order",
            "constraint":
                "disjoint_from_assembly_and_normalized_record_ids",
        },
        "normalized_inputs": {
            "identifier": "record_id",
            "constraint": "disjoint_from_every_calculation_id",
        },
        "shared_reuse": {
            "allowed": True,
            "constraint":
                "same_calculation_id_only_for_byte_identical_complete_calculation",
        },
    },
    "chronology": {
        "direct_dependencies": {
            "left": "assembly.calculated_at",
            "operator": ">=",
            "right": "each_present_direct_dependency.lineage.calculated_at",
        },
        "nested_dependencies": {
            "left": "assembly.calculated_at",
            "operator": ">=",
            "right":
                "each_recursive_verified_dependency.lineage.calculated_at",
        },
        "normalized_inputs": {
            "left": "assembly.calculated_at",
            "operator": ">=",
            "right": "each_normalized_input.normalized_at",
        },
        "zero_artifacts": {"comparison_count": 0},
    },
    "prohibited_behavior": (
        "invoke_upstream_producers", "access_providers", "invoke_llm",
        "perform_screening", "invoke_scanner", "invoke_renderer",
        "use_implicit_clock", "generate_calculation_id", "generate_prose",
        "generate_state", "generate_missing_data_descriptions",
        "generate_screening_reasons", "synthesize_normalized_inputs",
        "introduce_generic_artifact_registry_or_framework",
    ),
}


def _float_repr(value: float) -> str:
    if type(value) is not float or not math.isfinite(value):
        raise TypeError("public float must have exact finite float type")
    return repr(value)


def _option_leg(value: OptionLeg) -> dict:
    return {
        "underlying": value.underlying,
        "option_type": value.option_type,
        "strike_float_repr": _float_repr(value.strike),
        "expiration": value.expiration,
        "quantity": value.quantity,
        "contract_multiplier": value.contract_multiplier,
    }


def _structure(value: OptionStructure) -> dict:
    return {
        "structure_type": value.structure_type,
        "underlying": value.underlying,
        "assumed_portfolio_value_repr": _float_repr(
            value.assumed_portfolio_value
        ),
        "expected_holding_days": value.expected_holding_days,
        "legs": tuple(_option_leg(item) for item in value.legs),
    }


def _evidence(value: ClassifiedEvidence) -> dict:
    return {
        "evidence_id": value.evidence_id,
        "kind": value.kind.value,
        "impact": value.impact.value,
        "statement": value.statement,
        "source": value.source,
        "methodology": value.methodology,
    }


def _volatility(value: object) -> dict:
    return {
        "underlying": value.underlying,
        "as_of_date": value.as_of_date,
        "reference_tenor_days": value.reference_tenor_days,
        "iv_percentile_float_repr": _float_repr(value.iv_percentile),
        "iv_history_lookback_observations":
            value.iv_history_lookback_observations,
        "historical_median_atm_iv_float_repr": _float_repr(
            value.historical_median_atm_iv
        ),
        "matched_realized_volatility_float_repr": _float_repr(
            value.matched_realized_volatility
        ),
        "matched_realized_window_days": value.matched_realized_window_days,
        "term_structure": tuple({
            "tenor_days": item.tenor_days,
            "atm_iv_float_repr": _float_repr(item.atm_iv),
        } for item in value.term_structure),
    }


def _tail(value: object) -> dict:
    return {
        "underlying": value.underlying,
        "as_of_date": value.as_of_date,
        "expiration": value.expiration,
        "atm_iv_float_repr": _float_repr(value.atm_iv),
        "put_25_delta_iv_float_repr": _float_repr(value.put_25_delta_iv),
        "call_25_delta_iv_float_repr": _float_repr(value.call_25_delta_iv),
        "put_10_delta_iv_float_repr": _float_repr(value.put_10_delta_iv),
        "call_10_delta_iv_float_repr": _float_repr(value.call_10_delta_iv),
        "skew_percentile_float_repr": _float_repr(value.skew_percentile),
        "skew_history_lookback_observations":
            value.skew_history_lookback_observations,
        "delta_methodology": value.delta_methodology,
    }


def _liquidity(value: object) -> dict:
    return {
        "structure": _structure(value.structure),
        "as_of_date": value.as_of_date,
        "quoted_bid_value_float_repr": _float_repr(value.quoted_bid_value),
        "quoted_ask_value_float_repr": _float_repr(value.quoted_ask_value),
        "minimum_leg_open_interest": value.minimum_leg_open_interest,
        "minimum_leg_daily_volume": value.minimum_leg_daily_volume,
        "quote_methodology": value.quote_methodology,
    }


def _costs(value: object) -> dict:
    return {
        "structure": _structure(value.structure),
        "as_of_date": value.as_of_date,
        "quoted_mid_premium_float_repr": _float_repr(
            value.quoted_mid_premium
        ),
        "estimated_spread_cost_float_repr": _float_repr(
            value.estimated_spread_cost
        ),
        "commissions_and_fees_float_repr": _float_repr(
            value.commissions_and_fees
        ),
        "theta_per_day_float_repr": _float_repr(value.theta_per_day),
        "gamma_float_repr": _float_repr(value.gamma),
        "underlying_price_float_repr": _float_repr(value.underlying_price),
        "greeks_methodology": value.greeks_methodology,
        "repeated_bet_count": value.repeated_bet_count,
    }


def _scenario(value: object) -> dict:
    return {
        "underlying_move_float_repr": _float_repr(value.underlying_move),
        "iv_change_float_repr": _float_repr(value.iv_change),
        "valuation_time": value.valuation_time,
        "days_forward": value.days_forward,
    }


def _scenario_result(value: object) -> dict:
    return {
        "structure": _structure(value.structure),
        "as_of_date": value.as_of_date,
        "scenario": _scenario(value.scenario),
        "valuation_date": value.valuation_date,
        "base_underlying_price_float_repr": _float_repr(
            value.base_underlying_price
        ),
        "leg_volatility_inputs": tuple({
            "leg": _option_leg(item.leg),
            "base_iv_float_repr": _float_repr(item.base_iv),
        } for item in value.leg_volatility_inputs),
        "estimated_position_value_float_repr": _float_repr(
            value.estimated_position_value
        ),
        "entry_cost_basis_float_repr": _float_repr(value.entry_cost_basis),
        "estimated_exit_cost_float_repr": _float_repr(
            value.estimated_exit_cost
        ),
        "pricing_methodology": value.pricing_methodology,
    }


def _rational(value: object) -> object:
    if value is None:
        return None
    return {"numerator": value.numerator, "denominator": value.denominator}


def _expiration(value: object) -> dict:
    return {
        "structure": _structure(value.structure),
        "as_of_date": value.as_of_date,
        "base_underlying_price": value.base_underlying_price,
        "total_entry_cost": value.total_entry_cost,
        "thresholds": tuple({
            "position_value_multiple": item.position_value_multiple,
            "side": item.side.value,
            "status": item.status.value,
            "target_position_value": _rational(item.target_position_value),
            "threshold_underlying_price": _rational(
                item.threshold_underlying_price
            ),
            "absolute_move_from_base": _rational(
                item.absolute_move_from_base
            ),
            "relative_move_from_base": _rational(
                item.relative_move_from_base
            ),
        } for item in value.thresholds),
    }


def _portfolio(value: object) -> object:
    if value is None:
        return None
    return {
        "amount": value.amount,
        "as_of_date": value.as_of_date,
        "methodology": value.methodology,
    }


def _affordability(value: object) -> dict:
    assumptions = value.assumptions
    return {
        "structure": _structure(value.structure),
        "as_of_date": value.as_of_date,
        "assumptions": {
            "portfolio_value": _portfolio(assumptions.portfolio_value),
            "maximum_single_structure_loss_fraction": _rational(
                assumptions.maximum_single_structure_loss_fraction
            ),
            "maximum_repeated_loss_fraction": _rational(
                assumptions.maximum_repeated_loss_fraction
            ),
            "risk_budget_methodology": assumptions.risk_budget_methodology,
        },
        "single_position_maximum_loss": value.single_position_maximum_loss,
        "repeated_bet_count": value.repeated_bet_count,
        "repeated_aggregate_maximum_loss":
            value.repeated_aggregate_maximum_loss,
        "single_loss_fraction": _rational(value.single_loss_fraction),
        "repeated_loss_fraction": _rational(value.repeated_loss_fraction),
        "status": value.status.value,
        "reason_codes": tuple(item.value for item in value.reason_codes),
    }


def _lineage(value: CalculationLineage) -> dict:
    return {
        "calculation_id": value.calculation_id,
        "calculation_type": value.calculation_type,
        "methodology_id": value.methodology_id,
        "methodology_version": value.methodology_version,
        "calculated_at": value.calculated_at,
        "inputs": tuple({
            "record_id": item.record_id,
            "normalized_at": item.normalized_at,
            "source_ids": item.source_ids,
        } for item in value.inputs),
        "parameters_json": value.parameters_json,
        "quality_flags": tuple(item.value for item in value.quality_flags),
    }


def _wrapper(value: object, record_builder: object) -> object:
    if value is None:
        return None
    plural = hasattr(value, "records")
    records = value.records if plural else value.record
    return {
        "wrapper_type": type(value).__name__,
        "records" if plural else "record": (
            tuple(record_builder(item) for item in records)
            if plural else record_builder(records)
        ),
        "lineage": _lineage(value.lineage),
    }


def _caller_inputs(record: CandidateResearchRecord) -> dict:
    return {
        "candidate_id": record.candidate_id,
        "state": record.state.value,
        "state_rationale": record.state_rationale,
        "as_of_date": record.as_of_date,
        "hypothesis": record.hypothesis,
        "structure": _structure(record.structure),
        "evidence": tuple(_evidence(item) for item in record.evidence),
        "falsification_conditions": record.falsification_conditions,
        "missing_data": record.missing_data,
        "false_positive_reasons": record.false_positive_reasons,
        "ai_interpretation": record.ai_interpretation,
        "human_review_questions": record.human_review_questions,
    }


def _candidate_record(record: CandidateResearchRecord) -> dict:
    result = _caller_inputs(record)
    result.update({
        "volatility_environment": (
            None if record.volatility_environment is None
            else _volatility(record.volatility_environment)
        ),
        "tail_pricing_slices": tuple(
            _tail(item) for item in record.tail_pricing_slices
        ),
        "costs": None if record.costs is None else _costs(record.costs),
        "liquidity": (
            None if record.liquidity is None else _liquidity(record.liquidity)
        ),
        "scenario_results": tuple(
            _scenario_result(item) for item in record.scenario_results
        ),
    })
    return result


def _parameters(result: object) -> dict:
    return {
        "schema_version": "v0.1",
        "output_architecture": {
            "result_type": "CandidateResearchRecordAssemblyResult",
            "candidate_record_type": "CandidateResearchRecord",
            "artifact_representation":
                "seven_explicit_optional_reviewed_wrapper_fields",
            "lineage_type": "CalculationLineage",
        },
        "caller_inputs": _caller_inputs(result.record),
        "candidate_record": _candidate_record(result.record),
        "volatility_environment_result": _wrapper(
            result.volatility_environment_result, _volatility
        ),
        "tail_pricing_result": _wrapper(result.tail_pricing_result, _tail),
        "structure_liquidity_result": _wrapper(
            result.structure_liquidity_result, _liquidity
        ),
        "structure_costs_result": _wrapper(
            result.structure_costs_result, _costs
        ),
        "scenario_valuation_result": _wrapper(
            result.scenario_valuation_result, _scenario_result
        ),
        "expiration_payoff_threshold_result": _wrapper(
            result.expiration_payoff_threshold_result, _expiration
        ),
        "structure_affordability_result": _wrapper(
            result.structure_affordability_result, _affordability
        ),
        "assembly_rules": _ASSEMBLY_RULES,
    }


def _exact_tree(actual: object, expected: object, path: str) -> None:
    if type(actual) is not type(expected):
        raise TypeError(f"{path} has the wrong exact type")
    if type(expected) is dict:
        if set(actual) != set(expected):
            raise ValueError(f"{path} has the wrong exact key schema")
        for key in expected:
            _exact_tree(actual[key], expected[key], f"{path}.{key}")
    elif type(expected) is tuple:
        if len(actual) != len(expected):
            raise ValueError(f"{path} has the wrong cardinality")
        for index, (left, right) in enumerate(zip(actual, expected)):
            _exact_tree(left, right, f"{path}[{index}]")
    elif actual != expected:
        raise ValueError(f"{path} has the wrong frozen value")


def _union_inputs(artifacts: tuple) -> tuple:
    references = {}
    for artifact in artifacts:
        if artifact is None:
            continue
        for reference in artifact.lineage.inputs:
            existing = references.get(reference.record_id)
            if existing is not None and existing != reference:
                if existing.normalized_at != reference.normalized_at:
                    raise ValueError("normalized input time overlap conflicts")
                raise ValueError("normalized input source overlap conflicts")
            references[reference.record_id] = reference
    return tuple(references[key] for key in sorted(references))


def _quality_flags(artifacts: tuple) -> tuple:
    selected = {
        flag
        for artifact in artifacts if artifact is not None
        for flag in artifact.lineage.quality_flags
    }
    if any(artifact is None for artifact in artifacts):
        selected.add(CalculationQualityFlag.INCOMPLETE_INPUT_USED)
    return tuple(flag for flag in CalculationQualityFlag if flag in selected)


def _construct_record(result: object) -> CandidateResearchRecord:
    record = result.record
    return CandidateResearchRecord(
        candidate_id=record.candidate_id,
        state=record.state,
        state_rationale=record.state_rationale,
        as_of_date=record.as_of_date,
        hypothesis=record.hypothesis,
        structure=record.structure,
        volatility_environment=(
            None if result.volatility_environment_result is None
            else result.volatility_environment_result.record
        ),
        tail_pricing_slices=(
            () if result.tail_pricing_result is None
            else result.tail_pricing_result.records
        ),
        costs=(
            None if result.structure_costs_result is None
            else result.structure_costs_result.record
        ),
        liquidity=(
            None if result.structure_liquidity_result is None
            else result.structure_liquidity_result.record
        ),
        scenario_results=(
            () if result.scenario_valuation_result is None
            else result.scenario_valuation_result.records
        ),
        evidence=record.evidence,
        falsification_conditions=record.falsification_conditions,
        missing_data=record.missing_data,
        false_positive_reasons=record.false_positive_reasons,
        ai_interpretation=record.ai_interpretation,
        human_review_questions=record.human_review_questions,
    )


def _intrinsic_artifacts(result: object) -> tuple:
    artifacts = tuple(getattr(result, name) for name in _ARTIFACT_FIELDS)
    verified = []
    nested = []
    reconstructed = {}
    for name, artifact, expected_type in zip(
        _ARTIFACT_FIELDS, artifacts, _ARTIFACT_TYPES
    ):
        if artifact is None:
            verified.append(None)
            continue
        if hasattr(artifact, "records"):
            current = expected_type(artifact.records, artifact.lineage)
        else:
            current = expected_type(artifact.record, artifact.lineage)
        verified.append(current)
        if name == "volatility_environment_result":
            _record, _lineage_value, decoded, _tenors = (
                _transformations._verify_volatility_environment_result(
                    current.record, current.lineage
                )
            )
            realized = decoded["realized_volatility_dependency"]
            realized_record, realized_lineage, _inputs, _flags = (
                _transformations._reconstruct_realized_dependency(
                    realized,
                    current.record.underlying,
                    current.lineage.calculation_id,
                    current.lineage.calculated_at,
                )
            )
            nested.append((realized_record, realized_lineage))
        elif name == "tail_pricing_result":
            _decoded, _observations, dependency = (
                _transformations._verify_tail_pricing_result(
                    current.records, current.lineage
                )
            )
            reconstructed["tail_volatility"] = dependency
            nested.append(dependency)
        elif name == "scenario_valuation_result":
            costs, tail, pricing, volatility = (
                _transformations._reconstruct_scenario_valuation_dependencies(
                    current.records, current.lineage
                )
            )
            reconstructed["scenario_costs"] = costs
            reconstructed["scenario_tail"] = tail
            reconstructed["scenario_volatility"] = volatility
            nested.extend((costs, tail, pricing, volatility))
        elif name == "expiration_payoff_threshold_result":
            decoded = _transformations._decode_expiration_threshold_parameters(
                current.lineage.parameters_json
            )
            costs = (
                _transformations._expiration_threshold_dependency_from_disclosure(
                    current.record,
                    current.lineage,
                    decoded["structure_costs_dependency"],
                )
            )
            reconstructed["expiration_costs"] = costs
            nested.append(costs)
        elif name == "structure_affordability_result":
            decoded = _risk._decode_parameters(current.lineage.parameters_json)
            costs = _risk._dependency_from_disclosure(
                current.record,
                current.lineage,
                decoded["structure_costs_dependency"],
            )
            reconstructed["affordability_costs"] = costs
            nested.append(costs)
    return tuple(verified), tuple(nested), reconstructed


def _require_outer_artifact_types(values: tuple) -> None:
    for name, value, expected_type in zip(
        _ARTIFACT_FIELDS, values, _ARTIFACT_TYPES
    ):
        if value is not None and type(value) is not expected_type:
            raise TypeError(f"{name} has the wrong exact wrapper type")


def _require_initialized_outer_artifacts(values: tuple) -> None:
    tuple_record_types = (
        TailPricingTransformationResult,
        ScenarioValuationTransformationResult,
    )
    for name, value, expected_type in zip(
        _ARTIFACT_FIELDS, values, _ARTIFACT_TYPES
    ):
        if value is None:
            continue
        required_fields = (
            ("records", "lineage")
            if expected_type in tuple_record_types
            else ("record", "lineage")
        )
        for field_name in required_fields:
            try:
                object.__getattribute__(value, field_name)
            except AttributeError as error:
                raise ValueError(
                    f"{name} lacks required field {field_name}"
                ) from error


def _verify_dependencies(artifacts: tuple, reconstructed: dict) -> None:
    by_name = dict(zip(_ARTIFACT_FIELDS, artifacts))
    for dependent, dependencies in _ASSEMBLY_RULES[
        "dependency_closure"
    ].items():
        if by_name[dependent] is not None and any(
            by_name[name] is None for name in dependencies
        ):
            raise ValueError(f"{dependent} is missing a direct dependency")
    comparisons = (
        ("tail_pricing_result", "tail_volatility",
         "volatility_environment_result"),
        ("scenario_valuation_result", "scenario_tail",
         "tail_pricing_result"),
        ("scenario_valuation_result", "scenario_costs",
         "structure_costs_result"),
        ("expiration_payoff_threshold_result", "expiration_costs",
         "structure_costs_result"),
        ("structure_affordability_result", "affordability_costs",
         "structure_costs_result"),
    )
    for dependent, key, supplied in comparisons:
        if by_name[dependent] is not None and reconstructed[key] != by_name[supplied]:
            raise ValueError(f"{dependent} shared dependency is not exact")


def _verify_state(result: object, artifacts: tuple) -> None:
    state = result.record.state
    if type(state) is not CandidateState:
        raise TypeError("record state must have exact type CandidateState")
    incomplete = any(
        artifact is not None
        and CalculationQualityFlag.INCOMPLETE_INPUT_USED
        in artifact.lineage.quality_flags
        for artifact in artifacts
    )
    absent = any(artifact is None for artifact in artifacts)
    if state is CandidateState.INVESTIGATE:
        if absent:
            raise ValueError("investigate requires all seven artifacts")
        if incomplete:
            raise ValueError("investigate rejects incomplete direct artifacts")
        status = result.structure_affordability_result.record.status
        if status not in {
            AffordabilityStatus.AFFORDABLE,
            AffordabilityStatus.NOT_AFFORDABLE,
        }:
            raise ValueError("investigate requires conclusive affordability")
    elif state in {CandidateState.WATCH, CandidateState.REJECT}:
        if (absent or incomplete) and not result.record.missing_data:
            raise ValueError("partial candidate requires nonempty missing_data")
    elif state is CandidateState.DATA_INSUFFICIENT:
        if not result.record.missing_data:
            raise ValueError("data-insufficient requires nonempty missing_data")


def _verify_cross_artifacts(result: object, artifacts: tuple) -> None:
    record = _construct_record(result)
    if record != result.record:
        raise ValueError("sidecar record does not correspond to artifacts")
    costs = result.structure_costs_result
    for dependent in (
        result.expiration_payoff_threshold_result,
        result.structure_affordability_result,
    ):
        if dependent is not None and (
            dependent.record.structure != result.record.structure
            or dependent.record.as_of_date != result.record.as_of_date
        ):
            raise ValueError("sidecar-only artifact structure or date differs")
    affordability = result.structure_affordability_result
    if affordability is not None:
        portfolio = affordability.record.assumptions.portfolio_value
        if portfolio is not None and portfolio.amount != decimal.Decimal(
            str(result.record.structure.assumed_portfolio_value)
        ):
            raise ValueError("affordability portfolio assumption differs")


def _calculation_metadata(nested: tuple) -> tuple:
    result = []
    for value in nested:
        lineage = value.lineage if hasattr(value, "lineage") else value[1]
        result.append((value, lineage))
    return tuple(result)


def _verify_id_and_time(
    result: object, artifacts: tuple, nested: tuple, inputs: tuple
) -> None:
    direct_lineages = tuple(
        artifact.lineage for artifact in artifacts if artifact is not None
    )
    direct_ids = tuple(item.calculation_id for item in direct_lineages)
    if len(set(direct_ids)) != len(direct_ids):
        raise ValueError("direct calculation IDs must be pairwise distinct")
    calculations = {
        artifact.lineage.calculation_id: artifact
        for artifact in artifacts if artifact is not None
    }
    for value, lineage in _calculation_metadata(nested):
        existing = calculations.get(lineage.calculation_id)
        if existing is not None and existing != value:
            raise ValueError("nested calculation ID is reused inconsistently")
        calculations[lineage.calculation_id] = value
    all_lineages = direct_lineages + tuple(
        lineage for _value, lineage in _calculation_metadata(nested)
    )
    all_ids = set(direct_ids) | set(calculations)
    if result.lineage.calculation_id in all_ids:
        raise ValueError("assembly calculation ID collides with dependency")
    input_ids = {item.record_id for item in inputs}
    if all_ids & input_ids or result.lineage.calculation_id in input_ids:
        raise ValueError("calculation ID collides with normalized input")
    if any(result.lineage.calculated_at < item.calculated_at for item in all_lineages):
        raise ValueError("assembly calculation precedes a dependency")
    if any(result.lineage.calculated_at < item.normalized_at for item in inputs):
        raise ValueError("assembly calculation precedes a normalized input")


def _verify_candidate_research_record_assembly(result: object) -> None:
    if type(result.record) is not CandidateResearchRecord:
        raise TypeError("record must have exact type CandidateResearchRecord")
    if type(result.lineage) is not CalculationLineage:
        raise TypeError("lineage must have exact type CalculationLineage")
    lineage = result.lineage
    for name in (
        "calculation_id", "calculation_type", "methodology_id",
        "methodology_version", "parameters_json",
    ):
        if type(getattr(lineage, name)) is not str:
            raise TypeError(f"lineage {name} must have exact type str")
    if type(lineage.calculated_at) is not datetime.datetime:
        raise TypeError("lineage calculated_at must have exact type datetime")
    if type(lineage.inputs) is not tuple:
        raise TypeError("lineage inputs must have exact type tuple")
    if type(lineage.quality_flags) is not tuple:
        raise TypeError("lineage quality_flags must have exact type tuple")
    verified_lineage = CalculationLineage(
        lineage.calculation_id,
        lineage.calculation_type,
        lineage.methodology_id,
        lineage.methodology_version,
        lineage.calculated_at,
        lineage.inputs,
        lineage.parameters_json,
        lineage.quality_flags,
    )
    if verified_lineage != lineage:
        raise ValueError("assembly lineage is not in canonical constructor state")
    artifact_values = tuple(
        getattr(result, name) for name in _ARTIFACT_FIELDS
    )
    _require_outer_artifact_types(artifact_values)
    _require_initialized_outer_artifacts(artifact_values)
    artifacts, nested, reconstructed = _intrinsic_artifacts(result)
    _verify_dependencies(artifacts, reconstructed)
    _verify_cross_artifacts(result, artifacts)
    _verify_state(result, artifacts)
    expected_parameters = _parameters(result)
    decoded = _transformations._decode_strict_tagged_parameters(
        result.lineage.parameters_json, _PARAMETER_KEYS, "6B assembly"
    )
    _exact_tree(decoded, expected_parameters, "parameters")
    inputs = _union_inputs(artifacts)
    flags = _quality_flags(artifacts)
    _verify_id_and_time(result, artifacts, nested, inputs)
    expected_lineage = CalculationLineage(
        calculation_id=result.lineage.calculation_id,
        calculation_type=_CALCULATION_TYPE,
        methodology_id=_METHODOLOGY_ID,
        methodology_version=_METHODOLOGY_VERSION,
        calculated_at=result.lineage.calculated_at,
        inputs=inputs,
        parameters_json=canonicalize_lineage_parameters(expected_parameters),
        quality_flags=flags,
    )
    if result.lineage != expected_lineage:
        raise ValueError("assembly lineage does not correspond to the sidecar")


@dataclass(frozen=True)
class CandidateResearchRecordAssemblyResult:
    record: CandidateResearchRecord
    volatility_environment_result: Optional[
        VolatilityEnvironmentTransformationResult
    ]
    tail_pricing_result: Optional[TailPricingTransformationResult]
    structure_liquidity_result: Optional[
        StructureLiquidityTransformationResult
    ]
    structure_costs_result: Optional[StructureCostsTransformationResult]
    scenario_valuation_result: Optional[
        ScenarioValuationTransformationResult
    ]
    expiration_payoff_threshold_result: Optional[
        ExpirationPayoffThresholdTransformationResult
    ]
    structure_affordability_result: Optional[
        StructureAffordabilityAssessmentResult
    ]
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        with decimal.localcontext():
            _verify_candidate_research_record_assembly(self)


def assemble_candidate_research_record(
    calculation_id: object,
    candidate_id: object,
    state: object,
    state_rationale: object,
    as_of_date: object,
    hypothesis: object,
    structure: object,
    volatility_environment_result: object,
    tail_pricing_result: object,
    structure_liquidity_result: object,
    structure_costs_result: object,
    scenario_valuation_result: object,
    expiration_payoff_threshold_result: object,
    structure_affordability_result: object,
    evidence: object,
    falsification_conditions: object,
    missing_data: object,
    false_positive_reasons: object,
    ai_interpretation: object,
    human_review_questions: object,
    calculated_at: object,
) -> CandidateResearchRecordAssemblyResult:
    artifact_values = (
        volatility_environment_result,
        tail_pricing_result,
        structure_liquidity_result,
        structure_costs_result,
        scenario_valuation_result,
        expiration_payoff_threshold_result,
        structure_affordability_result,
    )
    _require_outer_artifact_types(artifact_values)
    _require_initialized_outer_artifacts(artifact_values)
    record = CandidateResearchRecord(
        candidate_id=candidate_id,
        state=state,
        state_rationale=state_rationale,
        as_of_date=as_of_date,
        hypothesis=hypothesis,
        structure=structure,
        volatility_environment=(
            None if volatility_environment_result is None
            else volatility_environment_result.record
        ),
        tail_pricing_slices=(
            () if tail_pricing_result is None else tail_pricing_result.records
        ),
        costs=(
            None if structure_costs_result is None
            else structure_costs_result.record
        ),
        liquidity=(
            None if structure_liquidity_result is None
            else structure_liquidity_result.record
        ),
        scenario_results=(
            () if scenario_valuation_result is None
            else scenario_valuation_result.records
        ),
        evidence=evidence,
        falsification_conditions=falsification_conditions,
        missing_data=missing_data,
        false_positive_reasons=false_positive_reasons,
        ai_interpretation=ai_interpretation,
        human_review_questions=human_review_questions,
    )
    shell = object.__new__(CandidateResearchRecordAssemblyResult)
    values = (
        record,
        volatility_environment_result,
        tail_pricing_result,
        structure_liquidity_result,
        structure_costs_result,
        scenario_valuation_result,
        expiration_payoff_threshold_result,
        structure_affordability_result,
    )
    for name, value in zip(
        ("record",) + _ARTIFACT_FIELDS, values
    ):
        object.__setattr__(shell, name, value)
    artifacts, nested, reconstructed = _intrinsic_artifacts(shell)
    _verify_dependencies(artifacts, reconstructed)
    _verify_cross_artifacts(shell, artifacts)
    _verify_state(shell, artifacts)
    inputs = _union_inputs(artifacts)
    flags = _quality_flags(artifacts)
    parameters_json = canonicalize_lineage_parameters(_parameters(shell))
    lineage = CalculationLineage(
        calculation_id=calculation_id,
        calculation_type=_CALCULATION_TYPE,
        methodology_id=_METHODOLOGY_ID,
        methodology_version=_METHODOLOGY_VERSION,
        calculated_at=calculated_at,
        inputs=inputs,
        parameters_json=parameters_json,
        quality_flags=flags,
    )
    return CandidateResearchRecordAssemblyResult(
        record,
        volatility_environment_result,
        tail_pricing_result,
        structure_liquidity_result,
        structure_costs_result,
        scenario_valuation_result,
        expiration_payoff_threshold_result,
        structure_affordability_result,
        lineage,
    )
