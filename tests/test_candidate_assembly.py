import dataclasses
import datetime
import copy
import functools
import inspect
import json
import math
import decimal
import subprocess
import sys
import unittest
from unittest import mock

import convexity_hunter
from convexity_hunter import market_data, market_data_transformations
from convexity_hunter.candidate_assembly import (
    CandidateResearchRecordAssemblyResult,
    assemble_candidate_research_record,
)
import convexity_hunter.candidate_assembly as assembly
from convexity_hunter.evidence import (
    CandidateState,
    ClassifiedEvidence,
    EvidenceImpact,
    EvidenceKind,
)
from convexity_hunter.market_data import (
    CalculationQualityFlag,
    MarketDataRelationshipRole,
    SourceQualityFlag,
)
from convexity_hunter.market_data import (
    CalculationInputReference,
    CalculationLineage,
    canonicalize_lineage_parameters,
)
from convexity_hunter.market_data_transformations import (
    ExactRational,
    HistoricalRealizedVolatilityTransformationResult,
    ScenarioPricingCalculationResult,
    transform_expiration_payoff_thresholds,
    transform_scenario_valuation,
)
from convexity_hunter.report import CandidateResearchRecord
from convexity_hunter import risk_assessment
from convexity_hunter.risk_assessment import (
    RiskBudgetAssumptions,
    assess_structure_affordability,
)

from test_market_data_transformations import (
    CALCULATED_AT,
    SESSION_DATE,
    make_scenario_valuation_result,
    make_historical_assessment,
    transform_historical,
    make_selection,
    transform,
)
from test_risk_assessment import complete_assumptions


# Frozen, source-level byte oracles.  These are deliberately complete rather
# than hashes or values assembled by any test-time serializer.

ZERO_WATCH_PARAMETERS_JSON = (
    '{"$map":[["assembly_rules",{"$map":[["calculation_id_closure",{"$map":[["direct_dependencies",{"'
    '$map":[["constraint","pairwise_distinct_and_disjoint_from_assembly"],["fields",{"$list":["volati'
    'lity_environment_result","tail_pricing_result","structure_liquidity_result","structure_costs_res'
    'ult","scenario_valuation_result","expiration_payoff_threshold_result","structure_affordability_r'
    'esult"]}]]}],["nested_dependencies",{"$map":[["collection_order","first_occurrence_depth_first_b'
    'y_direct_field_order"],["constraint","disjoint_from_assembly_and_normalized_record_ids"],["roots'
    '",{"$list":["volatility_environment_result","tail_pricing_result","structure_liquidity_result","'
    'structure_costs_result","scenario_valuation_result","expiration_payoff_threshold_result","struct'
    'ure_affordability_result"]}],["traversal","recursive_verified_dependency_disclosures"]]}],["norm'
    'alized_inputs",{"$map":[["constraint","disjoint_from_every_calculation_id"],["identifier","recor'
    'd_id"]]}],["shared_reuse",{"$map":[["allowed",true],["constraint","same_calculation_id_only_for_'
    'byte_identical_complete_calculation"]]}]]}],["candidate_record_mapping",{"$map":[["costs","struc'
    'ture_costs_result.record"],["liquidity","structure_liquidity_result.record"],["scenario_results"'
    ',"scenario_valuation_result.records"],["sidecar_only",{"$list":["expiration_payoff_threshold_res'
    'ult","structure_affordability_result"]}],["tail_pricing_slices","tail_pricing_result.records"],['
    '"volatility_environment","volatility_environment_result.record"]]}],["chronology",{"$map":[["dir'
    'ect_dependencies",{"$map":[["left","assembly.calculated_at"],["operator",">="],["right","each_pr'
    'esent_direct_dependency.lineage.calculated_at"]]}],["nested_dependencies",{"$map":[["left","asse'
    'mbly.calculated_at"],["operator",">="],["right","each_recursive_verified_dependency.lineage.calc'
    'ulated_at"]]}],["normalized_inputs",{"$map":[["left","assembly.calculated_at"],["operator",">="]'
    ',["right","each_normalized_input.normalized_at"]]}],["zero_artifacts",{"$map":[["comparison_coun'
    't",0]]}]]}],["dependency_closure",{"$map":[["expiration_payoff_threshold_result",{"$list":["stru'
    'cture_costs_result"]}],["scenario_valuation_result",{"$list":["volatility_environment_result","t'
    'ail_pricing_result","structure_costs_result"]}],["structure_affordability_result",{"$list":["str'
    'ucture_costs_result"]}],["tail_pricing_result",{"$list":["volatility_environment_result"]}]]}],['
    '"missing_data",{"$map":[["data_insufficient",{"$map":[["assembler_generates_descriptions",false]'
    ',["empty_allowed",false],["nonempty_required_when",{"$list":["always"]}],["semantic_corresponden'
    'ce_to_individual_missing_artifacts_required",false]]}],["investigate",{"$map":[["assembler_gener'
    'ates_descriptions",false],["empty_allowed",true],["nonempty_required_when",{"$list":[]}],["seman'
    'tic_correspondence_to_individual_missing_artifacts_required",false]]}],["reject",{"$map":[["asse'
    'mbler_generates_descriptions",false],["empty_allowed",true],["nonempty_required_when",{"$list":['
    '"any_artifact_absent","any_direct_artifact_has_incomplete_input_used"]}],["semantic_corresponden'
    'ce_to_individual_missing_artifacts_required",false]]}],["watch",{"$map":[["assembler_generates_d'
    'escriptions",false],["empty_allowed",true],["nonempty_required_when",{"$list":["any_artifact_abs'
    'ent","any_direct_artifact_has_incomplete_input_used"]}],["semantic_correspondence_to_individual_'
    'missing_artifacts_required",false]]}]]}],["normalized_input_union",{"$map":[["caller_values",{"$'
    'list":["candidate_id","state","state_rationale","as_of_date","hypothesis","structure","evidence"'
    ',"falsification_conditions","missing_data","false_positive_reasons","ai_interpretation","human_r'
    'eview_questions"]}],["conflicting_overlap",{"$list":["reject_same_record_id_with_different_norma'
    'lized_at","reject_same_record_id_with_different_source_ids"]}],["deduplication",{"$list":["recor'
    'd_id","normalized_at","source_ids"]}],["ordering","record_id"],["zero_artifacts",{"$list":[]}]]}'
    '],["prohibited_behavior",{"$list":["invoke_upstream_producers","access_providers","invoke_llm","'
    'perform_screening","invoke_scanner","invoke_renderer","use_implicit_clock","generate_calculation'
    '_id","generate_prose","generate_state","generate_missing_data_descriptions","generate_screening_'
    'reasons","synthesize_normalized_inputs","introduce_generic_artifact_registry_or_framework"]}],["'
    'quality_flag_derivation",{"$map":[["artifact_absence","incomplete_input_used"],["non_causes",{"$'
    'list":["candidate_id","state","state_rationale","as_of_date","hypothesis","structure","evidence"'
    ',"falsification_conditions","missing_data","false_positive_reasons","ai_interpretation","human_r'
    'eview_questions"]}],["ordering",{"$list":["decimal_to_float_converted","interpolated","annualize'
    'd","adjusted_input_used","correction_selected","composite_input_used","assumption_applied","inco'
    'mplete_input_used"]}],["upstream_incomplete","included_by_upstream_union"],["upstream_union",{"$'
    'list":["volatility_environment_result","tail_pricing_result","structure_liquidity_result","struc'
    'ture_costs_result","scenario_valuation_result","expiration_payoff_threshold_result","structure_a'
    'ffordability_result"]}]]}],["shared_dependency_identity",{"$map":[["affordability_to_costs",{"$m'
    'ap":[["comparison_dimensions",{"$list":["wrapper_type","record_or_records","lineage"]}],["depend'
    'ent_field","structure_affordability_result"],["supplied_direct_dependency_field","structure_cost'
    's_result"]]}],["expiration_to_costs",{"$map":[["comparison_dimensions",{"$list":["wrapper_type",'
    '"record_or_records","lineage"]}],["dependent_field","expiration_payoff_threshold_result"],["supp'
    'lied_direct_dependency_field","structure_costs_result"]]}],["scenario_to_costs",{"$map":[["compa'
    'rison_dimensions",{"$list":["wrapper_type","record_or_records","lineage"]}],["dependent_field","'
    'scenario_valuation_result"],["supplied_direct_dependency_field","structure_costs_result"]]}],["s'
    'cenario_to_tail",{"$map":[["comparison_dimensions",{"$list":["wrapper_type","record_or_records",'
    '"lineage"]}],["dependent_field","scenario_valuation_result"],["supplied_direct_dependency_field"'
    ',"tail_pricing_result"]]}],["tail_to_volatility",{"$map":[["comparison_dimensions",{"$list":["wr'
    'apper_type","record_or_records","lineage"]}],["dependent_field","tail_pricing_result"],["supplie'
    'd_direct_dependency_field","volatility_environment_result"]]}]]}],["state_completeness",{"$map":'
    '[["data_insufficient",{"$map":[["affordability_requirement",{"$list":[]}],["artifact_cardinality'
    '",{"$map":[["maximum",7],["minimum",0]]}],["incomplete_input_treatment","allowed"],["state_chang'
    'e_prohibited",true]]}],["investigate",{"$map":[["affordability_requirement",{"$list":["affordabl'
    'e","not_affordable"]}],["artifact_cardinality",{"$map":[["maximum",7],["minimum",7]]}],["incompl'
    'ete_input_treatment","reject_any_direct_incomplete_input_used"],["state_change_prohibited",true]'
    ']}],["reject",{"$map":[["affordability_requirement",{"$list":[]}],["artifact_cardinality",{"$map'
    '":[["maximum",7],["minimum",0]]}],["incomplete_input_treatment","allowed"],["state_change_prohib'
    'ited",true]]}],["watch",{"$map":[["affordability_requirement",{"$list":[]}],["artifact_cardinali'
    'ty",{"$map":[["maximum",7],["minimum",0]]}],["incomplete_input_treatment","allowed"],["state_cha'
    'nge_prohibited",true]]}]]}]]}],["caller_inputs",{"$map":[["ai_interpretation",null],["as_of_date'
    '",{"$date":"2030-01-02"}],["candidate_id","candidate-001"],["evidence",{"$list":[{"$map":[["evid'
    'ence_id","evidence-1"],["impact","supports"],["kind","calculated_metric"],["methodology","fixtur'
    'e-v1"],["source","synthetic fixture"],["statement","Synthetic reviewed evidence"]]}]}],["false_p'
    'ositive_reasons",{"$list":["false-positive channel"]}],["falsification_conditions",{"$list":["co'
    'ntrary evidence"]}],["human_review_questions",{"$list":["what changes the conclusion?"]}],["hypo'
    'thesis","testable convexity hypothesis"],["missing_data",{"$list":["artifacts pending"]}],["stat'
    'e","watch"],["state_rationale","caller supplied state"],["structure",{"$map":[["assumed_portfoli'
    'o_value_repr","100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$map":[["contract_mul'
    'tiplier",100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],["stri'
    'ke_float_repr","100.0"],["underlying","SPY"]]}]}],["structure_type","long_call"],["underlying","'
    'SPY"]]}]]}],["candidate_record",{"$map":[["ai_interpretation",null],["as_of_date",{"$date":"2030'
    '-01-02"}],["candidate_id","candidate-001"],["costs",null],["evidence",{"$list":[{"$map":[["evide'
    'nce_id","evidence-1"],["impact","supports"],["kind","calculated_metric"],["methodology","fixture'
    '-v1"],["source","synthetic fixture"],["statement","Synthetic reviewed evidence"]]}]}],["false_po'
    'sitive_reasons",{"$list":["false-positive channel"]}],["falsification_conditions",{"$list":["con'
    'trary evidence"]}],["human_review_questions",{"$list":["what changes the conclusion?"]}],["hypot'
    'hesis","testable convexity hypothesis"],["liquidity",null],["missing_data",{"$list":["artifacts '
    'pending"]}],["scenario_results",{"$list":[]}],["state","watch"],["state_rationale","caller suppl'
    'ied state"],["structure",{"$map":[["assumed_portfolio_value_repr","100000.0"],["expected_holding'
    '_days",14],["legs",{"$list":[{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-0'
    '3-03"}],["option_type","call"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]'
    ']}]}],["structure_type","long_call"],["underlying","SPY"]]}],["tail_pricing_slices",{"$list":[]}'
    '],["volatility_environment",null]]}],["expiration_payoff_threshold_result",null],["output_archit'
    'ecture",{"$map":[["artifact_representation","seven_explicit_optional_reviewed_wrapper_fields"],['
    '"candidate_record_type","CandidateResearchRecord"],["lineage_type","CalculationLineage"],["resul'
    't_type","CandidateResearchRecordAssemblyResult"]]}],["scenario_valuation_result",null],["schema_'
    'version","v0.1"],["structure_affordability_result",null],["structure_costs_result",null],["struc'
    'ture_liquidity_result",null],["tail_pricing_result",null],["volatility_environment_result",null]'
    ']}'
)

COMPLETE_INVESTIGATE_PARAMETERS_JSON = (
    '{"$map":[["assembly_rules",{"$map":[["calculation_id_closure",{"$map":[["direct_dependencies",{"'
    '$map":[["constraint","pairwise_distinct_and_disjoint_from_assembly"],["fields",{"$list":["volati'
    'lity_environment_result","tail_pricing_result","structure_liquidity_result","structure_costs_res'
    'ult","scenario_valuation_result","expiration_payoff_threshold_result","structure_affordability_r'
    'esult"]}]]}],["nested_dependencies",{"$map":[["collection_order","first_occurrence_depth_first_b'
    'y_direct_field_order"],["constraint","disjoint_from_assembly_and_normalized_record_ids"],["roots'
    '",{"$list":["volatility_environment_result","tail_pricing_result","structure_liquidity_result","'
    'structure_costs_result","scenario_valuation_result","expiration_payoff_threshold_result","struct'
    'ure_affordability_result"]}],["traversal","recursive_verified_dependency_disclosures"]]}],["norm'
    'alized_inputs",{"$map":[["constraint","disjoint_from_every_calculation_id"],["identifier","recor'
    'd_id"]]}],["shared_reuse",{"$map":[["allowed",true],["constraint","same_calculation_id_only_for_'
    'byte_identical_complete_calculation"]]}]]}],["candidate_record_mapping",{"$map":[["costs","struc'
    'ture_costs_result.record"],["liquidity","structure_liquidity_result.record"],["scenario_results"'
    ',"scenario_valuation_result.records"],["sidecar_only",{"$list":["expiration_payoff_threshold_res'
    'ult","structure_affordability_result"]}],["tail_pricing_slices","tail_pricing_result.records"],['
    '"volatility_environment","volatility_environment_result.record"]]}],["chronology",{"$map":[["dir'
    'ect_dependencies",{"$map":[["left","assembly.calculated_at"],["operator",">="],["right","each_pr'
    'esent_direct_dependency.lineage.calculated_at"]]}],["nested_dependencies",{"$map":[["left","asse'
    'mbly.calculated_at"],["operator",">="],["right","each_recursive_verified_dependency.lineage.calc'
    'ulated_at"]]}],["normalized_inputs",{"$map":[["left","assembly.calculated_at"],["operator",">="]'
    ',["right","each_normalized_input.normalized_at"]]}],["zero_artifacts",{"$map":[["comparison_coun'
    't",0]]}]]}],["dependency_closure",{"$map":[["expiration_payoff_threshold_result",{"$list":["stru'
    'cture_costs_result"]}],["scenario_valuation_result",{"$list":["volatility_environment_result","t'
    'ail_pricing_result","structure_costs_result"]}],["structure_affordability_result",{"$list":["str'
    'ucture_costs_result"]}],["tail_pricing_result",{"$list":["volatility_environment_result"]}]]}],['
    '"missing_data",{"$map":[["data_insufficient",{"$map":[["assembler_generates_descriptions",false]'
    ',["empty_allowed",false],["nonempty_required_when",{"$list":["always"]}],["semantic_corresponden'
    'ce_to_individual_missing_artifacts_required",false]]}],["investigate",{"$map":[["assembler_gener'
    'ates_descriptions",false],["empty_allowed",true],["nonempty_required_when",{"$list":[]}],["seman'
    'tic_correspondence_to_individual_missing_artifacts_required",false]]}],["reject",{"$map":[["asse'
    'mbler_generates_descriptions",false],["empty_allowed",true],["nonempty_required_when",{"$list":['
    '"any_artifact_absent","any_direct_artifact_has_incomplete_input_used"]}],["semantic_corresponden'
    'ce_to_individual_missing_artifacts_required",false]]}],["watch",{"$map":[["assembler_generates_d'
    'escriptions",false],["empty_allowed",true],["nonempty_required_when",{"$list":["any_artifact_abs'
    'ent","any_direct_artifact_has_incomplete_input_used"]}],["semantic_correspondence_to_individual_'
    'missing_artifacts_required",false]]}]]}],["normalized_input_union",{"$map":[["caller_values",{"$'
    'list":["candidate_id","state","state_rationale","as_of_date","hypothesis","structure","evidence"'
    ',"falsification_conditions","missing_data","false_positive_reasons","ai_interpretation","human_r'
    'eview_questions"]}],["conflicting_overlap",{"$list":["reject_same_record_id_with_different_norma'
    'lized_at","reject_same_record_id_with_different_source_ids"]}],["deduplication",{"$list":["recor'
    'd_id","normalized_at","source_ids"]}],["ordering","record_id"],["zero_artifacts",{"$list":[]}]]}'
    '],["prohibited_behavior",{"$list":["invoke_upstream_producers","access_providers","invoke_llm","'
    'perform_screening","invoke_scanner","invoke_renderer","use_implicit_clock","generate_calculation'
    '_id","generate_prose","generate_state","generate_missing_data_descriptions","generate_screening_'
    'reasons","synthesize_normalized_inputs","introduce_generic_artifact_registry_or_framework"]}],["'
    'quality_flag_derivation",{"$map":[["artifact_absence","incomplete_input_used"],["non_causes",{"$'
    'list":["candidate_id","state","state_rationale","as_of_date","hypothesis","structure","evidence"'
    ',"falsification_conditions","missing_data","false_positive_reasons","ai_interpretation","human_r'
    'eview_questions"]}],["ordering",{"$list":["decimal_to_float_converted","interpolated","annualize'
    'd","adjusted_input_used","correction_selected","composite_input_used","assumption_applied","inco'
    'mplete_input_used"]}],["upstream_incomplete","included_by_upstream_union"],["upstream_union",{"$'
    'list":["volatility_environment_result","tail_pricing_result","structure_liquidity_result","struc'
    'ture_costs_result","scenario_valuation_result","expiration_payoff_threshold_result","structure_a'
    'ffordability_result"]}]]}],["shared_dependency_identity",{"$map":[["affordability_to_costs",{"$m'
    'ap":[["comparison_dimensions",{"$list":["wrapper_type","record_or_records","lineage"]}],["depend'
    'ent_field","structure_affordability_result"],["supplied_direct_dependency_field","structure_cost'
    's_result"]]}],["expiration_to_costs",{"$map":[["comparison_dimensions",{"$list":["wrapper_type",'
    '"record_or_records","lineage"]}],["dependent_field","expiration_payoff_threshold_result"],["supp'
    'lied_direct_dependency_field","structure_costs_result"]]}],["scenario_to_costs",{"$map":[["compa'
    'rison_dimensions",{"$list":["wrapper_type","record_or_records","lineage"]}],["dependent_field","'
    'scenario_valuation_result"],["supplied_direct_dependency_field","structure_costs_result"]]}],["s'
    'cenario_to_tail",{"$map":[["comparison_dimensions",{"$list":["wrapper_type","record_or_records",'
    '"lineage"]}],["dependent_field","scenario_valuation_result"],["supplied_direct_dependency_field"'
    ',"tail_pricing_result"]]}],["tail_to_volatility",{"$map":[["comparison_dimensions",{"$list":["wr'
    'apper_type","record_or_records","lineage"]}],["dependent_field","tail_pricing_result"],["supplie'
    'd_direct_dependency_field","volatility_environment_result"]]}]]}],["state_completeness",{"$map":'
    '[["data_insufficient",{"$map":[["affordability_requirement",{"$list":[]}],["artifact_cardinality'
    '",{"$map":[["maximum",7],["minimum",0]]}],["incomplete_input_treatment","allowed"],["state_chang'
    'e_prohibited",true]]}],["investigate",{"$map":[["affordability_requirement",{"$list":["affordabl'
    'e","not_affordable"]}],["artifact_cardinality",{"$map":[["maximum",7],["minimum",7]]}],["incompl'
    'ete_input_treatment","reject_any_direct_incomplete_input_used"],["state_change_prohibited",true]'
    ']}],["reject",{"$map":[["affordability_requirement",{"$list":[]}],["artifact_cardinality",{"$map'
    '":[["maximum",7],["minimum",0]]}],["incomplete_input_treatment","allowed"],["state_change_prohib'
    'ited",true]]}],["watch",{"$map":[["affordability_requirement",{"$list":[]}],["artifact_cardinali'
    'ty",{"$map":[["maximum",7],["minimum",0]]}],["incomplete_input_treatment","allowed"],["state_cha'
    'nge_prohibited",true]]}]]}]]}],["caller_inputs",{"$map":[["ai_interpretation",null],["as_of_date'
    '",{"$date":"2030-01-02"}],["candidate_id","candidate-complete"],["evidence",{"$list":[{"$map":[['
    '"evidence_id","evidence-1"],["impact","supports"],["kind","calculated_metric"],["methodology","f'
    'ixture-v1"],["source","synthetic fixture"],["statement","Synthetic reviewed evidence"]]}]}],["fa'
    'lse_positive_reasons",{"$list":["false-positive channel"]}],["falsification_conditions",{"$list"'
    ':["contrary evidence"]}],["human_review_questions",{"$list":["what changes the conclusion?"]}],['
    '"hypothesis","testable convexity hypothesis"],["missing_data",{"$list":[]}],["state","investigat'
    'e"],["state_rationale","reviewed complete artifacts"],["structure",{"$map":[["assumed_portfolio_'
    'value_repr","100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$map":[["contract_multi'
    'plier",100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],["strike'
    '_float_repr","100.0"],["underlying","SPY"]]}]}],["structure_type","long_call"],["underlying","SP'
    'Y"]]}]]}],["candidate_record",{"$map":[["ai_interpretation",null],["as_of_date",{"$date":"2030-0'
    '1-02"}],["candidate_id","candidate-complete"],["costs",{"$map":[["as_of_date",{"$date":"2030-01-'
    '02"}],["commissions_and_fees_float_repr","1.25"],["estimated_spread_cost_float_repr","20.0"],["g'
    'amma_float_repr","2.0"],["greeks_methodology","model=Synthetic Black-Scholes;model_version=fixtu'
    're-v1;rate_input=Synthetic USD curve input;dividend_input=Synthetic dividend input;theta_day_bas'
    'is=Provider calendar-day convention;unit_convention=Contract-defined canonical units"],["quoted_'
    'mid_premium_float_repr","120.0"],["repeated_bet_count",1],["structure",{"$map":[["assumed_portfo'
    'lio_value_repr","100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$map":[["contract_m'
    'ultiplier",100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],["st'
    'rike_float_repr","100.0"],["underlying","SPY"]]}]}],["structure_type","long_call"],["underlying"'
    ',"SPY"]]}],["theta_per_day_float_repr","-10.0"],["underlying_price_float_repr","100.0"]]}],["evi'
    'dence",{"$list":[{"$map":[["evidence_id","evidence-1"],["impact","supports"],["kind","calculated'
    '_metric"],["methodology","fixture-v1"],["source","synthetic fixture"],["statement","Synthetic re'
    'viewed evidence"]]}]}],["false_positive_reasons",{"$list":["false-positive channel"]}],["falsifi'
    'cation_conditions",{"$list":["contrary evidence"]}],["human_review_questions",{"$list":["what ch'
    'anges the conclusion?"]}],["hypothesis","testable convexity hypothesis"],["liquidity",{"$map":[['
    '"as_of_date",{"$date":"2030-01-02"}],["minimum_leg_daily_volume",40],["minimum_leg_open_interest'
    '",80],["quote_methodology","exact selected option quotes scaled by quantity and contract multipl'
    'ier"],["quoted_ask_value_float_repr","140.0"],["quoted_bid_value_float_repr","100.0"],["structur'
    'e",{"$map":[["assumed_portfolio_value_repr","100000.0"],["expected_holding_days",14],["legs",{"$'
    'list":[{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-03-03"}],["option_type"'
    ',"call"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]}]}],["structure_type'
    '","long_call"],["underlying","SPY"]]}]]}],["missing_data",{"$list":[]}],["scenario_results",{"$l'
    'ist":[{"$map":[["as_of_date",{"$date":"2030-01-02"}],["base_underlying_price_float_repr","100.0"'
    '],["entry_cost_basis_float_repr","141.25"],["estimated_exit_cost_float_repr","2.5"],["estimated_'
    'position_value_float_repr","250.0"],["leg_volatility_inputs",{"$list":[{"$map":[["base_iv_float_'
    'repr","0.2"],["leg",{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-03-03"}],['
    '"option_type","call"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]}]]}]}],'
    '["pricing_methodology","{\\"$map\\":[[\\"base_iv_source\\",\\"ScenarioPricing_v0.1_actual_structure_l'
    'eg_iv_evidence\\"],[\\"base_underlying_source\\",\\"StructureCosts_v0.2_underlying_price_exact\\"],[\\'
    '"entry_cost_rule\\",\\"StructureCosts_v0.2_stable_total_entry_cost_float\\"],[\\"exit_cost_rule\\",{\\'
    '"$map\\":[[\\"methodology\\",\\"explicit_fixture_exit_cost_v0.1\\"],[\\"source\\",\\"explicit_scenario_s'
    'pecific_decimal_assumption\\"]]}],[\\"expiration_rule\\",{\\"$map\\":[[\\"active\\",false],[\\"call_form'
    'ula\\",\\"max(shocked_underlying-strike,0)*quantity*multiplier\\"],[\\"external_expiration_value\\",\\'
    '"prohibited\\"],[\\"iv_effect\\",\\"none_base_leg_ivs_retained_for_audit\\"],[\\"put_formula\\",\\"max(s'
    'trike-shocked_underlying,0)*quantity*multiplier\\"]]}],[\\"float_conversion_rule\\",\\"convert_base_'
    'iv_gross_and_exit_cost_once_to_finite_float\\"],[\\"limitations\\",\\"Internal consistency is valida'
    'ted; self-consistent fabricated dependency artifacts are not cryptographically authenticated.\\"]'
    ',[\\"nonexpiration_rule\\",{\\"$map\\":[[\\"active\\",true],[\\"rule\\",\\"consume_authoritative_gross_va'
    'lue_without_repricing\\"]]}],[\\"provider_disclosure\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-p'
    'ricing-calculation-001\\"],[\\"dividend_methodology\\",{\\"$map\\":[[\\"dividend_coverage_end_date\\",{'
    '\\"$date\\":\\"2030-03-15\\"}],[\\"dividend_coverage_start_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"divi'
    'dend_source\\",\\"explicit_zero_dividend_assumption\\"],[\\"dividend_treatment\\",\\"explicit_zero_div'
    'idend_assumption\\"],[\\"explicit_zero_dividend_assumption\\",true]]}],[\\"interpolation_treatment\\"'
    ',\\"none\\"],[\\"numerical_boundary\\",\\"provider option values; local validation only\\"],[\\"payload'
    '_sha256\\",\\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\\"],[\\"position_scal'
    'ing_rule\\",\\"per_underlying_unit_value_times_quantity_times_contract_multiplier\\"],[\\"pricing_mo'
    'del_name\\",\\"Synthetic disclosed option model\\"],[\\"pricing_model_version\\",\\"model-v2\\"],[\\"pro'
    'ducer_calculated_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:05.000000Z\\"}],[\\"producer_name\\",\\"Synt'
    'hetic Scenario Provider\\"],[\\"producer_version\\",\\"provider-v3\\"],[\\"rate_methodology\\",{\\"$map\\'
    '":[[\\"rate_compounding_conversion\\",\\"continuous equivalent\\"],[\\"rate_currency\\",\\"USD\\"],[\\"ra'
    'te_curve_identity\\",\\"synthetic-usd-curve-20300102\\"],[\\"rate_day_count_convention\\",\\"actual_36'
    '5\\"],[\\"rate_effective_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"rate_interpolation\\",\\"none\\"],[\\"r'
    'ate_remaining_tenor_treatment\\",\\"remaining calendar tenor\\"],[\\"rate_source\\",\\"Synthetic USD c'
    'urve\\"]]}],[\\"remaining_time_rule\\",\\"expiration_minus_valuation_date_calendar_days\\"],[\\"reques'
    't_id\\",\\"scenario-request-001\\"],[\\"settlement_treatment\\",\\"physical settlement at declared ter'
    'ms\\"],[\\"skew_treatment\\",\\"preserve leg-level base differences\\"],[\\"status\\",\\"active_authorit'
    'ative_provider_calculated\\"],[\\"surface_treatment\\",\\"actual leg IV parallel shock\\"],[\\"term_tr'
    'eatment\\",\\"remaining tenor per scenario\\"]]}],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forward'
    '\\",0],[\\"iv_change\\",{\\"$decimal\\":\\"0.0\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.0\\"}],[\\"val'
    'uation_time\\",\\"immediate\\"]]}],[\\"scenario_pricing_dependency\\",{\\"$map\\":[[\\"calculation_id\\",'
    '\\"scenario-pricing-calculation-001\\"],[\\"identity\\",{\\"$list\\":[\\"nonexpiration_scenario_pricing'
    '\\",\\"authoritative-provider-option-scenario-pricing-evidence\\",\\"v0.1\\"]}]]}],[\\"schema_version\\'
    '",\\"v0.1\\"],[\\"structure_costs_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-valuation-'
    'costs\\"],[\\"identity\\",{\\"$list\\":[\\"structure_costs\\",\\"exact-structure-costs\\",\\"v0.2\\"]}]]}],'
    '[\\"tail_pricing_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"calculation-3c7e\\"],[\\"identity\\",'
    '{\\"$list\\":[\\"tail_pricing\\",\\"nearest-observed-delta-wing-tail-relative-pricing\\",\\"v0.2\\"]}],['
    '\\"use\\",\\"context_only\\"]]}],[\\"valuation_source\\",\\"authoritative_provider_nonexpiration\\"]]}"]'
    ',["scenario",{"$map":[["days_forward",0],["iv_change_float_repr","0.0"],["underlying_move_float_'
    'repr","0.0"],["valuation_time","immediate"]]}],["structure",{"$map":[["assumed_portfolio_value_r'
    'epr","100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$map":[["contract_multiplier",'
    '100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],["strike_float_'
    'repr","100.0"],["underlying","SPY"]]}]}],["structure_type","long_call"],["underlying","SPY"]]}],'
    '["valuation_date",{"$date":"2030-01-02"}]]},{"$map":[["as_of_date",{"$date":"2030-01-02"}],["bas'
    'e_underlying_price_float_repr","100.0"],["entry_cost_basis_float_repr","141.25"],["estimated_exi'
    't_cost_float_repr","2.5"],["estimated_position_value_float_repr","300.0"],["leg_volatility_input'
    's",{"$list":[{"$map":[["base_iv_float_repr","0.2"],["leg",{"$map":[["contract_multiplier",100],['
    '"expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],["strike_float_repr",'
    '"100.0"],["underlying","SPY"]]}]]}]}],["pricing_methodology","{\\"$map\\":[[\\"base_iv_source\\",\\"S'
    'cenarioPricing_v0.1_actual_structure_leg_iv_evidence\\"],[\\"base_underlying_source\\",\\"StructureC'
    'osts_v0.2_underlying_price_exact\\"],[\\"entry_cost_rule\\",\\"StructureCosts_v0.2_stable_total_entr'
    'y_cost_float\\"],[\\"exit_cost_rule\\",{\\"$map\\":[[\\"methodology\\",\\"explicit_fixture_exit_cost_v0.'
    '1\\"],[\\"source\\",\\"explicit_scenario_specific_decimal_assumption\\"]]}],[\\"expiration_rule\\",{\\"$'
    'map\\":[[\\"active\\",false],[\\"call_formula\\",\\"max(shocked_underlying-strike,0)*quantity*multipli'
    'er\\"],[\\"external_expiration_value\\",\\"prohibited\\"],[\\"iv_effect\\",\\"none_base_leg_ivs_retained'
    '_for_audit\\"],[\\"put_formula\\",\\"max(strike-shocked_underlying,0)*quantity*multiplier\\"]]}],[\\"f'
    'loat_conversion_rule\\",\\"convert_base_iv_gross_and_exit_cost_once_to_finite_float\\"],[\\"limitati'
    'ons\\",\\"Internal consistency is validated; self-consistent fabricated dependency artifacts are n'
    'ot cryptographically authenticated.\\"],[\\"nonexpiration_rule\\",{\\"$map\\":[[\\"active\\",true],[\\"r'
    'ule\\",\\"consume_authoritative_gross_value_without_repricing\\"]]}],[\\"provider_disclosure\\",{\\"$m'
    'ap\\":[[\\"calculation_id\\",\\"scenario-pricing-calculation-001\\"],[\\"dividend_methodology\\",{\\"$ma'
    'p\\":[[\\"dividend_coverage_end_date\\",{\\"$date\\":\\"2030-03-15\\"}],[\\"dividend_coverage_start_date'
    '\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"dividend_source\\",\\"explicit_zero_dividend_assumption\\"],[\\"di'
    'vidend_treatment\\",\\"explicit_zero_dividend_assumption\\"],[\\"explicit_zero_dividend_assumption\\"'
    ',true]]}],[\\"interpolation_treatment\\",\\"none\\"],[\\"numerical_boundary\\",\\"provider option value'
    's; local validation only\\"],[\\"payload_sha256\\",\\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
    'bbbbbbbbbbbbbbbbbb\\"],[\\"position_scaling_rule\\",\\"per_underlying_unit_value_times_quantity_time'
    's_contract_multiplier\\"],[\\"pricing_model_name\\",\\"Synthetic disclosed option model\\"],[\\"pricin'
    'g_model_version\\",\\"model-v2\\"],[\\"producer_calculated_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:05'
    '.000000Z\\"}],[\\"producer_name\\",\\"Synthetic Scenario Provider\\"],[\\"producer_version\\",\\"provide'
    'r-v3\\"],[\\"rate_methodology\\",{\\"$map\\":[[\\"rate_compounding_conversion\\",\\"continuous equivalen'
    't\\"],[\\"rate_currency\\",\\"USD\\"],[\\"rate_curve_identity\\",\\"synthetic-usd-curve-20300102\\"],[\\"r'
    'ate_day_count_convention\\",\\"actual_365\\"],[\\"rate_effective_date\\",{\\"$date\\":\\"2030-01-02\\"}],'
    '[\\"rate_interpolation\\",\\"none\\"],[\\"rate_remaining_tenor_treatment\\",\\"remaining calendar tenor'
    '\\"],[\\"rate_source\\",\\"Synthetic USD curve\\"]]}],[\\"remaining_time_rule\\",\\"expiration_minus_val'
    'uation_date_calendar_days\\"],[\\"request_id\\",\\"scenario-request-001\\"],[\\"settlement_treatment\\"'
    ',\\"physical settlement at declared terms\\"],[\\"skew_treatment\\",\\"preserve leg-level base differ'
    'ences\\"],[\\"status\\",\\"active_authoritative_provider_calculated\\"],[\\"surface_treatment\\",\\"actu'
    'al leg IV parallel shock\\"],[\\"term_treatment\\",\\"remaining tenor per scenario\\"]]}],[\\"scenario'
    '_identity\\",{\\"$map\\":[[\\"days_forward\\",7],[\\"iv_change\\",{\\"$decimal\\":\\"0.2\\"}],[\\"underlying'
    '_move\\",{\\"$decimal\\":\\"0.1\\"}],[\\"valuation_time\\",\\"days_forward\\"]]}],[\\"scenario_pricing_dep'
    'endency\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-pricing-calculation-001\\"],[\\"identity\\",{\\"'
    '$list\\":[\\"nonexpiration_scenario_pricing\\",\\"authoritative-provider-option-scenario-pricing-evi'
    'dence\\",\\"v0.1\\"]}]]}],[\\"schema_version\\",\\"v0.1\\"],[\\"structure_costs_dependency\\",{\\"$map\\":['
    '[\\"calculation_id\\",\\"scenario-valuation-costs\\"],[\\"identity\\",{\\"$list\\":[\\"structure_costs\\",'
    '\\"exact-structure-costs\\",\\"v0.2\\"]}]]}],[\\"tail_pricing_dependency\\",{\\"$map\\":[[\\"calculation_'
    'id\\",\\"calculation-3c7e\\"],[\\"identity\\",{\\"$list\\":[\\"tail_pricing\\",\\"nearest-observed-delta-w'
    'ing-tail-relative-pricing\\",\\"v0.2\\"]}],[\\"use\\",\\"context_only\\"]]}],[\\"valuation_source\\",\\"au'
    'thoritative_provider_nonexpiration\\"]]}"],["scenario",{"$map":[["days_forward",7],["iv_change_fl'
    'oat_repr","0.2"],["underlying_move_float_repr","0.1"],["valuation_time","days_forward"]]}],["str'
    'ucture",{"$map":[["assumed_portfolio_value_repr","100000.0"],["expected_holding_days",14],["legs'
    '",{"$list":[{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-03-03"}],["option_'
    'type","call"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]}]}],["structure'
    '_type","long_call"],["underlying","SPY"]]}],["valuation_date",{"$date":"2030-01-09"}]]},{"$map":'
    '[["as_of_date",{"$date":"2030-01-02"}],["base_underlying_price_float_repr","100.0"],["entry_cost'
    '_basis_float_repr","141.25"],["estimated_exit_cost_float_repr","2.5"],["estimated_position_value'
    '_float_repr","200.0"],["leg_volatility_inputs",{"$list":[{"$map":[["base_iv_float_repr","0.2"],['
    '"leg",{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-03-03"}],["option_type",'
    '"call"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]}]]}]}],["pricing_meth'
    'odology","{\\"$map\\":[[\\"base_iv_source\\",\\"ScenarioPricing_v0.1_actual_structure_leg_iv_evidence'
    '\\"],[\\"base_underlying_source\\",\\"StructureCosts_v0.2_underlying_price_exact\\"],[\\"entry_cost_ru'
    'le\\",\\"StructureCosts_v0.2_stable_total_entry_cost_float\\"],[\\"exit_cost_rule\\",{\\"$map\\":[[\\"me'
    'thodology\\",\\"explicit_fixture_exit_cost_v0.1\\"],[\\"source\\",\\"explicit_scenario_specific_decima'
    'l_assumption\\"]]}],[\\"expiration_rule\\",{\\"$map\\":[[\\"active\\",false],[\\"call_formula\\",\\"max(sh'
    'ocked_underlying-strike,0)*quantity*multiplier\\"],[\\"external_expiration_value\\",\\"prohibited\\"]'
    ',[\\"iv_effect\\",\\"none_base_leg_ivs_retained_for_audit\\"],[\\"put_formula\\",\\"max(strike-shocked_'
    'underlying,0)*quantity*multiplier\\"]]}],[\\"float_conversion_rule\\",\\"convert_base_iv_gross_and_e'
    'xit_cost_once_to_finite_float\\"],[\\"limitations\\",\\"Internal consistency is validated; self-cons'
    'istent fabricated dependency artifacts are not cryptographically authenticated.\\"],[\\"nonexpirat'
    'ion_rule\\",{\\"$map\\":[[\\"active\\",true],[\\"rule\\",\\"consume_authoritative_gross_value_without_re'
    'pricing\\"]]}],[\\"provider_disclosure\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-pricing-calcula'
    'tion-001\\"],[\\"dividend_methodology\\",{\\"$map\\":[[\\"dividend_coverage_end_date\\",{\\"$date\\":\\"20'
    '30-03-15\\"}],[\\"dividend_coverage_start_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"dividend_source\\",'
    '\\"explicit_zero_dividend_assumption\\"],[\\"dividend_treatment\\",\\"explicit_zero_dividend_assumpti'
    'on\\"],[\\"explicit_zero_dividend_assumption\\",true]]}],[\\"interpolation_treatment\\",\\"none\\"],[\\"'
    'numerical_boundary\\",\\"provider option values; local validation only\\"],[\\"payload_sha256\\",\\"bb'
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\\"],[\\"position_scaling_rule\\",\\"p'
    'er_underlying_unit_value_times_quantity_times_contract_multiplier\\"],[\\"pricing_model_name\\",\\"S'
    'ynthetic disclosed option model\\"],[\\"pricing_model_version\\",\\"model-v2\\"],[\\"producer_calculat'
    'ed_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:05.000000Z\\"}],[\\"producer_name\\",\\"Synthetic Scenario'
    ' Provider\\"],[\\"producer_version\\",\\"provider-v3\\"],[\\"rate_methodology\\",{\\"$map\\":[[\\"rate_com'
    'pounding_conversion\\",\\"continuous equivalent\\"],[\\"rate_currency\\",\\"USD\\"],[\\"rate_curve_ident'
    'ity\\",\\"synthetic-usd-curve-20300102\\"],[\\"rate_day_count_convention\\",\\"actual_365\\"],[\\"rate_e'
    'ffective_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"rate_interpolation\\",\\"none\\"],[\\"rate_remaining_'
    'tenor_treatment\\",\\"remaining calendar tenor\\"],[\\"rate_source\\",\\"Synthetic USD curve\\"]]}],[\\"'
    'remaining_time_rule\\",\\"expiration_minus_valuation_date_calendar_days\\"],[\\"request_id\\",\\"scena'
    'rio-request-001\\"],[\\"settlement_treatment\\",\\"physical settlement at declared terms\\"],[\\"skew_'
    'treatment\\",\\"preserve leg-level base differences\\"],[\\"status\\",\\"active_authoritative_provider'
    '_calculated\\"],[\\"surface_treatment\\",\\"actual leg IV parallel shock\\"],[\\"term_treatment\\",\\"re'
    'maining tenor per scenario\\"]]}],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forward\\",0],[\\"iv_ch'
    'ange\\",{\\"$decimal\\":\\"-0.1\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"-0.05\\"}],[\\"valuation_time'
    '\\",\\"holding_horizon\\"]]}],[\\"scenario_pricing_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"sce'
    'nario-pricing-calculation-001\\"],[\\"identity\\",{\\"$list\\":[\\"nonexpiration_scenario_pricing\\",\\"'
    'authoritative-provider-option-scenario-pricing-evidence\\",\\"v0.1\\"]}]]}],[\\"schema_version\\",\\"v'
    '0.1\\"],[\\"structure_costs_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-valuation-costs'
    '\\"],[\\"identity\\",{\\"$list\\":[\\"structure_costs\\",\\"exact-structure-costs\\",\\"v0.2\\"]}]]}],[\\"ta'
    'il_pricing_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"calculation-3c7e\\"],[\\"identity\\",{\\"$l'
    'ist\\":[\\"tail_pricing\\",\\"nearest-observed-delta-wing-tail-relative-pricing\\",\\"v0.2\\"]}],[\\"use'
    '\\",\\"context_only\\"]]}],[\\"valuation_source\\",\\"authoritative_provider_nonexpiration\\"]]}"],["sc'
    'enario",{"$map":[["days_forward",0],["iv_change_float_repr","-0.1"],["underlying_move_float_repr'
    '","-0.05"],["valuation_time","holding_horizon"]]}],["structure",{"$map":[["assumed_portfolio_val'
    'ue_repr","100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$map":[["contract_multipli'
    'er",100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],["strike_fl'
    'oat_repr","100.0"],["underlying","SPY"]]}]}],["structure_type","long_call"],["underlying","SPY"]'
    ']}],["valuation_date",{"$date":"2030-01-16"}]]},{"$map":[["as_of_date",{"$date":"2030-01-02"}],['
    '"base_underlying_price_float_repr","100.0"],["entry_cost_basis_float_repr","141.25"],["estimated'
    '_exit_cost_float_repr","0.0"],["estimated_position_value_float_repr","1000.0"],["leg_volatility_'
    'inputs",{"$list":[{"$map":[["base_iv_float_repr","0.2"],["leg",{"$map":[["contract_multiplier",1'
    '00],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],["strike_float_r'
    'epr","100.0"],["underlying","SPY"]]}]]}]}],["pricing_methodology","{\\"$map\\":[[\\"base_iv_source\\'
    '",\\"ScenarioPricing_v0.1_actual_structure_leg_iv_evidence\\"],[\\"base_underlying_source\\",\\"Struc'
    'tureCosts_v0.2_underlying_price_exact\\"],[\\"entry_cost_rule\\",\\"StructureCosts_v0.2_stable_total'
    '_entry_cost_float\\"],[\\"exit_cost_rule\\",{\\"$map\\":[[\\"methodology\\",\\"explicit_fixture_exit_cos'
    't_v0.1\\"],[\\"source\\",\\"explicit_scenario_specific_decimal_assumption\\"]]}],[\\"expiration_rule\\"'
    ',{\\"$map\\":[[\\"active\\",true],[\\"call_formula\\",\\"max(shocked_underlying-strike,0)*quantity*mult'
    'iplier\\"],[\\"external_expiration_value\\",\\"prohibited\\"],[\\"iv_effect\\",\\"none_base_leg_ivs_reta'
    'ined_for_audit\\"],[\\"put_formula\\",\\"max(strike-shocked_underlying,0)*quantity*multiplier\\"]]}],'
    '[\\"float_conversion_rule\\",\\"convert_base_iv_gross_and_exit_cost_once_to_finite_float\\"],[\\"limi'
    'tations\\",\\"Internal consistency is validated; self-consistent fabricated dependency artifacts a'
    're not cryptographically authenticated.\\"],[\\"nonexpiration_rule\\",{\\"$map\\":[[\\"active\\",false]'
    ',[\\"rule\\",\\"consume_authoritative_gross_value_without_repricing\\"]]}],[\\"provider_disclosure\\",'
    '{\\"$map\\":[[\\"external_expiration_value\\",\\"prohibited\\"],[\\"status\\",\\"inactive_for_expiration\\'
    '"]]}],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forward\\",0],[\\"iv_change\\",{\\"$decimal\\":\\"0.5\\'
    '"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.1\\"}],[\\"valuation_time\\",\\"expiration\\"]]}],[\\"scena'
    'rio_pricing_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-pricing-calculation-001\\"],[\\'
    '"identity\\",{\\"$list\\":[\\"nonexpiration_scenario_pricing\\",\\"authoritative-provider-option-scena'
    'rio-pricing-evidence\\",\\"v0.1\\"]}]]}],[\\"schema_version\\",\\"v0.1\\"],[\\"structure_costs_dependenc'
    'y\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-valuation-costs\\"],[\\"identity\\",{\\"$list\\":[\\"str'
    'ucture_costs\\",\\"exact-structure-costs\\",\\"v0.2\\"]}]]}],[\\"tail_pricing_dependency\\",{\\"$map\\":['
    '[\\"calculation_id\\",\\"calculation-3c7e\\"],[\\"identity\\",{\\"$list\\":[\\"tail_pricing\\",\\"nearest-o'
    'bserved-delta-wing-tail-relative-pricing\\",\\"v0.2\\"]}],[\\"use\\",\\"context_only\\"]]}],[\\"valuatio'
    'n_source\\",\\"terminal_intrinsic_expiration\\"]]}"],["scenario",{"$map":[["days_forward",0],["iv_c'
    'hange_float_repr","0.5"],["underlying_move_float_repr","0.1"],["valuation_time","expiration"]]}]'
    ',["structure",{"$map":[["assumed_portfolio_value_repr","100000.0"],["expected_holding_days",14],'
    '["legs",{"$list":[{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-03-03"}],["o'
    'ption_type","call"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]}]}],["str'
    'ucture_type","long_call"],["underlying","SPY"]]}],["valuation_date",{"$date":"2030-03-03"}]]}]}]'
    ',["state","investigate"],["state_rationale","reviewed complete artifacts"],["structure",{"$map":'
    '[["assumed_portfolio_value_repr","100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$m'
    'ap":[["contract_multiplier",100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["'
    'quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]}]}],["structure_type","long_cal'
    'l"],["underlying","SPY"]]}],["tail_pricing_slices",{"$list":[{"$map":[["as_of_date",{"$date":"20'
    '30-01-02"}],["atm_iv_float_repr","0.3"],["call_10_delta_iv_float_repr","0.26"],["call_25_delta_i'
    'v_float_repr","0.28"],["delta_methodology","{\\"$map\\":[[\\"delta_basis\\",\\"spot\\"],[\\"interpolati'
    'on_methodology\\",\\"none\\"],[\\"model_provider_methodology\\",\\"Synthetic Black-Scholes provider de'
    'lta\\"],[\\"premium_adjustment\\",\\"unadjusted\\"],[\\"signed_delta_convention\\",\\"call_positive_put_'
    'negative\\"],[\\"target_selection_methodology\\",\\"nearest_observed_signed_delta\\"]]}"],["expiratio'
    'n",{"$date":"2030-02-01"}],["put_10_delta_iv_float_repr","0.42"],["put_25_delta_iv_float_repr","'
    '0.36"],["skew_history_lookback_observations",3],["skew_percentile_float_repr","0.666666666666666'
    '6"],["underlying","SPY"]]},{"$map":[["as_of_date",{"$date":"2030-01-02"}],["atm_iv_float_repr","'
    '0.4"],["call_10_delta_iv_float_repr","0.36"],["call_25_delta_iv_float_repr","0.38"],["delta_meth'
    'odology","{\\"$map\\":[[\\"delta_basis\\",\\"spot\\"],[\\"interpolation_methodology\\",\\"none\\"],[\\"mode'
    'l_provider_methodology\\",\\"Synthetic Black-Scholes provider delta\\"],[\\"premium_adjustment\\",\\"u'
    'nadjusted\\"],[\\"signed_delta_convention\\",\\"call_positive_put_negative\\"],[\\"target_selection_me'
    'thodology\\",\\"nearest_observed_signed_delta\\"]]}"],["expiration",{"$date":"2030-03-03"}],["put_1'
    '0_delta_iv_float_repr","0.52"],["put_25_delta_iv_float_repr","0.46"],["skew_history_lookback_obs'
    'ervations",3],["skew_percentile_float_repr","0.6666666666666666"],["underlying","SPY"]]}]}],["vo'
    'latility_environment",{"$map":[["as_of_date",{"$date":"2030-01-02"}],["historical_median_atm_iv_'
    'float_repr","0.21"],["iv_history_lookback_observations",3],["iv_percentile_float_repr","1.0"],["'
    'matched_realized_volatility_float_repr","0.3328756933888896"],["matched_realized_window_days",30'
    '],["reference_tenor_days",30],["term_structure",{"$list":[{"$map":[["atm_iv_float_repr","0.3"],['
    '"tenor_days",30]]},{"$map":[["atm_iv_float_repr","0.4"],["tenor_days",60]]}]}],["underlying","SP'
    'Y"]]}]]}],["expiration_payoff_threshold_result",{"$map":[["lineage",{"$map":[["calculated_at",{"'
    '$datetime":"2030-01-02T15:30:15.000000Z"}],["calculation_id","expiration-thresholds-shared"],["c'
    'alculation_type","expiration_payoff_thresholds"],["inputs",{"$list":[{"$map":[["normalized_at",{'
    '"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","cost-call-contract-reference"],["sourc'
    'e_ids",{"$list":["cost-call-contract-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datet'
    'ime":"2030-01-02T15:30:00.000002Z"}],["record_id","cost-call-greeks"],["source_ids",{"$list":["c'
    'ost-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.00000'
    '2Z"}],["record_id","cost-call-quote"],["source_ids",{"$list":["cost-call-quote-source-0"]}]]},{"'
    '$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","cost-underlyi'
    'ng-quote"],["source_ids",{"$list":["cost-underlying-quote-source-0"]}]]}]}],["methodology_id","c'
    'losed-form-terminal-intrinsic-position-value-multiples"],["methodology_version","v0.1"],["parame'
    'ters_json","{\\"$map\\":[[\\"calculation_values\\",{\\"$list\\":[{\\"$map\\":[[\\"absolute_move_from_base'
    '\\",{\\"$map\\":[[\\"denominator\\",80],[\\"numerator\\",113]]}],[\\"payoff_distance\\",{\\"$map\\":[[\\"den'
    'ominator\\",80],[\\"numerator\\",113]]}],[\\"position_scale\\",{\\"$map\\":[[\\"contract_multiplier\\",10'
    '0],[\\"quantity\\",1],[\\"underlying_units\\",100]]}],[\\"position_value_multiple\\",1],[\\"relative_mo'
    've_from_base\\",{\\"$map\\":[[\\"denominator\\",8000],[\\"numerator\\",113]]}],[\\"side\\",\\"upside\\"],[\\'
    '"status\\",\\"available\\"],[\\"strike_exact\\",{\\"$map\\":[[\\"denominator\\",1],[\\"numerator\\",100]]}]'
    ',[\\"target_position_value\\",{\\"$map\\":[[\\"denominator\\",4],[\\"numerator\\",565]]}],[\\"threshold_u'
    'nderlying_price\\",{\\"$map\\":[[\\"denominator\\",80],[\\"numerator\\",8113]]}],[\\"unconstrained_thres'
    'hold_underlying_price\\",{\\"$map\\":[[\\"denominator\\",80],[\\"numerator\\",8113]]}]]},{\\"$map\\":[[\\"'
    'absolute_move_from_base\\",{\\"$map\\":[[\\"denominator\\",40],[\\"numerator\\",113]]}],[\\"payoff_dista'
    'nce\\",{\\"$map\\":[[\\"denominator\\",40],[\\"numerator\\",113]]}],[\\"position_scale\\",{\\"$map\\":[[\\"c'
    'ontract_multiplier\\",100],[\\"quantity\\",1],[\\"underlying_units\\",100]]}],[\\"position_value_multi'
    'ple\\",2],[\\"relative_move_from_base\\",{\\"$map\\":[[\\"denominator\\",4000],[\\"numerator\\",113]]}],['
    '\\"side\\",\\"upside\\"],[\\"status\\",\\"available\\"],[\\"strike_exact\\",{\\"$map\\":[[\\"denominator\\",1]'
    ',[\\"numerator\\",100]]}],[\\"target_position_value\\",{\\"$map\\":[[\\"denominator\\",2],[\\"numerator\\"'
    ',565]]}],[\\"threshold_underlying_price\\",{\\"$map\\":[[\\"denominator\\",40],[\\"numerator\\",4113]]}]'
    ',[\\"unconstrained_threshold_underlying_price\\",{\\"$map\\":[[\\"denominator\\",40],[\\"numerator\\",41'
    '13]]}]]},{\\"$map\\":[[\\"absolute_move_from_base\\",{\\"$map\\":[[\\"denominator\\",16],[\\"numerator\\",'
    '113]]}],[\\"payoff_distance\\",{\\"$map\\":[[\\"denominator\\",16],[\\"numerator\\",113]]}],[\\"position_'
    'scale\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"quantity\\",1],[\\"underlying_units\\",100]]}],'
    '[\\"position_value_multiple\\",5],[\\"relative_move_from_base\\",{\\"$map\\":[[\\"denominator\\",1600],['
    '\\"numerator\\",113]]}],[\\"side\\",\\"upside\\"],[\\"status\\",\\"available\\"],[\\"strike_exact\\",{\\"$map'
    '\\":[[\\"denominator\\",1],[\\"numerator\\",100]]}],[\\"target_position_value\\",{\\"$map\\":[[\\"denomina'
    'tor\\",4],[\\"numerator\\",2825]]}],[\\"threshold_underlying_price\\",{\\"$map\\":[[\\"denominator\\",16]'
    ',[\\"numerator\\",1713]]}],[\\"unconstrained_threshold_underlying_price\\",{\\"$map\\":[[\\"denominator'
    '\\",16],[\\"numerator\\",1713]]}]]},{\\"$map\\":[[\\"absolute_move_from_base\\",{\\"$map\\":[[\\"denominat'
    'or\\",8],[\\"numerator\\",113]]}],[\\"payoff_distance\\",{\\"$map\\":[[\\"denominator\\",8],[\\"numerator\\'
    '",113]]}],[\\"position_scale\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"quantity\\",1],[\\"under'
    'lying_units\\",100]]}],[\\"position_value_multiple\\",10],[\\"relative_move_from_base\\",{\\"$map\\":[['
    '\\"denominator\\",800],[\\"numerator\\",113]]}],[\\"side\\",\\"upside\\"],[\\"status\\",\\"available\\"],[\\"'
    'strike_exact\\",{\\"$map\\":[[\\"denominator\\",1],[\\"numerator\\",100]]}],[\\"target_position_value\\",'
    '{\\"$map\\":[[\\"denominator\\",2],[\\"numerator\\",2825]]}],[\\"threshold_underlying_price\\",{\\"$map\\"'
    ':[[\\"denominator\\",8],[\\"numerator\\",913]]}],[\\"unconstrained_threshold_underlying_price\\",{\\"$m'
    'ap\\":[[\\"denominator\\",8],[\\"numerator\\",913]]}]]}]}],[\\"limitations\\",\\"Expiration intrinsic pa'
    'yoff evidence only; no probabilities, expected returns, recommendations, screening, position siz'
    'ing, exit-cost adjustment, provider access, or pricing model.\\"],[\\"move_rules\\",{\\"$map\\":[[\\"a'
    'bsolute\\",\\"threshold_underlying_price-base_underlying_price\\"],[\\"relative\\",\\"absolute_move_fr'
    'om_base/base_underlying_price\\"],[\\"signed\\",true]]}],[\\"numeric_representation\\",{\\"$map\\":[[\\"'
    'decimal_conversion\\",\\"exact_coefficient_and_exponent\\"],[\\"float_prohibited\\",true],[\\"mapping_'
    'keys\\",{\\"$list\\":[\\"numerator\\",\\"denominator\\"]}],[\\"positive_denominator\\",true],[\\"public_ty'
    'pe\\",\\"ExactRational\\"],[\\"reduced\\",true],[\\"rounding\\",\\"none\\"]]}],[\\"output_architecture\\",\\'
    '"single_expiration_payoff_threshold_evidence_record\\"],[\\"payoff_threshold_rules\\",{\\"$map\\":[[\\'
    '"exit_cost\\",\\"excluded\\"],[\\"long_call\\",\\"strike+payoff_distance\\"],[\\"long_put\\",\\"strike-pay'
    'off_distance\\"],[\\"long_straddle_downside\\",\\"strike-payoff_distance\\"],[\\"long_straddle_upside\\'
    '",\\"strike+payoff_distance\\"],[\\"payoff_distance\\",\\"target_position_value/(quantity*contract_mu'
    'ltiplier)\\"],[\\"position_value_multiple\\",\\"expiration_gross_position_value/total_entry_cost\\"],'
    '[\\"target_position_value\\",\\"multiple*total_entry_cost\\"]]}],[\\"schema_version\\",\\"expiration-pa'
    'yoff-thresholds-v0.1\\"],[\\"solution_domain\\",{\\"$map\\":[[\\"negative_lower_threshold\\",\\"unavaila'
    'ble_negative_underlying_price\\"],[\\"negative_published_threshold\\",\\"prohibited\\"],[\\"underlying'
    '_price\\",\\"nonnegative\\"],[\\"zero_lower_threshold\\",\\"available\\"]]}],[\\"structure_costs_depende'
    'ncy\\",{\\"$map\\":[[\\"calculated_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:04.000000Z\\"}],[\\"calculat'
    'ion_id\\",\\"scenario-valuation-costs\\"],[\\"calculation_type\\",\\"structure_costs\\"],[\\"input_rule\\'
    '",\\"exact_reuse_of_structure_costs_lineage_inputs\\"],[\\"methodology_id\\",\\"exact-structure-costs'
    '\\"],[\\"methodology_version\\",\\"v0.2\\"],[\\"parameters_json\\",\\"{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_va'
    'lues\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"commissions_and_fees_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.25\\\\\\"}],[\\\\'
    '\\"cumulative_repeated_bet_cost_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"141.250\\\\\\"}],[\\\\\\"estimated_spre'
    'ad_cost_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"20.000\\\\\\"}],[\\\\\\"gamma_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"'
    '2.000\\\\\\"}],[\\\\\\"maximum_loss_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"141.250\\\\\\"}],[\\\\\\"quoted_mid_prem'
    'ium_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"120.000\\\\\\"}],[\\\\\\"stable_record_values\\\\\\",{\\\\\\"$map\\\\\\":[['
    '\\\\\\"commissions_and_fees_repr\\\\\\",\\\\\\"1.25\\\\\\"],[\\\\\\"cumulative_repeated_bet_cost_repr\\\\\\",\\\\\\"1'
    '41.25\\\\\\"],[\\\\\\"estimated_spread_cost_repr\\\\\\",\\\\\\"20.0\\\\\\"],[\\\\\\"gamma_repr\\\\\\",\\\\\\"2.0\\\\\\"],[\\'
    '\\\\"maximum_loss_repr\\\\\\",\\\\\\"141.25\\\\\\"],[\\\\\\"quoted_mid_premium_repr\\\\\\",\\\\\\"120.0\\\\\\"],[\\\\\\"th'
    'eta_per_day_repr\\\\\\",\\\\\\"-10.0\\\\\\"],[\\\\\\"total_entry_cost_repr\\\\\\",\\\\\\"141.25\\\\\\"],[\\\\\\"underlyi'
    'ng_price_repr\\\\\\",\\\\\\"100.0\\\\\\"]]}],[\\\\\\"theta_per_day_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-10.000\\\\'
    '\\"}],[\\\\\\"total_entry_cost_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"141.250\\\\\\"}],[\\\\\\"underlying_price_e'
    'xact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.000\\\\\\"}]]}],[\\\\\\"commission_and_fee_scope\\\\\\",\\\\\\"entry_only'
    '_total_position\\\\\\"],[\\\\\\"commissions_and_fees_usd\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.25\\\\\\"}],[\\\\\\"gam'
    'ma_input_unit\\\\\\",\\\\\\"option_value_change_per_usd_squared_per_underlying_unit\\\\\\"],[\\\\\\"gamma_po'
    'sition_rule\\\\\\",\\\\\\"sum(gamma_per_underlying_unit_per_usd_squared*quantity*contract_multiplier)\\'
    '\\\\"],[\\\\\\"greeks_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"dividend_input_description\\\\\\",\\\\\\"Syntheti'
    'c dividend input\\\\\\"],[\\\\\\"model_name\\\\\\",\\\\\\"Synthetic Black-Scholes\\\\\\"],[\\\\\\"model_version\\\\\\'
    '",\\\\\\"fixture-v1\\\\\\"],[\\\\\\"rate_input_description\\\\\\",\\\\\\"Synthetic USD curve input\\\\\\"],[\\\\\\"th'
    'eta_day_basis\\\\\\",\\\\\\"Provider calendar-day convention\\\\\\"],[\\\\\\"unit_convention\\\\\\",\\\\\\"Contrac'
    't-defined canonical units\\\\\\"]]}],[\\\\\\"leg_correspondence\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\'
    '\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\'
    '"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"option_contract_reference_record_id\\\\\\"'
    ',\\\\\\"cost-call-contract-reference\\\\\\"],[\\\\\\"option_greeks_record_id\\\\\\",\\\\\\"cost-call-greeks\\\\\\"'
    '],[\\\\\\"option_quote_record_id\\\\\\",\\\\\\"cost-call-quote\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\'
    '\\\\"quantity\\\\\\",1],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying\\\\\\",{\\\\\\"$m'
    'ap\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\"'
    ',\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"cost-under'
    'lying-quote\\\\\\"]]}]}],[\\\\\\"normalized_evidence\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_references\\\\\\",{'
    '\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],['
    '\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"exercise_style\\\\\\",\\\\\\"American\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"'
    '$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"last_trade_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\'
    '"listing_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-09-16\\\\\\"}],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":'
    '\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"propagated_quality'
    '_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"quantity\\\\\\",1],[\\\\\\"record_id\\\\\\",\\\\\\"cost-call-contract-re'
    'ference\\\\\\"],[\\\\\\"settlement_type\\\\\\",\\\\\\"Physical\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"'
    'cost-call-contract-reference-source-0\\\\\\"]}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],['
    '\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\'
    '\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}]}],[\\\\\\"option_greeks\\'
    '\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\'
    '\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"dividend_input_description\\\\\\",\\\\\\"Synthetic dividend inp'
    'ut\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"gamma\\\\\\",{\\\\\\"$decimal\\\\\\"'
    ':\\\\\\"0.020\\\\\\"}],[\\\\\\"model_name\\\\\\",\\\\\\"Synthetic Black-Scholes\\\\\\"],[\\\\\\"model_version\\\\\\",\\\\\\'
    '"fixture-v1\\\\\\"],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}]'
    ',[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"q'
    'uantity\\\\\\",1],[\\\\\\"rate_input_description\\\\\\",\\\\\\"Synthetic USD curve input\\\\\\"],[\\\\\\"record_id'
    '\\\\\\",\\\\\\"cost-call-greeks\\\\\\"],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"so'
    'urce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"cost-call-greeks-source-0\\\\\\"]}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"theta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.100\\\\\\"}],[\\\\\\"theta_day_basis\\\\\\",\\'
    '\\\\"Provider calendar-day convention\\\\\\"],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\'
    '\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\'
    '",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"unit_convention\\\\\\",\\\\\\"Contract-defined canonical units\\\\\\"]]}]}],[\\\\\\"o'
    'ption_quotes\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"ask_premium\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.40\\'
    '\\\\"}],[\\\\\\"bid_premium\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.00\\\\\\"}],[\\\\\\"contract_multiplier\\\\\\",100],[\\'
    '\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\'
    '\\"2030-03-03\\\\\\"}],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"'
    '}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\'
    '"quantity\\\\\\",1],[\\\\\\"record_id\\\\\\",\\\\\\"cost-call-quote\\\\\\"],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\'
    '":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"cost-call-quote-source-0\\\\\\"]}],['
    '\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currenc'
    'y\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"s'
    'ymbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}]}],[\\\\\\"underlying_quote\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"ask_price\\\\\\",{\\\\\\"'
    '$decimal\\\\\\":\\\\\\"101.00\\\\\\"}],[\\\\\\"bid_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"99.00\\\\\\"}],[\\\\\\"midpoint'
    '_rule\\\\\\",\\\\\\"(bid_price+ask_price)/2\\\\\\"],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01'
    '-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\'
    '\\\\",\\\\\\"cost-underlying-quote\\\\\\"],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\'
    '\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"cost-underlying-quote-source-0\\\\\\"]}],[\\\\\\"underlying\\\\\\",{'
    '\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_ty'
    'pe\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"underlying_price_exact\\\\\\",{\\\\\\"$decima'
    'l\\\\\\":\\\\\\"100.000\\\\\\"}]]}]]}],[\\\\\\"position_value_unit\\\\\\",\\\\\\"usd\\\\\\"],[\\\\\\"premium_input_unit\\'
    '\\\\",\\\\\\"usd_per_underlying_unit\\\\\\"],[\\\\\\"premium_midpoint_rule\\\\\\",\\\\\\"sum(((bid_premium+ask_pr'
    'emium)/2)*quantity*contract_multiplier)\\\\\\"],[\\\\\\"repeated_bet_count\\\\\\",1],[\\\\\\"spread_cost_rul'
    'e\\\\\\",\\\\\\"sum(((ask_premium-bid_premium)/2)*quantity*contract_multiplier)\\\\\\"],[\\\\\\"spread_cost_'
    'scope\\\\\\",\\\\\\"entry_only_midpoint_to_ask\\\\\\"],[\\\\\\"structure_identity\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"as'
    'sumed_portfolio_value_repr\\\\\\",\\\\\\"100000.0\\\\\\"],[\\\\\\"expected_holding_days\\\\\\",14],[\\\\\\"legs\\\\\\'
    '",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"expiration\\\\\\",{\\\\\\"$dat'
    'e\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\\\\\"strike_f'
    'loat_repr\\\\\\",\\\\\\"100.0\\\\\\"],[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}]}],[\\\\\\"structure_type\\\\\\",\\\\\\"l'
    'ong_call\\\\\\"],[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"theta_day_basis\\\\\\",\\\\\\"Provider calendar'
    '-day convention\\\\\\"],[\\\\\\"theta_input_unit\\\\\\",\\\\\\"usd_per_underlying_unit_per_declared_day_basi'
    's\\\\\\"],[\\\\\\"theta_position_rule\\\\\\",\\\\\\"sum(theta_per_underlying_unit_per_declared_day_basis*qua'
    'ntity*contract_multiplier)\\\\\\"],[\\\\\\"underlying_price_rule\\\\\\",\\\\\\"(bid_price+ask_price)/2\\\\\\"],'
    '[\\\\\\"underlying_price_unit\\\\\\",\\\\\\"usd_per_underlying_share\\\\\\"]]}\\"],[\\"quality_flags\\",{\\"$lis'
    't\\":[\\"decimal_to_float_converted\\",\\"assumption_applied\\"]}]]}],[\\"supported_structure_scope\\",'
    '{\\"$list\\":[\\"long_call\\",\\"long_put\\",\\"long_straddle_same_strike_expiration_quantity_multiplie'
    'r\\"]}],[\\"target_multiples\\",{\\"$list\\":[1,2,5,10]}],[\\"threshold_ordering\\",{\\"$map\\":[[\\"multi'
    'ple_order\\",{\\"$list\\":[1,2,5,10]}],[\\"straddle_side_order\\",{\\"$list\\":[\\"downside\\",\\"upside\\"'
    ']}],[\\"unavailable_records_retain_position\\",true]]}]]}"],["quality_flags",{"$list":["assumption'
    '_applied"]}]]}],["record",{"$map":[["as_of_date",{"$date":"2030-01-02"}],["base_underlying_price'
    '",{"$decimal":"100.000"}],["structure",{"$map":[["assumed_portfolio_value_repr","100000.0"],["ex'
    'pected_holding_days",14],["legs",{"$list":[{"$map":[["contract_multiplier",100],["expiration",{"'
    '$date":"2030-03-03"}],["option_type","call"],["quantity",1],["strike_float_repr","100.0"],["unde'
    'rlying","SPY"]]}]}],["structure_type","long_call"],["underlying","SPY"]]}],["thresholds",{"$list'
    '":[{"$map":[["absolute_move_from_base",{"$map":[["denominator",80],["numerator",113]]}],["positi'
    'on_value_multiple",1],["relative_move_from_base",{"$map":[["denominator",8000],["numerator",113]'
    ']}],["side","upside"],["status","available"],["target_position_value",{"$map":[["denominator",4]'
    ',["numerator",565]]}],["threshold_underlying_price",{"$map":[["denominator",80],["numerator",811'
    '3]]}]]},{"$map":[["absolute_move_from_base",{"$map":[["denominator",40],["numerator",113]]}],["p'
    'osition_value_multiple",2],["relative_move_from_base",{"$map":[["denominator",4000],["numerator"'
    ',113]]}],["side","upside"],["status","available"],["target_position_value",{"$map":[["denominato'
    'r",2],["numerator",565]]}],["threshold_underlying_price",{"$map":[["denominator",40],["numerator'
    '",4113]]}]]},{"$map":[["absolute_move_from_base",{"$map":[["denominator",16],["numerator",113]]}'
    '],["position_value_multiple",5],["relative_move_from_base",{"$map":[["denominator",1600],["numer'
    'ator",113]]}],["side","upside"],["status","available"],["target_position_value",{"$map":[["denom'
    'inator",4],["numerator",2825]]}],["threshold_underlying_price",{"$map":[["denominator",16],["num'
    'erator",1713]]}]]},{"$map":[["absolute_move_from_base",{"$map":[["denominator",8],["numerator",1'
    '13]]}],["position_value_multiple",10],["relative_move_from_base",{"$map":[["denominator",800],["'
    'numerator",113]]}],["side","upside"],["status","available"],["target_position_value",{"$map":[["'
    'denominator",2],["numerator",2825]]}],["threshold_underlying_price",{"$map":[["denominator",8],['
    '"numerator",913]]}]]}]}],["total_entry_cost",{"$decimal":"141.250"}]]}],["wrapper_type","Expirat'
    'ionPayoffThresholdTransformationResult"]]}],["output_architecture",{"$map":[["artifact_represent'
    'ation","seven_explicit_optional_reviewed_wrapper_fields"],["candidate_record_type","CandidateRes'
    'earchRecord"],["lineage_type","CalculationLineage"],["result_type","CandidateResearchRecordAssem'
    'blyResult"]]}],["scenario_valuation_result",{"$map":[["lineage",{"$map":[["calculated_at",{"$dat'
    'etime":"2030-01-02T15:30:14.000000Z"}],["calculation_id","scenario-valuation-calculation-001"],['
    '"calculation_type","scenario_valuation"],["inputs",{"$list":[{"$map":[["normalized_at",{"$dateti'
    'me":"2030-01-02T15:30:00.000002Z"}],["record_id","cost-call-contract-reference"],["source_ids",{'
    '"$list":["cost-call-contract-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"20'
    '30-01-02T15:30:00.000002Z"}],["record_id","cost-call-greeks"],["source_ids",{"$list":["cost-call'
    '-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["'
    'record_id","cost-call-quote"],["source_ids",{"$list":["cost-call-quote-source-0"]}]]},{"$map":[['
    '"normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","cost-underlying-quote'
    '"],["source_ids",{"$list":["cost-underlying-quote-source-0"]}]]},{"$map":[["normalized_at",{"$da'
    'tetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-0"],["source_ids",{"$list":["hrv-0-sou'
    'rce-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id",'
    '"hrv-1"],["source_ids",{"$list":["hrv-1-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2'
    '030-01-02T15:30:00.000002Z"}],["record_id","hrv-2"],["source_ids",{"$list":["hrv-2-source-0"]}]]'
    '},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:04.000000Z"}],["record_id","scenario-'
    'iv-0"],["source_ids",{"$list":["source-001"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01'
    '-02T15:30:04.000000Z"}],["record_id","scenario-reference-0"],["source_ids",{"$list":["source-001'
    '"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:04.000000Z"}],["record_id","scen'
    'ario-underlying-quote"],["source_ids",{"$list":["source-001"]}]]},{"$map":[["normalized_at",{"$d'
    'atetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-call10-greeks"],["source_'
    'ids",{"$list":["tail-current-30-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$dateti'
    'me":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-call10-iv"],["source_ids",{"$l'
    'ist":["tail-current-30-call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-'
    '02T15:30:00.000002Z"}],["record_id","tail-current-30-call10-quote"],["source_ids",{"$list":["tai'
    'l-current-30-call10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:3'
    '0:00.000002Z"}],["record_id","tail-current-30-call10-reference"],["source_ids",{"$list":["tail-c'
    'urrent-30-call10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:'
    '30:00.000002Z"}],["record_id","tail-current-30-call25-greeks"],["source_ids",{"$list":["tail-cur'
    'rent-30-call25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","tail-current-30-call25-iv"],["source_ids",{"$list":["tail-current-30-c'
    'all25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],['
    '"record_id","tail-current-30-call25-quote"],["source_ids",{"$list":["tail-current-30-call25-quot'
    'e-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record'
    '_id","tail-current-30-call25-reference"],["source_ids",{"$list":["tail-current-30-call25-referen'
    'ce-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["recor'
    'd_id","tail-current-30-put10-greeks"],["source_ids",{"$list":["tail-current-30-put10-greeks-sour'
    'ce-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","'
    'tail-current-30-put10-iv"],["source_ids",{"$list":["tail-current-30-put10-iv-source-0"]}]]},{"$m'
    'ap":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30'
    '-put10-quote"],["source_ids",{"$list":["tail-current-30-put10-quote-source-0"]}]]},{"$map":[["no'
    'rmalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-put10-re'
    'ference"],["source_ids",{"$list":["tail-current-30-put10-reference-source-0"]}]]},{"$map":[["nor'
    'malized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-put25-gre'
    'eks"],["source_ids",{"$list":["tail-current-30-put25-greeks-source-0"]}]]},{"$map":[["normalized'
    '_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-put25-iv"],["sou'
    'rce_ids",{"$list":["tail-current-30-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetim'
    'e":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-put25-quote"],["source_ids",{"$'
    'list":["tail-current-30-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-'
    '01-02T15:30:00.000002Z"}],["record_id","tail-current-30-put25-reference"],["source_ids",{"$list"'
    ':["tail-current-30-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-0'
    '1-02T15:30:00.000002Z"}],["record_id","tail-current-60-call10-greeks"],["source_ids",{"$list":["'
    'tail-current-60-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T'
    '15:30:00.000002Z"}],["record_id","tail-current-60-call10-iv"],["source_ids",{"$list":["tail-curr'
    'ent-60-call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0000'
    '02Z"}],["record_id","tail-current-60-call10-quote"],["source_ids",{"$list":["tail-current-60-cal'
    'l10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],'
    '["record_id","tail-current-60-call10-reference"],["source_ids",{"$list":["tail-current-60-call10'
    '-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}]'
    ',["record_id","tail-current-60-call25-greeks"],["source_ids",{"$list":["tail-current-60-call25-g'
    'reeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["re'
    'cord_id","tail-current-60-call25-iv"],["source_ids",{"$list":["tail-current-60-call25-iv-source-'
    '0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tai'
    'l-current-60-call25-quote"],["source_ids",{"$list":["tail-current-60-call25-quote-source-0"]}]]}'
    ',{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-curre'
    'nt-60-call25-reference"],["source_ids",{"$list":["tail-current-60-call25-reference-source-0"]}]]'
    '},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-curr'
    'ent-60-put10-greeks"],["source_ids",{"$list":["tail-current-60-put10-greeks-source-0"]}]]},{"$ma'
    'p":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-'
    'put10-iv"],["source_ids",{"$list":["tail-current-60-put10-iv-source-0"]}]]},{"$map":[["normalize'
    'd_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-put10-quote"],['
    '"source_ids",{"$list":["tail-current-60-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$'
    'datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-put10-reference"],["sour'
    'ce_ids",{"$list":["tail-current-60-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$d'
    'atetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-put25-greeks"],["source_i'
    'ds",{"$list":["tail-current-60-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime'
    '":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-put25-iv"],["source_ids",{"$list'
    '":["tail-current-60-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T1'
    '5:30:00.000002Z"}],["record_id","tail-current-60-put25-quote"],["source_ids",{"$list":["tail-cur'
    'rent-60-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0'
    '00002Z"}],["record_id","tail-current-60-put25-reference"],["source_ids",{"$list":["tail-current-'
    '60-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.00'
    '0002Z"}],["record_id","tail-history-0-30-call10-greeks"],["source_ids",{"$list":["tail-history-0'
    '-30-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000'
    '002Z"}],["record_id","tail-history-0-30-call10-iv"],["source_ids",{"$list":["tail-history-0-30-c'
    'all10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],['
    '"record_id","tail-history-0-30-call10-quote"],["source_ids",{"$list":["tail-history-0-30-call10-'
    'quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["re'
    'cord_id","tail-history-0-30-call10-reference"],["source_ids",{"$list":["tail-history-0-30-call10'
    '-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}]'
    ',["record_id","tail-history-0-30-call25-greeks"],["source_ids",{"$list":["tail-history-0-30-call'
    '25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],'
    '["record_id","tail-history-0-30-call25-iv"],["source_ids",{"$list":["tail-history-0-30-call25-iv'
    '-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_'
    'id","tail-history-0-30-call25-quote"],["source_ids",{"$list":["tail-history-0-30-call25-quote-so'
    'urce-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id"'
    ',"tail-history-0-30-call25-reference"],["source_ids",{"$list":["tail-history-0-30-call25-referen'
    'ce-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["recor'
    'd_id","tail-history-0-30-put10-greeks"],["source_ids",{"$list":["tail-history-0-30-put10-greeks-'
    'source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_i'
    'd","tail-history-0-30-put10-iv"],["source_ids",{"$list":["tail-history-0-30-put10-iv-source-0"]}'
    ']]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-hi'
    'story-0-30-put10-quote"],["source_ids",{"$list":["tail-history-0-30-put10-quote-source-0"]}]]},{'
    '"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history'
    '-0-30-put10-reference"],["source_ids",{"$list":["tail-history-0-30-put10-reference-source-0"]}]]'
    '},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-hist'
    'ory-0-30-put25-greeks"],["source_ids",{"$list":["tail-history-0-30-put25-greeks-source-0"]}]]},{'
    '"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history'
    '-0-30-put25-iv"],["source_ids",{"$list":["tail-history-0-30-put25-iv-source-0"]}]]},{"$map":[["n'
    'ormalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-put25'
    '-quote"],["source_ids",{"$list":["tail-history-0-30-put25-quote-source-0"]}]]},{"$map":[["normal'
    'ized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-put25-refe'
    'rence"],["source_ids",{"$list":["tail-history-0-30-put25-reference-source-0"]}]]},{"$map":[["nor'
    'malized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-atm-cal'
    'l-greeks"],["source_ids",{"$list":["tail-history-0-60-atm-call-greeks-source-0"]}]]},{"$map":[["'
    'normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-atm-'
    'call-iv"],["source_ids",{"$list":["tail-history-0-60-atm-call-iv-source-0"]}]]},{"$map":[["norma'
    'lized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-atm-call-'
    'quote"],["source_ids",{"$list":["tail-history-0-60-atm-call-quote-source-0"]}]]},{"$map":[["norm'
    'alized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-atm-call'
    '-reference"],["source_ids",{"$list":["tail-history-0-60-atm-call-reference-source-0"]}]]},{"$map'
    '":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60'
    '-atm-put-greeks"],["source_ids",{"$list":["tail-history-0-60-atm-put-greeks-source-0"]}]]},{"$ma'
    'p":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-6'
    '0-atm-put-iv"],["source_ids",{"$list":["tail-history-0-60-atm-put-iv-source-0"]}]]},{"$map":[["n'
    'ormalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-atm-p'
    'ut-quote"],["source_ids",{"$list":["tail-history-0-60-atm-put-quote-source-0"]}]]},{"$map":[["no'
    'rmalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-atm-pu'
    't-reference"],["source_ids",{"$list":["tail-history-0-60-atm-put-reference-source-0"]}]]},{"$map'
    '":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60'
    '-call10-greeks"],["source_ids",{"$list":["tail-history-0-60-call10-greeks-source-0"]}]]},{"$map"'
    ':[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-'
    'call10-iv"],["source_ids",{"$list":["tail-history-0-60-call10-iv-source-0"]}]]},{"$map":[["norma'
    'lized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-call10-qu'
    'ote"],["source_ids",{"$list":["tail-history-0-60-call10-quote-source-0"]}]]},{"$map":[["normaliz'
    'ed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-call10-refer'
    'ence"],["source_ids",{"$list":["tail-history-0-60-call10-reference-source-0"]}]]},{"$map":[["nor'
    'malized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-call25-'
    'greeks"],["source_ids",{"$list":["tail-history-0-60-call25-greeks-source-0"]}]]},{"$map":[["norm'
    'alized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-call25-i'
    'v"],["source_ids",{"$list":["tail-history-0-60-call25-iv-source-0"]}]]},{"$map":[["normalized_at'
    '",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-call25-quote"],["'
    'source_ids",{"$list":["tail-history-0-60-call25-quote-source-0"]}]]},{"$map":[["normalized_at",{'
    '"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-call25-reference"],['
    '"source_ids",{"$list":["tail-history-0-60-call25-reference-source-0"]}]]},{"$map":[["normalized_'
    'at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-put10-greeks"],'
    '["source_ids",{"$list":["tail-history-0-60-put10-greeks-source-0"]}]]},{"$map":[["normalized_at"'
    ',{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-put10-iv"],["sourc'
    'e_ids",{"$list":["tail-history-0-60-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetim'
    'e":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-put10-quote"],["source_ids",{'
    '"$list":["tail-history-0-60-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2'
    '030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-put10-reference"],["source_ids",{"'
    '$list":["tail-history-0-60-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime"'
    ':"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-put25-greeks"],["source_ids",{"'
    '$list":["tail-history-0-60-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2'
    '030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60-put25-iv"],["source_ids",{"$list":'
    '["tail-history-0-60-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T1'
    '5:30:00.000002Z"}],["record_id","tail-history-0-60-put25-quote"],["source_ids",{"$list":["tail-h'
    'istory-0-60-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:'
    '00.000002Z"}],["record_id","tail-history-0-60-put25-reference"],["source_ids",{"$list":["tail-hi'
    'story-0-60-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:'
    '30:00.000002Z"}],["record_id","tail-history-0-60-underlying"],["source_ids",{"$list":["tail-hist'
    'ory-0-60-underlying-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0'
    '00002Z"}],["record_id","tail-history-1-30-call10-greeks"],["source_ids",{"$list":["tail-history-'
    '1-30-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.00'
    '0002Z"}],["record_id","tail-history-1-30-call10-iv"],["source_ids",{"$list":["tail-history-1-30-'
    'call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],'
    '["record_id","tail-history-1-30-call10-quote"],["source_ids",{"$list":["tail-history-1-30-call10'
    '-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["r'
    'ecord_id","tail-history-1-30-call10-reference"],["source_ids",{"$list":["tail-history-1-30-call1'
    '0-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}'
    '],["record_id","tail-history-1-30-call25-greeks"],["source_ids",{"$list":["tail-history-1-30-cal'
    'l25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}]'
    ',["record_id","tail-history-1-30-call25-iv"],["source_ids",{"$list":["tail-history-1-30-call25-i'
    'v-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record'
    '_id","tail-history-1-30-call25-quote"],["source_ids",{"$list":["tail-history-1-30-call25-quote-s'
    'ource-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id'
    '","tail-history-1-30-call25-reference"],["source_ids",{"$list":["tail-history-1-30-call25-refere'
    'nce-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["reco'
    'rd_id","tail-history-1-30-put10-greeks"],["source_ids",{"$list":["tail-history-1-30-put10-greeks'
    '-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_'
    'id","tail-history-1-30-put10-iv"],["source_ids",{"$list":["tail-history-1-30-put10-iv-source-0"]'
    '}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-h'
    'istory-1-30-put10-quote"],["source_ids",{"$list":["tail-history-1-30-put10-quote-source-0"]}]]},'
    '{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-histor'
    'y-1-30-put10-reference"],["source_ids",{"$list":["tail-history-1-30-put10-reference-source-0"]}]'
    ']},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-his'
    'tory-1-30-put25-greeks"],["source_ids",{"$list":["tail-history-1-30-put25-greeks-source-0"]}]]},'
    '{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-histor'
    'y-1-30-put25-iv"],["source_ids",{"$list":["tail-history-1-30-put25-iv-source-0"]}]]},{"$map":[["'
    'normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-put2'
    '5-quote"],["source_ids",{"$list":["tail-history-1-30-put25-quote-source-0"]}]]},{"$map":[["norma'
    'lized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-put25-ref'
    'erence"],["source_ids",{"$list":["tail-history-1-30-put25-reference-source-0"]}]]},{"$map":[["no'
    'rmalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-atm-ca'
    'll-greeks"],["source_ids",{"$list":["tail-history-1-60-atm-call-greeks-source-0"]}]]},{"$map":[['
    '"normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-atm'
    '-call-iv"],["source_ids",{"$list":["tail-history-1-60-atm-call-iv-source-0"]}]]},{"$map":[["norm'
    'alized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-atm-call'
    '-quote"],["source_ids",{"$list":["tail-history-1-60-atm-call-quote-source-0"]}]]},{"$map":[["nor'
    'malized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-atm-cal'
    'l-reference"],["source_ids",{"$list":["tail-history-1-60-atm-call-reference-source-0"]}]]},{"$ma'
    'p":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-6'
    '0-atm-put-greeks"],["source_ids",{"$list":["tail-history-1-60-atm-put-greeks-source-0"]}]]},{"$m'
    'ap":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-'
    '60-atm-put-iv"],["source_ids",{"$list":["tail-history-1-60-atm-put-iv-source-0"]}]]},{"$map":[["'
    'normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-atm-'
    'put-quote"],["source_ids",{"$list":["tail-history-1-60-atm-put-quote-source-0"]}]]},{"$map":[["n'
    'ormalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-atm-p'
    'ut-reference"],["source_ids",{"$list":["tail-history-1-60-atm-put-reference-source-0"]}]]},{"$ma'
    'p":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-6'
    '0-call10-greeks"],["source_ids",{"$list":["tail-history-1-60-call10-greeks-source-0"]}]]},{"$map'
    '":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60'
    '-call10-iv"],["source_ids",{"$list":["tail-history-1-60-call10-iv-source-0"]}]]},{"$map":[["norm'
    'alized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-call10-q'
    'uote"],["source_ids",{"$list":["tail-history-1-60-call10-quote-source-0"]}]]},{"$map":[["normali'
    'zed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-call10-refe'
    'rence"],["source_ids",{"$list":["tail-history-1-60-call10-reference-source-0"]}]]},{"$map":[["no'
    'rmalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-call25'
    '-greeks"],["source_ids",{"$list":["tail-history-1-60-call25-greeks-source-0"]}]]},{"$map":[["nor'
    'malized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-call25-'
    'iv"],["source_ids",{"$list":["tail-history-1-60-call25-iv-source-0"]}]]},{"$map":[["normalized_a'
    't",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-call25-quote"],['
    '"source_ids",{"$list":["tail-history-1-60-call25-quote-source-0"]}]]},{"$map":[["normalized_at",'
    '{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-call25-reference"],'
    '["source_ids",{"$list":["tail-history-1-60-call25-reference-source-0"]}]]},{"$map":[["normalized'
    '_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-put10-greeks"]'
    ',["source_ids",{"$list":["tail-history-1-60-put10-greeks-source-0"]}]]},{"$map":[["normalized_at'
    '",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-put10-iv"],["sour'
    'ce_ids",{"$list":["tail-history-1-60-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$dateti'
    'me":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-put10-quote"],["source_ids",'
    '{"$list":["tail-history-1-60-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"'
    '2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-put10-reference"],["source_ids",{'
    '"$list":["tail-history-1-60-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime'
    '":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-put25-greeks"],["source_ids",{'
    '"$list":["tail-history-1-60-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"'
    '2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-60-put25-iv"],["source_ids",{"$list"'
    ':["tail-history-1-60-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T'
    '15:30:00.000002Z"}],["record_id","tail-history-1-60-put25-quote"],["source_ids",{"$list":["tail-'
    'history-1-60-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30'
    ':00.000002Z"}],["record_id","tail-history-1-60-put25-reference"],["source_ids",{"$list":["tail-h'
    'istory-1-60-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15'
    ':30:00.000002Z"}],["record_id","tail-history-1-60-underlying"],["source_ids",{"$list":["tail-his'
    'tory-1-60-underlying-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.'
    '000002Z"}],["record_id","tail-history-2-30-call10-greeks"],["source_ids",{"$list":["tail-history'
    '-2-30-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0'
    '00002Z"}],["record_id","tail-history-2-30-call10-iv"],["source_ids",{"$list":["tail-history-2-30'
    '-call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}]'
    ',["record_id","tail-history-2-30-call10-quote"],["source_ids",{"$list":["tail-history-2-30-call1'
    '0-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["'
    'record_id","tail-history-2-30-call10-reference"],["source_ids",{"$list":["tail-history-2-30-call'
    '10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"'
    '}],["record_id","tail-history-2-30-call25-greeks"],["source_ids",{"$list":["tail-history-2-30-ca'
    'll25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}'
    '],["record_id","tail-history-2-30-call25-iv"],["source_ids",{"$list":["tail-history-2-30-call25-'
    'iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["recor'
    'd_id","tail-history-2-30-call25-quote"],["source_ids",{"$list":["tail-history-2-30-call25-quote-'
    'source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_i'
    'd","tail-history-2-30-call25-reference"],["source_ids",{"$list":["tail-history-2-30-call25-refer'
    'ence-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["rec'
    'ord_id","tail-history-2-30-put10-greeks"],["source_ids",{"$list":["tail-history-2-30-put10-greek'
    's-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record'
    '_id","tail-history-2-30-put10-iv"],["source_ids",{"$list":["tail-history-2-30-put10-iv-source-0"'
    ']}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-'
    'history-2-30-put10-quote"],["source_ids",{"$list":["tail-history-2-30-put10-quote-source-0"]}]]}'
    ',{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-histo'
    'ry-2-30-put10-reference"],["source_ids",{"$list":["tail-history-2-30-put10-reference-source-0"]}'
    ']]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-hi'
    'story-2-30-put25-greeks"],["source_ids",{"$list":["tail-history-2-30-put25-greeks-source-0"]}]]}'
    ',{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-histo'
    'ry-2-30-put25-iv"],["source_ids",{"$list":["tail-history-2-30-put25-iv-source-0"]}]]},{"$map":[['
    '"normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-put'
    '25-quote"],["source_ids",{"$list":["tail-history-2-30-put25-quote-source-0"]}]]},{"$map":[["norm'
    'alized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-put25-re'
    'ference"],["source_ids",{"$list":["tail-history-2-30-put25-reference-source-0"]}]]},{"$map":[["n'
    'ormalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-atm-c'
    'all-greeks"],["source_ids",{"$list":["tail-history-2-60-atm-call-greeks-source-0"]}]]},{"$map":['
    '["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-at'
    'm-call-iv"],["source_ids",{"$list":["tail-history-2-60-atm-call-iv-source-0"]}]]},{"$map":[["nor'
    'malized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-atm-cal'
    'l-quote"],["source_ids",{"$list":["tail-history-2-60-atm-call-quote-source-0"]}]]},{"$map":[["no'
    'rmalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-atm-ca'
    'll-reference"],["source_ids",{"$list":["tail-history-2-60-atm-call-reference-source-0"]}]]},{"$m'
    'ap":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-'
    '60-atm-put-greeks"],["source_ids",{"$list":["tail-history-2-60-atm-put-greeks-source-0"]}]]},{"$'
    'map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2'
    '-60-atm-put-iv"],["source_ids",{"$list":["tail-history-2-60-atm-put-iv-source-0"]}]]},{"$map":[['
    '"normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-atm'
    '-put-quote"],["source_ids",{"$list":["tail-history-2-60-atm-put-quote-source-0"]}]]},{"$map":[["'
    'normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-atm-'
    'put-reference"],["source_ids",{"$list":["tail-history-2-60-atm-put-reference-source-0"]}]]},{"$m'
    'ap":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-'
    '60-call10-greeks"],["source_ids",{"$list":["tail-history-2-60-call10-greeks-source-0"]}]]},{"$ma'
    'p":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-6'
    '0-call10-iv"],["source_ids",{"$list":["tail-history-2-60-call10-iv-source-0"]}]]},{"$map":[["nor'
    'malized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-call10-'
    'quote"],["source_ids",{"$list":["tail-history-2-60-call10-quote-source-0"]}]]},{"$map":[["normal'
    'ized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-call10-ref'
    'erence"],["source_ids",{"$list":["tail-history-2-60-call10-reference-source-0"]}]]},{"$map":[["n'
    'ormalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-call2'
    '5-greeks"],["source_ids",{"$list":["tail-history-2-60-call25-greeks-source-0"]}]]},{"$map":[["no'
    'rmalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-call25'
    '-iv"],["source_ids",{"$list":["tail-history-2-60-call25-iv-source-0"]}]]},{"$map":[["normalized_'
    'at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-call25-quote"],'
    '["source_ids",{"$list":["tail-history-2-60-call25-quote-source-0"]}]]},{"$map":[["normalized_at"'
    ',{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-call25-reference"]'
    ',["source_ids",{"$list":["tail-history-2-60-call25-reference-source-0"]}]]},{"$map":[["normalize'
    'd_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-put10-greeks"'
    '],["source_ids",{"$list":["tail-history-2-60-put10-greeks-source-0"]}]]},{"$map":[["normalized_a'
    't",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-put10-iv"],["sou'
    'rce_ids",{"$list":["tail-history-2-60-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datet'
    'ime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-put10-quote"],["source_ids"'
    ',{"$list":["tail-history-2-60-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":'
    '"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-put10-reference"],["source_ids",'
    '{"$list":["tail-history-2-60-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetim'
    'e":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-put25-greeks"],["source_ids",'
    '{"$list":["tail-history-2-60-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":'
    '"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-60-put25-iv"],["source_ids",{"$list'
    '":["tail-history-2-60-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02'
    'T15:30:00.000002Z"}],["record_id","tail-history-2-60-put25-quote"],["source_ids",{"$list":["tail'
    '-history-2-60-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:3'
    '0:00.000002Z"}],["record_id","tail-history-2-60-put25-reference"],["source_ids",{"$list":["tail-'
    'history-2-60-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T1'
    '5:30:00.000002Z"}],["record_id","tail-history-2-60-underlying"],["source_ids",{"$list":["tail-hi'
    'story-2-60-underlying-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","ve-current-0-call-greeks"],["source_ids",{"$list":["ve-current-0-call-'
    'greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["r'
    'ecord_id","ve-current-0-call-iv"],["source_ids",{"$list":["ve-current-0-call-iv-source-0"]}]]},{'
    '"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0'
    '-call-quote"],["source_ids",{"$list":["ve-current-0-call-quote-source-0"]}]]},{"$map":[["normali'
    'zed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-call-reference"]'
    ',["source_ids",{"$list":["ve-current-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{'
    '"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-put-greeks"],["source_ids'
    '",{"$list":["ve-current-0-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030'
    '-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-put-iv"],["source_ids",{"$list":["ve-curre'
    'nt-0-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}'
    '],["record_id","ve-current-0-put-quote"],["source_ids",{"$list":["ve-current-0-put-quote-source-'
    '0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-'
    'current-0-put-reference"],["source_ids",{"$list":["ve-current-0-put-reference-source-0"]}]]},{"$'
    'map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-c'
    'all-greeks"],["source_ids",{"$list":["ve-current-1-call-greeks-source-0"]}]]},{"$map":[["normali'
    'zed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-call-iv"],["sour'
    'ce_ids",{"$list":["ve-current-1-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2'
    '030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-call-quote"],["source_ids",{"$list":["v'
    'e-current-1-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:0'
    '0.000002Z"}],["record_id","ve-current-1-call-reference"],["source_ids",{"$list":["ve-current-1-c'
    'all-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z'
    '"}],["record_id","ve-current-1-put-greeks"],["source_ids",{"$list":["ve-current-1-put-greeks-sou'
    'rce-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id",'
    '"ve-current-1-put-iv"],["source_ids",{"$list":["ve-current-1-put-iv-source-0"]}]]},{"$map":[["no'
    'rmalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-put-quote"]'
    ',["source_ids",{"$list":["ve-current-1-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$dat'
    'etime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-put-reference"],["source_ids",'
    '{"$list":["ve-current-1-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"203'
    '0-01-02T15:30:00.000002Z"}],["record_id","ve-current-underlying"],["source_ids",{"$list":["ve-cu'
    'rrent-underlying-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0000'
    '02Z"}],["record_id","ve-history-0-0-call-greeks"],["source_ids",{"$list":["ve-history-0-0-call-g'
    'reeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["re'
    'cord_id","ve-history-0-0-call-iv"],["source_ids",{"$list":["ve-history-0-0-call-iv-source-0"]}]]'
    '},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-histor'
    'y-0-0-call-quote"],["source_ids",{"$list":["ve-history-0-0-call-quote-source-0"]}]]},{"$map":[["'
    'normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-call-re'
    'ference"],["source_ids",{"$list":["ve-history-0-0-call-reference-source-0"]}]]},{"$map":[["norma'
    'lized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-put-greeks"]'
    ',["source_ids",{"$list":["ve-history-0-0-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$'
    'datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-put-iv"],["source_ids",{"'
    '$list":["ve-history-0-0-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02'
    'T15:30:00.000002Z"}],["record_id","ve-history-0-0-put-quote"],["source_ids",{"$list":["ve-histor'
    'y-0-0-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.00000'
    '2Z"}],["record_id","ve-history-0-0-put-reference"],["source_ids",{"$list":["ve-history-0-0-put-r'
    'eference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],['
    '"record_id","ve-history-0-underlying"],["source_ids",{"$list":["ve-history-0-underlying-source-0'
    '"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-h'
    'istory-1-0-call-greeks"],["source_ids",{"$list":["ve-history-1-0-call-greeks-source-0"]}]]},{"$m'
    'ap":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-0-'
    'call-iv"],["source_ids",{"$list":["ve-history-1-0-call-iv-source-0"]}]]},{"$map":[["normalized_a'
    't",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-0-call-quote"],["sour'
    'ce_ids",{"$list":["ve-history-1-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetim'
    'e":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-0-call-reference"],["source_ids",{'
    '"$list":["ve-history-1-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2'
    '030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-0-put-greeks"],["source_ids",{"$list":['
    '"ve-history-1-0-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:'
    '30:00.000002Z"}],["record_id","ve-history-1-0-put-iv"],["source_ids",{"$list":["ve-history-1-0-p'
    'ut-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["re'
    'cord_id","ve-history-1-0-put-quote"],["source_ids",{"$list":["ve-history-1-0-put-quote-source-0"'
    ']}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-hi'
    'story-1-0-put-reference"],["source_ids",{"$list":["ve-history-1-0-put-reference-source-0"]}]]},{'
    '"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1'
    '-underlying"],["source_ids",{"$list":["ve-history-1-underlying-source-0"]}]]},{"$map":[["normali'
    'zed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-0-call-greeks"],'
    '["source_ids",{"$list":["ve-history-2-0-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$'
    'datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-0-call-iv"],["source_ids",{'
    '"$list":["ve-history-2-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-'
    '02T15:30:00.000002Z"}],["record_id","ve-history-2-0-call-quote"],["source_ids",{"$list":["ve-his'
    'tory-2-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0'
    '00002Z"}],["record_id","ve-history-2-0-call-reference"],["source_ids",{"$list":["ve-history-2-0-'
    'call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002'
    'Z"}],["record_id","ve-history-2-0-put-greeks"],["source_ids",{"$list":["ve-history-2-0-put-greek'
    's-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record'
    '_id","ve-history-2-0-put-iv"],["source_ids",{"$list":["ve-history-2-0-put-iv-source-0"]}]]},{"$m'
    'ap":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-0-'
    'put-quote"],["source_ids",{"$list":["ve-history-2-0-put-quote-source-0"]}]]},{"$map":[["normaliz'
    'ed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-0-put-reference"]'
    ',["source_ids",{"$list":["ve-history-2-0-put-reference-source-0"]}]]},{"$map":[["normalized_at",'
    '{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-underlying"],["source_id'
    's",{"$list":["ve-history-2-underlying-source-0"]}]]}]}],["methodology_id","hybrid-authoritative-'
    'nonexpiration-terminal-intrinsic-after-costs"],["methodology_version","v0.1"],["parameters_json"'
    ',"{\\"$map\\":[[\\"base_iv_rule\\",\\"ScenarioPricing_v0.1_actual_leg_evidence_in_public_leg_order\\"]'
    ',[\\"base_underlying_rule\\",{\\"$map\\":[[\\"exact_source\\",\\"StructureCosts_v0.2_calculation_values'
    '\\"],[\\"scenario_result_source\\",\\"StructureCosts_stable_float\\"]]}],[\\"bounded_loss_rule\\",\\"pnl'
    '_after_costs_not_less_than_negative_entry_cost\\"],[\\"calculation_values\\",{\\"$list\\":[{\\"$map\\":'
    '[[\\"base_leg_ivs_exact\\",{\\"$list\\":[{\\"$decimal\\":\\"0.20\\"}]}],[\\"base_underlying_exact\\",{\\"$d'
    'ecimal\\":\\"100.000\\"}],[\\"exit_cost_assumption_exact\\",{\\"$decimal\\":\\"2.50\\"}],[\\"expiration_pe'
    'r_leg_payoffs_exact\\",{\\"$list\\":[]}],[\\"gross_position_value_exact\\",{\\"$decimal\\":\\"250.00\\"}]'
    ',[\\"loss_is_within_entry_cost\\",true],[\\"pricing_methodology\\",\\"{\\\\\\"$map\\\\\\":[[\\\\\\"base_iv_sou'
    'rce\\\\\\",\\\\\\"ScenarioPricing_v0.1_actual_structure_leg_iv_evidence\\\\\\"],[\\\\\\"base_underlying_sour'
    'ce\\\\\\",\\\\\\"StructureCosts_v0.2_underlying_price_exact\\\\\\"],[\\\\\\"entry_cost_rule\\\\\\",\\\\\\"Structur'
    'eCosts_v0.2_stable_total_entry_cost_float\\\\\\"],[\\\\\\"exit_cost_rule\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"metho'
    'dology\\\\\\",\\\\\\"explicit_fixture_exit_cost_v0.1\\\\\\"],[\\\\\\"source\\\\\\",\\\\\\"explicit_scenario_specif'
    'ic_decimal_assumption\\\\\\"]]}],[\\\\\\"expiration_rule\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"active\\\\\\",false],[\\\\'
    '\\"call_formula\\\\\\",\\\\\\"max(shocked_underlying-strike,0)*quantity*multiplier\\\\\\"],[\\\\\\"external_e'
    'xpiration_value\\\\\\",\\\\\\"prohibited\\\\\\"],[\\\\\\"iv_effect\\\\\\",\\\\\\"none_base_leg_ivs_retained_for_au'
    'dit\\\\\\"],[\\\\\\"put_formula\\\\\\",\\\\\\"max(strike-shocked_underlying,0)*quantity*multiplier\\\\\\"]]}],['
    '\\\\\\"float_conversion_rule\\\\\\",\\\\\\"convert_base_iv_gross_and_exit_cost_once_to_finite_float\\\\\\"],'
    '[\\\\\\"limitations\\\\\\",\\\\\\"Internal consistency is validated; self-consistent fabricated dependenc'
    'y artifacts are not cryptographically authenticated.\\\\\\"],[\\\\\\"nonexpiration_rule\\\\\\",{\\\\\\"$map\\'
    '\\\\":[[\\\\\\"active\\\\\\",true],[\\\\\\"rule\\\\\\",\\\\\\"consume_authoritative_gross_value_without_repricing'
    '\\\\\\"]]}],[\\\\\\"provider_disclosure\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\"scenario-pricin'
    'g-calculation-001\\\\\\"],[\\\\\\"dividend_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"dividend_coverage_end_d'
    'ate\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-15\\\\\\"}],[\\\\\\"dividend_coverage_start_date\\\\\\",{\\\\\\"$date\\\\\\"'
    ':\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"dividend_source\\\\\\",\\\\\\"explicit_zero_dividend_assumption\\\\\\"],[\\\\\\"d'
    'ividend_treatment\\\\\\",\\\\\\"explicit_zero_dividend_assumption\\\\\\"],[\\\\\\"explicit_zero_dividend_ass'
    'umption\\\\\\",true]]}],[\\\\\\"interpolation_treatment\\\\\\",\\\\\\"none\\\\\\"],[\\\\\\"numerical_boundary\\\\\\",'
    '\\\\\\"provider option values; local validation only\\\\\\"],[\\\\\\"payload_sha256\\\\\\",\\\\\\"bbbbbbbbbbbbb'
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\\\\\\"],[\\\\\\"position_scaling_rule\\\\\\",\\\\\\"per_'
    'underlying_unit_value_times_quantity_times_contract_multiplier\\\\\\"],[\\\\\\"pricing_model_name\\\\\\",'
    '\\\\\\"Synthetic disclosed option model\\\\\\"],[\\\\\\"pricing_model_version\\\\\\",\\\\\\"model-v2\\\\\\"],[\\\\\\"'
    'producer_calculated_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:05.000000Z\\\\\\"}],[\\\\\\"produce'
    'r_name\\\\\\",\\\\\\"Synthetic Scenario Provider\\\\\\"],[\\\\\\"producer_version\\\\\\",\\\\\\"provider-v3\\\\\\"],['
    '\\\\\\"rate_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"rate_compounding_conversion\\\\\\",\\\\\\"continuous equi'
    'valent\\\\\\"],[\\\\\\"rate_currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"rate_curve_identity\\\\\\",\\\\\\"synthetic-usd-c'
    'urve-20300102\\\\\\"],[\\\\\\"rate_day_count_convention\\\\\\",\\\\\\"actual_365\\\\\\"],[\\\\\\"rate_effective_da'
    'te\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"rate_interpolation\\\\\\",\\\\\\"none\\\\\\"],[\\\\\\"rate_r'
    'emaining_tenor_treatment\\\\\\",\\\\\\"remaining calendar tenor\\\\\\"],[\\\\\\"rate_source\\\\\\",\\\\\\"Syntheti'
    'c USD curve\\\\\\"]]}],[\\\\\\"remaining_time_rule\\\\\\",\\\\\\"expiration_minus_valuation_date_calendar_da'
    'ys\\\\\\"],[\\\\\\"request_id\\\\\\",\\\\\\"scenario-request-001\\\\\\"],[\\\\\\"settlement_treatment\\\\\\",\\\\\\"phys'
    'ical settlement at declared terms\\\\\\"],[\\\\\\"skew_treatment\\\\\\",\\\\\\"preserve leg-level base diffe'
    'rences\\\\\\"],[\\\\\\"status\\\\\\",\\\\\\"active_authoritative_provider_calculated\\\\\\"],[\\\\\\"surface_treat'
    'ment\\\\\\",\\\\\\"actual leg IV parallel shock\\\\\\"],[\\\\\\"term_treatment\\\\\\",\\\\\\"remaining tenor per s'
    'cenario\\\\\\"]]}],[\\\\\\"scenario_identity\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",0],[\\\\\\"iv_chang'
    'e\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"underlying_move\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],['
    '\\\\\\"valuation_time\\\\\\",\\\\\\"immediate\\\\\\"]]}],[\\\\\\"scenario_pricing_dependency\\\\\\",{\\\\\\"$map\\\\\\":'
    '[[\\\\\\"calculation_id\\\\\\",\\\\\\"scenario-pricing-calculation-001\\\\\\"],[\\\\\\"identity\\\\\\",{\\\\\\"$list\\'
    '\\\\":[\\\\\\"nonexpiration_scenario_pricing\\\\\\",\\\\\\"authoritative-provider-option-scenario-pricing-e'
    'vidence\\\\\\",\\\\\\"v0.1\\\\\\"]}]]}],[\\\\\\"schema_version\\\\\\",\\\\\\"v0.1\\\\\\"],[\\\\\\"structure_costs_depend'
    'ency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\"scenario-valuation-costs\\\\\\"],[\\\\\\"identity\\'
    '\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"structure_costs\\\\\\",\\\\\\"exact-structure-costs\\\\\\",\\\\\\"v0.2\\\\\\"]}]]}],[\\\\'
    '\\"tail_pricing_dependency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\"calculation-3c7e\\\\\\"],['
    '\\\\\\"identity\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail_pricing\\\\\\",\\\\\\"nearest-observed-delta-wing-tail-relat'
    'ive-pricing\\\\\\",\\\\\\"v0.2\\\\\\"]}],[\\\\\\"use\\\\\\",\\\\\\"context_only\\\\\\"]]}],[\\\\\\"valuation_source\\\\\\",'
    '\\\\\\"authoritative_provider_nonexpiration\\\\\\"]]}\\"],[\\"remaining_calendar_days\\",60],[\\"scenario_'
    'identity\\",{\\"$map\\":[[\\"days_forward\\",0],[\\"iv_change\\",{\\"$decimal\\":\\"0.0\\"}],[\\"underlying_'
    'move\\",{\\"$decimal\\":\\"0.0\\"}],[\\"valuation_time\\",\\"immediate\\"]]}],[\\"shocked_leg_ivs_exact\\",'
    '{\\"$list\\":[{\\"$decimal\\":\\"0.200\\"}]}],[\\"shocked_underlying_exact\\",{\\"$decimal\\":\\"100.0000\\"'
    '}],[\\"stable_after_cost_pnl_repr\\",\\"106.25\\"],[\\"stable_base_underlying_repr\\",\\"100.0\\"],[\\"st'
    'able_entry_cost_repr\\",\\"141.25\\"],[\\"stable_exit_cost_repr\\",\\"2.5\\"],[\\"stable_gross_value_rep'
    'r\\",\\"250.0\\"],[\\"stable_net_liquidation_repr\\",\\"247.5\\"],[\\"stable_return_on_entry_cost_repr\\"'
    ',\\"0.7522123893805309\\"],[\\"valuation_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"valuation_source\\",\\'
    '"authoritative_provider_nonexpiration\\"]]},{\\"$map\\":[[\\"base_leg_ivs_exact\\",{\\"$list\\":[{\\"$de'
    'cimal\\":\\"0.20\\"}]}],[\\"base_underlying_exact\\",{\\"$decimal\\":\\"100.000\\"}],[\\"exit_cost_assumpt'
    'ion_exact\\",{\\"$decimal\\":\\"2.50\\"}],[\\"expiration_per_leg_payoffs_exact\\",{\\"$list\\":[]}],[\\"gr'
    'oss_position_value_exact\\",{\\"$decimal\\":\\"300.00\\"}],[\\"loss_is_within_entry_cost\\",true],[\\"pr'
    'icing_methodology\\",\\"{\\\\\\"$map\\\\\\":[[\\\\\\"base_iv_source\\\\\\",\\\\\\"ScenarioPricing_v0.1_actual_str'
    'ucture_leg_iv_evidence\\\\\\"],[\\\\\\"base_underlying_source\\\\\\",\\\\\\"StructureCosts_v0.2_underlying_p'
    'rice_exact\\\\\\"],[\\\\\\"entry_cost_rule\\\\\\",\\\\\\"StructureCosts_v0.2_stable_total_entry_cost_float\\\\'
    '\\"],[\\\\\\"exit_cost_rule\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"methodology\\\\\\",\\\\\\"explicit_fixture_exit_cost_v'
    '0.1\\\\\\"],[\\\\\\"source\\\\\\",\\\\\\"explicit_scenario_specific_decimal_assumption\\\\\\"]]}],[\\\\\\"expirati'
    'on_rule\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"active\\\\\\",false],[\\\\\\"call_formula\\\\\\",\\\\\\"max(shocked_underlyi'
    'ng-strike,0)*quantity*multiplier\\\\\\"],[\\\\\\"external_expiration_value\\\\\\",\\\\\\"prohibited\\\\\\"],[\\\\'
    '\\"iv_effect\\\\\\",\\\\\\"none_base_leg_ivs_retained_for_audit\\\\\\"],[\\\\\\"put_formula\\\\\\",\\\\\\"max(strik'
    'e-shocked_underlying,0)*quantity*multiplier\\\\\\"]]}],[\\\\\\"float_conversion_rule\\\\\\",\\\\\\"convert_b'
    'ase_iv_gross_and_exit_cost_once_to_finite_float\\\\\\"],[\\\\\\"limitations\\\\\\",\\\\\\"Internal consisten'
    'cy is validated; self-consistent fabricated dependency artifacts are not cryptographically authe'
    'nticated.\\\\\\"],[\\\\\\"nonexpiration_rule\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"active\\\\\\",true],[\\\\\\"rule\\\\\\",\\\\'
    '\\"consume_authoritative_gross_value_without_repricing\\\\\\"]]}],[\\\\\\"provider_disclosure\\\\\\",{\\\\\\"'
    '$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\"scenario-pricing-calculation-001\\\\\\"],[\\\\\\"dividend_method'
    'ology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"dividend_coverage_end_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-15\\\\\\"}]'
    ',[\\\\\\"dividend_coverage_start_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"dividend_source\\'
    '\\\\",\\\\\\"explicit_zero_dividend_assumption\\\\\\"],[\\\\\\"dividend_treatment\\\\\\",\\\\\\"explicit_zero_div'
    'idend_assumption\\\\\\"],[\\\\\\"explicit_zero_dividend_assumption\\\\\\",true]]}],[\\\\\\"interpolation_tre'
    'atment\\\\\\",\\\\\\"none\\\\\\"],[\\\\\\"numerical_boundary\\\\\\",\\\\\\"provider option values; local validatio'
    'n only\\\\\\"],[\\\\\\"payload_sha256\\\\\\",\\\\\\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
    'bbbbbbbb\\\\\\"],[\\\\\\"position_scaling_rule\\\\\\",\\\\\\"per_underlying_unit_value_times_quantity_times_'
    'contract_multiplier\\\\\\"],[\\\\\\"pricing_model_name\\\\\\",\\\\\\"Synthetic disclosed option model\\\\\\"],['
    '\\\\\\"pricing_model_version\\\\\\",\\\\\\"model-v2\\\\\\"],[\\\\\\"producer_calculated_at\\\\\\",{\\\\\\"$datetime\\\\'
    '\\":\\\\\\"2030-01-02T15:30:05.000000Z\\\\\\"}],[\\\\\\"producer_name\\\\\\",\\\\\\"Synthetic Scenario Provider\\'
    '\\\\"],[\\\\\\"producer_version\\\\\\",\\\\\\"provider-v3\\\\\\"],[\\\\\\"rate_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\'
    '\\"rate_compounding_conversion\\\\\\",\\\\\\"continuous equivalent\\\\\\"],[\\\\\\"rate_currency\\\\\\",\\\\\\"USD\\'
    '\\\\"],[\\\\\\"rate_curve_identity\\\\\\",\\\\\\"synthetic-usd-curve-20300102\\\\\\"],[\\\\\\"rate_day_count_conv'
    'ention\\\\\\",\\\\\\"actual_365\\\\\\"],[\\\\\\"rate_effective_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],'
    '[\\\\\\"rate_interpolation\\\\\\",\\\\\\"none\\\\\\"],[\\\\\\"rate_remaining_tenor_treatment\\\\\\",\\\\\\"remaining '
    'calendar tenor\\\\\\"],[\\\\\\"rate_source\\\\\\",\\\\\\"Synthetic USD curve\\\\\\"]]}],[\\\\\\"remaining_time_rul'
    'e\\\\\\",\\\\\\"expiration_minus_valuation_date_calendar_days\\\\\\"],[\\\\\\"request_id\\\\\\",\\\\\\"scenario-re'
    'quest-001\\\\\\"],[\\\\\\"settlement_treatment\\\\\\",\\\\\\"physical settlement at declared terms\\\\\\"],[\\\\\\'
    '"skew_treatment\\\\\\",\\\\\\"preserve leg-level base differences\\\\\\"],[\\\\\\"status\\\\\\",\\\\\\"active_auth'
    'oritative_provider_calculated\\\\\\"],[\\\\\\"surface_treatment\\\\\\",\\\\\\"actual leg IV parallel shock\\\\'
    '\\"],[\\\\\\"term_treatment\\\\\\",\\\\\\"remaining tenor per scenario\\\\\\"]]}],[\\\\\\"scenario_identity\\\\\\",'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",7],[\\\\\\"iv_change\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.2\\\\\\"}],[\\\\\\"'
    'underlying_move\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.1\\\\\\"}],[\\\\\\"valuation_time\\\\\\",\\\\\\"days_forward\\\\\\"'
    ']]}],[\\\\\\"scenario_pricing_dependency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\"scenario-pr'
    'icing-calculation-001\\\\\\"],[\\\\\\"identity\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"nonexpiration_scenario_pricing\\'
    '\\\\",\\\\\\"authoritative-provider-option-scenario-pricing-evidence\\\\\\",\\\\\\"v0.1\\\\\\"]}]]}],[\\\\\\"sche'
    'ma_version\\\\\\",\\\\\\"v0.1\\\\\\"],[\\\\\\"structure_costs_dependency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation'
    '_id\\\\\\",\\\\\\"scenario-valuation-costs\\\\\\"],[\\\\\\"identity\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"structure_costs\\'
    '\\\\",\\\\\\"exact-structure-costs\\\\\\",\\\\\\"v0.2\\\\\\"]}]]}],[\\\\\\"tail_pricing_dependency\\\\\\",{\\\\\\"$map\\'
    '\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\"calculation-3c7e\\\\\\"],[\\\\\\"identity\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tai'
    'l_pricing\\\\\\",\\\\\\"nearest-observed-delta-wing-tail-relative-pricing\\\\\\",\\\\\\"v0.2\\\\\\"]}],[\\\\\\"use'
    '\\\\\\",\\\\\\"context_only\\\\\\"]]}],[\\\\\\"valuation_source\\\\\\",\\\\\\"authoritative_provider_nonexpiration'
    '\\\\\\"]]}\\"],[\\"remaining_calendar_days\\",53],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forward\\",'
    '7],[\\"iv_change\\",{\\"$decimal\\":\\"0.2\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.1\\"}],[\\"valuat'
    'ion_time\\",\\"days_forward\\"]]}],[\\"shocked_leg_ivs_exact\\",{\\"$list\\":[{\\"$decimal\\":\\"0.240\\"}]'
    '}],[\\"shocked_underlying_exact\\",{\\"$decimal\\":\\"110.0000\\"}],[\\"stable_after_cost_pnl_repr\\",\\"'
    '156.25\\"],[\\"stable_base_underlying_repr\\",\\"100.0\\"],[\\"stable_entry_cost_repr\\",\\"141.25\\"],[\\'
    '"stable_exit_cost_repr\\",\\"2.5\\"],[\\"stable_gross_value_repr\\",\\"300.0\\"],[\\"stable_net_liquidat'
    'ion_repr\\",\\"297.5\\"],[\\"stable_return_on_entry_cost_repr\\",\\"1.1061946902654867\\"],[\\"valuation'
    '_date\\",{\\"$date\\":\\"2030-01-09\\"}],[\\"valuation_source\\",\\"authoritative_provider_nonexpiration'
    '\\"]]},{\\"$map\\":[[\\"base_leg_ivs_exact\\",{\\"$list\\":[{\\"$decimal\\":\\"0.20\\"}]}],[\\"base_underlyi'
    'ng_exact\\",{\\"$decimal\\":\\"100.000\\"}],[\\"exit_cost_assumption_exact\\",{\\"$decimal\\":\\"2.50\\"}],'
    '[\\"expiration_per_leg_payoffs_exact\\",{\\"$list\\":[]}],[\\"gross_position_value_exact\\",{\\"$decima'
    'l\\":\\"200.00\\"}],[\\"loss_is_within_entry_cost\\",true],[\\"pricing_methodology\\",\\"{\\\\\\"$map\\\\\\":['
    '[\\\\\\"base_iv_source\\\\\\",\\\\\\"ScenarioPricing_v0.1_actual_structure_leg_iv_evidence\\\\\\"],[\\\\\\"base'
    '_underlying_source\\\\\\",\\\\\\"StructureCosts_v0.2_underlying_price_exact\\\\\\"],[\\\\\\"entry_cost_rule\\'
    '\\\\",\\\\\\"StructureCosts_v0.2_stable_total_entry_cost_float\\\\\\"],[\\\\\\"exit_cost_rule\\\\\\",{\\\\\\"$map'
    '\\\\\\":[[\\\\\\"methodology\\\\\\",\\\\\\"explicit_fixture_exit_cost_v0.1\\\\\\"],[\\\\\\"source\\\\\\",\\\\\\"explicit'
    '_scenario_specific_decimal_assumption\\\\\\"]]}],[\\\\\\"expiration_rule\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"activ'
    'e\\\\\\",false],[\\\\\\"call_formula\\\\\\",\\\\\\"max(shocked_underlying-strike,0)*quantity*multiplier\\\\\\"]'
    ',[\\\\\\"external_expiration_value\\\\\\",\\\\\\"prohibited\\\\\\"],[\\\\\\"iv_effect\\\\\\",\\\\\\"none_base_leg_ivs'
    '_retained_for_audit\\\\\\"],[\\\\\\"put_formula\\\\\\",\\\\\\"max(strike-shocked_underlying,0)*quantity*mult'
    'iplier\\\\\\"]]}],[\\\\\\"float_conversion_rule\\\\\\",\\\\\\"convert_base_iv_gross_and_exit_cost_once_to_fi'
    'nite_float\\\\\\"],[\\\\\\"limitations\\\\\\",\\\\\\"Internal consistency is validated; self-consistent fabr'
    'icated dependency artifacts are not cryptographically authenticated.\\\\\\"],[\\\\\\"nonexpiration_rul'
    'e\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"active\\\\\\",true],[\\\\\\"rule\\\\\\",\\\\\\"consume_authoritative_gross_value_w'
    'ithout_repricing\\\\\\"]]}],[\\\\\\"provider_disclosure\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\'
    '"scenario-pricing-calculation-001\\\\\\"],[\\\\\\"dividend_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"dividen'
    'd_coverage_end_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-15\\\\\\"}],[\\\\\\"dividend_coverage_start_date\\\\\\'
    '",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"dividend_source\\\\\\",\\\\\\"explicit_zero_dividend_assump'
    'tion\\\\\\"],[\\\\\\"dividend_treatment\\\\\\",\\\\\\"explicit_zero_dividend_assumption\\\\\\"],[\\\\\\"explicit_z'
    'ero_dividend_assumption\\\\\\",true]]}],[\\\\\\"interpolation_treatment\\\\\\",\\\\\\"none\\\\\\"],[\\\\\\"numeric'
    'al_boundary\\\\\\",\\\\\\"provider option values; local validation only\\\\\\"],[\\\\\\"payload_sha256\\\\\\",\\'
    '\\\\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\\\\\\"],[\\\\\\"position_scaling_r'
    'ule\\\\\\",\\\\\\"per_underlying_unit_value_times_quantity_times_contract_multiplier\\\\\\"],[\\\\\\"pricing'
    '_model_name\\\\\\",\\\\\\"Synthetic disclosed option model\\\\\\"],[\\\\\\"pricing_model_version\\\\\\",\\\\\\"mod'
    'el-v2\\\\\\"],[\\\\\\"producer_calculated_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:05.000000Z\\\\\\'
    '"}],[\\\\\\"producer_name\\\\\\",\\\\\\"Synthetic Scenario Provider\\\\\\"],[\\\\\\"producer_version\\\\\\",\\\\\\"pr'
    'ovider-v3\\\\\\"],[\\\\\\"rate_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"rate_compounding_conversion\\\\\\",\\\\\\'
    '"continuous equivalent\\\\\\"],[\\\\\\"rate_currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"rate_curve_identity\\\\\\",\\\\\\'
    '"synthetic-usd-curve-20300102\\\\\\"],[\\\\\\"rate_day_count_convention\\\\\\",\\\\\\"actual_365\\\\\\"],[\\\\\\"r'
    'ate_effective_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"rate_interpolation\\\\\\",\\\\\\"none\\'
    '\\\\"],[\\\\\\"rate_remaining_tenor_treatment\\\\\\",\\\\\\"remaining calendar tenor\\\\\\"],[\\\\\\"rate_source\\'
    '\\\\",\\\\\\"Synthetic USD curve\\\\\\"]]}],[\\\\\\"remaining_time_rule\\\\\\",\\\\\\"expiration_minus_valuation_'
    'date_calendar_days\\\\\\"],[\\\\\\"request_id\\\\\\",\\\\\\"scenario-request-001\\\\\\"],[\\\\\\"settlement_treatm'
    'ent\\\\\\",\\\\\\"physical settlement at declared terms\\\\\\"],[\\\\\\"skew_treatment\\\\\\",\\\\\\"preserve leg-'
    'level base differences\\\\\\"],[\\\\\\"status\\\\\\",\\\\\\"active_authoritative_provider_calculated\\\\\\"],[\\'
    '\\\\"surface_treatment\\\\\\",\\\\\\"actual leg IV parallel shock\\\\\\"],[\\\\\\"term_treatment\\\\\\",\\\\\\"remai'
    'ning tenor per scenario\\\\\\"]]}],[\\\\\\"scenario_identity\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",'
    '0],[\\\\\\"iv_change\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.1\\\\\\"}],[\\\\\\"underlying_move\\\\\\",{\\\\\\"$decimal\\\\\\'
    '":\\\\\\"-0.05\\\\\\"}],[\\\\\\"valuation_time\\\\\\",\\\\\\"holding_horizon\\\\\\"]]}],[\\\\\\"scenario_pricing_depe'
    'ndency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\"scenario-pricing-calculation-001\\\\\\"],[\\\\\\'
    '"identity\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"nonexpiration_scenario_pricing\\\\\\",\\\\\\"authoritative-provider-'
    'option-scenario-pricing-evidence\\\\\\",\\\\\\"v0.1\\\\\\"]}]]}],[\\\\\\"schema_version\\\\\\",\\\\\\"v0.1\\\\\\"],[\\'
    '\\\\"structure_costs_dependency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\"scenario-valuation-'
    'costs\\\\\\"],[\\\\\\"identity\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"structure_costs\\\\\\",\\\\\\"exact-structure-costs\\\\'
    '\\",\\\\\\"v0.2\\\\\\"]}]]}],[\\\\\\"tail_pricing_dependency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\'
    '\\"calculation-3c7e\\\\\\"],[\\\\\\"identity\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail_pricing\\\\\\",\\\\\\"nearest-obser'
    'ved-delta-wing-tail-relative-pricing\\\\\\",\\\\\\"v0.2\\\\\\"]}],[\\\\\\"use\\\\\\",\\\\\\"context_only\\\\\\"]]}],['
    '\\\\\\"valuation_source\\\\\\",\\\\\\"authoritative_provider_nonexpiration\\\\\\"]]}\\"],[\\"remaining_calenda'
    'r_days\\",46],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forward\\",0],[\\"iv_change\\",{\\"$decimal\\"'
    ':\\"-0.1\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"-0.05\\"}],[\\"valuation_time\\",\\"holding_horizon'
    '\\"]]}],[\\"shocked_leg_ivs_exact\\",{\\"$list\\":[{\\"$decimal\\":\\"0.180\\"}]}],[\\"shocked_underlying_'
    'exact\\",{\\"$decimal\\":\\"95.00000\\"}],[\\"stable_after_cost_pnl_repr\\",\\"56.25\\"],[\\"stable_base_u'
    'nderlying_repr\\",\\"100.0\\"],[\\"stable_entry_cost_repr\\",\\"141.25\\"],[\\"stable_exit_cost_repr\\",\\'
    '"2.5\\"],[\\"stable_gross_value_repr\\",\\"200.0\\"],[\\"stable_net_liquidation_repr\\",\\"197.5\\"],[\\"s'
    'table_return_on_entry_cost_repr\\",\\"0.39823008849557523\\"],[\\"valuation_date\\",{\\"$date\\":\\"2030'
    '-01-16\\"}],[\\"valuation_source\\",\\"authoritative_provider_nonexpiration\\"]]},{\\"$map\\":[[\\"base_'
    'leg_ivs_exact\\",{\\"$list\\":[{\\"$decimal\\":\\"0.20\\"}]}],[\\"base_underlying_exact\\",{\\"$decimal\\":'
    '\\"100.000\\"}],[\\"exit_cost_assumption_exact\\",{\\"$decimal\\":\\"0\\"}],[\\"expiration_per_leg_payoff'
    's_exact\\",{\\"$list\\":[{\\"$decimal\\":\\"1000.0000\\"}]}],[\\"gross_position_value_exact\\",{\\"$decima'
    'l\\":\\"1000.0000\\"}],[\\"loss_is_within_entry_cost\\",true],[\\"pricing_methodology\\",\\"{\\\\\\"$map\\\\\\'
    '":[[\\\\\\"base_iv_source\\\\\\",\\\\\\"ScenarioPricing_v0.1_actual_structure_leg_iv_evidence\\\\\\"],[\\\\\\"b'
    'ase_underlying_source\\\\\\",\\\\\\"StructureCosts_v0.2_underlying_price_exact\\\\\\"],[\\\\\\"entry_cost_ru'
    'le\\\\\\",\\\\\\"StructureCosts_v0.2_stable_total_entry_cost_float\\\\\\"],[\\\\\\"exit_cost_rule\\\\\\",{\\\\\\"$'
    'map\\\\\\":[[\\\\\\"methodology\\\\\\",\\\\\\"explicit_fixture_exit_cost_v0.1\\\\\\"],[\\\\\\"source\\\\\\",\\\\\\"expli'
    'cit_scenario_specific_decimal_assumption\\\\\\"]]}],[\\\\\\"expiration_rule\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"ac'
    'tive\\\\\\",true],[\\\\\\"call_formula\\\\\\",\\\\\\"max(shocked_underlying-strike,0)*quantity*multiplier\\\\\\'
    '"],[\\\\\\"external_expiration_value\\\\\\",\\\\\\"prohibited\\\\\\"],[\\\\\\"iv_effect\\\\\\",\\\\\\"none_base_leg_i'
    'vs_retained_for_audit\\\\\\"],[\\\\\\"put_formula\\\\\\",\\\\\\"max(strike-shocked_underlying,0)*quantity*mu'
    'ltiplier\\\\\\"]]}],[\\\\\\"float_conversion_rule\\\\\\",\\\\\\"convert_base_iv_gross_and_exit_cost_once_to_'
    'finite_float\\\\\\"],[\\\\\\"limitations\\\\\\",\\\\\\"Internal consistency is validated; self-consistent fa'
    'bricated dependency artifacts are not cryptographically authenticated.\\\\\\"],[\\\\\\"nonexpiration_r'
    'ule\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"active\\\\\\",false],[\\\\\\"rule\\\\\\",\\\\\\"consume_authoritative_gross_valu'
    'e_without_repricing\\\\\\"]]}],[\\\\\\"provider_disclosure\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"external_expiration'
    '_value\\\\\\",\\\\\\"prohibited\\\\\\"],[\\\\\\"status\\\\\\",\\\\\\"inactive_for_expiration\\\\\\"]]}],[\\\\\\"scenario'
    '_identity\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",0],[\\\\\\"iv_change\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0'
    '.5\\\\\\"}],[\\\\\\"underlying_move\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.1\\\\\\"}],[\\\\\\"valuation_time\\\\\\",\\\\\\"ex'
    'piration\\\\\\"]]}],[\\\\\\"scenario_pricing_dependency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\'
    '"scenario-pricing-calculation-001\\\\\\"],[\\\\\\"identity\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"nonexpiration_scena'
    'rio_pricing\\\\\\",\\\\\\"authoritative-provider-option-scenario-pricing-evidence\\\\\\",\\\\\\"v0.1\\\\\\"]}]]'
    '}],[\\\\\\"schema_version\\\\\\",\\\\\\"v0.1\\\\\\"],[\\\\\\"structure_costs_dependency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\'
    '"calculation_id\\\\\\",\\\\\\"scenario-valuation-costs\\\\\\"],[\\\\\\"identity\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"stru'
    'cture_costs\\\\\\",\\\\\\"exact-structure-costs\\\\\\",\\\\\\"v0.2\\\\\\"]}]]}],[\\\\\\"tail_pricing_dependency\\\\\\'
    '",{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_id\\\\\\",\\\\\\"calculation-3c7e\\\\\\"],[\\\\\\"identity\\\\\\",{\\\\\\"$list\\'
    '\\\\":[\\\\\\"tail_pricing\\\\\\",\\\\\\"nearest-observed-delta-wing-tail-relative-pricing\\\\\\",\\\\\\"v0.2\\\\\\"'
    ']}],[\\\\\\"use\\\\\\",\\\\\\"context_only\\\\\\"]]}],[\\\\\\"valuation_source\\\\\\",\\\\\\"terminal_intrinsic_expir'
    'ation\\\\\\"]]}\\"],[\\"remaining_calendar_days\\",0],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forwar'
    'd\\",0],[\\"iv_change\\",{\\"$decimal\\":\\"0.5\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.1\\"}],[\\"va'
    'luation_time\\",\\"expiration\\"]]}],[\\"shocked_leg_ivs_exact\\",{\\"$list\\":[{\\"$decimal\\":\\"0.300\\"'
    '}]}],[\\"shocked_underlying_exact\\",{\\"$decimal\\":\\"110.0000\\"}],[\\"stable_after_cost_pnl_repr\\",'
    '\\"858.75\\"],[\\"stable_base_underlying_repr\\",\\"100.0\\"],[\\"stable_entry_cost_repr\\",\\"141.25\\"],'
    '[\\"stable_exit_cost_repr\\",\\"0.0\\"],[\\"stable_gross_value_repr\\",\\"1000.0\\"],[\\"stable_net_liqui'
    'dation_repr\\",\\"1000.0\\"],[\\"stable_return_on_entry_cost_repr\\",\\"6.079646017699115\\"],[\\"valuat'
    'ion_date\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"valuation_source\\",\\"terminal_intrinsic_expiration\\"]]'
    '}]}],[\\"cross_dependency_consistency\\",{\\"$map\\":[[\\"as_of_date\\",\\"exact_equal\\"],[\\"expiration'
    '\\",\\"exactly_one_tail_match\\"],[\\"leg_identity_and_multiplier\\",\\"exact_equal\\"],[\\"structure\\",'
    '\\"exact_equal\\"],[\\"underlying\\",\\"exact_equal\\"]]}],[\\"entry_cost_rule\\",\\"StructureCosts_v0.2_'
    'stable_total_entry_cost_float\\"],[\\"exit_cost_assumptions\\",{\\"$map\\":[[\\"methodology\\",\\"explic'
    'it_fixture_exit_cost_v0.1\\"],[\\"ordered_values\\",{\\"$list\\":[{\\"$map\\":[[\\"exit_cost\\",{\\"$decim'
    'al\\":\\"2.50\\"}],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forward\\",0],[\\"iv_change\\",{\\"$decima'
    'l\\":\\"0.0\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.0\\"}],[\\"valuation_time\\",\\"immediate\\"]]}]'
    ']},{\\"$map\\":[[\\"exit_cost\\",{\\"$decimal\\":\\"2.50\\"}],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_'
    'forward\\",7],[\\"iv_change\\",{\\"$decimal\\":\\"0.2\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.1\\"}]'
    ',[\\"valuation_time\\",\\"days_forward\\"]]}]]},{\\"$map\\":[[\\"exit_cost\\",{\\"$decimal\\":\\"2.50\\"}],['
    '\\"scenario_identity\\",{\\"$map\\":[[\\"days_forward\\",0],[\\"iv_change\\",{\\"$decimal\\":\\"-0.1\\"}],[\\'
    '"underlying_move\\",{\\"$decimal\\":\\"-0.05\\"}],[\\"valuation_time\\",\\"holding_horizon\\"]]}]]},{\\"$m'
    'ap\\":[[\\"exit_cost\\",{\\"$decimal\\":\\"0\\"}],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forward\\",0'
    '],[\\"iv_change\\",{\\"$decimal\\":\\"0.5\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.1\\"}],[\\"valuati'
    'on_time\\",\\"expiration\\"]]}]]}]}]]}],[\\"expiration_payoff_rule\\",{\\"$map\\":[[\\"arithmetic\\",\\"De'
    'cimal_precision_34_ROUND_HALF_EVEN\\"],[\\"call\\",\\"max(shocked_underlying-strike,0)*quantity*mult'
    'iplier\\"],[\\"external_value\\",\\"prohibited\\"],[\\"iv_independent\\",true],[\\"put\\",\\"max(strike-sh'
    'ocked_underlying,0)*quantity*multiplier\\"]]}],[\\"float_conversion_rule\\",{\\"$map\\":[[\\"converted'
    '\\",{\\"$list\\":[\\"base_leg_iv\\",\\"gross_position_value\\",\\"exit_cost\\"]}],[\\"decimal_context\\",\\"'
    'precision_34_ROUND_HALF_EVEN\\"],[\\"finite_required\\",true],[\\"stable_cost_floats\\",{\\"$list\\":[\\'
    '"base_underlying_price\\",\\"entry_cost_basis\\"]}]]}],[\\"iv_shock_rule\\",\\"actual_leg_base_iv_time'
    's_one_plus_decimal_string_iv_change\\"],[\\"limitations\\",\\"Validates internal consistency, not cr'
    'yptographic authenticity; probabilities, expected returns, screening, recommendations, sizing, a'
    'nd execution are outside scope.\\"],[\\"lineage_union_rule\\",{\\"$map\\":[[\\"calculated_dependencies'
    '_are_not_inputs\\",true],[\\"conflicting_overlap\\",\\"reject\\"],[\\"exact_overlap\\",\\"deduplicate\\"]'
    ']}],[\\"net_liquidation_rule\\",\\"max(gross_position_value-exit_cost,0.0)\\"],[\\"nonexpiration_valu'
    'ation_rule\\",\\"consume_authoritative_provider_gross_value_without_repricing\\"],[\\"output_archite'
    'cture\\",{\\"$map\\":[[\\"lineage\\",\\"one_shared_CalculationLineage\\"],[\\"records\\",\\"ordered_Scenar'
    'ioResult_tuple\\"],[\\"result_type\\",\\"ScenarioValuationTransformationResult\\"]]}],[\\"record_metho'
    'dology_disclosure\\",{\\"$map\\":[[\\"schema_keys\\",{\\"$list\\":[\\"base_iv_source\\",\\"base_underlying'
    '_source\\",\\"entry_cost_rule\\",\\"exit_cost_rule\\",\\"expiration_rule\\",\\"float_conversion_rule\\",\\'
    '"limitations\\",\\"nonexpiration_rule\\",\\"provider_disclosure\\",\\"scenario_identity\\",\\"scenario_p'
    'ricing_dependency\\",\\"schema_version\\",\\"structure_costs_dependency\\",\\"tail_pricing_dependency\\'
    '",\\"valuation_source\\"]}],[\\"serializer\\",\\"canonicalize_lineage_parameters\\"]]}],[\\"scenario_de'
    'claration\\",{\\"$map\\":[[\\"ordered_scenarios\\",{\\"$list\\":[{\\"$map\\":[[\\"days_forward\\",0],[\\"iv_'
    'change\\",{\\"$decimal\\":\\"0.0\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.0\\"}],[\\"valuation_time\\'
    '",\\"immediate\\"]]},{\\"$map\\":[[\\"days_forward\\",7],[\\"iv_change\\",{\\"$decimal\\":\\"0.2\\"}],[\\"und'
    'erlying_move\\",{\\"$decimal\\":\\"0.1\\"}],[\\"valuation_time\\",\\"days_forward\\"]]},{\\"$map\\":[[\\"day'
    's_forward\\",0],[\\"iv_change\\",{\\"$decimal\\":\\"-0.1\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"-0.0'
    '5\\"}],[\\"valuation_time\\",\\"holding_horizon\\"]]},{\\"$map\\":[[\\"days_forward\\",0],[\\"iv_change\\",'
    '{\\"$decimal\\":\\"0.5\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.1\\"}],[\\"valuation_time\\",\\"expir'
    'ation\\"]]}]}],[\\"scenario_grid_complete\\",false]]}],[\\"scenario_grid_semantics\\",{\\"$map\\":[[\\"c'
    'omplete_rule\\",\\"exact_cartesian_product_per_time_group\\"],[\\"false_rule\\",\\"explicitly_disclose'
    'd_subset\\"],[\\"relative_iv_changes\\",{\\"$list\\":[{\\"$decimal\\":\\"-0.20\\"},{\\"$decimal\\":\\"0\\"},{'
    '\\"$decimal\\":\\"0.20\\"},{\\"$decimal\\":\\"0.50\\"}]}],[\\"underlying_moves\\",{\\"$list\\":[{\\"$decimal\\'
    '":\\"-0.20\\"},{\\"$decimal\\":\\"-0.10\\"},{\\"$decimal\\":\\"-0.05\\"},{\\"$decimal\\":\\"0\\"},{\\"$decimal\\'
    '":\\"0.05\\"},{\\"$decimal\\":\\"0.10\\"},{\\"$decimal\\":\\"0.20\\"}]}]]}],[\\"scenario_ordering\\",{\\"$map'
    '\\":[[\\"keys\\",{\\"$list\\":[\\"valuation_date\\",\\"valuation_time_rank\\",\\"days_forward\\",\\"underlyi'
    'ng_move_decimal\\",\\"iv_change_decimal\\"]}],[\\"valuation_time_rank\\",{\\"$map\\":[[\\"days_forward\\"'
    ',1],[\\"expiration\\",3],[\\"holding_horizon\\",2],[\\"immediate\\",0]]}]]}],[\\"scenario_pricing_depen'
    'dency\\",{\\"$map\\":[[\\"calculated_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:06.000000Z\\"}],[\\"calcul'
    'ation_id\\",\\"scenario-pricing-calculation-001\\"],[\\"calculation_type\\",\\"nonexpiration_scenario_'
    'pricing\\"],[\\"methodology_id\\",\\"authoritative-provider-option-scenario-pricing-evidence\\"],[\\"m'
    'ethodology_version\\",\\"v0.1\\"],[\\"parameters_json\\",\\"{\\\\\\"$map\\\\\\":[[\\\\\\"base_underlying_eviden'
    'ce\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"ask_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"101\\\\\\"}],[\\\\\\"base_underlying_pr'
    'ice\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"bid_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"99\\\\\\"}],[\\\\\\"m'
    'idpoint_formula\\\\\\",\\\\\\"bid_price_plus_ask_price_divided_by_2\\\\\\"],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$'
    'datetime\\\\\\":\\\\\\"2030-01-02T15:30:04.000000Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\'
    '\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"scenario-underlying-quote\\\\\\"],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\'
    '\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"source-001\\\\\\"]}],[\\\\\\"underlyi'
    'ng_key\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\'
    '"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}],[\\\\\\"calculation_values\\\\\\",{'
    '\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"base_underlying_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\'
    '\\"estimated_gross_position_value\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"250.00\\\\\\"}],[\\\\\\"leg_values\\\\\\",{\\\\\\'
    '"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"base_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"contract_key\\\\'
    '\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"delivera'
    'ble_id\\\\\\",\\\\\\"standard-100-share\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],['
    '\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underly'
    'ing_key\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\'
    '\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}],[\\\\\\"leg\\\\\\",{\\\\\\"$map\\\\\\":['
    '[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"o'
    'ption_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\'
    '"}],[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"per_underlying_unit_option_value\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"2.50\\\\\\"}],[\\\\\\"remaining_calendar_days\\\\\\",60],[\\\\\\"shocked_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"0.200\\\\\\"}],[\\\\\\"total_leg_value\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"250.00\\\\\\"}]]}]}],[\\\\\\"scenario\\\\\\"'
    ',{\\\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",0],[\\\\\\"iv_change\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\'
    '"underlying_move\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"valuation_time\\\\\\",\\\\\\"immediate\\\\\\"]]'
    '}],[\\\\\\"shocked_underlying_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying_quote_rec'
    'ord_id\\\\\\",\\\\\\"scenario-underlying-quote\\\\\\"],[\\\\\\"valuation_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01'
    '-02\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"base_underlying_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"e'
    'stimated_gross_position_value\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"300.00\\\\\\"}],[\\\\\\"leg_values\\\\\\",{\\\\\\"$l'
    'ist\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"base_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"contract_key\\\\\\",'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable'
    '_id\\\\\\",\\\\\\"standard-100-share\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\'
    '"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying'
    '_key\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"s'
    'ecurity_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}],[\\\\\\"leg\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\'
    '\\"contract_multiplier\\\\\\",100],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"opti'
    'on_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}]'
    ',[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"per_underlying_unit_option_value\\\\\\",{\\\\\\"$decimal\\\\\\"'
    ':\\\\\\"3.00\\\\\\"}],[\\\\\\"remaining_calendar_days\\\\\\",53],[\\\\\\"shocked_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0'
    '.240\\\\\\"}],[\\\\\\"total_leg_value\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"300.00\\\\\\"}]]}]}],[\\\\\\"scenario\\\\\\",{\\'
    '\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",7],[\\\\\\"iv_change\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.2\\\\\\"}],[\\\\\\"un'
    'derlying_move\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.1\\\\\\"}],[\\\\\\"valuation_time\\\\\\",\\\\\\"days_forward\\\\\\"]]'
    '}],[\\\\\\"shocked_underlying_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110.0\\\\\\"}],[\\\\\\"underlying_quote_rec'
    'ord_id\\\\\\",\\\\\\"scenario-underlying-quote\\\\\\"],[\\\\\\"valuation_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01'
    '-09\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"base_underlying_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"e'
    'stimated_gross_position_value\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"200.00\\\\\\"}],[\\\\\\"leg_values\\\\\\",{\\\\\\"$l'
    'ist\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"base_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"contract_key\\\\\\",'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable'
    '_id\\\\\\",\\\\\\"standard-100-share\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\'
    '"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying'
    '_key\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"s'
    'ecurity_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}],[\\\\\\"leg\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\'
    '\\"contract_multiplier\\\\\\",100],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"opti'
    'on_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}]'
    ',[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"per_underlying_unit_option_value\\\\\\",{\\\\\\"$decimal\\\\\\"'
    ':\\\\\\"2.00\\\\\\"}],[\\\\\\"remaining_calendar_days\\\\\\",46],[\\\\\\"shocked_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0'
    '.180\\\\\\"}],[\\\\\\"total_leg_value\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"200.00\\\\\\"}]]}]}],[\\\\\\"scenario\\\\\\",{\\'
    '\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",0],[\\\\\\"iv_change\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.1\\\\\\"}],[\\\\\\"u'
    'nderlying_move\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.05\\\\\\"}],[\\\\\\"valuation_time\\\\\\",\\\\\\"holding_horizon'
    '\\\\\\"]]}],[\\\\\\"shocked_underlying_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95.00\\\\\\"}],[\\\\\\"underlying_quo'
    'te_record_id\\\\\\",\\\\\\"scenario-underlying-quote\\\\\\"],[\\\\\\"valuation_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2'
    '030-01-16\\\\\\"}]]}]}],[\\\\\\"contract_reference_evidence\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"co'
    'ntract_key\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],['
    '\\\\\\"deliverable_id\\\\\\",\\\\\\"standard-100-share\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-0'
    '3-03\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],'
    '[\\\\\\"underlying_key\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"A'
    'RCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}],[\\\\\\"exercise_st'
    'yle\\\\\\",\\\\\\"american\\\\\\"],[\\\\\\"leg\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"exp'
    'iration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quantity'
    '\\\\\\",1],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\'
    '\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:04.000000Z\\\\\\"}],[\\\\\\"propagated_qu'
    'ality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"scenario-reference-0\\\\\\"],[\\\\\\"settle'
    'ment_type\\\\\\",\\\\\\"physical\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"source-001\\\\\\"]}]]}]}],['
    '\\\\\\"dividend_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"dividend_coverage_end_date\\\\\\",{\\\\\\"$date\\\\\\":\\'
    '\\\\"2030-03-15\\\\\\"}],[\\\\\\"dividend_coverage_start_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\'
    '\\\\"dividend_source\\\\\\",\\\\\\"explicit_zero_dividend_assumption\\\\\\"],[\\\\\\"dividend_treatment\\\\\\",\\\\'
    '\\"explicit_zero_dividend_assumption\\\\\\"],[\\\\\\"explicit_zero_dividend_assumption\\\\\\",true]]}],[\\\\'
    '\\"exercise_and_settlement_support\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$list\\\\\\":[\\\\\\"american\\\\\\",\\\\\\"physi'
    'cal\\\\\\"]}]}],[\\\\\\"float_conversion_rule\\\\\\",\\\\\\"none_all_3c7f1_economic_values_remain_decimal\\\\\\'
    '"],[\\\\\\"iv_shock_rule\\\\\\",\\\\\\"base_iv_times_one_plus_decimal_string_iv_change\\\\\\"],[\\\\\\"leg_corr'
    'espondence\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"base_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],'
    '[\\\\\\"contract_key\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD'
    '\\\\\\"],[\\\\\\"deliverable_id\\\\\\",\\\\\\"standard-100-share\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\'
    '"2030-03-03\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0'
    '\\\\\\"}],[\\\\\\"underlying_key\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\'
    '",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}],[\\\\\\"cont'
    'ract_reference_record_id\\\\\\",\\\\\\"scenario-reference-0\\\\\\"],[\\\\\\"exercise_style\\\\\\",\\\\\\"american\\'
    '\\\\"],[\\\\\\"implied_volatility_record_id\\\\\\",\\\\\\"scenario-iv-0\\\\\\"],[\\\\\\"leg\\\\\\",{\\\\\\"$map\\\\\\":[[\\'
    '\\\\"contract_multiplier\\\\\\",100],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"opt'
    'ion_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}'
    '],[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"settlement_type\\\\\\",\\\\\\"physical\\\\\\"]]}]}],[\\\\\\"leg_i'
    'v_evidence\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_key\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract'
    '_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",\\\\\\"standard-100-sha'
    're\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\'
    '"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying_key\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\'
    '"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"'
    '],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}],[\\\\\\"dividend_input_description\\\\\\",\\\\\\"Explicit zero divid'
    'ends\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"leg\\\\\\",{\\\\\\"$map\\\\\\'
    '":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\'
    '\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0'
    '\\\\\\"}],[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"model_name\\\\\\",\\\\\\"Synthetic IV model\\\\\\"],[\\\\\\"'
    'model_version\\\\\\",\\\\\\"iv-v1\\\\\\"],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:'
    '04.000000Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"rate_input_descripti'
    'on\\\\\\",\\\\\\"Synthetic USD curve\\\\\\"],[\\\\\\"record_id\\\\\\",\\\\\\"scenario-iv-0\\\\\\"],[\\\\\\"session_date\\'
    '\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"source-001\\\\\\"]}'
    '],[\\\\\\"unit_convention\\\\\\",\\\\\\"annualized_decimal_ratio\\\\\\"]]}]}],[\\\\\\"limitations\\\\\\",\\\\\\"Self-'
    'consistent declarations are not provider-authenticated.\\\\\\"],[\\\\\\"output_architecture\\\\\\",{\\\\\\"$'
    'map\\\\\\":[[\\\\\\"construction_boundary\\\\\\",\\\\\\"authoritative_producer_direct_construction\\\\\\"],[\\\\\\'
    '"lineage_scope\\\\\\",\\\\\\"shared_batch\\\\\\"],[\\\\\\"record_type\\\\\\",\\\\\\"NonExpirationScenarioPricingCa'
    'lculation\\\\\\"],[\\\\\\"records_container\\\\\\",\\\\\\"ordered_tuple\\\\\\"]]}],[\\\\\\"position_scaling_rule\\\\'
    '\\",\\\\\\"per_underlying_unit_value_times_quantity_times_contract_multiplier\\\\\\"],[\\\\\\"pricing_meth'
    'odology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"numerical_calculation_boundary\\\\\\",\\\\\\"provider option values; l'
    'ocal validation only\\\\\\"],[\\\\\\"pricing_model_name\\\\\\",\\\\\\"Synthetic disclosed option model\\\\\\"],'
    '[\\\\\\"pricing_model_version\\\\\\",\\\\\\"model-v2\\\\\\"],[\\\\\\"settlement_treatment\\\\\\",\\\\\\"physical sett'
    'lement at declared terms\\\\\\"],[\\\\\\"skew_treatment\\\\\\",\\\\\\"preserve leg-level base differences\\\\\\'
    '"],[\\\\\\"term_treatment\\\\\\",\\\\\\"remaining tenor per scenario\\\\\\"],[\\\\\\"volatility_interpolation\\\\'
    '\\",\\\\\\"none\\\\\\"],[\\\\\\"volatility_surface_treatment\\\\\\",\\\\\\"actual leg IV parallel shock\\\\\\"]]}],'
    '[\\\\\\"producer_identity\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"producer_name\\\\\\",\\\\\\"Synthetic Scenario Provider'
    '\\\\\\"],[\\\\\\"producer_version\\\\\\",\\\\\\"provider-v3\\\\\\"]]}],[\\\\\\"producer_provenance\\\\\\",{\\\\\\"$map\\\\'
    '\\":[[\\\\\\"pricing_payload_sha256\\\\\\",\\\\\\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
    'bbbbbbbb\\\\\\"],[\\\\\\"pricing_request_id\\\\\\",\\\\\\"scenario-request-001\\\\\\"],[\\\\\\"pricing_source_clas'
    'sification\\\\\\",\\\\\\"provider_calculated\\\\\\"],[\\\\\\"producer_calculated_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\'
    '\\\\"2030-01-02T15:30:05.000000Z\\\\\\"}]]}],[\\\\\\"rate_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"rate_compo'
    'unding_conversion\\\\\\",\\\\\\"continuous equivalent\\\\\\"],[\\\\\\"rate_currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"ra'
    'te_curve_identity\\\\\\",\\\\\\"synthetic-usd-curve-20300102\\\\\\"],[\\\\\\"rate_day_count_convention\\\\\\",\\'
    '\\\\"actual_365\\\\\\"],[\\\\\\"rate_effective_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"rate_in'
    'terpolation\\\\\\",\\\\\\"none\\\\\\"],[\\\\\\"rate_remaining_tenor_treatment\\\\\\",\\\\\\"remaining calendar ten'
    'or\\\\\\"],[\\\\\\"rate_source\\\\\\",\\\\\\"Synthetic USD curve\\\\\\"]]}],[\\\\\\"remaining_time_rule\\\\\\",\\\\\\"ex'
    'piration_minus_valuation_date_calendar_days\\\\\\"],[\\\\\\"scenario_definitions\\\\\\",{\\\\\\"$list\\\\\\":[{'
    '\\\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",0],[\\\\\\"iv_change\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"u'
    'nderlying_move\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"valuation_time\\\\\\",\\\\\\"immediate\\\\\\"]]},'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",7],[\\\\\\"iv_change\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.2\\\\\\"}],[\\\\\\"'
    'underlying_move\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.1\\\\\\"}],[\\\\\\"valuation_time\\\\\\",\\\\\\"days_forward\\\\\\"'
    ']]},{\\\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",0],[\\\\\\"iv_change\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.1\\\\\\"}],'
    '[\\\\\\"underlying_move\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.05\\\\\\"}],[\\\\\\"valuation_time\\\\\\",\\\\\\"holding_h'
    'orizon\\\\\\"]]}]}],[\\\\\\"scenario_ordering\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"keys\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"val'
    'uation_date\\\\\\",\\\\\\"valuation_time_rank\\\\\\",\\\\\\"days_forward\\\\\\",\\\\\\"underlying_move_decimal\\\\\\"'
    ',\\\\\\"iv_change_decimal\\\\\\"]}],[\\\\\\"valuation_time_rank\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"days_forward\\\\\\",'
    '1],[\\\\\\"holding_horizon\\\\\\",2],[\\\\\\"immediate\\\\\\",0]]}]]}],[\\\\\\"structure_identity\\\\\\",{\\\\\\"$map'
    '\\\\\\":[[\\\\\\"as_of_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"assumed_portfolio_value\\\\\\",{'
    '\\\\\\"$decimal\\\\\\":\\\\\\"100000.0\\\\\\"}],[\\\\\\"expected_holding_days\\\\\\",14],[\\\\\\"legs\\\\\\",{\\\\\\"$list\\'
    '\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"203'
    '0-03-03\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\\\\\"strike\\\\\\",{\\\\\\"$deci'
    'mal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}]}],[\\\\\\"shared_expiration\\\\\\",{\\\\\\"$d'
    'ate\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"structure_type\\\\\\",\\\\\\"long_call\\\\\\"]]}],[\\\\\\"supported_struct'
    'ure_scope\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"common_expiration\\\\\\",true],[\\\\\\"long_only\\\\\\",true],[\\\\\\"maxi'
    'mum_leg_count\\\\\\",2],[\\\\\\"structure_types\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"long_call\\\\\\",\\\\\\"long_put\\\\\\"'
    ',\\\\\\"long_straddle\\\\\\"]}]]}],[\\\\\\"underlying_shock_rule\\\\\\",\\\\\\"base_underlying_price_times_one_'
    'plus_decimal_string_underlying_move\\\\\\"],[\\\\\\"valuation_date_rules\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"days_'
    'forward\\\\\\",\\\\\\"as_of_date_plus_days_forward_calendar_days\\\\\\"],[\\\\\\"expiration\\\\\\",\\\\\\"rejected'
    '\\\\\\"],[\\\\\\"holding_horizon\\\\\\",\\\\\\"as_of_date_plus_expected_holding_days_calendar_days\\\\\\"],[\\\\\\'
    '"immediate\\\\\\",\\\\\\"as_of_date\\\\\\"]]}]]}\\"],[\\"quality_flags\\",{\\"$list\\":[\\"annualized\\",\\"assum'
    'ption_applied\\"]}],[\\"selected\\",{\\"$map\\":[[\\"actual_leg_iv_tuple\\",{\\"$list\\":[{\\"$map\\":[[\\"b'
    'ase_iv\\",{\\"$decimal\\":\\"0.20\\"}],[\\"contract_key\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"'
    'currency\\",\\"USD\\"],[\\"deliverable_id\\",\\"standard-100-share\\"],[\\"expiration\\",{\\"$date\\":\\"203'
    '0-03-03\\"}],[\\"option_type\\",\\"call\\"],[\\"strike\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying_key\\"'
    ',{\\"$map\\":[[\\"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"sym'
    'bol\\",\\"SPY\\"]]}]]}],[\\"contract_reference_record_id\\",\\"scenario-reference-0\\"],[\\"exercise_sty'
    'le\\",\\"american\\"],[\\"implied_volatility_record_id\\",\\"scenario-iv-0\\"],[\\"leg\\",{\\"$map\\":[[\\"c'
    'ontract_multiplier\\",100],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"option_type\\",\\"call\\"]'
    ',[\\"quantity\\",1],[\\"strike\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying\\",\\"SPY\\"]]}],[\\"settlemen'
    't_type\\",\\"physical\\"]]}]}],[\\"as_of_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"base_underlying_price'
    '\\",{\\"$decimal\\":\\"100\\"}],[\\"declared_nonexpiration_scenarios\\",{\\"$list\\":[{\\"$map\\":[[\\"days_'
    'forward\\",0],[\\"iv_change\\",{\\"$decimal\\":\\"0.0\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.0\\"}]'
    ',[\\"valuation_time\\",\\"immediate\\"]]},{\\"$map\\":[[\\"days_forward\\",7],[\\"iv_change\\",{\\"$decimal'
    '\\":\\"0.2\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.1\\"}],[\\"valuation_time\\",\\"days_forward\\"]]'
    '},{\\"$map\\":[[\\"days_forward\\",0],[\\"iv_change\\",{\\"$decimal\\":\\"-0.1\\"}],[\\"underlying_move\\",{'
    '\\"$decimal\\":\\"-0.05\\"}],[\\"valuation_time\\",\\"holding_horizon\\"]]}]}],[\\"producer_identity\\",{\\'
    '"$map\\":[[\\"payload_sha256\\",\\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\\'
    '"],[\\"pricing_model_name\\",\\"Synthetic disclosed option model\\"],[\\"pricing_model_version\\",\\"mo'
    'del-v2\\"],[\\"producer_name\\",\\"Synthetic Scenario Provider\\"],[\\"producer_version\\",\\"provider-v'
    '3\\"],[\\"request_id\\",\\"scenario-request-001\\"]]}],[\\"structure_identity\\",{\\"$map\\":[[\\"as_of_da'
    'te\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"assumed_portfolio_value\\",{\\"$decimal\\":\\"100000.0\\"}],[\\"ex'
    'pected_holding_days\\",14],[\\"legs\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"expi'
    'ration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"option_type\\",\\"call\\"],[\\"quantity\\",1],[\\"strike\\",{\\"'
    '$decimal\\":\\"100.0\\"}],[\\"underlying\\",\\"SPY\\"]]}]}],[\\"shared_expiration\\",{\\"$date\\":\\"2030-03'
    '-03\\"}],[\\"structure_type\\",\\"long_call\\"]]}]]}]]}],[\\"structure_costs_dependency\\",{\\"$map\\":[['
    '\\"calculated_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:04.000000Z\\"}],[\\"calculation_id\\",\\"scenari'
    'o-valuation-costs\\"],[\\"calculation_type\\",\\"structure_costs\\"],[\\"methodology_id\\",\\"exact-stru'
    'cture-costs\\"],[\\"methodology_version\\",\\"v0.2\\"],[\\"parameters_json\\",\\"{\\\\\\"$map\\\\\\":[[\\\\\\"cal'
    'culation_values\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"commissions_and_fees_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.2'
    '5\\\\\\"}],[\\\\\\"cumulative_repeated_bet_cost_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"141.250\\\\\\"}],[\\\\\\"est'
    'imated_spread_cost_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"20.000\\\\\\"}],[\\\\\\"gamma_exact\\\\\\",{\\\\\\"$decim'
    'al\\\\\\":\\\\\\"2.000\\\\\\"}],[\\\\\\"maximum_loss_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"141.250\\\\\\"}],[\\\\\\"quot'
    'ed_mid_premium_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"120.000\\\\\\"}],[\\\\\\"stable_record_values\\\\\\",{\\\\\\"'
    '$map\\\\\\":[[\\\\\\"commissions_and_fees_repr\\\\\\",\\\\\\"1.25\\\\\\"],[\\\\\\"cumulative_repeated_bet_cost_rep'
    'r\\\\\\",\\\\\\"141.25\\\\\\"],[\\\\\\"estimated_spread_cost_repr\\\\\\",\\\\\\"20.0\\\\\\"],[\\\\\\"gamma_repr\\\\\\",\\\\\\"'
    '2.0\\\\\\"],[\\\\\\"maximum_loss_repr\\\\\\",\\\\\\"141.25\\\\\\"],[\\\\\\"quoted_mid_premium_repr\\\\\\",\\\\\\"120.0\\\\'
    '\\"],[\\\\\\"theta_per_day_repr\\\\\\",\\\\\\"-10.0\\\\\\"],[\\\\\\"total_entry_cost_repr\\\\\\",\\\\\\"141.25\\\\\\"],[\\'
    '\\\\"underlying_price_repr\\\\\\",\\\\\\"100.0\\\\\\"]]}],[\\\\\\"theta_per_day_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"-10.000\\\\\\"}],[\\\\\\"total_entry_cost_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"141.250\\\\\\"}],[\\\\\\"underly'
    'ing_price_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.000\\\\\\"}]]}],[\\\\\\"commission_and_fee_scope\\\\\\",\\\\\\'
    '"entry_only_total_position\\\\\\"],[\\\\\\"commissions_and_fees_usd\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.25\\\\\\"'
    '}],[\\\\\\"gamma_input_unit\\\\\\",\\\\\\"option_value_change_per_usd_squared_per_underlying_unit\\\\\\"],[\\'
    '\\\\"gamma_position_rule\\\\\\",\\\\\\"sum(gamma_per_underlying_unit_per_usd_squared*quantity*contract_m'
    'ultiplier)\\\\\\"],[\\\\\\"greeks_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"dividend_input_description\\\\\\",\\'
    '\\\\"Synthetic dividend input\\\\\\"],[\\\\\\"model_name\\\\\\",\\\\\\"Synthetic Black-Scholes\\\\\\"],[\\\\\\"model'
    '_version\\\\\\",\\\\\\"fixture-v1\\\\\\"],[\\\\\\"rate_input_description\\\\\\",\\\\\\"Synthetic USD curve input\\\\'
    '\\"],[\\\\\\"theta_day_basis\\\\\\",\\\\\\"Provider calendar-day convention\\\\\\"],[\\\\\\"unit_convention\\\\\\",'
    '\\\\\\"Contract-defined canonical units\\\\\\"]]}],[\\\\\\"leg_correspondence\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$m'
    'ap\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\"'
    ',null],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"option_contract_reference_re'
    'cord_id\\\\\\",\\\\\\"cost-call-contract-reference\\\\\\"],[\\\\\\"option_greeks_record_id\\\\\\",\\\\\\"cost-call'
    '-greeks\\\\\\"],[\\\\\\"option_quote_record_id\\\\\\",\\\\\\"cost-call-quote\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"c'
    'all\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying\\'
    '\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"securi'
    'ty_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\'
    '"cost-underlying-quote\\\\\\"]]}]}],[\\\\\\"normalized_evidence\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_refer'
    'ences\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\'
    '"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"exercise_style\\\\\\",\\\\\\"American\\\\\\"],[\\\\\\"expiratio'
    'n\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"last_trade_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03'
    '\\\\\\"}],[\\\\\\"listing_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-09-16\\\\\\"}],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$da'
    'tetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"propaga'
    'ted_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"quantity\\\\\\",1],[\\\\\\"record_id\\\\\\",\\\\\\"cost-call-'
    'contract-reference\\\\\\"],[\\\\\\"settlement_type\\\\\\",\\\\\\"Physical\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$lis'
    't\\\\\\":[\\\\\\"cost-call-contract-reference-source-0\\\\\\"]}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"10'
    '0.0\\\\\\"}],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\"'
    ',\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}]}],[\\\\\\"opt'
    'ion_greeks\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\'
    '",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"dividend_input_description\\\\\\",\\\\\\"Synthetic d'
    'ividend input\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"gamma\\\\\\",{\\\\\\"$'
    'decimal\\\\\\":\\\\\\"0.020\\\\\\"}],[\\\\\\"model_name\\\\\\",\\\\\\"Synthetic Black-Scholes\\\\\\"],[\\\\\\"model_vers'
    'ion\\\\\\",\\\\\\"fixture-v1\\\\\\"],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.00'
    '0002Z\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":'
    '[]}],[\\\\\\"quantity\\\\\\",1],[\\\\\\"rate_input_description\\\\\\",\\\\\\"Synthetic USD curve input\\\\\\"],[\\\\'
    '\\"record_id\\\\\\",\\\\\\"cost-call-greeks\\\\\\"],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\'
    '"}],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"cost-call-greeks-source-0\\\\\\"]}],[\\\\\\"strike\\\\\\",{\\\\'
    '\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"theta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.100\\\\\\"}],[\\\\\\"theta_day_'
    'basis\\\\\\",\\\\\\"Provider calendar-day convention\\\\\\"],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"curr'
    'ency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\'
    '\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"unit_convention\\\\\\",\\\\\\"Contract-defined canonical units\\\\\\"]]'
    '}]}],[\\\\\\"option_quotes\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"ask_premium\\\\\\",{\\\\\\"$decimal\\\\\\'
    '":\\\\\\"1.40\\\\\\"}],[\\\\\\"bid_premium\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.00\\\\\\"}],[\\\\\\"contract_multiplier\\'
    '\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"expiration\\\\\\",{\\\\\\"$'
    'date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.'
    '000002Z\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\'
    '":[]}],[\\\\\\"quantity\\\\\\",1],[\\\\\\"record_id\\\\\\",\\\\\\"cost-call-quote\\\\\\"],[\\\\\\"session_date\\\\\\",{\\'
    '\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"cost-call-quote-source'
    '-0\\\\\\"]}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[['
    '\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\'
    '\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}]}],[\\\\\\"underlying_quote\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"ask_pric'
    'e\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"101.00\\\\\\"}],[\\\\\\"bid_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"99.00\\\\\\"}],[\\'
    '\\\\"midpoint_rule\\\\\\",\\\\\\"(bid_price+ask_price)/2\\\\\\"],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":'
    '\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\'
    '"record_id\\\\\\",\\\\\\"cost-underlying-quote\\\\\\"],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-0'
    '2\\\\\\"}],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"cost-underlying-quote-source-0\\\\\\"]}],[\\\\\\"under'
    'lying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"'
    'security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"underlying_price_exact\\\\\\",{'
    '\\\\\\"$decimal\\\\\\":\\\\\\"100.000\\\\\\"}]]}]]}],[\\\\\\"position_value_unit\\\\\\",\\\\\\"usd\\\\\\"],[\\\\\\"premium_'
    'input_unit\\\\\\",\\\\\\"usd_per_underlying_unit\\\\\\"],[\\\\\\"premium_midpoint_rule\\\\\\",\\\\\\"sum(((bid_pre'
    'mium+ask_premium)/2)*quantity*contract_multiplier)\\\\\\"],[\\\\\\"repeated_bet_count\\\\\\",1],[\\\\\\"spre'
    'ad_cost_rule\\\\\\",\\\\\\"sum(((ask_premium-bid_premium)/2)*quantity*contract_multiplier)\\\\\\"],[\\\\\\"s'
    'pread_cost_scope\\\\\\",\\\\\\"entry_only_midpoint_to_ask\\\\\\"],[\\\\\\"structure_identity\\\\\\",{\\\\\\"$map\\\\'
    '\\":[[\\\\\\"assumed_portfolio_value_repr\\\\\\",\\\\\\"100000.0\\\\\\"],[\\\\\\"expected_holding_days\\\\\\",14],['
    '\\\\\\"legs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"expiration\\\\\\'
    '",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\'
    '\\\\"strike_float_repr\\\\\\",\\\\\\"100.0\\\\\\"],[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}]}],[\\\\\\"structure_typ'
    'e\\\\\\",\\\\\\"long_call\\\\\\"],[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"theta_day_basis\\\\\\",\\\\\\"Provid'
    'er calendar-day convention\\\\\\"],[\\\\\\"theta_input_unit\\\\\\",\\\\\\"usd_per_underlying_unit_per_declar'
    'ed_day_basis\\\\\\"],[\\\\\\"theta_position_rule\\\\\\",\\\\\\"sum(theta_per_underlying_unit_per_declared_da'
    'y_basis*quantity*contract_multiplier)\\\\\\"],[\\\\\\"underlying_price_rule\\\\\\",\\\\\\"(bid_price+ask_pri'
    'ce)/2\\\\\\"],[\\\\\\"underlying_price_unit\\\\\\",\\\\\\"usd_per_underlying_share\\\\\\"]]}\\"],[\\"quality_flag'
    's\\",{\\"$list\\":[\\"decimal_to_float_converted\\",\\"assumption_applied\\"]}],[\\"selected\\",{\\"$map\\"'
    ':[[\\"as_of_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"commissions_and_fees_exact\\",{\\"$decimal\\":\\"1.'
    '25\\"}],[\\"estimated_spread_cost_exact\\",{\\"$decimal\\":\\"20.000\\"}],[\\"maximum_loss_exact\\",{\\"$d'
    'ecimal\\":\\"141.250\\"}],[\\"quoted_mid_premium_exact\\",{\\"$decimal\\":\\"120.000\\"}],[\\"structure_id'
    'entity\\",{\\"$map\\":[[\\"assumed_portfolio_value_repr\\",\\"100000.0\\"],[\\"expected_holding_days\\",1'
    '4],[\\"legs\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"expiration\\",{\\"$date\\":\\"2'
    '030-03-03\\"}],[\\"option_type\\",\\"call\\"],[\\"quantity\\",1],[\\"strike_float_repr\\",\\"100.0\\"],[\\"u'
    'nderlying\\",\\"SPY\\"]]}]}],[\\"structure_type\\",\\"long_call\\"],[\\"underlying\\",\\"SPY\\"]]}],[\\"tota'
    'l_entry_cost_exact\\",{\\"$decimal\\":\\"141.250\\"}],[\\"total_entry_cost_repr\\",\\"141.25\\"],[\\"under'
    'lying_price_exact\\",{\\"$decimal\\":\\"100.000\\"}],[\\"underlying_price_repr\\",\\"100.0\\"]]}]]}],[\\"s'
    'upported_structure_scope\\",{\\"$map\\":[[\\"excluded\\",{\\"$list\\":[\\"shorts\\",\\"spreads\\",\\"exotics'
    '\\"]}],[\\"included\\",{\\"$list\\":[\\"one_long_call\\",\\"one_long_put\\",\\"one_long_straddle\\",\\"posit'
    'ive_long_quantities\\",\\"one_common_underlying\\",\\"one_common_expiration\\"]}]]}],[\\"tail_pricing_'
    'dependency\\",{\\"$map\\":[[\\"calculated_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:05.000000Z\\"}],[\\"c'
    'alculation_id\\",\\"calculation-3c7e\\"],[\\"calculation_type\\",\\"tail_pricing\\"],[\\"methodology_id\\'
    '",\\"nearest-observed-delta-wing-tail-relative-pricing\\"],[\\"methodology_version\\",\\"v0.2\\"],[\\"p'
    'arameters_json\\",\\"{\\\\\\"$map\\\\\\":[[\\\\\\"analytics_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"greeks_divi'
    'dend_input_description\\\\\\",\\\\\\"Synthetic dividend input\\\\\\"],[\\\\\\"greeks_model_name\\\\\\",\\\\\\"Synt'
    'hetic Black-Scholes\\\\\\"],[\\\\\\"greeks_model_version\\\\\\",\\\\\\"fixture-v1\\\\\\"],[\\\\\\"greeks_rate_inpu'
    't_description\\\\\\",\\\\\\"Synthetic USD curve input\\\\\\"],[\\\\\\"greeks_unit_convention\\\\\\",\\\\\\"Contrac'
    't-defined canonical units\\\\\\"],[\\\\\\"iv_dividend_input_description\\\\\\",\\\\\\"Synthetic dividend inp'
    'ut\\\\\\"],[\\\\\\"iv_model_name\\\\\\",\\\\\\"Synthetic Black-Scholes\\\\\\"],[\\\\\\"iv_model_version\\\\\\",\\\\\\"fi'
    'xture-v1\\\\\\"],[\\\\\\"iv_rate_input_description\\\\\\",\\\\\\"Synthetic USD curve input\\\\\\"],[\\\\\\"iv_unit'
    '_convention\\\\\\",\\\\\\"annualized_decimal_ratio\\\\\\"]]}],[\\\\\\"atm_dependency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\'
    '"as_of_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"calculated_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\'
    '\\"2030-01-02T15:30:04.000000Z\\\\\\"}],[\\\\\\"calculation_id\\\\\\",\\\\\\"calculation-3c7d\\\\\\"],[\\\\\\"calcu'
    'lation_type\\\\\\",\\\\\\"volatility_environment\\\\\\"],[\\\\\\"current_atm_observations\\\\\\",{\\\\\\"$list\\\\\\"'
    ':[{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_refe'
    'rence_record_id\\\\\\",\\\\\\"ve-current-0-call-reference\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$'
    'decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"call_iv_record_id\\\\\\",\\\\\\"ve-current-0-call-iv\\\\\\"],[\\\\\\"call_qu'
    'ote_record_id\\\\\\",\\\\\\"ve-current-0-call-quote\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"curren'
    'cy\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_underlying_midpoint\\\\\\",{\\\\\\"'
    '$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.300\\\\\\"}],'
    '[\\\\\\"put_contract_reference_record_id\\\\\\",\\\\\\"ve-current-0-put-reference\\\\\\"],[\\\\\\"put_implied_v'
    'olatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"ve-current-0-put-iv'
    '\\\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"ve-current-0-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal'
    '\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-02-01\\\\\\"}],[\\\\\\"selected_at'
    'm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.300\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-current-0-'
    'call-iv\\\\\\"],[\\\\\\"selected_put_iv_record_id\\\\\\",\\\\\\"ve-current-0-put-iv\\\\\\"],[\\\\\\"selected_strik'
    'e\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],'
    '[\\\\\\"tenor_days\\\\\\",30],[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"unde'
    'rlying_quote_record_id\\\\\\",\\\\\\"ve-current-underlying\\\\\\"]]},{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\'
    '\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference_record_id\\\\\\",\\\\\\"ve-current-1-c'
    'all-reference\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"call_i'
    'v_record_id\\\\\\",\\\\\\"ve-current-1-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"ve-current-1-cal'
    'l-quote\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_i'
    'd\\\\\\",null],[\\\\\\"distance_to_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired'
    '_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.400\\\\\\"}],[\\\\\\"put_contract_reference_record_id\\'
    '\\\\",\\\\\\"ve-current-1-put-reference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.'
    '40\\\\\\"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"ve-current-1-put-iv\\\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\'
    '"ve-current-1-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"expiratio'
    'n\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"selected_atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.400\\\\'
    '\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-current-1-call-iv\\\\\\"],[\\\\\\"selected_put_iv_reco'
    'rd_id\\\\\\",\\\\\\"ve-current-1-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],'
    '[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"tenor_days\\\\\\",60],[\\\\\\"underlyin'
    'g_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"ve-curr'
    'ent-underlying\\\\\\"]]}]}],[\\\\\\"historical_atm_observations\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\'
    '\\"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference_record_id\\\\\\",'
    '\\\\\\"ve-history-0-0-call-reference\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.'
    '19\\\\\\"}],[\\\\\\"call_iv_record_id\\\\\\",\\\\\\"ve-history-0-0-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\'
    '",\\\\\\"ve-history-0-0-call-quote\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD'
    '\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\'
    '\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.200\\\\\\"}],[\\\\\\"put_contr'
    'act_reference_record_id\\\\\\",\\\\\\"ve-history-0-0-put-reference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\'
    '",{\\\\\\"$decimal\\\\\\":\\\\\\"0.21\\\\\\"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"ve-history-0-0-put-iv\\\\\\"],[\\\\\\'
    '"put_quote_record_id\\\\\\",\\\\\\"ve-history-0-0-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\'
    '"100\\\\\\"}]]}]}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-23\\\\\\"}],[\\\\\\"selected_atm_iv\\\\\\"'
    ',{\\\\\\"$decimal\\\\\\":\\\\\\"0.200\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-history-0-0-call-i'
    'v\\\\\\"],[\\\\\\"selected_put_iv_record_id\\\\\\",\\\\\\"ve-history-0-0-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\'
    '",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-24\\\\\\"}],[\\\\\\'
    '"tenor_days\\\\\\",30],[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlyi'
    'ng_quote_record_id\\\\\\",\\\\\\"ve-history-0-underlying\\\\\\"]]},{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\'
    '",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference_record_id\\\\\\",\\\\\\"ve-history-1-0-c'
    'all-reference\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"call_i'
    'v_record_id\\\\\\",\\\\\\"ve-history-1-0-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"ve-history-1-0'
    '-call-quote\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverab'
    'le_id\\\\\\",null],[\\\\\\"distance_to_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"pa'
    'ired_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.210\\\\\\"}],[\\\\\\"put_contract_reference_record'
    '_id\\\\\\",\\\\\\"ve-history-1-0-put-reference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":'
    '\\\\\\"0.22\\\\\\"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"ve-history-1-0-put-iv\\\\\\"],[\\\\\\"put_quote_record_id'
    '\\\\\\",\\\\\\"ve-history-1-0-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\'
    '"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-26\\\\\\"}],[\\\\\\"selected_atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\'
    '\\\\"0.210\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-history-1-0-call-iv\\\\\\"],[\\\\\\"selected'
    '_put_iv_record_id\\\\\\",\\\\\\"ve-history-1-0-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\",{\\\\\\"$decimal\\\\\\":'
    '\\\\\\"100\\\\\\"}],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-27\\\\\\"}],[\\\\\\"tenor_days\\\\\\",30],'
    '[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying_quote_record_id\\\\'
    '\\",\\\\\\"ve-history-1-underlying\\\\\\"]]},{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\'
    '\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference_record_id\\\\\\",\\\\\\"ve-history-2-0-call-reference\\\\\\"],['
    '\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.21\\\\\\"}],[\\\\\\"call_iv_record_id\\\\\\",\\\\\\"'
    've-history-2-0-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"ve-history-2-0-call-quote\\\\\\"],[\\\\'
    '\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\'
    '"distance_to_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied_volatil'
    'ity\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.220\\\\\\"}],[\\\\\\"put_contract_reference_record_id\\\\\\",\\\\\\"ve-histo'
    'ry-2-0-put-reference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.23\\\\\\"}],[\\\\\\"'
    'put_iv_record_id\\\\\\",\\\\\\"ve-history-2-0-put-iv\\\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"ve-history-'
    '2-0-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"expiration\\\\\\",{\\\\\\'
    '"$date\\\\\\":\\\\\\"2030-01-29\\\\\\"}],[\\\\\\"selected_atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.220\\\\\\"}],[\\\\\\"'
    'selected_call_iv_record_id\\\\\\",\\\\\\"ve-history-2-0-call-iv\\\\\\"],[\\\\\\"selected_put_iv_record_id\\\\\\'
    '",\\\\\\"ve-history-2-0-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"s'
    'ession_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-30\\\\\\"}],[\\\\\\"tenor_days\\\\\\",30],[\\\\\\"underlying_midp'
    'oint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"ve-history-2-'
    'underlying\\\\\\"]]}]}],[\\\\\\"historical_median_atm_iv_float_repr\\\\\\",\\\\\\"0.21\\\\\\"],[\\\\\\"historical_'
    'observation_count\\\\\\",3],[\\\\\\"inputs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{'
    '\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"hrv-0\\\\\\"],[\\\\\\"s'
    'ource_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"hrv-0-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",'
    '{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"hrv-1\\\\\\"],[\\\\\\"'
    'source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"hrv-1-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\"'
    ',{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"hrv-2\\\\\\"],[\\\\\\'
    '"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"hrv-2-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\'
    '",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-c'
    'all-iv\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-call-iv-source-0\\\\\\"]}]]},{\\\\\\"'
    '$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"r'
    'ecord_id\\\\\\",\\\\\\"ve-current-0-call-quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current'
    '-0-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"203'
    '0-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-call-reference\\\\\\"],[\\\\\\"sour'
    'ce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\'
    '"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\'
    '\\\\"ve-current-0-put-iv\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-put-iv-source-0'
    '\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.00000'
    '2Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-put-quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":['
    '\\\\\\"ve-current-0-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetim'
    'e\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-put-reference\\\\\\'
    '"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-put-reference-source-0\\\\\\"]}]]},{\\\\\\"$ma'
    'p\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"reco'
    'rd_id\\\\\\",\\\\\\"ve-current-1-call-iv\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-cal'
    'l-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T1'
    '5:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-call-quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\'
    '\\\\"$list\\\\\\":[\\\\\\"ve-current-1-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\'
    '",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-c'
    'all-reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-call-reference-source-0\\'
    '\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-put-iv\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"'
    've-current-1-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\'
    '\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-put-quote\\\\\\"],[\\\\\\"sou'
    'rce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"nor'
    'malized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"v'
    'e-current-1-put-reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-put-referenc'
    'e-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:3'
    '0:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-underlying\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$l'
    'ist\\\\\\":[\\\\\\"ve-current-underlying-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"'
    '$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-call-i'
    'v\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$ma'
    'p\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"reco'
    'rd_id\\\\\\",\\\\\\"ve-history-0-0-call-quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-'
    '0-0-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"20'
    '30-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-call-reference\\\\\\"],[\\\\\\"s'
    'ource_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":'
    '[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\'
    '\\\\",\\\\\\"ve-history-0-0-put-iv\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-put-iv'
    '-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30'
    ':00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-put-quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"'
    '$list\\\\\\":[\\\\\\"ve-history-0-0-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",'
    '{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-p'
    'ut-reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-put-reference-source-0\\'
    '\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-underlying\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":['
    '\\\\\\"ve-history-0-underlying-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$dateti'
    'me\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-call-iv\\\\\\"],'
    '[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":['
    '[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\'
    '\\",\\\\\\"ve-history-1-0-call-quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-cal'
    'l-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-0'
    '2T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-call-reference\\\\\\"],[\\\\\\"source_i'
    'ds\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"n'
    'ormalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\'
    '"ve-history-1-0-put-iv\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-put-iv-source'
    '-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000'
    '002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-put-quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\'
    '\\":[\\\\\\"ve-history-1-0-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$d'
    'atetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-put-refe'
    'rence\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-put-reference-source-0\\\\\\"]}]]'
    '},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}]'
    ',[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-underlying\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-'
    'history-1-underlying-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":'
    '\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-call-iv\\\\\\"],[\\\\\\"so'
    'urce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"no'
    'rmalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"'
    've-history-2-0-call-quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-call-quote'
    '-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30'
    ':00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-call-reference\\\\\\"],[\\\\\\"source_ids\\\\\\",'
    '{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normaliz'
    'ed_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-his'
    'tory-2-0-put-iv\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-put-iv-source-0\\\\\\"]'
    '}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\'
    '"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-put-quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\'
    '"ve-history-2-0-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime'
    '\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-put-reference\\\\'
    '\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-put-reference-source-0\\\\\\"]}]]},{\\\\\\"'
    '$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"r'
    'ecord_id\\\\\\",\\\\\\"ve-history-2-underlying\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history'
    '-2-underlying-source-0\\\\\\"]}]]}]}],[\\\\\\"iv_percentile_float_repr\\\\\\",\\\\\\"1.0\\\\\\"],[\\\\\\"matched_r'
    'ealized_volatility_float_repr\\\\\\",\\\\\\"0.3328756933888896\\\\\\"],[\\\\\\"matched_realized_window_days\\'
    '\\\\",30],[\\\\\\"methodology_id\\\\\\",\\\\\\"paired-atm-volatility-environment\\\\\\"],[\\\\\\"methodology_vers'
    'ion\\\\\\",\\\\\\"v0.2\\\\\\"],[\\\\\\"parameters_json\\\\\\",\\\\\\"{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"atm_candidate'
    '_universe\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"completeness_semantics\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"no_elig'
    'ible_paired_call_put_strike_omitted\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"declared_complete\\\\\\\\\\\\\\",true],[\\\\\\\\\\\\\\"s'
    'cope\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"all_exact_selected_session_expiration_universes\\\\\\\\\\\\\\"]]}],[\\\\\\\\\\\\\\"atm_se'
    'lection_rule\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"nearest_paired_call_put_strike_to_underlying_bid_ask_midpoint\\\\\\\\\\\\'
    '\\"],[\\\\\\\\\\\\\\"call_put_combination_rule\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"arithmetic_mean_of_same_strike_call_and_p'
    'ut_implied_volatility\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"current_observations\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\'
    '\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"candidate_pairs\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\'
    '\\":[[\\\\\\\\\\\\\\"call_contract_reference_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-call-reference\\\\\\\\\\\\'
    '\\"],[\\\\\\\\\\\\\\"call_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.30\\\\\\\\\\\\\\"}],[\\'
    '\\\\\\\\\\\\"call_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-call-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"call_quote_recor'
    'd_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-call-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"contract_multiplier\\\\\\\\\\\\\\",100],'
    '[\\\\\\\\\\\\\\"currency\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"USD\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"deliverable_id\\\\\\\\\\\\\\",null],[\\\\\\\\\\\\\\"di'
    'stance_to_underlying_midpoint\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.0\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"p'
    'aired_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.300\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"put_'
    'contract_reference_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-put-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"put_im'
    'plied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.30\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"put_iv_record'
    '_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"put_quote_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve'
    '-current-0-put-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"strike\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100\\\\\\\\\\'
    '\\\\"}]]}]}],[\\\\\\\\\\\\\\"expiration\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-02-01\\\\\\\\\\\\\\"}],[\\\\\\\\'
    '\\\\\\"selected_atm_iv\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.300\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"selected_'
    'call_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-call-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"selected_put_iv_record_'
    'id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"selected_strike\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decim'
    'al\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"session_date\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"20'
    '30-01-02\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"tenor_days\\\\\\\\\\\\\\",30],[\\\\\\\\\\\\\\"underlying_midpoint\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\'
    '"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100.0\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"underlying_quote_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve'
    '-current-underlying\\\\\\\\\\\\\\"]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"candidate_pairs\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"'
    '$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"call_contract_reference_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\'
    '"ve-current-1-call-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"call_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal'
    '\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.40\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"call_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-call-iv\\'
    '\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"call_quote_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-call-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\'
    '"contract_multiplier\\\\\\\\\\\\\\",100],[\\\\\\\\\\\\\\"currency\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"USD\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"delive'
    'rable_id\\\\\\\\\\\\\\",null],[\\\\\\\\\\\\\\"distance_to_underlying_midpoint\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\'
    '":\\\\\\\\\\\\\\"0.0\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"paired_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\'
    '\\\\\\\\"0.400\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"put_contract_reference_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-put-'
    'reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"put_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.4'
    '0\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"put_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"put_'
    'quote_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-put-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"strike\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\'
    '"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100\\\\\\\\\\\\\\"}]]}]}],[\\\\\\\\\\\\\\"expiration\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":'
    '\\\\\\\\\\\\\\"2030-03-03\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"selected_atm_iv\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"'
    '0.400\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"selected_call_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-call-iv\\\\\\\\\\\\\\"'
    '],[\\\\\\\\\\\\\\"selected_put_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"selec'
    'ted_strike\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"session_date\\\\\\\\\\\\\\"'
    ',{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"tenor_days\\\\\\\\\\\\\\",60],[\\\\\\\\\\\\\\"un'
    'derlying_midpoint\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100.0\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"underlying_'
    'quote_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-underlying\\\\\\\\\\\\\\"]]}]}],[\\\\\\\\\\\\\\"float_conversion_ru'
    'le\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"convert_only_final_decimal_research_values_to_finite_float\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"'
    'historical_expected_session_dates\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\'
    '"2029-12-24\\\\\\\\\\\\\\"},{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2029-12-27\\\\\\\\\\\\\\"},{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\'
    '\\\\\\\\\\\\"2029-12-30\\\\\\\\\\\\\\"}]}],[\\\\\\\\\\\\\\"historical_matched_tenor_rule\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"expiration_'
    'minus_session_date_calendar_days_equals_reference_tenor\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"historical_observation'
    '_count\\\\\\\\\\\\\\",3],[\\\\\\\\\\\\\\"historical_observations\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$map'
    '\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"candidate_pairs\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\'
    '\\\\"call_contract_reference_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-call-reference\\\\\\\\\\\\\\"],[\\\\\\'
    '\\\\\\\\"call_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.19\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"c'
    'all_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-call-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"call_quote_record_id\\\\'
    '\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-call-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"contract_multiplier\\\\\\\\\\\\\\",100],[\\\\\\'
    '\\\\\\\\"currency\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"USD\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"deliverable_id\\\\\\\\\\\\\\",null],[\\\\\\\\\\\\\\"distan'
    'ce_to_underlying_midpoint\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.0\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"paire'
    'd_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.200\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"put_cont'
    'ract_reference_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-put-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"put_impl'
    'ied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.21\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"put_iv_record_i'
    'd\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"put_quote_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve'
    '-history-0-0-put-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"strike\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100\\\\\\'
    '\\\\\\\\"}]]}]}],[\\\\\\\\\\\\\\"expiration\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-23\\\\\\\\\\\\\\"}],[\\\\'
    '\\\\\\\\\\"selected_atm_iv\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.200\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"selecte'
    'd_call_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-call-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"selected_put_iv_rec'
    'ord_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"selected_strike\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"'
    '$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"session_date\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\'
    '\\\\\\"2029-12-24\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"tenor_days\\\\\\\\\\\\\\",30],[\\\\\\\\\\\\\\"underlying_midpoint\\\\\\\\\\\\\\",{\\'
    '\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100.0\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"underlying_quote_record_id\\\\\\\\\\\\\\",\\\\\\\\'
    '\\\\\\"ve-history-0-underlying\\\\\\\\\\\\\\"]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"candidate_pairs\\\\\\\\\\\\\\",{'
    '\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"call_contract_reference_record_id\\\\\\\\\\\\\\"'
    ',\\\\\\\\\\\\\\"ve-history-1-0-call-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"call_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\'
    '\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.20\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"call_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-'
    '1-0-call-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"call_quote_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-0-call-quote\\\\\\\\'
    '\\\\\\"],[\\\\\\\\\\\\\\"contract_multiplier\\\\\\\\\\\\\\",100],[\\\\\\\\\\\\\\"currency\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"USD\\\\\\\\\\\\\\"],['
    '\\\\\\\\\\\\\\"deliverable_id\\\\\\\\\\\\\\",null],[\\\\\\\\\\\\\\"distance_to_underlying_midpoint\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$'
    'decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.0\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"paired_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decim'
    'al\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.210\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"put_contract_reference_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-'
    'history-1-0-put-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"put_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\'
    '\\\\\\":\\\\\\\\\\\\\\"0.22\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"put_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-0-put-iv\\\\\\\\\\'
    '\\\\"],[\\\\\\\\\\\\\\"put_quote_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-0-put-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"str'
    'ike\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100\\\\\\\\\\\\\\"}]]}]}],[\\\\\\\\\\\\\\"expiration\\\\\\\\\\\\\\",{\\\\'
    '\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-26\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"selected_atm_iv\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$deci'
    'mal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.210\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"selected_call_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-histo'
    'ry-1-0-call-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"selected_put_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-0-put-iv'
    '\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"selected_strike\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100\\\\\\\\\\\\\\"}],[\\\\\\\\'
    '\\\\\\"session_date\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2029-12-27\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"tenor_days'
    '\\\\\\\\\\\\\\",30],[\\\\\\\\\\\\\\"underlying_midpoint\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100.0\\\\\\\\\\\\\\'
    '"}],[\\\\\\\\\\\\\\"underlying_quote_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-underlying\\\\\\\\\\\\\\"]]},{\\\\\\\\'
    '\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"candidate_pairs\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\"'
    ':[[\\\\\\\\\\\\\\"call_contract_reference_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-call-reference\\\\\\\\\\\\'
    '\\"],[\\\\\\\\\\\\\\"call_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.21\\\\\\\\\\\\\\"}],[\\'
    '\\\\\\\\\\\\"call_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-call-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"call_quote_rec'
    'ord_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-call-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"contract_multiplier\\\\\\\\\\\\\\",1'
    '00],[\\\\\\\\\\\\\\"currency\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"USD\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"deliverable_id\\\\\\\\\\\\\\",null],[\\\\\\\\\\\\'
    '\\"distance_to_underlying_midpoint\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.0\\\\\\\\\\\\\\"}],[\\\\\\\\\\'
    '\\\\"paired_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.220\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"'
    'put_contract_reference_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-put-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"'
    'put_implied_volatility\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.23\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"put_iv_'
    'record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"put_quote_record_id\\\\\\\\\\\\\\",\\\\'
    '\\\\\\\\\\"ve-history-2-0-put-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"strike\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\'
    '\\"100\\\\\\\\\\\\\\"}]]}]}],[\\\\\\\\\\\\\\"expiration\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-29\\\\\\\\\\\\'
    '\\"}],[\\\\\\\\\\\\\\"selected_atm_iv\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"0.220\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\'
    '"selected_call_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-call-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"selected_pu'
    't_iv_record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"selected_strike\\\\\\\\\\\\\\",{'
    '\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"session_date\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\\\\\\\'
    '\\\\":\\\\\\\\\\\\\\"2029-12-30\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"tenor_days\\\\\\\\\\\\\\",30],[\\\\\\\\\\\\\\"underlying_midpoint\\\\\\'
    '\\\\\\\\",{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100.0\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"underlying_quote_record_id\\\\\\\\\\'
    '\\\\",\\\\\\\\\\\\\\"ve-history-2-underlying\\\\\\\\\\\\\\"]]}]}],[\\\\\\\\\\\\\\"historical_sample_semantics\\\\\\\\\\\\\\",\\'
    '\\\\\\\\\\\\"caller_declared_observation_sample\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"iv_methodology\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$map'
    '\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"dividend_input_description\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"Synthetic dividend input\\\\\\\\\\\\\\"],'
    '[\\\\\\\\\\\\\\"model_name\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"Synthetic Black-Scholes\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"model_version\\\\\\\\\\'
    '\\\\",\\\\\\\\\\\\\\"fixture-v1\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"rate_input_description\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"Synthetic USD cu'
    'rve input\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"unit_convention\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"annualized_decimal_ratio\\\\\\\\\\\\\\"]]}]'
    ',[\\\\\\\\\\\\\\"median_formula\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"odd_middle_even_arithmetic_mean_of_two_middle_values\\\\\\'
    '\\\\\\\\"],[\\\\\\\\\\\\\\"normalized_evidence\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"direct_inputs\\\\\\\\\\\\\\'
    '",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$dateti'
    'me\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\'
    '\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-call-iv\\\\\\\\\\\\\\"],'
    '[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_implied_volatility\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\'
    '\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-0-call-iv-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[['
    '\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\'
    '\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\'
    '\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-call-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_quote\\\\\\\\\\'
    '\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-0-call-quote-source-'
    '0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":'
    '\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\'
    '"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-call-reference\\\\\\\\\\\\\\"],[\\\\\\'
    '\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_contract_reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\'
    '\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-0-call-reference-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\"'
    ':[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\'
    '\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_'
    'id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_implied_vol'
    'atility\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-0-put-iv'
    '-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\'
    '\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",'
    '{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-0-put-quote\\\\\\\\\\\\\\"],['
    '\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\'
    '\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-0-put-quote-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"norm'
    'alized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\'
    '\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\'
    '\\\\\\"ve-current-0-put-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_contract_reference\\'
    '\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-0-put-reference-'
    'source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\'
    '\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{'
    '\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-call-iv\\\\\\\\\\\\\\"],[\\\\\\'
    '\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_implied_volatility\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\'
    '\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-1-call-iv-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\'
    '\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"'
    '}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\'
    '\\\\",\\\\\\\\\\\\\\"ve-current-1-call-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_quote\\\\\\\\\\\\\\"]'
    ',[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-1-call-quote-source-0\\\\\\'
    '\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\'
    '\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$li'
    'st\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-call-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\'
    '"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_contract_reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$l'
    'ist\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-1-call-reference-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\'
    '\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\'
    '\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\'
    '\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_implied_volatil'
    'ity\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-1-put-iv-sou'
    'rce-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\'
    '\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\'
    '\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-1-put-quote\\\\\\\\\\\\\\"],[\\\\\\\\'
    '\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\'
    '":[\\\\\\\\\\\\\\"ve-current-1-put-quote-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normaliz'
    'ed_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"'
    'propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"'
    've-current-1-put-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_contract_reference\\\\\\\\\\'
    '\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-current-1-put-reference-sour'
    'ce-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\'
    '\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\'
    '\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-current-underlying\\\\\\\\\\\\\\"],[\\\\\\\\\\\\'
    '\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"underlying_quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\'
    '\\\\":[\\\\\\\\\\\\\\"ve-current-underlying-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normali'
    'zed_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\'
    '"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\'
    '"ve-history-0-0-call-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_implied_volatility\\\\\\\\\\\\\\"'
    '],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-0-0-call-iv-source-0\\\\\\'
    '\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\'
    '\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$li'
    'st\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-call-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"r'
    'ole\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\'
    '\\\\\\\\\\"ve-history-0-0-call-quote-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized'
    '_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"pr'
    'opagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve'
    '-history-0-0-call-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_contract_reference\\\\\\\\'
    '\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-0-0-call-reference-'
    'source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\'
    '\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{'
    '\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-put-iv\\\\\\\\\\\\\\"],[\\\\'
    '\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_implied_volatility\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\'
    '\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-0-0-put-iv-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\'
    '\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\'
    '\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\'
    '\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-put-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_quote\\\\\\\\\\\\'
    '\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-0-0-put-quote-source-'
    '0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":'
    '\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\'
    '"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-0-put-reference\\\\\\\\\\\\\\"],[\\\\'
    '\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_contract_reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\'
    '\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-0-0-put-reference-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\'
    '\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"recor'
    'd_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-0-underlying\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"underlying_q'
    'uote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-0-underlyin'
    'g-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime'
    '\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\"'
    ',{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-0-call-iv\\\\\\\\\\\\\\"],'
    '[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_implied_volatility\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\'
    '\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-1-0-call-iv-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":'
    '[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\'
    '\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_i'
    'd\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-0-call-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_quote\\'
    '\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-1-0-call-quote-s'
    'ource-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\'
    '\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\'
    '\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-0-call-reference\\\\\\\\\\\\'
    '\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_contract_reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\"'
    ',{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-1-0-call-reference-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$m'
    'ap\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:0'
    '0.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\'
    '\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-0-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option'
    '_implied_volatility\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-hist'
    'ory-1-0-put-iv-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\'
    '\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_'
    'flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-0-put-'
    'quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{'
    '\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-1-0-put-quote-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\'
    '\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.00000'
    '2Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"reco'
    'rd_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1-0-put-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option'
    '_contract_reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-hist'
    'ory-1-0-put-reference-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\'
    '",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_q'
    'uality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-1'
    '-underlying\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"underlying_quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids'
    '\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-1-underlying-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"'
    '$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30'
    ':00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\'
    '\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-call-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"opt'
    'ion_implied_volatility\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-h'
    'istory-2-0-call-iv-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{'
    '\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_qual'
    'ity_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-'
    'call-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\'
    '\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-2-0-call-quote-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$ma'
    'p\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00'
    '.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\'
    '\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-call-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\'
    '"option_contract_reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"'
    've-history-2-0-call-reference-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_a'
    't\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"prop'
    'agated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-h'
    'istory-2-0-put-iv\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_implied_volatility\\\\\\\\\\\\\\"],[\\\\\\'
    '\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-2-0-put-iv-source-0\\\\\\\\\\\\\\"]}'
    ']]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"203'
    '0-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\'
    '\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-0-put-quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\'
    '\\\\",\\\\\\\\\\\\\\"option_quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve'
    '-history-2-0-put-quote-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\'
    '\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_'
    'quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-'
    '2-0-put-reference\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"role\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"option_contract_reference\\\\\\\\\\\\\\"],[\\\\\\'
    '\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"ve-history-2-0-put-reference-source-0\\\\\\'
    '\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\'
    '\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"propagated_quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$li'
    'st\\\\\\\\\\\\\\":[]}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ve-history-2-underlying\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"rol'
    'e\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"underlying_quote\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":['
    '\\\\\\\\\\\\\\"ve-history-2-underlying-source-0\\\\\\\\\\\\\\"]}]]}]}]]}],[\\\\\\\\\\\\\\"percentile_formula\\\\\\\\\\\\\\",'
    '\\\\\\\\\\\\\\"inclusive_count_historical_atm_iv_lte_current_reference_atm_iv_divided_by_count\\\\\\\\\\\\\\"]'
    ',[\\\\\\\\\\\\\\"realized_volatility_dependency\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"adjustment_meth'
    'odology\\\\\\\\\\\\\\",null],[\\\\\\\\\\\\\\"annualization_sessions_per_year\\\\\\\\\\\\\\",252],[\\\\\\\\\\\\\\"annualized_'
    'realized_volatility_float_repr\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"0.3328756933888896\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"calculated_a'
    't\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:04.000000Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"calc'
    'ulation_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"calculation-3c7c\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"calculation_type\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"h'
    'istorical_realized_volatility\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"end_session_date\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":'
    '\\\\\\\\\\\\\\"2030-01-02\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"inputs\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\'
    '\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"hrv-0\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\'
    '\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"hrv-0-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized'
    '_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$datetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"re'
    'cord_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"hrv-1\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\'
    '\\\\"hrv-1-source-0\\\\\\\\\\\\\\"]}]]},{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"normalized_at\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$d'
    'atetime\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"record_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\'
    '"hrv-2\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"source_ids\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\\\\\\\\\"hrv-2-source-0\\\\\\\\\\\\'
    '\\"]}]]}]}],[\\\\\\\\\\\\\\"log_returns\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\'
    '\\"0.01980262729617971302602906688510039\\\\\\\\\\\\\\"},{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"-0.0098522964'
    '43011630177813709340839653\\\\\\\\\\\\\\"}]}],[\\\\\\\\\\\\\\"methodology_id\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"historical-log-re'
    'turn-sample-realized-volatility\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"methodology_version\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"v0.1\\\\\\\\\\\\'
    '\\"],[\\\\\\\\\\\\\\"parameters_json\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"{\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\\\\\\\\\'
    '\\\\\\\\"adjustment_methodology\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",null],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"annualization_rule\\\\\\\\\\\\\\\\\\\\\\'
    '\\\\\\\\",\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"daily_sample_standard_deviation_times_square_root_sessions_per_year\\\\\\\\\\\\\\'
    '\\\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"annualization_sessions_per_year\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",252],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\'
    '\\"expected_session_dates\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\\\\\\\\\\\\\\\'
    '\\"$date\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\":\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"2029-12-03\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"},{\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"$date\\\\\\\\\\\\'
    '\\\\\\\\\\\\\\\\\\":\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"2029-12-18\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"},{\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\":\\\\'
    '\\\\\\\\\\\\\\\\\\\\\\\\\\"2030-01-02\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"}]}],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"price_basis\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",\\\\\\\\\\\\'
    '\\\\\\\\\\\\\\\\\\"raw_close\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"price_observation_count\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",3]'
    ',[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"price_unit\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"usd_per_underlying_share\\\\\\\\\\\\\\\\\\\\\\'
    '\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"return_association_rule\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"ending_session\\\\'
    '\\\\\\\\\\\\\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"return_formula\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"natural_log_pric'
    'e_ratio\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"return_observation_count\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",2],[\\\\\\\\\\\\\\\\\\'
    '\\\\\\\\\\\\"return_unit\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"decimal_ratio\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\'
    '\\\\"underlying\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"currency\\\\'
    '\\\\\\\\\\\\\\\\\\\\\\\\\\",\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"USD\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"listing_mic\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"'
    ',\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"ARCX\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"security_type\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",\\\\\\\\\\\\\\\\\\\\'
    '\\\\\\\\\\"etf\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"symbol\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"SPY\\\\\\\\\\\\\\\\\\\\'
    '\\\\\\\\\\"]]}],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"variance_estimator\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"sample_variance\\\\'
    '\\\\\\\\\\\\\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"volatility_unit\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"annualized_deci'
    'mal_ratio\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"window_end_session_date\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\\\\\\\\\'
    '\\\\\\\\"$date\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\":\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"2030-01-02\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"window_'
    'start_session_date\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\":\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"2029-1'
    '2-03\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\"}]]}\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"price_basis\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"raw_close\\\\\\\\\\\\\\"],[\\\\\\\\\\'
    '\\\\"price_observation_count\\\\\\\\\\\\\\",3],[\\\\\\\\\\\\\\"prices\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$'
    'decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"100\\\\\\\\\\\\\\"},{\\\\\\\\\\\\\\"$decimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"102\\\\\\\\\\\\\\"},{\\\\\\\\\\\\\\"$de'
    'cimal\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"101\\\\\\\\\\\\\\"}]}],[\\\\\\\\\\\\\\"quality_flags\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[\\\\\\'
    '\\\\\\\\"decimal_to_float_converted\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"annualized\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"assumption_applied\\\\\\'
    '\\\\\\\\"]}],[\\\\\\\\\\\\\\"return_formula\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"natural_log_price_ratio\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"retur'
    'n_observation_count\\\\\\\\\\\\\\",2],[\\\\\\\\\\\\\\"session_dates\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$'
    'date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2029-12-03\\\\\\\\\\\\\\"},{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2029-12-18\\\\\\\\\\\\\\"},{\\\\\\'
    '\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02\\\\\\\\\\\\\\"}]}],[\\\\\\\\\\\\\\"start_session_date\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$'
    'date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2029-12-03\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"underlying\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\'
    '\\\\\\\\\\"currency\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"USD\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"listing_mic\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ARCX\\\\\\\\\\\\\\"],['
    '\\\\\\\\\\\\\\"security_type\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"etf\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"symbol\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"SPY\\\\\\\\\\\\\\"]]'
    '}],[\\\\\\\\\\\\\\"variance_estimator\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"sample_variance\\\\\\\\\\\\\\"]]}],[\\\\\\\\\\\\\\"realized_win'
    'dow_matching_rule\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"realized_end_equals_current_as_of_and_calendar_span_equals_ref'
    'erence_tenor\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"reference_tenor_days\\\\\\\\\\\\\\",30],[\\\\\\\\\\\\\\"strike_tie_rule\\\\\\\\\\\\\\"'
    ',\\\\\\\\\\\\\\"lower_strike\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"term_tenor_rule\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"expiration_minus_session'
    '_date_calendar_days\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"underlying_midpoint_rule\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"bid_ask_midpoint_'
    'no_last_fallback\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"volatility_unit\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"annualized_decimal_ratio\\\\\\\\\\'
    '\\\\"]]}\\\\\\"],[\\\\\\"quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"decimal_to_float_converted\\\\\\",\\\\\\"annual'
    'ized\\\\\\",\\\\\\"assumption_applied\\\\\\"]}],[\\\\\\"reference_tenor_days\\\\\\",30],[\\\\\\"term_points\\\\\\",{\\'
    '\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"atm_iv_float_repr\\\\\\",\\\\\\"0.3\\\\\\"],[\\\\\\"tenor_days\\\\\\",30]]},{'
    '\\\\\\"$map\\\\\\":[[\\\\\\"atm_iv_float_repr\\\\\\",\\\\\\"0.4\\\\\\"],[\\\\\\"tenor_days\\\\\\",60]]}]}],[\\\\\\"underlyi'
    'ng\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"candidate_universe\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"current_semantics\\\\\\",\\\\\\'
    '"no_eligible_nearest_signed_delta_candidate_omitted\\\\\\"],[\\\\\\"declared_complete\\\\\\",true],[\\\\\\"h'
    'istorical_semantics\\\\\\",\\\\\\"no_eligible_paired_atm_or_nearest_signed_delta_candidate_omitted\\\\\\"'
    '],[\\\\\\"scope\\\\\\",\\\\\\"current_delta_and_historical_atm_and_delta_candidate_universes\\\\\\"]]}],[\\\\\\'
    '"current_expiration_observations\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"atm_dependency_selected'
    '_call_iv_record_id\\\\\\",\\\\\\"ve-current-0-call-iv\\\\\\"],[\\\\\\"atm_dependency_selected_put_iv_record_'
    'id\\\\\\",\\\\\\"ve-current-0-put-iv\\\\\\"],[\\\\\\"atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.300\\\\\\"}],[\\\\\\"candi'
    'date_contracts\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contrac'
    't_reference_record_id\\\\\\",\\\\\\"ve-current-0-call-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\'
    '\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\'
    '"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"ve-cur'
    'rent-0-call-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"iv_rec'
    'ord_id\\\\\\",\\\\\\"ve-current-0-call-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id'
    '\\\\\\",\\\\\\"ve-current-0-call-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.50\\\\\\"}],[\\\\'
    '\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],'
    '[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-current-30-call25-reference\\\\\\"],[\\\\\\"currency\\\\\\'
    '",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"0.14\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_'
    'id\\\\\\",\\\\\\"tail-current-30-call25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"'
    '0.28\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-30-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"cal'
    'l\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-30-call25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\'
    '"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\'
    '\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-current-30-call10'
    '-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10'
    '_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-current-30-call10-greeks\\\\\\"],[\\\\\\"implied_volat'
    'ility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.26\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-30-call10-iv\\\\'
    '\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-30-call10-quote'
    '\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\'
    '\\\\"110\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_i'
    'd\\\\\\",\\\\\\"tail-current-30-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_i'
    'd\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_'
    'target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-current-30-put10-'
    'greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.42\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\'
    '\\\\"tail-current-30-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"'
    'tail-current-30-put10-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"st'
    'rike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"'
    'contract_reference_record_id\\\\\\",\\\\\\"tail-current-30-put25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"'
    'USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14'
    '\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\"'
    ',\\\\\\"tail-current-30-put25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.36\\\\\\'
    '"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-30-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\'
    '\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-30-put25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contrac'
    't_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"ve-current-0-put-reference\\\\\\"],'
    '[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\'
    '"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\'
    '\\"greeks_record_id\\\\\\",\\\\\\"ve-current-0-put-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decima'
    'l\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"ve-current-0-put-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\'
    '"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"ve-current-0-put-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$d'
    'ecimal\\\\\\":\\\\\\"-0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"downside_25'
    '_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.060\\\\\\"}],[\\\\\\"downside_wing_curvature\\\\\\",{\\\\\\"$decimal'
    '\\\\\\":\\\\\\"0.06\\\\\\"}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-02-01\\\\\\"}],[\\\\\\"historical_obse'
    'rvation_count\\\\\\",3],[\\\\\\"selected_call_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],'
    '[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-current-30-call10-reference\\\\\\"],[\\\\\\"currency\\\\\\'
    '",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],'
    '[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-current-30-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\'
    '\\"$decimal\\\\\\":\\\\\\"0.26\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-30-call10-iv\\\\\\"],[\\\\\\"opti'
    'on_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-30-call10-quote\\\\\\"],[\\\\\\"se'
    'lected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}'
    '],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.10\\\\\\"}]]}],[\\\\\\"selected_call_25\\\\\\",{\\\\\\"$map\\'
    '\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-current-30'
    '-call25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distanc'
    'e\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-current-30-call25-gree'
    'ks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.28\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"t'
    'ail-current-30-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"ta'
    'il-current-30-call25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"st'
    'rike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}]]'
    '}],[\\\\\\"selected_put_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_refer'
    'ence_record_id\\\\\\",\\\\\\"tail-current-30-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"'
    'deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_i'
    'd\\\\\\",\\\\\\"tail-current-30-put10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.'
    '42\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-30-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\'
    '"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-30-put10-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$d'
    'ecimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}],[\\\\\\"target_delta\\\\\\",'
    '{\\\\\\"$decimal\\\\\\":\\\\\\"-0.10\\\\\\"}]]}],[\\\\\\"selected_put_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multi'
    'plier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-current-30-put25-reference\\\\\\"],[\\'
    '\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\'
    '\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-current-30-put25-greeks\\\\\\"],[\\\\\\"implied_volat'
    'ility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.36\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-30-put25-iv\\\\\\'
    '"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-30-put25-quote\\\\\\'
    '"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\'
    '\\\\"95\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.25\\\\\\"}]]}],[\\\\\\"session_date\\\\\\",{\\\\'
    '\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"skew_percentile\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.66666666666666'
    '66666666666666666667\\\\\\"}],[\\\\\\"tenor_days\\\\\\",30],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"ve-cu'
    'rrent-underlying\\\\\\"],[\\\\\\"upside_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.020\\\\\\"}],[\\\\\\"upsi'
    'de_wing_curvature\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.02\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"atm_dependency_sel'
    'ected_call_iv_record_id\\\\\\",\\\\\\"ve-current-1-call-iv\\\\\\"],[\\\\\\"atm_dependency_selected_put_iv_re'
    'cord_id\\\\\\",\\\\\\"ve-current-1-put-iv\\\\\\"],[\\\\\\"atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.400\\\\\\"}],[\\\\\\"'
    'candidate_contracts\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"co'
    'ntract_reference_record_id\\\\\\",\\\\\\"ve-current-1-call-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\'
    '"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}]'
    ',[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"v'
    'e-current-1-call-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"i'
    'v_record_id\\\\\\",\\\\\\"ve-current-1-call-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_reco'
    'rd_id\\\\\\",\\\\\\"ve-current-1-call-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.50\\\\\\"}'
    '],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",'
    '100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-current-60-call25-reference\\\\\\"],[\\\\\\"curren'
    'cy\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\'
    '\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_re'
    'cord_id\\\\\\",\\\\\\"tail-current-60-call25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\"'
    ':\\\\\\"0.38\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-60-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\'
    '\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-60-call25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\"'
    ',{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}]]},{\\\\\\"$map\\\\\\'
    '":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-current-60-c'
    'all10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_'
    'to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\'
    '\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-current-60-call10-greeks\\\\\\"],[\\\\\\"implied_'
    'volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.36\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-60-call10'
    '-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-60-call10-'
    'quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"110\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_rec'
    'ord_id\\\\\\",\\\\\\"tail-current-60-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"delivera'
    'ble_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_t'
    'o_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-current-60-p'
    'ut10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.52\\\\\\"}],[\\\\\\"iv_record_id\\'
    '\\\\",\\\\\\"tail-current-60-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\"'
    ',\\\\\\"tail-current-60-put10-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\'
    '\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],'
    '[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-current-60-put25-reference\\\\\\"],[\\\\\\"currency\\\\\\"'
    ',\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\'
    '"0.14\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_i'
    'd\\\\\\",\\\\\\"tail-current-60-put25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.'
    '46\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-60-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\'
    '"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-60-put25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$dec'
    'imal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"co'
    'ntract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"ve-current-1-put-reference\\'
    '\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\"'
    ',{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}'
    '],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"ve-current-1-put-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$d'
    'ecimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"ve-current-1-put-iv\\\\\\"],[\\\\\\"option_type\\\\\\'
    '",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"ve-current-1-put-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\'
    '\\\\"$decimal\\\\\\":\\\\\\"-0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"downsi'
    'de_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.060\\\\\\"}],[\\\\\\"downside_wing_curvature\\\\\\",{\\\\\\"$de'
    'cimal\\\\\\":\\\\\\"0.06\\\\\\"}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"historical'
    '_observation_count\\\\\\",3],[\\\\\\"selected_call_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",'
    '100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-current-60-call10-reference\\\\\\"],[\\\\\\"curren'
    'cy\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\'
    '\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-current-60-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\'
    '",{\\\\\\"$decimal\\\\\\":\\\\\\"0.36\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-60-call10-iv\\\\\\"],[\\\\\\'
    '"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-60-call10-quote\\\\\\"],[\\'
    '\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110'
    '\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.10\\\\\\"}]]}],[\\\\\\"selected_call_25\\\\\\",{\\\\\\"'
    '$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-curre'
    'nt-60-call25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"di'
    'stance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-current-60-call25'
    '-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.38\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",'
    '\\\\\\"tail-current-60-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\'
    '\\\\"tail-current-60-call25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\'
    '\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\'
    '\\"}]]}],[\\\\\\"selected_put_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_'
    'reference_record_id\\\\\\",\\\\\\"tail-current-60-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],'
    '[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_rec'
    'ord_id\\\\\\",\\\\\\"tail-current-60-put10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\'
    '\\\\"0.52\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-60-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"p'
    'ut\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-60-put10-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\'
    '\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}],[\\\\\\"target_delta'
    '\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.10\\\\\\"}]]}],[\\\\\\"selected_put_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_'
    'multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-current-60-put25-reference\\\\\\'
    '"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-current-60-put25-greeks\\\\\\"],[\\\\\\"implied_'
    'volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.46\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-current-60-put25-'
    'iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-current-60-put25-quo'
    'te\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"95\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.25\\\\\\"}]]}],[\\\\\\"session_date\\\\\\'
    '",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"skew_percentile\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.666666666'
    '6666666666666666666666667\\\\\\"}],[\\\\\\"tenor_days\\\\\\",60],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"'
    've-current-underlying\\\\\\"],[\\\\\\"upside_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.020\\\\\\"}],[\\\\\\'
    '"upside_wing_curvature\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.02\\\\\\"}]]}]}],[\\\\\\"current_skew_formula\\\\\\",'
    '\\\\\\"put_25_delta_iv_minus_atm_iv\\\\\\"],[\\\\\\"delta_convention\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"delta_basis\\'
    '\\\\",\\\\\\"spot\\\\\\"],[\\\\\\"interpolation_methodology\\\\\\",\\\\\\"none\\\\\\"],[\\\\\\"model_provider_methodolo'
    'gy\\\\\\",\\\\\\"Synthetic Black-Scholes provider delta\\\\\\"],[\\\\\\"premium_adjustment\\\\\\",\\\\\\"unadjuste'
    'd\\\\\\"],[\\\\\\"signed_delta_convention\\\\\\",\\\\\\"call_positive_put_negative\\\\\\"],[\\\\\\"target_selectio'
    'n_methodology\\\\\\",\\\\\\"nearest_observed_signed_delta\\\\\\"]]}],[\\\\\\"delta_point_selection_rule\\\\\\",'
    '\\\\\\"nearest_observed_signed_delta\\\\\\"],[\\\\\\"delta_tie_rule\\\\\\",\\\\\\"reject_equal_distance_or_rema'
    'ining_economic_ambiguity\\\\\\"],[\\\\\\"float_conversion_rule\\\\\\",\\\\\\"convert_only_final_tail_pricing'
    '_record_values_to_finite_float\\\\\\"],[\\\\\\"historical_eod_semantics\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"declar'
    'ed\\\\\\",true],[\\\\\\"methodology\\\\\\",\\\\\\"Synthetic official regular-session EOD snapshot\\\\\\"],[\\\\\\"'
    'sample_semantics\\\\\\",\\\\\\"caller_declared_daily_eod_observation_sample\\\\\\"],[\\\\\\"scope\\\\\\",\\\\\\"ev'
    'ery_historical_session_and_tenor_selection\\\\\\"]]}],[\\\\\\"historical_expected_session_dates\\\\\\",{\\'
    '\\\\"$list\\\\\\":[{\\\\\\"$date\\\\\\":\\\\\\"2029-12-24\\\\\\"},{\\\\\\"$date\\\\\\":\\\\\\"2029-12-27\\\\\\"},{\\\\\\"$date\\\\'
    '\\":\\\\\\"2029-12-30\\\\\\"}]}],[\\\\\\"historical_matched_tenor_rule\\\\\\",\\\\\\"expiration_minus_session_da'
    'te_calendar_days_equals_current_tenor\\\\\\"],[\\\\\\"historical_observations_by_tenor\\\\\\",{\\\\\\"$list\\'
    '\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"current_expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-02-01\\\\\\"}],[\\\\\\"histori'
    'cal_observations\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.200\\'
    '\\\\"}],[\\\\\\"call_10_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.16\\\\\\"}],[\\\\\\"call_25_delta_iv\\\\\\",{\\\\\\"'
    '$decimal\\\\\\":\\\\\\"0.18\\\\\\"}],[\\\\\\"candidate_contracts\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"con'
    'tract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"ve-history-0-0-call-referenc'
    'e\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\'
    '\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\'
    '"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"ve-history-0-0-call-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\'
    '\\\\"$decimal\\\\\\":\\\\\\"0.19\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"ve-history-0-0-call-iv\\\\\\"],[\\\\\\"option'
    '_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"ve-history-0-0-call-quote\\\\\\"],[\\\\\\"signed_'
    'delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]},{\\\\'
    '\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-his'
    'tory-0-30-call25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\'
    '\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\'
    '"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0-30-call25-greeks\\\\\\"],'
    '[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.18\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-hist'
    'ory-0-30-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-his'
    'tory-0-30-call25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"strike\\\\'
    '\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contr'
    'act_reference_record_id\\\\\\",\\\\\\"tail-history-0-30-call10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"US'
    'D\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\'
    '\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\'
    '\\\\"tail-history-0-30-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.16\\\\'
    '\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-30-call10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\'
    '"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-30-call10-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$'
    'decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\'
    '"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-0-30-put10-'
    'reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_'
    'target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\'
    '"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0-30-put10-greeks\\\\\\"],[\\\\\\"implied_volat'
    'ility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-30-put10-iv\\'
    '\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-30-put10-quot'
    'e\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\"'
    ':\\\\\\"90\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_'
    'id\\\\\\",\\\\\\"tail-history-0-30-put25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverabl'
    'e_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"distance_to_'
    '25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0-30-p'
    'ut25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"iv_record_id\\'
    '\\\\",\\\\\\"tail-history-0-30-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\'
    '\\",\\\\\\"tail-history-0-30-put25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.24\\\\\\"}'
    '],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",1'
    '00],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"ve-history-0-0-put-reference\\\\\\"],[\\\\\\"currency\\\\\\'
    '",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\\\"greeks_record_'
    'id\\\\\\",\\\\\\"ve-history-0-0-put-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.21'
    '\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"ve-history-0-0-put-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\'
    '\\\\"quote_record_id\\\\\\",\\\\\\"ve-history-0-0-put-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\"'
    ':\\\\\\"-0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"downside_25_delta_ske'
    'w\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.040\\\\\\"}],[\\\\\\"downside_wing_curvature\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0'
    '.06\\\\\\"}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-23\\\\\\"}],[\\\\\\"put_10_delta_iv\\\\\\",{\\\\\\"'
    '$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"put_25_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"selec'
    'ted_call_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_'
    'id\\\\\\",\\\\\\"tail-history-0-30-call10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverab'
    'le_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\'
    '"tail-history-0-30-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.16\\\\\\"'
    '}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-30-call10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"]'
    ',[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-30-call10-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$'
    'decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}],[\\\\\\"target_delta\\\\\\"'
    ',{\\\\\\"$decimal\\\\\\":\\\\\\"0.10\\\\\\"}]]}],[\\\\\\"selected_call_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_mult'
    'iplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-0-30-call25-reference\\\\\\"'
    '],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\'
    '\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0-30-call25-greeks\\\\\\"],[\\\\\\"implie'
    'd_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.18\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-30-ca'
    'll25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-30-c'
    'all25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$'
    'decimal\\\\\\":\\\\\\"105\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}]]}],[\\\\\\"selecte'
    'd_paired_atm_evidence\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":'
    '[[\\\\\\"call_contract_reference_record_id\\\\\\",\\\\\\"ve-history-0-0-call-reference\\\\\\"],[\\\\\\"call_imp'
    'lied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.19\\\\\\"}],[\\\\\\"call_iv_record_id\\\\\\",\\\\\\"ve-history-0'
    '-0-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"ve-history-0-0-call-quote\\\\\\"],[\\\\\\"contract_m'
    'ultiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to'
    '_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied_volatility\\\\\\",{\\\\\\'
    '"$decimal\\\\\\":\\\\\\"0.200\\\\\\"}],[\\\\\\"put_contract_reference_record_id\\\\\\",\\\\\\"ve-history-0-0-put-r'
    'eference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.21\\\\\\"}],[\\\\\\"put_iv_recor'
    'd_id\\\\\\",\\\\\\"ve-history-0-0-put-iv\\\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"ve-history-0-0-put-quot'
    'e\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"selected_atm_iv\\\\\\",{\\\\\\"$decim'
    'al\\\\\\":\\\\\\"0.200\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-history-0-0-call-iv\\\\\\"],[\\\\\\"'
    'selected_put_iv_record_id\\\\\\",\\\\\\"ve-history-0-0-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\",{\\\\\\"$deci'
    'mal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}]]}],[\\\\\\"sel'
    'ected_put_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record'
    '_id\\\\\\",\\\\\\"tail-history-0-30-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverab'
    'le_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\'
    '"tail-history-0-30-put10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}'
    '],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-30-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\'
    '\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-30-put10-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$deci'
    'mal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\'
    '\\"$decimal\\\\\\":\\\\\\"-0.10\\\\\\"}]]}],[\\\\\\"selected_put_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multipli'
    'er\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-0-30-put25-reference\\\\\\"],[\\\\'
    '\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0-30-put25-greeks\\\\\\"],[\\\\\\"implied_vola'
    'tility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-30-put25-iv'
    '\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-30-put25-quo'
    'te\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"95\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.25\\\\\\"}]]}],[\\\\\\"session_date\\\\\\'
    '",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-24\\\\\\"}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"ve-history-0-under'
    'lying\\\\\\"],[\\\\\\"upside_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.020\\\\\\"}],[\\\\\\"upside_wing_cur'
    'vature\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.02\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":'
    '\\\\\\"0.210\\\\\\"}],[\\\\\\"call_10_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.17\\\\\\"}],[\\\\\\"call_25_delta_iv'
    '\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.19\\\\\\"}],[\\\\\\"candidate_contracts\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\"'
    ':[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"ve-history-1-0-cal'
    'l-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_1'
    '0_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\'
    '\\\\"0.25\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"ve-history-1-0-call-greeks\\\\\\"],[\\\\\\"implied_volatil'
    'ity\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"ve-history-1-0-call-iv\\\\\\"],['
    '\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"ve-history-1-0-call-quote\\\\\\"],[\\'
    '\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\'
    '\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\'
    '\\"tail-history-1-30-call25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\"'
    ',null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"distance_to_25_targe'
    't\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-1-30-call25-gr'
    'eeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.19\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\'
    '"tail-history-1-30-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\'
    '\\"tail-history-1-30-call25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\'
    '\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],'
    '[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-1-30-call10-reference\\\\\\"],[\\\\\\"currency\\'
    '\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":'
    '\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_recor'
    'd_id\\\\\\",\\\\\\"tail-history-1-30-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":'
    '\\\\\\"0.17\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-1-30-call10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\'
    '\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-1-30-call10-quote\\\\\\"],[\\\\\\"signed_delta\\'
    '\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}]]},{\\\\\\"$map'
    '\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-1'
    '-30-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"dista'
    'nce_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decim'
    'al\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-1-30-put10-greeks\\\\\\"],[\\\\\\"imp'
    'lied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.33\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-1-30'
    '-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-1-30-'
    'put10-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$d'
    'ecimal\\\\\\":\\\\\\"90\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_referen'
    'ce_record_id\\\\\\",\\\\\\"tail-history-1-30-put25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"'
    'deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"di'
    'stance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-hist'
    'ory-1-30-put25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.27\\\\\\"}],[\\\\\\"iv_'
    'record_id\\\\\\",\\\\\\"tail-history-1-30-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_r'
    'ecord_id\\\\\\",\\\\\\"tail-history-1-30-put25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"'
    '-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multip'
    'lier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"ve-history-1-0-put-reference\\\\\\"],[\\\\\\"c'
    'urrency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$deci'
    'mal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\\\"gree'
    'ks_record_id\\\\\\",\\\\\\"ve-history-1-0-put-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\'
    '":\\\\\\"0.22\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"ve-history-1-0-put-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"p'
    'ut\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"ve-history-1-0-put-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$d'
    'ecimal\\\\\\":\\\\\\"-0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"downside_25'
    '_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.060\\\\\\"}],[\\\\\\"downside_wing_curvature\\\\\\",{\\\\\\"$decimal'
    '\\\\\\":\\\\\\"0.06\\\\\\"}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-26\\\\\\"}],[\\\\\\"put_10_delta_iv'
    '\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.33\\\\\\"}],[\\\\\\"put_25_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.27\\\\\\"}],'
    '[\\\\\\"selected_call_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_referen'
    'ce_record_id\\\\\\",\\\\\\"tail-history-1-30-call10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\'
    '"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_'
    'id\\\\\\",\\\\\\"tail-history-1-30-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"0.17\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-1-30-call10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\'
    '"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-1-30-call10-quote\\\\\\"],[\\\\\\"selected_delta\\'
    '\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}],[\\\\\\"target'
    '_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.10\\\\\\"}]]}],[\\\\\\"selected_call_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"con'
    'tract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-1-30-call25-ref'
    'erence\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"'
    '$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-1-30-call25-greeks\\\\\\"],['
    '\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.19\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-histo'
    'ry-1-30-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-hist'
    'ory-1-30-call25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"strike\\'
    '\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}]]}],[\\'
    '\\\\"selected_paired_atm_evidence\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\'
    '"$map\\\\\\":[[\\\\\\"call_contract_reference_record_id\\\\\\",\\\\\\"ve-history-1-0-call-reference\\\\\\"],[\\\\'
    '\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"call_iv_record_id\\\\\\",\\\\\\"ve'
    '-history-1-0-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"ve-history-1-0-call-quote\\\\\\"],[\\\\\\"'
    'contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"d'
    'istance_to_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied_volatilit'
    'y\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.210\\\\\\"}],[\\\\\\"put_contract_reference_record_id\\\\\\",\\\\\\"ve-history'
    '-1-0-put-reference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.22\\\\\\"}],[\\\\\\"pu'
    't_iv_record_id\\\\\\",\\\\\\"ve-history-1-0-put-iv\\\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"ve-history-1-'
    '0-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"selected_atm_iv\\\\\\",{'
    '\\\\\\"$decimal\\\\\\":\\\\\\"0.210\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-history-1-0-call-iv\\'
    '\\\\"],[\\\\\\"selected_put_iv_record_id\\\\\\",\\\\\\"ve-history-1-0-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\",'
    '{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}]]}'
    '],[\\\\\\"selected_put_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_refere'
    'nce_record_id\\\\\\",\\\\\\"tail-history-1-30-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\'
    '"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_'
    'id\\\\\\",\\\\\\"tail-history-1-30-put10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\'
    '"0.33\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-1-30-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"p'
    'ut\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-1-30-put10-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",'
    '{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}],[\\\\\\"target_del'
    'ta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.10\\\\\\"}]]}],[\\\\\\"selected_put_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contrac'
    't_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-1-30-put25-referenc'
    'e\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$deci'
    'mal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-1-30-put25-greeks\\\\\\"],[\\\\\\"im'
    'plied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.27\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-1-3'
    '0-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-1-30'
    '-put25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\'
    '"$decimal\\\\\\":\\\\\\"95\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.25\\\\\\"}]]}],[\\\\\\"sessi'
    'on_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-27\\\\\\"}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"ve-histo'
    'ry-1-underlying\\\\\\"],[\\\\\\"upside_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.020\\\\\\"}],[\\\\\\"upsid'
    'e_wing_curvature\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.02\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"atm_iv\\\\\\",{\\\\\\"$de'
    'cimal\\\\\\":\\\\\\"0.220\\\\\\"}],[\\\\\\"call_10_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.18\\\\\\"}],[\\\\\\"call_2'
    '5_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"candidate_contracts\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\'
    '\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"ve-histo'
    'ry-2-0-call-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"dis'
    'tance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$dec'
    'imal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"ve-history-2-0-call-greeks\\\\\\"],[\\\\\\"impli'
    'ed_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.21\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"ve-history-2-0-call'
    '-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"ve-history-2-0-call-quo'
    'te\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\"'
    ':\\\\\\"100\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record'
    '_id\\\\\\",\\\\\\"tail-history-2-30-call25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"delivera'
    'ble_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"distance_t'
    'o_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-2-30'
    '-call25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"iv_record_'
    'id\\\\\\",\\\\\\"tail-history-2-30-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record'
    '_id\\\\\\",\\\\\\"tail-history-2-30-call25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24'
    '\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier'
    '\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-2-30-call10-reference\\\\\\"],[\\\\\\'
    '"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$de'
    'cimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"gr'
    'eeks_record_id\\\\\\",\\\\\\"tail-history-2-30-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$de'
    'cimal\\\\\\":\\\\\\"0.18\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-2-30-call10-iv\\\\\\"],[\\\\\\"option_'
    'type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-2-30-call10-quote\\\\\\"],[\\\\\\"sig'
    'ned_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}]]}'
    ',{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail'
    '-history-2-30-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],'
    '[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{'
    '\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-2-30-put10-greeks\\\\\\"'
    '],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.36\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-hi'
    'story-2-30-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-his'
    'tory-2-30-put10-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\'
    '\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contra'
    'ct_reference_record_id\\\\\\",\\\\\\"tail-history-2-30-put25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\'
    '\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"'
    '}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\'
    '"tail-history-2-30-put25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}'
    '],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-2-30-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\'
    '\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-2-30-put25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decima'
    'l\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contr'
    'act_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"ve-history-2-0-put-reference\\\\'
    '\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",'
    '{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}]'
    ',[\\\\\\"greeks_record_id\\\\\\",\\\\\\"ve-history-2-0-put-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$'
    'decimal\\\\\\":\\\\\\"0.23\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"ve-history-2-0-put-iv\\\\\\"],[\\\\\\"option_type'
    '\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"ve-history-2-0-put-quote\\\\\\"],[\\\\\\"signed_delta\\\\'
    '\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"d'
    'ownside_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.080\\\\\\"}],[\\\\\\"downside_wing_curvature\\\\\\",{\\\\'
    '\\"$decimal\\\\\\":\\\\\\"0.06\\\\\\"}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-29\\\\\\"}],[\\\\\\"put_1'
    '0_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.36\\\\\\"}],[\\\\\\"put_25_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0'
    '.30\\\\\\"}],[\\\\\\"selected_call_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contra'
    'ct_reference_record_id\\\\\\",\\\\\\"tail-history-2-30-call10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD'
    '\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"gree'
    'ks_record_id\\\\\\",\\\\\\"tail-history-2-30-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$deci'
    'mal\\\\\\":\\\\\\"0.18\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-2-30-call10-iv\\\\\\"],[\\\\\\"option_ty'
    'pe\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-2-30-call10-quote\\\\\\"],[\\\\\\"selec'
    'ted_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}],['
    '\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.10\\\\\\"}]]}],[\\\\\\"selected_call_25\\\\\\",{\\\\\\"$map\\\\\\"'
    ':[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-2-30-'
    'call25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance'
    '\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-2-30-call25-gre'
    'eks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"'
    'tail-history-2-30-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\'
    '"tail-history-2-30-call25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\'
    '\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\'
    '\\"}]]}],[\\\\\\"selected_paired_atm_evidence\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{\\\\\\"$list'
    '\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference_record_id\\\\\\",\\\\\\"ve-history-2-0-call-referenc'
    'e\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.21\\\\\\"}],[\\\\\\"call_iv_record_id\\'
    '\\\\",\\\\\\"ve-history-2-0-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"ve-history-2-0-call-quote\\'
    '\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",nu'
    'll],[\\\\\\"distance_to_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied'
    '_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.220\\\\\\"}],[\\\\\\"put_contract_reference_record_id\\\\\\",\\\\\\"'
    've-history-2-0-put-reference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.23\\\\\\"'
    '}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"ve-history-2-0-put-iv\\\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"ve-'
    'history-2-0-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"selected_at'
    'm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.220\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-history-2-'
    '0-call-iv\\\\\\"],[\\\\\\"selected_put_iv_record_id\\\\\\",\\\\\\"ve-history-2-0-put-iv\\\\\\"],[\\\\\\"selected_s'
    'trike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100'
    '.0\\\\\\"}]]}],[\\\\\\"selected_put_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contr'
    'act_reference_record_id\\\\\\",\\\\\\"tail-history-2-30-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD'
    '\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"gree'
    'ks_record_id\\\\\\",\\\\\\"tail-history-2-30-put10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decim'
    'al\\\\\\":\\\\\\"0.36\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-2-30-put10-iv\\\\\\"],[\\\\\\"option_type'
    '\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-2-30-put10-quote\\\\\\"],[\\\\\\"selected_'
    'delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}],[\\\\\\"'
    'target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.10\\\\\\"}]]}],[\\\\\\"selected_put_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\'
    '\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-2-30-put2'
    '5-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",'
    '{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-2-30-put25-greeks\\\\\\'
    '"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-h'
    'istory-2-30-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-hi'
    'story-2-30-put25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strik'
    'e\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.25\\\\\\"}]]}],'
    '[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-30\\\\\\"}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\'
    '\\"ve-history-2-underlying\\\\\\"],[\\\\\\"upside_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.020\\\\\\"}],'
    '[\\\\\\"upside_wing_curvature\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.02\\\\\\"}]]}]}],[\\\\\\"tenor_days\\\\\\",30]]},'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"current_expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"historical_o'
    'bservations\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.300\\\\\\"}]'
    ',[\\\\\\"call_10_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.26\\\\\\"}],[\\\\\\"call_25_delta_iv\\\\\\",{\\\\\\"$deci'
    'mal\\\\\\":\\\\\\"0.28\\\\\\"}],[\\\\\\"candidate_contracts\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract'
    '_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-call-refere'
    'nce\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target'
    '\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\'
    '\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-call-greeks\\\\\\"],[\\\\\\"implied_volatili'
    'ty\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-call-iv\\'
    '\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-call-'
    'quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"100\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_rec'
    'ord_id\\\\\\",\\\\\\"tail-history-0-60-call25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliv'
    'erable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"distanc'
    'e_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0'
    '-60-call25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.28\\\\\\"}],[\\\\\\"iv_reco'
    'rd_id\\\\\\",\\\\\\"tail-history-0-60-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_rec'
    'ord_id\\\\\\",\\\\\\"tail-history-0-60-call25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0'
    '.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multipl'
    'ier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-0-60-call10-reference\\\\\\"],['
    '\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"'
    '$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\'
    '"greeks_record_id\\\\\\",\\\\\\"tail-history-0-60-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"'
    '$decimal\\\\\\":\\\\\\"0.26\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-60-call10-iv\\\\\\"],[\\\\\\"opti'
    'on_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-60-call10-quote\\\\\\"],[\\\\\\"'
    'signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}'
    ']]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"t'
    'ail-history-0-60-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",nul'
    'l],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\'
    '",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0-60-put10-greeks\\'
    '\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail'
    '-history-0-60-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-'
    'history-0-60-put10-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strik'
    'e\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"con'
    'tract_reference_record_id\\\\\\",\\\\\\"tail-history-0-60-put25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"U'
    'SD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\'
    '\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",'
    '\\\\\\"tail-history-0-60-put25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.34\\\\'
    '\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-60-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"]'
    ',[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-60-put25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$dec'
    'imal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"co'
    'ntract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-put-r'
    'eference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_t'
    'arget\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"'
    '0.25\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-put-greeks\\\\\\"],[\\\\\\"implied_vola'
    'tility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-put-'
    'iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-put'
    '-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decima'
    'l\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"downside_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.040\\\\\\"}],[\\\\\\"'
    'downside_wing_curvature\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.06\\\\\\"}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":'
    '\\\\\\"2030-02-22\\\\\\"}],[\\\\\\"put_10_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"put_25_delta'
    '_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.34\\\\\\"}],[\\\\\\"selected_call_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_'
    'multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-0-60-call10-reference'
    '\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decim'
    'al\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0-60-call10-greeks\\\\\\"],[\\\\\\"im'
    'plied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.26\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-6'
    '0-call10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-'
    '60-call10-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\'
    '\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.10\\\\\\"}]]}],[\\\\\\"sel'
    'ected_call_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_recor'
    'd_id\\\\\\",\\\\\\"tail-history-0-60-call25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliver'
    'able_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\'
    '\\\\"tail-history-0-60-call25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.28\\\\'
    '\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-60-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\'
    '"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-60-call25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\'
    '"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}],[\\\\\\"target_delta\\\\'
    '\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}]]}],[\\\\\\"selected_paired_atm_evidence\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\'
    '"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference_record_id\\\\\\",\\'
    '\\\\"tail-history-0-60-atm-call-reference\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":'
    '\\\\\\"0.30\\\\\\"}],[\\\\\\"call_iv_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-call-iv\\\\\\"],[\\\\\\"call_quote'
    '_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-call-quote\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"'
    'currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_underlying_midpoint\\\\\\"'
    ',{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.300\\'
    '\\\\"}],[\\\\\\"put_contract_reference_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-put-reference\\\\\\"],[\\\\'
    '\\"put_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"tail'
    '-history-0-60-atm-put-iv\\\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-put-quote\\\\'
    '\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"selected_atm_iv\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"0.300\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-call-iv\\\\\\"],['
    '\\\\\\"selected_put_iv_record_id\\\\\\",\\\\\\"tail-history-0-60-atm-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\"'
    ',{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}]]'
    '}],[\\\\\\"selected_put_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_refer'
    'ence_record_id\\\\\\",\\\\\\"tail-history-0-60-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\'
    '\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record'
    '_id\\\\\\",\\\\\\"tail-history-0-60-put10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"0.40\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-60-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"'
    'put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-60-put10-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\"'
    ',{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}],[\\\\\\"target_de'
    'lta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.10\\\\\\"}]]}],[\\\\\\"selected_put_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contra'
    'ct_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-0-60-put25-referen'
    'ce\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$dec'
    'imal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-0-60-put25-greeks\\\\\\"],[\\\\\\"i'
    'mplied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.34\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-0-'
    '60-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-0-6'
    '0-put25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\'
    '\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.25\\\\\\"}]]}],[\\\\\\"sess'
    'ion_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-24\\\\\\"}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"tail-hi'
    'story-0-60-underlying\\\\\\"],[\\\\\\"upside_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.020\\\\\\"}],[\\\\\\'
    '"upside_wing_curvature\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.02\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"atm_iv\\\\\\",{\\'
    '\\\\"$decimal\\\\\\":\\\\\\"0.310\\\\\\"}],[\\\\\\"call_10_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.27\\\\\\"}],[\\\\\\"'
    'call_25_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.29\\\\\\"}],[\\\\\\"candidate_contracts\\\\\\",{\\\\\\"$list\\\\\\'
    '":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"ta'
    'il-history-1-60-atm-call-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",n'
    'ull],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_target\\'
    '\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-1-60-atm-call-gr'
    'eeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.31\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\'
    '"tail-history-1-60-atm-call-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",'
    '\\\\\\"tail-history-1-60-atm-call-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.50\\\\\\"}]'
    ',[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",1'
    '00],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-1-60-call25-reference\\\\\\"],[\\\\\\"curre'
    'ncy\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_r'
    'ecord_id\\\\\\",\\\\\\"tail-history-1-60-call25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"0.29\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-1-60-call25-iv\\\\\\"],[\\\\\\"option_type\\\\'
    '\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-1-60-call25-quote\\\\\\"],[\\\\\\"signed_de'
    'lta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}]]},{\\\\\\"'
    '$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-histo'
    'ry-1-60-call10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"'
    'distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$'
    'decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-1-60-call10-greeks\\\\\\"],[\\'
    '\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.27\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-histor'
    'y-1-60-call10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-histo'
    'ry-1-60-call10-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\"'
    ',{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contrac'
    't_reference_record_id\\\\\\",\\\\\\"tail-history-1-60-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\'
    '\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}'
    '],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"'
    'tail-history-1-60-put10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.43\\\\\\"}]'
    ',[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-1-60-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\'
    '\\"quote_record_id\\\\\\",\\\\\\"tail-history-1-60-put10-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal'
    '\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contra'
    'ct_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-1-60-put25-referen'
    'ce\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\'
    '\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\'
    '\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-1-60-put25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\'
    '\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.37\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-1-60-put25-iv\\\\\\"],[\\'
    '\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-1-60-put25-quote\\\\\\"],'
    '[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95'
    '\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",'
    '\\\\\\"tail-history-1-60-atm-put-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\'
    '\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"distance_to_25_ta'
    'rget\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-1-60-atm-pu'
    't-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.31\\\\\\"}],[\\\\\\"iv_record_id\\\\\\"'
    ',\\\\\\"tail-history-1-60-atm-put-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\'
    '",\\\\\\"tail-history-1-60-atm-put-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.50\\\\\\"'
    '}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"downside_25_delta_skew\\\\\\",{\\\\\\"$de'
    'cimal\\\\\\":\\\\\\"0.060\\\\\\"}],[\\\\\\"downside_wing_curvature\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.06\\\\\\"}],[\\\\\\'
    '"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-02-25\\\\\\"}],[\\\\\\"put_10_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\'
    '\\\\"0.43\\\\\\"}],[\\\\\\"put_25_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.37\\\\\\"}],[\\\\\\"selected_call_10\\\\\\'
    '",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tai'
    'l-history-1-60-call10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null'
    '],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-'
    '1-60-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.27\\\\\\"}],[\\\\\\"iv_rec'
    'ord_id\\\\\\",\\\\\\"tail-history-1-60-call10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_re'
    'cord_id\\\\\\",\\\\\\"tail-history-1-60-call10-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal'
    '\\\\\\":\\\\\\"0.10\\\\\\"}]]}],[\\\\\\"selected_call_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100'
    '],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-1-60-call25-reference\\\\\\"],[\\\\\\"currenc'
    'y\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\'
    '"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-1-60-call25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\'
    '\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.29\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-1-60-call25-iv\\\\\\"],['
    '\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-1-60-call25-quote\\\\\\'
    '"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"105\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}]]}],[\\\\\\"selected_paired_atm_e'
    'vidence\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_con'
    'tract_reference_record_id\\\\\\",\\\\\\"tail-history-1-60-atm-call-reference\\\\\\"],[\\\\\\"call_implied_vo'
    'latility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.31\\\\\\"}],[\\\\\\"call_iv_record_id\\\\\\",\\\\\\"tail-history-1-60-a'
    'tm-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"tail-history-1-60-atm-call-quote\\\\\\"],[\\\\\\"con'
    'tract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"dist'
    'ance_to_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied_volatility\\\\'
    '\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.310\\\\\\"}],[\\\\\\"put_contract_reference_record_id\\\\\\",\\\\\\"tail-history-'
    '1-60-atm-put-reference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.31\\\\\\"}],[\\\\'
    '\\"put_iv_record_id\\\\\\",\\\\\\"tail-history-1-60-atm-put-iv\\\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"ta'
    'il-history-1-60-atm-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"sel'
    'ected_atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.310\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"tail-'
    'history-1-60-atm-call-iv\\\\\\"],[\\\\\\"selected_put_iv_record_id\\\\\\",\\\\\\"tail-history-1-60-atm-put-i'
    'v\\\\\\"],[\\\\\\"selected_strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"underlying_midpoint\\\\\\",{\\\\'
    '\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}]]}],[\\\\\\"selected_put_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multipli'
    'er\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-1-60-put10-reference\\\\\\"],[\\\\'
    '\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\'
    '\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-1-60-put10-greeks\\\\\\"],[\\\\\\"implied_vola'
    'tility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.43\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-1-60-put10-iv'
    '\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-1-60-put10-quo'
    'te\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"90\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.10\\\\\\"}]]}],[\\\\\\"selected_put_25'
    '\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"'
    'tail-history-1-60-put25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",nu'
    'll],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-histor'
    'y-1-60-put25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.37\\\\\\"}],[\\\\\\"iv_re'
    'cord_id\\\\\\",\\\\\\"tail-history-1-60-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_rec'
    'ord_id\\\\\\",\\\\\\"tail-history-1-60-put25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"'
    '-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\'
    '\\":\\\\\\"-0.25\\\\\\"}]]}],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-27\\\\\\"}],[\\\\\\"underlying_'
    'quote_record_id\\\\\\",\\\\\\"tail-history-1-60-underlying\\\\\\"],[\\\\\\"upside_25_delta_skew\\\\\\",{\\\\\\"$de'
    'cimal\\\\\\":\\\\\\"-0.020\\\\\\"}],[\\\\\\"upside_wing_curvature\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.02\\\\\\"}]]},{\\'
    '\\\\"$map\\\\\\":[[\\\\\\"atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.320\\\\\\"}],[\\\\\\"call_10_delta_iv\\\\\\",{\\\\\\"$d'
    'ecimal\\\\\\":\\\\\\"0.28\\\\\\"}],[\\\\\\"call_25_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"candid'
    'ate_contracts\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract'
    '_reference_record_id\\\\\\",\\\\\\"tail-history-2-60-atm-call-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD'
    '\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\'
    '"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\'
    '\\"tail-history-2-60-atm-call-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.32\\'
    '\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-2-60-atm-call-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call'
    '\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-2-60-atm-call-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{'
    '\\\\\\"$decimal\\\\\\":\\\\\\"0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]},{\\\\\\"$map\\\\\\":'
    '[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-2-60-c'
    'all25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_'
    'to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\'
    '\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-2-60-call25-greeks\\\\\\"],[\\\\\\"implie'
    'd_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-2-60-ca'
    'll25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-2-60-c'
    'all25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$de'
    'cimal\\\\\\":\\\\\\"105\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_referen'
    'ce_record_id\\\\\\",\\\\\\"tail-history-2-60-call10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\'
    '"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"d'
    'istance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-his'
    'tory-2-60-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.28\\\\\\"}],[\\\\\\"i'
    'v_record_id\\\\\\",\\\\\\"tail-history-2-60-call10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quo'
    'te_record_id\\\\\\",\\\\\\"tail-history-2-60-call10-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\"'
    ':\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_m'
    'ultiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-2-60-put10-reference\\\\'
    '\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",'
    '{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}]'
    ',[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-2-60-put10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{'
    '\\\\\\"$decimal\\\\\\":\\\\\\"0.46\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-2-60-put10-iv\\\\\\"],[\\\\\\"o'
    'ption_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-2-60-put10-quote\\\\\\"],[\\\\\\'
    '"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"'
    '}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"'
    'tail-history-2-60-put25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",nu'
    'll],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.14\\\\\\"}],[\\\\\\"distance_to_25_target\\\\'
    '\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-2-60-put25-greeks'
    '\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tai'
    'l-history-2-60-put25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail'
    '-history-2-60-put25-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"stri'
    'ke\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"co'
    'ntract_reference_record_id\\\\\\",\\\\\\"tail-history-2-60-atm-put-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\'
    '\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_10_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.'
    '40\\\\\\"}],[\\\\\\"distance_to_25_target\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\\\"greeks_record_id\\\\'
    '\\",\\\\\\"tail-history-2-60-atm-put-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0'
    '.32\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-2-60-atm-put-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"p'
    'ut\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-2-60-atm-put-quote\\\\\\"],[\\\\\\"signed_delta\\\\\\",'
    '{\\\\\\"$decimal\\\\\\":\\\\\\"-0.50\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"down'
    'side_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.080\\\\\\"}],[\\\\\\"downside_wing_curvature\\\\\\",{\\\\\\"$'
    'decimal\\\\\\":\\\\\\"0.06\\\\\\"}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-02-28\\\\\\"}],[\\\\\\"put_10_d'
    'elta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.46\\\\\\"}],[\\\\\\"put_25_delta_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40'
    '\\\\\\"}],[\\\\\\"selected_call_10\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_'
    'reference_record_id\\\\\\",\\\\\\"tail-history-2-60-call10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\'
    '"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_'
    'record_id\\\\\\",\\\\\\"tail-history-2-60-call10-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal'
    '\\\\\\":\\\\\\"0.28\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-2-60-call10-iv\\\\\\"],[\\\\\\"option_type\\'
    '\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-2-60-call10-quote\\\\\\"],[\\\\\\"selected'
    '_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.11\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"110\\\\\\"}],[\\\\\\'
    '"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.10\\\\\\"}]]}],[\\\\\\"selected_call_25\\\\\\",{\\\\\\"$map\\\\\\":[['
    '\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-history-2-60-cal'
    'l25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\'
    '",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-2-60-call25-greeks'
    '\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tai'
    'l-history-2-60-call25-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"ta'
    'il-history-2-60-call25-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.24\\\\\\"}],[\\\\\\"'
    'strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"105\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}'
    ']]}],[\\\\\\"selected_paired_atm_evidence\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\'
    '":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference_record_id\\\\\\",\\\\\\"tail-history-2-60-atm-call-refe'
    'rence\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.32\\\\\\"}],[\\\\\\"call_iv_record'
    '_id\\\\\\",\\\\\\"tail-history-2-60-atm-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"tail-history-2-'
    '60-atm-call-quote\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"del'
    'iverable_id\\\\\\",null],[\\\\\\"distance_to_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],['
    '\\\\\\"paired_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.320\\\\\\"}],[\\\\\\"put_contract_reference_'
    'record_id\\\\\\",\\\\\\"tail-history-2-60-atm-put-reference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"'
    '$decimal\\\\\\":\\\\\\"0.32\\\\\\"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"tail-history-2-60-atm-put-iv\\\\\\"],[\\\\\\'
    '"put_quote_record_id\\\\\\",\\\\\\"tail-history-2-60-atm-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\'
    '\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"selected_atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.320\\\\\\"}],[\\\\\\"selected_'
    'call_iv_record_id\\\\\\",\\\\\\"tail-history-2-60-atm-call-iv\\\\\\"],[\\\\\\"selected_put_iv_record_id\\\\\\",'
    '\\\\\\"tail-history-2-60-atm-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],['
    '\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}]]}],[\\\\\\"selected_put_10\\\\\\",{\\\\\\"$'
    'map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contract_reference_record_id\\\\\\",\\\\\\"tail-histor'
    'y-2-60-put10-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"di'
    'stance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greeks_record_id\\\\\\",\\\\\\"tail-history-2-60-put1'
    '0-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.46\\\\\\"}],[\\\\\\"iv_record_id\\\\\\"'
    ',\\\\\\"tail-history-2-60-put10-iv\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",'
    '\\\\\\"tail-history-2-60-put10-quote\\\\\\"],[\\\\\\"selected_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.11\\\\\\"}]'
    ',[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"90\\\\\\"}],[\\\\\\"target_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.1'
    '0\\\\\\"}]]}],[\\\\\\"selected_put_25\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"contra'
    'ct_reference_record_id\\\\\\",\\\\\\"tail-history-2-60-put25-reference\\\\\\"],[\\\\\\"currency\\\\\\",\\\\\\"USD\\'
    '\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.01\\\\\\"}],[\\\\\\"greek'
    's_record_id\\\\\\",\\\\\\"tail-history-2-60-put25-greeks\\\\\\"],[\\\\\\"implied_volatility\\\\\\",{\\\\\\"$decima'
    'l\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"iv_record_id\\\\\\",\\\\\\"tail-history-2-60-put25-iv\\\\\\"],[\\\\\\"option_type\\'
    '\\\\",\\\\\\"put\\\\\\"],[\\\\\\"quote_record_id\\\\\\",\\\\\\"tail-history-2-60-put25-quote\\\\\\"],[\\\\\\"selected_d'
    'elta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.24\\\\\\"}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"95\\\\\\"}],[\\\\\\"t'
    'arget_delta\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.25\\\\\\"}]]}],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"20'
    '29-12-30\\\\\\"}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"tail-history-2-60-underlying\\\\\\"],[\\\\\\"up'
    'side_25_delta_skew\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.020\\\\\\"}],[\\\\\\"upside_wing_curvature\\\\\\",{\\\\\\"$d'
    'ecimal\\\\\\":\\\\\\"-0.02\\\\\\"}]]}]}],[\\\\\\"tenor_days\\\\\\",60]]}]}],[\\\\\\"interpolation_rule\\\\\\",\\\\\\"non'
    'e\\\\\\"],[\\\\\\"normalized_evidence\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"direct_inputs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$'
    'map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"pr'
    'opagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-30-call10-gre'
    'eks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-curre'
    'nt-30-call10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\'
    '\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"'
    'record_id\\\\\\",\\\\\\"tail-current-30-call10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"'
    '],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30-call10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\'
    '\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propag'
    'ated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-30-call10-quote\\\\'
    '\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30-'
    'call10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030'
    '-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_'
    'id\\\\\\",\\\\\\"tail-current-30-call10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"'
    '],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30-call10-reference-source-0\\\\\\"]}]]},{\\\\'
    '\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\'
    '"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-30-call25-'
    'greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-cu'
    'rrent-30-call25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\'
    '":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\'
    '\\\\"record_id\\\\\\",\\\\\\"tail-current-30-call25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\'
    '\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30-call25-iv-source-0\\\\\\"]}]]},{\\\\\\"$m'
    'ap\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"pro'
    'pagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-30-call25-quot'
    'e\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-'
    '30-call25-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2'
    '030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"reco'
    'rd_id\\\\\\",\\\\\\"tail-current-30-call25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\'
    '\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30-call25-reference-source-0\\\\\\"]}]]},'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],['
    '\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-30-put1'
    '0-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-'
    'current-30-put10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\'
    '\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],['
    '\\\\\\"record_id\\\\\\",\\\\\\"tail-current-30-put10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\'
    '\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30-put10-iv-source-0\\\\\\"]}]]},{\\\\\\"$ma'
    'p\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"prop'
    'agated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-30-put10-quote\\'
    '\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30'
    '-put10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030'
    '-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_'
    'id\\\\\\",\\\\\\"tail-current-30-put10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"]'
    ',[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30-put10-reference-source-0\\\\\\"]}]]},{\\\\\\"'
    '$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"p'
    'ropagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-30-put25-gre'
    'eks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-curre'
    'nt-30-put25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\'
    '\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"r'
    'ecord_id\\\\\\",\\\\\\"tail-current-30-put25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],'
    '[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30-put25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\"'
    ':[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagate'
    'd_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-30-put25-quote\\\\\\"],'
    '[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30-put2'
    '5-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-0'
    '2T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\'
    '",\\\\\\"tail-current-30-put25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\'
    '"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-30-put25-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\'
    '\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propag'
    'ated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-60-call10-greeks\\'
    '\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-6'
    '0-call10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2'
    '030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"reco'
    'rd_id\\\\\\",\\\\\\"tail-current-60-call10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\'
    '\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-call10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":'
    '[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated'
    '_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-60-call10-quote\\\\\\"],'
    '[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-call'
    '10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-'
    '02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\'
    '\\",\\\\\\"tail-current-60-call10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\'
    '\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-call10-reference-source-0\\\\\\"]}]]},{\\\\\\"$m'
    'ap\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"pro'
    'pagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-60-call25-gree'
    'ks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-curren'
    't-60-call25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\'
    '\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"r'
    'ecord_id\\\\\\",\\\\\\"tail-current-60-call25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"]'
    ',[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-call25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\'
    '\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propaga'
    'ted_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-60-call25-quote\\\\\\'
    '"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-c'
    'all25-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-'
    '01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_i'
    'd\\\\\\",\\\\\\"tail-current-60-call25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"]'
    ',[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-call25-reference-source-0\\\\\\"]}]]},{\\\\\\'
    '"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"'
    'propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-60-put10-gr'
    'eeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-curr'
    'ent-60-put10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\'
    '\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"'
    'record_id\\\\\\",\\\\\\"tail-current-60-put10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"]'
    ',[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-put10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\'
    '":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagat'
    'ed_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-60-put10-quote\\\\\\"]'
    ',[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-put'
    '10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-'
    '02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\'
    '\\",\\\\\\"tail-current-60-put10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\'
    '\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-put10-reference-source-0\\\\\\"]}]]},{\\\\\\"$map'
    '\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propa'
    'gated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-60-put25-greeks\\'
    '\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-6'
    '0-put25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"20'
    '30-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"recor'
    'd_id\\\\\\",\\\\\\"tail-current-60-put25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\'
    '"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-put25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\'
    '\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_qu'
    'ality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-current-60-put25-quote\\\\\\"],[\\\\\\'
    '"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-put25-qu'
    'ote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15'
    ':30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\'
    '\\"tail-current-60-put25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"sou'
    'rce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-current-60-put25-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":'
    '[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated'
    '_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-30-call10-greeks\\\\\\'
    '"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-3'
    '0-call10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2'
    '030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"reco'
    'rd_id\\\\\\",\\\\\\"tail-history-0-30-call10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],'
    '[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-30-call10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\'
    '\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propag'
    'ated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-30-call10-quote'
    '\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0'
    '-30-call10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"'
    '2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"rec'
    'ord_id\\\\\\",\\\\\\"tail-history-0-30-call10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_referen'
    'ce\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-30-call10-reference-source-0\\\\\\"]'
    '}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\'
    '"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-'
    '30-call25-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\'
    '\\\\"tail-history-0-30-call25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"'
    '$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list'
    '\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-30-call25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_impli'
    'ed_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-30-call25-iv-source-0\\'
    '\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-histor'
    'y-0-30-call25-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":'
    '[\\\\\\"tail-history-0-30-call25-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\'
    '"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$lis'
    't\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-30-call25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"opti'
    'on_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-30-call25-refe'
    'rence-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T'
    '15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",'
    '\\\\\\"tail-history-0-30-put10-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\"'
    ',{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-30-put10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normal'
    'ized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_fla'
    'gs\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-30-put10-iv\\\\\\"],[\\\\\\"role\\\\\\",'
    '\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-30-put'
    '10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T'
    '15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",'
    '\\\\\\"tail-history-0-30-put10-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{'
    '\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-30-put10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalize'
    'd_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\'
    '\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-30-put10-reference\\\\\\"],[\\\\\\"role\\'
    '\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-30'
    '-put10-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"'
    '2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"rec'
    'ord_id\\\\\\",\\\\\\"tail-history-0-30-put25-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"sou'
    'rce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-30-put25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":['
    '[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_'
    'quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-30-put25-iv\\\\\\"],[\\\\'
    '\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-histo'
    'ry-0-30-put25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"'
    '2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"rec'
    'ord_id\\\\\\",\\\\\\"tail-history-0-30-put25-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"sourc'
    'e_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-30-put25-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\'
    '\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_qua'
    'lity_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-30-put25-reference\\\\\\"]'
    ',[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-h'
    'istory-0-30-put25-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$dateti'
    'me\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]'
    '}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-atm-call-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks'
    '\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-atm-call-greeks-source-0\\\\\\"]}]]'
    '},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}]'
    ',[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-'
    'atm-call-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list'
    '\\\\\\":[\\\\\\"tail-history-0-60-atm-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",'
    '{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"'
    '$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-atm-call-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"op'
    'tion_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-atm-call-quote-source-'
    '0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.0000'
    '02Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-hist'
    'ory-0-60-atm-call-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_id'
    's\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-atm-call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":['
    '[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_'
    'quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-atm-put-greeks\\\\\\'
    '"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-6'
    '0-atm-put-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"'
    '2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"rec'
    'ord_id\\\\\\",\\\\\\"tail-history-0-60-atm-put-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"'
    '],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-atm-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$m'
    'ap\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"pro'
    'pagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-atm-put-q'
    'uote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-histo'
    'ry-0-60-atm-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\"'
    ':\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\'
    '\\"record_id\\\\\\",\\\\\\"tail-history-0-60-atm-put-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_r'
    'eference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-atm-put-reference-source'
    '-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000'
    '002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-his'
    'tory-0-60-call10-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list'
    '\\\\\\":[\\\\\\"tail-history-0-60-call10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\'
    '",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\'
    '\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-call10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"optio'
    'n_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-call10-iv-so'
    'urce-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00'
    '.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail'
    '-history-0-60-call10-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$li'
    'st\\\\\\":[\\\\\\"tail-history-0-60-call10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\'
    '\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\'
    '\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-call10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\'
    '\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-call'
    '10-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030'
    '-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_'
    'id\\\\\\",\\\\\\"tail-history-0-60-call25-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source'
    '_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-call25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\'
    '\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_qu'
    'ality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-call25-iv\\\\\\"],[\\\\\\'
    '"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-histor'
    'y-0-60-call25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"'
    '2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"rec'
    'ord_id\\\\\\",\\\\\\"tail-history-0-60-call25-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"sour'
    'ce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-call25-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[['
    '\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_q'
    'uality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-call25-reference\\\\'
    '\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tai'
    'l-history-0-60-call25-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$da'
    'tetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\'
    '":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-put10-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greek'
    's\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-put10-greeks-source-0\\\\\\"]}]]},'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],['
    '\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-pu'
    't10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":'
    '[\\\\\\"tail-history-0-60-put10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$da'
    'tetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\'
    '":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-put10-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\'
    '\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-put10-quote-source-0\\\\\\"]}]]},{\\\\'
    '\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\'
    '"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-put10'
    '-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\'
    '\\\\":[\\\\\\"tail-history-0-60-put10-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\'
    '\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\'
    '\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-put25-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"o'
    'ption_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-put25-greeks-source-'
    '0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.0000'
    '02Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-hist'
    'ory-0-60-put25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\'
    '"$list\\\\\\":[\\\\\\"tail-history-0-60-put25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\'
    '\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\'
    '\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-put25-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"op'
    'tion_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-put25-quote-source-0\\\\'
    '\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z'
    '\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history'
    '-0-60-put25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",'
    '{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-put25-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"norm'
    'alized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_f'
    'lags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-0-60-underlying\\\\\\"],[\\\\\\"role\\'
    '\\\\",\\\\\\"underlying_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-0-60-underlyi'
    'ng-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:'
    '30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\'
    '"tail-history-1-30-call10-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{'
    '\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-call10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normali'
    'zed_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flag'
    's\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-30-call10-iv\\\\\\"],[\\\\\\"role\\\\\\",'
    '\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-cal'
    'l10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02'
    'T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\"'
    ',\\\\\\"tail-history-1-30-call10-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\"'
    ',{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-call10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normal'
    'ized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_fla'
    'gs\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-30-call10-reference\\\\\\"],[\\\\\\"r'
    'ole\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-'
    '1-30-call10-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\"'
    ':\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\'
    '\\"record_id\\\\\\",\\\\\\"tail-history-1-30-call25-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\'
    '\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-call25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$ma'
    'p\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"prop'
    'agated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-30-call25-iv\\'
    '\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ta'
    'il-history-1-30-call25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime'
    '\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}]'
    ',[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-30-call25-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],'
    '[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-call25-quote-source-0\\\\\\"]}]]},{\\\\\\"$m'
    'ap\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"pro'
    'pagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-30-call25-re'
    'ference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\"'
    ':[\\\\\\"tail-history-1-30-call25-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\"'
    ',{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\'
    '"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-30-put10-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"opt'
    'ion_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-put10-greeks-source-0\\'
    '\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-histor'
    'y-1-30-put10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$'
    'list\\\\\\":[\\\\\\"tail-history-1-30-put10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\"'
    ',{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\'
    '"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-30-put10-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"opti'
    'on_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-put10-quote-source-0\\\\\\"'
    ']}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\'
    '\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1'
    '-30-put10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\'
    '\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-put10-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normal'
    'ized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_fla'
    'gs\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-30-put25-greeks\\\\\\"],[\\\\\\"role\\'
    '\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-put25-greek'
    's-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:3'
    '0:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"'
    'tail-history-1-30-put25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids'
    '\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-put25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normal'
    'ized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_fla'
    'gs\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-30-put25-quote\\\\\\"],[\\\\\\"role\\\\'
    '\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-put25-quote-s'
    'ource-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:0'
    '0.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tai'
    'l-history-1-30-put25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source'
    '_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-30-put25-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":['
    '[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_'
    'quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-atm-call-greeks\\\\'
    '\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-'
    '60-atm-call-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\'
    '\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"r'
    'ecord_id\\\\\\",\\\\\\"tail-history-1-60-atm-call-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\'
    '\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-atm-call-iv-source-0\\\\\\"]}]]},{\\\\'
    '\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\'
    '"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-atm-c'
    'all-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-'
    'history-1-60-atm-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$dateti'
    'me\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]'
    '}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-atm-call-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_con'
    'tract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-atm-call-referenc'
    'e-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:3'
    '0:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"'
    'tail-history-1-60-atm-put-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{'
    '\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-atm-put-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normal'
    'ized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_fla'
    'gs\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-atm-put-iv\\\\\\"],[\\\\\\"role\\\\\\'
    '",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-a'
    'tm-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01'
    '-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\'
    '\\\\",\\\\\\"tail-history-1-60-atm-put-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids'
    '\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-atm-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"n'
    'ormalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_qualit'
    'y_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-atm-put-reference\\\\\\"],'
    '[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-hi'
    'story-1-60-atm-put-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datet'
    'ime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":['
    ']}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-call10-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\'
    '\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-call10-greeks-source-0\\\\\\"]}]]},{'
    '\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\'
    '\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-cal'
    'l10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":'
    '[\\\\\\"tail-history-1-60-call10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$d'
    'atetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\'
    '\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-call10-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quot'
    'e\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-call10-quote-source-0\\\\\\"]}]]},'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],['
    '\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-ca'
    'll10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$l'
    'ist\\\\\\":[\\\\\\"tail-history-1-60-call10-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized'
    '_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\'
    '\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-call25-greeks\\\\\\"],[\\\\\\"role\\\\\\"'
    ',\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-call25-greeks-'
    'source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:'
    '00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ta'
    'il-history-1-60-call25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\'
    '\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-call25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normal'
    'ized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_fla'
    'gs\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-call25-quote\\\\\\"],[\\\\\\"role\\'
    '\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-call25-quote'
    '-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30'
    ':00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"t'
    'ail-history-1-60-call25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"sou'
    'rce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-call25-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\'
    '\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propaga'
    'ted_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-put10-greeks\\'
    '\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1'
    '-60-put10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"'
    '2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"rec'
    'ord_id\\\\\\",\\\\\\"tail-history-1-60-put10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],'
    '[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-put10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\'
    '\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propaga'
    'ted_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-put10-quote\\\\'
    '\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-6'
    '0-put10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"203'
    '0-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record'
    '_id\\\\\\",\\\\\\"tail-history-1-60-put10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\'
    '\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-put10-reference-source-0\\\\\\"]}]]},'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],['
    '\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-pu'
    't25-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tai'
    'l-history-1-60-put25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$dateti'
    'me\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]'
    '}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-put25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volat'
    'ility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-put25-iv-source-0\\\\\\"]}]]},'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],['
    '\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-pu'
    't25-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-'
    'history-1-60-put25-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\'
    '\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],'
    '[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-1-60-put25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_'
    'reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-1-60-put25-reference-source-'
    '0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.0000'
    '02Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-hist'
    'ory-1-60-underlying\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"underlying_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\'
    '\\\\":[\\\\\\"tail-history-1-60-underlying-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\'
    '\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$l'
    'ist\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-30-call10-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"optio'
    'n_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-call10-greeks-source-0\\\\'
    '\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z'
    '\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history'
    '-2-30-call10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$'
    'list\\\\\\":[\\\\\\"tail-history-2-30-call10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\'
    '",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\'
    '\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-30-call10-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"op'
    'tion_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-call10-quote-source-0\\'
    '\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-histor'
    'y-2-30-call10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\'
    '",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-call10-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"n'
    'ormalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_qualit'
    'y_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-30-call25-greeks\\\\\\"],[\\\\\\'
    '"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-call2'
    '5-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-'
    '02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\'
    '\\",\\\\\\"tail-history-2-30-call25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"so'
    'urce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-call25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\'
    '\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_qu'
    'ality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-30-call25-quote\\\\\\"],['
    '\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-cal'
    'l25-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01'
    '-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\'
    '\\\\",\\\\\\"tail-history-2-30-call25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"]'
    ',[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-call25-reference-source-0\\\\\\"]}]]},{\\'
    '\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\'
    '\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-30-put1'
    '0-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-'
    'history-2-30-put10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime'
    '\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}]'
    ',[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-30-put10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatil'
    'ity\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-put10-iv-source-0\\\\\\"]}]]},{\\'
    '\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\'
    '\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-30-put1'
    '0-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-hi'
    'story-2-30-put10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\'
    '":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\'
    '\\\\"record_id\\\\\\",\\\\\\"tail-history-2-30-put10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_re'
    'ference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-put10-reference-source-0\\'
    '\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-histor'
    'y-2-30-put25-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\"'
    ':[\\\\\\"tail-history-2-30-put25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\'
    '\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$li'
    'st\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-30-put25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_impl'
    'ied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-put25-iv-source-0\\'
    '\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-histor'
    'y-2-30-put25-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":['
    '\\\\\\"tail-history-2-30-put25-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$'
    'datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\'
    '\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-30-put25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_'
    'contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-30-put25-referenc'
    'e-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:3'
    '0:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"'
    'tail-history-2-60-atm-call-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",'
    '{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-atm-call-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"norm'
    'alized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_f'
    'lags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-atm-call-iv\\\\\\"],[\\\\\\"role'
    '\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-6'
    '0-atm-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"203'
    '0-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record'
    '_id\\\\\\",\\\\\\"tail-history-2-60-atm-call-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"sourc'
    'e_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-atm-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":['
    '[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_'
    'quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-atm-call-referenc'
    'e\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"'
    'tail-history-2-60-atm-call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\'
    '\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$li'
    'st\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-atm-put-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"optio'
    'n_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-atm-put-greeks-source-0\\'
    '\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-histor'
    'y-2-60-atm-put-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\'
    '"$list\\\\\\":[\\\\\\"tail-history-2-60-atm-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at'
    '\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",'
    '{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-atm-put-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\'
    '\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-atm-put-quote-sour'
    'ce-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.0'
    '00002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-h'
    'istory-2-60-atm-put-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_'
    'ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-atm-put-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":'
    '[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated'
    '_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-call10-greeks\\\\\\'
    '"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-6'
    '0-call10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2'
    '030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"reco'
    'rd_id\\\\\\",\\\\\\"tail-history-2-60-call10-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],'
    '[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-call10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\'
    '\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propag'
    'ated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-call10-quote'
    '\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2'
    '-60-call10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"'
    '2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"rec'
    'ord_id\\\\\\",\\\\\\"tail-history-2-60-call10-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_referen'
    'ce\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-call10-reference-source-0\\\\\\"]'
    '}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\'
    '"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-'
    '60-call25-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\'
    '\\\\"tail-history-2-60-call25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"'
    '$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list'
    '\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-call25-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_impli'
    'ed_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-call25-iv-source-0\\'
    '\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-histor'
    'y-2-60-call25-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":'
    '[\\\\\\"tail-history-2-60-call25-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\'
    '"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$lis'
    't\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-call25-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"opti'
    'on_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-call25-refe'
    'rence-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T'
    '15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",'
    '\\\\\\"tail-history-2-60-put10-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\"'
    ',{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-put10-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normal'
    'ized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_fla'
    'gs\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-put10-iv\\\\\\"],[\\\\\\"role\\\\\\",'
    '\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-put'
    '10-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T'
    '15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",'
    '\\\\\\"tail-history-2-60-put10-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{'
    '\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-put10-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalize'
    'd_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\'
    '\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-put10-reference\\\\\\"],[\\\\\\"role\\'
    '\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60'
    '-put10-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"'
    '2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"rec'
    'ord_id\\\\\\",\\\\\\"tail-history-2-60-put25-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"sou'
    'rce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-put25-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":['
    '[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_'
    'quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-put25-iv\\\\\\"],[\\\\'
    '\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-histo'
    'ry-2-60-put25-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"'
    '2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"rec'
    'ord_id\\\\\\",\\\\\\"tail-history-2-60-put25-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"sourc'
    'e_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-put25-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\'
    '\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_qua'
    'lity_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-put25-reference\\\\\\"]'
    ',[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-h'
    'istory-2-60-put25-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$dateti'
    'me\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]'
    '}],[\\\\\\"record_id\\\\\\",\\\\\\"tail-history-2-60-underlying\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"underlying_quote\\\\'
    '\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"tail-history-2-60-underlying-source-0\\\\\\"]}]]},{\\\\\\"'
    '$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"p'
    'ropagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-call-greeks\\'
    '\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-c'
    'all-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-0'
    '1-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id'
    '\\\\\\",\\\\\\"ve-current-0-call-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_'
    'ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalize'
    'd_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\'
    '\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-call-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"op'
    'tion_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-call-quote-source-0\\\\\\"]}]]'
    '},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}]'
    ',[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-call-'
    'reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\'
    '\\":[\\\\\\"ve-current-0-call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\'
    '"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$lis'
    't\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-put-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\'
    '\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-put-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\'
    '\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propag'
    'ated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-put-iv\\\\\\"],[\\\\\\"'
    'role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0'
    '-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-0'
    '2T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\'
    '",\\\\\\"ve-current-0-put-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$'
    'list\\\\\\":[\\\\\\"ve-current-0-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\'
    '\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$li'
    'st\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-put-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_cont'
    'ract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-put-reference-source-0\\'
    '\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002'
    'Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-'
    '1-call-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"'
    've-current-1-call-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\'
    '\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],'
    '[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-call-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"'
    '],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":['
    '[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_'
    'quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-call-quote\\\\\\"],[\\\\\\"r'
    'ole\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-call-quote-so'
    'urce-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00'
    '.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-c'
    'urrent-1-call-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\'
    '",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normaliz'
    'ed_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags'
    '\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-put-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"o'
    'ption_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-put-greeks-source-0\\\\\\"]}'
    ']]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"'
    '}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-put'
    '-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\'
    '\\"ve-current-1-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\"'
    ':\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\'
    '\\"record_id\\\\\\",\\\\\\"ve-current-1-put-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_'
    'ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normali'
    'zed_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flag'
    's\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-put-reference\\\\\\"],[\\\\\\"role\\\\\\",\\'
    '\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-put-refer'
    'ence-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T1'
    '5:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\'
    '\\\\"ve-current-underlying\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"underlying_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$'
    'list\\\\\\":[\\\\\\"ve-current-underlying-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\'
    '"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$lis'
    't\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-call-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greek'
    's\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-call-greeks-source-0\\\\\\"]}]]},{\\\\\\'
    '"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"'
    'propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-call-iv\\\\'
    '\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-'
    'history-0-0-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\'
    '\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"'
    'record_id\\\\\\",\\\\\\"ve-history-0-0-call-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source'
    '_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"nor'
    'malized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_'
    'flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-call-reference\\\\\\"],[\\\\\\"rol'
    'e\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-'
    'call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"20'
    '30-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"recor'
    'd_id\\\\\\",\\\\\\"ve-history-0-0-put-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids'
    '\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-put-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normali'
    'zed_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flag'
    's\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-put-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"op'
    'tion_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-put-iv-sourc'
    'e-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.00'
    '0002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-hist'
    'ory-0-0-put-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\'
    '\\\\"ve-history-0-0-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$dateti'
    'me\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]'
    '}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-put-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_re'
    'ference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-put-reference-source-0\\\\\\"]}'
    ']]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"'
    '}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-und'
    'erlying\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"underlying_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-'
    'history-0-underlying-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":'
    '\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\'
    '"record_id\\\\\\",\\\\\\"ve-history-1-0-call-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"sou'
    'rce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-call-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\'
    '"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_qual'
    'ity_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-call-iv\\\\\\"],[\\\\\\"role\\\\'
    '\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-cal'
    'l-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T1'
    '5:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\'
    '\\\\"ve-history-1-0-call-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$'
    'list\\\\\\":[\\\\\\"ve-history-1-0-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",'
    '{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"'
    '$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-call-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"optio'
    'n_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-call-reference-'
    'source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:'
    '00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve'
    '-history-1-0-put-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list'
    '\\\\\\":[\\\\\\"ve-history-1-0-put-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\'
    '"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$lis'
    't\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-put-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_vo'
    'latility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-put-iv-source-0\\\\\\"]}]]},{\\'
    '\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\'
    '\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-put-quo'
    'te\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1'
    '-0-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030'
    '-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_'
    'id\\\\\\",\\\\\\"ve-history-1-0-put-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\'
    '\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-put-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\'
    '\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propaga'
    'ted_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-underlying\\\\\\"],[\\'
    '\\\\"role\\\\\\",\\\\\\"underlying_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-under'
    'lying-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T'
    '15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",'
    '\\\\\\"ve-history-2-0-call-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\'
    '\\"$list\\\\\\":[\\\\\\"ve-history-2-0-call-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\'
    '\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{'
    '\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-call-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_i'
    'mplied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-call-iv-source-0\\\\'
    '\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z'
    '\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2'
    '-0-call-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"v'
    'e-history-2-0-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\'
    '\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],'
    '[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-call-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_refe'
    'rence\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-call-reference-source-0\\\\\\"]}]'
    ']},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}'
    '],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-pu'
    't-greeks\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_greeks\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-hi'
    'story-2-0-put-greeks-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":'
    '\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\'
    '"record_id\\\\\\",\\\\\\"ve-history-2-0-put-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],['
    '\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\'
    '\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_qu'
    'ality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-put-quote\\\\\\"],[\\\\\\"ro'
    'le\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-put-quote-so'
    'urce-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00'
    '.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-h'
    'istory-2-0-put-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\'
    '\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-put-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normal'
    'ized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_fla'
    'gs\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-underlying\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\'
    '"underlying_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-underlying-source-0\\'
    '\\\\"]}]]}]}]]}],[\\\\\\"same_contract_reuse_rule\\\\\\",\\\\\\"reject_same_economic_contract_across_10_and'
    '_25_same_side\\\\\\"],[\\\\\\"skew_percentile_formula\\\\\\",\\\\\\"inclusive_count_historical_downside_25_s'
    'kew_lte_current_divided_by_count\\\\\\"],[\\\\\\"skew_term_structure_ordering\\\\\\",\\\\\\"ascending_days_t'
    'o_expiration_then_expiration\\\\\\"],[\\\\\\"tail_output_architecture\\\\\\",\\\\\\"ordered_tail_pricing_sli'
    'ce_tuple\\\\\\"],[\\\\\\"target_deltas\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"call_10\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.10\\'
    '\\\\"}],[\\\\\\"call_25\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.25\\\\\\"}],[\\\\\\"put_10\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0'
    '.10\\\\\\"}],[\\\\\\"put_25\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-0.25\\\\\\"}]]}],[\\\\\\"volatility_unit\\\\\\",\\\\\\"annu'
    'alized_decimal_ratio\\\\\\"]]}\\"],[\\"quality_flags\\",{\\"$list\\":[\\"decimal_to_float_converted\\",\\"a'
    'nnualized\\",\\"assumption_applied\\"]}],[\\"selected\\",{\\"$map\\":[[\\"as_of_date\\",{\\"$date\\":\\"2030'
    '-01-02\\"}],[\\"matching_candidate_details\\",{\\"$list\\":[]}],[\\"ordered_expirations\\",{\\"$list\\":['
    '{\\"$date\\":\\"2030-02-01\\"},{\\"$date\\":\\"2030-03-03\\"}]}],[\\"structure_expiration_match\\",{\\"$dat'
    'e\\":\\"2030-03-03\\"}],[\\"underlying\\",\\"SPY\\"]]}]]}],[\\"underlying_shock_rule\\",\\"exact_base_unde'
    'rlying_times_one_plus_decimal_string_move\\"],[\\"valuation_date_rules\\",{\\"$map\\":[[\\"days_forwar'
    'd\\",\\"as_of_date_plus_days_forward_calendar_days\\"],[\\"expiration\\",\\"common_expiration\\"],[\\"ho'
    'lding_horizon\\",\\"as_of_date_plus_expected_holding_days\\"],[\\"immediate\\",\\"as_of_date\\"]]}]]}"]'
    ',["quality_flags",{"$list":["decimal_to_float_converted","annualized","assumption_applied"]}]]}]'
    ',["records",{"$list":[{"$map":[["as_of_date",{"$date":"2030-01-02"}],["base_underlying_price_flo'
    'at_repr","100.0"],["entry_cost_basis_float_repr","141.25"],["estimated_exit_cost_float_repr","2.'
    '5"],["estimated_position_value_float_repr","250.0"],["leg_volatility_inputs",{"$list":[{"$map":['
    '["base_iv_float_repr","0.2"],["leg",{"$map":[["contract_multiplier",100],["expiration",{"$date":'
    '"2030-03-03"}],["option_type","call"],["quantity",1],["strike_float_repr","100.0"],["underlying"'
    ',"SPY"]]}]]}]}],["pricing_methodology","{\\"$map\\":[[\\"base_iv_source\\",\\"ScenarioPricing_v0.1_ac'
    'tual_structure_leg_iv_evidence\\"],[\\"base_underlying_source\\",\\"StructureCosts_v0.2_underlying_p'
    'rice_exact\\"],[\\"entry_cost_rule\\",\\"StructureCosts_v0.2_stable_total_entry_cost_float\\"],[\\"exi'
    't_cost_rule\\",{\\"$map\\":[[\\"methodology\\",\\"explicit_fixture_exit_cost_v0.1\\"],[\\"source\\",\\"exp'
    'licit_scenario_specific_decimal_assumption\\"]]}],[\\"expiration_rule\\",{\\"$map\\":[[\\"active\\",fal'
    'se],[\\"call_formula\\",\\"max(shocked_underlying-strike,0)*quantity*multiplier\\"],[\\"external_expi'
    'ration_value\\",\\"prohibited\\"],[\\"iv_effect\\",\\"none_base_leg_ivs_retained_for_audit\\"],[\\"put_f'
    'ormula\\",\\"max(strike-shocked_underlying,0)*quantity*multiplier\\"]]}],[\\"float_conversion_rule\\"'
    ',\\"convert_base_iv_gross_and_exit_cost_once_to_finite_float\\"],[\\"limitations\\",\\"Internal consi'
    'stency is validated; self-consistent fabricated dependency artifacts are not cryptographically a'
    'uthenticated.\\"],[\\"nonexpiration_rule\\",{\\"$map\\":[[\\"active\\",true],[\\"rule\\",\\"consume_author'
    'itative_gross_value_without_repricing\\"]]}],[\\"provider_disclosure\\",{\\"$map\\":[[\\"calculation_i'
    'd\\",\\"scenario-pricing-calculation-001\\"],[\\"dividend_methodology\\",{\\"$map\\":[[\\"dividend_cover'
    'age_end_date\\",{\\"$date\\":\\"2030-03-15\\"}],[\\"dividend_coverage_start_date\\",{\\"$date\\":\\"2030-0'
    '1-02\\"}],[\\"dividend_source\\",\\"explicit_zero_dividend_assumption\\"],[\\"dividend_treatment\\",\\"e'
    'xplicit_zero_dividend_assumption\\"],[\\"explicit_zero_dividend_assumption\\",true]]}],[\\"interpola'
    'tion_treatment\\",\\"none\\"],[\\"numerical_boundary\\",\\"provider option values; local validation on'
    'ly\\"],[\\"payload_sha256\\",\\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\\"],'
    '[\\"position_scaling_rule\\",\\"per_underlying_unit_value_times_quantity_times_contract_multiplier\\'
    '"],[\\"pricing_model_name\\",\\"Synthetic disclosed option model\\"],[\\"pricing_model_version\\",\\"mo'
    'del-v2\\"],[\\"producer_calculated_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:05.000000Z\\"}],[\\"produc'
    'er_name\\",\\"Synthetic Scenario Provider\\"],[\\"producer_version\\",\\"provider-v3\\"],[\\"rate_method'
    'ology\\",{\\"$map\\":[[\\"rate_compounding_conversion\\",\\"continuous equivalent\\"],[\\"rate_currency\\'
    '",\\"USD\\"],[\\"rate_curve_identity\\",\\"synthetic-usd-curve-20300102\\"],[\\"rate_day_count_conventi'
    'on\\",\\"actual_365\\"],[\\"rate_effective_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"rate_interpolation\\'
    '",\\"none\\"],[\\"rate_remaining_tenor_treatment\\",\\"remaining calendar tenor\\"],[\\"rate_source\\",\\'
    '"Synthetic USD curve\\"]]}],[\\"remaining_time_rule\\",\\"expiration_minus_valuation_date_calendar_d'
    'ays\\"],[\\"request_id\\",\\"scenario-request-001\\"],[\\"settlement_treatment\\",\\"physical settlement'
    ' at declared terms\\"],[\\"skew_treatment\\",\\"preserve leg-level base differences\\"],[\\"status\\",\\'
    '"active_authoritative_provider_calculated\\"],[\\"surface_treatment\\",\\"actual leg IV parallel sho'
    'ck\\"],[\\"term_treatment\\",\\"remaining tenor per scenario\\"]]}],[\\"scenario_identity\\",{\\"$map\\":'
    '[[\\"days_forward\\",0],[\\"iv_change\\",{\\"$decimal\\":\\"0.0\\"}],[\\"underlying_move\\",{\\"$decimal\\":'
    '\\"0.0\\"}],[\\"valuation_time\\",\\"immediate\\"]]}],[\\"scenario_pricing_dependency\\",{\\"$map\\":[[\\"c'
    'alculation_id\\",\\"scenario-pricing-calculation-001\\"],[\\"identity\\",{\\"$list\\":[\\"nonexpiration_'
    'scenario_pricing\\",\\"authoritative-provider-option-scenario-pricing-evidence\\",\\"v0.1\\"]}]]}],[\\'
    '"schema_version\\",\\"v0.1\\"],[\\"structure_costs_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"sce'
    'nario-valuation-costs\\"],[\\"identity\\",{\\"$list\\":[\\"structure_costs\\",\\"exact-structure-costs\\"'
    ',\\"v0.2\\"]}]]}],[\\"tail_pricing_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"calculation-3c7e\\"'
    '],[\\"identity\\",{\\"$list\\":[\\"tail_pricing\\",\\"nearest-observed-delta-wing-tail-relative-pricing'
    '\\",\\"v0.2\\"]}],[\\"use\\",\\"context_only\\"]]}],[\\"valuation_source\\",\\"authoritative_provider_none'
    'xpiration\\"]]}"],["scenario",{"$map":[["days_forward",0],["iv_change_float_repr","0.0"],["underl'
    'ying_move_float_repr","0.0"],["valuation_time","immediate"]]}],["structure",{"$map":[["assumed_p'
    'ortfolio_value_repr","100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$map":[["contr'
    'act_multiplier",100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1]'
    ',["strike_float_repr","100.0"],["underlying","SPY"]]}]}],["structure_type","long_call"],["underl'
    'ying","SPY"]]}],["valuation_date",{"$date":"2030-01-02"}]]},{"$map":[["as_of_date",{"$date":"203'
    '0-01-02"}],["base_underlying_price_float_repr","100.0"],["entry_cost_basis_float_repr","141.25"]'
    ',["estimated_exit_cost_float_repr","2.5"],["estimated_position_value_float_repr","300.0"],["leg_'
    'volatility_inputs",{"$list":[{"$map":[["base_iv_float_repr","0.2"],["leg",{"$map":[["contract_mu'
    'ltiplier",100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],["str'
    'ike_float_repr","100.0"],["underlying","SPY"]]}]]}]}],["pricing_methodology","{\\"$map\\":[[\\"base'
    '_iv_source\\",\\"ScenarioPricing_v0.1_actual_structure_leg_iv_evidence\\"],[\\"base_underlying_sourc'
    'e\\",\\"StructureCosts_v0.2_underlying_price_exact\\"],[\\"entry_cost_rule\\",\\"StructureCosts_v0.2_s'
    'table_total_entry_cost_float\\"],[\\"exit_cost_rule\\",{\\"$map\\":[[\\"methodology\\",\\"explicit_fixtu'
    're_exit_cost_v0.1\\"],[\\"source\\",\\"explicit_scenario_specific_decimal_assumption\\"]]}],[\\"expira'
    'tion_rule\\",{\\"$map\\":[[\\"active\\",false],[\\"call_formula\\",\\"max(shocked_underlying-strike,0)*q'
    'uantity*multiplier\\"],[\\"external_expiration_value\\",\\"prohibited\\"],[\\"iv_effect\\",\\"none_base_'
    'leg_ivs_retained_for_audit\\"],[\\"put_formula\\",\\"max(strike-shocked_underlying,0)*quantity*multi'
    'plier\\"]]}],[\\"float_conversion_rule\\",\\"convert_base_iv_gross_and_exit_cost_once_to_finite_floa'
    't\\"],[\\"limitations\\",\\"Internal consistency is validated; self-consistent fabricated dependency'
    ' artifacts are not cryptographically authenticated.\\"],[\\"nonexpiration_rule\\",{\\"$map\\":[[\\"act'
    'ive\\",true],[\\"rule\\",\\"consume_authoritative_gross_value_without_repricing\\"]]}],[\\"provider_di'
    'sclosure\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-pricing-calculation-001\\"],[\\"dividend_meth'
    'odology\\",{\\"$map\\":[[\\"dividend_coverage_end_date\\",{\\"$date\\":\\"2030-03-15\\"}],[\\"dividend_cov'
    'erage_start_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"dividend_source\\",\\"explicit_zero_dividend_ass'
    'umption\\"],[\\"dividend_treatment\\",\\"explicit_zero_dividend_assumption\\"],[\\"explicit_zero_divid'
    'end_assumption\\",true]]}],[\\"interpolation_treatment\\",\\"none\\"],[\\"numerical_boundary\\",\\"provi'
    'der option values; local validation only\\"],[\\"payload_sha256\\",\\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
    'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\\"],[\\"position_scaling_rule\\",\\"per_underlying_unit_value_tim'
    'es_quantity_times_contract_multiplier\\"],[\\"pricing_model_name\\",\\"Synthetic disclosed option mo'
    'del\\"],[\\"pricing_model_version\\",\\"model-v2\\"],[\\"producer_calculated_at\\",{\\"$datetime\\":\\"203'
    '0-01-02T15:30:05.000000Z\\"}],[\\"producer_name\\",\\"Synthetic Scenario Provider\\"],[\\"producer_ver'
    'sion\\",\\"provider-v3\\"],[\\"rate_methodology\\",{\\"$map\\":[[\\"rate_compounding_conversion\\",\\"cont'
    'inuous equivalent\\"],[\\"rate_currency\\",\\"USD\\"],[\\"rate_curve_identity\\",\\"synthetic-usd-curve-'
    '20300102\\"],[\\"rate_day_count_convention\\",\\"actual_365\\"],[\\"rate_effective_date\\",{\\"$date\\":\\'
    '"2030-01-02\\"}],[\\"rate_interpolation\\",\\"none\\"],[\\"rate_remaining_tenor_treatment\\",\\"remainin'
    'g calendar tenor\\"],[\\"rate_source\\",\\"Synthetic USD curve\\"]]}],[\\"remaining_time_rule\\",\\"expi'
    'ration_minus_valuation_date_calendar_days\\"],[\\"request_id\\",\\"scenario-request-001\\"],[\\"settle'
    'ment_treatment\\",\\"physical settlement at declared terms\\"],[\\"skew_treatment\\",\\"preserve leg-l'
    'evel base differences\\"],[\\"status\\",\\"active_authoritative_provider_calculated\\"],[\\"surface_tr'
    'eatment\\",\\"actual leg IV parallel shock\\"],[\\"term_treatment\\",\\"remaining tenor per scenario\\"'
    ']]}],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forward\\",7],[\\"iv_change\\",{\\"$decimal\\":\\"0.2\\"'
    '}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.1\\"}],[\\"valuation_time\\",\\"days_forward\\"]]}],[\\"scen'
    'ario_pricing_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-pricing-calculation-001\\"],['
    '\\"identity\\",{\\"$list\\":[\\"nonexpiration_scenario_pricing\\",\\"authoritative-provider-option-scen'
    'ario-pricing-evidence\\",\\"v0.1\\"]}]]}],[\\"schema_version\\",\\"v0.1\\"],[\\"structure_costs_dependen'
    'cy\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-valuation-costs\\"],[\\"identity\\",{\\"$list\\":[\\"st'
    'ructure_costs\\",\\"exact-structure-costs\\",\\"v0.2\\"]}]]}],[\\"tail_pricing_dependency\\",{\\"$map\\":'
    '[[\\"calculation_id\\",\\"calculation-3c7e\\"],[\\"identity\\",{\\"$list\\":[\\"tail_pricing\\",\\"nearest-'
    'observed-delta-wing-tail-relative-pricing\\",\\"v0.2\\"]}],[\\"use\\",\\"context_only\\"]]}],[\\"valuati'
    'on_source\\",\\"authoritative_provider_nonexpiration\\"]]}"],["scenario",{"$map":[["days_forward",7'
    '],["iv_change_float_repr","0.2"],["underlying_move_float_repr","0.1"],["valuation_time","days_fo'
    'rward"]]}],["structure",{"$map":[["assumed_portfolio_value_repr","100000.0"],["expected_holding_'
    'days",14],["legs",{"$list":[{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-03'
    '-03"}],["option_type","call"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]'
    '}]}],["structure_type","long_call"],["underlying","SPY"]]}],["valuation_date",{"$date":"2030-01-'
    '09"}]]},{"$map":[["as_of_date",{"$date":"2030-01-02"}],["base_underlying_price_float_repr","100.'
    '0"],["entry_cost_basis_float_repr","141.25"],["estimated_exit_cost_float_repr","2.5"],["estimate'
    'd_position_value_float_repr","200.0"],["leg_volatility_inputs",{"$list":[{"$map":[["base_iv_floa'
    't_repr","0.2"],["leg",{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-03-03"}]'
    ',["option_type","call"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]}]]}]}'
    '],["pricing_methodology","{\\"$map\\":[[\\"base_iv_source\\",\\"ScenarioPricing_v0.1_actual_structure'
    '_leg_iv_evidence\\"],[\\"base_underlying_source\\",\\"StructureCosts_v0.2_underlying_price_exact\\"],'
    '[\\"entry_cost_rule\\",\\"StructureCosts_v0.2_stable_total_entry_cost_float\\"],[\\"exit_cost_rule\\",'
    '{\\"$map\\":[[\\"methodology\\",\\"explicit_fixture_exit_cost_v0.1\\"],[\\"source\\",\\"explicit_scenario'
    '_specific_decimal_assumption\\"]]}],[\\"expiration_rule\\",{\\"$map\\":[[\\"active\\",false],[\\"call_fo'
    'rmula\\",\\"max(shocked_underlying-strike,0)*quantity*multiplier\\"],[\\"external_expiration_value\\"'
    ',\\"prohibited\\"],[\\"iv_effect\\",\\"none_base_leg_ivs_retained_for_audit\\"],[\\"put_formula\\",\\"max'
    '(strike-shocked_underlying,0)*quantity*multiplier\\"]]}],[\\"float_conversion_rule\\",\\"convert_bas'
    'e_iv_gross_and_exit_cost_once_to_finite_float\\"],[\\"limitations\\",\\"Internal consistency is vali'
    'dated; self-consistent fabricated dependency artifacts are not cryptographically authenticated.\\'
    '"],[\\"nonexpiration_rule\\",{\\"$map\\":[[\\"active\\",true],[\\"rule\\",\\"consume_authoritative_gross_'
    'value_without_repricing\\"]]}],[\\"provider_disclosure\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario'
    '-pricing-calculation-001\\"],[\\"dividend_methodology\\",{\\"$map\\":[[\\"dividend_coverage_end_date\\"'
    ',{\\"$date\\":\\"2030-03-15\\"}],[\\"dividend_coverage_start_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"di'
    'vidend_source\\",\\"explicit_zero_dividend_assumption\\"],[\\"dividend_treatment\\",\\"explicit_zero_d'
    'ividend_assumption\\"],[\\"explicit_zero_dividend_assumption\\",true]]}],[\\"interpolation_treatment'
    '\\",\\"none\\"],[\\"numerical_boundary\\",\\"provider option values; local validation only\\"],[\\"paylo'
    'ad_sha256\\",\\"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\\"],[\\"position_sc'
    'aling_rule\\",\\"per_underlying_unit_value_times_quantity_times_contract_multiplier\\"],[\\"pricing_'
    'model_name\\",\\"Synthetic disclosed option model\\"],[\\"pricing_model_version\\",\\"model-v2\\"],[\\"p'
    'roducer_calculated_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:05.000000Z\\"}],[\\"producer_name\\",\\"Sy'
    'nthetic Scenario Provider\\"],[\\"producer_version\\",\\"provider-v3\\"],[\\"rate_methodology\\",{\\"$ma'
    'p\\":[[\\"rate_compounding_conversion\\",\\"continuous equivalent\\"],[\\"rate_currency\\",\\"USD\\"],[\\"'
    'rate_curve_identity\\",\\"synthetic-usd-curve-20300102\\"],[\\"rate_day_count_convention\\",\\"actual_'
    '365\\"],[\\"rate_effective_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"rate_interpolation\\",\\"none\\"],[\\'
    '"rate_remaining_tenor_treatment\\",\\"remaining calendar tenor\\"],[\\"rate_source\\",\\"Synthetic USD'
    ' curve\\"]]}],[\\"remaining_time_rule\\",\\"expiration_minus_valuation_date_calendar_days\\"],[\\"requ'
    'est_id\\",\\"scenario-request-001\\"],[\\"settlement_treatment\\",\\"physical settlement at declared t'
    'erms\\"],[\\"skew_treatment\\",\\"preserve leg-level base differences\\"],[\\"status\\",\\"active_author'
    'itative_provider_calculated\\"],[\\"surface_treatment\\",\\"actual leg IV parallel shock\\"],[\\"term_'
    'treatment\\",\\"remaining tenor per scenario\\"]]}],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forwa'
    'rd\\",0],[\\"iv_change\\",{\\"$decimal\\":\\"-0.1\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"-0.05\\"}],['
    '\\"valuation_time\\",\\"holding_horizon\\"]]}],[\\"scenario_pricing_dependency\\",{\\"$map\\":[[\\"calcul'
    'ation_id\\",\\"scenario-pricing-calculation-001\\"],[\\"identity\\",{\\"$list\\":[\\"nonexpiration_scena'
    'rio_pricing\\",\\"authoritative-provider-option-scenario-pricing-evidence\\",\\"v0.1\\"]}]]}],[\\"sche'
    'ma_version\\",\\"v0.1\\"],[\\"structure_costs_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario'
    '-valuation-costs\\"],[\\"identity\\",{\\"$list\\":[\\"structure_costs\\",\\"exact-structure-costs\\",\\"v0'
    '.2\\"]}]]}],[\\"tail_pricing_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"calculation-3c7e\\"],[\\"'
    'identity\\",{\\"$list\\":[\\"tail_pricing\\",\\"nearest-observed-delta-wing-tail-relative-pricing\\",\\"'
    'v0.2\\"]}],[\\"use\\",\\"context_only\\"]]}],[\\"valuation_source\\",\\"authoritative_provider_nonexpira'
    'tion\\"]]}"],["scenario",{"$map":[["days_forward",0],["iv_change_float_repr","-0.1"],["underlying'
    '_move_float_repr","-0.05"],["valuation_time","holding_horizon"]]}],["structure",{"$map":[["assum'
    'ed_portfolio_value_repr","100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$map":[["c'
    'ontract_multiplier",100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity'
    '",1],["strike_float_repr","100.0"],["underlying","SPY"]]}]}],["structure_type","long_call"],["un'
    'derlying","SPY"]]}],["valuation_date",{"$date":"2030-01-16"}]]},{"$map":[["as_of_date",{"$date":'
    '"2030-01-02"}],["base_underlying_price_float_repr","100.0"],["entry_cost_basis_float_repr","141.'
    '25"],["estimated_exit_cost_float_repr","0.0"],["estimated_position_value_float_repr","1000.0"],['
    '"leg_volatility_inputs",{"$list":[{"$map":[["base_iv_float_repr","0.2"],["leg",{"$map":[["contra'
    'ct_multiplier",100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],'
    '["strike_float_repr","100.0"],["underlying","SPY"]]}]]}]}],["pricing_methodology","{\\"$map\\":[[\\'
    '"base_iv_source\\",\\"ScenarioPricing_v0.1_actual_structure_leg_iv_evidence\\"],[\\"base_underlying_'
    'source\\",\\"StructureCosts_v0.2_underlying_price_exact\\"],[\\"entry_cost_rule\\",\\"StructureCosts_v'
    '0.2_stable_total_entry_cost_float\\"],[\\"exit_cost_rule\\",{\\"$map\\":[[\\"methodology\\",\\"explicit_'
    'fixture_exit_cost_v0.1\\"],[\\"source\\",\\"explicit_scenario_specific_decimal_assumption\\"]]}],[\\"e'
    'xpiration_rule\\",{\\"$map\\":[[\\"active\\",true],[\\"call_formula\\",\\"max(shocked_underlying-strike,'
    '0)*quantity*multiplier\\"],[\\"external_expiration_value\\",\\"prohibited\\"],[\\"iv_effect\\",\\"none_b'
    'ase_leg_ivs_retained_for_audit\\"],[\\"put_formula\\",\\"max(strike-shocked_underlying,0)*quantity*m'
    'ultiplier\\"]]}],[\\"float_conversion_rule\\",\\"convert_base_iv_gross_and_exit_cost_once_to_finite_'
    'float\\"],[\\"limitations\\",\\"Internal consistency is validated; self-consistent fabricated depend'
    'ency artifacts are not cryptographically authenticated.\\"],[\\"nonexpiration_rule\\",{\\"$map\\":[[\\'
    '"active\\",false],[\\"rule\\",\\"consume_authoritative_gross_value_without_repricing\\"]]}],[\\"provid'
    'er_disclosure\\",{\\"$map\\":[[\\"external_expiration_value\\",\\"prohibited\\"],[\\"status\\",\\"inactive'
    '_for_expiration\\"]]}],[\\"scenario_identity\\",{\\"$map\\":[[\\"days_forward\\",0],[\\"iv_change\\",{\\"$'
    'decimal\\":\\"0.5\\"}],[\\"underlying_move\\",{\\"$decimal\\":\\"0.1\\"}],[\\"valuation_time\\",\\"expiratio'
    'n\\"]]}],[\\"scenario_pricing_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-pricing-calcu'
    'lation-001\\"],[\\"identity\\",{\\"$list\\":[\\"nonexpiration_scenario_pricing\\",\\"authoritative-provi'
    'der-option-scenario-pricing-evidence\\",\\"v0.1\\"]}]]}],[\\"schema_version\\",\\"v0.1\\"],[\\"structure'
    '_costs_dependency\\",{\\"$map\\":[[\\"calculation_id\\",\\"scenario-valuation-costs\\"],[\\"identity\\",{'
    '\\"$list\\":[\\"structure_costs\\",\\"exact-structure-costs\\",\\"v0.2\\"]}]]}],[\\"tail_pricing_dependen'
    'cy\\",{\\"$map\\":[[\\"calculation_id\\",\\"calculation-3c7e\\"],[\\"identity\\",{\\"$list\\":[\\"tail_prici'
    'ng\\",\\"nearest-observed-delta-wing-tail-relative-pricing\\",\\"v0.2\\"]}],[\\"use\\",\\"context_only\\"'
    ']]}],[\\"valuation_source\\",\\"terminal_intrinsic_expiration\\"]]}"],["scenario",{"$map":[["days_fo'
    'rward",0],["iv_change_float_repr","0.5"],["underlying_move_float_repr","0.1"],["valuation_time",'
    '"expiration"]]}],["structure",{"$map":[["assumed_portfolio_value_repr","100000.0"],["expected_ho'
    'lding_days",14],["legs",{"$list":[{"$map":[["contract_multiplier",100],["expiration",{"$date":"2'
    '030-03-03"}],["option_type","call"],["quantity",1],["strike_float_repr","100.0"],["underlying","'
    'SPY"]]}]}],["structure_type","long_call"],["underlying","SPY"]]}],["valuation_date",{"$date":"20'
    '30-03-03"}]]}]}],["wrapper_type","ScenarioValuationTransformationResult"]]}],["schema_version","'
    'v0.1"],["structure_affordability_result",{"$map":[["lineage",{"$map":[["calculated_at",{"$dateti'
    'me":"2030-01-02T15:30:16.000000Z"}],["calculation_id","affordability-shared"],["calculation_type'
    '","structure_affordability"],["inputs",{"$list":[{"$map":[["normalized_at",{"$datetime":"2030-01'
    '-02T15:30:00.000002Z"}],["record_id","cost-call-contract-reference"],["source_ids",{"$list":["co'
    'st-call-contract-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:'
    '30:00.000002Z"}],["record_id","cost-call-greeks"],["source_ids",{"$list":["cost-call-greeks-sour'
    'ce-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","'
    'cost-call-quote"],["source_ids",{"$list":["cost-call-quote-source-0"]}]]},{"$map":[["normalized_'
    'at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","cost-underlying-quote"],["source_'
    'ids",{"$list":["cost-underlying-quote-source-0"]}]]}]}],["methodology_id","exact-bounded-loss-ag'
    'ainst-declared-risk-fractions"],["methodology_version","v0.1"],["parameters_json","{\\"$map\\":[[\\'
    '"affordability_rule\\",{\\"$map\\":[[\\"complete_rule\\",\\"both_comparisons_must_pass\\"],[\\"equality_'
    'boundary\\",\\"affordable\\"],[\\"incomplete_precedence\\",\\"missing_assumptions_precede_boundary_bre'
    'ach_evaluation\\"],[\\"repeated_comparison\\",\\"repeated_loss_fraction<=maximum_repeated_loss_fract'
    'ion\\"],[\\"required_assumptions\\",{\\"$list\\":[\\"portfolio_value\\",\\"maximum_single_structure_loss'
    '_fraction\\",\\"maximum_repeated_loss_fraction\\",\\"risk_budget_methodology\\"]}],[\\"single_comparis'
    'on\\",\\"single_loss_fraction<=maximum_single_structure_loss_fraction\\"]]}],[\\"calculation_values\\'
    '",{\\"$map\\":[[\\"maximum_repeated_loss_fraction\\",{\\"$map\\":[[\\"denominator\\",50],[\\"numerator\\",'
    '1]]}],[\\"maximum_single_structure_loss_fraction\\",{\\"$map\\":[[\\"denominator\\",100],[\\"numerator\\'
    '",1]]}],[\\"portfolio_value\\",{\\"$decimal\\":\\"100000.0\\"}],[\\"repeated_aggregate_maximum_loss\\",{'
    '\\"$decimal\\":\\"141.250\\"}],[\\"repeated_bet_count\\",1],[\\"repeated_loss_fraction\\",{\\"$map\\":[[\\"'
    'denominator\\",80000],[\\"numerator\\",113]]}],[\\"single_loss_fraction\\",{\\"$map\\":[[\\"denominator\\'
    '",80000],[\\"numerator\\",113]]}],[\\"single_position_maximum_loss\\",{\\"$decimal\\":\\"141.250\\"}]]}]'
    ',[\\"currency\\",\\"USD\\"],[\\"limitations\\",\\"Affordability evidence for one declared structure and'
    ' equal repeated attempts only; no annual budget, committed exposure, inverse sizing, quantity re'
    'commendation, portfolio optimization, probability, expected return, screening, reporting, provid'
    'er access, monitoring, or execution.\\"],[\\"outcome\\",{\\"$map\\":[[\\"reason_codes\\",{\\"$list\\":[]}'
    '],[\\"status\\",\\"affordable\\"]]}],[\\"output_architecture\\",\\"standalone_structure_affordability_e'
    'vidence\\"],[\\"risk_budget_assumptions\\",{\\"$map\\":[[\\"legacy_portfolio_value_correspondence\\",\\"'
    'exact_equality_to_Decimal(str(assumed_portfolio_value))\\"],[\\"maximum_repeated_loss_fraction\\",{'
    '\\"$map\\":[[\\"denominator\\",50],[\\"numerator\\",1]]}],[\\"maximum_single_structure_loss_fraction\\",'
    '{\\"$map\\":[[\\"denominator\\",100],[\\"numerator\\",1]]}],[\\"missing_assumption_policy\\",\\"data_insu'
    'fficient_without_boundary_breach_evaluation\\"],[\\"portfolio_value\\",{\\"$map\\":[[\\"amount\\",{\\"$d'
    'ecimal\\":\\"100000.0\\"}],[\\"as_of_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"currency\\",\\"USD\\"],[\\"me'
    'thodology\\",\\"declared NAV\\"]]}],[\\"risk_budget_methodology\\",\\"risk policy\\"]]}],[\\"risk_scope\\'
    '",{\\"$map\\":[[\\"annual_budget\\",\\"excluded\\"],[\\"existing_committed_exposure\\",\\"excluded\\"],[\\"'
    'inverse_sizing\\",\\"excluded\\"],[\\"repeated_attempts\\",\\"equal_repeated_attempts_not_concurrency_'
    'or_annual_frequency\\"],[\\"single_position\\",\\"one_already_specified_structure\\"]]}],[\\"schema_ve'
    'rsion\\",\\"v0.1\\"],[\\"structure_costs_dependency\\",{\\"$map\\":[[\\"calculated_at\\",{\\"$datetime\\":\\'
    '"2030-01-02T15:30:04.000000Z\\"}],[\\"calculation_id\\",\\"scenario-valuation-costs\\"],[\\"calculatio'
    'n_type\\",\\"structure_costs\\"],[\\"input_rule\\",\\"exact_reuse_of_structure_costs_lineage_inputs\\"]'
    ',[\\"methodology_id\\",\\"exact-structure-costs\\"],[\\"methodology_version\\",\\"v0.2\\"],[\\"parameters'
    '_json\\",\\"{\\\\\\"$map\\\\\\":[[\\\\\\"calculation_values\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"commissions_and_fees_ex'
    'act\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.25\\\\\\"}],[\\\\\\"cumulative_repeated_bet_cost_exact\\\\\\",{\\\\\\"$decim'
    'al\\\\\\":\\\\\\"141.250\\\\\\"}],[\\\\\\"estimated_spread_cost_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"20.000\\\\\\"}]'
    ',[\\\\\\"gamma_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"2.000\\\\\\"}],[\\\\\\"maximum_loss_exact\\\\\\",{\\\\\\"$decima'
    'l\\\\\\":\\\\\\"141.250\\\\\\"}],[\\\\\\"quoted_mid_premium_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"120.000\\\\\\"}],[\\'
    '\\\\"stable_record_values\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"commissions_and_fees_repr\\\\\\",\\\\\\"1.25\\\\\\"],[\\\\\\'
    '"cumulative_repeated_bet_cost_repr\\\\\\",\\\\\\"141.25\\\\\\"],[\\\\\\"estimated_spread_cost_repr\\\\\\",\\\\\\"2'
    '0.0\\\\\\"],[\\\\\\"gamma_repr\\\\\\",\\\\\\"2.0\\\\\\"],[\\\\\\"maximum_loss_repr\\\\\\",\\\\\\"141.25\\\\\\"],[\\\\\\"quoted'
    '_mid_premium_repr\\\\\\",\\\\\\"120.0\\\\\\"],[\\\\\\"theta_per_day_repr\\\\\\",\\\\\\"-10.0\\\\\\"],[\\\\\\"total_entry'
    '_cost_repr\\\\\\",\\\\\\"141.25\\\\\\"],[\\\\\\"underlying_price_repr\\\\\\",\\\\\\"100.0\\\\\\"]]}],[\\\\\\"theta_per_d'
    'ay_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"-10.000\\\\\\"}],[\\\\\\"total_entry_cost_exact\\\\\\",{\\\\\\"$decimal\\\\'
    '\\":\\\\\\"141.250\\\\\\"}],[\\\\\\"underlying_price_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.000\\\\\\"}]]}],[\\\\\\'
    '"commission_and_fee_scope\\\\\\",\\\\\\"entry_only_total_position\\\\\\"],[\\\\\\"commissions_and_fees_usd\\\\'
    '\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.25\\\\\\"}],[\\\\\\"gamma_input_unit\\\\\\",\\\\\\"option_value_change_per_usd_sq'
    'uared_per_underlying_unit\\\\\\"],[\\\\\\"gamma_position_rule\\\\\\",\\\\\\"sum(gamma_per_underlying_unit_pe'
    'r_usd_squared*quantity*contract_multiplier)\\\\\\"],[\\\\\\"greeks_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\'
    '"dividend_input_description\\\\\\",\\\\\\"Synthetic dividend input\\\\\\"],[\\\\\\"model_name\\\\\\",\\\\\\"Synthe'
    'tic Black-Scholes\\\\\\"],[\\\\\\"model_version\\\\\\",\\\\\\"fixture-v1\\\\\\"],[\\\\\\"rate_input_description\\\\\\'
    '",\\\\\\"Synthetic USD curve input\\\\\\"],[\\\\\\"theta_day_basis\\\\\\",\\\\\\"Provider calendar-day conventi'
    'on\\\\\\"],[\\\\\\"unit_convention\\\\\\",\\\\\\"Contract-defined canonical units\\\\\\"]]}],[\\\\\\"leg_correspon'
    'dence\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\'
    '"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],'
    '[\\\\\\"option_contract_reference_record_id\\\\\\",\\\\\\"cost-call-contract-reference\\\\\\"],[\\\\\\"option_g'
    'reeks_record_id\\\\\\",\\\\\\"cost-call-greeks\\\\\\"],[\\\\\\"option_quote_record_id\\\\\\",\\\\\\"cost-call-quot'
    'e\\\\\\"],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\"'
    ':\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_'
    'mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"u'
    'nderlying_quote_record_id\\\\\\",\\\\\\"cost-underlying-quote\\\\\\"]]}]}],[\\\\\\"normalized_evidence\\\\\\",{'
    '\\\\\\"$map\\\\\\":[[\\\\\\"contract_references\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multipli'
    'er\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"exercise_style\\\\\\"'
    ',\\\\\\"American\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"last_trade_date\\'
    '\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"listing_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-09-16\\\\\\"}'
    '],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"option_ty'
    'pe\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"quantity\\\\\\",1],'
    '[\\\\\\"record_id\\\\\\",\\\\\\"cost-call-contract-reference\\\\\\"],[\\\\\\"settlement_type\\\\\\",\\\\\\"Physical\\\\'
    '\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"cost-call-contract-reference-source-0\\\\\\"]}],[\\\\\\"st'
    'rike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",'
    '\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\'
    '\\\\",\\\\\\"SPY\\\\\\"]]}]]}]}],[\\\\\\"option_greeks\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_mul'
    'tiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"dividend_inpu'
    't_description\\\\\\",\\\\\\"Synthetic dividend input\\\\\\"],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-'
    '03-03\\\\\\"}],[\\\\\\"gamma\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.020\\\\\\"}],[\\\\\\"model_name\\\\\\",\\\\\\"Synthetic B'
    'lack-Scholes\\\\\\"],[\\\\\\"model_version\\\\\\",\\\\\\"fixture-v1\\\\\\"],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$dateti'
    'me\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"propagated_'
    'quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"quantity\\\\\\",1],[\\\\\\"rate_input_description\\\\\\",\\\\\\"S'
    'ynthetic USD curve input\\\\\\"],[\\\\\\"record_id\\\\\\",\\\\\\"cost-call-greeks\\\\\\"],[\\\\\\"session_date\\\\\\"'
    ',{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"cost-call-greeks-so'
    'urce-0\\\\\\"]}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"theta\\\\\\",{\\\\\\"$decimal\\\\\\"'
    ':\\\\\\"-0.100\\\\\\"}],[\\\\\\"theta_day_basis\\\\\\",\\\\\\"Provider calendar-day convention\\\\\\"],[\\\\\\"underl'
    'ying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"s'
    'ecurity_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"unit_convention\\\\\\",\\\\\\"Contr'
    'act-defined canonical units\\\\\\"]]}]}],[\\\\\\"option_quotes\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\'
    '"ask_premium\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.40\\\\\\"}],[\\\\\\"bid_premium\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"1.0'
    '0\\\\\\"}],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\"'
    ',null],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"normalized_at\\\\\\",{\\\\\\"$date'
    'time\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"call\\\\\\"],[\\\\\\"propagate'
    'd_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"quantity\\\\\\",1],[\\\\\\"record_id\\\\\\",\\\\\\"cost-call-qu'
    'ote\\\\\\"],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"source_ids\\\\\\",{\\\\\\"$lis'
    't\\\\\\":[\\\\\\"cost-call-quote-source-0\\\\\\"]}],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\'
    '\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"'
    '],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}]]}]}],[\\\\\\"underlying_quote'
    '\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"ask_price\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"101.00\\\\\\"}],[\\\\\\"bid_price\\\\\\",{\\\\'
    '\\"$decimal\\\\\\":\\\\\\"99.00\\\\\\"}],[\\\\\\"midpoint_rule\\\\\\",\\\\\\"(bid_price+ask_price)/2\\\\\\"],[\\\\\\"norm'
    'alized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_f'
    'lags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"cost-underlying-quote\\\\\\"],[\\\\\\"session_date'
    '\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"cost-underlying'
    '-quote-source-0\\\\\\"]}],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"li'
    'sting_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],'
    '[\\\\\\"underlying_price_exact\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.000\\\\\\"}]]}]]}],[\\\\\\"position_value_un'
    'it\\\\\\",\\\\\\"usd\\\\\\"],[\\\\\\"premium_input_unit\\\\\\",\\\\\\"usd_per_underlying_unit\\\\\\"],[\\\\\\"premium_mi'
    'dpoint_rule\\\\\\",\\\\\\"sum(((bid_premium+ask_premium)/2)*quantity*contract_multiplier)\\\\\\"],[\\\\\\"re'
    'peated_bet_count\\\\\\",1],[\\\\\\"spread_cost_rule\\\\\\",\\\\\\"sum(((ask_premium-bid_premium)/2)*quantity'
    '*contract_multiplier)\\\\\\"],[\\\\\\"spread_cost_scope\\\\\\",\\\\\\"entry_only_midpoint_to_ask\\\\\\"],[\\\\\\"s'
    'tructure_identity\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"assumed_portfolio_value_repr\\\\\\",\\\\\\"100000.0\\\\\\"],[\\\\'
    '\\"expected_holding_days\\\\\\",14],[\\\\\\"legs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"contract_multi'
    'plier\\\\\\",100],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"option_type\\\\\\",\\\\\\"'
    'call\\\\\\"],[\\\\\\"quantity\\\\\\",1],[\\\\\\"strike_float_repr\\\\\\",\\\\\\"100.0\\\\\\"],[\\\\\\"underlying\\\\\\",\\\\\\'
    '"SPY\\\\\\"]]}]}],[\\\\\\"structure_type\\\\\\",\\\\\\"long_call\\\\\\"],[\\\\\\"underlying\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\'
    '\\\\"theta_day_basis\\\\\\",\\\\\\"Provider calendar-day convention\\\\\\"],[\\\\\\"theta_input_unit\\\\\\",\\\\\\"u'
    'sd_per_underlying_unit_per_declared_day_basis\\\\\\"],[\\\\\\"theta_position_rule\\\\\\",\\\\\\"sum(theta_pe'
    'r_underlying_unit_per_declared_day_basis*quantity*contract_multiplier)\\\\\\"],[\\\\\\"underlying_pric'
    'e_rule\\\\\\",\\\\\\"(bid_price+ask_price)/2\\\\\\"],[\\\\\\"underlying_price_unit\\\\\\",\\\\\\"usd_per_underlyin'
    'g_share\\\\\\"]]}\\"],[\\"quality_flags\\",{\\"$list\\":[\\"decimal_to_float_converted\\",\\"assumption_app'
    'lied\\"]}]]}]]}"],["quality_flags",{"$list":["assumption_applied"]}]]}],["record",{"$map":[["as_o'
    'f_date",{"$date":"2030-01-02"}],["assumptions",{"$map":[["maximum_repeated_loss_fraction",{"$map'
    '":[["denominator",50],["numerator",1]]}],["maximum_single_structure_loss_fraction",{"$map":[["de'
    'nominator",100],["numerator",1]]}],["portfolio_value",{"$map":[["amount",{"$decimal":"100000.0"}'
    '],["as_of_date",{"$date":"2030-01-02"}],["methodology","declared NAV"]]}],["risk_budget_methodol'
    'ogy","risk policy"]]}],["reason_codes",{"$list":[]}],["repeated_aggregate_maximum_loss",{"$decim'
    'al":"141.250"}],["repeated_bet_count",1],["repeated_loss_fraction",{"$map":[["denominator",80000'
    '],["numerator",113]]}],["single_loss_fraction",{"$map":[["denominator",80000],["numerator",113]]'
    '}],["single_position_maximum_loss",{"$decimal":"141.250"}],["status","affordable"],["structure",'
    '{"$map":[["assumed_portfolio_value_repr","100000.0"],["expected_holding_days",14],["legs",{"$lis'
    't":[{"$map":[["contract_multiplier",100],["expiration",{"$date":"2030-03-03"}],["option_type","c'
    'all"],["quantity",1],["strike_float_repr","100.0"],["underlying","SPY"]]}]}],["structure_type","'
    'long_call"],["underlying","SPY"]]}]]}],["wrapper_type","StructureAffordabilityAssessmentResult"]'
    ']}],["structure_costs_result",{"$map":[["lineage",{"$map":[["calculated_at",{"$datetime":"2030-0'
    '1-02T15:30:04.000000Z"}],["calculation_id","scenario-valuation-costs"],["calculation_type","stru'
    'cture_costs"],["inputs",{"$list":[{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.00'
    '0002Z"}],["record_id","cost-call-contract-reference"],["source_ids",{"$list":["cost-call-contrac'
    't-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}'
    '],["record_id","cost-call-greeks"],["source_ids",{"$list":["cost-call-greeks-source-0"]}]]},{"$m'
    'ap":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","cost-call-quote'
    '"],["source_ids",{"$list":["cost-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime'
    '":"2030-01-02T15:30:00.000002Z"}],["record_id","cost-underlying-quote"],["source_ids",{"$list":['
    '"cost-underlying-quote-source-0"]}]]}]}],["methodology_id","exact-structure-costs"],["methodolog'
    'y_version","v0.2"],["parameters_json","{\\"$map\\":[[\\"calculation_values\\",{\\"$map\\":[[\\"commissi'
    'ons_and_fees_exact\\",{\\"$decimal\\":\\"1.25\\"}],[\\"cumulative_repeated_bet_cost_exact\\",{\\"$decima'
    'l\\":\\"141.250\\"}],[\\"estimated_spread_cost_exact\\",{\\"$decimal\\":\\"20.000\\"}],[\\"gamma_exact\\",{'
    '\\"$decimal\\":\\"2.000\\"}],[\\"maximum_loss_exact\\",{\\"$decimal\\":\\"141.250\\"}],[\\"quoted_mid_premi'
    'um_exact\\",{\\"$decimal\\":\\"120.000\\"}],[\\"stable_record_values\\",{\\"$map\\":[[\\"commissions_and_f'
    'ees_repr\\",\\"1.25\\"],[\\"cumulative_repeated_bet_cost_repr\\",\\"141.25\\"],[\\"estimated_spread_cost'
    '_repr\\",\\"20.0\\"],[\\"gamma_repr\\",\\"2.0\\"],[\\"maximum_loss_repr\\",\\"141.25\\"],[\\"quoted_mid_prem'
    'ium_repr\\",\\"120.0\\"],[\\"theta_per_day_repr\\",\\"-10.0\\"],[\\"total_entry_cost_repr\\",\\"141.25\\"],'
    '[\\"underlying_price_repr\\",\\"100.0\\"]]}],[\\"theta_per_day_exact\\",{\\"$decimal\\":\\"-10.000\\"}],[\\'
    '"total_entry_cost_exact\\",{\\"$decimal\\":\\"141.250\\"}],[\\"underlying_price_exact\\",{\\"$decimal\\":'
    '\\"100.000\\"}]]}],[\\"commission_and_fee_scope\\",\\"entry_only_total_position\\"],[\\"commissions_and'
    '_fees_usd\\",{\\"$decimal\\":\\"1.25\\"}],[\\"gamma_input_unit\\",\\"option_value_change_per_usd_squared'
    '_per_underlying_unit\\"],[\\"gamma_position_rule\\",\\"sum(gamma_per_underlying_unit_per_usd_squared'
    '*quantity*contract_multiplier)\\"],[\\"greeks_methodology\\",{\\"$map\\":[[\\"dividend_input_descripti'
    'on\\",\\"Synthetic dividend input\\"],[\\"model_name\\",\\"Synthetic Black-Scholes\\"],[\\"model_version'
    '\\",\\"fixture-v1\\"],[\\"rate_input_description\\",\\"Synthetic USD curve input\\"],[\\"theta_day_basis'
    '\\",\\"Provider calendar-day convention\\"],[\\"unit_convention\\",\\"Contract-defined canonical units'
    '\\"]]}],[\\"leg_correspondence\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"currency\\'
    '",\\"USD\\"],[\\"deliverable_id\\",null],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"option_contr'
    'act_reference_record_id\\",\\"cost-call-contract-reference\\"],[\\"option_greeks_record_id\\",\\"cost-'
    'call-greeks\\"],[\\"option_quote_record_id\\",\\"cost-call-quote\\"],[\\"option_type\\",\\"call\\"],[\\"qu'
    'antity\\",1],[\\"strike\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying\\",{\\"$map\\":[[\\"currency\\",\\"USD'
    '\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"symbol\\",\\"SPY\\"]]}],[\\"underlying'
    '_quote_record_id\\",\\"cost-underlying-quote\\"]]}]}],[\\"normalized_evidence\\",{\\"$map\\":[[\\"contra'
    'ct_references\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"d'
    'eliverable_id\\",null],[\\"exercise_style\\",\\"American\\"],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\'
    '"}],[\\"last_trade_date\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"listing_date\\",{\\"$date\\":\\"2029-09-16\\"'
    '}],[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"option_type\\",\\"call\\"'
    '],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"quantity\\",1],[\\"record_id\\",\\"cost-call-cont'
    'ract-reference\\"],[\\"settlement_type\\",\\"Physical\\"],[\\"source_ids\\",{\\"$list\\":[\\"cost-call-con'
    'tract-reference-source-0\\"]}],[\\"strike\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying\\",{\\"$map\\":[['
    '\\"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"symbol\\",\\"SPY\\"'
    ']]}]]}]}],[\\"option_greeks\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"currency\\",'
    '\\"USD\\"],[\\"deliverable_id\\",null],[\\"dividend_input_description\\",\\"Synthetic dividend input\\"]'
    ',[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"gamma\\",{\\"$decimal\\":\\"0.020\\"}],[\\"model_name\\'
    '",\\"Synthetic Black-Scholes\\"],[\\"model_version\\",\\"fixture-v1\\"],[\\"normalized_at\\",{\\"$datetim'
    'e\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"option_type\\",\\"call\\"],[\\"propagated_quality_flags\\",{'
    '\\"$list\\":[]}],[\\"quantity\\",1],[\\"rate_input_description\\",\\"Synthetic USD curve input\\"],[\\"re'
    'cord_id\\",\\"cost-call-greeks\\"],[\\"session_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"source_ids\\",{\\'
    '"$list\\":[\\"cost-call-greeks-source-0\\"]}],[\\"strike\\",{\\"$decimal\\":\\"100.0\\"}],[\\"theta\\",{\\"$'
    'decimal\\":\\"-0.100\\"}],[\\"theta_day_basis\\",\\"Provider calendar-day convention\\"],[\\"underlying\\'
    '",{\\"$map\\":[[\\"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"sy'
    'mbol\\",\\"SPY\\"]]}],[\\"unit_convention\\",\\"Contract-defined canonical units\\"]]}]}],[\\"option_quo'
    'tes\\",{\\"$list\\":[{\\"$map\\":[[\\"ask_premium\\",{\\"$decimal\\":\\"1.40\\"}],[\\"bid_premium\\",{\\"$deci'
    'mal\\":\\"1.00\\"}],[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],'
    '[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30'
    ':00.000002Z\\"}],[\\"option_type\\",\\"call\\"],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"quan'
    'tity\\",1],[\\"record_id\\",\\"cost-call-quote\\"],[\\"session_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"s'
    'ource_ids\\",{\\"$list\\":[\\"cost-call-quote-source-0\\"]}],[\\"strike\\",{\\"$decimal\\":\\"100.0\\"}],[\\'
    '"underlying\\",{\\"$map\\":[[\\"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"'
    'etf\\"],[\\"symbol\\",\\"SPY\\"]]}]]}]}],[\\"underlying_quote\\",{\\"$map\\":[[\\"ask_price\\",{\\"$decimal\\'
    '":\\"101.00\\"}],[\\"bid_price\\",{\\"$decimal\\":\\"99.00\\"}],[\\"midpoint_rule\\",\\"(bid_price+ask_pric'
    'e)/2\\"],[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_qualit'
    'y_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"cost-underlying-quote\\"],[\\"session_date\\",{\\"$date\\"'
    ':\\"2030-01-02\\"}],[\\"source_ids\\",{\\"$list\\":[\\"cost-underlying-quote-source-0\\"]}],[\\"underlyin'
    'g\\",{\\"$map\\":[[\\"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"'
    'symbol\\",\\"SPY\\"]]}],[\\"underlying_price_exact\\",{\\"$decimal\\":\\"100.000\\"}]]}]]}],[\\"position_v'
    'alue_unit\\",\\"usd\\"],[\\"premium_input_unit\\",\\"usd_per_underlying_unit\\"],[\\"premium_midpoint_ru'
    'le\\",\\"sum(((bid_premium+ask_premium)/2)*quantity*contract_multiplier)\\"],[\\"repeated_bet_count\\'
    '",1],[\\"spread_cost_rule\\",\\"sum(((ask_premium-bid_premium)/2)*quantity*contract_multiplier)\\"],'
    '[\\"spread_cost_scope\\",\\"entry_only_midpoint_to_ask\\"],[\\"structure_identity\\",{\\"$map\\":[[\\"ass'
    'umed_portfolio_value_repr\\",\\"100000.0\\"],[\\"expected_holding_days\\",14],[\\"legs\\",{\\"$list\\":[{'
    '\\"$map\\":[[\\"contract_multiplier\\",100],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"option_ty'
    'pe\\",\\"call\\"],[\\"quantity\\",1],[\\"strike_float_repr\\",\\"100.0\\"],[\\"underlying\\",\\"SPY\\"]]}]}],'
    '[\\"structure_type\\",\\"long_call\\"],[\\"underlying\\",\\"SPY\\"]]}],[\\"theta_day_basis\\",\\"Provider c'
    'alendar-day convention\\"],[\\"theta_input_unit\\",\\"usd_per_underlying_unit_per_declared_day_basis'
    '\\"],[\\"theta_position_rule\\",\\"sum(theta_per_underlying_unit_per_declared_day_basis*quantity*con'
    'tract_multiplier)\\"],[\\"underlying_price_rule\\",\\"(bid_price+ask_price)/2\\"],[\\"underlying_price'
    '_unit\\",\\"usd_per_underlying_share\\"]]}"],["quality_flags",{"$list":["decimal_to_float_converted'
    '","assumption_applied"]}]]}],["record",{"$map":[["as_of_date",{"$date":"2030-01-02"}],["commissi'
    'ons_and_fees_float_repr","1.25"],["estimated_spread_cost_float_repr","20.0"],["gamma_float_repr"'
    ',"2.0"],["greeks_methodology","model=Synthetic Black-Scholes;model_version=fixture-v1;rate_input'
    '=Synthetic USD curve input;dividend_input=Synthetic dividend input;theta_day_basis=Provider cale'
    'ndar-day convention;unit_convention=Contract-defined canonical units"],["quoted_mid_premium_floa'
    't_repr","120.0"],["repeated_bet_count",1],["structure",{"$map":[["assumed_portfolio_value_repr",'
    '"100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$map":[["contract_multiplier",100],'
    '["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],["strike_float_repr"'
    ',"100.0"],["underlying","SPY"]]}]}],["structure_type","long_call"],["underlying","SPY"]]}],["the'
    'ta_per_day_float_repr","-10.0"],["underlying_price_float_repr","100.0"]]}],["wrapper_type","Stru'
    'ctureCostsTransformationResult"]]}],["structure_liquidity_result",{"$map":[["lineage",{"$map":[['
    '"calculated_at",{"$datetime":"2030-01-02T15:30:04.000000Z"}],["calculation_id","calculation-3c7a'
    '"],["calculation_type","structure_liquidity"],["inputs",{"$list":[{"$map":[["normalized_at",{"$d'
    'atetime":"2030-01-02T15:30:00.000002Z"}],["record_id","liquidity-call-open-interest"],["source_i'
    'ds",{"$list":["liquidity-call-open-interest-source-0"]}]]},{"$map":[["normalized_at",{"$datetime'
    '":"2030-01-02T15:30:00.000002Z"}],["record_id","liquidity-call-quote"],["source_ids",{"$list":["'
    'liquidity-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.'
    '000002Z"}],["record_id","liquidity-call-volume"],["source_ids",{"$list":["liquidity-call-volume-'
    'source-0"]}]]}]}],["methodology_id","exact-structure-liquidity"],["methodology_version","v0.2"],'
    '["parameters_json","{\\"$map\\":[[\\"activity_count_unit\\",\\"contracts\\"],[\\"calculation_values\\",{'
    '\\"$map\\":[[\\"as_of_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"minimum_leg_daily_volume\\",40],[\\"minim'
    'um_leg_open_interest\\",80],[\\"quote_methodology\\",\\"exact selected option quotes scaled by quant'
    'ity and contract multiplier\\"],[\\"quoted_ask_value_exact\\",{\\"$decimal\\":\\"140.00\\"}],[\\"quoted_'
    'bid_value_exact\\",{\\"$decimal\\":\\"100.00\\"}],[\\"stable_public_values\\",{\\"$map\\":[[\\"quoted_ask_'
    'value_repr\\",\\"140.0\\"],[\\"quoted_bid_value_repr\\",\\"100.0\\"]]}]]}],[\\"leg_correspondence\\",{\\"$'
    'list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null'
    '],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"open_interest_record_id\\",\\"liquidity-call-open'
    '-interest\\"],[\\"option_type\\",\\"call\\"],[\\"quantity\\",1],[\\"quote_record_id\\",\\"liquidity-call-q'
    'uote\\"],[\\"strike\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying\\",{\\"$map\\":[[\\"currency\\",\\"USD\\"],'
    '[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"symbol\\",\\"SPY\\"]]}],[\\"volume_record_'
    'id\\",\\"liquidity-call-volume\\"]]}]}],[\\"minimum_leg_rule\\",\\"minimum_unscaled_contract_count_acr'
    'oss_legs\\"],[\\"normalized_evidence\\",{\\"$map\\":[[\\"option_open_interest\\",{\\"$list\\":[{\\"$map\\":'
    '[[\\"contract\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id'
    '\\",null],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"option_type\\",\\"call\\"],[\\"strike\\",{\\"$'
    'decimal\\":\\"100.0\\"}],[\\"underlying\\",{\\"$map\\":[[\\"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\'
    '"],[\\"security_type\\",\\"etf\\"],[\\"symbol\\",\\"SPY\\"]]}]]}],[\\"leg_index\\",0],[\\"normalized_at\\",{'
    '\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"open_interest\\",80],[\\"open_interest_session_'
    'date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",'
    '\\"liquidity-call-open-interest\\"],[\\"source_ids\\",{\\"$list\\":[\\"liquidity-call-open-interest-sou'
    'rce-0\\"]}]]}]}],[\\"option_quotes\\",{\\"$list\\":[{\\"$map\\":[[\\"ask_premium\\",{\\"$decimal\\":\\"1.40\\'
    '"}],[\\"bid_premium\\",{\\"$decimal\\":\\"1.00\\"}],[\\"contract\\",{\\"$map\\":[[\\"contract_multiplier\\",'
    '100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}'
    '],[\\"option_type\\",\\"call\\"],[\\"strike\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying\\",{\\"$map\\":[[\\'
    '"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"symbol\\",\\"SPY\\"]'
    ']}]]}],[\\"leg_index\\",0],[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"'
    'propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"liquidity-call-quote\\"],[\\"session_d'
    'ate\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"source_ids\\",{\\"$list\\":[\\"liquidity-call-quote-source-0\\"]'
    '}]]}]}],[\\"option_volumes\\",{\\"$list\\":[{\\"$map\\":[[\\"contract\\",{\\"$map\\":[[\\"contract_multipli'
    'er\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"expiration\\",{\\"$date\\":\\"2030-03-'
    '03\\"}],[\\"option_type\\",\\"call\\"],[\\"strike\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying\\",{\\"$map\\'
    '":[[\\"currency\\",\\"USD\\"],[\\"listing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"symbol\\",\\"S'
    'PY\\"]]}]]}],[\\"cumulative_volume\\",40],[\\"is_session_complete\\",true],[\\"leg_index\\",0],[\\"norma'
    'lized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$li'
    'st\\":[]}],[\\"record_id\\",\\"liquidity-call-volume\\"],[\\"session_date\\",{\\"$date\\":\\"2030-01-02\\"}'
    '],[\\"source_ids\\",{\\"$list\\":[\\"liquidity-call-volume-source-0\\"]}]]}]}]]}],[\\"position_value_ru'
    'le\\",\\"sum(premium_per_underlying_unit*quantity*contract_multiplier)\\"],[\\"position_value_unit\\"'
    ',\\"usd\\"],[\\"premium_input_unit\\",\\"usd_per_underlying_unit\\"],[\\"structure_identity\\",{\\"$map\\"'
    ':[[\\"assumed_portfolio_value_repr\\",\\"100000.0\\"],[\\"expected_holding_days\\",14],[\\"legs\\",{\\"$l'
    'ist\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"o'
    'ption_type\\",\\"call\\"],[\\"quantity\\",1],[\\"strike_float_repr\\",\\"100.0\\"],[\\"underlying\\",\\"SPY\\'
    '"]]}]}],[\\"structure_type\\",\\"long_call\\"],[\\"underlying\\",\\"SPY\\"]]}]]}"],["quality_flags",{"$l'
    'ist":["decimal_to_float_converted"]}]]}],["record",{"$map":[["as_of_date",{"$date":"2030-01-02"}'
    '],["minimum_leg_daily_volume",40],["minimum_leg_open_interest",80],["quote_methodology","exact s'
    'elected option quotes scaled by quantity and contract multiplier"],["quoted_ask_value_float_repr'
    '","140.0"],["quoted_bid_value_float_repr","100.0"],["structure",{"$map":[["assumed_portfolio_val'
    'ue_repr","100000.0"],["expected_holding_days",14],["legs",{"$list":[{"$map":[["contract_multipli'
    'er",100],["expiration",{"$date":"2030-03-03"}],["option_type","call"],["quantity",1],["strike_fl'
    'oat_repr","100.0"],["underlying","SPY"]]}]}],["structure_type","long_call"],["underlying","SPY"]'
    ']}]]}],["wrapper_type","StructureLiquidityTransformationResult"]]}],["tail_pricing_result",{"$ma'
    'p":[["lineage",{"$map":[["calculated_at",{"$datetime":"2030-01-02T15:30:05.000000Z"}],["calculat'
    'ion_id","calculation-3c7e"],["calculation_type","tail_pricing"],["inputs",{"$list":[{"$map":[["n'
    'ormalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-0"],["source_ids",{'
    '"$list":["hrv-0-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.00000'
    '2Z"}],["record_id","hrv-1"],["source_ids",{"$list":["hrv-1-source-0"]}]]},{"$map":[["normalized_'
    'at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-2"],["source_ids",{"$list":["'
    'hrv-2-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["re'
    'cord_id","tail-current-30-call10-greeks"],["source_ids",{"$list":["tail-current-30-call10-greeks'
    '-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_'
    'id","tail-current-30-call10-iv"],["source_ids",{"$list":["tail-current-30-call10-iv-source-0"]}]'
    ']},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-cur'
    'rent-30-call10-quote"],["source_ids",{"$list":["tail-current-30-call10-quote-source-0"]}]]},{"$m'
    'ap":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30'
    '-call10-reference"],["source_ids",{"$list":["tail-current-30-call10-reference-source-0"]}]]},{"$'
    'map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-3'
    '0-call25-greeks"],["source_ids",{"$list":["tail-current-30-call25-greeks-source-0"]}]]},{"$map":'
    '[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-cal'
    'l25-iv"],["source_ids",{"$list":["tail-current-30-call25-iv-source-0"]}]]},{"$map":[["normalized'
    '_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-call25-quote"],['
    '"source_ids",{"$list":["tail-current-30-call25-quote-source-0"]}]]},{"$map":[["normalized_at",{"'
    '$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-call25-reference"],["so'
    'urce_ids",{"$list":["tail-current-30-call25-reference-source-0"]}]]},{"$map":[["normalized_at",{'
    '"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-put10-greeks"],["sourc'
    'e_ids",{"$list":["tail-current-30-put10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datet'
    'ime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-30-put10-iv"],["source_ids",{"$l'
    'ist":["tail-current-30-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-0'
    '2T15:30:00.000002Z"}],["record_id","tail-current-30-put10-quote"],["source_ids",{"$list":["tail-'
    'current-30-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:0'
    '0.000002Z"}],["record_id","tail-current-30-put10-reference"],["source_ids",{"$list":["tail-curre'
    'nt-30-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","tail-current-30-put25-greeks"],["source_ids",{"$list":["tail-current-3'
    '0-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002'
    'Z"}],["record_id","tail-current-30-put25-iv"],["source_ids",{"$list":["tail-current-30-put25-iv-'
    'source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_i'
    'd","tail-current-30-put25-quote"],["source_ids",{"$list":["tail-current-30-put25-quote-source-0"'
    ']}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-'
    'current-30-put25-reference"],["source_ids",{"$list":["tail-current-30-put25-reference-source-0"]'
    '}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-c'
    'urrent-60-call10-greeks"],["source_ids",{"$list":["tail-current-60-call10-greeks-source-0"]}]]},'
    '{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-curren'
    't-60-call10-iv"],["source_ids",{"$list":["tail-current-60-call10-iv-source-0"]}]]},{"$map":[["no'
    'rmalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-call10-q'
    'uote"],["source_ids",{"$list":["tail-current-60-call10-quote-source-0"]}]]},{"$map":[["normalize'
    'd_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-call10-referenc'
    'e"],["source_ids",{"$list":["tail-current-60-call10-reference-source-0"]}]]},{"$map":[["normaliz'
    'ed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-call25-greeks"'
    '],["source_ids",{"$list":["tail-current-60-call25-greeks-source-0"]}]]},{"$map":[["normalized_at'
    '",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-call25-iv"],["sourc'
    'e_ids",{"$list":["tail-current-60-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime'
    '":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-call25-quote"],["source_ids",{"$'
    'list":["tail-current-60-call25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030'
    '-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-call25-reference"],["source_ids",{"$lis'
    't":["tail-current-60-call25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"203'
    '0-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-put10-greeks"],["source_ids",{"$list":'
    '["tail-current-60-put10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02'
    'T15:30:00.000002Z"}],["record_id","tail-current-60-put10-iv"],["source_ids",{"$list":["tail-curr'
    'ent-60-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.00000'
    '2Z"}],["record_id","tail-current-60-put10-quote"],["source_ids",{"$list":["tail-current-60-put10'
    '-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["r'
    'ecord_id","tail-current-60-put10-reference"],["source_ids",{"$list":["tail-current-60-put10-refe'
    'rence-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["re'
    'cord_id","tail-current-60-put25-greeks"],["source_ids",{"$list":["tail-current-60-put25-greeks-s'
    'ource-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id'
    '","tail-current-60-put25-iv"],["source_ids",{"$list":["tail-current-60-put25-iv-source-0"]}]]},{'
    '"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current'
    '-60-put25-quote"],["source_ids",{"$list":["tail-current-60-put25-quote-source-0"]}]]},{"$map":[['
    '"normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-current-60-put25'
    '-reference"],["source_ids",{"$list":["tail-current-60-put25-reference-source-0"]}]]},{"$map":[["'
    'normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-call'
    '10-greeks"],["source_ids",{"$list":["tail-history-0-30-call10-greeks-source-0"]}]]},{"$map":[["n'
    'ormalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-call1'
    '0-iv"],["source_ids",{"$list":["tail-history-0-30-call10-iv-source-0"]}]]},{"$map":[["normalized'
    '_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-call10-quote"]'
    ',["source_ids",{"$list":["tail-history-0-30-call10-quote-source-0"]}]]},{"$map":[["normalized_at'
    '",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-call10-reference"'
    '],["source_ids",{"$list":["tail-history-0-30-call10-reference-source-0"]}]]},{"$map":[["normaliz'
    'ed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-call25-greek'
    's"],["source_ids",{"$list":["tail-history-0-30-call25-greeks-source-0"]}]]},{"$map":[["normalize'
    'd_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-call25-iv"],['
    '"source_ids",{"$list":["tail-history-0-30-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$'
    'datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-call25-quote"],["sourc'
    'e_ids",{"$list":["tail-history-0-30-call25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$dat'
    'etime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-call25-reference"],["sour'
    'ce_ids",{"$list":["tail-history-0-30-call25-reference-source-0"]}]]},{"$map":[["normalized_at",{'
    '"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-put10-greeks"],["sou'
    'rce_ids",{"$list":["tail-history-0-30-put10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$d'
    'atetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-put10-iv"],["source_ids'
    '",{"$list":["tail-history-0-30-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2'
    '030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-put10-quote"],["source_ids",{"$lis'
    't":["tail-history-0-30-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-0'
    '1-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-put10-reference"],["source_ids",{"$list'
    '":["tail-history-0-30-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"203'
    '0-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-put25-greeks"],["source_ids",{"$list'
    '":["tail-history-0-30-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-0'
    '1-02T15:30:00.000002Z"}],["record_id","tail-history-0-30-put25-iv"],["source_ids",{"$list":["tai'
    'l-history-0-30-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:'
    '00.000002Z"}],["record_id","tail-history-0-30-put25-quote"],["source_ids",{"$list":["tail-histor'
    'y-0-30-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.00'
    '0002Z"}],["record_id","tail-history-0-30-put25-reference"],["source_ids",{"$list":["tail-history'
    '-0-30-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","tail-history-0-60-atm-call-greeks"],["source_ids",{"$list":["tail-hist'
    'ory-0-60-atm-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30'
    ':00.000002Z"}],["record_id","tail-history-0-60-atm-call-iv"],["source_ids",{"$list":["tail-histo'
    'ry-0-60-atm-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0'
    '00002Z"}],["record_id","tail-history-0-60-atm-call-quote"],["source_ids",{"$list":["tail-history'
    '-0-60-atm-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.'
    '000002Z"}],["record_id","tail-history-0-60-atm-call-reference"],["source_ids",{"$list":["tail-hi'
    'story-0-60-atm-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T'
    '15:30:00.000002Z"}],["record_id","tail-history-0-60-atm-put-greeks"],["source_ids",{"$list":["ta'
    'il-history-0-60-atm-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02'
    'T15:30:00.000002Z"}],["record_id","tail-history-0-60-atm-put-iv"],["source_ids",{"$list":["tail-'
    'history-0-60-atm-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:'
    '00.000002Z"}],["record_id","tail-history-0-60-atm-put-quote"],["source_ids",{"$list":["tail-hist'
    'ory-0-60-atm-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:0'
    '0.000002Z"}],["record_id","tail-history-0-60-atm-put-reference"],["source_ids",{"$list":["tail-h'
    'istory-0-60-atm-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T'
    '15:30:00.000002Z"}],["record_id","tail-history-0-60-call10-greeks"],["source_ids",{"$list":["tai'
    'l-history-0-60-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T1'
    '5:30:00.000002Z"}],["record_id","tail-history-0-60-call10-iv"],["source_ids",{"$list":["tail-his'
    'tory-0-60-call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0'
    '00002Z"}],["record_id","tail-history-0-60-call10-quote"],["source_ids",{"$list":["tail-history-0'
    '-60-call10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0000'
    '02Z"}],["record_id","tail-history-0-60-call10-reference"],["source_ids",{"$list":["tail-history-'
    '0-60-call10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","tail-history-0-60-call25-greeks"],["source_ids",{"$list":["tail-histor'
    'y-0-60-call25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.'
    '000002Z"}],["record_id","tail-history-0-60-call25-iv"],["source_ids",{"$list":["tail-history-0-6'
    '0-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}'
    '],["record_id","tail-history-0-60-call25-quote"],["source_ids",{"$list":["tail-history-0-60-call'
    '25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],['
    '"record_id","tail-history-0-60-call25-reference"],["source_ids",{"$list":["tail-history-0-60-cal'
    'l25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z'
    '"}],["record_id","tail-history-0-60-put10-greeks"],["source_ids",{"$list":["tail-history-0-60-pu'
    't10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}]'
    ',["record_id","tail-history-0-60-put10-iv"],["source_ids",{"$list":["tail-history-0-60-put10-iv-'
    'source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_i'
    'd","tail-history-0-60-put10-quote"],["source_ids",{"$list":["tail-history-0-60-put10-quote-sourc'
    'e-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","t'
    'ail-history-0-60-put10-reference"],["source_ids",{"$list":["tail-history-0-60-put10-reference-so'
    'urce-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id"'
    ',"tail-history-0-60-put25-greeks"],["source_ids",{"$list":["tail-history-0-60-put25-greeks-sourc'
    'e-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","t'
    'ail-history-0-60-put25-iv"],["source_ids",{"$list":["tail-history-0-60-put25-iv-source-0"]}]]},{'
    '"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history'
    '-0-60-put25-quote"],["source_ids",{"$list":["tail-history-0-60-put25-quote-source-0"]}]]},{"$map'
    '":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0-60'
    '-put25-reference"],["source_ids",{"$list":["tail-history-0-60-put25-reference-source-0"]}]]},{"$'
    'map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-0'
    '-60-underlying"],["source_ids",{"$list":["tail-history-0-60-underlying-source-0"]}]]},{"$map":[['
    '"normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-cal'
    'l10-greeks"],["source_ids",{"$list":["tail-history-1-30-call10-greeks-source-0"]}]]},{"$map":[["'
    'normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-call'
    '10-iv"],["source_ids",{"$list":["tail-history-1-30-call10-iv-source-0"]}]]},{"$map":[["normalize'
    'd_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-call10-quote"'
    '],["source_ids",{"$list":["tail-history-1-30-call10-quote-source-0"]}]]},{"$map":[["normalized_a'
    't",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-call10-reference'
    '"],["source_ids",{"$list":["tail-history-1-30-call10-reference-source-0"]}]]},{"$map":[["normali'
    'zed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-call25-gree'
    'ks"],["source_ids",{"$list":["tail-history-1-30-call25-greeks-source-0"]}]]},{"$map":[["normaliz'
    'ed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-call25-iv"],'
    '["source_ids",{"$list":["tail-history-1-30-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{"'
    '$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-call25-quote"],["sour'
    'ce_ids",{"$list":["tail-history-1-30-call25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$da'
    'tetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-call25-reference"],["sou'
    'rce_ids",{"$list":["tail-history-1-30-call25-reference-source-0"]}]]},{"$map":[["normalized_at",'
    '{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-put10-greeks"],["so'
    'urce_ids",{"$list":["tail-history-1-30-put10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$'
    'datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-put10-iv"],["source_id'
    's",{"$list":["tail-history-1-30-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"'
    '2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-put10-quote"],["source_ids",{"$li'
    'st":["tail-history-1-30-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-'
    '01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-put10-reference"],["source_ids",{"$lis'
    't":["tail-history-1-30-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"20'
    '30-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-put25-greeks"],["source_ids",{"$lis'
    't":["tail-history-1-30-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-'
    '01-02T15:30:00.000002Z"}],["record_id","tail-history-1-30-put25-iv"],["source_ids",{"$list":["ta'
    'il-history-1-30-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30'
    ':00.000002Z"}],["record_id","tail-history-1-30-put25-quote"],["source_ids",{"$list":["tail-histo'
    'ry-1-30-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0'
    '00002Z"}],["record_id","tail-history-1-30-put25-reference"],["source_ids",{"$list":["tail-histor'
    'y-1-30-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:0'
    '0.000002Z"}],["record_id","tail-history-1-60-atm-call-greeks"],["source_ids",{"$list":["tail-his'
    'tory-1-60-atm-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:3'
    '0:00.000002Z"}],["record_id","tail-history-1-60-atm-call-iv"],["source_ids",{"$list":["tail-hist'
    'ory-1-60-atm-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.'
    '000002Z"}],["record_id","tail-history-1-60-atm-call-quote"],["source_ids",{"$list":["tail-histor'
    'y-1-60-atm-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","tail-history-1-60-atm-call-reference"],["source_ids",{"$list":["tail-h'
    'istory-1-60-atm-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02'
    'T15:30:00.000002Z"}],["record_id","tail-history-1-60-atm-put-greeks"],["source_ids",{"$list":["t'
    'ail-history-1-60-atm-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-0'
    '2T15:30:00.000002Z"}],["record_id","tail-history-1-60-atm-put-iv"],["source_ids",{"$list":["tail'
    '-history-1-60-atm-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30'
    ':00.000002Z"}],["record_id","tail-history-1-60-atm-put-quote"],["source_ids",{"$list":["tail-his'
    'tory-1-60-atm-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:'
    '00.000002Z"}],["record_id","tail-history-1-60-atm-put-reference"],["source_ids",{"$list":["tail-'
    'history-1-60-atm-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02'
    'T15:30:00.000002Z"}],["record_id","tail-history-1-60-call10-greeks"],["source_ids",{"$list":["ta'
    'il-history-1-60-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T'
    '15:30:00.000002Z"}],["record_id","tail-history-1-60-call10-iv"],["source_ids",{"$list":["tail-hi'
    'story-1-60-call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.'
    '000002Z"}],["record_id","tail-history-1-60-call10-quote"],["source_ids",{"$list":["tail-history-'
    '1-60-call10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000'
    '002Z"}],["record_id","tail-history-1-60-call10-reference"],["source_ids",{"$list":["tail-history'
    '-1-60-call10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:0'
    '0.000002Z"}],["record_id","tail-history-1-60-call25-greeks"],["source_ids",{"$list":["tail-histo'
    'ry-1-60-call25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","tail-history-1-60-call25-iv"],["source_ids",{"$list":["tail-history-1-'
    '60-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"'
    '}],["record_id","tail-history-1-60-call25-quote"],["source_ids",{"$list":["tail-history-1-60-cal'
    'l25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],'
    '["record_id","tail-history-1-60-call25-reference"],["source_ids",{"$list":["tail-history-1-60-ca'
    'll25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002'
    'Z"}],["record_id","tail-history-1-60-put10-greeks"],["source_ids",{"$list":["tail-history-1-60-p'
    'ut10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}'
    '],["record_id","tail-history-1-60-put10-iv"],["source_ids",{"$list":["tail-history-1-60-put10-iv'
    '-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_'
    'id","tail-history-1-60-put10-quote"],["source_ids",{"$list":["tail-history-1-60-put10-quote-sour'
    'ce-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","'
    'tail-history-1-60-put10-reference"],["source_ids",{"$list":["tail-history-1-60-put10-reference-s'
    'ource-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id'
    '","tail-history-1-60-put25-greeks"],["source_ids",{"$list":["tail-history-1-60-put25-greeks-sour'
    'ce-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","'
    'tail-history-1-60-put25-iv"],["source_ids",{"$list":["tail-history-1-60-put25-iv-source-0"]}]]},'
    '{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-histor'
    'y-1-60-put25-quote"],["source_ids",{"$list":["tail-history-1-60-put25-quote-source-0"]}]]},{"$ma'
    'p":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-1-6'
    '0-put25-reference"],["source_ids",{"$list":["tail-history-1-60-put25-reference-source-0"]}]]},{"'
    '$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-'
    '1-60-underlying"],["source_ids",{"$list":["tail-history-1-60-underlying-source-0"]}]]},{"$map":['
    '["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-ca'
    'll10-greeks"],["source_ids",{"$list":["tail-history-2-30-call10-greeks-source-0"]}]]},{"$map":[['
    '"normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-cal'
    'l10-iv"],["source_ids",{"$list":["tail-history-2-30-call10-iv-source-0"]}]]},{"$map":[["normaliz'
    'ed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-call10-quote'
    '"],["source_ids",{"$list":["tail-history-2-30-call10-quote-source-0"]}]]},{"$map":[["normalized_'
    'at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-call10-referenc'
    'e"],["source_ids",{"$list":["tail-history-2-30-call10-reference-source-0"]}]]},{"$map":[["normal'
    'ized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-call25-gre'
    'eks"],["source_ids",{"$list":["tail-history-2-30-call25-greeks-source-0"]}]]},{"$map":[["normali'
    'zed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-call25-iv"]'
    ',["source_ids",{"$list":["tail-history-2-30-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{'
    '"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-call25-quote"],["sou'
    'rce_ids",{"$list":["tail-history-2-30-call25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$d'
    'atetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-call25-reference"],["so'
    'urce_ids",{"$list":["tail-history-2-30-call25-reference-source-0"]}]]},{"$map":[["normalized_at"'
    ',{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-put10-greeks"],["s'
    'ource_ids",{"$list":["tail-history-2-30-put10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"'
    '$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-put10-iv"],["source_i'
    'ds",{"$list":["tail-history-2-30-put10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":'
    '"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-put10-quote"],["source_ids",{"$l'
    'ist":["tail-history-2-30-put10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030'
    '-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-put10-reference"],["source_ids",{"$li'
    'st":["tail-history-2-30-put10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2'
    '030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-put25-greeks"],["source_ids",{"$li'
    'st":["tail-history-2-30-put25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030'
    '-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-30-put25-iv"],["source_ids",{"$list":["t'
    'ail-history-2-30-put25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:3'
    '0:00.000002Z"}],["record_id","tail-history-2-30-put25-quote"],["source_ids",{"$list":["tail-hist'
    'ory-2-30-put25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.'
    '000002Z"}],["record_id","tail-history-2-30-put25-reference"],["source_ids",{"$list":["tail-histo'
    'ry-2-30-put25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:'
    '00.000002Z"}],["record_id","tail-history-2-60-atm-call-greeks"],["source_ids",{"$list":["tail-hi'
    'story-2-60-atm-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:'
    '30:00.000002Z"}],["record_id","tail-history-2-60-atm-call-iv"],["source_ids",{"$list":["tail-his'
    'tory-2-60-atm-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","tail-history-2-60-atm-call-quote"],["source_ids",{"$list":["tail-histo'
    'ry-2-60-atm-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:0'
    '0.000002Z"}],["record_id","tail-history-2-60-atm-call-reference"],["source_ids",{"$list":["tail-'
    'history-2-60-atm-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-0'
    '2T15:30:00.000002Z"}],["record_id","tail-history-2-60-atm-put-greeks"],["source_ids",{"$list":["'
    'tail-history-2-60-atm-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-'
    '02T15:30:00.000002Z"}],["record_id","tail-history-2-60-atm-put-iv"],["source_ids",{"$list":["tai'
    'l-history-2-60-atm-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:3'
    '0:00.000002Z"}],["record_id","tail-history-2-60-atm-put-quote"],["source_ids",{"$list":["tail-hi'
    'story-2-60-atm-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30'
    ':00.000002Z"}],["record_id","tail-history-2-60-atm-put-reference"],["source_ids",{"$list":["tail'
    '-history-2-60-atm-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-0'
    '2T15:30:00.000002Z"}],["record_id","tail-history-2-60-call10-greeks"],["source_ids",{"$list":["t'
    'ail-history-2-60-call10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02'
    'T15:30:00.000002Z"}],["record_id","tail-history-2-60-call10-iv"],["source_ids",{"$list":["tail-h'
    'istory-2-60-call10-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","tail-history-2-60-call10-quote"],["source_ids",{"$list":["tail-history'
    '-2-60-call10-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.00'
    '0002Z"}],["record_id","tail-history-2-60-call10-reference"],["source_ids",{"$list":["tail-histor'
    'y-2-60-call10-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:'
    '00.000002Z"}],["record_id","tail-history-2-60-call25-greeks"],["source_ids",{"$list":["tail-hist'
    'ory-2-60-call25-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:0'
    '0.000002Z"}],["record_id","tail-history-2-60-call25-iv"],["source_ids",{"$list":["tail-history-2'
    '-60-call25-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z'
    '"}],["record_id","tail-history-2-60-call25-quote"],["source_ids",{"$list":["tail-history-2-60-ca'
    'll25-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}]'
    ',["record_id","tail-history-2-60-call25-reference"],["source_ids",{"$list":["tail-history-2-60-c'
    'all25-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.00000'
    '2Z"}],["record_id","tail-history-2-60-put10-greeks"],["source_ids",{"$list":["tail-history-2-60-'
    'put10-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"'
    '}],["record_id","tail-history-2-60-put10-iv"],["source_ids",{"$list":["tail-history-2-60-put10-i'
    'v-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record'
    '_id","tail-history-2-60-put10-quote"],["source_ids",{"$list":["tail-history-2-60-put10-quote-sou'
    'rce-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id",'
    '"tail-history-2-60-put10-reference"],["source_ids",{"$list":["tail-history-2-60-put10-reference-'
    'source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_i'
    'd","tail-history-2-60-put25-greeks"],["source_ids",{"$list":["tail-history-2-60-put25-greeks-sou'
    'rce-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id",'
    '"tail-history-2-60-put25-iv"],["source_ids",{"$list":["tail-history-2-60-put25-iv-source-0"]}]]}'
    ',{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-histo'
    'ry-2-60-put25-quote"],["source_ids",{"$list":["tail-history-2-60-put25-quote-source-0"]}]]},{"$m'
    'ap":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history-2-'
    '60-put25-reference"],["source_ids",{"$list":["tail-history-2-60-put25-reference-source-0"]}]]},{'
    '"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","tail-history'
    '-2-60-underlying"],["source_ids",{"$list":["tail-history-2-60-underlying-source-0"]}]]},{"$map":'
    '[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-call-g'
    'reeks"],["source_ids",{"$list":["ve-current-0-call-greeks-source-0"]}]]},{"$map":[["normalized_a'
    't",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-call-iv"],["source_id'
    's",{"$list":["ve-current-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-0'
    '1-02T15:30:00.000002Z"}],["record_id","ve-current-0-call-quote"],["source_ids",{"$list":["ve-cur'
    'rent-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000'
    '002Z"}],["record_id","ve-current-0-call-reference"],["source_ids",{"$list":["ve-current-0-call-r'
    'eference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],['
    '"record_id","ve-current-0-put-greeks"],["source_ids",{"$list":["ve-current-0-put-greeks-source-0'
    '"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-c'
    'urrent-0-put-iv"],["source_ids",{"$list":["ve-current-0-put-iv-source-0"]}]]},{"$map":[["normali'
    'zed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-put-quote"],["so'
    'urce_ids",{"$list":["ve-current-0-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime'
    '":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-put-reference"],["source_ids",{"$li'
    'st":["ve-current-0-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-'
    '02T15:30:00.000002Z"}],["record_id","ve-current-1-call-greeks"],["source_ids",{"$list":["ve-curr'
    'ent-1-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000'
    '002Z"}],["record_id","ve-current-1-call-iv"],["source_ids",{"$list":["ve-current-1-call-iv-sourc'
    'e-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","v'
    'e-current-1-call-quote"],["source_ids",{"$list":["ve-current-1-call-quote-source-0"]}]]},{"$map"'
    ':[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-call-'
    'reference"],["source_ids",{"$list":["ve-current-1-call-reference-source-0"]}]]},{"$map":[["norma'
    'lized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-put-greeks"],['
    '"source_ids",{"$list":["ve-current-1-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$date'
    'time":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-put-iv"],["source_ids",{"$list"'
    ':["ve-current-1-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:0'
    '0.000002Z"}],["record_id","ve-current-1-put-quote"],["source_ids",{"$list":["ve-current-1-put-qu'
    'ote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["reco'
    'rd_id","ve-current-1-put-reference"],["source_ids",{"$list":["ve-current-1-put-reference-source-'
    '0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-'
    'current-underlying"],["source_ids",{"$list":["ve-current-underlying-source-0"]}]]},{"$map":[["no'
    'rmalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-call-gree'
    'ks"],["source_ids",{"$list":["ve-history-0-0-call-greeks-source-0"]}]]},{"$map":[["normalized_at'
    '",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-call-iv"],["source_i'
    'ds",{"$list":["ve-history-0-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"203'
    '0-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-call-quote"],["source_ids",{"$list":["v'
    'e-history-0-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30'
    ':00.000002Z"}],["record_id","ve-history-0-0-call-reference"],["source_ids",{"$list":["ve-history'
    '-0-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0'
    '00002Z"}],["record_id","ve-history-0-0-put-greeks"],["source_ids",{"$list":["ve-history-0-0-put-'
    'greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["r'
    'ecord_id","ve-history-0-0-put-iv"],["source_ids",{"$list":["ve-history-0-0-put-iv-source-0"]}]]}'
    ',{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history'
    '-0-0-put-quote"],["source_ids",{"$list":["ve-history-0-0-put-quote-source-0"]}]]},{"$map":[["nor'
    'malized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-put-refere'
    'nce"],["source_ids",{"$list":["ve-history-0-0-put-reference-source-0"]}]]},{"$map":[["normalized'
    '_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-underlying"],["sour'
    'ce_ids",{"$list":["ve-history-0-underlying-source-0"]}]]},{"$map":[["normalized_at",{"$datetime"'
    ':"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-0-call-greeks"],["source_ids",{"$lis'
    't":["ve-history-1-0-call-greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-0'
    '2T15:30:00.000002Z"}],["record_id","ve-history-1-0-call-iv"],["source_ids",{"$list":["ve-history'
    '-1-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"'
    '}],["record_id","ve-history-1-0-call-quote"],["source_ids",{"$list":["ve-history-1-0-call-quote-'
    'source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_i'
    'd","ve-history-1-0-call-reference"],["source_ids",{"$list":["ve-history-1-0-call-reference-sourc'
    'e-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","v'
    'e-history-1-0-put-greeks"],["source_ids",{"$list":["ve-history-1-0-put-greeks-source-0"]}]]},{"$'
    'map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-0'
    '-put-iv"],["source_ids",{"$list":["ve-history-1-0-put-iv-source-0"]}]]},{"$map":[["normalized_at'
    '",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-0-put-quote"],["source'
    '_ids",{"$list":["ve-history-1-0-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":'
    '"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-0-put-reference"],["source_ids",{"$li'
    'st":["ve-history-1-0-put-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-0'
    '1-02T15:30:00.000002Z"}],["record_id","ve-history-1-underlying"],["source_ids",{"$list":["ve-his'
    'tory-1-underlying-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000'
    '002Z"}],["record_id","ve-history-2-0-call-greeks"],["source_ids",{"$list":["ve-history-2-0-call-'
    'greeks-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["r'
    'ecord_id","ve-history-2-0-call-iv"],["source_ids",{"$list":["ve-history-2-0-call-iv-source-0"]}]'
    ']},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-histo'
    'ry-2-0-call-quote"],["source_ids",{"$list":["ve-history-2-0-call-quote-source-0"]}]]},{"$map":[['
    '"normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-0-call-r'
    'eference"],["source_ids",{"$list":["ve-history-2-0-call-reference-source-0"]}]]},{"$map":[["norm'
    'alized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-0-put-greeks"'
    '],["source_ids",{"$list":["ve-history-2-0-put-greeks-source-0"]}]]},{"$map":[["normalized_at",{"'
    '$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-0-put-iv"],["source_ids",{'
    '"$list":["ve-history-2-0-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-0'
    '2T15:30:00.000002Z"}],["record_id","ve-history-2-0-put-quote"],["source_ids",{"$list":["ve-histo'
    'ry-2-0-put-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0000'
    '02Z"}],["record_id","ve-history-2-0-put-reference"],["source_ids",{"$list":["ve-history-2-0-put-'
    'reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],'
    '["record_id","ve-history-2-underlying"],["source_ids",{"$list":["ve-history-2-underlying-source-'
    '0"]}]]}]}],["methodology_id","nearest-observed-delta-wing-tail-relative-pricing"],["methodology_'
    'version","v0.2"],["parameters_json","{\\"$map\\":[[\\"analytics_methodology\\",{\\"$map\\":[[\\"greeks_'
    'dividend_input_description\\",\\"Synthetic dividend input\\"],[\\"greeks_model_name\\",\\"Synthetic Bl'
    'ack-Scholes\\"],[\\"greeks_model_version\\",\\"fixture-v1\\"],[\\"greeks_rate_input_description\\",\\"Sy'
    'nthetic USD curve input\\"],[\\"greeks_unit_convention\\",\\"Contract-defined canonical units\\"],[\\"'
    'iv_dividend_input_description\\",\\"Synthetic dividend input\\"],[\\"iv_model_name\\",\\"Synthetic Bla'
    'ck-Scholes\\"],[\\"iv_model_version\\",\\"fixture-v1\\"],[\\"iv_rate_input_description\\",\\"Synthetic U'
    'SD curve input\\"],[\\"iv_unit_convention\\",\\"annualized_decimal_ratio\\"]]}],[\\"atm_dependency\\",{'
    '\\"$map\\":[[\\"as_of_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"calculated_at\\",{\\"$datetime\\":\\"2030-0'
    '1-02T15:30:04.000000Z\\"}],[\\"calculation_id\\",\\"calculation-3c7d\\"],[\\"calculation_type\\",\\"vola'
    'tility_environment\\"],[\\"current_atm_observations\\",{\\"$list\\":[{\\"$map\\":[[\\"candidate_pairs\\",'
    '{\\"$list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve-current-0-call-reference\\"],['
    '\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"call_iv_record_id\\",\\"ve-current-0-call-'
    'iv\\"],[\\"call_quote_record_id\\",\\"ve-current-0-call-quote\\"],[\\"contract_multiplier\\",100],[\\"cu'
    'rrency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\",{\\"$decimal\\":\\'
    '"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.300\\"}],[\\"put_contract_reference_reco'
    'rd_id\\",\\"ve-current-0-put-reference\\"],[\\"put_implied_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"'
    'put_iv_record_id\\",\\"ve-current-0-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-current-0-put-quote\\"]'
    ',[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"2030-02-01\\"}],[\\"selecte'
    'd_atm_iv\\",{\\"$decimal\\":\\"0.300\\"}],[\\"selected_call_iv_record_id\\",\\"ve-current-0-call-iv\\"],['
    '\\"selected_put_iv_record_id\\",\\"ve-current-0-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"100\\'
    '"}],[\\"session_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"tenor_days\\",30],[\\"underlying_midpoint\\",{'
    '\\"$decimal\\":\\"100.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-current-underlying\\"]]},{\\"$map\\":'
    '[[\\"candidate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve-current'
    '-1-call-reference\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.40\\"}],[\\"call_iv_record_id\\'
    '",\\"ve-current-1-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-current-1-call-quote\\"],[\\"contract_m'
    'ultiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midp'
    'oint\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.400\\"}],[\\"put_c'
    'ontract_reference_record_id\\",\\"ve-current-1-put-reference\\"],[\\"put_implied_volatility\\",{\\"$de'
    'cimal\\":\\"0.40\\"}],[\\"put_iv_record_id\\",\\"ve-current-1-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-'
    'current-1-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"203'
    '0-03-03\\"}],[\\"selected_atm_iv\\",{\\"$decimal\\":\\"0.400\\"}],[\\"selected_call_iv_record_id\\",\\"ve-'
    'current-1-call-iv\\"],[\\"selected_put_iv_record_id\\",\\"ve-current-1-put-iv\\"],[\\"selected_strike\\'
    '",{\\"$decimal\\":\\"100\\"}],[\\"session_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"tenor_days\\",60],[\\"u'
    'nderlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-current-unde'
    'rlying\\"]]}]}],[\\"historical_atm_observations\\",{\\"$list\\":[{\\"$map\\":[[\\"candidate_pairs\\",{\\"$'
    'list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve-history-0-0-call-reference\\"],[\\"'
    'call_implied_volatility\\",{\\"$decimal\\":\\"0.19\\"}],[\\"call_iv_record_id\\",\\"ve-history-0-0-call-'
    'iv\\"],[\\"call_quote_record_id\\",\\"ve-history-0-0-call-quote\\"],[\\"contract_multiplier\\",100],[\\"'
    'currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\",{\\"$decimal\\"'
    ':\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.200\\"}],[\\"put_contract_reference_re'
    'cord_id\\",\\"ve-history-0-0-put-reference\\"],[\\"put_implied_volatility\\",{\\"$decimal\\":\\"0.21\\"}]'
    ',[\\"put_iv_record_id\\",\\"ve-history-0-0-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-history-0-0-put-'
    'quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"2030-01-23\\"}],[\\'
    '"selected_atm_iv\\",{\\"$decimal\\":\\"0.200\\"}],[\\"selected_call_iv_record_id\\",\\"ve-history-0-0-ca'
    'll-iv\\"],[\\"selected_put_iv_record_id\\",\\"ve-history-0-0-put-iv\\"],[\\"selected_strike\\",{\\"$deci'
    'mal\\":\\"100\\"}],[\\"session_date\\",{\\"$date\\":\\"2029-12-24\\"}],[\\"tenor_days\\",30],[\\"underlying_'
    'midpoint\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-history-0-underlying\\"'
    ']]},{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\'
    '",\\"ve-history-1-0-call-reference\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.20\\"}],[\\"ca'
    'll_iv_record_id\\",\\"ve-history-1-0-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-history-1-0-call-qu'
    'ote\\"],[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distanc'
    'e_to_underlying_midpoint\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":'
    '\\"0.210\\"}],[\\"put_contract_reference_record_id\\",\\"ve-history-1-0-put-reference\\"],[\\"put_impli'
    'ed_volatility\\",{\\"$decimal\\":\\"0.22\\"}],[\\"put_iv_record_id\\",\\"ve-history-1-0-put-iv\\"],[\\"put'
    '_quote_record_id\\",\\"ve-history-1-0-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"exp'
    'iration\\",{\\"$date\\":\\"2030-01-26\\"}],[\\"selected_atm_iv\\",{\\"$decimal\\":\\"0.210\\"}],[\\"selected'
    '_call_iv_record_id\\",\\"ve-history-1-0-call-iv\\"],[\\"selected_put_iv_record_id\\",\\"ve-history-1-0'
    '-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"100\\"}],[\\"session_date\\",{\\"$date\\":\\"2029-12-2'
    '7\\"}],[\\"tenor_days\\",30],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying_quote'
    '_record_id\\",\\"ve-history-1-underlying\\"]]},{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\":[{\\"$map\\'
    '":[[\\"call_contract_reference_record_id\\",\\"ve-history-2-0-call-reference\\"],[\\"call_implied_vol'
    'atility\\",{\\"$decimal\\":\\"0.21\\"}],[\\"call_iv_record_id\\",\\"ve-history-2-0-call-iv\\"],[\\"call_qu'
    'ote_record_id\\",\\"ve-history-2-0-call-quote\\"],[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD'
    '\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\",{\\"$decimal\\":\\"0.0\\"}],[\\"pa'
    'ired_implied_volatility\\",{\\"$decimal\\":\\"0.220\\"}],[\\"put_contract_reference_record_id\\",\\"ve-h'
    'istory-2-0-put-reference\\"],[\\"put_implied_volatility\\",{\\"$decimal\\":\\"0.23\\"}],[\\"put_iv_recor'
    'd_id\\",\\"ve-history-2-0-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-history-2-0-put-quote\\"],[\\"stri'
    'ke\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"2030-01-29\\"}],[\\"selected_atm_iv'
    '\\",{\\"$decimal\\":\\"0.220\\"}],[\\"selected_call_iv_record_id\\",\\"ve-history-2-0-call-iv\\"],[\\"sele'
    'cted_put_iv_record_id\\",\\"ve-history-2-0-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"100\\"}],'
    '[\\"session_date\\",{\\"$date\\":\\"2029-12-30\\"}],[\\"tenor_days\\",30],[\\"underlying_midpoint\\",{\\"$d'
    'ecimal\\":\\"100.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-history-2-underlying\\"]]}]}],[\\"histor'
    'ical_median_atm_iv_float_repr\\",\\"0.21\\"],[\\"historical_observation_count\\",3],[\\"inputs\\",{\\"$l'
    'ist\\":[{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_'
    'id\\",\\"hrv-0\\"],[\\"source_ids\\",{\\"$list\\":[\\"hrv-0-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\'
    '",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"hrv-1\\"],[\\"source_ids\\",{\\"'
    '$list\\":[\\"hrv-1-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30'
    ':00.000002Z\\"}],[\\"record_id\\",\\"hrv-2\\"],[\\"source_ids\\",{\\"$list\\":[\\"hrv-2-source-0\\"]}]]},{\\'
    '"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve'
    '-current-0-call-iv\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-call-iv-source-0\\"]}]]},{\\"$map'
    '\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-curr'
    'ent-0-call-quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-call-quote-source-0\\"]}]]},{\\"$ma'
    'p\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-cur'
    'rent-0-call-reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-call-reference-source-0\\"]}]'
    ']},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\"'
    ',\\"ve-current-0-put-iv\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-put-iv-source-0\\"]}]]},{\\"$'
    'map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-c'
    'urrent-0-put-quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-put-quote-source-0\\"]}]]},{\\"$m'
    'ap\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-cu'
    'rrent-0-put-reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-put-reference-source-0\\"]}]]'
    '},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",'
    '\\"ve-current-1-call-iv\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-call-iv-source-0\\"]}]]},{\\"'
    '$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-'
    'current-1-call-quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-call-quote-source-0\\"]}]]},{\\'
    '"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve'
    '-current-1-call-reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-call-reference-source-0\\'
    '"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_'
    'id\\",\\"ve-current-1-put-iv\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-put-iv-source-0\\"]}]]},'
    '{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"'
    've-current-1-put-quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-put-quote-source-0\\"]}]]},{'
    '\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"v'
    'e-current-1-put-reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-put-reference-source-0\\"'
    ']}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_i'
    'd\\",\\"ve-current-underlying\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-underlying-source-0\\"]}]'
    ']},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\"'
    ',\\"ve-history-0-0-call-iv\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-iv-source-0\\"]}]]'
    '},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",'
    '\\"ve-history-0-0-call-quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-quote-source-0\\'
    '"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_'
    'id\\",\\"ve-history-0-0-call-reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-refere'
    'nce-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"'
    '}],[\\"record_id\\",\\"ve-history-0-0-put-iv\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-put-iv'
    '-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],'
    '[\\"record_id\\",\\"ve-history-0-0-put-quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-put-qu'
    'ote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"'
    '}],[\\"record_id\\",\\"ve-history-0-0-put-reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0'
    '-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:0'
    '0.000002Z\\"}],[\\"record_id\\",\\"ve-history-0-underlying\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-histo'
    'ry-0-underlying-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:'
    '00.000002Z\\"}],[\\"record_id\\",\\"ve-history-1-0-call-iv\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-histo'
    'ry-1-0-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:0'
    '0.000002Z\\"}],[\\"record_id\\",\\"ve-history-1-0-call-quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-his'
    'tory-1-0-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15'
    ':30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-1-0-call-reference\\"],[\\"source_ids\\",{\\"$list\\":'
    '[\\"ve-history-1-0-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"'
    '2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-1-0-put-iv\\"],[\\"source_ids\\",{\\"$li'
    'st\\":[\\"ve-history-1-0-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"203'
    '0-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-1-0-put-quote\\"],[\\"source_ids\\",{\\"$li'
    'st\\":[\\"ve-history-1-0-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"'
    '2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-1-0-put-reference\\"],[\\"source_ids\\"'
    ',{\\"$list\\":[\\"ve-history-1-0-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$da'
    'tetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-1-underlying\\"],[\\"source'
    '_ids\\",{\\"$list\\":[\\"ve-history-1-underlying-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$d'
    'atetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-2-0-call-iv\\"],[\\"source'
    '_ids\\",{\\"$list\\":[\\"ve-history-2-0-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$da'
    'tetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-2-0-call-quote\\"],[\\"sour'
    'ce_ids\\",{\\"$list\\":[\\"ve-history-2-0-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{'
    '\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-2-0-call-reference\\"'
    '],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-0-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"norm'
    'alized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-2-0-put'
    '-iv\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-0-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normali'
    'zed_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-2-0-put-qu'
    'ote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-0-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"norm'
    'alized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-history-2-0-put'
    '-reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-0-put-reference-source-0\\"]}]]},{\\"$map'
    '\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"ve-hist'
    'ory-2-underlying\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-underlying-source-0\\"]}]]}]}],[\\"'
    'iv_percentile_float_repr\\",\\"1.0\\"],[\\"matched_realized_volatility_float_repr\\",\\"0.332875693388'
    '8896\\"],[\\"matched_realized_window_days\\",30],[\\"methodology_id\\",\\"paired-atm-volatility-enviro'
    'nment\\"],[\\"methodology_version\\",\\"v0.2\\"],[\\"parameters_json\\",\\"{\\\\\\"$map\\\\\\":[[\\\\\\"atm_candi'
    'date_universe\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"completeness_semantics\\\\\\",\\\\\\"no_eligible_paired_call_put'
    '_strike_omitted\\\\\\"],[\\\\\\"declared_complete\\\\\\",true],[\\\\\\"scope\\\\\\",\\\\\\"all_exact_selected_sess'
    'ion_expiration_universes\\\\\\"]]}],[\\\\\\"atm_selection_rule\\\\\\",\\\\\\"nearest_paired_call_put_strike_'
    'to_underlying_bid_ask_midpoint\\\\\\"],[\\\\\\"call_put_combination_rule\\\\\\",\\\\\\"arithmetic_mean_of_sa'
    'me_strike_call_and_put_implied_volatility\\\\\\"],[\\\\\\"current_observations\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\'
    '\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference'
    '_record_id\\\\\\",\\\\\\"ve-current-0-call-reference\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decim'
    'al\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"call_iv_record_id\\\\\\",\\\\\\"ve-current-0-call-iv\\\\\\"],[\\\\\\"call_quote_r'
    'ecord_id\\\\\\",\\\\\\"ve-current-0-call-quote\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\'
    '",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_underlying_midpoint\\\\\\",{\\\\\\"$deci'
    'mal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.300\\\\\\"}],[\\\\\\"'
    'put_contract_reference_record_id\\\\\\",\\\\\\"ve-current-0-put-reference\\\\\\"],[\\\\\\"put_implied_volati'
    'lity\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.30\\\\\\"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"ve-current-0-put-iv\\\\\\"]'
    ',[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"ve-current-0-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":'
    '\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-02-01\\\\\\"}],[\\\\\\"selected_atm_iv\\'
    '\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.300\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-current-0-call-'
    'iv\\\\\\"],[\\\\\\"selected_put_iv_record_id\\\\\\",\\\\\\"ve-current-0-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\"'
    ',{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"'
    'tenor_days\\\\\\",30],[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlyin'
    'g_quote_record_id\\\\\\",\\\\\\"ve-current-underlying\\\\\\"]]},{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{'
    '\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference_record_id\\\\\\",\\\\\\"ve-current-1-call-r'
    'eference\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\"}],[\\\\\\"call_iv_rec'
    'ord_id\\\\\\",\\\\\\"ve-current-1-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"ve-current-1-call-quo'
    'te\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\"'
    ',null],[\\\\\\"distance_to_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_impl'
    'ied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.400\\\\\\"}],[\\\\\\"put_contract_reference_record_id\\\\\\",\\'
    '\\\\"ve-current-1-put-reference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.40\\\\\\'
    '"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"ve-current-1-put-iv\\\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"ve-c'
    'urrent-1-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"expiration\\\\\\"'
    ',{\\\\\\"$date\\\\\\":\\\\\\"2030-03-03\\\\\\"}],[\\\\\\"selected_atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.400\\\\\\"}],'
    '[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-current-1-call-iv\\\\\\"],[\\\\\\"selected_put_iv_record_id'
    '\\\\\\",\\\\\\"ve-current-1-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"'
    'session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"tenor_days\\\\\\",60],[\\\\\\"underlying_mid'
    'point\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"ve-current-u'
    'nderlying\\\\\\"]]}]}],[\\\\\\"float_conversion_rule\\\\\\",\\\\\\"convert_only_final_decimal_research_value'
    's_to_finite_float\\\\\\"],[\\\\\\"historical_expected_session_dates\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$date\\\\\\"'
    ':\\\\\\"2029-12-24\\\\\\"},{\\\\\\"$date\\\\\\":\\\\\\"2029-12-27\\\\\\"},{\\\\\\"$date\\\\\\":\\\\\\"2029-12-30\\\\\\"}]}],[\\'
    '\\\\"historical_matched_tenor_rule\\\\\\",\\\\\\"expiration_minus_session_date_calendar_days_equals_refe'
    'rence_tenor\\\\\\"],[\\\\\\"historical_observation_count\\\\\\",3],[\\\\\\"historical_observations\\\\\\",{\\\\\\"'
    '$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_cont'
    'ract_reference_record_id\\\\\\",\\\\\\"ve-history-0-0-call-reference\\\\\\"],[\\\\\\"call_implied_volatility'
    '\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.19\\\\\\"}],[\\\\\\"call_iv_record_id\\\\\\",\\\\\\"ve-history-0-0-call-iv\\\\\\"]'
    ',[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"ve-history-0-0-call-quote\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",1'
    '00],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_underlying_mid'
    'point\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\'
    '\\\\"0.200\\\\\\"}],[\\\\\\"put_contract_reference_record_id\\\\\\",\\\\\\"ve-history-0-0-put-reference\\\\\\"],['
    '\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.21\\\\\\"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"ve'
    '-history-0-0-put-iv\\\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"ve-history-0-0-put-quote\\\\\\"],[\\\\\\"str'
    'ike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-23\\\\'
    '\\"}],[\\\\\\"selected_atm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.200\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\'
    '\\\\",\\\\\\"ve-history-0-0-call-iv\\\\\\"],[\\\\\\"selected_put_iv_record_id\\\\\\",\\\\\\"ve-history-0-0-put-iv'
    '\\\\\\"],[\\\\\\"selected_strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\'
    '\\\\":\\\\\\"2029-12-24\\\\\\"}],[\\\\\\"tenor_days\\\\\\",30],[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":'
    '\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying_quote_record_id\\\\\\",\\\\\\"ve-history-0-underlying\\\\\\"]]},{\\\\\\"$map'
    '\\\\\\":[[\\\\\\"candidate_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference_recor'
    'd_id\\\\\\",\\\\\\"ve-history-1-0-call-reference\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\'
    '\\":\\\\\\"0.20\\\\\\"}],[\\\\\\"call_iv_record_id\\\\\\",\\\\\\"ve-history-1-0-call-iv\\\\\\"],[\\\\\\"call_quote_rec'
    'ord_id\\\\\\",\\\\\\"ve-history-1-0-call-quote\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\'
    '",\\\\\\"USD\\\\\\"],[\\\\\\"deliverable_id\\\\\\",null],[\\\\\\"distance_to_underlying_midpoint\\\\\\",{\\\\\\"$deci'
    'mal\\\\\\":\\\\\\"0.0\\\\\\"}],[\\\\\\"paired_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.210\\\\\\"}],[\\\\\\"'
    'put_contract_reference_record_id\\\\\\",\\\\\\"ve-history-1-0-put-reference\\\\\\"],[\\\\\\"put_implied_vola'
    'tility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.22\\\\\\"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"ve-history-1-0-put-iv\\'
    '\\\\"],[\\\\\\"put_quote_record_id\\\\\\",\\\\\\"ve-history-1-0-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decima'
    'l\\\\\\":\\\\\\"100\\\\\\"}]]}]}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-26\\\\\\"}],[\\\\\\"selected_a'
    'tm_iv\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.210\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-history-1'
    '-0-call-iv\\\\\\"],[\\\\\\"selected_put_iv_record_id\\\\\\",\\\\\\"ve-history-1-0-put-iv\\\\\\"],[\\\\\\"selected_'
    'strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-27\\\\'
    '\\"}],[\\\\\\"tenor_days\\\\\\",30],[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\'
    '"underlying_quote_record_id\\\\\\",\\\\\\"ve-history-1-underlying\\\\\\"]]},{\\\\\\"$map\\\\\\":[[\\\\\\"candidate'
    '_pairs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"call_contract_reference_record_id\\\\\\",\\\\\\"ve-hist'
    'ory-2-0-call-reference\\\\\\"],[\\\\\\"call_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.21\\\\\\"}],[\\'
    '\\\\"call_iv_record_id\\\\\\",\\\\\\"ve-history-2-0-call-iv\\\\\\"],[\\\\\\"call_quote_record_id\\\\\\",\\\\\\"ve-hi'
    'story-2-0-call-quote\\\\\\"],[\\\\\\"contract_multiplier\\\\\\",100],[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"'
    'deliverable_id\\\\\\",null],[\\\\\\"distance_to_underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.0\\\\\\"}'
    '],[\\\\\\"paired_implied_volatility\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"0.220\\\\\\"}],[\\\\\\"put_contract_referen'
    'ce_record_id\\\\\\",\\\\\\"ve-history-2-0-put-reference\\\\\\"],[\\\\\\"put_implied_volatility\\\\\\",{\\\\\\"$dec'
    'imal\\\\\\":\\\\\\"0.23\\\\\\"}],[\\\\\\"put_iv_record_id\\\\\\",\\\\\\"ve-history-2-0-put-iv\\\\\\"],[\\\\\\"put_quote_'
    'record_id\\\\\\",\\\\\\"ve-history-2-0-put-quote\\\\\\"],[\\\\\\"strike\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"}]]'
    '}]}],[\\\\\\"expiration\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2030-01-29\\\\\\"}],[\\\\\\"selected_atm_iv\\\\\\",{\\\\\\"$deci'
    'mal\\\\\\":\\\\\\"0.220\\\\\\"}],[\\\\\\"selected_call_iv_record_id\\\\\\",\\\\\\"ve-history-2-0-call-iv\\\\\\"],[\\\\\\'
    '"selected_put_iv_record_id\\\\\\",\\\\\\"ve-history-2-0-put-iv\\\\\\"],[\\\\\\"selected_strike\\\\\\",{\\\\\\"$dec'
    'imal\\\\\\":\\\\\\"100\\\\\\"}],[\\\\\\"session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-30\\\\\\"}],[\\\\\\"tenor_days'
    '\\\\\\",30],[\\\\\\"underlying_midpoint\\\\\\",{\\\\\\"$decimal\\\\\\":\\\\\\"100.0\\\\\\"}],[\\\\\\"underlying_quote_re'
    'cord_id\\\\\\",\\\\\\"ve-history-2-underlying\\\\\\"]]}]}],[\\\\\\"historical_sample_semantics\\\\\\",\\\\\\"calle'
    'r_declared_observation_sample\\\\\\"],[\\\\\\"iv_methodology\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"dividend_input_de'
    'scription\\\\\\",\\\\\\"Synthetic dividend input\\\\\\"],[\\\\\\"model_name\\\\\\",\\\\\\"Synthetic Black-Scholes\\'
    '\\\\"],[\\\\\\"model_version\\\\\\",\\\\\\"fixture-v1\\\\\\"],[\\\\\\"rate_input_description\\\\\\",\\\\\\"Synthetic US'
    'D curve input\\\\\\"],[\\\\\\"unit_convention\\\\\\",\\\\\\"annualized_decimal_ratio\\\\\\"]]}],[\\\\\\"median_for'
    'mula\\\\\\",\\\\\\"odd_middle_even_arithmetic_mean_of_two_middle_values\\\\\\"],[\\\\\\"normalized_evidence\\'
    '\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"direct_inputs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",'
    '{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"'
    '$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-call-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied'
    '_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-call-iv-source-0\\\\\\"]}]]},'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],['
    '\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-call-qu'
    'ote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-'
    '0-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030'
    '-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_'
    'id\\\\\\",\\\\\\"ve-current-0-call-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\'
    '\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\"'
    ':[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagate'
    'd_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-put-iv\\\\\\"],[\\\\\\"rol'
    'e\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-pu'
    't-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T1'
    '5:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\'
    '\\\\"ve-current-0-put-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$lis'
    't\\\\\\":[\\\\\\"ve-current-0-put-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$'
    'datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\'
    '\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-0-put-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contrac'
    't_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-0-put-reference-source-0\\\\\\"'
    ']}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\'
    '\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-c'
    'all-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":'
    '[\\\\\\"ve-current-1-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime'
    '\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}]'
    ',[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-call-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"so'
    'urce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"n'
    'ormalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_qualit'
    'y_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-call-reference\\\\\\"],[\\\\\\"rol'
    'e\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-ca'
    'll-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030'
    '-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_'
    'id\\\\\\",\\\\\\"ve-current-1-put-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source'
    '_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalize'
    'd_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\'
    '\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-put-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"opt'
    'ion_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-1-put-quote-source-0\\\\\\"]}]]},'
    '{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],['
    '\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-1-put-ref'
    'erence\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":'
    '[\\\\\\"ve-current-1-put-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$da'
    'tetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\'
    '":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-current-underlying\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"underlying_quote\\\\\\"]'
    ',[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-current-underlying-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":['
    '[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_'
    'quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-call-iv\\\\\\"],[\\\\\\"ro'
    'le\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0'
    '-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-'
    '02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\'
    '\\",\\\\\\"ve-history-0-0-call-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\'
    '\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\'
    '\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{'
    '\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-call-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"o'
    'ption_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-call-refere'
    'nce-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15'
    ':30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\'
    '\\"ve-history-0-0-put-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\'
    '",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\'
    '\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{'
    '\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-put-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option'
    '_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-0-put-quote-source-0\\\\\\"]}]]},{'
    '\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\'
    '\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-0-put-re'
    'ference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\"'
    ':[\\\\\\"ve-history-0-0-put-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"'
    '$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list'
    '\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-0-underlying\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"underlying_quote'
    '\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-0-underlying-source-0\\\\\\"]}]]},{\\\\\\"$ma'
    'p\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"prop'
    'agated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-call-iv\\\\\\"],'
    '[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-hist'
    'ory-1-0-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2'
    '030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"reco'
    'rd_id\\\\\\",\\\\\\"ve-history-1-0-call-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids'
    '\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normali'
    'zed_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flag'
    's\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-call-reference\\\\\\"],[\\\\\\"role\\\\\\'
    '",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-call'
    '-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-0'
    '1-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id'
    '\\\\\\",\\\\\\"ve-history-1-0-put-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source'
    '_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normali'
    'zed_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flag'
    's\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0-put-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\'
    '"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-0-put-quote-source-0\\\\\\"'
    ']}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\'
    '\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-0'
    '-put-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$l'
    'ist\\\\\\":[\\\\\\"ve-history-1-0-put-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\'
    '",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\'
    '\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-1-underlying\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"underlyin'
    'g_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-1-underlying-source-0\\\\\\"]}]]},{'
    '\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\'
    '\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-call-i'
    'v\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"'
    've-history-2-0-call-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\'
    '":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\'
    '\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-call-quote\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"sou'
    'rce_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-call-quote-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"'
    'normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quali'
    'ty_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-call-reference\\\\\\"],[\\\\\\"'
    'role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2'
    '-0-call-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\'
    '"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"re'
    'cord_id\\\\\\",\\\\\\"ve-history-2-0-put-iv\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_implied_volatility\\\\\\"],[\\\\\\'
    '"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-put-iv-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"'
    'normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quali'
    'ty_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-0-put-quote\\\\\\"],[\\\\\\"role\\'
    '\\\\",\\\\\\"option_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-put-quote-sourc'
    'e-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.00'
    '0002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-hist'
    'ory-2-0-put-reference\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"option_contract_reference\\\\\\"],[\\\\\\"source_ids\\\\\\",'
    '{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-0-put-reference-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalize'
    'd_at\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"propagated_quality_flags\\'
    '\\\\",{\\\\\\"$list\\\\\\":[]}],[\\\\\\"record_id\\\\\\",\\\\\\"ve-history-2-underlying\\\\\\"],[\\\\\\"role\\\\\\",\\\\\\"un'
    'derlying_quote\\\\\\"],[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"ve-history-2-underlying-source-0\\\\\\"'
    ']}]]}]}]]}],[\\\\\\"percentile_formula\\\\\\",\\\\\\"inclusive_count_historical_atm_iv_lte_current_refere'
    'nce_atm_iv_divided_by_count\\\\\\"],[\\\\\\"realized_volatility_dependency\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"adj'
    'ustment_methodology\\\\\\",null],[\\\\\\"annualization_sessions_per_year\\\\\\",252],[\\\\\\"annualized_real'
    'ized_volatility_float_repr\\\\\\",\\\\\\"0.3328756933888896\\\\\\"],[\\\\\\"calculated_at\\\\\\",{\\\\\\"$datetime'
    '\\\\\\":\\\\\\"2030-01-02T15:30:04.000000Z\\\\\\"}],[\\\\\\"calculation_id\\\\\\",\\\\\\"calculation-3c7c\\\\\\"],[\\\\'
    '\\"calculation_type\\\\\\",\\\\\\"historical_realized_volatility\\\\\\"],[\\\\\\"end_session_date\\\\\\",{\\\\\\"$d'
    'ate\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"inputs\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\\\'
    '\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"hrv-0\\\\\\"],[\\'
    '\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"hrv-0-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at\\'
    '\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"hrv-1\\\\\\"],['
    '\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"hrv-1-source-0\\\\\\"]}]]},{\\\\\\"$map\\\\\\":[[\\\\\\"normalized_at'
    '\\\\\\",{\\\\\\"$datetime\\\\\\":\\\\\\"2030-01-02T15:30:00.000002Z\\\\\\"}],[\\\\\\"record_id\\\\\\",\\\\\\"hrv-2\\\\\\"],'
    '[\\\\\\"source_ids\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\"hrv-2-source-0\\\\\\"]}]]}]}],[\\\\\\"log_returns\\\\\\",{\\\\\\"$li'
    'st\\\\\\":[{\\\\\\"$decimal\\\\\\":\\\\\\"0.01980262729617971302602906688510039\\\\\\"},{\\\\\\"$decimal\\\\\\":\\\\\\"-'
    '0.009852296443011630177813709340839653\\\\\\"}]}],[\\\\\\"methodology_id\\\\\\",\\\\\\"historical-log-return'
    '-sample-realized-volatility\\\\\\"],[\\\\\\"methodology_version\\\\\\",\\\\\\"v0.1\\\\\\"],[\\\\\\"parameters_json'
    '\\\\\\",\\\\\\"{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"adjustment_methodology\\\\\\\\\\\\\\",null],[\\\\\\\\\\\\\\"annualiza'
    'tion_rule\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"daily_sample_standard_deviation_times_square_root_sessions_per_year\\\\\\'
    '\\\\\\\\"],[\\\\\\\\\\\\\\"annualization_sessions_per_year\\\\\\\\\\\\\\",252],[\\\\\\\\\\\\\\"expected_session_dates\\\\\\\\'
    '\\\\\\",{\\\\\\\\\\\\\\"$list\\\\\\\\\\\\\\":[{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2029-12-03\\\\\\\\\\\\\\"},{\\\\\\\\\\\\\\"$date\\\\'
    '\\\\\\\\\\":\\\\\\\\\\\\\\"2029-12-18\\\\\\\\\\\\\\"},{\\\\\\\\\\\\\\"$date\\\\\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02\\\\\\\\\\\\\\"}]}],[\\\\\\\\\\\\'
    '\\"price_basis\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"raw_close\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"price_observation_count\\\\\\\\\\\\\\",3],[\\\\'
    '\\\\\\\\\\"price_unit\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"usd_per_underlying_share\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"return_association_r'
    'ule\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ending_session\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"return_formula\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"natural_log_'
    'price_ratio\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"return_observation_count\\\\\\\\\\\\\\",2],[\\\\\\\\\\\\\\"return_unit\\\\\\\\\\\\\\",\\'
    '\\\\\\\\\\\\"decimal_ratio\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"underlying\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$map\\\\\\\\\\\\\\":[[\\\\\\\\\\\\\\"curren'
    'cy\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"USD\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"listing_mic\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"ARCX\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"secu'
    'rity_type\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"etf\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"symbol\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"SPY\\\\\\\\\\\\\\"]]}],[\\\\\\\\\\\\\\"'
    'variance_estimator\\\\\\\\\\\\\\",\\\\\\\\\\\\\\"sample_variance\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"volatility_unit\\\\\\\\\\\\\\",\\\\\\'
    '\\\\\\\\"annualized_decimal_ratio\\\\\\\\\\\\\\"],[\\\\\\\\\\\\\\"window_end_session_date\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\'
    '\\\\\\\\\\":\\\\\\\\\\\\\\"2030-01-02\\\\\\\\\\\\\\"}],[\\\\\\\\\\\\\\"window_start_session_date\\\\\\\\\\\\\\",{\\\\\\\\\\\\\\"$date\\\\\\'
    '\\\\\\\\":\\\\\\\\\\\\\\"2029-12-03\\\\\\\\\\\\\\"}]]}\\\\\\"],[\\\\\\"price_basis\\\\\\",\\\\\\"raw_close\\\\\\"],[\\\\\\"price_obs'
    'ervation_count\\\\\\",3],[\\\\\\"prices\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$decimal\\\\\\":\\\\\\"100\\\\\\"},{\\\\\\"$decim'
    'al\\\\\\":\\\\\\"102\\\\\\"},{\\\\\\"$decimal\\\\\\":\\\\\\"101\\\\\\"}]}],[\\\\\\"quality_flags\\\\\\",{\\\\\\"$list\\\\\\":[\\\\\\'
    '"decimal_to_float_converted\\\\\\",\\\\\\"annualized\\\\\\",\\\\\\"assumption_applied\\\\\\"]}],[\\\\\\"return_for'
    'mula\\\\\\",\\\\\\"natural_log_price_ratio\\\\\\"],[\\\\\\"return_observation_count\\\\\\",2],[\\\\\\"session_date'
    's\\\\\\",{\\\\\\"$list\\\\\\":[{\\\\\\"$date\\\\\\":\\\\\\"2029-12-03\\\\\\"},{\\\\\\"$date\\\\\\":\\\\\\"2029-12-18\\\\\\"},{\\\\\\'
    '"$date\\\\\\":\\\\\\"2030-01-02\\\\\\"}]}],[\\\\\\"start_session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-03\\\\\\"}'
    '],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":[[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARC'
    'X\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"variance_estimat'
    'or\\\\\\",\\\\\\"sample_variance\\\\\\"]]}],[\\\\\\"realized_window_matching_rule\\\\\\",\\\\\\"realized_end_equal'
    's_current_as_of_and_calendar_span_equals_reference_tenor\\\\\\"],[\\\\\\"reference_tenor_days\\\\\\",30],'
    '[\\\\\\"strike_tie_rule\\\\\\",\\\\\\"lower_strike\\\\\\"],[\\\\\\"term_tenor_rule\\\\\\",\\\\\\"expiration_minus_ses'
    'sion_date_calendar_days\\\\\\"],[\\\\\\"underlying_midpoint_rule\\\\\\",\\\\\\"bid_ask_midpoint_no_last_fall'
    'back\\\\\\"],[\\\\\\"volatility_unit\\\\\\",\\\\\\"annualized_decimal_ratio\\\\\\"]]}\\"],[\\"quality_flags\\",{\\"'
    '$list\\":[\\"decimal_to_float_converted\\",\\"annualized\\",\\"assumption_applied\\"]}],[\\"reference_te'
    'nor_days\\",30],[\\"term_points\\",{\\"$list\\":[{\\"$map\\":[[\\"atm_iv_float_repr\\",\\"0.3\\"],[\\"tenor_'
    'days\\",30]]},{\\"$map\\":[[\\"atm_iv_float_repr\\",\\"0.4\\"],[\\"tenor_days\\",60]]}]}],[\\"underlying\\"'
    ',\\"SPY\\"]]}],[\\"candidate_universe\\",{\\"$map\\":[[\\"current_semantics\\",\\"no_eligible_nearest_sig'
    'ned_delta_candidate_omitted\\"],[\\"declared_complete\\",true],[\\"historical_semantics\\",\\"no_eligi'
    'ble_paired_atm_or_nearest_signed_delta_candidate_omitted\\"],[\\"scope\\",\\"current_delta_and_histo'
    'rical_atm_and_delta_candidate_universes\\"]]}],[\\"current_expiration_observations\\",{\\"$list\\":[{'
    '\\"$map\\":[[\\"atm_dependency_selected_call_iv_record_id\\",\\"ve-current-0-call-iv\\"],[\\"atm_depend'
    'ency_selected_put_iv_record_id\\",\\"ve-current-0-put-iv\\"],[\\"atm_iv\\",{\\"$decimal\\":\\"0.300\\"}],'
    '[\\"candidate_contracts\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_refere'
    'nce_record_id\\",\\"ve-current-0-call-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null'
    '],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\'
    '"0.25\\"}],[\\"greeks_record_id\\",\\"ve-current-0-call-greeks\\"],[\\"implied_volatility\\",{\\"$decima'
    'l\\":\\"0.30\\"}],[\\"iv_record_id\\",\\"ve-current-0-call-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_r'
    'ecord_id\\",\\"ve-current-0-call-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.50\\"}],[\\"strike\\",{'
    '\\"$decimal\\":\\"100\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_i'
    'd\\",\\"tail-current-30-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"di'
    'stance_to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.01\\"'
    '}],[\\"greeks_record_id\\",\\"tail-current-30-call25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\'
    '":\\"0.28\\"}],[\\"iv_record_id\\",\\"tail-current-30-call25-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quot'
    'e_record_id\\",\\"tail-current-30-call25-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"st'
    'rike\\",{\\"$decimal\\":\\"105\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_'
    'record_id\\",\\"tail-current-30-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",nul'
    'l],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":'
    '\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-current-30-call10-greeks\\"],[\\"implied_volatility\\",{\\"$'
    'decimal\\":\\"0.26\\"}],[\\"iv_record_id\\",\\"tail-current-30-call10-iv\\"],[\\"option_type\\",\\"call\\"]'
    ',[\\"quote_record_id\\",\\"tail-current-30-call10-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.11\\"'
    '}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_re'
    'ference_record_id\\",\\"tail-current-30-put10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_i'
    'd\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance_to_25_target\\",{\\"$dec'
    'imal\\":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-current-30-put10-greeks\\"],[\\"implied_volatility\\'
    '",{\\"$decimal\\":\\"0.42\\"}],[\\"iv_record_id\\",\\"tail-current-30-put10-iv\\"],[\\"option_type\\",\\"pu'
    't\\"],[\\"quote_record_id\\",\\"tail-current-30-put10-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.'
    '11\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract'
    '_reference_record_id\\",\\"tail-current-30-put25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverabl'
    'e_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$'
    'decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-current-30-put25-greeks\\"],[\\"implied_volatili'
    'ty\\",{\\"$decimal\\":\\"0.36\\"}],[\\"iv_record_id\\",\\"tail-current-30-put25-iv\\"],[\\"option_type\\",\\'
    '"put\\"],[\\"quote_record_id\\",\\"tail-current-30-put25-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"'
    '-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contr'
    'act_reference_record_id\\",\\"ve-current-0-put-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_'
    'id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$de'
    'cimal\\":\\"0.25\\"}],[\\"greeks_record_id\\",\\"ve-current-0-put-greeks\\"],[\\"implied_volatility\\",{\\'
    '"$decimal\\":\\"0.30\\"}],[\\"iv_record_id\\",\\"ve-current-0-put-iv\\"],[\\"option_type\\",\\"put\\"],[\\"q'
    'uote_record_id\\",\\"ve-current-0-put-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.50\\"}],[\\"stri'
    'ke\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"downside_25_delta_skew\\",{\\"$decimal\\":\\"0.060\\"}],[\\"downs'
    'ide_wing_curvature\\",{\\"$decimal\\":\\"0.06\\"}],[\\"expiration\\",{\\"$date\\":\\"2030-02-01\\"}],[\\"his'
    'torical_observation_count\\",3],[\\"selected_call_10\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\'
    '"contract_reference_record_id\\",\\"tail-current-30-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"'
    'deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-curre'
    'nt-30-call10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.26\\"}],[\\"iv_record_id\\",\\"tail'
    '-current-30-call10-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-current-30-call1'
    '0-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}],[\\"t'
    'arget_delta\\",{\\"$decimal\\":\\"0.10\\"}]]}],[\\"selected_call_25\\",{\\"$map\\":[[\\"contract_multiplie'
    'r\\",100],[\\"contract_reference_record_id\\",\\"tail-current-30-call25-reference\\"],[\\"currency\\",\\'
    '"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\'
    '"tail-current-30-call25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.28\\"}],[\\"iv_record_'
    'id\\",\\"tail-current-30-call25-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-curre'
    'nt-30-call25-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"1'
    '05\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"0.25\\"}]]}],[\\"selected_put_10\\",{\\"$map\\":[[\\"contract'
    '_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-current-30-put10-reference\\"],[\\"cur'
    'rency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_reco'
    'rd_id\\",\\"tail-current-30-put10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.42\\"}],[\\"iv'
    '_record_id\\",\\"tail-current-30-put10-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail'
    '-current-30-put10-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"-0.11\\"}],[\\"strike\\",{\\"$decimal'
    '\\":\\"90\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.10\\"}]]}],[\\"selected_put_25\\",{\\"$map\\":[[\\"co'
    'ntract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-current-30-put25-reference\\"],'
    '[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greek'
    's_record_id\\",\\"tail-current-30-put25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.36\\"}]'
    ',[\\"iv_record_id\\",\\"tail-current-30-put25-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",'
    '\\"tail-current-30-put25-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$d'
    'ecimal\\":\\"95\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.25\\"}]]}],[\\"session_date\\",{\\"$date\\":\\"'
    '2030-01-02\\"}],[\\"skew_percentile\\",{\\"$decimal\\":\\"0.6666666666666666666666666666666667\\"}],[\\"'
    'tenor_days\\",30],[\\"underlying_quote_record_id\\",\\"ve-current-underlying\\"],[\\"upside_25_delta_s'
    'kew\\",{\\"$decimal\\":\\"-0.020\\"}],[\\"upside_wing_curvature\\",{\\"$decimal\\":\\"-0.02\\"}]]},{\\"$map\\'
    '":[[\\"atm_dependency_selected_call_iv_record_id\\",\\"ve-current-1-call-iv\\"],[\\"atm_dependency_se'
    'lected_put_iv_record_id\\",\\"ve-current-1-put-iv\\"],[\\"atm_iv\\",{\\"$decimal\\":\\"0.400\\"}],[\\"cand'
    'idate_contracts\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_rec'
    'ord_id\\",\\"ve-current-1-call-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"di'
    'stance_to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.25\\"'
    '}],[\\"greeks_record_id\\",\\"ve-current-1-call-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0'
    '.40\\"}],[\\"iv_record_id\\",\\"ve-current-1-call-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_i'
    'd\\",\\"ve-current-1-call-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.50\\"}],[\\"strike\\",{\\"$deci'
    'mal\\":\\"100\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"t'
    'ail-current-60-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_'
    'to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"g'
    'reeks_record_id\\",\\"tail-current-60-call25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.3'
    '8\\"}],[\\"iv_record_id\\",\\"tail-current-60-call25-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_recor'
    'd_id\\",\\"tail-current-60-call25-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"strike\\",'
    '{\\"$decimal\\":\\"105\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_'
    'id\\",\\"tail-current-60-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"d'
    'istance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.14\\'
    '"}],[\\"greeks_record_id\\",\\"tail-current-60-call10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal'
    '\\":\\"0.36\\"}],[\\"iv_record_id\\",\\"tail-current-60-call10-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quo'
    'te_record_id\\",\\"tail-current-60-call10-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.11\\"}],[\\"s'
    'trike\\",{\\"$decimal\\":\\"110\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference'
    '_record_id\\",\\"tail-current-60-put10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",nul'
    'l],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":'
    '\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-current-60-put10-greeks\\"],[\\"implied_volatility\\",{\\"$d'
    'ecimal\\":\\"0.52\\"}],[\\"iv_record_id\\",\\"tail-current-60-put10-iv\\"],[\\"option_type\\",\\"put\\"],[\\'
    '"quote_record_id\\",\\"tail-current-60-put10-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.11\\"}],'
    '[\\"strike\\",{\\"$decimal\\":\\"90\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_refere'
    'nce_record_id\\",\\"tail-current-60-put25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",'
    'null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$decimal'
    '\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-current-60-put25-greeks\\"],[\\"implied_volatility\\",{\\'
    '"$decimal\\":\\"0.46\\"}],[\\"iv_record_id\\",\\"tail-current-60-put25-iv\\"],[\\"option_type\\",\\"put\\"]'
    ',[\\"quote_record_id\\",\\"tail-current-60-put25-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.24\\"'
    '}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_ref'
    'erence_record_id\\",\\"ve-current-1-put-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",nu'
    'll],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\"'
    ':\\"0.25\\"}],[\\"greeks_record_id\\",\\"ve-current-1-put-greeks\\"],[\\"implied_volatility\\",{\\"$decim'
    'al\\":\\"0.40\\"}],[\\"iv_record_id\\",\\"ve-current-1-put-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_re'
    'cord_id\\",\\"ve-current-1-put-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.50\\"}],[\\"strike\\",{\\'
    '"$decimal\\":\\"100\\"}]]}]}],[\\"downside_25_delta_skew\\",{\\"$decimal\\":\\"0.060\\"}],[\\"downside_win'
    'g_curvature\\",{\\"$decimal\\":\\"0.06\\"}],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"historical'
    '_observation_count\\",3],[\\"selected_call_10\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contra'
    'ct_reference_record_id\\",\\"tail-current-60-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliver'
    'able_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-current-60-c'
    'all10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.36\\"}],[\\"iv_record_id\\",\\"tail-curren'
    't-60-call10-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-current-60-call10-quote'
    '\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}],[\\"target_d'
    'elta\\",{\\"$decimal\\":\\"0.10\\"}]]}],[\\"selected_call_25\\",{\\"$map\\":[[\\"contract_multiplier\\",100'
    '],[\\"contract_reference_record_id\\",\\"tail-current-60-call25-reference\\"],[\\"currency\\",\\"USD\\"]'
    ',[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-c'
    'urrent-60-call25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.38\\"}],[\\"iv_record_id\\",\\"'
    'tail-current-60-call25-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-current-60-c'
    'all25-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"105\\"}],'
    '[\\"target_delta\\",{\\"$decimal\\":\\"0.25\\"}]]}],[\\"selected_put_10\\",{\\"$map\\":[[\\"contract_multip'
    'lier\\",100],[\\"contract_reference_record_id\\",\\"tail-current-60-put10-reference\\"],[\\"currency\\"'
    ',\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\"'
    ',\\"tail-current-60-put10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.52\\"}],[\\"iv_record'
    '_id\\",\\"tail-current-60-put10-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-curren'
    't-60-put10-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"-0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"90'
    '\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.10\\"}]]}],[\\"selected_put_25\\",{\\"$map\\":[[\\"contract_'
    'multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-current-60-put25-reference\\"],[\\"curr'
    'ency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_recor'
    'd_id\\",\\"tail-current-60-put25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.46\\"}],[\\"iv_'
    'record_id\\",\\"tail-current-60-put25-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-'
    'current-60-put25-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\'
    '":\\"95\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.25\\"}]]}],[\\"session_date\\",{\\"$date\\":\\"2030-01'
    '-02\\"}],[\\"skew_percentile\\",{\\"$decimal\\":\\"0.6666666666666666666666666666666667\\"}],[\\"tenor_d'
    'ays\\",60],[\\"underlying_quote_record_id\\",\\"ve-current-underlying\\"],[\\"upside_25_delta_skew\\",{'
    '\\"$decimal\\":\\"-0.020\\"}],[\\"upside_wing_curvature\\",{\\"$decimal\\":\\"-0.02\\"}]]}]}],[\\"current_s'
    'kew_formula\\",\\"put_25_delta_iv_minus_atm_iv\\"],[\\"delta_convention\\",{\\"$map\\":[[\\"delta_basis\\'
    '",\\"spot\\"],[\\"interpolation_methodology\\",\\"none\\"],[\\"model_provider_methodology\\",\\"Synthetic'
    ' Black-Scholes provider delta\\"],[\\"premium_adjustment\\",\\"unadjusted\\"],[\\"signed_delta_convent'
    'ion\\",\\"call_positive_put_negative\\"],[\\"target_selection_methodology\\",\\"nearest_observed_signe'
    'd_delta\\"]]}],[\\"delta_point_selection_rule\\",\\"nearest_observed_signed_delta\\"],[\\"delta_tie_ru'
    'le\\",\\"reject_equal_distance_or_remaining_economic_ambiguity\\"],[\\"float_conversion_rule\\",\\"con'
    'vert_only_final_tail_pricing_record_values_to_finite_float\\"],[\\"historical_eod_semantics\\",{\\"$'
    'map\\":[[\\"declared\\",true],[\\"methodology\\",\\"Synthetic official regular-session EOD snapshot\\"]'
    ',[\\"sample_semantics\\",\\"caller_declared_daily_eod_observation_sample\\"],[\\"scope\\",\\"every_hist'
    'orical_session_and_tenor_selection\\"]]}],[\\"historical_expected_session_dates\\",{\\"$list\\":[{\\"$'
    'date\\":\\"2029-12-24\\"},{\\"$date\\":\\"2029-12-27\\"},{\\"$date\\":\\"2029-12-30\\"}]}],[\\"historical_ma'
    'tched_tenor_rule\\",\\"expiration_minus_session_date_calendar_days_equals_current_tenor\\"],[\\"hist'
    'orical_observations_by_tenor\\",{\\"$list\\":[{\\"$map\\":[[\\"current_expiration\\",{\\"$date\\":\\"2030-'
    '02-01\\"}],[\\"historical_observations\\",{\\"$list\\":[{\\"$map\\":[[\\"atm_iv\\",{\\"$decimal\\":\\"0.200\\'
    '"}],[\\"call_10_delta_iv\\",{\\"$decimal\\":\\"0.16\\"}],[\\"call_25_delta_iv\\",{\\"$decimal\\":\\"0.18\\"}'
    '],[\\"candidate_contracts\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_refe'
    'rence_record_id\\",\\"ve-history-0-0-call-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",'
    'null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal'
    '\\":\\"0.25\\"}],[\\"greeks_record_id\\",\\"ve-history-0-0-call-greeks\\"],[\\"implied_volatility\\",{\\"$'
    'decimal\\":\\"0.19\\"}],[\\"iv_record_id\\",\\"ve-history-0-0-call-iv\\"],[\\"option_type\\",\\"call\\"],[\\'
    '"quote_record_id\\",\\"ve-history-0-0-call-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.50\\"}],[\\"'
    'strike\\",{\\"$decimal\\":\\"100\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_referenc'
    'e_record_id\\",\\"tail-history-0-30-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\"'
    ',null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$decima'
    'l\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-0-30-call25-greeks\\"],[\\"implied_volatility\\'
    '",{\\"$decimal\\":\\"0.18\\"}],[\\"iv_record_id\\",\\"tail-history-0-30-call25-iv\\"],[\\"option_type\\",\\'
    '"call\\"],[\\"quote_record_id\\",\\"tail-history-0-30-call25-quote\\"],[\\"signed_delta\\",{\\"$decimal\\'
    '":\\"0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"105\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"c'
    'ontract_reference_record_id\\",\\"tail-history-0-30-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"'
    'deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance_to_25_tar'
    'get\\",{\\"$decimal\\":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-0-30-call10-greeks\\"],[\\"imp'
    'lied_volatility\\",{\\"$decimal\\":\\"0.16\\"}],[\\"iv_record_id\\",\\"tail-history-0-30-call10-iv\\"],[\\'
    '"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-0-30-call10-quote\\"],[\\"signed_delt'
    'a\\",{\\"$decimal\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}]]},{\\"$map\\":[[\\"contract_multip'
    'lier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-0-30-put10-reference\\"],[\\"currency'
    '\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"dis'
    'tance_to_25_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-0-30-put10-gr'
    'eeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"iv_record_id\\",\\"tail-history-0-30-p'
    'ut10-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-0-30-put10-quote\\"],[\\"'
    'signed_delta\\",{\\"$decimal\\":\\"-0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}]]},{\\"$map\\":[[\\"cont'
    'ract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-0-30-put25-reference\\"],'
    '[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.14'
    '\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-0-'
    '30-put25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.24\\"}],[\\"iv_record_id\\",\\"tail-his'
    'tory-0-30-put25-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-0-30-put25-q'
    'uote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}]]},{\\"$map'
    '\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"ve-history-0-0-put-referen'
    'ce\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":'
    '\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.25\\"}],[\\"greeks_record_id\\",\\"ve-histor'
    'y-0-0-put-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.21\\"}],[\\"iv_record_id\\",\\"ve-hist'
    'ory-0-0-put-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"ve-history-0-0-put-quote\\"],['
    '\\"signed_delta\\",{\\"$decimal\\":\\"-0.50\\"}],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"downside_'
    '25_delta_skew\\",{\\"$decimal\\":\\"0.040\\"}],[\\"downside_wing_curvature\\",{\\"$decimal\\":\\"0.06\\"}],'
    '[\\"expiration\\",{\\"$date\\":\\"2030-01-23\\"}],[\\"put_10_delta_iv\\",{\\"$decimal\\":\\"0.30\\"}],[\\"put'
    '_25_delta_iv\\",{\\"$decimal\\":\\"0.24\\"}],[\\"selected_call_10\\",{\\"$map\\":[[\\"contract_multiplier\\'
    '",100],[\\"contract_reference_record_id\\",\\"tail-history-0-30-call10-reference\\"],[\\"currency\\",\\'
    '"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\'
    '"tail-history-0-30-call10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.16\\"}],[\\"iv_recor'
    'd_id\\",\\"tail-history-0-30-call10-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-h'
    'istory-0-30-call10-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal'
    '\\":\\"110\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"0.10\\"}]]}],[\\"selected_call_25\\",{\\"$map\\":[[\\"c'
    'ontract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-0-30-call25-reference'
    '\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"g'
    'reeks_record_id\\",\\"tail-history-0-30-call25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0'
    '.18\\"}],[\\"iv_record_id\\",\\"tail-history-0-30-call25-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_r'
    'ecord_id\\",\\"tail-history-0-30-call25-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"s'
    'trike\\",{\\"$decimal\\":\\"105\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"0.25\\"}]]}],[\\"selected_paired'
    '_atm_evidence\\",{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_referenc'
    'e_record_id\\",\\"ve-history-0-0-call-reference\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.'
    '19\\"}],[\\"call_iv_record_id\\",\\"ve-history-0-0-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-history'
    '-0-0-call-quote\\"],[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null'
    '],[\\"distance_to_underlying_midpoint\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\'
    '"$decimal\\":\\"0.200\\"}],[\\"put_contract_reference_record_id\\",\\"ve-history-0-0-put-reference\\"],'
    '[\\"put_implied_volatility\\",{\\"$decimal\\":\\"0.21\\"}],[\\"put_iv_record_id\\",\\"ve-history-0-0-put-'
    'iv\\"],[\\"put_quote_record_id\\",\\"ve-history-0-0-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]'
    ']}]}],[\\"selected_atm_iv\\",{\\"$decimal\\":\\"0.200\\"}],[\\"selected_call_iv_record_id\\",\\"ve-histor'
    'y-0-0-call-iv\\"],[\\"selected_put_iv_record_id\\",\\"ve-history-0-0-put-iv\\"],[\\"selected_strike\\",'
    '{\\"$decimal\\":\\"100\\"}],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}]]}],[\\"selected_put_10'
    '\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-0-3'
    '0-put10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\'
    '":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-0-30-put10-greeks\\"],[\\"implied_volatility\\",{'
    '\\"$decimal\\":\\"0.30\\"}],[\\"iv_record_id\\",\\"tail-history-0-30-put10-iv\\"],[\\"option_type\\",\\"put'
    '\\"],[\\"quote_record_id\\",\\"tail-history-0-30-put10-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"'
    '-0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.10\\"}]]}],[\\"s'
    'elected_put_25\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"ta'
    'il-history-0-30-put25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\'
    '",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-0-30-put25-greeks\\"],[\\"implied_'
    'volatility\\",{\\"$decimal\\":\\"0.24\\"}],[\\"iv_record_id\\",\\"tail-history-0-30-put25-iv\\"],[\\"optio'
    'n_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-0-30-put25-quote\\"],[\\"selected_delta\\",{\\'
    '"$decimal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.'
    '25\\"}]]}],[\\"session_date\\",{\\"$date\\":\\"2029-12-24\\"}],[\\"underlying_quote_record_id\\",\\"ve-his'
    'tory-0-underlying\\"],[\\"upside_25_delta_skew\\",{\\"$decimal\\":\\"-0.020\\"}],[\\"upside_wing_curvatu'
    're\\",{\\"$decimal\\":\\"-0.02\\"}]]},{\\"$map\\":[[\\"atm_iv\\",{\\"$decimal\\":\\"0.210\\"}],[\\"call_10_del'
    'ta_iv\\",{\\"$decimal\\":\\"0.17\\"}],[\\"call_25_delta_iv\\",{\\"$decimal\\":\\"0.19\\"}],[\\"candidate_con'
    'tracts\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",'
    '\\"ve-history-1-0-call-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_'
    'to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.25\\"}],[\\"g'
    'reeks_record_id\\",\\"ve-history-1-0-call-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.20\\"'
    '}],[\\"iv_record_id\\",\\"ve-history-1-0-call-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\"'
    ',\\"ve-history-1-0-call-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.50\\"}],[\\"strike\\",{\\"$decim'
    'al\\":\\"100\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"ta'
    'il-history-1-30-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance'
    '_to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"'
    'greeks_record_id\\",\\"tail-history-1-30-call25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"'
    '0.19\\"}],[\\"iv_record_id\\",\\"tail-history-1-30-call25-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_'
    'record_id\\",\\"tail-history-1-30-call25-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"st'
    'rike\\",{\\"$decimal\\":\\"105\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_'
    'record_id\\",\\"tail-history-1-30-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",n'
    'ull],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\'
    '":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-1-30-call10-greeks\\"],[\\"implied_volatility\\",'
    '{\\"$decimal\\":\\"0.17\\"}],[\\"iv_record_id\\",\\"tail-history-1-30-call10-iv\\"],[\\"option_type\\",\\"c'
    'all\\"],[\\"quote_record_id\\",\\"tail-history-1-30-call10-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":'
    '\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"con'
    'tract_reference_record_id\\",\\"tail-history-1-30-put10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"del'
    'iverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance_to_25_target'
    '\\",{\\"$decimal\\":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-1-30-put10-greeks\\"],[\\"implied'
    '_volatility\\",{\\"$decimal\\":\\"0.33\\"}],[\\"iv_record_id\\",\\"tail-history-1-30-put10-iv\\"],[\\"opti'
    'on_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-1-30-put10-quote\\"],[\\"signed_delta\\",{\\"'
    '$decimal\\":\\"-0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",'
    '100],[\\"contract_reference_record_id\\",\\"tail-history-1-30-put25-reference\\"],[\\"currency\\",\\"US'
    'D\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_t'
    'o_25_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-1-30-put25-greeks\\"]'
    ',[\\"implied_volatility\\",{\\"$decimal\\":\\"0.27\\"}],[\\"iv_record_id\\",\\"tail-history-1-30-put25-iv'
    '\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-1-30-put25-quote\\"],[\\"signed_'
    'delta\\",{\\"$decimal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}]]},{\\"$map\\":[[\\"contract_mu'
    'ltiplier\\",100],[\\"contract_reference_record_id\\",\\"ve-history-1-0-put-reference\\"],[\\"currency\\'
    '",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"dist'
    'ance_to_25_target\\",{\\"$decimal\\":\\"0.25\\"}],[\\"greeks_record_id\\",\\"ve-history-1-0-put-greeks\\"'
    '],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.22\\"}],[\\"iv_record_id\\",\\"ve-history-1-0-put-iv\\"],'
    '[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"ve-history-1-0-put-quote\\"],[\\"signed_delta\\",{'
    '\\"$decimal\\":\\"-0.50\\"}],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"downside_25_delta_skew\\",{\\'
    '"$decimal\\":\\"0.060\\"}],[\\"downside_wing_curvature\\",{\\"$decimal\\":\\"0.06\\"}],[\\"expiration\\",{\\'
    '"$date\\":\\"2030-01-26\\"}],[\\"put_10_delta_iv\\",{\\"$decimal\\":\\"0.33\\"}],[\\"put_25_delta_iv\\",{\\"'
    '$decimal\\":\\"0.27\\"}],[\\"selected_call_10\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract'
    '_reference_record_id\\",\\"tail-history-1-30-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliver'
    'able_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-1-30'
    '-call10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.17\\"}],[\\"iv_record_id\\",\\"tail-hist'
    'ory-1-30-call10-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-1-30-call10'
    '-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}],[\\"ta'
    'rget_delta\\",{\\"$decimal\\":\\"0.10\\"}]]}],[\\"selected_call_25\\",{\\"$map\\":[[\\"contract_multiplier'
    '\\",100],[\\"contract_reference_record_id\\",\\"tail-history-1-30-call25-reference\\"],[\\"currency\\",'
    '\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",'
    '\\"tail-history-1-30-call25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.19\\"}],[\\"iv_reco'
    'rd_id\\",\\"tail-history-1-30-call25-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-'
    'history-1-30-call25-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decima'
    'l\\":\\"105\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"0.25\\"}]]}],[\\"selected_paired_atm_evidence\\",{\\'
    '"$map\\":[[\\"candidate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve'
    '-history-1-0-call-reference\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.20\\"}],[\\"call_iv_'
    'record_id\\",\\"ve-history-1-0-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-history-1-0-call-quote\\"]'
    ',[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_u'
    'nderlying_midpoint\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.21'
    '0\\"}],[\\"put_contract_reference_record_id\\",\\"ve-history-1-0-put-reference\\"],[\\"put_implied_vol'
    'atility\\",{\\"$decimal\\":\\"0.22\\"}],[\\"put_iv_record_id\\",\\"ve-history-1-0-put-iv\\"],[\\"put_quote'
    '_record_id\\",\\"ve-history-1-0-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"selected_'
    'atm_iv\\",{\\"$decimal\\":\\"0.210\\"}],[\\"selected_call_iv_record_id\\",\\"ve-history-1-0-call-iv\\"],['
    '\\"selected_put_iv_record_id\\",\\"ve-history-1-0-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"10'
    '0\\"}],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}]]}],[\\"selected_put_10\\",{\\"$map\\":[[\\"c'
    'ontract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-1-30-put10-reference\\'
    '"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"gr'
    'eeks_record_id\\",\\"tail-history-1-30-put10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.3'
    '3\\"}],[\\"iv_record_id\\",\\"tail-history-1-30-put10-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_recor'
    'd_id\\",\\"tail-history-1-30-put10-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"-0.11\\"}],[\\"strik'
    'e\\",{\\"$decimal\\":\\"90\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.10\\"}]]}],[\\"selected_put_25\\",{'
    '\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-1-30-pu'
    't25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"'
    '0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-1-30-put25-greeks\\"],[\\"implied_volatility\\",{\\"$d'
    'ecimal\\":\\"0.27\\"}],[\\"iv_record_id\\",\\"tail-history-1-30-put25-iv\\"],[\\"option_type\\",\\"put\\"],'
    '[\\"quote_record_id\\",\\"tail-history-1-30-put25-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"-0.2'
    '4\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.25\\"}]]}],[\\"sessi'
    'on_date\\",{\\"$date\\":\\"2029-12-27\\"}],[\\"underlying_quote_record_id\\",\\"ve-history-1-underlying\\'
    '"],[\\"upside_25_delta_skew\\",{\\"$decimal\\":\\"-0.020\\"}],[\\"upside_wing_curvature\\",{\\"$decimal\\"'
    ':\\"-0.02\\"}]]},{\\"$map\\":[[\\"atm_iv\\",{\\"$decimal\\":\\"0.220\\"}],[\\"call_10_delta_iv\\",{\\"$decima'
    'l\\":\\"0.18\\"}],[\\"call_25_delta_iv\\",{\\"$decimal\\":\\"0.20\\"}],[\\"candidate_contracts\\",{\\"$list\\'
    '":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"ve-history-2-0-c'
    'all-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"'
    '$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.25\\"}],[\\"greeks_record_id\\",'
    '\\"ve-history-2-0-call-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.21\\"}],[\\"iv_record_id'
    '\\",\\"ve-history-2-0-call-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"ve-history-2-0-'
    'call-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.50\\"}],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]},{'
    '\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-2-30-ca'
    'll25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\'
    '"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\"'
    ',\\"tail-history-2-30-call25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.20\\"}],[\\"iv_rec'
    'ord_id\\",\\"tail-history-2-30-call25-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail'
    '-history-2-30-call25-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decimal'
    '\\":\\"105\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail'
    '-history-2-30-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_t'
    'o_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"gr'
    'eeks_record_id\\",\\"tail-history-2-30-call10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.'
    '18\\"}],[\\"iv_record_id\\",\\"tail-history-2-30-call10-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_re'
    'cord_id\\",\\"tail-history-2-30-call10-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.11\\"}],[\\"stri'
    'ke\\",{\\"$decimal\\":\\"110\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_re'
    'cord_id\\",\\"tail-history-2-30-put10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null'
    '],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\'
    '"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-2-30-put10-greeks\\"],[\\"implied_volatility\\",{\\"$'
    'decimal\\":\\"0.36\\"}],[\\"iv_record_id\\",\\"tail-history-2-30-put10-iv\\"],[\\"option_type\\",\\"put\\"]'
    ',[\\"quote_record_id\\",\\"tail-history-2-30-put10-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.11'
    '\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_r'
    'eference_record_id\\",\\"tail-history-2-30-put25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverabl'
    'e_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$'
    'decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-2-30-put25-greeks\\"],[\\"implied_volati'
    'lity\\",{\\"$decimal\\":\\"0.30\\"}],[\\"iv_record_id\\",\\"tail-history-2-30-put25-iv\\"],[\\"option_type'
    '\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-2-30-put25-quote\\"],[\\"signed_delta\\",{\\"$decima'
    'l\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\'
    '"contract_reference_record_id\\",\\"ve-history-2-0-put-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deli'
    'verable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\'
    '",{\\"$decimal\\":\\"0.25\\"}],[\\"greeks_record_id\\",\\"ve-history-2-0-put-greeks\\"],[\\"implied_volat'
    'ility\\",{\\"$decimal\\":\\"0.23\\"}],[\\"iv_record_id\\",\\"ve-history-2-0-put-iv\\"],[\\"option_type\\",\\'
    '"put\\"],[\\"quote_record_id\\",\\"ve-history-2-0-put-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.'
    '50\\"}],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"downside_25_delta_skew\\",{\\"$decimal\\":\\"0.08'
    '0\\"}],[\\"downside_wing_curvature\\",{\\"$decimal\\":\\"0.06\\"}],[\\"expiration\\",{\\"$date\\":\\"2030-01'
    '-29\\"}],[\\"put_10_delta_iv\\",{\\"$decimal\\":\\"0.36\\"}],[\\"put_25_delta_iv\\",{\\"$decimal\\":\\"0.30\\'
    '"}],[\\"selected_call_10\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_'
    'id\\",\\"tail-history-2-30-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\'
    '"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-2-30-call10-greeks\\"],'
    '[\\"implied_volatility\\",{\\"$decimal\\":\\"0.18\\"}],[\\"iv_record_id\\",\\"tail-history-2-30-call10-iv'
    '\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-2-30-call10-quote\\"],[\\"selec'
    'ted_delta\\",{\\"$decimal\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}],[\\"target_delta\\",{\\"$d'
    'ecimal\\":\\"0.10\\"}]]}],[\\"selected_call_25\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contrac'
    't_reference_record_id\\",\\"tail-history-2-30-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"delive'
    'rable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-2-3'
    '0-call25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.20\\"}],[\\"iv_record_id\\",\\"tail-his'
    'tory-2-30-call25-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-2-30-call2'
    '5-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"105\\"}],[\\"t'
    'arget_delta\\",{\\"$decimal\\":\\"0.25\\"}]]}],[\\"selected_paired_atm_evidence\\",{\\"$map\\":[[\\"candid'
    'ate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve-history-2-0-call-'
    'reference\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.21\\"}],[\\"call_iv_record_id\\",\\"ve-h'
    'istory-2-0-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-history-2-0-call-quote\\"],[\\"contract_multi'
    'plier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint'
    '\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.220\\"}],[\\"put_contr'
    'act_reference_record_id\\",\\"ve-history-2-0-put-reference\\"],[\\"put_implied_volatility\\",{\\"$deci'
    'mal\\":\\"0.23\\"}],[\\"put_iv_record_id\\",\\"ve-history-2-0-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-'
    'history-2-0-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"selected_atm_iv\\",{\\"$decim'
    'al\\":\\"0.220\\"}],[\\"selected_call_iv_record_id\\",\\"ve-history-2-0-call-iv\\"],[\\"selected_put_iv_'
    'record_id\\",\\"ve-history-2-0-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"100\\"}],[\\"underlyin'
    'g_midpoint\\",{\\"$decimal\\":\\"100.0\\"}]]}],[\\"selected_put_10\\",{\\"$map\\":[[\\"contract_multiplier'
    '\\",100],[\\"contract_reference_record_id\\",\\"tail-history-2-30-put10-reference\\"],[\\"currency\\",\\'
    '"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\'
    '"tail-history-2-30-put10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.36\\"}],[\\"iv_record'
    '_id\\",\\"tail-history-2-30-put10-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-hist'
    'ory-2-30-put10-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"-0.11\\"}],[\\"strike\\",{\\"$decimal\\":'
    '\\"90\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.10\\"}]]}],[\\"selected_put_25\\",{\\"$map\\":[[\\"contr'
    'act_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-2-30-put25-reference\\"],['
    '\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks'
    '_record_id\\",\\"tail-history-2-30-put25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.30\\"}'
    '],[\\"iv_record_id\\",\\"tail-history-2-30-put25-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id'
    '\\",\\"tail-history-2-30-put25-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"-0.24\\"}],[\\"strike\\",'
    '{\\"$decimal\\":\\"95\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.25\\"}]]}],[\\"session_date\\",{\\"$date'
    '\\":\\"2029-12-30\\"}],[\\"underlying_quote_record_id\\",\\"ve-history-2-underlying\\"],[\\"upside_25_de'
    'lta_skew\\",{\\"$decimal\\":\\"-0.020\\"}],[\\"upside_wing_curvature\\",{\\"$decimal\\":\\"-0.02\\"}]]}]}],'
    '[\\"tenor_days\\",30]]},{\\"$map\\":[[\\"current_expiration\\",{\\"$date\\":\\"2030-03-03\\"}],[\\"historic'
    'al_observations\\",{\\"$list\\":[{\\"$map\\":[[\\"atm_iv\\",{\\"$decimal\\":\\"0.300\\"}],[\\"call_10_delta_'
    'iv\\",{\\"$decimal\\":\\"0.26\\"}],[\\"call_25_delta_iv\\",{\\"$decimal\\":\\"0.28\\"}],[\\"candidate_contra'
    'cts\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"t'
    'ail-history-0-60-atm-call-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"dista'
    'nce_to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.25\\"}],'
    '[\\"greeks_record_id\\",\\"tail-history-0-60-atm-call-greeks\\"],[\\"implied_volatility\\",{\\"$decimal'
    '\\":\\"0.30\\"}],[\\"iv_record_id\\",\\"tail-history-0-60-atm-call-iv\\"],[\\"option_type\\",\\"call\\"],[\\'
    '"quote_record_id\\",\\"tail-history-0-60-atm-call-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.50\\'
    '"}],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_r'
    'eference_record_id\\",\\"tail-history-0-60-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverab'
    'le_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"'
    '$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-0-60-call25-greeks\\"],[\\"implied_vola'
    'tility\\",{\\"$decimal\\":\\"0.28\\"}],[\\"iv_record_id\\",\\"tail-history-0-60-call25-iv\\"],[\\"option_t'
    'ype\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-0-60-call25-quote\\"],[\\"signed_delta\\",{\\"$d'
    'ecimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"105\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",10'
    '0],[\\"contract_reference_record_id\\",\\"tail-history-0-60-call10-reference\\"],[\\"currency\\",\\"USD'
    '\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance_to'
    '_25_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-0-60-call10-greeks\\"]'
    ',[\\"implied_volatility\\",{\\"$decimal\\":\\"0.26\\"}],[\\"iv_record_id\\",\\"tail-history-0-60-call10-i'
    'v\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-0-60-call10-quote\\"],[\\"sign'
    'ed_delta\\",{\\"$decimal\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}]]},{\\"$map\\":[[\\"contract'
    '_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-0-60-put10-reference\\"],[\\"c'
    'urrency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}]'
    ',[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-0-60-p'
    'ut10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.40\\"}],[\\"iv_record_id\\",\\"tail-history'
    '-0-60-put10-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-0-60-put10-quote'
    '\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}]]},{\\"$map\\":['
    '[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-0-60-put25-refere'
    'nce\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\"'
    ':\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-his'
    'tory-0-60-put25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.34\\"}],[\\"iv_record_id\\",\\"t'
    'ail-history-0-60-put25-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-0-60-'
    'put25-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}]]},'
    '{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-0-60-a'
    'tm-put-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",'
    '{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.25\\"}],[\\"greeks_record_id'
    '\\",\\"tail-history-0-60-atm-put-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"iv_'
    'record_id\\",\\"tail-history-0-60-atm-put-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"t'
    'ail-history-0-60-atm-put-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.50\\"}],[\\"strike\\",{\\"$de'
    'cimal\\":\\"100\\"}]]}]}],[\\"downside_25_delta_skew\\",{\\"$decimal\\":\\"0.040\\"}],[\\"downside_wing_cu'
    'rvature\\",{\\"$decimal\\":\\"0.06\\"}],[\\"expiration\\",{\\"$date\\":\\"2030-02-22\\"}],[\\"put_10_delta_i'
    'v\\",{\\"$decimal\\":\\"0.40\\"}],[\\"put_25_delta_iv\\",{\\"$decimal\\":\\"0.34\\"}],[\\"selected_call_10\\"'
    ',{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-0-60-'
    'call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\"'
    ':\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-0-60-call10-greeks\\"],[\\"implied_volatility\\",{'
    '\\"$decimal\\":\\"0.26\\"}],[\\"iv_record_id\\",\\"tail-history-0-60-call10-iv\\"],[\\"option_type\\",\\"ca'
    'll\\"],[\\"quote_record_id\\",\\"tail-history-0-60-call10-quote\\"],[\\"selected_delta\\",{\\"$decimal\\"'
    ':\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"0.10\\"}]]}],[\\'
    '"selected_call_25\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\'
    '"tail-history-0-60-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"dista'
    'nce\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-0-60-call25-greeks\\"],[\\"imp'
    'lied_volatility\\",{\\"$decimal\\":\\"0.28\\"}],[\\"iv_record_id\\",\\"tail-history-0-60-call25-iv\\"],[\\'
    '"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-0-60-call25-quote\\"],[\\"selected_de'
    'lta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"105\\"}],[\\"target_delta\\",{\\"$decimal'
    '\\":\\"0.25\\"}]]}],[\\"selected_paired_atm_evidence\\",{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\":[{'
    '\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"tail-history-0-60-atm-call-reference\\"],[\\"ca'
    'll_implied_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"call_iv_record_id\\",\\"tail-history-0-60-atm-'
    'call-iv\\"],[\\"call_quote_record_id\\",\\"tail-history-0-60-atm-call-quote\\"],[\\"contract_multiplie'
    'r\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\",{'
    '\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.300\\"}],[\\"put_contract_'
    'reference_record_id\\",\\"tail-history-0-60-atm-put-reference\\"],[\\"put_implied_volatility\\",{\\"$d'
    'ecimal\\":\\"0.30\\"}],[\\"put_iv_record_id\\",\\"tail-history-0-60-atm-put-iv\\"],[\\"put_quote_record_'
    'id\\",\\"tail-history-0-60-atm-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"selected_a'
    'tm_iv\\",{\\"$decimal\\":\\"0.300\\"}],[\\"selected_call_iv_record_id\\",\\"tail-history-0-60-atm-call-i'
    'v\\"],[\\"selected_put_iv_record_id\\",\\"tail-history-0-60-atm-put-iv\\"],[\\"selected_strike\\",{\\"$d'
    'ecimal\\":\\"100\\"}],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}]]}],[\\"selected_put_10\\",{\\'
    '"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-0-60-put'
    '10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":\\"0'
    '.01\\"}],[\\"greeks_record_id\\",\\"tail-history-0-60-put10-greeks\\"],[\\"implied_volatility\\",{\\"$de'
    'cimal\\":\\"0.40\\"}],[\\"iv_record_id\\",\\"tail-history-0-60-put10-iv\\"],[\\"option_type\\",\\"put\\"],['
    '\\"quote_record_id\\",\\"tail-history-0-60-put10-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"-0.11'
    '\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.10\\"}]]}],[\\"select'
    'ed_put_25\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-hi'
    'story-0-60-put25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"'
    '$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-0-60-put25-greeks\\"],[\\"implied_volat'
    'ility\\",{\\"$decimal\\":\\"0.34\\"}],[\\"iv_record_id\\",\\"tail-history-0-60-put25-iv\\"],[\\"option_typ'
    'e\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-0-60-put25-quote\\"],[\\"selected_delta\\",{\\"$dec'
    'imal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.25\\"}'
    ']]}],[\\"session_date\\",{\\"$date\\":\\"2029-12-24\\"}],[\\"underlying_quote_record_id\\",\\"tail-histor'
    'y-0-60-underlying\\"],[\\"upside_25_delta_skew\\",{\\"$decimal\\":\\"-0.020\\"}],[\\"upside_wing_curvatu'
    're\\",{\\"$decimal\\":\\"-0.02\\"}]]},{\\"$map\\":[[\\"atm_iv\\",{\\"$decimal\\":\\"0.310\\"}],[\\"call_10_del'
    'ta_iv\\",{\\"$decimal\\":\\"0.27\\"}],[\\"call_25_delta_iv\\",{\\"$decimal\\":\\"0.29\\"}],[\\"candidate_con'
    'tracts\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",'
    '\\"tail-history-1-60-atm-call-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"di'
    'stance_to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.25\\"'
    '}],[\\"greeks_record_id\\",\\"tail-history-1-60-atm-call-greeks\\"],[\\"implied_volatility\\",{\\"$deci'
    'mal\\":\\"0.31\\"}],[\\"iv_record_id\\",\\"tail-history-1-60-atm-call-iv\\"],[\\"option_type\\",\\"call\\"]'
    ',[\\"quote_record_id\\",\\"tail-history-1-60-atm-call-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"0.'
    '50\\"}],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contrac'
    't_reference_record_id\\",\\"tail-history-1-60-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"delive'
    'rable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",'
    '{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-1-60-call25-greeks\\"],[\\"implied_v'
    'olatility\\",{\\"$decimal\\":\\"0.29\\"}],[\\"iv_record_id\\",\\"tail-history-1-60-call25-iv\\"],[\\"optio'
    'n_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-1-60-call25-quote\\"],[\\"signed_delta\\",{\\'
    '"$decimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"105\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\"'
    ',100],[\\"contract_reference_record_id\\",\\"tail-history-1-60-call10-reference\\"],[\\"currency\\",\\"'
    'USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"distance'
    '_to_25_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-1-60-call10-greeks'
    '\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.27\\"}],[\\"iv_record_id\\",\\"tail-history-1-60-call1'
    '0-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-1-60-call10-quote\\"],[\\"s'
    'igned_delta\\",{\\"$decimal\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}]]},{\\"$map\\":[[\\"contr'
    'act_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-1-60-put10-reference\\"],['
    '\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\'
    '"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-1-6'
    '0-put10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.43\\"}],[\\"iv_record_id\\",\\"tail-hist'
    'ory-1-60-put10-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-1-60-put10-qu'
    'ote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}]]},{\\"$map\\'
    '":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-1-60-put25-ref'
    'erence\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decima'
    'l\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-'
    'history-1-60-put25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.37\\"}],[\\"iv_record_id\\",'
    '\\"tail-history-1-60-put25-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-1-'
    '60-put25-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}]'
    ']},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-1-6'
    '0-atm-put-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target'
    '\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.25\\"}],[\\"greeks_record'
    '_id\\",\\"tail-history-1-60-atm-put-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.31\\"}],[\\"'
    'iv_record_id\\",\\"tail-history-1-60-atm-put-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",'
    '\\"tail-history-1-60-atm-put-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.50\\"}],[\\"strike\\",{\\"'
    '$decimal\\":\\"100\\"}]]}]}],[\\"downside_25_delta_skew\\",{\\"$decimal\\":\\"0.060\\"}],[\\"downside_wing'
    '_curvature\\",{\\"$decimal\\":\\"0.06\\"}],[\\"expiration\\",{\\"$date\\":\\"2030-02-25\\"}],[\\"put_10_delt'
    'a_iv\\",{\\"$decimal\\":\\"0.43\\"}],[\\"put_25_delta_iv\\",{\\"$decimal\\":\\"0.37\\"}],[\\"selected_call_1'
    '0\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-1-'
    '60-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decima'
    'l\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-1-60-call10-greeks\\"],[\\"implied_volatility\\'
    '",{\\"$decimal\\":\\"0.27\\"}],[\\"iv_record_id\\",\\"tail-history-1-60-call10-iv\\"],[\\"option_type\\",\\'
    '"call\\"],[\\"quote_record_id\\",\\"tail-history-1-60-call10-quote\\"],[\\"selected_delta\\",{\\"$decima'
    'l\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"0.10\\"}]]}]'
    ',[\\"selected_call_25\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\'
    '",\\"tail-history-1-60-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"di'
    'stance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-1-60-call25-greeks\\"],[\\"'
    'implied_volatility\\",{\\"$decimal\\":\\"0.29\\"}],[\\"iv_record_id\\",\\"tail-history-1-60-call25-iv\\"]'
    ',[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-1-60-call25-quote\\"],[\\"selected'
    '_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"105\\"}],[\\"target_delta\\",{\\"$deci'
    'mal\\":\\"0.25\\"}]]}],[\\"selected_paired_atm_evidence\\",{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\"'
    ':[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"tail-history-1-60-atm-call-reference\\"],[\\'
    '"call_implied_volatility\\",{\\"$decimal\\":\\"0.31\\"}],[\\"call_iv_record_id\\",\\"tail-history-1-60-a'
    'tm-call-iv\\"],[\\"call_quote_record_id\\",\\"tail-history-1-60-atm-call-quote\\"],[\\"contract_multip'
    'lier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\'
    '",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.310\\"}],[\\"put_contra'
    'ct_reference_record_id\\",\\"tail-history-1-60-atm-put-reference\\"],[\\"put_implied_volatility\\",{\\'
    '"$decimal\\":\\"0.31\\"}],[\\"put_iv_record_id\\",\\"tail-history-1-60-atm-put-iv\\"],[\\"put_quote_reco'
    'rd_id\\",\\"tail-history-1-60-atm-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"selecte'
    'd_atm_iv\\",{\\"$decimal\\":\\"0.310\\"}],[\\"selected_call_iv_record_id\\",\\"tail-history-1-60-atm-cal'
    'l-iv\\"],[\\"selected_put_iv_record_id\\",\\"tail-history-1-60-atm-put-iv\\"],[\\"selected_strike\\",{\\'
    '"$decimal\\":\\"100\\"}],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}]]}],[\\"selected_put_10\\"'
    ',{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-1-60-'
    'put10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal\\":'
    '\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-1-60-put10-greeks\\"],[\\"implied_volatility\\",{\\"'
    '$decimal\\":\\"0.43\\"}],[\\"iv_record_id\\",\\"tail-history-1-60-put10-iv\\"],[\\"option_type\\",\\"put\\"'
    '],[\\"quote_record_id\\",\\"tail-history-1-60-put10-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\"-0'
    '.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.10\\"}]]}],[\\"sel'
    'ected_put_25\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail'
    '-history-1-60-put25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",'
    '{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-1-60-put25-greeks\\"],[\\"implied_vo'
    'latility\\",{\\"$decimal\\":\\"0.37\\"}],[\\"iv_record_id\\",\\"tail-history-1-60-put25-iv\\"],[\\"option_'
    'type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-1-60-put25-quote\\"],[\\"selected_delta\\",{\\"$'
    'decimal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.25'
    '\\"}]]}],[\\"session_date\\",{\\"$date\\":\\"2029-12-27\\"}],[\\"underlying_quote_record_id\\",\\"tail-his'
    'tory-1-60-underlying\\"],[\\"upside_25_delta_skew\\",{\\"$decimal\\":\\"-0.020\\"}],[\\"upside_wing_curv'
    'ature\\",{\\"$decimal\\":\\"-0.02\\"}]]},{\\"$map\\":[[\\"atm_iv\\",{\\"$decimal\\":\\"0.320\\"}],[\\"call_10_'
    'delta_iv\\",{\\"$decimal\\":\\"0.28\\"}],[\\"call_25_delta_iv\\",{\\"$decimal\\":\\"0.30\\"}],[\\"candidate_'
    'contracts\\",{\\"$list\\":[{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id'
    '\\",\\"tail-history-2-60-atm-call-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\'
    '"distance_to_10_target\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.2'
    '5\\"}],[\\"greeks_record_id\\",\\"tail-history-2-60-atm-call-greeks\\"],[\\"implied_volatility\\",{\\"$d'
    'ecimal\\":\\"0.32\\"}],[\\"iv_record_id\\",\\"tail-history-2-60-atm-call-iv\\"],[\\"option_type\\",\\"call'
    '\\"],[\\"quote_record_id\\",\\"tail-history-2-60-atm-call-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\'
    '"0.50\\"}],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"cont'
    'ract_reference_record_id\\",\\"tail-history-2-60-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"del'
    'iverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"distance_to_25_target'
    '\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-2-60-call25-greeks\\"],[\\"implie'
    'd_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"iv_record_id\\",\\"tail-history-2-60-call25-iv\\"],[\\"op'
    'tion_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-2-60-call25-quote\\"],[\\"signed_delta\\"'
    ',{\\"$decimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"105\\"}]]},{\\"$map\\":[[\\"contract_multiplie'
    'r\\",100],[\\"contract_reference_record_id\\",\\"tail-history-2-60-call10-reference\\"],[\\"currency\\"'
    ',\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"dista'
    'nce_to_25_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-2-60-call10-gre'
    'eks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.28\\"}],[\\"iv_record_id\\",\\"tail-history-2-60-ca'
    'll10-iv\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-2-60-call10-quote\\"],['
    '\\"signed_delta\\",{\\"$decimal\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}]]},{\\"$map\\":[[\\"co'
    'ntract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-2-60-put10-reference\\"'
    '],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$decimal\\":\\"0.'
    '01\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.14\\"}],[\\"greeks_record_id\\",\\"tail-history-'
    '2-60-put10-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.46\\"}],[\\"iv_record_id\\",\\"tail-h'
    'istory-2-60-put10-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-2-60-put10'
    '-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}]]},{\\"$m'
    'ap\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-2-60-put25-'
    'reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_target\\",{\\"$dec'
    'imal\\":\\"0.14\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"ta'
    'il-history-2-60-put25-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.40\\"}],[\\"iv_record_id'
    '\\",\\"tail-history-2-60-put25-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history'
    '-2-60-put25-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\'
    '"}]]},{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-'
    '2-60-atm-put-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_10_tar'
    'get\\",{\\"$decimal\\":\\"0.40\\"}],[\\"distance_to_25_target\\",{\\"$decimal\\":\\"0.25\\"}],[\\"greeks_rec'
    'ord_id\\",\\"tail-history-2-60-atm-put-greeks\\"],[\\"implied_volatility\\",{\\"$decimal\\":\\"0.32\\"}],'
    '[\\"iv_record_id\\",\\"tail-history-2-60-atm-put-iv\\"],[\\"option_type\\",\\"put\\"],[\\"quote_record_id'
    '\\",\\"tail-history-2-60-atm-put-quote\\"],[\\"signed_delta\\",{\\"$decimal\\":\\"-0.50\\"}],[\\"strike\\",'
    '{\\"$decimal\\":\\"100\\"}]]}]}],[\\"downside_25_delta_skew\\",{\\"$decimal\\":\\"0.080\\"}],[\\"downside_w'
    'ing_curvature\\",{\\"$decimal\\":\\"0.06\\"}],[\\"expiration\\",{\\"$date\\":\\"2030-02-28\\"}],[\\"put_10_d'
    'elta_iv\\",{\\"$decimal\\":\\"0.46\\"}],[\\"put_25_delta_iv\\",{\\"$decimal\\":\\"0.40\\"}],[\\"selected_cal'
    'l_10\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history'
    '-2-60-call10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$dec'
    'imal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-2-60-call10-greeks\\"],[\\"implied_volatili'
    'ty\\",{\\"$decimal\\":\\"0.28\\"}],[\\"iv_record_id\\",\\"tail-history-2-60-call10-iv\\"],[\\"option_type\\'
    '",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-2-60-call10-quote\\"],[\\"selected_delta\\",{\\"$dec'
    'imal\\":\\"0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"110\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"0.10\\"}]'
    ']}],[\\"selected_call_25\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_'
    'id\\",\\"tail-history-2-60-call25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\'
    '"distance\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-2-60-call25-greeks\\"],'
    '[\\"implied_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"iv_record_id\\",\\"tail-history-2-60-call25-iv'
    '\\"],[\\"option_type\\",\\"call\\"],[\\"quote_record_id\\",\\"tail-history-2-60-call25-quote\\"],[\\"selec'
    'ted_delta\\",{\\"$decimal\\":\\"0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"105\\"}],[\\"target_delta\\",{\\"$d'
    'ecimal\\":\\"0.25\\"}]]}],[\\"selected_paired_atm_evidence\\",{\\"$map\\":[[\\"candidate_pairs\\",{\\"$lis'
    't\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"tail-history-2-60-atm-call-reference\\"]'
    ',[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.32\\"}],[\\"call_iv_record_id\\",\\"tail-history-2-6'
    '0-atm-call-iv\\"],[\\"call_quote_record_id\\",\\"tail-history-2-60-atm-call-quote\\"],[\\"contract_mul'
    'tiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoi'
    'nt\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.320\\"}],[\\"put_con'
    'tract_reference_record_id\\",\\"tail-history-2-60-atm-put-reference\\"],[\\"put_implied_volatility\\"'
    ',{\\"$decimal\\":\\"0.32\\"}],[\\"put_iv_record_id\\",\\"tail-history-2-60-atm-put-iv\\"],[\\"put_quote_r'
    'ecord_id\\",\\"tail-history-2-60-atm-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"sele'
    'cted_atm_iv\\",{\\"$decimal\\":\\"0.320\\"}],[\\"selected_call_iv_record_id\\",\\"tail-history-2-60-atm-'
    'call-iv\\"],[\\"selected_put_iv_record_id\\",\\"tail-history-2-60-atm-put-iv\\"],[\\"selected_strike\\"'
    ',{\\"$decimal\\":\\"100\\"}],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}]]}],[\\"selected_put_1'
    '0\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"tail-history-2-'
    '60-put10-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance\\",{\\"$decimal'
    '\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-2-60-put10-greeks\\"],[\\"implied_volatility\\",'
    '{\\"$decimal\\":\\"0.46\\"}],[\\"iv_record_id\\",\\"tail-history-2-60-put10-iv\\"],[\\"option_type\\",\\"pu'
    't\\"],[\\"quote_record_id\\",\\"tail-history-2-60-put10-quote\\"],[\\"selected_delta\\",{\\"$decimal\\":\\'
    '"-0.11\\"}],[\\"strike\\",{\\"$decimal\\":\\"90\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0.10\\"}]]}],[\\"'
    'selected_put_25\\",{\\"$map\\":[[\\"contract_multiplier\\",100],[\\"contract_reference_record_id\\",\\"t'
    'ail-history-2-60-put25-reference\\"],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance'
    '\\",{\\"$decimal\\":\\"0.01\\"}],[\\"greeks_record_id\\",\\"tail-history-2-60-put25-greeks\\"],[\\"implied'
    '_volatility\\",{\\"$decimal\\":\\"0.40\\"}],[\\"iv_record_id\\",\\"tail-history-2-60-put25-iv\\"],[\\"opti'
    'on_type\\",\\"put\\"],[\\"quote_record_id\\",\\"tail-history-2-60-put25-quote\\"],[\\"selected_delta\\",{'
    '\\"$decimal\\":\\"-0.24\\"}],[\\"strike\\",{\\"$decimal\\":\\"95\\"}],[\\"target_delta\\",{\\"$decimal\\":\\"-0'
    '.25\\"}]]}],[\\"session_date\\",{\\"$date\\":\\"2029-12-30\\"}],[\\"underlying_quote_record_id\\",\\"tail-'
    'history-2-60-underlying\\"],[\\"upside_25_delta_skew\\",{\\"$decimal\\":\\"-0.020\\"}],[\\"upside_wing_c'
    'urvature\\",{\\"$decimal\\":\\"-0.02\\"}]]}]}],[\\"tenor_days\\",60]]}]}],[\\"interpolation_rule\\",\\"non'
    'e\\"],[\\"normalized_evidence\\",{\\"$map\\":[[\\"direct_inputs\\",{\\"$list\\":[{\\"$map\\":[[\\"normalized'
    '_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":'
    '[]}],[\\"record_id\\",\\"tail-current-30-call10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_id'
    's\\",{\\"$list\\":[\\"tail-current-30-call10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\'
    '"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"'
    'record_id\\",\\"tail-current-30-call10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_id'
    's\\",{\\"$list\\":[\\"tail-current-30-call10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$da'
    'tetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"reco'
    'rd_id\\",\\"tail-current-30-call10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\"'
    ':[\\"tail-current-30-call10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"'
    '2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"t'
    'ail-current-30-call10-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$'
    'list\\":[\\"tail-current-30-call10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$dat'
    'etime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"recor'
    'd_id\\",\\"tail-current-30-call25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\'
    '":[\\"tail-current-30-call25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":'
    '\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\'
    '"tail-current-30-call25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\'
    '":[\\"tail-current-30-call25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"20'
    '30-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tai'
    'l-current-30-call25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-curr'
    'ent-30-call25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15'
    ':30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-3'
    '0-call25-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tai'
    'l-current-30-call25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"203'
    '0-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail'
    '-current-30-put10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-curr'
    'ent-30-put10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15'
    ':30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-3'
    '0-put10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-curren'
    't-30-put10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00'
    '.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-30-put1'
    '0-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-30-put10-quote'
    '-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],'
    '[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-30-put10-reference\\"'
    '],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-30-put10-r'
    'eference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.0000'
    '02Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-30-put25-gre'
    'eks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-30-put25-greeks-s'
    'ource-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\'
    '"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-30-put25-iv\\"],[\\"role'
    '\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-30-put25-iv-source-'
    '0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propa'
    'gated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-30-put25-quote\\"],[\\"role\\",'
    '\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-30-put25-quote-source-0\\"]}]]},{\\"$'
    'map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality'
    '_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-30-put25-reference\\"],[\\"role\\",\\"option_'
    'contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-30-put25-reference-source-0\\"]}'
    ']]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated'
    '_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-60-call10-greeks\\"],[\\"role\\",\\"o'
    'ption_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-60-call10-greeks-source-0\\"]}]]},{\\"$'
    'map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality'
    '_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-60-call10-iv\\"],[\\"role\\",\\"option_implie'
    'd_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-60-call10-iv-source-0\\"]}]]},{\\"$map\\'
    '":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_fla'
    'gs\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-60-call10-quote\\"],[\\"role\\",\\"option_quote\\"'
    '],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-60-call10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"norma'
    'lized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$li'
    'st\\":[]}],[\\"record_id\\",\\"tail-current-60-call10-reference\\"],[\\"role\\",\\"option_contract_refer'
    'ence\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-60-call10-reference-source-0\\"]}]]},{\\"$map\\"'
    ':[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flag'
    's\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-60-call25-greeks\\"],[\\"role\\",\\"option_greeks\\'
    '"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-60-call25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"nor'
    'malized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$'
    'list\\":[]}],[\\"record_id\\",\\"tail-current-60-call25-iv\\"],[\\"role\\",\\"option_implied_volatility\\'
    '"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-60-call25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normali'
    'zed_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list'
    '\\":[]}],[\\"record_id\\",\\"tail-current-60-call25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_i'
    'ds\\",{\\"$list\\":[\\"tail-current-60-call25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\'
    '"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"'
    'record_id\\",\\"tail-current-60-call25-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"so'
    'urce_ids\\",{\\"$list\\":[\\"tail-current-60-call25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normaliz'
    'ed_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\'
    '":[]}],[\\"record_id\\",\\"tail-current-60-put10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_i'
    'ds\\",{\\"$list\\":[\\"tail-current-60-put10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\'
    '"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"'
    'record_id\\",\\"tail-current-60-put10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids'
    '\\",{\\"$list\\":[\\"tail-current-60-put10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$date'
    'time\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record'
    '_id\\",\\"tail-current-60-put10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\'
    '"tail-current-60-put10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030'
    '-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-'
    'current-60-put10-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\'
    '":[\\"tail-current-60-put10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\'
    '":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\"'
    ',\\"tail-current-60-put25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"ta'
    'il-current-60-put25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-0'
    '1-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-cu'
    'rrent-60-put25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail'
    '-current-60-put25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T1'
    '5:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-'
    '60-put25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-60-put2'
    '5-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.00000'
    '2Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-current-60-put25-refe'
    'rence\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-current-60-'
    'put25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:'
    '00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-'
    'call10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-30-ca'
    'll10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.0'
    '00002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-call'
    '10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-3'
    '0-call10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.0'
    '00002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-call'
    '10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-30-call10-q'
    'uote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\'
    '"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-call10-refe'
    'rence\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-3'
    '0-call10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:'
    '30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-'
    '30-call25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-30'
    '-call25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:0'
    '0.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-c'
    'all25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-'
    '0-30-call25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:0'
    '0.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-c'
    'all25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-30-call2'
    '5-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.00000'
    '2Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-call25-r'
    'eference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-'
    '0-30-call25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T'
    '15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history'
    '-0-30-put10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-'
    '30-put10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:'
    '00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-'
    'put10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-'
    '0-30-put10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00'
    '.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-pu'
    't10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-30-put10-q'
    'uote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\'
    '"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-put10-refer'
    'ence\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-30'
    '-put10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30'
    ':00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30'
    '-put25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-30-pu'
    't25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.00'
    '0002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-put25'
    '-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-30-'
    'put25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.0000'
    '02Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-put25-q'
    'uote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-30-put25-quote-'
    'source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],['
    '\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-30-put25-reference\\'
    '"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-30-put2'
    '5-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.0'
    '00002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-60-atm-'
    'call-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-60-atm-'
    'call-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.0'
    '00002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-60-atm-'
    'call-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0'
    '-60-atm-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:'
    '00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-60-'
    'atm-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-0-60-at'
    'm-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.'
    '000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-0-60-atm'
    '-call-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-h'
    'istory-0-60-atm-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"20'
    '30-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tai'
    'l-history-0-60-atm-put-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail'
    '-history-0-60-atm-put-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030'
    '-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-'
    'history-0-60-atm-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":['
    '\\"tail-history-0-60-atm-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"20'
    '30-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tai'
    'l-history-0-60-atm-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-h'
    'istory-0-60-atm-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01'
    '-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-his'
    'tory-0-60-atm-put-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list'
    '\\":[\\"tail-history-0-60-atm-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$date'
    'time\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record'
    '_id\\",\\"tail-history-0-60-call10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list'
    '\\":[\\"tail-history-0-60-call10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime'
    '\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\'
    '",\\"tail-history-0-60-call10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$'
    'list\\":[\\"tail-history-0-60-call10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime'
    '\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\'
    '",\\"tail-history-0-60-call10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"'
    'tail-history-0-60-call10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"20'
    '30-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tai'
    'l-history-0-60-call10-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$'
    'list\\":[\\"tail-history-0-60-call10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$d'
    'atetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"rec'
    'ord_id\\",\\"tail-history-0-60-call25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$l'
    'ist\\":[\\"tail-history-0-60-call25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datet'
    'ime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_'
    'id\\",\\"tail-history-0-60-call25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{'
    '\\"$list\\":[\\"tail-history-0-60-call25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datet'
    'ime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_'
    'id\\",\\"tail-history-0-60-call25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":'
    '[\\"tail-history-0-60-call25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\'
    '"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"'
    'tail-history-0-60-call25-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{'
    '\\"$list\\":[\\"tail-history-0-60-call25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\'
    '"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"'
    'record_id\\",\\"tail-history-0-60-put10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"'
    '$list\\":[\\"tail-history-0-60-put10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$date'
    'time\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record'
    '_id\\",\\"tail-history-0-60-put10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{'
    '\\"$list\\":[\\"tail-history-0-60-put10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$dateti'
    'me\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_i'
    'd\\",\\"tail-history-0-60-put10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\'
    '"tail-history-0-60-put10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"20'
    '30-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tai'
    'l-history-0-60-put10-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$l'
    'ist\\":[\\"tail-history-0-60-put10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$dat'
    'etime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"recor'
    'd_id\\",\\"tail-history-0-60-put25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list'
    '\\":[\\"tail-history-0-60-put25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\'
    '":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\"'
    ',\\"tail-history-0-60-put25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$li'
    'st\\":[\\"tail-history-0-60-put25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":'
    '\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\'
    '"tail-history-0-60-put25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail'
    '-history-0-60-put25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01'
    '-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-his'
    'tory-0-60-put25-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\"'
    ':[\\"tail-history-0-60-put25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime'
    '\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\'
    '",\\"tail-history-0-60-underlying\\"],[\\"role\\",\\"underlying_quote\\"],[\\"source_ids\\",{\\"$list\\":['
    '\\"tail-history-0-60-underlying-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"20'
    '30-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tai'
    'l-history-1-30-call10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-'
    'history-1-30-call10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-0'
    '1-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-hi'
    'story-1-30-call10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"t'
    'ail-history-1-30-call10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-0'
    '1-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-hi'
    'story-1-30-call10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-histor'
    'y-1-30-call10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15'
    ':30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-1'
    '-30-call10-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"t'
    'ail-history-1-30-call10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\'
    '"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"'
    'tail-history-1-30-call25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"ta'
    'il-history-1-30-call25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"203'
    '0-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail'
    '-history-1-30-call25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":['
    '\\"tail-history-1-30-call25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"203'
    '0-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail'
    '-history-1-30-call25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-his'
    'tory-1-30-call25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02'
    'T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-histor'
    'y-1-30-call25-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":['
    '\\"tail-history-1-30-call25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\'
    '":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\"'
    ',\\"tail-history-1-30-put10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"'
    'tail-history-1-30-put10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"20'
    '30-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tai'
    'l-history-1-30-put10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":['
    '\\"tail-history-1-30-put10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030'
    '-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-'
    'history-1-30-put10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-histo'
    'ry-1-30-put10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15'
    ':30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-1'
    '-30-put10-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ta'
    'il-history-1-30-put10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2'
    '030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ta'
    'il-history-1-30-put25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-'
    'history-1-30-put25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01'
    '-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-his'
    'tory-1-30-put25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tai'
    'l-history-1-30-put25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-0'
    '2T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-histo'
    'ry-1-30-put25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-1-'
    '30-put25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:0'
    '0.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-1-30-p'
    'ut25-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-hi'
    'story-1-30-put25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-0'
    '1-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-hi'
    'story-1-60-atm-call-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-hi'
    'story-1-60-atm-call-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-0'
    '1-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-hi'
    'story-1-60-atm-call-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\'
    '"tail-history-1-60-atm-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"20'
    '30-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tai'
    'l-history-1-60-atm-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-'
    'history-1-60-atm-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-'
    '01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-h'
    'istory-1-60-atm-call-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$l'
    'ist\\":[\\"tail-history-1-60-atm-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$'
    'datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"re'
    'cord_id\\",\\"tail-history-1-60-atm-put-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"'
    '$list\\":[\\"tail-history-1-60-atm-put-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$da'
    'tetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"reco'
    'rd_id\\",\\"tail-history-1-60-atm-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids'
    '\\",{\\"$list\\":[\\"tail-history-1-60-atm-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$'
    'datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"re'
    'cord_id\\",\\"tail-history-1-60-atm-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$l'
    'ist\\":[\\"tail-history-1-60-atm-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datet'
    'ime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_'
    'id\\",\\"tail-history-1-60-atm-put-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source'
    '_ids\\",{\\"$list\\":[\\"tail-history-1-60-atm-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalize'
    'd_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\"'
    ':[]}],[\\"record_id\\",\\"tail-history-1-60-call10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source'
    '_ids\\",{\\"$list\\":[\\"tail-history-1-60-call10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at'
    '\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}'
    '],[\\"record_id\\",\\"tail-history-1-60-call10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"so'
    'urce_ids\\",{\\"$list\\":[\\"tail-history-1-60-call10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at'
    '\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}'
    '],[\\"record_id\\",\\"tail-history-1-60-call10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\"'
    ',{\\"$list\\":[\\"tail-history-1-60-call10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$'
    'datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"re'
    'cord_id\\",\\"tail-history-1-60-call10-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"so'
    'urce_ids\\",{\\"$list\\":[\\"tail-history-1-60-call10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normal'
    'ized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$lis'
    't\\":[]}],[\\"record_id\\",\\"tail-history-1-60-call25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"sou'
    'rce_ids\\",{\\"$list\\":[\\"tail-history-1-60-call25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized'
    '_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":'
    '[]}],[\\"record_id\\",\\"tail-history-1-60-call25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\'
    '"source_ids\\",{\\"$list\\":[\\"tail-history-1-60-call25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized'
    '_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":'
    '[]}],[\\"record_id\\",\\"tail-history-1-60-call25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_id'
    's\\",{\\"$list\\":[\\"tail-history-1-60-call25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{'
    '\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\'
    '"record_id\\",\\"tail-history-1-60-call25-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\'
    '"source_ids\\",{\\"$list\\":[\\"tail-history-1-60-call25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"nor'
    'malized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$'
    'list\\":[]}],[\\"record_id\\",\\"tail-history-1-60-put10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"s'
    'ource_ids\\",{\\"$list\\":[\\"tail-history-1-60-put10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalize'
    'd_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\"'
    ':[]}],[\\"record_id\\",\\"tail-history-1-60-put10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\'
    '"source_ids\\",{\\"$list\\":[\\"tail-history-1-60-put10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_'
    'at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":['
    ']}],[\\"record_id\\",\\"tail-history-1-60-put10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\'
    '",{\\"$list\\":[\\"tail-history-1-60-put10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$'
    'datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"re'
    'cord_id\\",\\"tail-history-1-60-put10-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"sou'
    'rce_ids\\",{\\"$list\\":[\\"tail-history-1-60-put10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normaliz'
    'ed_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\'
    '":[]}],[\\"record_id\\",\\"tail-history-1-60-put25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source'
    '_ids\\",{\\"$list\\":[\\"tail-history-1-60-put25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\'
    '",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}]'
    ',[\\"record_id\\",\\"tail-history-1-60-put25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"sour'
    'ce_ids\\",{\\"$list\\":[\\"tail-history-1-60-put25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",'
    '{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],['
    '\\"record_id\\",\\"tail-history-1-60-put25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"'
    '$list\\":[\\"tail-history-1-60-put25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datet'
    'ime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_'
    'id\\",\\"tail-history-1-60-put25-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_i'
    'ds\\",{\\"$list\\":[\\"tail-history-1-60-put25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at'
    '\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}'
    '],[\\"record_id\\",\\"tail-history-1-60-underlying\\"],[\\"role\\",\\"underlying_quote\\"],[\\"source_ids'
    '\\",{\\"$list\\":[\\"tail-history-1-60-underlying-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$'
    'datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"re'
    'cord_id\\",\\"tail-history-2-30-call10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$'
    'list\\":[\\"tail-history-2-30-call10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$date'
    'time\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record'
    '_id\\",\\"tail-history-2-30-call10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",'
    '{\\"$list\\":[\\"tail-history-2-30-call10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$date'
    'time\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record'
    '_id\\",\\"tail-history-2-30-call10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\"'
    ':[\\"tail-history-2-30-call10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":'
    '\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\'
    '"tail-history-2-30-call10-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",'
    '{\\"$list\\":[\\"tail-history-2-30-call10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{'
    '\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\'
    '"record_id\\",\\"tail-history-2-30-call25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{'
    '\\"$list\\":[\\"tail-history-2-30-call25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$d'
    'atetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"rec'
    'ord_id\\",\\"tail-history-2-30-call25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids'
    '\\",{\\"$list\\":[\\"tail-history-2-30-call25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$d'
    'atetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"rec'
    'ord_id\\",\\"tail-history-2-30-call25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$lis'
    't\\":[\\"tail-history-2-30-call25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime'
    '\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\'
    '",\\"tail-history-2-30-call25-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids'
    '\\",{\\"$list\\":[\\"tail-history-2-30-call25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\'
    '",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}]'
    ',[\\"record_id\\",\\"tail-history-2-30-put10-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\"'
    ',{\\"$list\\":[\\"tail-history-2-30-put10-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$'
    'datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"re'
    'cord_id\\",\\"tail-history-2-30-put10-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids'
    '\\",{\\"$list\\":[\\"tail-history-2-30-put10-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$da'
    'tetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"reco'
    'rd_id\\",\\"tail-history-2-30-put10-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\'
    '":[\\"tail-history-2-30-put10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":'
    '\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\'
    '"tail-history-2-30-put10-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{'
    '\\"$list\\":[\\"tail-history-2-30-put10-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"'
    '$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"r'
    'ecord_id\\",\\"tail-history-2-30-put25-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$'
    'list\\":[\\"tail-history-2-30-put25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datet'
    'ime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_'
    'id\\",\\"tail-history-2-30-put25-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\'
    '"$list\\":[\\"tail-history-2-30-put25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetim'
    'e\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id'
    '\\",\\"tail-history-2-30-put25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"'
    'tail-history-2-30-put25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"203'
    '0-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail'
    '-history-2-30-put25-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$li'
    'st\\":[\\"tail-history-2-30-put25-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$date'
    'time\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record'
    '_id\\",\\"tail-history-2-60-atm-call-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$li'
    'st\\":[\\"tail-history-2-60-atm-call-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$date'
    'time\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record'
    '_id\\",\\"tail-history-2-60-atm-call-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\'
    '",{\\"$list\\":[\\"tail-history-2-60-atm-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$'
    'datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"re'
    'cord_id\\",\\"tail-history-2-60-atm-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$'
    'list\\":[\\"tail-history-2-60-atm-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$dat'
    'etime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"recor'
    'd_id\\",\\"tail-history-2-60-atm-call-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"sou'
    'rce_ids\\",{\\"$list\\":[\\"tail-history-2-60-atm-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"norma'
    'lized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$li'
    'st\\":[]}],[\\"record_id\\",\\"tail-history-2-60-atm-put-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"s'
    'ource_ids\\",{\\"$list\\":[\\"tail-history-2-60-atm-put-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normali'
    'zed_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list'
    '\\":[]}],[\\"record_id\\",\\"tail-history-2-60-atm-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"'
    '],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-atm-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"norma'
    'lized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$li'
    'st\\":[]}],[\\"record_id\\",\\"tail-history-2-60-atm-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"sou'
    'rce_ids\\",{\\"$list\\":[\\"tail-history-2-60-atm-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized'
    '_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":'
    '[]}],[\\"record_id\\",\\"tail-history-2-60-atm-put-reference\\"],[\\"role\\",\\"option_contract_referen'
    'ce\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-atm-put-reference-source-0\\"]}]]},{\\"$map\\'
    '":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_fla'
    'gs\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-call10-greeks\\"],[\\"role\\",\\"option_gree'
    'ks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-call10-greeks-source-0\\"]}]]},{\\"$map\\":[['
    '\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\"'
    ',{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-call10-iv\\"],[\\"role\\",\\"option_implied_vola'
    'tility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-call10-iv-source-0\\"]}]]},{\\"$map\\":[['
    '\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\"'
    ',{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-call10-quote\\"],[\\"role\\",\\"option_quote\\"],'
    '[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-call10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"norma'
    'lized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$li'
    'st\\":[]}],[\\"record_id\\",\\"tail-history-2-60-call10-reference\\"],[\\"role\\",\\"option_contract_ref'
    'erence\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-call10-reference-source-0\\"]}]]},{\\"$m'
    'ap\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_'
    'flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-call25-greeks\\"],[\\"role\\",\\"option_g'
    'reeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-call25-greeks-source-0\\"]}]]},{\\"$map\\"'
    ':[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flag'
    's\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-call25-iv\\"],[\\"role\\",\\"option_implied_v'
    'olatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-call25-iv-source-0\\"]}]]},{\\"$map\\"'
    ':[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flag'
    's\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-call25-quote\\"],[\\"role\\",\\"option_quote\\'
    '"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-call25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"no'
    'rmalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"'
    '$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-call25-reference\\"],[\\"role\\",\\"option_contract_'
    'reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-call25-reference-source-0\\"]}]]},{\\'
    '"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quali'
    'ty_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-put10-greeks\\"],[\\"role\\",\\"option'
    '_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-put10-greeks-source-0\\"]}]]},{\\"$map\\'
    '":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_fla'
    'gs\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-put10-iv\\"],[\\"role\\",\\"option_implied_v'
    'olatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-put10-iv-source-0\\"]}]]},{\\"$map\\":'
    '[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags'
    '\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-put10-quote\\"],[\\"role\\",\\"option_quote\\"]'
    ',[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-put10-quote-source-0\\"]}]]},{\\"$map\\":[[\\"norma'
    'lized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$li'
    'st\\":[]}],[\\"record_id\\",\\"tail-history-2-60-put10-reference\\"],[\\"role\\",\\"option_contract_refe'
    'rence\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-put10-reference-source-0\\"]}]]},{\\"$map'
    '\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_fl'
    'ags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-put25-greeks\\"],[\\"role\\",\\"option_gree'
    'ks\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-put25-greeks-source-0\\"]}]]},{\\"$map\\":[[\\'
    '"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",'
    '{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-put25-iv\\"],[\\"role\\",\\"option_implied_volati'
    'lity\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-put25-iv-source-0\\"]}]]},{\\"$map\\":[[\\"n'
    'ormalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\'
    '"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-put25-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"s'
    'ource_ids\\",{\\"$list\\":[\\"tail-history-2-60-put25-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized'
    '_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":'
    '[]}],[\\"record_id\\",\\"tail-history-2-60-put25-reference\\"],[\\"role\\",\\"option_contract_reference'
    '\\"],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-put25-reference-source-0\\"]}]]},{\\"$map\\":[['
    '\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\"'
    ',{\\"$list\\":[]}],[\\"record_id\\",\\"tail-history-2-60-underlying\\"],[\\"role\\",\\"underlying_quote\\"'
    '],[\\"source_ids\\",{\\"$list\\":[\\"tail-history-2-60-underlying-source-0\\"]}]]},{\\"$map\\":[[\\"norma'
    'lized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$li'
    'st\\":[]}],[\\"record_id\\",\\"ve-current-0-call-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_id'
    's\\",{\\"$list\\":[\\"ve-current-0-call-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$dat'
    'etime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"recor'
    'd_id\\",\\"ve-current-0-call-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$li'
    'st\\":[\\"ve-current-0-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030'
    '-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-cu'
    'rrent-0-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-cal'
    'l-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.00000'
    '2Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-call-referenc'
    'e\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-call-re'
    'ference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.00000'
    '2Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-put-greeks\\"]'
    ',[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-put-greeks-source-0\\"]}'
    ']]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated'
    '_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-put-iv\\"],[\\"role\\",\\"option_impl'
    'ied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-put-iv-source-0\\"]}]]},{\\"$map\\":[['
    '\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\"'
    ',{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"sourc'
    'e_ids\\",{\\"$list\\":[\\"ve-current-0-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$d'
    'atetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"rec'
    'ord_id\\",\\"ve-current-0-put-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\'
    '",{\\"$list\\":[\\"ve-current-0-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$dat'
    'etime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"recor'
    'd_id\\",\\"ve-current-1-call-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"'
    've-current-1-call-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-'
    '02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-curren'
    't-1-call-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current'
    '-1-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.00'
    '0002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-call-quote'
    '\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-call-quote-source-0\\"'
    ']}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagat'
    'ed_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-call-reference\\"],[\\"role\\",\\"o'
    'ption_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-call-reference-source-0\\"'
    ']}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagat'
    'ed_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-put-greeks\\"],[\\"role\\",\\"optio'
    'n_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-put-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"'
    'normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{'
    '\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],'
    '[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",'
    '{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],['
    '\\"record_id\\",\\"ve-current-1-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\"'
    ':[\\"ve-current-1-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-0'
    '1-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-curr'
    'ent-1-put-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve'
    '-current-1-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-'
    '02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-curren'
    't-underlying\\"],[\\"role\\",\\"underlying_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-underly'
    'ing-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"'
    '}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-call-greeks\\"],'
    '[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-greeks-source-0\\"'
    ']}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagat'
    'ed_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-call-iv\\"],[\\"role\\",\\"option'
    '_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-iv-source-0\\"]}]]},{\\"$'
    'map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality'
    '_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-call-quote\\"],[\\"role\\",\\"option_quote\\'
    '"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normali'
    'zed_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list'
    '\\":[]}],[\\"record_id\\",\\"ve-history-0-0-call-reference\\"],[\\"role\\",\\"option_contract_reference\\'
    '"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"nor'
    'malized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$'
    'list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-put-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source'
    '_ids\\",{\\"$list\\":[\\"ve-history-0-0-put-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"'
    '$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"r'
    'ecord_id\\",\\"ve-history-0-0-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{'
    '\\"$list\\":[\\"ve-history-0-0-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":'
    '\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\'
    '"ve-history-0-0-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-histor'
    'y-0-0-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:'
    '00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-put'
    '-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-'
    '0-0-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:3'
    '0:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-und'
    'erlying\\"],[\\"role\\",\\"underlying_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-underlying'
    '-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],'
    '[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-1-0-call-greeks\\"],[\\"'
    'role\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0-call-greeks-source-0\\"]}]'
    ']},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_'
    'quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-1-0-call-iv\\"],[\\"role\\",\\"option_im'
    'plied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0-call-iv-source-0\\"]}]]},{\\"$map'
    '\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_fl'
    'ags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-1-0-call-quote\\"],[\\"role\\",\\"option_quote\\"],'
    '[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized'
    '_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":'
    '[]}],[\\"record_id\\",\\"ve-history-1-0-call-reference\\"],[\\"role\\",\\"option_contract_reference\\"],'
    '[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normal'
    'ized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$lis'
    't\\":[]}],[\\"record_id\\",\\"ve-history-1-0-put-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_id'
    's\\",{\\"$list\\":[\\"ve-history-1-0-put-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$da'
    'tetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"reco'
    'rd_id\\",\\"ve-history-1-0-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$'
    'list\\":[\\"ve-history-1-0-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2'
    '030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve'
    '-history-1-0-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1'
    '-0-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.'
    '000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-1-0-put-re'
    'ference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0'
    '-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:0'
    '0.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-1-underl'
    'ying\\"],[\\"role\\",\\"underlying_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-underlying-so'
    'urce-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"'
    'propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-2-0-call-greeks\\"],[\\"rol'
    'e\\",\\"option_greeks\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-0-call-greeks-source-0\\"]}]]},'
    '{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_qua'
    'lity_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-2-0-call-iv\\"],[\\"role\\",\\"option_impli'
    'ed_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-0-call-iv-source-0\\"]}]]},{\\"$map\\":'
    '[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags'
    '\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-2-0-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"'
    'source_ids\\",{\\"$list\\":[\\"ve-history-2-0-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at'
    '\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}'
    '],[\\"record_id\\",\\"ve-history-2-0-call-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"'
    'source_ids\\",{\\"$list\\":[\\"ve-history-2-0-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalize'
    'd_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\"'
    ':[]}],[\\"record_id\\",\\"ve-history-2-0-put-greeks\\"],[\\"role\\",\\"option_greeks\\"],[\\"source_ids\\"'
    ',{\\"$list\\":[\\"ve-history-2-0-put-greeks-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datet'
    'ime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_'
    'id\\",\\"ve-history-2-0-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$lis'
    't\\":[\\"ve-history-2-0-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030'
    '-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-hi'
    'story-2-0-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-0-'
    'put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000'
    '002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-2-0-put-refer'
    'ence\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-0-pu'
    't-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.0'
    '00002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-2-underlyin'
    'g\\"],[\\"role\\",\\"underlying_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-underlying-sourc'
    'e-0\\"]}]]}]}]]}],[\\"same_contract_reuse_rule\\",\\"reject_same_economic_contract_across_10_and_25_'
    'same_side\\"],[\\"skew_percentile_formula\\",\\"inclusive_count_historical_downside_25_skew_lte_curr'
    'ent_divided_by_count\\"],[\\"skew_term_structure_ordering\\",\\"ascending_days_to_expiration_then_ex'
    'piration\\"],[\\"tail_output_architecture\\",\\"ordered_tail_pricing_slice_tuple\\"],[\\"target_deltas'
    '\\",{\\"$map\\":[[\\"call_10\\",{\\"$decimal\\":\\"0.10\\"}],[\\"call_25\\",{\\"$decimal\\":\\"0.25\\"}],[\\"put'
    '_10\\",{\\"$decimal\\":\\"-0.10\\"}],[\\"put_25\\",{\\"$decimal\\":\\"-0.25\\"}]]}],[\\"volatility_unit\\",\\"'
    'annualized_decimal_ratio\\"]]}"],["quality_flags",{"$list":["decimal_to_float_converted","annuali'
    'zed","assumption_applied"]}]]}],["records",{"$list":[{"$map":[["as_of_date",{"$date":"2030-01-02'
    '"}],["atm_iv_float_repr","0.3"],["call_10_delta_iv_float_repr","0.26"],["call_25_delta_iv_float_'
    'repr","0.28"],["delta_methodology","{\\"$map\\":[[\\"delta_basis\\",\\"spot\\"],[\\"interpolation_metho'
    'dology\\",\\"none\\"],[\\"model_provider_methodology\\",\\"Synthetic Black-Scholes provider delta\\"],['
    '\\"premium_adjustment\\",\\"unadjusted\\"],[\\"signed_delta_convention\\",\\"call_positive_put_negative'
    '\\"],[\\"target_selection_methodology\\",\\"nearest_observed_signed_delta\\"]]}"],["expiration",{"$da'
    'te":"2030-02-01"}],["put_10_delta_iv_float_repr","0.42"],["put_25_delta_iv_float_repr","0.36"],['
    '"skew_history_lookback_observations",3],["skew_percentile_float_repr","0.6666666666666666"],["un'
    'derlying","SPY"]]},{"$map":[["as_of_date",{"$date":"2030-01-02"}],["atm_iv_float_repr","0.4"],["'
    'call_10_delta_iv_float_repr","0.36"],["call_25_delta_iv_float_repr","0.38"],["delta_methodology"'
    ',"{\\"$map\\":[[\\"delta_basis\\",\\"spot\\"],[\\"interpolation_methodology\\",\\"none\\"],[\\"model_provid'
    'er_methodology\\",\\"Synthetic Black-Scholes provider delta\\"],[\\"premium_adjustment\\",\\"unadjuste'
    'd\\"],[\\"signed_delta_convention\\",\\"call_positive_put_negative\\"],[\\"target_selection_methodolog'
    'y\\",\\"nearest_observed_signed_delta\\"]]}"],["expiration",{"$date":"2030-03-03"}],["put_10_delta_'
    'iv_float_repr","0.52"],["put_25_delta_iv_float_repr","0.46"],["skew_history_lookback_observation'
    's",3],["skew_percentile_float_repr","0.6666666666666666"],["underlying","SPY"]]}]}],["wrapper_ty'
    'pe","TailPricingTransformationResult"]]}],["volatility_environment_result",{"$map":[["lineage",{'
    '"$map":[["calculated_at",{"$datetime":"2030-01-02T15:30:04.000000Z"}],["calculation_id","calcula'
    'tion-3c7d"],["calculation_type","volatility_environment"],["inputs",{"$list":[{"$map":[["normali'
    'zed_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-0"],["source_ids",{"$list'
    '":["hrv-0-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],'
    '["record_id","hrv-1"],["source_ids",{"$list":["hrv-1-source-0"]}]]},{"$map":[["normalized_at",{"'
    '$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","hrv-2"],["source_ids",{"$list":["hrv-2-'
    'source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_i'
    'd","ve-current-0-call-iv"],["source_ids",{"$list":["ve-current-0-call-iv-source-0"]}]]},{"$map":'
    '[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-call-q'
    'uote"],["source_ids",{"$list":["ve-current-0-call-quote-source-0"]}]]},{"$map":[["normalized_at"'
    ',{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-call-reference"],["sour'
    'ce_ids",{"$list":["ve-current-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datet'
    'ime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-0-put-iv"],["source_ids",{"$list":'
    '["ve-current-0-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","ve-current-0-put-quote"],["source_ids",{"$list":["ve-current-0-put-quo'
    'te-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["recor'
    'd_id","ve-current-0-put-reference"],["source_ids",{"$list":["ve-current-0-put-reference-source-0'
    '"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-c'
    'urrent-1-call-iv"],["source_ids",{"$list":["ve-current-1-call-iv-source-0"]}]]},{"$map":[["norma'
    'lized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-call-quote"],['
    '"source_ids",{"$list":["ve-current-1-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$date'
    'time":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-call-reference"],["source_ids",'
    '{"$list":["ve-current-1-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"20'
    '30-01-02T15:30:00.000002Z"}],["record_id","ve-current-1-put-iv"],["source_ids",{"$list":["ve-cur'
    'rent-1-put-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z'
    '"}],["record_id","ve-current-1-put-quote"],["source_ids",{"$list":["ve-current-1-put-quote-sourc'
    'e-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","v'
    'e-current-1-put-reference"],["source_ids",{"$list":["ve-current-1-put-reference-source-0"]}]]},{'
    '"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-current-u'
    'nderlying"],["source_ids",{"$list":["ve-current-underlying-source-0"]}]]},{"$map":[["normalized_'
    'at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-call-iv"],["source'
    '_ids",{"$list":["ve-history-0-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2'
    '030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-0-call-quote"],["source_ids",{"$list":['
    '"ve-history-0-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:'
    '30:00.000002Z"}],["record_id","ve-history-0-0-call-reference"],["source_ids",{"$list":["ve-histo'
    'ry-0-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00'
    '.000002Z"}],["record_id","ve-history-0-0-put-iv"],["source_ids",{"$list":["ve-history-0-0-put-iv'
    '-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_'
    'id","ve-history-0-0-put-quote"],["source_ids",{"$list":["ve-history-0-0-put-quote-source-0"]}]]}'
    ',{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history'
    '-0-0-put-reference"],["source_ids",{"$list":["ve-history-0-0-put-reference-source-0"]}]]},{"$map'
    '":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-0-unde'
    'rlying"],["source_ids",{"$list":["ve-history-0-underlying-source-0"]}]]},{"$map":[["normalized_a'
    't",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-0-call-iv"],["source_'
    'ids",{"$list":["ve-history-1-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"20'
    '30-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-0-call-quote"],["source_ids",{"$list":["'
    've-history-1-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:3'
    '0:00.000002Z"}],["record_id","ve-history-1-0-call-reference"],["source_ids",{"$list":["ve-histor'
    'y-1-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.'
    '000002Z"}],["record_id","ve-history-1-0-put-iv"],["source_ids",{"$list":["ve-history-1-0-put-iv-'
    'source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_i'
    'd","ve-history-1-0-put-quote"],["source_ids",{"$list":["ve-history-1-0-put-quote-source-0"]}]]},'
    '{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-'
    '1-0-put-reference"],["source_ids",{"$list":["ve-history-1-0-put-reference-source-0"]}]]},{"$map"'
    ':[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-1-under'
    'lying"],["source_ids",{"$list":["ve-history-1-underlying-source-0"]}]]},{"$map":[["normalized_at'
    '",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-0-call-iv"],["source_i'
    'ds",{"$list":["ve-history-2-0-call-iv-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"203'
    '0-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-0-call-quote"],["source_ids",{"$list":["v'
    'e-history-2-0-call-quote-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30'
    ':00.000002Z"}],["record_id","ve-history-2-0-call-reference"],["source_ids",{"$list":["ve-history'
    '-2-0-call-reference-source-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.0'
    '00002Z"}],["record_id","ve-history-2-0-put-iv"],["source_ids",{"$list":["ve-history-2-0-put-iv-s'
    'ource-0"]}]]},{"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id'
    '","ve-history-2-0-put-quote"],["source_ids",{"$list":["ve-history-2-0-put-quote-source-0"]}]]},{'
    '"$map":[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2'
    '-0-put-reference"],["source_ids",{"$list":["ve-history-2-0-put-reference-source-0"]}]]},{"$map":'
    '[["normalized_at",{"$datetime":"2030-01-02T15:30:00.000002Z"}],["record_id","ve-history-2-underl'
    'ying"],["source_ids",{"$list":["ve-history-2-underlying-source-0"]}]]}]}],["methodology_id","pai'
    'red-atm-volatility-environment"],["methodology_version","v0.2"],["parameters_json","{\\"$map\\":[['
    '\\"atm_candidate_universe\\",{\\"$map\\":[[\\"completeness_semantics\\",\\"no_eligible_paired_call_put_'
    'strike_omitted\\"],[\\"declared_complete\\",true],[\\"scope\\",\\"all_exact_selected_session_expiratio'
    'n_universes\\"]]}],[\\"atm_selection_rule\\",\\"nearest_paired_call_put_strike_to_underlying_bid_ask'
    '_midpoint\\"],[\\"call_put_combination_rule\\",\\"arithmetic_mean_of_same_strike_call_and_put_implie'
    'd_volatility\\"],[\\"current_observations\\",{\\"$list\\":[{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\"'
    ':[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve-current-0-call-reference\\"],[\\"call_imp'
    'lied_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"call_iv_record_id\\",\\"ve-current-0-call-iv\\"],[\\"c'
    'all_quote_record_id\\",\\"ve-current-0-call-quote\\"],[\\"contract_multiplier\\",100],[\\"currency\\",\\'
    '"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\",{\\"$decimal\\":\\"0.0\\"}],['
    '\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.300\\"}],[\\"put_contract_reference_record_id\\",\\"'
    've-current-0-put-reference\\"],[\\"put_implied_volatility\\",{\\"$decimal\\":\\"0.30\\"}],[\\"put_iv_rec'
    'ord_id\\",\\"ve-current-0-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-current-0-put-quote\\"],[\\"strike'
    '\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"2030-02-01\\"}],[\\"selected_atm_iv\\"'
    ',{\\"$decimal\\":\\"0.300\\"}],[\\"selected_call_iv_record_id\\",\\"ve-current-0-call-iv\\"],[\\"selected'
    '_put_iv_record_id\\",\\"ve-current-0-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"100\\"}],[\\"ses'
    'sion_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"tenor_days\\",30],[\\"underlying_midpoint\\",{\\"$decimal'
    '\\":\\"100.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-current-underlying\\"]]},{\\"$map\\":[[\\"candid'
    'ate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve-current-1-call-re'
    'ference\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.40\\"}],[\\"call_iv_record_id\\",\\"ve-cur'
    'rent-1-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-current-1-call-quote\\"],[\\"contract_multiplier\\'
    '",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\",{\\"'
    '$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.400\\"}],[\\"put_contract_re'
    'ference_record_id\\",\\"ve-current-1-put-reference\\"],[\\"put_implied_volatility\\",{\\"$decimal\\":\\"'
    '0.40\\"}],[\\"put_iv_record_id\\",\\"ve-current-1-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-current-1-'
    'put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"2030-03-03\\"}'
    '],[\\"selected_atm_iv\\",{\\"$decimal\\":\\"0.400\\"}],[\\"selected_call_iv_record_id\\",\\"ve-current-1-'
    'call-iv\\"],[\\"selected_put_iv_record_id\\",\\"ve-current-1-put-iv\\"],[\\"selected_strike\\",{\\"$deci'
    'mal\\":\\"100\\"}],[\\"session_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"tenor_days\\",60],[\\"underlying_'
    'midpoint\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-current-underlying\\"]]'
    '}]}],[\\"float_conversion_rule\\",\\"convert_only_final_decimal_research_values_to_finite_float\\"],'
    '[\\"historical_expected_session_dates\\",{\\"$list\\":[{\\"$date\\":\\"2029-12-24\\"},{\\"$date\\":\\"2029-'
    '12-27\\"},{\\"$date\\":\\"2029-12-30\\"}]}],[\\"historical_matched_tenor_rule\\",\\"expiration_minus_ses'
    'sion_date_calendar_days_equals_reference_tenor\\"],[\\"historical_observation_count\\",3],[\\"histor'
    'ical_observations\\",{\\"$list\\":[{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_c'
    'ontract_reference_record_id\\",\\"ve-history-0-0-call-reference\\"],[\\"call_implied_volatility\\",{\\'
    '"$decimal\\":\\"0.19\\"}],[\\"call_iv_record_id\\",\\"ve-history-0-0-call-iv\\"],[\\"call_quote_record_i'
    'd\\",\\"ve-history-0-0-call-quote\\"],[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliv'
    'erable_id\\",null],[\\"distance_to_underlying_midpoint\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied'
    '_volatility\\",{\\"$decimal\\":\\"0.200\\"}],[\\"put_contract_reference_record_id\\",\\"ve-history-0-0-p'
    'ut-reference\\"],[\\"put_implied_volatility\\",{\\"$decimal\\":\\"0.21\\"}],[\\"put_iv_record_id\\",\\"ve-'
    'history-0-0-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-history-0-0-put-quote\\"],[\\"strike\\",{\\"$dec'
    'imal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"2030-01-23\\"}],[\\"selected_atm_iv\\",{\\"$decim'
    'al\\":\\"0.200\\"}],[\\"selected_call_iv_record_id\\",\\"ve-history-0-0-call-iv\\"],[\\"selected_put_iv_'
    'record_id\\",\\"ve-history-0-0-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"100\\"}],[\\"session_d'
    'ate\\",{\\"$date\\":\\"2029-12-24\\"}],[\\"tenor_days\\",30],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"1'
    '00.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-history-0-underlying\\"]]},{\\"$map\\":[[\\"candidate_'
    'pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_reference_record_id\\",\\"ve-history-1-0-call-refe'
    'rence\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.20\\"}],[\\"call_iv_record_id\\",\\"ve-histo'
    'ry-1-0-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-history-1-0-call-quote\\"],[\\"contract_multiplie'
    'r\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null],[\\"distance_to_underlying_midpoint\\",{'
    '\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\"$decimal\\":\\"0.210\\"}],[\\"put_contract_'
    'reference_record_id\\",\\"ve-history-1-0-put-reference\\"],[\\"put_implied_volatility\\",{\\"$decimal\\'
    '":\\"0.22\\"}],[\\"put_iv_record_id\\",\\"ve-history-1-0-put-iv\\"],[\\"put_quote_record_id\\",\\"ve-hist'
    'ory-1-0-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]]}]}],[\\"expiration\\",{\\"$date\\":\\"2030-'
    '01-26\\"}],[\\"selected_atm_iv\\",{\\"$decimal\\":\\"0.210\\"}],[\\"selected_call_iv_record_id\\",\\"ve-hi'
    'story-1-0-call-iv\\"],[\\"selected_put_iv_record_id\\",\\"ve-history-1-0-put-iv\\"],[\\"selected_strik'
    'e\\",{\\"$decimal\\":\\"100\\"}],[\\"session_date\\",{\\"$date\\":\\"2029-12-27\\"}],[\\"tenor_days\\",30],[\\'
    '"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}],[\\"underlying_quote_record_id\\",\\"ve-history-1-'
    'underlying\\"]]},{\\"$map\\":[[\\"candidate_pairs\\",{\\"$list\\":[{\\"$map\\":[[\\"call_contract_referenc'
    'e_record_id\\",\\"ve-history-2-0-call-reference\\"],[\\"call_implied_volatility\\",{\\"$decimal\\":\\"0.'
    '21\\"}],[\\"call_iv_record_id\\",\\"ve-history-2-0-call-iv\\"],[\\"call_quote_record_id\\",\\"ve-history'
    '-2-0-call-quote\\"],[\\"contract_multiplier\\",100],[\\"currency\\",\\"USD\\"],[\\"deliverable_id\\",null'
    '],[\\"distance_to_underlying_midpoint\\",{\\"$decimal\\":\\"0.0\\"}],[\\"paired_implied_volatility\\",{\\'
    '"$decimal\\":\\"0.220\\"}],[\\"put_contract_reference_record_id\\",\\"ve-history-2-0-put-reference\\"],'
    '[\\"put_implied_volatility\\",{\\"$decimal\\":\\"0.23\\"}],[\\"put_iv_record_id\\",\\"ve-history-2-0-put-'
    'iv\\"],[\\"put_quote_record_id\\",\\"ve-history-2-0-put-quote\\"],[\\"strike\\",{\\"$decimal\\":\\"100\\"}]'
    ']}]}],[\\"expiration\\",{\\"$date\\":\\"2030-01-29\\"}],[\\"selected_atm_iv\\",{\\"$decimal\\":\\"0.220\\"}]'
    ',[\\"selected_call_iv_record_id\\",\\"ve-history-2-0-call-iv\\"],[\\"selected_put_iv_record_id\\",\\"ve'
    '-history-2-0-put-iv\\"],[\\"selected_strike\\",{\\"$decimal\\":\\"100\\"}],[\\"session_date\\",{\\"$date\\"'
    ':\\"2029-12-30\\"}],[\\"tenor_days\\",30],[\\"underlying_midpoint\\",{\\"$decimal\\":\\"100.0\\"}],[\\"unde'
    'rlying_quote_record_id\\",\\"ve-history-2-underlying\\"]]}]}],[\\"historical_sample_semantics\\",\\"ca'
    'ller_declared_observation_sample\\"],[\\"iv_methodology\\",{\\"$map\\":[[\\"dividend_input_description'
    '\\",\\"Synthetic dividend input\\"],[\\"model_name\\",\\"Synthetic Black-Scholes\\"],[\\"model_version\\"'
    ',\\"fixture-v1\\"],[\\"rate_input_description\\",\\"Synthetic USD curve input\\"],[\\"unit_convention\\"'
    ',\\"annualized_decimal_ratio\\"]]}],[\\"median_formula\\",\\"odd_middle_even_arithmetic_mean_of_two_m'
    'iddle_values\\"],[\\"normalized_evidence\\",{\\"$map\\":[[\\"direct_inputs\\",{\\"$list\\":[{\\"$map\\":[[\\'
    '"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",'
    '{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-call-iv\\"],[\\"role\\",\\"option_implied_volatility\\"'
    '],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at'
    '\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}'
    '],[\\"record_id\\",\\"ve-current-0-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$li'
    'st\\":[\\"ve-current-0-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2'
    '030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve'
    '-current-0-call-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\"'
    ':[\\"ve-current-0-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2'
    '030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve'
    '-current-0-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-c'
    'urrent-0-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:'
    '00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-put-q'
    'uote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-put-quote-source-'
    '0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propa'
    'gated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-0-put-reference\\"],[\\"role\\",\\'
    '"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-0-put-reference-source-0\\'
    '"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propaga'
    'ted_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-call-iv\\"],[\\"role\\",\\"option_'
    'implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-call-iv-source-0\\"]}]]},{\\"$map'
    '\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_fl'
    'ags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\'
    '"source_ids\\",{\\"$list\\":[\\"ve-current-1-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\'
    '",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}]'
    ',[\\"record_id\\",\\"ve-current-1-call-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"sou'
    'rce_ids\\",{\\"$list\\":[\\"ve-current-1-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\'
    '",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}]'
    ',[\\"record_id\\",\\"ve-current-1-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\'
    '",{\\"$list\\":[\\"ve-current-1-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\"'
    ':\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",'
    '\\"ve-current-1-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current'
    '-1-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.'
    '000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-1-put-refe'
    'rence\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-1-put'
    '-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.00'
    '0002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-current-underlying\\"'
    '],[\\"role\\",\\"underlying_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-current-underlying-source-0\\"'
    ']}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagat'
    'ed_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-call-iv\\"],[\\"role\\",\\"option'
    '_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-iv-source-0\\"]}]]},{\\"$'
    'map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality'
    '_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-call-quote\\"],[\\"role\\",\\"option_quote\\'
    '"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normali'
    'zed_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list'
    '\\":[]}],[\\"record_id\\",\\"ve-history-0-0-call-reference\\"],[\\"role\\",\\"option_contract_reference\\'
    '"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"nor'
    'malized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$'
    'list\\":[]}],[\\"record_id\\",\\"ve-history-0-0-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],['
    '\\"source_ids\\",{\\"$list\\":[\\"ve-history-0-0-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\"'
    ',{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],'
    '[\\"record_id\\",\\"ve-history-0-0-put-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$lis'
    't\\":[\\"ve-history-0-0-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2'
    '030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve'
    '-history-0-0-put-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\'
    '":[\\"ve-history-0-0-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\'
    '"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"'
    've-history-0-underlying\\"],[\\"role\\",\\"underlying_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-hist'
    'ory-0-underlying-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30'
    ':00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-1-0-ca'
    'll-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0-c'
    'all-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002'
    'Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-1-0-call-quote\\"'
    '],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0-call-quote-source-0\\"'
    ']}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagat'
    'ed_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-1-0-call-reference\\"],[\\"role\\",\\'
    '"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0-call-reference-source'
    '-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"prop'
    'agated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-1-0-put-iv\\"],[\\"role\\",\\"opt'
    'ion_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0-put-iv-source-0\\"]}]]},{\\'
    '"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quali'
    'ty_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-1-0-put-quote\\"],[\\"role\\",\\"option_quote'
    '\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0-put-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normali'
    'zed_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list'
    '\\":[]}],[\\"record_id\\",\\"ve-history-1-0-put-reference\\"],[\\"role\\",\\"option_contract_reference\\"'
    '],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-1-0-put-reference-source-0\\"]}]]},{\\"$map\\":[[\\"norma'
    'lized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$li'
    'st\\":[]}],[\\"record_id\\",\\"ve-history-1-underlying\\"],[\\"role\\",\\"underlying_quote\\"],[\\"source_'
    'ids\\",{\\"$list\\":[\\"ve-history-1-underlying-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$da'
    'tetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"reco'
    'rd_id\\",\\"ve-history-2-0-call-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"'
    '$list\\":[\\"ve-history-2-0-call-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\'
    '"2030-01-02T15:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"'
    've-history-2-0-call-quote\\"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-histor'
    'y-2-0-call-quote-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30'
    ':00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-2-0-ca'
    'll-reference\\"],[\\"role\\",\\"option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-histor'
    'y-2-0-call-reference-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T1'
    '5:30:00.000002Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-2-'
    '0-put-iv\\"],[\\"role\\",\\"option_implied_volatility\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-'
    '0-put-iv-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.0000'
    '02Z\\"}],[\\"propagated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-2-0-put-quote\\'
    '"],[\\"role\\",\\"option_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-0-put-quote-source-0\\"'
    ']}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propagat'
    'ed_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-2-0-put-reference\\"],[\\"role\\",\\"'
    'option_contract_reference\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-0-put-reference-source-0'
    '\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"propag'
    'ated_quality_flags\\",{\\"$list\\":[]}],[\\"record_id\\",\\"ve-history-2-underlying\\"],[\\"role\\",\\"und'
    'erlying_quote\\"],[\\"source_ids\\",{\\"$list\\":[\\"ve-history-2-underlying-source-0\\"]}]]}]}]]}],[\\"'
    'percentile_formula\\",\\"inclusive_count_historical_atm_iv_lte_current_reference_atm_iv_divided_by'
    '_count\\"],[\\"realized_volatility_dependency\\",{\\"$map\\":[[\\"adjustment_methodology\\",null],[\\"an'
    'nualization_sessions_per_year\\",252],[\\"annualized_realized_volatility_float_repr\\",\\"0.33287569'
    '33888896\\"],[\\"calculated_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:04.000000Z\\"}],[\\"calculation_i'
    'd\\",\\"calculation-3c7c\\"],[\\"calculation_type\\",\\"historical_realized_volatility\\"],[\\"end_sessi'
    'on_date\\",{\\"$date\\":\\"2030-01-02\\"}],[\\"inputs\\",{\\"$list\\":[{\\"$map\\":[[\\"normalized_at\\",{\\"$'
    'datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"hrv-0\\"],[\\"source_ids\\",{\\"$list\\'
    '":[\\"hrv-0-source-0\\"]}]]},{\\"$map\\":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.00'
    '0002Z\\"}],[\\"record_id\\",\\"hrv-1\\"],[\\"source_ids\\",{\\"$list\\":[\\"hrv-1-source-0\\"]}]]},{\\"$map\\'
    '":[[\\"normalized_at\\",{\\"$datetime\\":\\"2030-01-02T15:30:00.000002Z\\"}],[\\"record_id\\",\\"hrv-2\\"]'
    ',[\\"source_ids\\",{\\"$list\\":[\\"hrv-2-source-0\\"]}]]}]}],[\\"log_returns\\",{\\"$list\\":[{\\"$decimal'
    '\\":\\"0.01980262729617971302602906688510039\\"},{\\"$decimal\\":\\"-0.0098522964430116301778137093408'
    '39653\\"}]}],[\\"methodology_id\\",\\"historical-log-return-sample-realized-volatility\\"],[\\"methodo'
    'logy_version\\",\\"v0.1\\"],[\\"parameters_json\\",\\"{\\\\\\"$map\\\\\\":[[\\\\\\"adjustment_methodology\\\\\\",n'
    'ull],[\\\\\\"annualization_rule\\\\\\",\\\\\\"daily_sample_standard_deviation_times_square_root_sessions_'
    'per_year\\\\\\"],[\\\\\\"annualization_sessions_per_year\\\\\\",252],[\\\\\\"expected_session_dates\\\\\\",{\\\\\\'
    '"$list\\\\\\":[{\\\\\\"$date\\\\\\":\\\\\\"2029-12-03\\\\\\"},{\\\\\\"$date\\\\\\":\\\\\\"2029-12-18\\\\\\"},{\\\\\\"$date\\\\\\"'
    ':\\\\\\"2030-01-02\\\\\\"}]}],[\\\\\\"price_basis\\\\\\",\\\\\\"raw_close\\\\\\"],[\\\\\\"price_observation_count\\\\\\"'
    ',3],[\\\\\\"price_unit\\\\\\",\\\\\\"usd_per_underlying_share\\\\\\"],[\\\\\\"return_association_rule\\\\\\",\\\\\\"e'
    'nding_session\\\\\\"],[\\\\\\"return_formula\\\\\\",\\\\\\"natural_log_price_ratio\\\\\\"],[\\\\\\"return_observat'
    'ion_count\\\\\\",2],[\\\\\\"return_unit\\\\\\",\\\\\\"decimal_ratio\\\\\\"],[\\\\\\"underlying\\\\\\",{\\\\\\"$map\\\\\\":['
    '[\\\\\\"currency\\\\\\",\\\\\\"USD\\\\\\"],[\\\\\\"listing_mic\\\\\\",\\\\\\"ARCX\\\\\\"],[\\\\\\"security_type\\\\\\",\\\\\\"etf'
    '\\\\\\"],[\\\\\\"symbol\\\\\\",\\\\\\"SPY\\\\\\"]]}],[\\\\\\"variance_estimator\\\\\\",\\\\\\"sample_variance\\\\\\"],[\\\\\\"'
    'volatility_unit\\\\\\",\\\\\\"annualized_decimal_ratio\\\\\\"],[\\\\\\"window_end_session_date\\\\\\",{\\\\\\"$dat'
    'e\\\\\\":\\\\\\"2030-01-02\\\\\\"}],[\\\\\\"window_start_session_date\\\\\\",{\\\\\\"$date\\\\\\":\\\\\\"2029-12-03\\\\\\"}'
    ']]}\\"],[\\"price_basis\\",\\"raw_close\\"],[\\"price_observation_count\\",3],[\\"prices\\",{\\"$list\\":[{'
    '\\"$decimal\\":\\"100\\"},{\\"$decimal\\":\\"102\\"},{\\"$decimal\\":\\"101\\"}]}],[\\"quality_flags\\",{\\"$li'
    'st\\":[\\"decimal_to_float_converted\\",\\"annualized\\",\\"assumption_applied\\"]}],[\\"return_formula\\'
    '",\\"natural_log_price_ratio\\"],[\\"return_observation_count\\",2],[\\"session_dates\\",{\\"$list\\":[{'
    '\\"$date\\":\\"2029-12-03\\"},{\\"$date\\":\\"2029-12-18\\"},{\\"$date\\":\\"2030-01-02\\"}]}],[\\"start_sess'
    'ion_date\\",{\\"$date\\":\\"2029-12-03\\"}],[\\"underlying\\",{\\"$map\\":[[\\"currency\\",\\"USD\\"],[\\"list'
    'ing_mic\\",\\"ARCX\\"],[\\"security_type\\",\\"etf\\"],[\\"symbol\\",\\"SPY\\"]]}],[\\"variance_estimator\\",'
    '\\"sample_variance\\"]]}],[\\"realized_window_matching_rule\\",\\"realized_end_equals_current_as_of_a'
    'nd_calendar_span_equals_reference_tenor\\"],[\\"reference_tenor_days\\",30],[\\"strike_tie_rule\\",\\"'
    'lower_strike\\"],[\\"term_tenor_rule\\",\\"expiration_minus_session_date_calendar_days\\"],[\\"underly'
    'ing_midpoint_rule\\",\\"bid_ask_midpoint_no_last_fallback\\"],[\\"volatility_unit\\",\\"annualized_dec'
    'imal_ratio\\"]]}"],["quality_flags",{"$list":["decimal_to_float_converted","annualized","assumpti'
    'on_applied"]}]]}],["record",{"$map":[["as_of_date",{"$date":"2030-01-02"}],["historical_median_a'
    'tm_iv_float_repr","0.21"],["iv_history_lookback_observations",3],["iv_percentile_float_repr","1.'
    '0"],["matched_realized_volatility_float_repr","0.3328756933888896"],["matched_realized_window_da'
    'ys",30],["reference_tenor_days",30],["term_structure",{"$list":[{"$map":[["atm_iv_float_repr","0'
    '.3"],["tenor_days",30]]},{"$map":[["atm_iv_float_repr","0.4"],["tenor_days",60]]}]}],["underlyin'
    'g","SPY"]]}],["wrapper_type","VolatilityEnvironmentTransformationResult"]]}]]}'
)


COMPLETE_INPUT_REFERENCE_VALUES = (
    ('cost-call-contract-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('cost-call-contract-reference-source-0',)),
    ('cost-call-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('cost-call-greeks-source-0',)),
    ('cost-call-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('cost-call-quote-source-0',)),
    ('cost-underlying-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('cost-underlying-quote-source-0',)),
    ('hrv-0', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('hrv-0-source-0',)),
    ('hrv-1', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('hrv-1-source-0',)),
    ('hrv-2', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('hrv-2-source-0',)),
    ('liquidity-call-open-interest', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('liquidity-call-open-interest-source-0',)),
    ('liquidity-call-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('liquidity-call-quote-source-0',)),
    ('liquidity-call-volume', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('liquidity-call-volume-source-0',)),
    ('scenario-iv-0', datetime.datetime(2030, 1, 2, 15, 30, 4, 0, tzinfo=datetime.timezone.utc), ('source-001',)),
    ('scenario-reference-0', datetime.datetime(2030, 1, 2, 15, 30, 4, 0, tzinfo=datetime.timezone.utc), ('source-001',)),
    ('scenario-underlying-quote', datetime.datetime(2030, 1, 2, 15, 30, 4, 0, tzinfo=datetime.timezone.utc), ('source-001',)),
    ('tail-current-30-call10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-call10-greeks-source-0',)),
    ('tail-current-30-call10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-call10-iv-source-0',)),
    ('tail-current-30-call10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-call10-quote-source-0',)),
    ('tail-current-30-call10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-call10-reference-source-0',)),
    ('tail-current-30-call25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-call25-greeks-source-0',)),
    ('tail-current-30-call25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-call25-iv-source-0',)),
    ('tail-current-30-call25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-call25-quote-source-0',)),
    ('tail-current-30-call25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-call25-reference-source-0',)),
    ('tail-current-30-put10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-put10-greeks-source-0',)),
    ('tail-current-30-put10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-put10-iv-source-0',)),
    ('tail-current-30-put10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-put10-quote-source-0',)),
    ('tail-current-30-put10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-put10-reference-source-0',)),
    ('tail-current-30-put25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-put25-greeks-source-0',)),
    ('tail-current-30-put25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-put25-iv-source-0',)),
    ('tail-current-30-put25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-put25-quote-source-0',)),
    ('tail-current-30-put25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-30-put25-reference-source-0',)),
    ('tail-current-60-call10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-call10-greeks-source-0',)),
    ('tail-current-60-call10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-call10-iv-source-0',)),
    ('tail-current-60-call10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-call10-quote-source-0',)),
    ('tail-current-60-call10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-call10-reference-source-0',)),
    ('tail-current-60-call25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-call25-greeks-source-0',)),
    ('tail-current-60-call25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-call25-iv-source-0',)),
    ('tail-current-60-call25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-call25-quote-source-0',)),
    ('tail-current-60-call25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-call25-reference-source-0',)),
    ('tail-current-60-put10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-put10-greeks-source-0',)),
    ('tail-current-60-put10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-put10-iv-source-0',)),
    ('tail-current-60-put10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-put10-quote-source-0',)),
    ('tail-current-60-put10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-put10-reference-source-0',)),
    ('tail-current-60-put25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-put25-greeks-source-0',)),
    ('tail-current-60-put25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-put25-iv-source-0',)),
    ('tail-current-60-put25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-put25-quote-source-0',)),
    ('tail-current-60-put25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-current-60-put25-reference-source-0',)),
    ('tail-history-0-30-call10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-call10-greeks-source-0',)),
    ('tail-history-0-30-call10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-call10-iv-source-0',)),
    ('tail-history-0-30-call10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-call10-quote-source-0',)),
    ('tail-history-0-30-call10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-call10-reference-source-0',)),
    ('tail-history-0-30-call25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-call25-greeks-source-0',)),
    ('tail-history-0-30-call25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-call25-iv-source-0',)),
    ('tail-history-0-30-call25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-call25-quote-source-0',)),
    ('tail-history-0-30-call25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-call25-reference-source-0',)),
    ('tail-history-0-30-put10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-put10-greeks-source-0',)),
    ('tail-history-0-30-put10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-put10-iv-source-0',)),
    ('tail-history-0-30-put10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-put10-quote-source-0',)),
    ('tail-history-0-30-put10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-put10-reference-source-0',)),
    ('tail-history-0-30-put25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-put25-greeks-source-0',)),
    ('tail-history-0-30-put25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-put25-iv-source-0',)),
    ('tail-history-0-30-put25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-put25-quote-source-0',)),
    ('tail-history-0-30-put25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-30-put25-reference-source-0',)),
    ('tail-history-0-60-atm-call-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-atm-call-greeks-source-0',)),
    ('tail-history-0-60-atm-call-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-atm-call-iv-source-0',)),
    ('tail-history-0-60-atm-call-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-atm-call-quote-source-0',)),
    ('tail-history-0-60-atm-call-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-atm-call-reference-source-0',)),
    ('tail-history-0-60-atm-put-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-atm-put-greeks-source-0',)),
    ('tail-history-0-60-atm-put-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-atm-put-iv-source-0',)),
    ('tail-history-0-60-atm-put-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-atm-put-quote-source-0',)),
    ('tail-history-0-60-atm-put-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-atm-put-reference-source-0',)),
    ('tail-history-0-60-call10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-call10-greeks-source-0',)),
    ('tail-history-0-60-call10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-call10-iv-source-0',)),
    ('tail-history-0-60-call10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-call10-quote-source-0',)),
    ('tail-history-0-60-call10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-call10-reference-source-0',)),
    ('tail-history-0-60-call25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-call25-greeks-source-0',)),
    ('tail-history-0-60-call25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-call25-iv-source-0',)),
    ('tail-history-0-60-call25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-call25-quote-source-0',)),
    ('tail-history-0-60-call25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-call25-reference-source-0',)),
    ('tail-history-0-60-put10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-put10-greeks-source-0',)),
    ('tail-history-0-60-put10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-put10-iv-source-0',)),
    ('tail-history-0-60-put10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-put10-quote-source-0',)),
    ('tail-history-0-60-put10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-put10-reference-source-0',)),
    ('tail-history-0-60-put25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-put25-greeks-source-0',)),
    ('tail-history-0-60-put25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-put25-iv-source-0',)),
    ('tail-history-0-60-put25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-put25-quote-source-0',)),
    ('tail-history-0-60-put25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-put25-reference-source-0',)),
    ('tail-history-0-60-underlying', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-0-60-underlying-source-0',)),
    ('tail-history-1-30-call10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-call10-greeks-source-0',)),
    ('tail-history-1-30-call10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-call10-iv-source-0',)),
    ('tail-history-1-30-call10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-call10-quote-source-0',)),
    ('tail-history-1-30-call10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-call10-reference-source-0',)),
    ('tail-history-1-30-call25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-call25-greeks-source-0',)),
    ('tail-history-1-30-call25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-call25-iv-source-0',)),
    ('tail-history-1-30-call25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-call25-quote-source-0',)),
    ('tail-history-1-30-call25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-call25-reference-source-0',)),
    ('tail-history-1-30-put10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-put10-greeks-source-0',)),
    ('tail-history-1-30-put10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-put10-iv-source-0',)),
    ('tail-history-1-30-put10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-put10-quote-source-0',)),
    ('tail-history-1-30-put10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-put10-reference-source-0',)),
    ('tail-history-1-30-put25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-put25-greeks-source-0',)),
    ('tail-history-1-30-put25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-put25-iv-source-0',)),
    ('tail-history-1-30-put25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-put25-quote-source-0',)),
    ('tail-history-1-30-put25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-30-put25-reference-source-0',)),
    ('tail-history-1-60-atm-call-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-atm-call-greeks-source-0',)),
    ('tail-history-1-60-atm-call-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-atm-call-iv-source-0',)),
    ('tail-history-1-60-atm-call-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-atm-call-quote-source-0',)),
    ('tail-history-1-60-atm-call-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-atm-call-reference-source-0',)),
    ('tail-history-1-60-atm-put-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-atm-put-greeks-source-0',)),
    ('tail-history-1-60-atm-put-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-atm-put-iv-source-0',)),
    ('tail-history-1-60-atm-put-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-atm-put-quote-source-0',)),
    ('tail-history-1-60-atm-put-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-atm-put-reference-source-0',)),
    ('tail-history-1-60-call10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-call10-greeks-source-0',)),
    ('tail-history-1-60-call10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-call10-iv-source-0',)),
    ('tail-history-1-60-call10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-call10-quote-source-0',)),
    ('tail-history-1-60-call10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-call10-reference-source-0',)),
    ('tail-history-1-60-call25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-call25-greeks-source-0',)),
    ('tail-history-1-60-call25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-call25-iv-source-0',)),
    ('tail-history-1-60-call25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-call25-quote-source-0',)),
    ('tail-history-1-60-call25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-call25-reference-source-0',)),
    ('tail-history-1-60-put10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-put10-greeks-source-0',)),
    ('tail-history-1-60-put10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-put10-iv-source-0',)),
    ('tail-history-1-60-put10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-put10-quote-source-0',)),
    ('tail-history-1-60-put10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-put10-reference-source-0',)),
    ('tail-history-1-60-put25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-put25-greeks-source-0',)),
    ('tail-history-1-60-put25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-put25-iv-source-0',)),
    ('tail-history-1-60-put25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-put25-quote-source-0',)),
    ('tail-history-1-60-put25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-put25-reference-source-0',)),
    ('tail-history-1-60-underlying', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-1-60-underlying-source-0',)),
    ('tail-history-2-30-call10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-call10-greeks-source-0',)),
    ('tail-history-2-30-call10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-call10-iv-source-0',)),
    ('tail-history-2-30-call10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-call10-quote-source-0',)),
    ('tail-history-2-30-call10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-call10-reference-source-0',)),
    ('tail-history-2-30-call25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-call25-greeks-source-0',)),
    ('tail-history-2-30-call25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-call25-iv-source-0',)),
    ('tail-history-2-30-call25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-call25-quote-source-0',)),
    ('tail-history-2-30-call25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-call25-reference-source-0',)),
    ('tail-history-2-30-put10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-put10-greeks-source-0',)),
    ('tail-history-2-30-put10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-put10-iv-source-0',)),
    ('tail-history-2-30-put10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-put10-quote-source-0',)),
    ('tail-history-2-30-put10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-put10-reference-source-0',)),
    ('tail-history-2-30-put25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-put25-greeks-source-0',)),
    ('tail-history-2-30-put25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-put25-iv-source-0',)),
    ('tail-history-2-30-put25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-put25-quote-source-0',)),
    ('tail-history-2-30-put25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-30-put25-reference-source-0',)),
    ('tail-history-2-60-atm-call-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-atm-call-greeks-source-0',)),
    ('tail-history-2-60-atm-call-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-atm-call-iv-source-0',)),
    ('tail-history-2-60-atm-call-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-atm-call-quote-source-0',)),
    ('tail-history-2-60-atm-call-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-atm-call-reference-source-0',)),
    ('tail-history-2-60-atm-put-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-atm-put-greeks-source-0',)),
    ('tail-history-2-60-atm-put-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-atm-put-iv-source-0',)),
    ('tail-history-2-60-atm-put-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-atm-put-quote-source-0',)),
    ('tail-history-2-60-atm-put-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-atm-put-reference-source-0',)),
    ('tail-history-2-60-call10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-call10-greeks-source-0',)),
    ('tail-history-2-60-call10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-call10-iv-source-0',)),
    ('tail-history-2-60-call10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-call10-quote-source-0',)),
    ('tail-history-2-60-call10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-call10-reference-source-0',)),
    ('tail-history-2-60-call25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-call25-greeks-source-0',)),
    ('tail-history-2-60-call25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-call25-iv-source-0',)),
    ('tail-history-2-60-call25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-call25-quote-source-0',)),
    ('tail-history-2-60-call25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-call25-reference-source-0',)),
    ('tail-history-2-60-put10-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-put10-greeks-source-0',)),
    ('tail-history-2-60-put10-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-put10-iv-source-0',)),
    ('tail-history-2-60-put10-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-put10-quote-source-0',)),
    ('tail-history-2-60-put10-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-put10-reference-source-0',)),
    ('tail-history-2-60-put25-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-put25-greeks-source-0',)),
    ('tail-history-2-60-put25-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-put25-iv-source-0',)),
    ('tail-history-2-60-put25-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-put25-quote-source-0',)),
    ('tail-history-2-60-put25-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-put25-reference-source-0',)),
    ('tail-history-2-60-underlying', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('tail-history-2-60-underlying-source-0',)),
    ('ve-current-0-call-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-0-call-greeks-source-0',)),
    ('ve-current-0-call-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-0-call-iv-source-0',)),
    ('ve-current-0-call-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-0-call-quote-source-0',)),
    ('ve-current-0-call-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-0-call-reference-source-0',)),
    ('ve-current-0-put-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-0-put-greeks-source-0',)),
    ('ve-current-0-put-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-0-put-iv-source-0',)),
    ('ve-current-0-put-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-0-put-quote-source-0',)),
    ('ve-current-0-put-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-0-put-reference-source-0',)),
    ('ve-current-1-call-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-1-call-greeks-source-0',)),
    ('ve-current-1-call-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-1-call-iv-source-0',)),
    ('ve-current-1-call-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-1-call-quote-source-0',)),
    ('ve-current-1-call-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-1-call-reference-source-0',)),
    ('ve-current-1-put-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-1-put-greeks-source-0',)),
    ('ve-current-1-put-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-1-put-iv-source-0',)),
    ('ve-current-1-put-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-1-put-quote-source-0',)),
    ('ve-current-1-put-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-1-put-reference-source-0',)),
    ('ve-current-underlying', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-current-underlying-source-0',)),
    ('ve-history-0-0-call-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-0-0-call-greeks-source-0',)),
    ('ve-history-0-0-call-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-0-0-call-iv-source-0',)),
    ('ve-history-0-0-call-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-0-0-call-quote-source-0',)),
    ('ve-history-0-0-call-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-0-0-call-reference-source-0',)),
    ('ve-history-0-0-put-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-0-0-put-greeks-source-0',)),
    ('ve-history-0-0-put-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-0-0-put-iv-source-0',)),
    ('ve-history-0-0-put-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-0-0-put-quote-source-0',)),
    ('ve-history-0-0-put-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-0-0-put-reference-source-0',)),
    ('ve-history-0-underlying', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-0-underlying-source-0',)),
    ('ve-history-1-0-call-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-1-0-call-greeks-source-0',)),
    ('ve-history-1-0-call-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-1-0-call-iv-source-0',)),
    ('ve-history-1-0-call-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-1-0-call-quote-source-0',)),
    ('ve-history-1-0-call-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-1-0-call-reference-source-0',)),
    ('ve-history-1-0-put-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-1-0-put-greeks-source-0',)),
    ('ve-history-1-0-put-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-1-0-put-iv-source-0',)),
    ('ve-history-1-0-put-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-1-0-put-quote-source-0',)),
    ('ve-history-1-0-put-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-1-0-put-reference-source-0',)),
    ('ve-history-1-underlying', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-1-underlying-source-0',)),
    ('ve-history-2-0-call-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-2-0-call-greeks-source-0',)),
    ('ve-history-2-0-call-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-2-0-call-iv-source-0',)),
    ('ve-history-2-0-call-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-2-0-call-quote-source-0',)),
    ('ve-history-2-0-call-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-2-0-call-reference-source-0',)),
    ('ve-history-2-0-put-greeks', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-2-0-put-greeks-source-0',)),
    ('ve-history-2-0-put-iv', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-2-0-put-iv-source-0',)),
    ('ve-history-2-0-put-quote', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-2-0-put-quote-source-0',)),
    ('ve-history-2-0-put-reference', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-2-0-put-reference-source-0',)),
    ('ve-history-2-underlying', datetime.datetime(2030, 1, 2, 15, 30, 0, 2, tzinfo=datetime.timezone.utc), ('ve-history-2-underlying-source-0',)),
)


def evidence():
    return (
        ClassifiedEvidence(
            "evidence-1",
            EvidenceKind.CALCULATED_METRIC,
            EvidenceImpact.SUPPORTS,
            "Synthetic reviewed evidence",
            "synthetic fixture",
            "fixture-v1",
        ),
    )


@functools.lru_cache(maxsize=1)
def complete_artifacts():
    arguments = make_scenario_valuation_result(return_arguments=True)
    costs = arguments[1]
    tail = arguments[2]
    scenario = transform_scenario_valuation(*arguments)
    _decoded, _observations, volatility = (
        market_data_transformations._verify_tail_pricing_result(
            tail.records, tail.lineage
        )
    )
    selection = make_selection(
        costs.record.structure,
        bid=("1.00", "2.00"),
        ask=("1.40", "2.60"),
    )[0]
    liquidity = transform(costs.record.structure, selection)
    expiration = transform_expiration_payoff_thresholds(
        "expiration-thresholds-shared",
        costs,
        CALCULATED_AT + datetime.timedelta(seconds=11),
    )
    affordability = assess_structure_affordability(
        "affordability-shared",
        costs,
        complete_assumptions(),
        CALCULATED_AT + datetime.timedelta(seconds=12),
    )
    return (
        volatility, tail, liquidity, costs, scenario, expiration,
        affordability,
    )


def assemble_artifacts(
    artifacts,
    state=CandidateState.INVESTIGATE,
    missing=(),
    *,
    calculation_id="assembly-complete",
    calculated_at=CALCULATED_AT + datetime.timedelta(seconds=30),
    evidence_values=None,
    ai_interpretation=None,
):
    structure = next(
        item.record.structure
        for item in (
            artifacts[3], artifacts[2], artifacts[5], artifacts[6]
        )
        if item is not None
    ) if any(
        artifacts[index] is not None for index in (3, 2, 5, 6)
    ) else complete_artifacts()[3].record.structure
    return assemble_candidate_research_record(
        calculation_id,
        "candidate-complete",
        state,
        "reviewed complete artifacts",
        SESSION_DATE,
        "testable convexity hypothesis",
        structure,
        *artifacts,
        evidence() if evidence_values is None else evidence_values,
        ("contrary evidence",),
        missing,
        ("false-positive channel",),
        ai_interpretation,
        ("what changes the conclusion?",),
        calculated_at,
    )


def direct_values(result):
    return [
        getattr(result, field.name) for field in dataclasses.fields(result)
    ]


def bypass(value, **changes):
    forged = object.__new__(type(value))
    for field in dataclasses.fields(value):
        object.__setattr__(
            forged,
            field.name,
            changes.get(field.name, getattr(value, field.name)),
        )
    return forged


def forged_parameters(result, mutate):
    decoded = market_data_transformations._decode_strict_tagged_parameters(
        result.lineage.parameters_json, assembly._PARAMETER_KEYS, "test"
    )
    changed = copy.deepcopy(decoded)
    mutate(changed)
    lineage = dataclasses.replace(
        result.lineage,
        parameters_json=canonicalize_lineage_parameters(changed),
    )
    values = direct_values(result)
    values[-1] = lineage
    return values


def bypass_parameters(result, parameters_json):
    lineage = bypass(result.lineage, parameters_json=parameters_json)
    values = direct_values(result)
    values[-1] = lineage
    return values


def zero_arguments(state=CandidateState.WATCH, missing=("artifacts pending",)):
    structure = complete_artifacts()[3].record.structure
    return (
        "assembly-001",
        "candidate-001",
        state,
        "caller supplied state",
        SESSION_DATE,
        "testable convexity hypothesis",
        structure,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        evidence(),
        ("contrary evidence",),
        missing,
        ("false-positive channel",),
        None,
        ("what changes the conclusion?",),
        CALCULATED_AT + datetime.timedelta(seconds=30),
    )


class LiteralCanonicalGoldenTests(unittest.TestCase):
    def test_zero_artifact_watch_complete_literal_byte_golden(self):
        result = assemble_candidate_research_record(*zero_arguments())
        self.assertEqual(
            result.lineage.parameters_json,
            ZERO_WATCH_PARAMETERS_JSON,
        )
        self.assertEqual(result.lineage.inputs, ())
        self.assertEqual(result.lineage.quality_flags, (
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
        ))

    def test_complete_investigate_complete_literal_byte_golden(self):
        result = assemble_artifacts(complete_artifacts())
        self.assertEqual(
            result.lineage.parameters_json,
            COMPLETE_INVESTIGATE_PARAMETERS_JSON,
        )
        self.assertEqual(
            tuple(
                (item.record_id, item.normalized_at, item.source_ids)
                for item in result.lineage.inputs
            ),
            COMPLETE_INPUT_REFERENCE_VALUES,
        )
        self.assertEqual(
            tuple(item.record_id for item in result.lineage.inputs),
            tuple(sorted(item.record_id for item in result.lineage.inputs)),
        )
        self.assertEqual(result.lineage.quality_flags, (
            CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED,
            CalculationQualityFlag.ANNUALIZED,
            CalculationQualityFlag.ASSUMPTION_APPLIED,
        ))
        self.assertNotIn(
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
            result.lineage.quality_flags,
        )


class CandidateAssemblyPublicContractTests(unittest.TestCase):
    def test_exports_fields_signature_and_package_boundary(self):
        self.assertEqual(assembly.__all__, (
            "CandidateResearchRecordAssemblyResult",
            "assemble_candidate_research_record",
        ))
        self.assertFalse(hasattr(convexity_hunter,
                                 "CandidateResearchRecordAssemblyResult"))
        self.assertFalse(hasattr(convexity_hunter,
                                 "assemble_candidate_research_record"))
        self.assertEqual(len(market_data.__all__), 64)
        self.assertEqual(len(market_data_transformations.__all__), 25)
        self.assertEqual(len(risk_assessment.__all__), 7)
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                CandidateResearchRecordAssemblyResult
            )),
            ("record", "volatility_environment_result",
             "tail_pricing_result", "structure_liquidity_result",
             "structure_costs_result", "scenario_valuation_result",
             "expiration_payoff_threshold_result",
             "structure_affordability_result", "lineage"),
        )
        self.assertEqual(tuple(inspect.signature(
            assemble_candidate_research_record
        ).parameters), (
            "calculation_id", "candidate_id", "state", "state_rationale",
            "as_of_date", "hypothesis", "structure",
            "volatility_environment_result", "tail_pricing_result",
            "structure_liquidity_result", "structure_costs_result",
            "scenario_valuation_result",
            "expiration_payoff_threshold_result",
            "structure_affordability_result", "evidence",
            "falsification_conditions", "missing_data",
            "false_positive_reasons", "ai_interpretation",
            "human_review_questions", "calculated_at",
        ))


class ZeroArtifactAssemblyTests(unittest.TestCase):
    def test_watch_reject_and_data_insufficient_zero_artifact(self):
        for state in (
            CandidateState.WATCH,
            CandidateState.REJECT,
            CandidateState.DATA_INSUFFICIENT,
        ):
            with self.subTest(state=state):
                result = assemble_candidate_research_record(
                    *zero_arguments(state)
                )
                self.assertEqual(result.lineage.inputs, ())
                self.assertEqual(result.lineage.quality_flags, (
                    CalculationQualityFlag.INCOMPLETE_INPUT_USED,
                ))
                self.assertEqual(result.record.missing_data,
                                 ("artifacts pending",))
                self.assertEqual(CandidateResearchRecordAssemblyResult(
                    *tuple(getattr(result, field.name) for field in
                           dataclasses.fields(result))
                ), result)

    def test_zero_artifact_state_rejections(self):
        with self.assertRaises(ValueError):
            assemble_candidate_research_record(
                *zero_arguments(CandidateState.INVESTIGATE)
            )
        for state in (
            CandidateState.WATCH,
            CandidateState.REJECT,
            CandidateState.DATA_INSUFFICIENT,
        ):
            with self.subTest(state=state), self.assertRaises(ValueError):
                assemble_candidate_research_record(
                    *zero_arguments(state, ())
                )

    def test_canonical_schema_and_direct_mutations(self):
        result = assemble_candidate_research_record(*zero_arguments())
        decoded = market_data_transformations._decode_strict_tagged_parameters(
            result.lineage.parameters_json,
            assembly._PARAMETER_KEYS,
            "test",
        )
        self.assertEqual(set(decoded), assembly._PARAMETER_KEYS)
        self.assertEqual(len(decoded), 12)
        self.assertEqual(
            tuple(decoded[name] for name in assembly._ARTIFACT_FIELDS),
            (None,) * 7,
        )
        forged = dataclasses.replace(
            result.lineage,
            quality_flags=(),
        )
        with self.assertRaises(ValueError):
            CandidateResearchRecordAssemblyResult(
                result.record, None, None, None, None, None, None, None,
                forged,
            )


class CompleteAssemblyTests(unittest.TestCase):
    def complete_artifacts(self):
        return complete_artifacts()

    def assemble(self, state=CandidateState.INVESTIGATE, missing=()):
        return assemble_artifacts(self.complete_artifacts(), state, missing)

    def test_complete_state_matrix(self):
        for state, missing in (
            (CandidateState.INVESTIGATE, ()),
            (CandidateState.INVESTIGATE, ("optional note",)),
            (CandidateState.WATCH, ()),
            (CandidateState.WATCH, ("optional note",)),
            (CandidateState.REJECT, ()),
            (CandidateState.REJECT, ("optional note",)),
            (CandidateState.DATA_INSUFFICIENT, ("other fact missing",)),
        ):
            with self.subTest(state=state, missing=missing):
                result = self.assemble(state, missing)
                self.assertEqual(result.record.state, state)
                self.assertNotIn(
                    CalculationQualityFlag.INCOMPLETE_INPUT_USED,
                    result.lineage.quality_flags,
                )
                self.assertTrue(result.lineage.inputs)

    def test_dependency_closure_exact_identity_and_record_correspondence(self):
        result = self.assemble(CandidateState.WATCH)
        values = [
            getattr(result, field.name)
            for field in dataclasses.fields(result)
        ]
        values[1] = None
        with self.assertRaises(ValueError):
            CandidateResearchRecordAssemblyResult(*values)

        forged_record = dataclasses.replace(
            result.record, candidate_id="different-candidate"
        )
        values = [
            getattr(result, field.name)
            for field in dataclasses.fields(result)
        ]
        values[0] = forged_record
        with self.assertRaises(ValueError):
            CandidateResearchRecordAssemblyResult(*values)

    def test_lineage_collision_chronology_and_union(self):
        result = self.assemble(CandidateState.WATCH)
        mutations = (
            {"calculation_id": result.tail_pricing_result.lineage.calculation_id},
            {"calculated_at": CALCULATED_AT},
            {"inputs": result.lineage.inputs[:-1]},
        )
        for changes in mutations:
            with self.subTest(changes=changes):
                try:
                    lineage = dataclasses.replace(result.lineage, **changes)
                except ValueError:
                    continue
                values = [
                    getattr(result, field.name)
                    for field in dataclasses.fields(result)
                ]
                values[-1] = lineage
                with self.assertRaises(ValueError):
                    CandidateResearchRecordAssemblyResult(*values)

    def test_partial_watch_requires_missing_data(self):
        volatility = self.complete_artifacts()[0]
        arguments = list(zero_arguments(CandidateState.WATCH))
        arguments[7] = volatility
        result = assemble_candidate_research_record(*arguments)
        self.assertIs(result.volatility_environment_result, volatility)
        self.assertIn(
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
            result.lineage.quality_flags,
        )
        arguments[16] = ()
        with self.assertRaises(ValueError):
            assemble_candidate_research_record(*arguments)

    def test_direct_verification_never_calls_operational_producers(self):
        result = self.assemble(CandidateState.WATCH)
        blocked = (
            (market_data_transformations, "transform_volatility_environment"),
            (market_data_transformations, "transform_tail_pricing"),
            (market_data_transformations, "transform_structure_liquidity"),
            (market_data_transformations, "transform_structure_costs"),
            (market_data_transformations, "transform_scenario_valuation"),
            (market_data_transformations,
             "transform_expiration_payoff_thresholds"),
            (risk_assessment, "assess_structure_affordability"),
        )
        patches = [
            mock.patch.object(
                module, name,
                side_effect=AssertionError(f"{name} called"),
            )
            for module, name in blocked
        ]
        for patcher in patches:
            patcher.start()
        try:
            rebuilt = CandidateResearchRecordAssemblyResult(
                *tuple(
                    getattr(result, field.name)
                    for field in dataclasses.fields(result)
                )
            )
            self.assertEqual(rebuilt, result)
        finally:
            for patcher in reversed(patches):
                patcher.stop()


class CanonicalTopLevelMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.zero = assemble_candidate_research_record(*zero_arguments())
        cls.complete = assemble_artifacts(complete_artifacts())

    def assert_parameter_mutation_rejects(
        self, result, label, mutate, error=ValueError
    ):
        with self.subTest(label=label), self.assertRaises(error):
            CandidateResearchRecordAssemblyResult(
                *forged_parameters(result, mutate)
            )

    def test_each_top_level_key_missing_and_surplus(self):
        for key in sorted(assembly._PARAMETER_KEYS):
            self.assert_parameter_mutation_rejects(
                self.zero,
                f"missing-{key}",
                lambda value, key=key: value.pop(key),
            )
        self.assert_parameter_mutation_rejects(
            self.zero,
            "surplus-top-level",
            lambda value: value.__setitem__("surplus", "forbidden"),
        )

    def test_top_level_fixed_architecture_and_disclosure_matrix(self):
        cases = (
            ("schema-version", lambda v: v.__setitem__("schema_version", "v9"), ValueError),
            ("architecture-missing-key", lambda v: v["output_architecture"].pop("lineage_type"), ValueError),
            ("architecture-surplus-key", lambda v: v["output_architecture"].__setitem__("extra", "x"), ValueError),
            ("result-type", lambda v: v["output_architecture"].__setitem__("result_type", "Other"), ValueError),
            ("candidate-record-type", lambda v: v["output_architecture"].__setitem__("candidate_record_type", "Other"), ValueError),
            ("artifact-representation", lambda v: v["output_architecture"].__setitem__("artifact_representation", "registry"), ValueError),
            ("lineage-type", lambda v: v["output_architecture"].__setitem__("lineage_type", "Other"), ValueError),
            ("absent-artifact-malformed-map", lambda v: v.__setitem__("tail_pricing_result", {}), TypeError),
            ("present-artifact-to-none", lambda v: v.__setitem__("tail_pricing_result", None), TypeError),
            ("candidate-record-missing", lambda v: v["candidate_record"].pop("candidate_id"), ValueError),
            ("candidate-record-surplus", lambda v: v["candidate_record"].__setitem__("extra", None), ValueError),
            ("caller-input-missing", lambda v: v["caller_inputs"].pop("candidate_id"), ValueError),
            ("caller-input-surplus", lambda v: v["caller_inputs"].__setitem__("extra", None), ValueError),
        )
        for label, mutate, error in cases:
            result = self.complete if label == "present-artifact-to-none" else self.zero
            self.assert_parameter_mutation_rejects(result, label, mutate, error)


class AssemblyRulesMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = assemble_candidate_research_record(*zero_arguments())

    def assert_rule_mutation_rejects(self, label, mutate, error=ValueError):
        with self.subTest(label=label), self.assertRaises(error):
            CandidateResearchRecordAssemblyResult(
                *forged_parameters(
                    self.result,
                    lambda value: mutate(value["assembly_rules"]),
                )
            )

    def test_state_completeness_matrix(self):
        cases = (
            ("wrong-minimum", lambda r: r["state_completeness"]["investigate"]["artifact_cardinality"].__setitem__("minimum", 6), ValueError),
            ("boolean-minimum", lambda r: r["state_completeness"]["investigate"]["artifact_cardinality"].__setitem__("minimum", True), TypeError),
            ("wrong-maximum", lambda r: r["state_completeness"]["watch"]["artifact_cardinality"].__setitem__("maximum", 8), ValueError),
            ("affordability-reordered", lambda r: r["state_completeness"]["investigate"].__setitem__("affordability_requirement", ("not_affordable", "affordable")), ValueError),
            ("affordability-missing", lambda r: r["state_completeness"]["investigate"].__setitem__("affordability_requirement", ("affordable",)), ValueError),
            ("wrong-incomplete-treatment", lambda r: r["state_completeness"]["investigate"].__setitem__("incomplete_input_treatment", "allowed"), ValueError),
            ("state-change-false", lambda r: r["state_completeness"]["watch"].__setitem__("state_change_prohibited", False), ValueError),
            ("state-key-missing", lambda r: r["state_completeness"]["watch"].pop("affordability_requirement"), ValueError),
            ("state-key-surplus", lambda r: r["state_completeness"]["watch"].__setitem__("extra", True), ValueError),
        )
        for label, mutate, error in cases:
            self.assert_rule_mutation_rejects(label, mutate, error)

    def test_missing_data_and_dependency_closure_matrix(self):
        cases = (
            ("empty-allowed", lambda r: r["missing_data"]["watch"].__setitem__("empty_allowed", False)),
            ("missing-condition-reordered", lambda r: r["missing_data"]["watch"].__setitem__("nonempty_required_when", tuple(reversed(r["missing_data"]["watch"]["nonempty_required_when"])))),
            ("assembler-generation", lambda r: r["missing_data"]["watch"].__setitem__("assembler_generates_descriptions", True)),
            ("semantic-correspondence", lambda r: r["missing_data"]["watch"].__setitem__("semantic_correspondence_to_individual_missing_artifacts_required", True)),
            ("missing-data-key-missing", lambda r: r["missing_data"]["watch"].pop("empty_allowed")),
            ("missing-data-key-surplus", lambda r: r["missing_data"]["watch"].__setitem__("extra", False)),
            ("dependency-missing", lambda r: r["dependency_closure"].pop("tail_pricing_result")),
            ("dependency-surplus", lambda r: r["dependency_closure"].__setitem__("extra", ())),
            ("scenario-dependencies-reordered", lambda r: r["dependency_closure"].__setitem__("scenario_valuation_result", tuple(reversed(r["dependency_closure"]["scenario_valuation_result"])))),
            ("wrong-dependency-field", lambda r: r["dependency_closure"].__setitem__("tail_pricing_result", ("wrong",))),
        )
        for label, mutate in cases:
            self.assert_rule_mutation_rejects(label, mutate)

    def test_shared_identity_and_candidate_mapping_matrix(self):
        cases = (
            ("dependent-field", lambda r: r["shared_dependency_identity"]["tail_to_volatility"].__setitem__("dependent_field", "wrong")),
            ("supplied-field", lambda r: r["shared_dependency_identity"]["tail_to_volatility"].__setitem__("supplied_direct_dependency_field", "wrong")),
            ("dimension-missing", lambda r: r["shared_dependency_identity"]["tail_to_volatility"].__setitem__("comparison_dimensions", ("wrapper_type", "lineage"))),
            ("dimension-reordered", lambda r: r["shared_dependency_identity"]["tail_to_volatility"].__setitem__("comparison_dimensions", ("lineage", "record_or_records", "wrapper_type"))),
            ("dimension-surplus", lambda r: r["shared_dependency_identity"]["tail_to_volatility"].__setitem__("comparison_dimensions", ("wrapper_type", "record_or_records", "lineage", "extra"))),
            ("identity-key-set", lambda r: r["shared_dependency_identity"]["tail_to_volatility"].pop("dependent_field")),
            ("mapped-field", lambda r: r["candidate_record_mapping"].__setitem__("costs", "wrong")),
            ("sidecar-reordered", lambda r: r["candidate_record_mapping"].__setitem__("sidecar_only", tuple(reversed(r["candidate_record_mapping"]["sidecar_only"])))),
            ("sidecar-missing", lambda r: r["candidate_record_mapping"].__setitem__("sidecar_only", ("expiration_payoff_threshold_result",))),
            ("mapping-key-set", lambda r: r["candidate_record_mapping"].pop("liquidity")),
        )
        for label, mutate in cases:
            self.assert_rule_mutation_rejects(label, mutate)

    def test_input_union_and_quality_flag_matrix(self):
        cases = (
            ("nonempty-zero", lambda r: r["normalized_input_union"].__setitem__("zero_artifacts", ("x",))),
            ("dedup-reordered", lambda r: r["normalized_input_union"].__setitem__("deduplication", tuple(reversed(r["normalized_input_union"]["deduplication"])))),
            ("dedup-missing", lambda r: r["normalized_input_union"].__setitem__("deduplication", ("record_id", "normalized_at"))),
            ("conflict-rule", lambda r: r["normalized_input_union"].__setitem__("conflicting_overlap", ("allow",))),
            ("ordering", lambda r: r["normalized_input_union"].__setitem__("ordering", "normalized_at")),
            ("caller-missing", lambda r: r["normalized_input_union"].__setitem__("caller_values", r["normalized_input_union"]["caller_values"][:-1])),
            ("caller-reordered", lambda r: r["normalized_input_union"].__setitem__("caller_values", tuple(reversed(r["normalized_input_union"]["caller_values"])))),
            ("upstream-reordered", lambda r: r["quality_flag_derivation"].__setitem__("upstream_union", tuple(reversed(r["quality_flag_derivation"]["upstream_union"])))),
            ("upstream-missing", lambda r: r["quality_flag_derivation"].__setitem__("upstream_union", r["quality_flag_derivation"]["upstream_union"][:-1])),
            ("absence-flag", lambda r: r["quality_flag_derivation"].__setitem__("artifact_absence", "wrong")),
            ("upstream-incomplete", lambda r: r["quality_flag_derivation"].__setitem__("upstream_incomplete", "wrong")),
            ("flag-order", lambda r: r["quality_flag_derivation"].__setitem__("ordering", tuple(reversed(r["quality_flag_derivation"]["ordering"])))),
            ("noncause-missing", lambda r: r["quality_flag_derivation"].__setitem__("non_causes", r["quality_flag_derivation"]["non_causes"][:-1])),
            ("noncause-reordered", lambda r: r["quality_flag_derivation"].__setitem__("non_causes", tuple(reversed(r["quality_flag_derivation"]["non_causes"])))),
        )
        for label, mutate in cases:
            self.assert_rule_mutation_rejects(label, mutate)

    def test_id_closure_chronology_and_prohibited_matrix(self):
        cases = (
            ("direct-order", lambda r: r["calculation_id_closure"]["direct_dependencies"].__setitem__("fields", tuple(reversed(r["calculation_id_closure"]["direct_dependencies"]["fields"])))),
            ("direct-missing", lambda r: r["calculation_id_closure"]["direct_dependencies"].__setitem__("fields", r["calculation_id_closure"]["direct_dependencies"]["fields"][:-1])),
            ("direct-constraint", lambda r: r["calculation_id_closure"]["direct_dependencies"].__setitem__("constraint", "wrong")),
            ("nested-traversal", lambda r: r["calculation_id_closure"]["nested_dependencies"].__setitem__("traversal", "wrong")),
            ("nested-order", lambda r: r["calculation_id_closure"]["nested_dependencies"].__setitem__("collection_order", "wrong")),
            ("nested-constraint", lambda r: r["calculation_id_closure"]["nested_dependencies"].__setitem__("constraint", "wrong")),
            ("normalized-identifier", lambda r: r["calculation_id_closure"]["normalized_inputs"].__setitem__("identifier", "source_ids")),
            ("shared-bool", lambda r: r["calculation_id_closure"]["shared_reuse"].__setitem__("allowed", False)),
            ("shared-constraint", lambda r: r["calculation_id_closure"]["shared_reuse"].__setitem__("constraint", "wrong")),
            ("chronology-left", lambda r: r["chronology"]["direct_dependencies"].__setitem__("left", "wrong")),
            ("chronology-operator", lambda r: r["chronology"]["direct_dependencies"].__setitem__("operator", ">")),
            ("chronology-right", lambda r: r["chronology"]["normalized_inputs"].__setitem__("right", "wrong")),
            ("zero-count", lambda r: r["chronology"]["zero_artifacts"].__setitem__("comparison_count", 1)),
            ("zero-count-bool", lambda r: r["chronology"]["zero_artifacts"].__setitem__("comparison_count", False), TypeError),
            ("prohibited-removed", lambda r: r.__setitem__("prohibited_behavior", r["prohibited_behavior"][:-1])),
            ("prohibited-changed", lambda r: r.__setitem__("prohibited_behavior", ("changed",) + r["prohibited_behavior"][1:])),
            ("prohibited-reordered", lambda r: r.__setitem__("prohibited_behavior", tuple(reversed(r["prohibited_behavior"])))),
            ("prohibited-surplus", lambda r: r.__setitem__("prohibited_behavior", r["prohibited_behavior"] + ("extra",))),
        )
        for case in cases:
            label, mutate = case[:2]
            error = case[2] if len(case) == 3 else ValueError
            self.assert_rule_mutation_rejects(label, mutate, error)

    def test_fixed_container_subclasses_and_lists_reject(self):
        class DictSubclass(dict):
            pass

        class TupleSubclass(tuple):
            pass

        class StringSubclass(str):
            pass

        variants = (
            ("dict-subclass", DictSubclass(assembly._ASSEMBLY_RULES)),
            ("tuple-subclass", dict(
                assembly._ASSEMBLY_RULES,
                prohibited_behavior=TupleSubclass(
                    assembly._ASSEMBLY_RULES["prohibited_behavior"]
                ),
            )),
            ("list-for-tuple", dict(
                assembly._ASSEMBLY_RULES,
                prohibited_behavior=list(
                    assembly._ASSEMBLY_RULES["prohibited_behavior"]
                ),
            )),
            ("string-subclass", dict(
                assembly._ASSEMBLY_RULES,
                prohibited_behavior=(StringSubclass("invoke_upstream_producers"),)
                + assembly._ASSEMBLY_RULES["prohibited_behavior"][1:],
            )),
        )
        for label, rules in variants:
            with self.subTest(label=label), mock.patch.object(
                assembly, "_ASSEMBLY_RULES", rules
            ), self.assertRaises(TypeError):
                CandidateResearchRecordAssemblyResult(
                    *direct_values(self.result)
                )

        list_paths = (
            ("missing-data", ("missing_data", "watch", "nonempty_required_when")),
            ("dependency-closure", ("dependency_closure", "scenario_valuation_result")),
            ("candidate-mapping", ("candidate_record_mapping", "sidecar_only")),
            ("input-deduplication", ("normalized_input_union", "deduplication")),
            ("input-caller-values", ("normalized_input_union", "caller_values")),
            ("quality-upstream", ("quality_flag_derivation", "upstream_union")),
            ("quality-non-causes", ("quality_flag_derivation", "non_causes")),
        )
        for label, path in list_paths:
            rules = copy.deepcopy(assembly._ASSEMBLY_RULES)
            parent = rules
            for key in path[:-1]:
                parent = parent[key]
            parent[path[-1]] = list(parent[path[-1]])
            with self.subTest(list_boundary=label), mock.patch.object(
                assembly, "_ASSEMBLY_RULES", rules
            ), self.assertRaises(TypeError):
                CandidateResearchRecordAssemblyResult(
                    *direct_values(self.result)
                )


class TaggedJsonMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = assemble_candidate_research_record(*zero_arguments())

    def test_malformed_tagged_json_matrix_is_controlled_value_error(self):
        valid = self.result.lineage.parameters_json
        cases = (
            ("duplicate-object-key", '{"$map":[],"$map":[]}'),
            ("json-float", '{"$map":[["x",1.0]]}'),
            ("nan", '{"$map":[["x",NaN]]}'),
            ("infinity", '{"$map":[["x",Infinity]]}'),
            ("unknown-tag", '{"$unknown":"x"}'),
            ("malformed-date", '{"$date":"2030-99-99"}'),
            ("malformed-datetime", '{"$datetime":"2030-01-01"}'),
            ("malformed-decimal", '{"$decimal":"NaN"}'),
            ("unsorted-map", '{"$map":[["b",1],["a",2]]}'),
            ("duplicate-user-key", '{"$map":[["a",1],["a",2]]}'),
            ("malformed-list", '{"$list":{}}'),
            ("wrong-root-tag", '{"$list":[]}'),
            ("whitespace", valid.replace(":", ": ", 1)),
            ("noncanonical-escape", valid.replace(
                '"assembly_rules"', '"\\u0061ssembly_rules"', 1
            )),
            ("leading-text", "x" + valid),
            ("trailing-text", valid + "x"),
        )
        for label, text in cases:
            with self.subTest(label=label), self.assertRaises(ValueError):
                CandidateResearchRecordAssemblyResult(
                    *bypass_parameters(self.result, text)
                )


class CompleteStateAndDependencyMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = complete_artifacts()

    def affordability(self, assumptions, calculation_id):
        return assess_structure_affordability(
            calculation_id,
            self.artifacts[3],
            assumptions,
            CALCULATED_AT + datetime.timedelta(seconds=12),
        )

    def test_authentic_full_state_matrix_including_affordability_outcomes(self):
        not_affordable = self.affordability(
            complete_assumptions(single=ExactRational(0, 1)),
            "affordability-not-affordable",
        )
        cases = (
            ("investigate-affordable", CandidateState.INVESTIGATE, self.artifacts, ()),
            ("investigate-not-affordable", CandidateState.INVESTIGATE, self.artifacts[:-1] + (not_affordable,), ()),
            ("watch-complete", CandidateState.WATCH, self.artifacts, ()),
            ("watch-partial", CandidateState.WATCH, (self.artifacts[0],) + (None,) * 6, ("partial",)),
            ("watch-zero", CandidateState.WATCH, (None,) * 7, ("zero",)),
            ("reject-complete", CandidateState.REJECT, self.artifacts, ()),
            ("reject-partial", CandidateState.REJECT, (self.artifacts[0],) + (None,) * 6, ("partial",)),
            ("reject-zero", CandidateState.REJECT, (None,) * 7, ("zero",)),
            ("insufficient-complete", CandidateState.DATA_INSUFFICIENT, self.artifacts, ("other",)),
            ("insufficient-partial", CandidateState.DATA_INSUFFICIENT, (self.artifacts[0],) + (None,) * 6, ("other",)),
            ("insufficient-zero", CandidateState.DATA_INSUFFICIENT, (None,) * 7, ("other",)),
        )
        for label, state, artifacts, missing in cases:
            with self.subTest(label=label):
                result = assemble_artifacts(artifacts, state, missing)
                self.assertIs(result.record.state, state)

    def test_each_investigate_artifact_omission_rejects(self):
        for index, name in enumerate(assembly._ARTIFACT_FIELDS):
            artifacts = list(self.artifacts)
            artifacts[index] = None
            with self.subTest(field=name), self.assertRaises(ValueError):
                assemble_artifacts(
                    tuple(artifacts), CandidateState.INVESTIGATE, ("missing",)
                )

    def test_incomplete_and_inconclusive_affordability_reject_investigate(self):
        incomplete = self.affordability(
            RiskBudgetAssumptions(), "affordability-incomplete"
        )
        self.assertIn(
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
            incomplete.lineage.quality_flags,
        )
        for label, affordability in (
            ("incomplete", incomplete),
            ("inconclusive", incomplete),
        ):
            artifacts = self.artifacts[:-1] + (affordability,)
            with self.subTest(label=label), self.assertRaises(ValueError):
                assemble_artifacts(
                    artifacts, CandidateState.INVESTIGATE, ("missing",)
                )

    def test_authentic_incomplete_capable_direct_artifacts_reject_investigate(self):
        def mark_partial(record):
            original = record.metadata
            first = dataclasses.replace(
                original.source_references[0],
                quality_flags=(SourceQualityFlag.PARTIAL,),
            )
            changed = dataclasses.replace(
                original,
                source_references=(first,) + original.source_references[1:],
            )
            object.__setattr__(record, "metadata", changed)
            return original

        structure = self.artifacts[3].record.structure
        liquidity_selection, _assessment, liquidity_bindings = make_selection(
            structure, bid=("1.00", "2.00"), ask=("1.40", "2.60")
        )
        liquidity_record = liquidity_bindings[0][
            MarketDataRelationshipRole.OPTION_QUOTE
        ].selected_record
        original = mark_partial(liquidity_record)
        try:
            incomplete_liquidity = transform(structure, liquidity_selection)
        finally:
            object.__setattr__(liquidity_record, "metadata", original)
        self.assertIn(
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
            incomplete_liquidity.lineage.quality_flags,
        )
        with self.assertRaises(ValueError):
            assemble_artifacts(
                self.artifacts[:2] + (incomplete_liquidity,)
                + self.artifacts[3:],
                CandidateState.INVESTIGATE,
                ("incomplete liquidity",),
            )

    def test_empty_missing_data_rejection_matrix_and_complete_nonempty_success(self):
        partial = (self.artifacts[0],) + (None,) * 6
        cases = (
            ("watch-partial", CandidateState.WATCH, partial),
            ("watch-zero", CandidateState.WATCH, (None,) * 7),
            ("reject-partial", CandidateState.REJECT, partial),
            ("reject-zero", CandidateState.REJECT, (None,) * 7),
            ("insufficient-partial", CandidateState.DATA_INSUFFICIENT, partial),
            ("insufficient-zero", CandidateState.DATA_INSUFFICIENT, (None,) * 7),
            ("insufficient-complete", CandidateState.DATA_INSUFFICIENT, self.artifacts),
        )
        for label, state, artifacts in cases:
            with self.subTest(label=label), self.assertRaises(ValueError):
                assemble_artifacts(artifacts, state, ())
        for state in (
            CandidateState.INVESTIGATE,
            CandidateState.WATCH,
            CandidateState.REJECT,
        ):
            with self.subTest(complete_nonempty=state):
                assemble_artifacts(self.artifacts, state, ("allowed",))

    def test_complete_dependency_closure_matrix(self):
        v, tail, liquidity, costs, scenario, expiration, affordability = self.artifacts
        cases = (
            ("tail-without-volatility", (None, tail, None, None, None, None, None)),
            ("scenario-without-volatility", (None, tail, None, costs, scenario, None, None)),
            ("scenario-without-tail", (v, None, None, costs, scenario, None, None)),
            ("scenario-without-costs", (v, tail, None, None, scenario, None, None)),
            ("expiration-without-costs", (None, None, None, None, None, expiration, None)),
            ("affordability-without-costs", (None, None, None, None, None, None, affordability)),
        )
        for label, artifacts in cases:
            with self.subTest(label=label), self.assertRaises(ValueError):
                assemble_artifacts(
                    artifacts, CandidateState.WATCH, ("missing",)
                )
        for label, artifacts in (
            ("volatility-without-tail", (v,) + (None,) * 6),
            ("costs-without-dependent", (None, None, None, costs, None, None, None)),
            ("shared-cost-dependents", (v, tail, None, costs, scenario, expiration, affordability)),
        ):
            with self.subTest(label=label):
                assemble_artifacts(
                    artifacts, CandidateState.WATCH, ("permitted",)
                )
        incomplete = self.affordability(
            RiskBudgetAssumptions(), "affordability-incomplete-closure"
        )
        with self.assertRaises(ValueError):
            assemble_artifacts(
                (None, None, None, None, None, None, incomplete),
                CandidateState.WATCH,
                ("missing",),
            )


class SharedIdentityAndCorrespondenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = complete_artifacts()
        cls.result = assemble_artifacts(cls.artifacts)

    def valid_dependency_variant(self, artifact, **lineage_changes):
        lineage = dataclasses.replace(artifact.lineage, **lineage_changes)
        if hasattr(artifact, "records"):
            return type(artifact)(artifact.records, lineage)
        return type(artifact)(artifact.record, lineage)

    def test_economically_equal_independent_shared_dependencies_reject(self):
        relations = (
            ("tail-volatility", 0),
            ("scenario-tail", 1),
            ("scenario-costs", 3),
            ("expiration-costs", 3),
            ("affordability-costs", 3),
        )
        for label, index in relations:
            artifacts = list(self.artifacts)
            artifacts[index] = self.valid_dependency_variant(
                artifacts[index],
                calculation_id=f"independent-{label}",
            )
            with self.subTest(label=label), self.assertRaises(ValueError):
                assemble_artifacts(
                    tuple(artifacts), CandidateState.WATCH, ("identity",)
                )

    def test_shared_dependency_lineage_dimension_mutations_reject(self):
        target_indices = (0, 1, 3)
        base = self.artifacts
        for index in target_indices:
            artifact = base[index]
            mutations = (
                ("calculation-id", {"calculation_id": f"mutated-{index}"}),
                ("calculation-type", {"calculation_type": "wrong"}),
                ("methodology-id", {"methodology_id": "wrong"}),
                ("methodology-version", {"methodology_version": "wrong"}),
                ("calculated-time", {"calculated_at": artifact.lineage.calculated_at + datetime.timedelta(microseconds=1)}),
                ("parameters", {"parameters_json": '{"$map":[]}'}),
                ("normalized-input", {"inputs": artifact.lineage.inputs[:-1]}),
                ("quality-flags", {"quality_flags": ()}),
            )
            for dimension, changes in mutations:
                artifacts = list(base)
                try:
                    artifacts[index] = self.valid_dependency_variant(
                        artifact, **changes
                    )
                except (TypeError, ValueError):
                    continue
                with self.subTest(index=index, dimension=dimension), self.assertRaises(ValueError):
                    assemble_artifacts(
                        tuple(artifacts), CandidateState.WATCH, ("identity",)
                    )

    def test_each_shared_relation_exercises_its_dependent_path(self):
        relation_cases = (
            ("tail-to-volatility", (0, 1), 0),
            ("scenario-to-tail", (0, 1, 3, 4), 1),
            ("scenario-to-costs", (0, 1, 3, 4), 3),
            ("expiration-to-costs", (3, 5), 3),
            ("affordability-to-costs", (3, 6), 3),
        )
        for label, present, dependency_index in relation_cases:
            artifacts = [None] * 7
            for index in present:
                artifacts[index] = self.artifacts[index]
            dependency = artifacts[dependency_index]
            mutations = (
                ("calculation-id", {"calculation_id": f"{label}-other"}),
                ("calculation-type", {"calculation_type": "other"}),
                ("methodology-id", {"methodology_id": "other"}),
                ("methodology-version", {"methodology_version": "other"}),
                ("calculated-at", {"calculated_at": dependency.lineage.calculated_at + datetime.timedelta(microseconds=1)}),
                ("parameters", {"parameters_json": '{"$map":[]}'}),
                ("input", {"inputs": dependency.lineage.inputs[:-1]}),
                ("quality-flag", {"quality_flags": ()}),
            )
            for dimension, changes in mutations:
                changed = list(artifacts)
                try:
                    changed[dependency_index] = self.valid_dependency_variant(
                        dependency, **changes
                    )
                except (TypeError, ValueError):
                    changed[dependency_index] = bypass(
                        dependency,
                        lineage=bypass(dependency.lineage, **changes),
                    )
                with self.subTest(relation=label, dimension=dimension), self.assertRaises(
                    (TypeError, ValueError)
                ):
                    assemble_artifacts(
                        tuple(changed), CandidateState.WATCH, ("identity",)
                    )

    def test_final_record_and_qualitative_correspondence_mutations(self):
        mutations = (
            ("candidate-id", {"candidate_id": "other"}),
            ("state-rationale", {"state_rationale": "other rationale"}),
            ("hypothesis", {"hypothesis": "other hypothesis"}),
            ("missing-data-order", {"missing_data": ("b", "a")}),
            ("false-positive-order", {"false_positive_reasons": ("b", "a")}),
            ("ai-interpretation", {"ai_interpretation": "other"}),
        )
        for label, changes in mutations:
            try:
                record = dataclasses.replace(self.result.record, **changes)
            except ValueError:
                continue
            values = direct_values(self.result)
            values[0] = record
            with self.subTest(label=label), self.assertRaises(
                (TypeError, ValueError)
            ):
                CandidateResearchRecordAssemblyResult(*values)

    def test_complete_candidate_record_correspondence_matrix(self):
        record = self.result.record
        mutations = (
            ("caller-structure", {"structure": dataclasses.replace(
                record.structure,
                expected_holding_days=record.structure.expected_holding_days + 1,
            )}),
            ("caller-as-of-date", {"as_of_date": record.as_of_date - datetime.timedelta(days=1)}),
            ("caller-underlying", {"volatility_environment": dataclasses.replace(
                record.volatility_environment, underlying="QQQ"
            )}),
            ("mapped-volatility", {"volatility_environment": dataclasses.replace(
                record.volatility_environment,
                iv_percentile=record.volatility_environment.iv_percentile / 2,
            )}),
            ("mapped-tail", {"tail_pricing_slices": record.tail_pricing_slices[:-1]}),
            ("tail-order", {"tail_pricing_slices": tuple(reversed(record.tail_pricing_slices))}),
            ("mapped-costs", {"costs": dataclasses.replace(
                record.costs, quoted_mid_premium=record.costs.quoted_mid_premium + 1
            )}),
            ("mapped-liquidity", {"liquidity": dataclasses.replace(
                record.liquidity, quoted_bid_value=record.liquidity.quoted_bid_value + 1
            )}),
            ("mapped-scenario", {"scenario_results": record.scenario_results[:-1]}),
            ("scenario-order", {"scenario_results": tuple(reversed(record.scenario_results))}),
            ("cost-liquidity-midpoint", {"liquidity": dataclasses.replace(
                record.liquidity, quoted_ask_value=record.liquidity.quoted_ask_value + 1
            )}),
            ("scenario-entry-cost-basis", {"scenario_results": (
                dataclasses.replace(
                    record.scenario_results[0],
                    entry_cost_basis=record.scenario_results[0].entry_cost_basis + 1,
                ),
            ) + record.scenario_results[1:]}),
            ("scenario-underlying-basis", {"scenario_results": (
                dataclasses.replace(
                    record.scenario_results[0],
                    base_underlying_price=record.scenario_results[0].base_underlying_price + 1,
                ),
            ) + record.scenario_results[1:]}),
            ("qualitative-field", {"state_rationale": "different rationale"}),
            ("normalized-text-order", {"falsification_conditions": (
                "second condition", record.falsification_conditions[0]
            )}),
        )
        for label, changes in mutations:
            changed = bypass(record, **changes)
            values = direct_values(self.result)
            values[0] = changed
            with self.subTest(label=label), self.assertRaises(
                (TypeError, ValueError)
            ):
                CandidateResearchRecordAssemblyResult(*values)

    def test_sidecar_m4_m5_correspondence_matrix(self):
        expiration = self.artifacts[5]
        affordability = self.artifacts[6]
        cases = (
            ("expiration-structure", 6, bypass(
                expiration,
                record=bypass(expiration.record, structure=dataclasses.replace(
                    expiration.record.structure,
                    expected_holding_days=expiration.record.structure.expected_holding_days + 1,
                )),
            )),
            ("expiration-date", 6, bypass(
                expiration,
                record=bypass(expiration.record, as_of_date=expiration.record.as_of_date - datetime.timedelta(days=1)),
            )),
            ("expiration-retained-costs", 6, bypass(
                expiration,
                lineage=bypass(expiration.lineage, parameters_json='{"$map":[]}'),
            )),
            ("affordability-structure", 7, bypass(
                affordability,
                record=bypass(affordability.record, structure=dataclasses.replace(
                    affordability.record.structure,
                    expected_holding_days=affordability.record.structure.expected_holding_days + 1,
                )),
            )),
            ("affordability-date", 7, bypass(
                affordability,
                record=bypass(affordability.record, as_of_date=affordability.record.as_of_date - datetime.timedelta(days=1)),
            )),
            ("affordability-retained-costs", 7, bypass(
                affordability,
                lineage=bypass(affordability.lineage, parameters_json='{"$map":[]}'),
            )),
        )
        for label, value_index, artifact in cases:
            values = direct_values(self.result)
            values[value_index] = artifact
            with self.subTest(label=label), self.assertRaises(
                (TypeError, ValueError)
            ):
                CandidateResearchRecordAssemblyResult(*values)

        mismatched_portfolio = bypass(
            affordability,
            record=bypass(
                affordability.record,
                assumptions=complete_assumptions(portfolio="200000.0"),
            ),
        )
        values = direct_values(self.result)
        values[7] = mismatched_portfolio
        with self.assertRaises((TypeError, ValueError)):
            CandidateResearchRecordAssemblyResult(*values)


class AssemblyLineageMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = complete_artifacts()
        cls.complete = assemble_artifacts(cls.artifacts)
        cls.zero = assemble_candidate_research_record(*zero_arguments())

    def direct_with_lineage(self, lineage):
        values = direct_values(self.complete)
        values[-1] = lineage
        return CandidateResearchRecordAssemblyResult(*values)

    def test_zero_one_and_seven_artifact_unions_and_overlap(self):
        one = assemble_artifacts(
            (self.artifacts[0],) + (None,) * 6,
            CandidateState.WATCH,
            ("partial",),
        )
        self.assertEqual(self.zero.lineage.inputs, ())
        self.assertEqual(one.lineage.inputs, self.artifacts[0].lineage.inputs)
        expected_ids = sorted({
            reference.record_id
            for artifact in self.artifacts
            for reference in artifact.lineage.inputs
        })
        self.assertEqual(
            [item.record_id for item in self.complete.lineage.inputs],
            expected_ids,
        )
        self.assertLess(
            len(self.complete.lineage.inputs),
            sum(len(item.lineage.inputs) for item in self.artifacts),
        )
        qualitative = {
            self.complete.record.candidate_id,
            self.complete.record.hypothesis,
            *self.complete.record.missing_data,
        }
        self.assertTrue(qualitative.isdisjoint(
            item.record_id for item in self.complete.lineage.inputs
        ))

    def test_missing_surplus_conflict_duplicate_and_order_mutations(self):
        original = self.complete.lineage.inputs
        first = original[0]
        surplus = CalculationInputReference(
            "assembly-surplus",
            first.normalized_at,
            ("assembly-test",),
        )
        variants = (
            ("missing", original[:-1]),
            ("surplus", original + (surplus,)),
            ("conflicting-time", (dataclasses.replace(
                first,
                normalized_at=first.normalized_at - datetime.timedelta(
                    microseconds=1
                ),
            ),) + original[1:]),
            ("conflicting-source", (dataclasses.replace(
                first, source_ids=("different-source",)
            ),) + original[1:]),
            ("duplicate", original + (first,)),
            ("noncanonical-order", tuple(reversed(original))),
        )
        for label, inputs in variants:
            lineage = bypass(self.complete.lineage, inputs=inputs)
            with self.subTest(label=label), self.assertRaises(
                (TypeError, ValueError)
            ):
                self.direct_with_lineage(lineage)

    def test_calculation_id_collision_matrix(self):
        decoded_volatility = (
            market_data_transformations._decode_volatility_parameters(
                self.artifacts[0].lineage.parameters_json
            )
        )
        historical_id = decoded_volatility[
            "realized_volatility_dependency"
        ]["calculation_id"]
        _costs, _tail, provider, _volatility = (
            market_data_transformations
            ._reconstruct_scenario_valuation_dependencies(
                self.artifacts[4].records, self.artifacts[4].lineage
            )
        )
        cases = (
            ("direct-tail", self.artifacts[1].lineage.calculation_id),
            ("nested-historical", historical_id),
            ("nested-volatility", self.artifacts[0].lineage.calculation_id),
            ("nested-costs", self.artifacts[3].lineage.calculation_id),
            ("nested-provider", provider.lineage.calculation_id),
            ("normalized-input", self.complete.lineage.inputs[0].record_id),
        )
        for label, calculation_id in cases:
            try:
                lineage = dataclasses.replace(
                    self.complete.lineage, calculation_id=calculation_id
                )
            except ValueError:
                lineage = bypass(
                    self.complete.lineage, calculation_id=calculation_id
                )
            with self.subTest(label=label), self.assertRaises(ValueError):
                self.direct_with_lineage(lineage)

        liquidity = self.artifacts[2]
        colliding = dataclasses.replace(
            liquidity.lineage,
            calculation_id=self.artifacts[3].lineage.calculation_id,
        )
        colliding_liquidity = type(liquidity)(liquidity.record, colliding)
        artifacts = list(self.artifacts)
        artifacts[2] = colliding_liquidity
        with self.assertRaises(ValueError):
            assemble_artifacts(
                tuple(artifacts), CandidateState.WATCH, ("collision",)
            )

    def test_chronology_matrix_equality_and_datetime_types(self):
        nested_lineages = []
        volatility_decoded = (
            market_data_transformations._decode_volatility_parameters(
                self.artifacts[0].lineage.parameters_json
            )
        )
        nested_lineages.append(volatility_decoded[
            "realized_volatility_dependency"
        ]["calculated_at"])
        costs, tail, provider, volatility = (
            market_data_transformations
            ._reconstruct_scenario_valuation_dependencies(
                self.artifacts[4].records, self.artifacts[4].lineage
            )
        )
        nested_lineages.extend(item.lineage.calculated_at for item in (
            costs, tail, provider, volatility
        ))
        expiration_decoded = (
            market_data_transformations._decode_expiration_threshold_parameters(
                self.artifacts[5].lineage.parameters_json
            )
        )
        expiration_costs = (
            market_data_transformations
            ._expiration_threshold_dependency_from_disclosure(
                self.artifacts[5].record,
                self.artifacts[5].lineage,
                expiration_decoded["structure_costs_dependency"],
            )
        )
        affordability_decoded = risk_assessment._decode_parameters(
            self.artifacts[6].lineage.parameters_json
        )
        affordability_costs = risk_assessment._dependency_from_disclosure(
            self.artifacts[6].record,
            self.artifacts[6].lineage,
            affordability_decoded["structure_costs_dependency"],
        )
        nested_lineages.extend((
            expiration_costs.lineage.calculated_at,
            affordability_costs.lineage.calculated_at,
        ))
        direct_times = [
            artifact.lineage.calculated_at for artifact in self.artifacts
        ]
        input_times = [item.normalized_at for item in self.complete.lineage.inputs]
        latest = max(direct_times + nested_lineages + input_times)
        equality = assemble_artifacts(
            self.artifacts, calculated_at=latest
        )
        self.assertEqual(equality.lineage.calculated_at, latest)
        labels_and_times = (
            ("direct", max(direct_times)),
            ("historical", nested_lineages[0]),
            ("volatility-under-tail", volatility.lineage.calculated_at),
            ("tail-under-scenario", tail.lineage.calculated_at),
            ("costs-under-scenario", costs.lineage.calculated_at),
            ("provider", provider.lineage.calculated_at),
            ("costs-under-expiration", expiration_costs.lineage.calculated_at),
            ("costs-under-affordability", affordability_costs.lineage.calculated_at),
            ("normalized-input", max(input_times)),
        )
        for label, timestamp in labels_and_times:
            with self.subTest(label=label), self.assertRaises(ValueError):
                assemble_artifacts(
                    self.artifacts,
                    calculated_at=timestamp - datetime.timedelta(
                        microseconds=1
                    ),
                )
        assemble_candidate_research_record(*zero_arguments())
        arguments = list(zero_arguments())
        arguments[-1] = datetime.datetime(2030, 1, 1)
        with self.assertRaises(ValueError):
            assemble_candidate_research_record(*arguments)
        arguments[-1] = datetime.date(2030, 1, 1)
        with self.assertRaises(TypeError):
            assemble_candidate_research_record(*arguments)
        arguments[-1] = datetime.datetime(
            2030, 1, 2, 23, 30,
            tzinfo=datetime.timezone(datetime.timedelta(hours=8)),
        )
        normalized = assemble_candidate_research_record(*arguments)
        self.assertIs(normalized.lineage.calculated_at.tzinfo,
                      datetime.timezone.utc)

    def test_quality_flag_derivation_and_bypassed_mutations(self):
        incomplete_affordability = assess_structure_affordability(
            "affordability-incomplete-flags",
            self.artifacts[3],
            RiskBudgetAssumptions(),
            CALCULATED_AT + datetime.timedelta(seconds=12),
        )
        complete_with_incomplete = assemble_artifacts(
            self.artifacts[:-1] + (incomplete_affordability,),
            CandidateState.WATCH,
            ("incomplete",),
        )
        self.assertNotIn(
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
            self.complete.lineage.quality_flags,
        )
        self.assertIn(
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
            complete_with_incomplete.lineage.quality_flags,
        )
        self.assertEqual(self.zero.lineage.quality_flags, (
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
        ))
        partial = assemble_artifacts(
            (self.artifacts[0],) + (None,) * 6,
            CandidateState.WATCH,
            ("partial",),
            evidence_values=(ClassifiedEvidence(
                "assumption",
                EvidenceKind.ASSUMPTION,
                EvidenceImpact.NEUTRAL,
                "caller assumption",
            ),),
            ai_interpretation="caller AI text",
        )
        self.assertIn(
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
            partial.lineage.quality_flags,
        )
        several_absent = assemble_artifacts(
            self.artifacts[:4] + (None, None, None),
            CandidateState.WATCH,
            ("several absent",),
        )
        self.assertIn(
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
            several_absent.lineage.quality_flags,
        )
        insufficient = assemble_artifacts(
            self.artifacts,
            CandidateState.DATA_INSUFFICIENT,
            ("qualitative only",),
        )
        self.assertNotIn(
            CalculationQualityFlag.INCOMPLETE_INPUT_USED,
            insufficient.lineage.quality_flags,
        )
        empty_generic = CalculationLineage(
            "generic-empty", "generic", "generic-method", "v1",
            self.complete.lineage.calculated_at, (), "{\"$map\":[]}", (),
        )
        self.assertEqual(empty_generic.inputs, ())
        self.assertEqual(empty_generic.quality_flags, ())
        for label, flags in (
            ("missing", self.complete.lineage.quality_flags[:-1]),
            ("surplus", self.complete.lineage.quality_flags + (
                CalculationQualityFlag.INCOMPLETE_INPUT_USED,
            )),
            ("reordered", tuple(reversed(self.complete.lineage.quality_flags))),
        ):
            lineage = bypass(self.complete.lineage, quality_flags=flags)
            with self.subTest(label=label), self.assertRaises(
                (TypeError, ValueError)
            ):
                self.direct_with_lineage(lineage)


class ExactScalarAndContainerMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = complete_artifacts()
        cls.result = assemble_artifacts(cls.artifacts)

    def test_public_schema_scalar_mutations(self):
        cases = (
            ("bool-for-int", lambda p: p["candidate_record"]["structure"].__setitem__("expected_holding_days", True), TypeError),
            ("int-for-bool", lambda p: p["assembly_rules"]["state_completeness"]["watch"].__setitem__("state_change_prohibited", 1), TypeError),
            ("enum-string", lambda p: p["caller_inputs"].__setitem__("state", "unknown"), ValueError),
            ("float-repr-invalid", lambda p: p["candidate_record"]["structure"].__setitem__("assumed_portfolio_value_repr", "not-a-float"), ValueError),
            ("float-repr-noncanonical", lambda p: p["candidate_record"]["structure"].__setitem__("assumed_portfolio_value_repr", "100000.00"), ValueError),
            ("float-repr-nonfinite", lambda p: p["candidate_record"]["structure"].__setitem__("assumed_portfolio_value_repr", "inf"), ValueError),
            ("rational-zero-denominator", lambda p: p["expiration_payoff_threshold_result"]["record"]["thresholds"][0]["target_position_value"].__setitem__("denominator", 0), ValueError),
            ("rational-malformed", lambda p: p["expiration_payoff_threshold_result"]["record"]["thresholds"][0]["target_position_value"].__setitem__("numerator", "x"), TypeError),
            ("optional-rational-malformed", lambda p: p["structure_affordability_result"]["record"]["single_loss_fraction"].pop("numerator"), ValueError),
        )
        for label, mutate, error in cases:
            with self.subTest(label=label), self.assertRaises(error):
                CandidateResearchRecordAssemblyResult(
                    *forged_parameters(self.result, mutate)
                )

    def test_public_decimal_tag_replaced_by_string_rejects(self):
        def replace_first_decimal(value):
            if isinstance(value, dict):
                for key, item in value.items():
                    if type(item) is decimal.Decimal:
                        value[key] = str(item)
                        return True
                    if replace_first_decimal(item):
                        return True
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    if type(item) is decimal.Decimal:
                        value[index] = str(item)
                        return True
                    if replace_first_decimal(item):
                        return True
            elif isinstance(value, tuple):
                for item in value:
                    if replace_first_decimal(item):
                        return True
            return False

        with self.assertRaises((TypeError, ValueError)):
            CandidateResearchRecordAssemblyResult(
                *forged_parameters(
                    self.result,
                    lambda parameters: self.assertTrue(
                        replace_first_decimal(parameters)
                    ),
                )
            )

    def test_mapped_public_records_and_ordering_mutations_reject(self):
        artifact_mutations = (
            ("volatility-record", 0, dataclasses.replace(
                self.artifacts[0].record,
                iv_percentile=self.artifacts[0].record.iv_percentile / 2,
            )),
            ("tail-order", 1, tuple(reversed(self.artifacts[1].records))),
            ("cost-record", 3, dataclasses.replace(
                self.artifacts[3].record,
                quoted_mid_premium=self.artifacts[3].record.quoted_mid_premium + 1,
            )),
            ("liquidity-record", 2, dataclasses.replace(
                self.artifacts[2].record,
                quoted_bid_value=self.artifacts[2].record.quoted_bid_value + 1,
            )),
            ("scenario-order", 4, tuple(reversed(self.artifacts[4].records))),
        )
        for label, index, public_value in artifact_mutations:
            artifact = self.artifacts[index]
            values = direct_values(self.result)
            values[index + 1] = bypass(
                artifact,
                **({"records": public_value} if hasattr(artifact, "records") else {"record": public_value}),
            )
            with self.subTest(label=label), self.assertRaises((TypeError, ValueError)):
                CandidateResearchRecordAssemblyResult(*values)


class NoCallApiAndImportProtectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = complete_artifacts()
        cls.complete = assemble_artifacts(cls.artifacts)

    def test_complete_and_partial_paths_with_operational_boundaries_patched(self):
        import convexity_hunter.report as report_module
        import convexity_hunter.scanner as scanner_module

        blocked = (
            (market_data_transformations, "transform_volatility_environment"),
            (market_data_transformations, "transform_tail_pricing"),
            (market_data_transformations, "transform_structure_liquidity"),
            (market_data_transformations, "transform_structure_costs"),
            (market_data_transformations, "transform_scenario_valuation"),
            (market_data_transformations,
             "transform_expiration_payoff_thresholds"),
            (risk_assessment, "assess_structure_affordability"),
            (scanner_module, "screen_candidate"),
            (report_module, "render_candidate_markdown"),
        )
        patchers = [
            mock.patch.object(
                module, name,
                side_effect=AssertionError(f"{name} called"),
            )
            for module, name in blocked
        ]
        synthetic_boundaries = (
            "provider_scenario_pricing_producer",
            "provider_function",
            "llm_function",
            "system_clock",
            "id_generator",
        )
        patchers.extend(
            mock.patch.object(
                assembly, name,
                side_effect=AssertionError(f"{name} called"),
                create=True,
            )
            for name in synthetic_boundaries
        )
        for patcher in patchers:
            patcher.start()
        try:
            CandidateResearchRecordAssemblyResult(
                *direct_values(self.complete)
            )
            assemble_artifacts(
                (self.artifacts[0],) + (None,) * 6,
                CandidateState.WATCH,
                ("partial",),
            )
        finally:
            for patcher in reversed(patchers):
                patcher.stop()

    def test_exact_exports_fields_and_all_affected_signatures(self):
        self.assertEqual(assembly.__all__, (
            "CandidateResearchRecordAssemblyResult",
            "assemble_candidate_research_record",
        ))
        self.assertEqual(market_data_transformations.__all__, (
            "StructureLiquidityTransformationResult",
            "transform_structure_liquidity",
            "StructureCostsTransformationResult",
            "transform_structure_costs",
            "HistoricalReturnPriceBasis",
            "HistoricalRealizedVolatility",
            "HistoricalRealizedVolatilityTransformationResult",
            "transform_historical_realized_volatility",
            "VolatilityEnvironmentTransformationResult",
            "transform_volatility_environment",
            "TailPricingTransformationResult",
            "transform_tail_pricing",
            "ScenarioPricingMethodology",
            "ScenarioPricingLegCalculation",
            "NonExpirationScenarioPricingCalculation",
            "ScenarioPricingCalculationResult",
            "ScenarioValuationTransformationResult",
            "transform_scenario_valuation",
            "ExactRational",
            "ExpirationPayoffThresholdSide",
            "ExpirationPayoffThresholdStatus",
            "ExpirationPayoffThreshold",
            "ExpirationPayoffThresholdEvidence",
            "ExpirationPayoffThresholdTransformationResult",
            "transform_expiration_payoff_thresholds",
        ))
        self.assertEqual(risk_assessment.__all__, (
            "PortfolioValueAssumption", "RiskBudgetAssumptions",
            "AffordabilityStatus", "AffordabilityReasonCode",
            "StructureAffordabilityEvidence",
            "StructureAffordabilityAssessmentResult",
            "assess_structure_affordability",
        ))
        self.assertEqual(market_data.__all__, (
            "DataOrigin", "SourceQualityFlag", "NormalizationQualityFlag",
            "MarketPhase", "QuoteScope", "UnderlyingSecurityType",
            "DividendStatus", "SourceReference", "NormalizationMetadata",
            "UnderlyingKey", "OptionContractKey",
            "UnderlyingQuoteObservation", "OptionContractReference",
            "OptionQuoteObservation", "OptionVolumeObservation",
            "OptionOpenInterestObservation",
            "OptionImpliedVolatilityObservation", "OptionGreeksObservation",
            "UnderlyingDailyBarObservation", "RateCurvePointObservation",
            "DividendObservation", "MarketDataCategory",
            "MarketDataFreshnessPolicy", "FreshnessContext",
            "FreshnessStatus", "FreshnessReasonCode", "FreshnessAssessment",
            "assess_market_data_freshness", "CorrectionSelectionStatus",
            "CorrectionSelectionReasonCode", "CorrectionSelection",
            "select_correction_candidate", "CalculationQualityFlag",
            "CalculationInputReference", "CalculationLineage",
            "canonicalize_lineage_parameters", "semantic_observation_key",
            "SelectedFreshMarketDataBinding",
            "bind_selected_fresh_market_data",
            "MarketDataSnapshotTimingReasonCode",
            "MarketDataSnapshotTimingAssessment",
            "assess_market_data_snapshot_timing", "MarketDataBindingReference",
            "market_data_binding_reference",
            "resolve_market_data_binding_reference",
            "MarketDataRelationshipGroupKind", "MarketDataRelationshipRole",
            "MarketDataRelationshipGroupMember", "MarketDataRelationshipGroup",
            "MarketDataRelationshipRequest", "MarketDataRelationshipIssueCode",
            "MarketDataRelationshipGroupAssessment",
            "MarketDataRelationshipAssessment",
            "assess_market_data_relationships", "MarketDataSelectionStatus",
            "MarketDataSelectionReasonCode", "MarketDataRelationshipSelection",
            "select_market_data_relationship_assessment",
            "MarketDataHistoricalSeriesFrequency",
            "MarketDataHistoricalSeriesStatus",
            "MarketDataHistoricalSeriesReasonCode",
            "MarketDataHistoricalSeriesRequest",
            "MarketDataHistoricalSeriesAssessment",
            "assess_market_data_historical_series",
        ))
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                CandidateResearchRecordAssemblyResult
            )),
            (
                "record", "volatility_environment_result",
                "tail_pricing_result", "structure_liquidity_result",
                "structure_costs_result", "scenario_valuation_result",
                "expiration_payoff_threshold_result",
                "structure_affordability_result", "lineage",
            ),
        )
        self.assertEqual(
            tuple(inspect.signature(
                assemble_candidate_research_record
            ).parameters),
            (
                "calculation_id", "candidate_id", "state",
                "state_rationale", "as_of_date", "hypothesis", "structure",
                "volatility_environment_result", "tail_pricing_result",
                "structure_liquidity_result", "structure_costs_result",
                "scenario_valuation_result",
                "expiration_payoff_threshold_result",
                "structure_affordability_result", "evidence",
                "falsification_conditions", "missing_data",
                "false_positive_reasons", "ai_interpretation",
                "human_review_questions", "calculated_at",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                CandidateResearchRecord
            )),
            (
                "candidate_id", "state", "state_rationale", "as_of_date",
                "hypothesis", "structure", "volatility_environment",
                "tail_pricing_slices", "costs", "liquidity",
                "scenario_results", "evidence",
                "falsification_conditions", "missing_data",
                "false_positive_reasons", "ai_interpretation",
                "human_review_questions",
            ),
        )
        signatures = {
            "transform_volatility_environment": (
                "calculation_id", "current_relationship_selection",
                "historical_relationship_selections",
                "historical_expected_session_dates",
                "historical_realized_volatility_result",
                "reference_tenor_days", "atm_candidate_universes_complete",
                "calculated_at",
            ),
            "transform_tail_pricing": (
                "calculation_id", "current_relationship_selection",
                "historical_relationship_selections",
                "historical_expected_session_dates",
                "volatility_environment_result",
                "tail_candidate_universes_complete",
                "historical_end_of_day_observations_declared",
                "historical_end_of_day_methodology",
                "delta_methodology", "calculated_at",
            ),
            "transform_structure_liquidity": (
                "calculation_id", "structure", "relationship_selection",
                "calculated_at",
            ),
            "transform_structure_costs": (
                "calculation_id", "structure", "relationship_selection",
                "commissions_and_fees", "repeated_bet_count",
                "calculated_at",
            ),
            "transform_scenario_valuation": (
                "calculation_id", "structure_costs_result",
                "tail_pricing_result", "scenario_pricing_result",
                "scenarios", "scenario_grid_complete",
                "exit_cost_assumptions", "exit_cost_methodology",
                "calculated_at",
            ),
            "transform_expiration_payoff_thresholds": (
                "calculation_id", "structure_costs_result", "calculated_at",
            ),
        }
        for name, expected in signatures.items():
            with self.subTest(name=name):
                self.assertEqual(
                    tuple(inspect.signature(getattr(
                        market_data_transformations, name
                    )).parameters),
                    expected,
                )
        self.assertEqual(
            tuple(inspect.signature(
                risk_assessment.assess_structure_affordability
            ).parameters),
            (
                "calculation_id", "structure_costs_result",
                "risk_budget_assumptions", "calculated_at",
            ),
        )
        self.assertFalse(hasattr(
            convexity_hunter, "CandidateResearchRecordAssemblyResult"
        ))
        self.assertFalse(hasattr(
            convexity_hunter, "assemble_candidate_research_record"
        ))
        import convexity_hunter.report as report_module
        import convexity_hunter.scanner as scanner_module
        self.assertEqual(
            tuple(inspect.signature(scanner_module.screen_candidate).parameters),
            ("candidate", "policy"),
        )
        self.assertEqual(
            tuple(inspect.signature(
                report_module.render_candidate_markdown
            ).parameters),
            (
                "candidate",
                "locale",
                "screening_decision",
                "position_management_plan_result",
            ),
        )

    def test_fresh_interpreter_import_order_matrix(self):
        commands = (
            "import convexity_hunter.market_data_transformations; "
            "import convexity_hunter.risk_assessment; "
            "import convexity_hunter.candidate_assembly",
            "import convexity_hunter.risk_assessment; "
            "import convexity_hunter.market_data_transformations; "
            "import convexity_hunter.candidate_assembly",
            "import convexity_hunter.candidate_assembly",
            "import convexity_hunter.candidate_assembly; "
            "import convexity_hunter.market_data_transformations; "
            "import convexity_hunter.risk_assessment",
        )
        for index, command in enumerate(commands):
            with self.subTest(order=index):
                completed = subprocess.run(
                    [sys.executable, "-c", command],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)


class MalformedOuterWrapperStructuralValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = complete_artifacts()
        cls.complete = assemble_artifacts(cls.artifacts)

    def assert_direct_rejects(self, result, artifact_index, artifact, pattern):
        values = direct_values(result)
        values[artifact_index + 1] = artifact
        with self.assertRaisesRegex(ValueError, pattern):
            CandidateResearchRecordAssemblyResult(*values)

    def test_all_seven_empty_exact_wrappers_raise_controlled_value_error(self):
        for index, (name, authentic) in enumerate(zip(
            assembly._ARTIFACT_FIELDS, self.artifacts
        )):
            malformed = object.__new__(type(authentic))
            required = "records" if hasattr(authentic, "records") else "record"
            with self.subTest(field=name):
                self.assert_direct_rejects(
                    self.complete,
                    index,
                    malformed,
                    rf"^{name} lacks required field {required}$",
                )

    def test_partial_watch_dependency_paths_reject_before_state_rules(self):
        v, tail, _liquidity, costs, scenario, expiration, affordability = (
            self.artifacts
        )
        cases = (
            ("volatility", (v,) + (None,) * 6, 0),
            ("tail", (v, tail) + (None,) * 5, 1),
            ("scenario", (v, tail, None, costs, scenario, None, None), 4),
            ("expiration", (None, None, None, costs, None, expiration, None), 5),
            ("affordability", (None, None, None, costs, None, None, affordability), 6),
        )
        for label, artifacts, malformed_index in cases:
            valid = assemble_artifacts(
                artifacts,
                CandidateState.WATCH,
                (f"{label} partial fixture",),
            )
            malformed = object.__new__(type(artifacts[malformed_index]))
            required = (
                "records"
                if hasattr(artifacts[malformed_index], "records")
                else "record"
            )
            with self.subTest(path=label):
                self.assert_direct_rejects(
                    valid,
                    malformed_index,
                    malformed,
                    rf"lacks required field {required}",
                )

        arguments = list(zero_arguments(CandidateState.WATCH))
        arguments[7] = object.__new__(type(v))
        with self.assertRaisesRegex(
            ValueError,
            "volatility_environment_result lacks required field record",
        ):
            assemble_candidate_research_record(*arguments)

    def test_partially_initialized_single_and_tuple_wrappers(self):
        v = self.artifacts[0]
        tail = self.artifacts[1]
        cases = (
            ("single-record-only", 0, v, "record", v.record, "lineage"),
            ("single-lineage-only", 0, v, "lineage", v.lineage, "record"),
            ("tuple-records-only", 1, tail, "records", tail.records, "lineage"),
            ("tuple-lineage-only", 1, tail, "lineage", tail.lineage, "records"),
        )
        for label, index, authentic, present_name, present_value, absent in cases:
            malformed = object.__new__(type(authentic))
            object.__setattr__(malformed, present_name, present_value)
            with self.subTest(shape=label):
                self.assert_direct_rejects(
                    self.complete,
                    index,
                    malformed,
                    rf"lacks required field {absent}",
                )

    def test_wrong_outer_types_remain_type_error(self):
        volatility = self.artifacts[0]
        WrapperSubclass = type(
            "WrapperSubclass", (type(volatility),), {}
        )
        cases = (
            ("unrelated-object", object()),
            ("wrong-wrapper", self.artifacts[1]),
            ("subclass", object.__new__(WrapperSubclass)),
        )
        for label, artifact in cases:
            values = direct_values(self.complete)
            values[1] = artifact
            with self.subTest(kind=label), self.assertRaises(TypeError):
                CandidateResearchRecordAssemblyResult(*values)

    def test_initialized_malformed_field_values_keep_exception_taxonomy(self):
        volatility = self.artifacts[0]
        cases = (
            ("wrong-record-type", bypass(
                volatility, record=object()
            ), TypeError),
            ("wrong-lineage-type", bypass(
                volatility, lineage=object()
            ), TypeError),
            ("malformed-nested-record", bypass(
                volatility,
                record=bypass(volatility.record, reference_tenor_days=True),
            ), TypeError),
            ("malformed-lineage-content", bypass(
                volatility,
                lineage=bypass(
                    volatility.lineage, methodology_version="v9"
                ),
            ), ValueError),
        )
        for label, artifact, error in cases:
            values = direct_values(self.complete)
            values[1] = artifact
            with self.subTest(kind=label), self.assertRaises(error):
                CandidateResearchRecordAssemblyResult(*values)

    def test_structural_presence_precedes_state_and_missing_data(self):
        partial = assemble_artifacts(
            (self.artifacts[0],) + (None,) * 6,
            CandidateState.WATCH,
            ("partial",),
        )
        values = direct_values(partial)
        values[0] = bypass(
            partial.record,
            state=CandidateState.INVESTIGATE,
            missing_data=(),
        )
        values[1] = object.__new__(type(self.artifacts[0]))
        with self.assertRaisesRegex(
            ValueError,
            "volatility_environment_result lacks required field record",
        ):
            CandidateResearchRecordAssemblyResult(*values)


class ExistingWrapperEmptyLineageRegressionAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = complete_artifacts()
        cls.historical = transform_historical(
            make_historical_assessment()[0]
        )
        _costs, _tail, cls.provider, _volatility = (
            market_data_transformations
            ._reconstruct_scenario_valuation_dependencies(
                cls.artifacts[4].records, cls.artifacts[4].lineage
            )
        )

    def test_every_existing_calculated_wrapper_rejects_empty_lineage(self):
        wrappers = (
            ("historical", self.historical),
            ("volatility", self.artifacts[0]),
            ("tail", self.artifacts[1]),
            ("liquidity", self.artifacts[2]),
            ("costs", self.artifacts[3]),
            ("scenario-pricing", self.provider),
            ("scenario-valuation", self.artifacts[4]),
            ("expiration", self.artifacts[5]),
            ("affordability", self.artifacts[6]),
        )
        for label, wrapper in wrappers:
            empty = dataclasses.replace(wrapper.lineage, inputs=())
            arguments = (
                (wrapper.records, empty)
                if hasattr(wrapper, "records")
                else (wrapper.record, empty)
            )
            with self.subTest(label=label), self.assertRaises(ValueError):
                type(wrapper)(*arguments)


if __name__ == "__main__":
    unittest.main()
