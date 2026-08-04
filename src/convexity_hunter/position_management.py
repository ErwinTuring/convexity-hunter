"""Prospective, declaration-only position-management plans."""

import datetime
import decimal
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Tuple, Union

from . import candidate_assembly
from . import risk_assessment
from .candidate_assembly import CandidateResearchRecordAssemblyResult
from .evidence import CandidateState, OptionStructure
from .market_data import (
    CalculationInputReference,
    CalculationLineage,
    CalculationQualityFlag,
    canonicalize_lineage_parameters,
)
from .market_data_transformations import ExactRational


__all__ = (
    "PositionManagementScope",
    "PositionManagementCategory",
    "PositionManagementAuthority",
    "PositionManagementMetric",
    "PositionManagementComparison",
    "PositionManagementQualitativeTrigger",
    "QuantitativePositionManagementCondition",
    "QualitativePositionManagementCondition",
    "PositionManagementPlan",
    "PositionManagementPlanResult",
    "create_position_management_plan",
)


class PositionManagementScope(str, Enum):
    PROSPECTIVE_RESEARCH_GUIDANCE = "prospective_research_guidance"


class PositionManagementCategory(str, Enum):
    MONETIZATION = "monetization"
    REASSESSMENT = "reassessment"
    EXIT = "exit"


class PositionManagementAuthority(str, Enum):
    REVIEWED_ARTIFACT = "reviewed_artifact"
    CALLER = "caller"
    HUMAN_ANALYST = "human_analyst"


class PositionManagementMetric(str, Enum):
    NET_LIQUIDATION_VALUE_MULTIPLE = "net_liquidation_value_multiple"
    REMAINING_DTE = "remaining_dte"
    BID_ASK_SPREAD_FRACTION = "bid_ask_spread_fraction"
    ATM_IV = "atm_iv"
    SKEW_PERCENTILE = "skew_percentile"
    SINGLE_LOSS_FRACTION = "single_loss_fraction"
    REPEATED_LOSS_FRACTION = "repeated_loss_fraction"


class PositionManagementComparison(str, Enum):
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"


class PositionManagementQualitativeTrigger(str, Enum):
    EVENT_BECOMES_PUBLIC = "event_becomes_public"
    UNDERPRICING_EVIDENCE_DISAPPEARS = "underpricing_evidence_disappears"
    EVENT_WINDOW_SHIFTS = "event_window_shifts"
    EVIDENCE_STALE_OR_MISSING = "evidence_stale_or_missing"
    CONTRACT_ADJUSTED = "contract_adjusted"
    IMPACT_PATH_MATERIALLY_CHANGES = "impact_path_materially_changes"
    EVENT_WINDOW_EXPIRES_WITHOUT_HYPOTHESIZED_CHANGE = (
        "event_window_expires_without_hypothesized_change"
    )
    EVENT_CANCELLED = "event_cancelled"
    DEFINITIVE_CONTRARY_RESOLUTION = "definitive_contrary_resolution"
    EXEMPTION_CONFIRMED = "exemption_confirmed"
    IMPACT_PATH_INVALIDATED = "impact_path_invalidated"
    REVISED_EVENT_WINDOW_NOT_COVERED = "revised_event_window_not_covered"
    DATA_LOSS_PREVENTS_RESPONSIBLE_EVALUATION = (
        "data_loss_prevents_responsible_evaluation"
    )


_CATEGORY_ORDER = (
    PositionManagementCategory.MONETIZATION,
    PositionManagementCategory.REASSESSMENT,
    PositionManagementCategory.EXIT,
)
_CATEGORY_INDEX = {value: index for index, value in enumerate(_CATEGORY_ORDER)}
_QUALITATIVE_CATEGORY = {
    PositionManagementQualitativeTrigger.EVENT_BECOMES_PUBLIC:
        PositionManagementCategory.MONETIZATION,
    PositionManagementQualitativeTrigger.UNDERPRICING_EVIDENCE_DISAPPEARS:
        PositionManagementCategory.MONETIZATION,
    PositionManagementQualitativeTrigger.EVENT_WINDOW_SHIFTS:
        PositionManagementCategory.REASSESSMENT,
    PositionManagementQualitativeTrigger.EVIDENCE_STALE_OR_MISSING:
        PositionManagementCategory.REASSESSMENT,
    PositionManagementQualitativeTrigger.CONTRACT_ADJUSTED:
        PositionManagementCategory.REASSESSMENT,
    PositionManagementQualitativeTrigger.IMPACT_PATH_MATERIALLY_CHANGES:
        PositionManagementCategory.REASSESSMENT,
    PositionManagementQualitativeTrigger.EVENT_WINDOW_EXPIRES_WITHOUT_HYPOTHESIZED_CHANGE:
        PositionManagementCategory.EXIT,
    PositionManagementQualitativeTrigger.EVENT_CANCELLED:
        PositionManagementCategory.EXIT,
    PositionManagementQualitativeTrigger.DEFINITIVE_CONTRARY_RESOLUTION:
        PositionManagementCategory.EXIT,
    PositionManagementQualitativeTrigger.EXEMPTION_CONFIRMED:
        PositionManagementCategory.EXIT,
    PositionManagementQualitativeTrigger.IMPACT_PATH_INVALIDATED:
        PositionManagementCategory.EXIT,
    PositionManagementQualitativeTrigger.REVISED_EVENT_WINDOW_NOT_COVERED:
        PositionManagementCategory.EXIT,
    PositionManagementQualitativeTrigger.DATA_LOSS_PREVENTS_RESPONSIBLE_EVALUATION:
        PositionManagementCategory.EXIT,
}
_QUANTITATIVE_ALLOWED = {
    PositionManagementMetric.NET_LIQUIDATION_VALUE_MULTIPLE: (
        (PositionManagementCategory.MONETIZATION,),
        (PositionManagementComparison.GREATER_THAN_OR_EQUAL,),
        (PositionManagementAuthority.CALLER,
         PositionManagementAuthority.HUMAN_ANALYST),
    ),
    PositionManagementMetric.REMAINING_DTE: (
        (PositionManagementCategory.REASSESSMENT,),
        (PositionManagementComparison.LESS_THAN_OR_EQUAL,),
        (PositionManagementAuthority.CALLER,
         PositionManagementAuthority.HUMAN_ANALYST),
    ),
    PositionManagementMetric.BID_ASK_SPREAD_FRACTION: (
        (PositionManagementCategory.REASSESSMENT,
         PositionManagementCategory.EXIT),
        (PositionManagementComparison.GREATER_THAN_OR_EQUAL,),
        (PositionManagementAuthority.CALLER,
         PositionManagementAuthority.HUMAN_ANALYST),
    ),
    PositionManagementMetric.ATM_IV: (
        (PositionManagementCategory.MONETIZATION,
         PositionManagementCategory.REASSESSMENT),
        (PositionManagementComparison.GREATER_THAN_OR_EQUAL,
         PositionManagementComparison.LESS_THAN_OR_EQUAL),
        (PositionManagementAuthority.CALLER,
         PositionManagementAuthority.HUMAN_ANALYST),
    ),
    PositionManagementMetric.SKEW_PERCENTILE: (
        (PositionManagementCategory.MONETIZATION,
         PositionManagementCategory.REASSESSMENT),
        (PositionManagementComparison.GREATER_THAN_OR_EQUAL,
         PositionManagementComparison.LESS_THAN_OR_EQUAL),
        (PositionManagementAuthority.CALLER,
         PositionManagementAuthority.HUMAN_ANALYST),
    ),
    PositionManagementMetric.SINGLE_LOSS_FRACTION: (
        (PositionManagementCategory.REASSESSMENT,
         PositionManagementCategory.EXIT),
        (PositionManagementComparison.GREATER_THAN_OR_EQUAL,),
        (PositionManagementAuthority.REVIEWED_ARTIFACT,),
    ),
    PositionManagementMetric.REPEATED_LOSS_FRACTION: (
        (PositionManagementCategory.REASSESSMENT,
         PositionManagementCategory.EXIT),
        (PositionManagementComparison.GREATER_THAN_OR_EQUAL,),
        (PositionManagementAuthority.REVIEWED_ARTIFACT,),
    ),
}


_MAX_CANONICAL_JSON_DEPTH = 128


def _metric_rules() -> dict:
    common_text = "normalized_caller_or_human_audit_text"
    return {
        "net_liquidation_value_multiple": {
            "allowed_categories": ("monetization",),
            "allowed_comparisons": ("greater_than_or_equal",),
            "threshold_type": "exact_decimal",
            "minimum": decimal.Decimal("0"),
            "maximum": None,
            "minimum_inclusive": False,
            "maximum_inclusive": False,
            "allowed_authorities": ("caller", "human_analyst"),
            "required_artifact_field": "structure_costs_result",
            "required_reviewed_value": "exact_reviewed_total_entry_cost",
            "source_reference_rule": common_text,
            "declaration_only": True,
            "current_evaluation": False,
        },
        "remaining_dte": {
            "allowed_categories": ("reassessment",),
            "allowed_comparisons": ("less_than_or_equal",),
            "threshold_type": "exact_int",
            "minimum": 0,
            "maximum": "reviewed_dte_minus_one",
            "minimum_inclusive": True,
            "maximum_inclusive": True,
            "allowed_authorities": ("caller", "human_analyst"),
            "required_artifact_field": "structure",
            "required_reviewed_value": "common_structure_expiration_and_plan_as_of_date",
            "source_reference_rule": common_text,
            "declaration_only": True,
            "current_evaluation": False,
        },
        "bid_ask_spread_fraction": {
            "allowed_categories": ("reassessment", "exit"),
            "allowed_comparisons": ("greater_than_or_equal",),
            "threshold_type": "exact_decimal",
            "minimum": decimal.Decimal("0"),
            "maximum": None,
            "minimum_inclusive": True,
            "maximum_inclusive": False,
            "allowed_authorities": ("caller", "human_analyst"),
            "required_artifact_field": "structure_liquidity_result",
            "required_reviewed_value": "quote_methodology_and_calculation_identity",
            "source_reference_rule": common_text,
            "declaration_only": True,
            "current_evaluation": False,
        },
        "atm_iv": {
            "allowed_categories": ("monetization", "reassessment"),
            "allowed_comparisons": ("greater_than_or_equal", "less_than_or_equal"),
            "threshold_type": "exact_decimal",
            "minimum": decimal.Decimal("0"),
            "maximum": None,
            "minimum_inclusive": False,
            "maximum_inclusive": False,
            "allowed_authorities": ("caller", "human_analyst"),
            "required_artifact_field": "volatility_environment_result",
            "required_reviewed_value": "volatility_methodology_identity",
            "source_reference_rule": common_text,
            "declaration_only": True,
            "current_evaluation": False,
        },
        "skew_percentile": {
            "allowed_categories": ("monetization", "reassessment"),
            "allowed_comparisons": ("greater_than_or_equal", "less_than_or_equal"),
            "threshold_type": "exact_decimal",
            "minimum": decimal.Decimal("0"),
            "maximum": decimal.Decimal("1"),
            "minimum_inclusive": True,
            "maximum_inclusive": True,
            "allowed_authorities": ("caller", "human_analyst"),
            "required_artifact_field": "tail_pricing_result",
            "required_reviewed_value": "exact_structure_expiration_slice",
            "source_reference_rule": common_text,
            "declaration_only": True,
            "current_evaluation": False,
        },
        "single_loss_fraction": {
            "allowed_categories": ("reassessment", "exit"),
            "allowed_comparisons": ("greater_than_or_equal",),
            "threshold_type": "ExactRational",
            "minimum": None,
            "maximum": None,
            "minimum_inclusive": False,
            "maximum_inclusive": False,
            "allowed_authorities": ("reviewed_artifact",),
            "required_artifact_field": "structure_affordability_result",
            "required_reviewed_value": "corresponding_exact_boundary_and_fraction",
            "source_reference_rule": "exact_structure_affordability_lineage_calculation_id",
            "declaration_only": True,
            "current_evaluation": False,
        },
        "repeated_loss_fraction": {
            "allowed_categories": ("reassessment", "exit"),
            "allowed_comparisons": ("greater_than_or_equal",),
            "threshold_type": "ExactRational",
            "minimum": None,
            "maximum": None,
            "minimum_inclusive": False,
            "maximum_inclusive": False,
            "allowed_authorities": ("reviewed_artifact",),
            "required_artifact_field": "structure_affordability_result",
            "required_reviewed_value": "corresponding_exact_boundary_and_fraction",
            "source_reference_rule": "exact_structure_affordability_lineage_calculation_id",
            "declaration_only": True,
            "current_evaluation": False,
        },
    }


def _make_condition_rules() -> dict:
    category_values = tuple(value.value for value in _CATEGORY_ORDER)
    trigger_values = tuple(value.value for value in PositionManagementQualitativeTrigger)
    trigger_rules = {
        trigger.value: {
            "category": _QUALITATIVE_CATEGORY[trigger].value,
            "allowed_authorities": ("caller", "human_analyst"),
            "source_reference_rule": "normalized_caller_or_human_audit_text",
            "declaration_only": True,
            "current_truth_asserted": False,
            "event_intelligence_required": False,
        }
        for trigger in PositionManagementQualitativeTrigger
    }
    authority_common = {
        "allowed_condition_forms": ("quantitative", "qualitative"),
        "source_reference_rule": "normalized_caller_or_human_audit_text",
        "rationale_required": True,
        "normalized_input": False,
        "ai_authority": False,
    }
    return {
        "state_applicability": {
            "investigate": {
                "permitted": True,
                "required_categories": category_values,
                "optional_categories": (),
            },
            "watch": {
                "permitted": True,
                "required_categories": ("reassessment",),
                "optional_categories": ("monetization", "exit"),
            },
            "reject": {
                "permitted": False,
                "required_categories": (),
                "optional_categories": (),
            },
            "data_insufficient": {
                "permitted": False,
                "required_categories": (),
                "optional_categories": (),
            },
        },
        "category_order": category_values,
        "category_action_semantics": {
            "monetization": "consider monetization",
            "reassessment": "consider reassessment",
            "exit": "consider exit",
        },
        "condition_id": {
            "exact_type": "built_in_str",
            "pattern": "^[a-z][a-z0-9_]{0,63}$",
            "strip": False,
            "unicode_case_folding": False,
            "maximum_length": 64,
            "plan_wide_unique": True,
        },
        "metric_order": tuple(metric.value for metric in PositionManagementMetric),
        "metric_grammar": _metric_rules(),
        "qualitative_trigger_order": trigger_values,
        "qualitative_trigger_grammar": trigger_rules,
        "authority_rules": {
            "reviewed_artifact": {
                "allowed_condition_forms": ("quantitative",),
                "source_reference_rule": "exact_structure_affordability_lineage_calculation_id",
                "rationale_required": True,
                "normalized_input": False,
                "ai_authority": False,
            },
            "caller": dict(authority_common),
            "human_analyst": dict(authority_common),
        },
        "text_rules": {
            "source_reference": {
                "exact_type": "built_in_str",
                "strip": True,
                "empty_after_strip": False,
                "maximum_length": None,
                "duplicate_values": "allowed",
                "canonical_stored_value": "stripped",
                "subclass_rejected": True,
                "constructor_bypass": "reject_noncanonical_state",
                "surrogate_rejected": True,
            },
            "rationale": {
                "exact_type": "built_in_str",
                "strip": True,
                "empty_after_strip": False,
                "maximum_length": None,
                "duplicate_values": "allowed",
                "canonical_stored_value": "stripped",
                "subclass_rejected": True,
                "constructor_bypass": "reject_noncanonical_state",
                "surrogate_rejected": True,
            },
        },
        "ordering": {
            "condition_sort_key": (
                "category_enum_declaration_index",
                "condition_id",
            ),
            "accepted_input_containers": ("exact_tuple", "exact_list"),
            "stored_container": "exact_tuple",
            "validation_precedence": (
                "container_type",
                "item_exact_type",
                "intrinsic_condition_fields",
                "condition_id_duplicates",
                "semantic_duplicates",
                "trigger_category_conflicts",
                "canonical_sort",
                "state_cardinality",
                "assembly_prerequisites",
            ),
        },
        "duplicate_rules": {
            "negative_zero_normalization": True,
            "rational_normalization": "canonical_reduced_exact_rational",
            "source_reference_normalization": "strip_before_compare",
            "duplicate_check_timing": "after_intrinsic_normalization",
            "multiple_thresholds": "allow_when_semantic_identity_differs",
            "trigger_category_conflict": "reject_fixed_trigger_category_mismatch",
            "contradiction_solver": "absent",
        },
        "declaration_rules": {
            "current_trigger_status": False,
            "current_monitoring_state": False,
            "current_alert_state": False,
            "last_evaluation": False,
            "next_evaluation": False,
            "live_quote": False,
            "live_pnl": False,
            "automatic_decision": False,
            "action_field": False,
            "ai_field": False,
            "ai_authority": False,
        },
        "incomplete_input_rules": {
            "quantitative_condition_requires_complete_prerequisite": True,
            "missing_prerequisite": "reject_condition_and_result",
            "incomplete_prerequisite": "reject_condition_and_result",
            "qualitative_condition_with_partial_watch": True,
            "assembly_missing_data_conversion": False,
            "automatic_condition_generation": False,
            "upstream_incomplete_flag": "retain_exact_assembly_lineage_flag",
            "additional_incomplete_flag_for_empty_optional_watch_categories": False,
        },
        "risk_fraction_status_rules": {
            "accepted_conclusive_statuses": ("affordable", "not_affordable"),
            "data_insufficient_rule": (
                "allow_only_when_corresponding_boundary_and_fraction_are_exact"
            ),
            "otherwise": "reject_condition_and_result",
            "threshold_is_boundary": True,
            "current_fraction_disclosed_in_condition": False,
            "trigger_status_disclosed": False,
            "candidate_state_changed": False,
            "action_emitted": False,
        },
    }


_CONDITION_RULES = _make_condition_rules()

_OUTPUT_ARCHITECTURE = {
    "plan_type": "PositionManagementPlan",
    "result_type": "PositionManagementPlanResult",
    "retained_assembly_result_type": "CandidateResearchRecordAssemblyResult",
    "lineage_type": "CalculationLineage",
    "scope": "prospective_research_guidance",
    "semantics": (
        "prospective_research_guidance_for_"
        "hypothetical_future_long_option_position"
    ),
    "declaration_only": True,
    "current_evaluation_excluded": True,
    "package_root_exported": False,
}

_PROHIBITED_BEHAVIOR = (
    "ownership_claims",
    "opened_position_claims",
    "recommendation",
    "live_evaluation",
    "monitoring",
    "alerts",
    "scheduling",
    "provider_access",
    "llm_authority",
    "screening",
    "rendering",
    "sizing",
    "holdings",
    "brokerage",
    "order_management",
    "execution",
    "automatic_monetization",
    "automatic_exit",
    "stop_loss",
    "take_profit",
    "persistence",
    "generic_rule_framework",
    "upstream_producer_replay",
    "transformation_producer_replay",
    "affordability_producer_replay",
    "event_intelligence_access",
    "scanner_invocation",
    "renderer_invocation",
    "notifier_invocation",
    "system_clock",
    "calculation_id_generation",
    "condition_generation",
    "threshold_generation",
    "state_generation",
)


def _fixed_output_architecture() -> dict:
    return {
        "plan_type": "PositionManagementPlan",
        "result_type": "PositionManagementPlanResult",
        "retained_assembly_result_type": "CandidateResearchRecordAssemblyResult",
        "lineage_type": "CalculationLineage",
        "scope": "prospective_research_guidance",
        "semantics": (
            "prospective_research_guidance_for_"
            "hypothetical_future_long_option_position"
        ),
        "declaration_only": True,
        "current_evaluation_excluded": True,
        "package_root_exported": False,
    }


def _fixed_prohibited_behavior() -> tuple:
    return (
        "ownership_claims", "opened_position_claims", "recommendation",
        "live_evaluation", "monitoring", "alerts", "scheduling",
        "provider_access", "llm_authority", "screening", "rendering",
        "sizing", "holdings", "brokerage", "order_management", "execution",
        "automatic_monetization", "automatic_exit", "stop_loss", "take_profit",
        "persistence", "generic_rule_framework", "upstream_producer_replay",
        "transformation_producer_replay", "affordability_producer_replay",
        "event_intelligence_access", "scanner_invocation", "renderer_invocation",
        "notifier_invocation", "system_clock", "calculation_id_generation",
        "condition_generation", "threshold_generation", "state_generation",
    )


def _required_text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must have exact built-in type str")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in normalized):
        raise ValueError(f"{name} must not contain Unicode surrogates")
    return normalized


def _canonical_text(name: str, value: object) -> str:
    normalized = _required_text(name, value)
    if normalized != value:
        raise ValueError(f"{name} is not in canonical constructor state")
    return normalized


def _condition_id(value: object) -> str:
    if type(value) is not str:
        raise TypeError("condition_id must have exact built-in type str")
    if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", value, flags=re.ASCII) is None:
        raise ValueError("condition_id is not canonical")
    return value


def _exact_enum(value: object, enum_type: type, name: str) -> None:
    if type(value) is not enum_type:
        raise TypeError(f"{name} must have exact type {enum_type.__name__}")


def _normalize_decimal_threshold(value: object, name: str, *, positive: bool = False,
                                 nonnegative: bool = False) -> decimal.Decimal:
    if type(value) is not decimal.Decimal:
        raise TypeError(f"{name} must have exact type Decimal")
    if not value.is_finite():
        raise ValueError(f"{name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{name} must be greater than 0")
    if nonnegative and value < 0:
        raise ValueError(f"{name} must be 0 or greater")
    return decimal.Decimal("0") if value.is_zero() else value


def _strict_rational(value: object, name: str) -> ExactRational:
    if type(value) is not ExactRational:
        raise TypeError(f"{name} must have exact type ExactRational")

    try:
        numerator = object.__getattribute__(value, "numerator")
        denominator = object.__getattribute__(value, "denominator")
    except AttributeError as error:
        raise ValueError(f"{name} is partially initialized") from error
    if type(numerator) is not int or type(denominator) is not int:
        raise TypeError(f"{name} fields must have exact type int")
    try:
        rebuilt = ExactRational(numerator, denominator)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} is malformed") from error
    if rebuilt.numerator != numerator or rebuilt.denominator != denominator:
        raise ValueError(f"{name} must be canonical and reduced")
    if rebuilt.numerator < 0 or rebuilt.numerator > rebuilt.denominator:
        raise ValueError(f"{name} must be within inclusive range [0, 1]")
    return rebuilt


def _validate_quantitative_grammar(value: object) -> None:
    category, metric, comparison, authority = (
        value.category, value.metric, value.comparison, value.authority
    )
    allowed_categories, allowed_comparisons, allowed_authorities = _QUANTITATIVE_ALLOWED[metric]
    if category not in allowed_categories:
        raise ValueError("quantitative category is not allowed for metric")
    if comparison not in allowed_comparisons:
        raise ValueError("quantitative comparison is not allowed for metric")
    if authority not in allowed_authorities:
        raise ValueError("quantitative authority is not allowed for metric")
    if metric is PositionManagementMetric.REMAINING_DTE:
        if type(value.threshold) is not int:
            raise TypeError("remaining_dte threshold must have exact type int")
        if value.threshold < 0:
            raise ValueError("remaining_dte threshold must be nonnegative")
    elif metric in {
        PositionManagementMetric.NET_LIQUIDATION_VALUE_MULTIPLE,
        PositionManagementMetric.ATM_IV,
    }:
        _normalize_decimal_threshold(
            value.threshold, "threshold", positive=True
        )
    elif metric in {
        PositionManagementMetric.BID_ASK_SPREAD_FRACTION,
        PositionManagementMetric.SKEW_PERCENTILE,
    }:
        threshold = _normalize_decimal_threshold(
            value.threshold, "threshold", nonnegative=True
        )
        if metric is PositionManagementMetric.SKEW_PERCENTILE and threshold > 1:
            raise ValueError("skew_percentile threshold must be within [0, 1]")
    else:
        _strict_rational(value.threshold, "threshold")


def _verify_quantitative_intrinsic(
    value: object, *, require_canonical_text: bool = True
) -> None:
    fields = (
        "condition_id", "category", "metric", "comparison", "threshold",
        "authority", "source_reference", "rationale",
    )
    try:
        values = tuple(object.__getattribute__(value, field) for field in fields)
    except AttributeError as error:
        raise ValueError("quantitative condition is partially initialized") from error
    _condition_id(values[0])
    _exact_enum(values[1], PositionManagementCategory, "category")
    _exact_enum(values[2], PositionManagementMetric, "metric")
    _exact_enum(values[3], PositionManagementComparison, "comparison")
    _exact_enum(values[5], PositionManagementAuthority, "authority")
    text_validator = _canonical_text if require_canonical_text else _required_text
    text_validator("source_reference", values[6])
    text_validator("rationale", values[7])
    metric = values[2]
    threshold = values[4]
    if (
        require_canonical_text
        and type(threshold) is decimal.Decimal
        and threshold.is_zero()
        and threshold.is_signed()
    ):
        raise ValueError("threshold is not in canonical constructor state")
    if metric is PositionManagementMetric.REMAINING_DTE:
        if type(threshold) is not int:
            raise TypeError("remaining_dte threshold must have exact type int")
        if threshold < 0:
            raise ValueError("remaining_dte threshold must be nonnegative")
    elif metric in {
        PositionManagementMetric.NET_LIQUIDATION_VALUE_MULTIPLE,
        PositionManagementMetric.ATM_IV,
    }:
        _normalize_decimal_threshold(threshold, "threshold", positive=True)
    elif metric is PositionManagementMetric.BID_ASK_SPREAD_FRACTION:
        _normalize_decimal_threshold(threshold, "threshold", nonnegative=True)
    elif metric is PositionManagementMetric.SKEW_PERCENTILE:
        normalized = _normalize_decimal_threshold(threshold, "threshold", nonnegative=True)
        if normalized > 1:
            raise ValueError("skew_percentile threshold must be within [0, 1]")
    else:
        _strict_rational(threshold, "threshold")


def _verify_qualitative_intrinsic(
    value: object, *, require_canonical_text: bool = True
) -> None:
    fields = (
        "condition_id", "category", "trigger", "authority",
        "source_reference", "rationale",
    )
    try:
        values = tuple(object.__getattribute__(value, field) for field in fields)
    except AttributeError as error:
        raise ValueError("qualitative condition is partially initialized") from error
    _condition_id(values[0])
    _exact_enum(values[1], PositionManagementCategory, "category")
    _exact_enum(values[2], PositionManagementQualitativeTrigger, "trigger")
    _exact_enum(values[3], PositionManagementAuthority, "authority")
    text_validator = _canonical_text if require_canonical_text else _required_text
    text_validator("source_reference", values[4])
    text_validator("rationale", values[5])


def _validate_qualitative_grammar(value: object) -> None:
    expected_category = _QUALITATIVE_CATEGORY[value.trigger]
    if value.category is not expected_category:
        raise ValueError("qualitative trigger has a fixed category")
    if value.authority not in {
        PositionManagementAuthority.CALLER,
        PositionManagementAuthority.HUMAN_ANALYST,
    }:
        raise ValueError("qualitative authority must be caller or human analyst")


def _verify_condition_intrinsic(value: object) -> None:
    if type(value) is QuantitativePositionManagementCondition:
        _verify_quantitative_intrinsic(value)
    elif type(value) is QualitativePositionManagementCondition:
        _verify_qualitative_intrinsic(value)
    else:
        raise TypeError("condition must have an exact supported condition type")


def _condition_semantic_identity(value: object) -> tuple:
    if type(value) is QuantitativePositionManagementCondition:
        threshold = value.threshold
        if type(threshold) is decimal.Decimal and threshold.is_zero():
            threshold = decimal.Decimal("0")
        return (
            "quantitative", value.category, value.metric, value.comparison,
            threshold, value.authority, value.source_reference,
        )
    return (
        "qualitative", value.category, value.trigger, value.authority,
        value.source_reference,
    )


def _verify_plan_intrinsic(value: object) -> None:
    if type(value) is not PositionManagementPlan:
        raise TypeError("plan must have exact type PositionManagementPlan")
    fields = ("scope", "candidate_id", "candidate_state", "as_of_date", "structure", "conditions")
    try:
        scope, candidate_id, state, as_of_date, structure, conditions = tuple(
            object.__getattribute__(value, field) for field in fields
        )
    except AttributeError as error:
        raise ValueError("plan is partially initialized") from error
    if scope is not PositionManagementScope.PROSPECTIVE_RESEARCH_GUIDANCE:
        if type(scope) is not PositionManagementScope:
            raise TypeError("scope must have exact type PositionManagementScope")
        raise ValueError("scope is not prospective research guidance")
    if type(candidate_id) is not str:
        raise TypeError("candidate_id must have exact built-in type str")
    if not candidate_id or candidate_id.strip() != candidate_id:
        raise ValueError("candidate_id must already be canonical")
    if type(state) is not CandidateState:
        raise TypeError("candidate_state must have exact type CandidateState")
    if state not in {CandidateState.WATCH, CandidateState.INVESTIGATE}:
        raise ValueError("candidate_state is not permitted for a plan")
    if type(as_of_date) is not datetime.date:
        raise TypeError("as_of_date must have exact type date")
    risk_assessment._strict_structure(structure)
    if any(as_of_date >= leg.expiration for leg in structure.legs):
        raise ValueError("as_of_date must precede every structure expiration")
    if type(conditions) is not tuple:
        raise TypeError("conditions must have exact type tuple")
    if not all(
        type(condition) in {
            QuantitativePositionManagementCondition,
            QualitativePositionManagementCondition,
        }
        for condition in conditions
    ):
        raise TypeError("conditions contain an unsupported exact item type")
    for condition in conditions:
        _verify_condition_intrinsic(condition)
    identifiers = tuple(condition.condition_id for condition in conditions)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("condition IDs must be unique across the plan")
    semantic = tuple(_condition_semantic_identity(item) for item in conditions)
    if len(set(semantic)) != len(semantic):
        raise ValueError("semantic duplicate conditions are not permitted")
    for condition in conditions:
        if type(condition) is QualitativePositionManagementCondition:
            _validate_qualitative_grammar(condition)
        else:
            _validate_quantitative_grammar(condition)
    expected_order = tuple(
        sorted(conditions, key=lambda item: (_CATEGORY_INDEX[item.category], item.condition_id))
    )
    if conditions != expected_order:
        raise ValueError("conditions are not in canonical order")
    category_values = {condition.category for condition in conditions}
    required = (
        _CATEGORY_ORDER if state is CandidateState.INVESTIGATE
        else (PositionManagementCategory.REASSESSMENT,)
    )
    if any(category not in category_values for category in required):
        raise ValueError("plan does not satisfy candidate-state category cardinality")


@dataclass(frozen=True)
class QuantitativePositionManagementCondition:
    condition_id: str
    category: PositionManagementCategory
    metric: PositionManagementMetric
    comparison: PositionManagementComparison
    threshold: Union[int, decimal.Decimal, ExactRational]
    authority: PositionManagementAuthority
    source_reference: str
    rationale: str

    def __post_init__(self) -> None:
        if type(self) is not QuantitativePositionManagementCondition:
            raise TypeError("condition must have exact type QuantitativePositionManagementCondition")
        _verify_quantitative_intrinsic(self, require_canonical_text=False)
        _validate_quantitative_grammar(self)
        if type(self.threshold) is decimal.Decimal and self.threshold.is_zero():
            object.__setattr__(self, "threshold", decimal.Decimal("0"))
        object.__setattr__(self, "source_reference", _required_text("source_reference", self.source_reference))
        object.__setattr__(self, "rationale", _required_text("rationale", self.rationale))


@dataclass(frozen=True)
class QualitativePositionManagementCondition:
    condition_id: str
    category: PositionManagementCategory
    trigger: PositionManagementQualitativeTrigger
    authority: PositionManagementAuthority
    source_reference: str
    rationale: str

    def __post_init__(self) -> None:
        if type(self) is not QualitativePositionManagementCondition:
            raise TypeError("condition must have exact type QualitativePositionManagementCondition")
        _verify_qualitative_intrinsic(self, require_canonical_text=False)
        _validate_qualitative_grammar(self)
        object.__setattr__(self, "source_reference", _required_text("source_reference", self.source_reference))
        object.__setattr__(self, "rationale", _required_text("rationale", self.rationale))


@dataclass(frozen=True)
class PositionManagementPlan:
    scope: PositionManagementScope
    candidate_id: str
    candidate_state: CandidateState
    as_of_date: datetime.date
    structure: OptionStructure
    conditions: Tuple[
        Union[
            QuantitativePositionManagementCondition,
            QualitativePositionManagementCondition,
        ],
        ...,
    ]

    def __post_init__(self) -> None:
        if type(self.conditions) is not tuple and type(self.conditions) is not list:
            raise TypeError("conditions must have exact type tuple or list")
        normalized = tuple(self.conditions)
        for condition in normalized:
            if type(condition) not in {
                QuantitativePositionManagementCondition,
                QualitativePositionManagementCondition,
            }:
                raise TypeError("conditions contain an unsupported exact item type")
        # Validate intrinsic fields before canonical sorting, then discard caller order.
        for condition in normalized:
            _verify_condition_intrinsic(condition)
        identifiers = tuple(condition.condition_id for condition in normalized)
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("condition IDs must be unique across the plan")
        semantic = tuple(_condition_semantic_identity(item) for item in normalized)
        if len(set(semantic)) != len(semantic):
            raise ValueError("semantic duplicate conditions are not permitted")
        for condition in normalized:
            if type(condition) is QualitativePositionManagementCondition:
                _validate_qualitative_grammar(condition)
            else:
                _validate_quantitative_grammar(condition)
        normalized = tuple(sorted(normalized, key=lambda item: (_CATEGORY_INDEX[item.category], item.condition_id)))
        object.__setattr__(self, "conditions", normalized)
        _verify_plan_intrinsic(self)


def _canonical_rational(value: ExactRational) -> dict:
    return {"numerator": value.numerator, "denominator": value.denominator}


def _canonical_condition(value: object) -> dict:
    if type(value) is QuantitativePositionManagementCondition:
        threshold = value.threshold
        if type(threshold) is ExactRational:
            threshold = _canonical_rational(threshold)
        return {
            "condition_type": "quantitative",
            "condition_id": value.condition_id,
            "category": value.category.value,
            "metric": value.metric.value,
            "comparison": value.comparison.value,
            "threshold": threshold,
            "authority": value.authority.value,
            "source_reference": value.source_reference,
            "rationale": value.rationale,
        }
    return {
        "condition_type": "qualitative",
        "condition_id": value.condition_id,
        "category": value.category.value,
        "trigger": value.trigger.value,
        "authority": value.authority.value,
        "source_reference": value.source_reference,
        "rationale": value.rationale,
    }


def _canonical_plan(value: PositionManagementPlan) -> dict:
    return {
        "scope": value.scope.value,
        "candidate_id": value.candidate_id,
        "candidate_state": value.candidate_state.value,
        "as_of_date": value.as_of_date,
        "structure": candidate_assembly._structure(value.structure),
        "conditions": tuple(_canonical_condition(condition) for condition in value.conditions),
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


def _scan_canonical_json_depth(parameters_json: object) -> None:
    if type(parameters_json) is not str:
        raise TypeError("parameters_json must have exact built-in type str")
    depth = 0
    in_string = False
    escaped = False
    for character in parameters_json:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{" or character == "[":
            depth += 1
            if depth > _MAX_CANONICAL_JSON_DEPTH:
                raise ValueError("parameters_json nesting exceeds supported depth")
        elif (character == "}" or character == "]") and depth > 0:
            depth -= 1


def _decode_guarded_parameters(
    parameters_json: object,
    expected_keys: set,
    context: str,
) -> object:
    if type(parameters_json) is not str:
        raise TypeError("parameters_json must have exact built-in type str")
    _scan_canonical_json_depth(parameters_json)
    try:
        return candidate_assembly._transformations._decode_strict_tagged_parameters(
            parameters_json,
            expected_keys,
            context,
        )
    except RecursionError as error:
        raise ValueError(
            "parameters_json nesting exceeds supported depth"
        ) from error


def _strict_canonical_utc_datetime(
    value: object,
    name: str,
) -> datetime.datetime:
    if type(value) is not datetime.datetime:
        raise TypeError(f"{name} must have exact type datetime")
    if value.tzinfo is not datetime.timezone.utc or value.fold != 0:
        raise ValueError(f"{name} must be canonical UTC")
    return value


def _verify_retained_assembly(value: object) -> None:
    if type(value) is not CandidateResearchRecordAssemblyResult:
        raise TypeError("assembly_result must have exact type CandidateResearchRecordAssemblyResult")
    fields = (
        "record",
        "volatility_environment_result",
        "tail_pricing_result",
        "structure_liquidity_result",
        "structure_costs_result",
        "scenario_valuation_result",
        "expiration_payoff_threshold_result",
        "structure_affordability_result",
        "lineage",
    )
    for field in fields:
        try:
            object.__getattribute__(value, field)
        except AttributeError as error:
            raise ValueError(f"assembly_result lacks required field {field}") from error
    try:
        candidate_assembly._verify_candidate_research_record_assembly(value)
    except (AttributeError, KeyError, IndexError, json.JSONDecodeError,
            decimal.DecimalException, OverflowError) as error:
        raise ValueError("retained assembly has malformed structural state") from error


def _verify_lineage_constructor_state(value: object) -> None:
    if type(value) is not CalculationLineage:
        raise TypeError("lineage must have exact type CalculationLineage")
    fields = (
        "calculation_id", "calculation_type", "methodology_id",
        "methodology_version", "calculated_at", "inputs",
        "parameters_json", "quality_flags",
    )
    try:
        values = tuple(object.__getattribute__(value, field) for field in fields)
    except AttributeError as error:
        raise ValueError("lineage is partially initialized") from error

    (
        calculation_id,
        calculation_type,
        methodology_id,
        methodology_version,
        calculated_at,
        inputs,
        parameters_json,
        quality_flags,
    ) = values
    for name, field_value in (
        ("calculation_id", calculation_id),
        ("calculation_type", calculation_type),
        ("methodology_id", methodology_id),
        ("methodology_version", methodology_version),
        ("parameters_json", parameters_json),
    ):
        if type(field_value) is not str:
            raise TypeError(f"lineage {name} must have exact type str")
        if not field_value or field_value != field_value.strip():
            raise ValueError(f"lineage {name} is not canonical")

    _strict_canonical_utc_datetime(calculated_at, "lineage calculated_at")

    if type(inputs) is not tuple:
        raise TypeError("lineage inputs must have exact type tuple")
    verified_inputs = []
    for index, item in enumerate(inputs):
        label = f"lineage inputs[{index}]"
        if type(item) is not CalculationInputReference:
            raise TypeError(f"{label} must have exact type CalculationInputReference")
        try:
            record_id = object.__getattribute__(item, "record_id")
            normalized_at = object.__getattribute__(item, "normalized_at")
            source_ids = object.__getattribute__(item, "source_ids")
        except AttributeError as error:
            raise ValueError(f"{label} is partially initialized") from error
        if type(record_id) is not str:
            raise TypeError(f"{label}.record_id must have exact type str")
        if not record_id or record_id != record_id.strip():
            raise ValueError(f"{label}.record_id is not canonical")
        _strict_canonical_utc_datetime(normalized_at, f"{label}.normalized_at")
        if type(source_ids) is not tuple:
            raise TypeError(f"{label}.source_ids must have exact type tuple")
        normalized_source_ids = []
        for source_id in source_ids:
            if type(source_id) is not str:
                raise TypeError(f"{label}.source_ids items must have exact type str")
            if not source_id or source_id != source_id.strip():
                raise ValueError(f"{label}.source_ids item is not canonical")
            normalized_source_ids.append(source_id)
        if not normalized_source_ids:
            raise ValueError(f"{label}.source_ids must not be empty")
        if len(set(normalized_source_ids)) != len(normalized_source_ids):
            raise ValueError(f"{label}.source_ids must not contain duplicates")
        if tuple(sorted(normalized_source_ids)) != source_ids:
            raise ValueError(f"{label}.source_ids are not in canonical order")
        verified_inputs.append(item)
    if tuple(sorted(verified_inputs, key=lambda item: item.record_id)) != inputs:
        raise ValueError("lineage inputs are not in canonical order")
    if len({item.record_id for item in inputs}) != len(inputs):
        raise ValueError("lineage input record IDs must not contain duplicates")

    if type(quality_flags) is not tuple:
        raise TypeError("lineage quality_flags must have exact type tuple")
    if any(type(flag) is not CalculationQualityFlag for flag in quality_flags):
        raise TypeError("lineage quality_flags items must have exact enum type")
    if len(set(quality_flags)) != len(quality_flags):
        raise ValueError("lineage quality_flags must not contain duplicates")
    if tuple(flag for flag in CalculationQualityFlag if flag in set(quality_flags)) != quality_flags:
        raise ValueError("lineage quality_flags are not in canonical order")

    try:
        _decode_guarded_parameters(
            parameters_json,
            {
                "schema_version",
                "output_architecture",
                "reviewed_candidate_assembly",
                "plan",
                "condition_rules",
                "prohibited_behavior",
            },
            "position-management lineage",
        )
        rebuilt = CalculationLineage(*values)
    except (AttributeError, KeyError, IndexError, json.JSONDecodeError,
            decimal.DecimalException, OverflowError) as error:
        raise ValueError("lineage has malformed structural state") from error

    for field in fields:
        supplied = object.__getattribute__(value, field)
        canonical = object.__getattribute__(rebuilt, field)
        if type(supplied) is not type(canonical) or supplied != canonical:
            raise ValueError(f"lineage {field} is not in canonical constructor state")


def _verify_prerequisites(assembly: CandidateResearchRecordAssemblyResult,
                          plan: PositionManagementPlan) -> None:
    common_expiration = min(leg.expiration for leg in plan.structure.legs)
    direct = {
        name: getattr(assembly, name)
        for name in (
            "structure_costs_result", "structure_liquidity_result",
            "volatility_environment_result", "tail_pricing_result",
            "structure_affordability_result",
        )
    }
    affordability = direct["structure_affordability_result"]
    for condition in plan.conditions:
        if type(condition) is QualitativePositionManagementCondition:
            continue
        metric = condition.metric
        required = {
            PositionManagementMetric.NET_LIQUIDATION_VALUE_MULTIPLE: "structure_costs_result",
            PositionManagementMetric.BID_ASK_SPREAD_FRACTION: "structure_liquidity_result",
            PositionManagementMetric.ATM_IV: "volatility_environment_result",
            PositionManagementMetric.SKEW_PERCENTILE: "tail_pricing_result",
            PositionManagementMetric.SINGLE_LOSS_FRACTION: "structure_affordability_result",
            PositionManagementMetric.REPEATED_LOSS_FRACTION: "structure_affordability_result",
        }.get(metric)
        if required is not None and direct[required] is None:
            raise ValueError(f"{metric.value} prerequisite is missing")
        if metric is PositionManagementMetric.REMAINING_DTE:
            reviewed_dte = (common_expiration - plan.as_of_date).days
            if condition.threshold >= reviewed_dte:
                raise ValueError("remaining_dte threshold must be below reviewed DTE")
        if metric is PositionManagementMetric.SKEW_PERCENTILE:
            _select_structure_tail_slice(
                direct["tail_pricing_result"].records,
                common_expiration,
            )
        if metric in {
            PositionManagementMetric.SINGLE_LOSS_FRACTION,
            PositionManagementMetric.REPEATED_LOSS_FRACTION,
        }:
            record = affordability.record
            assumptions = record.assumptions
            boundary = (
                assumptions.maximum_single_structure_loss_fraction
                if metric is PositionManagementMetric.SINGLE_LOSS_FRACTION
                else assumptions.maximum_repeated_loss_fraction
            )
            actual = (
                record.single_loss_fraction
                if metric is PositionManagementMetric.SINGLE_LOSS_FRACTION
                else record.repeated_loss_fraction
            )
            if boundary is None or actual is None:
                raise ValueError("risk-fraction condition requires exact boundary and fraction")
            _strict_rational(boundary, "affordability boundary")
            _strict_rational(actual, "affordability fraction")
            if condition.threshold != boundary:
                raise ValueError("risk-fraction threshold must equal reviewed boundary")
            if condition.source_reference != affordability.lineage.calculation_id:
                raise ValueError("risk-fraction source reference must equal affordability calculation ID")


def _assembly_lineages(assembly: CandidateResearchRecordAssemblyResult) -> tuple:
    artifacts = tuple(
        getattr(assembly, name)
        for name in candidate_assembly._ARTIFACT_FIELDS
        if getattr(assembly, name) is not None
    )
    lineages = [artifact.lineage for artifact in artifacts]
    _verified, nested, _reconstructed = candidate_assembly._intrinsic_artifacts(assembly)
    for value in nested:
        lineages.append(value.lineage if hasattr(value, "lineage") else value[1])
    return tuple(lineages)


def _canonical_parameters(assembly: CandidateResearchRecordAssemblyResult,
                          plan: PositionManagementPlan) -> dict:
    return {
        "schema_version": "v0.1",
        "output_architecture": _fixed_output_architecture(),
        "reviewed_candidate_assembly": {
            "lineage": candidate_assembly._lineage(assembly.lineage),
            "parameters": candidate_assembly._parameters(assembly),
        },
        "plan": _canonical_plan(plan),
        "condition_rules": _make_condition_rules(),
        "prohibited_behavior": _fixed_prohibited_behavior(),
    }


def _verify_position_management_plan_result(value: object) -> None:
    if type(value) is not PositionManagementPlanResult:
        raise TypeError("value must have exact type PositionManagementPlanResult")
    try:
        assembly = object.__getattribute__(value, "assembly_result")
        plan = object.__getattribute__(value, "plan")
        lineage = object.__getattribute__(value, "lineage")
    except AttributeError as error:
        raise ValueError("result is partially initialized") from error
    _verify_retained_assembly(assembly)
    if type(plan) is not PositionManagementPlan:
        raise TypeError("plan must have exact type PositionManagementPlan")
    _verify_plan_intrinsic(plan)
    _verify_lineage_constructor_state(lineage)
    if plan.candidate_id != assembly.record.candidate_id:
        raise ValueError("plan candidate_id does not correspond to assembly")
    if plan.candidate_state is not assembly.record.state:
        raise ValueError("plan candidate_state does not correspond to assembly")
    if plan.as_of_date != assembly.record.as_of_date:
        raise ValueError("plan as_of_date does not correspond to assembly")
    if plan.structure is not assembly.record.structure:
        raise ValueError("plan structure must retain the exact reviewed structure")
    _verify_prerequisites(assembly, plan)
    if lineage.calculation_type != "position_management_plan":
        raise ValueError("position-management calculation type is invalid")
    if lineage.methodology_id != "prospective-human-judgment-position-management-plan":
        raise ValueError("position-management methodology ID is invalid")
    if lineage.methodology_version != "v0.1":
        raise ValueError("position-management methodology version is invalid")
    if lineage.inputs != assembly.lineage.inputs:
        raise ValueError("position-management inputs must equal assembly inputs")
    if lineage.quality_flags != assembly.lineage.quality_flags:
        raise ValueError("position-management quality flags must equal assembly flags")
    lineages = _assembly_lineages(assembly)
    dependency_ids = {
        assembly.lineage.calculation_id,
        *(item.calculation_id for item in lineages),
    }
    input_ids = {item.record_id for item in assembly.lineage.inputs}
    if lineage.calculation_id in dependency_ids or lineage.calculation_id in input_ids:
        raise ValueError("position-management calculation ID collides with retained dependency")
    if any(lineage.calculated_at < item.calculated_at for item in lineages):
        raise ValueError("position-management calculation precedes a dependency")
    if lineage.calculated_at < assembly.lineage.calculated_at:
        raise ValueError("position-management calculation precedes the assembly")
    if any(lineage.calculated_at < item.normalized_at for item in lineage.inputs):
        raise ValueError("position-management calculation precedes an input")
    expected_parameters = _canonical_parameters(assembly, plan)
    decoded = _decode_guarded_parameters(
        lineage.parameters_json,
        {"schema_version", "output_architecture", "reviewed_candidate_assembly",
         "plan", "condition_rules", "prohibited_behavior"},
        "position-management plan",
    )
    _exact_tree(decoded, expected_parameters, "parameters")
    if lineage.parameters_json != canonicalize_lineage_parameters(expected_parameters):
        raise ValueError("position-management parameters are not independently canonical")


def _select_structure_tail_slice(records: object, common_expiration: datetime.date) -> object:
    if type(records) is not tuple:
        raise TypeError("tail records must have exact type tuple")
    matching = tuple(
        item for item in records if item.expiration == common_expiration
    )
    if len(matching) != 1:
        raise ValueError(
            "skew_percentile requires one structure-expiration tail slice"
        )
    return matching[0]


@dataclass(frozen=True)
class PositionManagementPlanResult:
    assembly_result: CandidateResearchRecordAssemblyResult
    plan: PositionManagementPlan
    lineage: CalculationLineage

    def __post_init__(self) -> None:
        _verify_position_management_plan_result(self)


def _strict_calculated_at(value: object) -> datetime.datetime:
    return _strict_canonical_utc_datetime(value, "calculated_at")


def create_position_management_plan(
    calculation_id: object,
    assembly_result: object,
    conditions: object,
    calculated_at: object,
) -> PositionManagementPlanResult:
    """Create and fully verify one prospective position-management plan."""

    if type(calculation_id) is not str:
        raise TypeError("calculation_id must have exact built-in type str")
    normalized_id = calculation_id.strip()
    if not normalized_id:
        raise ValueError("calculation_id must not be empty")
    if type(assembly_result) is not CandidateResearchRecordAssemblyResult:
        raise TypeError("assembly_result must have exact type CandidateResearchRecordAssemblyResult")
    _verify_retained_assembly(assembly_result)
    calculated_at = _strict_calculated_at(calculated_at)
    plan = PositionManagementPlan(
        PositionManagementScope.PROSPECTIVE_RESEARCH_GUIDANCE,
        assembly_result.record.candidate_id,
        assembly_result.record.state,
        assembly_result.record.as_of_date,
        assembly_result.record.structure,
        conditions,
    )
    parameters = _canonical_parameters(assembly_result, plan)
    lineage = CalculationLineage(
        normalized_id,
        "position_management_plan",
        "prospective-human-judgment-position-management-plan",
        "v0.1",
        calculated_at,
        assembly_result.lineage.inputs,
        canonicalize_lineage_parameters(parameters),
        assembly_result.lineage.quality_flags,
    )
    return PositionManagementPlanResult(assembly_result, plan, lineage)
