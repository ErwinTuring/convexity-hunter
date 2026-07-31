import copy
import dataclasses
import datetime
import decimal
import inspect
import unittest
from dataclasses import FrozenInstanceError
from unittest import mock

import convexity_hunter
from convexity_hunter import market_data, market_data_transformations
from convexity_hunter.market_data import (
    CalculationInputReference,
    CalculationQualityFlag,
)
from convexity_hunter.market_data_transformations import ExactRational
from convexity_hunter.risk_assessment import (
    AffordabilityReasonCode,
    AffordabilityStatus,
    PortfolioValueAssumption,
    RiskBudgetAssumptions,
    StructureAffordabilityAssessmentResult,
    StructureAffordabilityEvidence,
    assess_structure_affordability,
)
import convexity_hunter.risk_assessment as risk

from test_market_data_transformations import (
    CALCULATED_AT,
    SESSION_DATE,
    make_cost_selection,
    make_structure,
    transform_costs,
)


def make_cost_result(*, repeated=2, fees=decimal.Decimal("1.25")):
    structure = make_structure(("call",))
    selection, _, _, _ = make_cost_selection(structure)
    return transform_costs(
        structure,
        selection,
        commissions_and_fees=fees,
        repeated_bet_count=repeated,
    )


def complete_assumptions(
    *,
    portfolio="100000.0",
    single=ExactRational(1, 100),
    repeated=ExactRational(1, 50),
):
    return RiskBudgetAssumptions(
        PortfolioValueAssumption(
            decimal.Decimal(portfolio), SESSION_DATE, " declared NAV "
        ),
        single,
        repeated,
        " risk policy ",
    )


def assess(assumptions=None, *, repeated=2, fees=decimal.Decimal("1.25")):
    costs = make_cost_result(repeated=repeated, fees=fees)
    return assess_structure_affordability(
        " affordability ",
        costs,
        complete_assumptions() if assumptions is None else assumptions,
        CALCULATED_AT + datetime.timedelta(seconds=1),
    )


def forge(value, **changes):
    result = object.__new__(type(value))
    for field in dataclasses.fields(value):
        object.__setattr__(
            result,
            field.name,
            changes.get(field.name, getattr(value, field.name)),
        )
    return result


class PublicContractTests(unittest.TestCase):
    def test_api_exports_fields_enums_signature_and_boundaries(self):
        self.assertEqual(risk.__all__, (
            "PortfolioValueAssumption",
            "RiskBudgetAssumptions",
            "AffordabilityStatus",
            "AffordabilityReasonCode",
            "StructureAffordabilityEvidence",
            "StructureAffordabilityAssessmentResult",
            "assess_structure_affordability",
        ))
        self.assertEqual(len(market_data.__all__), 64)
        self.assertEqual(len(market_data_transformations.__all__), 25)
        self.assertIs(ExactRational, market_data_transformations.ExactRational)
        self.assertFalse(hasattr(convexity_hunter, "PortfolioValueAssumption"))
        self.assertEqual(
            tuple(inspect.signature(assess_structure_affordability).parameters),
            (
                "calculation_id",
                "structure_costs_result",
                "risk_budget_assumptions",
                "calculated_at",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                PortfolioValueAssumption
            )),
            ("amount", "as_of_date", "methodology"),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                RiskBudgetAssumptions
            )),
            (
                "portfolio_value",
                "maximum_single_structure_loss_fraction",
                "maximum_repeated_loss_fraction",
                "risk_budget_methodology",
            ),
        )
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                StructureAffordabilityEvidence
            )),
            (
                "structure", "as_of_date", "assumptions",
                "single_position_maximum_loss", "repeated_bet_count",
                "repeated_aggregate_maximum_loss", "single_loss_fraction",
                "repeated_loss_fraction", "status", "reason_codes",
            ),
        )
        self.assertEqual(
            tuple(item.value for item in AffordabilityStatus),
            ("affordable", "not_affordable", "data_insufficient"),
        )
        self.assertEqual(
            tuple(item.value for item in AffordabilityReasonCode),
            (
                "missing_portfolio_value",
                "missing_single_loss_boundary",
                "missing_repeated_loss_boundary",
                "missing_risk_budget_methodology",
                "single_loss_exceeds_boundary",
                "repeated_loss_exceeds_boundary",
            ),
        )


class AssumptionTests(unittest.TestCase):
    def test_normalization_freezing_and_valid_boundaries(self):
        portfolio = PortfolioValueAssumption(
            decimal.Decimal("100000.0"), SESSION_DATE, " NAV "
        )
        self.assertEqual(portfolio.methodology, "NAV")
        assumptions = RiskBudgetAssumptions(
            portfolio, ExactRational(0, 1), ExactRational(1, 1), " policy "
        )
        self.assertEqual(assumptions.risk_budget_methodology, "policy")
        with self.assertRaises(FrozenInstanceError):
            portfolio.methodology = "x"
        self.assertEqual(RiskBudgetAssumptions(), RiskBudgetAssumptions())

    def test_portfolio_exact_type_and_value_rejections(self):
        for amount, error in (
            (1, TypeError), (1.0, TypeError), (True, TypeError),
            (decimal.Decimal("0"), ValueError),
            (decimal.Decimal("-1"), ValueError),
            (decimal.Decimal("NaN"), ValueError),
            (decimal.Decimal("Infinity"), ValueError),
        ):
            with self.subTest(amount=amount), self.assertRaises(error):
                PortfolioValueAssumption(amount, SESSION_DATE, "NAV")
        with self.assertRaises(TypeError):
            PortfolioValueAssumption(
                decimal.Decimal("1"),
                datetime.datetime(2026, 1, 1),
                "NAV",
            )
        with self.assertRaises(ValueError):
            PortfolioValueAssumption(
                decimal.Decimal("1"), SESSION_DATE, " "
            )

    def test_rational_and_methodology_rejections(self):
        for value in (0, 0.1, decimal.Decimal(".1"), True, {}, []):
            with self.subTest(value=value), self.assertRaises(TypeError):
                RiskBudgetAssumptions(
                    maximum_single_structure_loss_fraction=value
                )
        for value in (ExactRational(-1, 10), ExactRational(11, 10)):
            with self.assertRaises(ValueError):
                RiskBudgetAssumptions(
                    maximum_single_structure_loss_fraction=value
                )
        with self.assertRaises(TypeError):
            RiskBudgetAssumptions(risk_budget_methodology=1)
        with self.assertRaises(ValueError):
            RiskBudgetAssumptions(risk_budget_methodology=" ")

    def test_forged_nested_records_reject(self):
        forged_rational = object.__new__(ExactRational)
        object.__setattr__(forged_rational, "numerator", 2)
        object.__setattr__(forged_rational, "denominator", 4)
        with self.assertRaises(ValueError):
            RiskBudgetAssumptions(
                maximum_single_structure_loss_fraction=forged_rational
            )
        valid = PortfolioValueAssumption(
            decimal.Decimal("1"), SESSION_DATE, "NAV"
        )
        with self.assertRaises(ValueError):
            RiskBudgetAssumptions(
                portfolio_value=forge(valid, methodology=" ")
            )


class LiteralEconomicTests(unittest.TestCase):
    def test_exact_cost_authority_and_affordable_values(self):
        result = assess()
        self.assertEqual(
            result.record.single_position_maximum_loss,
            decimal.Decimal("141.250"),
        )
        self.assertEqual(
            result.record.repeated_aggregate_maximum_loss,
            decimal.Decimal("282.500"),
        )
        self.assertEqual(
            result.record.single_loss_fraction, ExactRational(113, 80000)
        )
        self.assertEqual(
            result.record.repeated_loss_fraction, ExactRational(113, 40000)
        )
        self.assertIs(result.record.status, AffordabilityStatus.AFFORDABLE)
        self.assertEqual(result.record.reason_codes, ())

    def test_single_repeated_and_both_breaches(self):
        cases = (
            (ExactRational(1, 1000), ExactRational(1, 1),
             (AffordabilityReasonCode.SINGLE_LOSS_EXCEEDS_BOUNDARY,)),
            (ExactRational(1, 1), ExactRational(1, 1000),
             (AffordabilityReasonCode.REPEATED_LOSS_EXCEEDS_BOUNDARY,)),
            (ExactRational(0, 1), ExactRational(0, 1), (
                AffordabilityReasonCode.SINGLE_LOSS_EXCEEDS_BOUNDARY,
                AffordabilityReasonCode.REPEATED_LOSS_EXCEEDS_BOUNDARY,
            )),
        )
        for single, repeated, reasons in cases:
            with self.subTest(reasons=reasons):
                result = assess(complete_assumptions(
                    single=single, repeated=repeated
                ))
                self.assertIs(
                    result.record.status, AffordabilityStatus.NOT_AFFORDABLE
                )
                self.assertEqual(result.record.reason_codes, reasons)

    def test_exact_equality_both_boundaries_is_affordable(self):
        cases = (
            (ExactRational(113, 80000), ExactRational(1, 1)),
            (ExactRational(1, 1), ExactRational(113, 40000)),
            (ExactRational(113, 80000), ExactRational(113, 40000)),
        )
        for single, repeated in cases:
            with self.subTest(single=single, repeated=repeated):
                assumptions = complete_assumptions(
                    single=single, repeated=repeated
                )
                self.assertIs(
                    assess(assumptions).record.status,
                    AffordabilityStatus.AFFORDABLE,
                )

    def test_mutated_public_float_cannot_override_exact_lineage(self):
        costs = make_cost_result()
        forged_record = forge(
            costs.record,
            quoted_mid_premium=costs.record.quoted_mid_premium + 1.0,
        )
        with self.assertRaises(ValueError):
            assess_structure_affordability(
                "new",
                forge(costs, record=forged_record),
                complete_assumptions(),
                CALCULATED_AT + datetime.timedelta(seconds=1),
            )

    def test_nonterminating_and_above_one_actual_fractions(self):
        structure = make_structure(("call",))
        object.__setattr__(structure, "assumed_portfolio_value", 3.0)
        selection, _, _, _ = make_cost_selection(structure)
        costs = transform_costs(
            structure, selection, commissions_and_fees=decimal.Decimal("1")
        )
        assumptions = complete_assumptions(
            portfolio="3.0",
            single=ExactRational(1, 1),
            repeated=ExactRational(1, 1),
        )
        result = assess_structure_affordability(
            "affordability", costs, assumptions,
            CALCULATED_AT + datetime.timedelta(seconds=1),
        )
        self.assertEqual(result.record.single_loss_fraction, ExactRational(47, 1))
        self.assertGreater(result.record.repeated_loss_fraction.numerator, 1)

    def test_repeated_count_one_and_greater_than_one(self):
        one = assess(repeated=1)
        three = assess(repeated=3)
        self.assertEqual(
            one.record.single_position_maximum_loss,
            one.record.repeated_aggregate_maximum_loss,
        )
        self.assertEqual(
            three.record.repeated_aggregate_maximum_loss,
            decimal.Decimal("423.750"),
        )


class MissingInputTests(unittest.TestCase):
    def test_missing_matrix_and_fraction_presence(self):
        portfolio = PortfolioValueAssumption(
            decimal.Decimal("100000.0"), SESSION_DATE, "NAV"
        )
        cases = (
            (RiskBudgetAssumptions(), tuple(AffordabilityReasonCode)[:4], False),
            (RiskBudgetAssumptions(
                portfolio, ExactRational(1, 100), ExactRational(1, 50), None
            ), (AffordabilityReasonCode.MISSING_RISK_BUDGET_METHODOLOGY,), True),
            (RiskBudgetAssumptions(
                portfolio, None, None, "policy"
            ), (
                AffordabilityReasonCode.MISSING_SINGLE_LOSS_BOUNDARY,
                AffordabilityReasonCode.MISSING_REPEATED_LOSS_BOUNDARY,
            ), True),
            (RiskBudgetAssumptions(
                portfolio, None, ExactRational(0, 1), "policy"
            ), (AffordabilityReasonCode.MISSING_SINGLE_LOSS_BOUNDARY,), True),
            (RiskBudgetAssumptions(
                portfolio, ExactRational(0, 1), None, "policy"
            ), (AffordabilityReasonCode.MISSING_REPEATED_LOSS_BOUNDARY,), True),
            (RiskBudgetAssumptions(
                None, ExactRational(0, 1), ExactRational(0, 1), "policy"
            ), (AffordabilityReasonCode.MISSING_PORTFOLIO_VALUE,), False),
        )
        for assumptions, reasons, fractions in cases:
            with self.subTest(reasons=reasons):
                result = assess(assumptions)
                self.assertIs(
                    result.record.status,
                    AffordabilityStatus.DATA_INSUFFICIENT,
                )
                self.assertEqual(result.record.reason_codes, reasons)
                self.assertEqual(
                    result.record.single_loss_fraction is not None, fractions
                )
                self.assertIn(
                    CalculationQualityFlag.INCOMPLETE_INPUT_USED,
                    result.lineage.quality_flags,
                )
                self.assertNotIn(
                    AffordabilityReasonCode.SINGLE_LOSS_EXCEEDS_BOUNDARY,
                    result.record.reason_codes,
                )


class CompatibilityChronologyTests(unittest.TestCase):
    def test_portfolio_value_and_date_mismatches_reject(self):
        with self.assertRaises(ValueError):
            assess(complete_assumptions(portfolio="99999"))
        bad = complete_assumptions()
        bad = dataclasses.replace(
            bad,
            portfolio_value=PortfolioValueAssumption(
                bad.portfolio_value.amount,
                SESSION_DATE + datetime.timedelta(days=1),
                "NAV",
            ),
        )
        with self.assertRaises(ValueError):
            assess(bad)

    def test_id_time_and_exact_argument_types(self):
        costs = make_cost_result()
        with self.assertRaises(ValueError):
            assess_structure_affordability(
                costs.lineage.calculation_id, costs, complete_assumptions(),
                CALCULATED_AT + datetime.timedelta(seconds=1),
            )
        with self.assertRaises(ValueError):
            assess_structure_affordability(
                costs.lineage.inputs[0].record_id, costs,
                complete_assumptions(),
                CALCULATED_AT + datetime.timedelta(seconds=1),
            )
        with self.assertRaises(ValueError):
            assess_structure_affordability(
                "new", costs, complete_assumptions(),
                costs.lineage.calculated_at - datetime.timedelta(seconds=1),
            )
        with self.assertRaises(ValueError):
            assess_structure_affordability(
                "new", costs, complete_assumptions(),
                datetime.datetime(2026, 1, 1),
            )
        for index, value in enumerate((1, object(), object(), object())):
            args = [
                "new", costs, complete_assumptions(),
                CALCULATED_AT + datetime.timedelta(seconds=1),
            ]
            args[index] = value
            with self.subTest(index=index), self.assertRaises(TypeError):
                assess_structure_affordability(*args)

    def test_timezone_normalization_and_determinism(self):
        costs = make_cost_result()
        at = (CALCULATED_AT + datetime.timedelta(seconds=1)).astimezone(
            datetime.timezone(datetime.timedelta(hours=8))
        )
        first = assess_structure_affordability(
            "id", costs, complete_assumptions(), at
        )
        second = assess_structure_affordability(
            "id", costs, complete_assumptions(), at
        )
        self.assertEqual(first, second)
        self.assertEqual(first.lineage.calculated_at.tzinfo, datetime.timezone.utc)


class TrustBoundaryTests(unittest.TestCase):
    def test_authentic_wrapper_reconstruction_and_forged_evidence(self):
        result = assess()
        rebuilt = StructureAffordabilityAssessmentResult(
            result.record, result.lineage
        )
        self.assertEqual(rebuilt, result)
        with self.assertRaises(ValueError):
            StructureAffordabilityAssessmentResult(
                forge(
                    result.record,
                    repeated_aggregate_maximum_loss=decimal.Decimal("1"),
                ),
                result.lineage,
            )

    def test_direct_evidence_type_arithmetic_status_and_reason_rejections(self):
        result = assess()
        class IntSubclass(int):
            pass

        mutations = (
            ({"repeated_bet_count": True}, TypeError),
            ({"repeated_bet_count": IntSubclass(2)}, TypeError),
            ({"single_position_maximum_loss": decimal.Decimal("NaN")}, ValueError),
            ({"single_position_maximum_loss": decimal.Decimal("0")}, ValueError),
            ({"single_position_maximum_loss": decimal.Decimal("Infinity")}, ValueError),
            ({"as_of_date": datetime.datetime(2026, 1, 1)}, TypeError),
            ({"single_loss_fraction": ExactRational(1, 2)}, ValueError),
            ({"status": AffordabilityStatus.NOT_AFFORDABLE}, ValueError),
            ({"reason_codes": []}, TypeError),
            ({"reason_codes": (
                AffordabilityReasonCode.SINGLE_LOSS_EXCEEDS_BOUNDARY,
                AffordabilityReasonCode.SINGLE_LOSS_EXCEEDS_BOUNDARY,
            )}, ValueError),
            ({"reason_codes": (
                AffordabilityReasonCode.REPEATED_LOSS_EXCEEDS_BOUNDARY,
                AffordabilityReasonCode.SINGLE_LOSS_EXCEEDS_BOUNDARY,
            )}, ValueError),
        )
        for changes, error in mutations:
            with self.subTest(changes=changes), self.assertRaises(error):
                StructureAffordabilityEvidence(
                    **{
                        field.name: changes.get(
                            field.name, getattr(result.record, field.name)
                        )
                        for field in dataclasses.fields(result.record)
                    }
                )

    def test_forged_structure_leg_assumption_and_rational_reject(self):
        result = assess()
        bad_leg = forge(result.record.structure.legs[0], quantity=True)
        bad_structure = forge(
            result.record.structure, legs=(bad_leg,)
        )
        with self.assertRaises(TypeError):
            dataclasses.replace(result.record, structure=bad_structure)
        bad_assumptions = forge(
            result.record.assumptions, risk_budget_methodology=" "
        )
        with self.assertRaises(ValueError):
            dataclasses.replace(result.record, assumptions=bad_assumptions)
        bad_fraction = object.__new__(ExactRational)
        object.__setattr__(bad_fraction, "numerator", 2)
        object.__setattr__(bad_fraction, "denominator", 4)
        with self.assertRaises(ValueError):
            dataclasses.replace(result.record, single_loss_fraction=bad_fraction)


class CanonicalLineageTests(unittest.TestCase):
    def mutate(self, result, callback):
        decoded = copy.deepcopy(risk._decode_parameters(
            result.lineage.parameters_json
        ))
        callback(decoded)
        return dataclasses.replace(
            result.lineage,
            parameters_json=market_data.canonicalize_lineage_parameters(decoded),
        )

    def test_exact_schema_and_dependency_retention(self):
        result = assess()
        decoded = risk._decode_parameters(result.lineage.parameters_json)
        self.assertEqual(set(decoded), risk._PARAMETER_KEYS)
        dependency = decoded["structure_costs_dependency"]
        costs = make_cost_result()
        self.assertEqual(
            dependency["parameters_json"], costs.lineage.parameters_json
        )
        self.assertEqual(
            tuple(decoded["risk_budget_assumptions"]["portfolio_value"]),
            ("amount", "as_of_date", "currency", "methodology"),
        )

    def test_complete_parameters_match_independent_literal_golden_bytes(self):
        expected = r'''{"$map":[["affordability_rule",{"$map":[["complete_rule","both_comparisons_must_pass"],["equality_boundary","affordable"],["incomplete_precedence","missing_assumptions_precede_boundary_breach_evaluation"],["repeated_comparison","repeated_loss_fraction<=maximum_repeated_loss_fraction"],["required_assumptions",{"$list":["portfolio_value","maximum_single_structure_loss_fraction","maximum_repeated_loss_fraction","risk_budget_methodology"]}],["single_comparison","single_loss_fraction<=maximum_single_structure_loss_fraction"]]}],["calculation_values",{"$map":[["maximum_repeated_loss_fraction",{"$map":[["denominator",50],["numerator",1]]}],["maximum_single_structure_loss_fraction",{"$map":[["denominator",100],["numerator",1]]}],["portfolio_value",{"$decimal":"100000.0"}],["repeated_aggregate_maximum_loss",{"$decimal":"282.500"}],["repeated_bet_count",2],["repeated_loss_fraction",{"$map":[["denominator",40000],["numerator",113]]}],["single_loss_fraction",{"$map":[["denominator",80000],["numerator",113]]}],["single_position_maximum_loss",{"$decimal":"141.250"}]]}],["currency","USD"],["limitations","Affordability evidence for one declared structure and equal repeated attempts only; no annual budget, committed exposure, inverse sizing, quantity recommendation, portfolio optimization, probability, expected return, screening, reporting, provider access, monitoring, or execution."],["outcome",{"$map":[["reason_codes",{"$list":[]}],["status","affordable"]]}],["output_architecture","standalone_structure_affordability_evidence"],["risk_budget_assumptions",{"$map":[["legacy_portfolio_value_correspondence","exact_equality_to_Decimal(str(assumed_portfolio_value))"],["maximum_repeated_loss_fraction",{"$map":[["denominator",50],["numerator",1]]}],["maximum_single_structure_loss_fraction",{"$map":[["denominator",100],["numerator",1]]}],["missing_assumption_policy","data_insufficient_without_boundary_breach_evaluation"],["portfolio_value",{"$map":[["amount",{"$decimal":"100000.0"}],["as_of_date",{"$date":"2030-01-02"}],["currency","USD"],["methodology","declared NAV"]]}],["risk_budget_methodology","risk policy"]]}],["risk_scope",{"$map":[["annual_budget","excluded"],["existing_committed_exposure","excluded"],["inverse_sizing","excluded"],["repeated_attempts","equal_repeated_attempts_not_concurrency_or_annual_frequency"],["single_position","one_already_specified_structure"]]}],["schema_version","v0.1"],["structure_costs_dependency",{"$map":[["calculated_at",{"$datetime":"2030-01-02T15:30:04.000000Z"}],["calculation_id","calculation-3c7b"],["calculation_type","structure_costs"],["input_rule","exact_reuse_of_structure_costs_lineage_inputs"],["methodology_id","exact-structure-costs"],["methodology_version","v0.2"],["parameters_json","{\"$map\":[[\"calculation_values\",{\"$map\":[[\"commissions_and_fees_exact\",{\"$decimal\":\"1.25\"}],[\"cumulative_repeated_bet_cost_exact\",{\"$decimal\":\"282.500\"}],[\"estimated_spread_cost_exact\",{\"$decimal\":\"20.000\"}],[\"gamma_exact\",{\"$decimal\":\"2.000\"}],[\"maximum_loss_exact\",{\"$decimal\":\"141.250\"}],[\"quoted_mid_premium_exact\",{\"$decimal\":\"120.000\"}],[\"stable_record_values\",{\"$map\":[[\"commissions_and_fees_repr\",\"1.25\"],[\"cumulative_repeated_bet_cost_repr\",\"282.5\"],[\"estimated_spread_cost_repr\",\"20.0\"],[\"gamma_repr\",\"2.0\"],[\"maximum_loss_repr\",\"141.25\"],[\"quoted_mid_premium_repr\",\"120.0\"],[\"theta_per_day_repr\",\"-10.0\"],[\"total_entry_cost_repr\",\"141.25\"],[\"underlying_price_repr\",\"100.0\"]]}],[\"theta_per_day_exact\",{\"$decimal\":\"-10.000\"}],[\"total_entry_cost_exact\",{\"$decimal\":\"141.250\"}],[\"underlying_price_exact\",{\"$decimal\":\"100.000\"}]]}],[\"commission_and_fee_scope\",\"entry_only_total_position\"],[\"commissions_and_fees_usd\",{\"$decimal\":\"1.25\"}],[\"gamma_input_unit\",\"option_value_change_per_usd_squared_per_underlying_unit\"],[\"gamma_position_rule\",\"sum(gamma_per_underlying_unit_per_usd_squared*quantity*contract_multiplier)\"],[\"greeks_methodology\",{\"$map\":[[\"dividend_input_description\",\"Synthetic dividend input\"],[\"model_name\",\"Synthetic Black-Scholes\"],[\"model_version\",\"fixture-v1\"],[\"rate_input_description\",\"Synthetic USD curve input\"],[\"theta_day_basis\",\"Provider calendar-day convention\"],[\"unit_convention\",\"Contract-defined canonical units\"]]}],[\"leg_correspondence\",{\"$list\":[{\"$map\":[[\"contract_multiplier\",100],[\"currency\",\"USD\"],[\"deliverable_id\",null],[\"expiration\",{\"$date\":\"2030-03-15\"}],[\"option_contract_reference_record_id\",\"cost-call-contract-reference\"],[\"option_greeks_record_id\",\"cost-call-greeks\"],[\"option_quote_record_id\",\"cost-call-quote\"],[\"option_type\",\"call\"],[\"quantity\",1],[\"strike\",{\"$decimal\":\"100.0\"}],[\"underlying\",{\"$map\":[[\"currency\",\"USD\"],[\"listing_mic\",\"ARCX\"],[\"security_type\",\"etf\"],[\"symbol\",\"SPY\"]]}],[\"underlying_quote_record_id\",\"cost-underlying-quote\"]]}]}],[\"normalized_evidence\",{\"$map\":[[\"contract_references\",{\"$list\":[{\"$map\":[[\"contract_multiplier\",100],[\"currency\",\"USD\"],[\"deliverable_id\",null],[\"exercise_style\",\"American\"],[\"expiration\",{\"$date\":\"2030-03-15\"}],[\"last_trade_date\",{\"$date\":\"2030-03-14\"}],[\"listing_date\",{\"$date\":\"2029-09-16\"}],[\"normalized_at\",{\"$datetime\":\"2030-01-02T15:30:00.000002Z\"}],[\"option_type\",\"call\"],[\"propagated_quality_flags\",{\"$list\":[]}],[\"quantity\",1],[\"record_id\",\"cost-call-contract-reference\"],[\"settlement_type\",\"Physical\"],[\"source_ids\",{\"$list\":[\"cost-call-contract-reference-source-0\"]}],[\"strike\",{\"$decimal\":\"100.0\"}],[\"underlying\",{\"$map\":[[\"currency\",\"USD\"],[\"listing_mic\",\"ARCX\"],[\"security_type\",\"etf\"],[\"symbol\",\"SPY\"]]}]]}]}],[\"option_greeks\",{\"$list\":[{\"$map\":[[\"contract_multiplier\",100],[\"currency\",\"USD\"],[\"deliverable_id\",null],[\"dividend_input_description\",\"Synthetic dividend input\"],[\"expiration\",{\"$date\":\"2030-03-15\"}],[\"gamma\",{\"$decimal\":\"0.020\"}],[\"model_name\",\"Synthetic Black-Scholes\"],[\"model_version\",\"fixture-v1\"],[\"normalized_at\",{\"$datetime\":\"2030-01-02T15:30:00.000002Z\"}],[\"option_type\",\"call\"],[\"propagated_quality_flags\",{\"$list\":[]}],[\"quantity\",1],[\"rate_input_description\",\"Synthetic USD curve input\"],[\"record_id\",\"cost-call-greeks\"],[\"session_date\",{\"$date\":\"2030-01-02\"}],[\"source_ids\",{\"$list\":[\"cost-call-greeks-source-0\"]}],[\"strike\",{\"$decimal\":\"100.0\"}],[\"theta\",{\"$decimal\":\"-0.100\"}],[\"theta_day_basis\",\"Provider calendar-day convention\"],[\"underlying\",{\"$map\":[[\"currency\",\"USD\"],[\"listing_mic\",\"ARCX\"],[\"security_type\",\"etf\"],[\"symbol\",\"SPY\"]]}],[\"unit_convention\",\"Contract-defined canonical units\"]]}]}],[\"option_quotes\",{\"$list\":[{\"$map\":[[\"ask_premium\",{\"$decimal\":\"1.40\"}],[\"bid_premium\",{\"$decimal\":\"1.00\"}],[\"contract_multiplier\",100],[\"currency\",\"USD\"],[\"deliverable_id\",null],[\"expiration\",{\"$date\":\"2030-03-15\"}],[\"normalized_at\",{\"$datetime\":\"2030-01-02T15:30:00.000002Z\"}],[\"option_type\",\"call\"],[\"propagated_quality_flags\",{\"$list\":[]}],[\"quantity\",1],[\"record_id\",\"cost-call-quote\"],[\"session_date\",{\"$date\":\"2030-01-02\"}],[\"source_ids\",{\"$list\":[\"cost-call-quote-source-0\"]}],[\"strike\",{\"$decimal\":\"100.0\"}],[\"underlying\",{\"$map\":[[\"currency\",\"USD\"],[\"listing_mic\",\"ARCX\"],[\"security_type\",\"etf\"],[\"symbol\",\"SPY\"]]}]]}]}],[\"underlying_quote\",{\"$map\":[[\"ask_price\",{\"$decimal\":\"101.00\"}],[\"bid_price\",{\"$decimal\":\"99.00\"}],[\"midpoint_rule\",\"(bid_price+ask_price)/2\"],[\"normalized_at\",{\"$datetime\":\"2030-01-02T15:30:00.000002Z\"}],[\"propagated_quality_flags\",{\"$list\":[]}],[\"record_id\",\"cost-underlying-quote\"],[\"session_date\",{\"$date\":\"2030-01-02\"}],[\"source_ids\",{\"$list\":[\"cost-underlying-quote-source-0\"]}],[\"underlying\",{\"$map\":[[\"currency\",\"USD\"],[\"listing_mic\",\"ARCX\"],[\"security_type\",\"etf\"],[\"symbol\",\"SPY\"]]}],[\"underlying_price_exact\",{\"$decimal\":\"100.000\"}]]}]]}],[\"position_value_unit\",\"usd\"],[\"premium_input_unit\",\"usd_per_underlying_unit\"],[\"premium_midpoint_rule\",\"sum(((bid_premium+ask_premium)/2)*quantity*contract_multiplier)\"],[\"repeated_bet_count\",2],[\"spread_cost_rule\",\"sum(((ask_premium-bid_premium)/2)*quantity*contract_multiplier)\"],[\"spread_cost_scope\",\"entry_only_midpoint_to_ask\"],[\"structure_identity\",{\"$map\":[[\"assumed_portfolio_value_repr\",\"100000.0\"],[\"expected_holding_days\",14],[\"legs\",{\"$list\":[{\"$map\":[[\"contract_multiplier\",100],[\"expiration\",{\"$date\":\"2030-03-15\"}],[\"option_type\",\"call\"],[\"quantity\",1],[\"strike_float_repr\",\"100.0\"],[\"underlying\",\"SPY\"]]}]}],[\"structure_type\",\"long_call\"],[\"underlying\",\"SPY\"]]}],[\"theta_day_basis\",\"Provider calendar-day convention\"],[\"theta_input_unit\",\"usd_per_underlying_unit_per_declared_day_basis\"],[\"theta_position_rule\",\"sum(theta_per_underlying_unit_per_declared_day_basis*quantity*contract_multiplier)\"],[\"underlying_price_rule\",\"(bid_price+ask_price)/2\"],[\"underlying_price_unit\",\"usd_per_underlying_share\"]]}"],["quality_flags",{"$list":["decimal_to_float_converted","assumption_applied"]}]]}]]}'''
        self.assertEqual(
            assess().lineage.parameters_json,
            expected,
        )

    def test_top_level_nested_and_semantic_mutations_reject(self):
        result = assess()
        mutations = (
            lambda value: value.pop("currency"),
            lambda value: value.update(extra=True),
            lambda value: value["risk_scope"].pop("annual_budget"),
            lambda value: value["risk_scope"].update(annual_budget="included"),
            lambda value: value["risk_scope"].update(
                repeated_attempts="annual_frequency"
            ),
            lambda value: value["structure_costs_dependency"].update(
                methodology_version="v9"
            ),
            lambda value: value["structure_costs_dependency"].update(
                input_rule="copied_inputs"
            ),
            lambda value: value["risk_budget_assumptions"].update(
                risk_budget_methodology="other"
            ),
            lambda value: value["risk_budget_assumptions"].update(
                missing_assumption_policy="evaluate_breaches"
            ),
            lambda value: value["calculation_values"].update(
                repeated_bet_count=99
            ),
            lambda value: value["affordability_rule"].update(
                required_assumptions=(
                    "risk_budget_methodology",
                    "portfolio_value",
                    "maximum_single_structure_loss_fraction",
                    "maximum_repeated_loss_fraction",
                )
            ),
            lambda value: value["affordability_rule"].update(
                single_comparison="single_loss_fraction<boundary"
            ),
            lambda value: value["affordability_rule"].update(
                repeated_comparison="repeated_loss_fraction<boundary"
            ),
            lambda value: value["affordability_rule"].update(
                equality_boundary="not_affordable"
            ),
            lambda value: value["affordability_rule"].update(
                incomplete_precedence="breaches_first"
            ),
            lambda value: value["outcome"].update(status="not_affordable"),
            lambda value: value.update(limitations="none"),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                lineage = self.mutate(result, mutation)
                with self.assertRaises((TypeError, ValueError)):
                    StructureAffordabilityAssessmentResult(
                        result.record, lineage
                    )

    def test_rational_dependency_and_outcome_order_mutations_reject(self):
        result = assess()
        mutations = (
            lambda value: value["calculation_values"][
                "single_loss_fraction"
            ].update(numerator=226, denominator=160000),
            lambda value: value["calculation_values"][
                "single_loss_fraction"
            ].update(denominator=0),
            lambda value: value["structure_costs_dependency"].update(
                parameters_json="{}"
            ),
            lambda value: value["outcome"].update(reason_codes=(
                "repeated_loss_exceeds_boundary",
                "single_loss_exceeds_boundary",
            )),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                lineage = self.mutate(result, mutation)
                with self.assertRaises((TypeError, ValueError)):
                    StructureAffordabilityAssessmentResult(
                        result.record, lineage
                    )

    def test_duplicate_float_malformed_tag_and_noncanonical_bytes_reject(self):
        result = assess()
        documents = (
            '{"$map":[["a",1],["a",2]]}',
            '{"$map":[["x",1.25]]}',
            '{"$map":[["x",{"$unknown":"1"}]]}',
            result.lineage.parameters_json + " ",
        )
        for document in documents:
            forged = forge(result.lineage, parameters_json=document)
            with self.subTest(document=document[:30]), self.assertRaises(ValueError):
                StructureAffordabilityAssessmentResult(result.record, forged)

    def test_lineage_identity_inputs_flags_and_chronology_reject(self):
        result = assess()
        costs = make_cost_result()
        mutations = (
            {"methodology_version": "v9"},
            {"calculation_id": costs.lineage.calculation_id},
            {"calculated_at": costs.lineage.calculated_at - datetime.timedelta(seconds=1)},
            {"quality_flags": (CalculationQualityFlag.ASSUMPTION_APPLIED,
                               CalculationQualityFlag.ANNUALIZED)},
            {"quality_flags": (
                CalculationQualityFlag.INCOMPLETE_INPUT_USED,
                CalculationQualityFlag.ASSUMPTION_APPLIED,
            )},
            {"inputs": costs.lineage.inputs[:-1]},
        )
        for changes in mutations:
            with self.subTest(changes=changes):
                forged = forge(result.lineage, **changes)
                with self.assertRaises((TypeError, ValueError)):
                    StructureAffordabilityAssessmentResult(
                        result.record, forged
                    )


class PrecedenceContextIsolationTests(unittest.TestCase):
    def test_dependency_and_assumption_validation_precede_arithmetic(self):
        costs = make_cost_result()
        forged_costs = forge(
            costs,
            lineage=forge(costs.lineage, methodology_version="v9"),
        )
        with mock.patch.object(
            risk, "_multiply_decimal_int_exact",
            side_effect=AssertionError("arithmetic reached"),
        ):
            with self.assertRaises(ValueError):
                assess_structure_affordability(
                    "new", forged_costs, complete_assumptions(),
                    CALCULATED_AT + datetime.timedelta(seconds=1),
                )
        forged_assumptions = forge(
            complete_assumptions(), risk_budget_methodology=" "
        )
        with mock.patch.object(
            risk, "_multiply_decimal_int_exact",
            side_effect=AssertionError("arithmetic reached"),
        ):
            with self.assertRaises(ValueError):
                assess_structure_affordability(
                    "new", costs, forged_assumptions,
                    CALCULATED_AT + datetime.timedelta(seconds=1),
                )

    def test_decimal_context_preserved_success_and_failure(self):
        context = decimal.getcontext()
        original = context.copy()
        context.prec = 7
        context.rounding = decimal.ROUND_FLOOR
        context.clear_flags()
        state = (
            context.prec, context.rounding, context.Emin, context.Emax,
            tuple(context.traps.items()), tuple(context.flags.items()),
        )
        try:
            assess()
            self.assertEqual(state, (
                context.prec, context.rounding, context.Emin, context.Emax,
                tuple(context.traps.items()), tuple(context.flags.items()),
            ))
            with self.assertRaises(ValueError):
                assess(complete_assumptions(portfolio="1"))
            self.assertEqual(state, (
                context.prec, context.rounding, context.Emin, context.Emax,
                tuple(context.traps.items()), tuple(context.flags.items()),
            ))
        finally:
            decimal.setcontext(original)

    def test_extreme_decimal_conversion_is_exact_or_controlled(self):
        context = decimal.getcontext()
        before = (
            context.prec, context.rounding, context.Emin, context.Emax,
            context.capitals, context.clamp,
            tuple(context.traps.items()), tuple(context.flags.items()),
        )
        positive = risk._decimal_to_rational(decimal.Decimal("1E+10001"))
        negative = risk._decimal_to_rational(decimal.Decimal("1E-10001"))
        self.assertEqual(positive, ExactRational(10 ** 10001, 1))
        self.assertEqual(negative, ExactRational(1, 10 ** 10001))
        self.assertEqual(before, (
            context.prec, context.rounding, context.Emin, context.Emax,
            context.capitals, context.clamp,
            tuple(context.traps.items()), tuple(context.flags.items()),
        ))

    def test_explicit_isolation_sentinels(self):
        costs = make_cost_result()
        blocked = (
            "CandidateResearchRecord", "screening", "report", "provider",
            "service", "scenario", "tail_pricing",
            "position_sizing", "monitoring", "execution",
        )
        with mock.patch.multiple(
            risk,
            **{
                name: mock.DEFAULT
                for name in blocked
            },
            create=True,
        ) as sentinels:
            for sentinel in sentinels.values():
                sentinel.side_effect = AssertionError("prohibited path reached")
            result = assess_structure_affordability(
                "new", costs, complete_assumptions(),
                CALCULATED_AT + datetime.timedelta(seconds=1),
            )
        self.assertIs(result.record.status, AffordabilityStatus.AFFORDABLE)


class AcceptedCorrectionTests(unittest.TestCase):
    class StringSubclass(str):
        pass

    class DatetimeSubclass(datetime.datetime):
        pass

    def forged_input(self, original, field, value):
        return forge(original, **{field: value})

    def forged_dependency(self, costs, forged_input):
        inputs = (forged_input,) + costs.lineage.inputs[1:]
        return forge(
            costs,
            lineage=forge(costs.lineage, inputs=inputs),
        )

    def test_authentic_input_reconstruction_succeeds(self):
        result = assess()
        rebuilt = tuple(
            risk._strict_input_reference(item)
            for item in result.lineage.inputs
        )
        self.assertTrue(
            risk._input_tuples_match(result.lineage.inputs, rebuilt)
        )
        self.assertEqual(
            StructureAffordabilityAssessmentResult(
                result.record, result.lineage
            ),
            result,
        )

    def test_producer_rejects_every_forged_nested_input_field_locally(self):
        costs = make_cost_result()
        original = costs.lineage.inputs[0]
        subclass_time = self.DatetimeSubclass(
            original.normalized_at.year,
            original.normalized_at.month,
            original.normalized_at.day,
            original.normalized_at.hour,
            original.normalized_at.minute,
            original.normalized_at.second,
            original.normalized_at.microsecond,
            tzinfo=datetime.timezone.utc,
        )
        cases = (
            self.forged_input(
                original,
                "record_id",
                self.StringSubclass(original.record_id),
            ),
            self.forged_input(
                original,
                "source_ids",
                (
                    self.StringSubclass(original.source_ids[0]),
                    *original.source_ids[1:],
                ),
            ),
            self.forged_input(
                original, "source_ids", list(original.source_ids)
            ),
            self.forged_input(
                original, "normalized_at", subclass_time
            ),
        )
        for forged_input in cases:
            with self.subTest(forged_input=forged_input):
                with self.assertRaises(TypeError):
                    assess_structure_affordability(
                        "new",
                        self.forged_dependency(costs, forged_input),
                        complete_assumptions(),
                        CALCULATED_AT + datetime.timedelta(seconds=1),
                    )

    def test_result_wrapper_rejects_every_forged_nested_input_field(self):
        result = assess()
        original = result.lineage.inputs[0]
        subclass_time = self.DatetimeSubclass(
            original.normalized_at.year,
            original.normalized_at.month,
            original.normalized_at.day,
            original.normalized_at.hour,
            original.normalized_at.minute,
            original.normalized_at.second,
            original.normalized_at.microsecond,
            tzinfo=datetime.timezone.utc,
        )
        cases = (
            self.forged_input(
                original,
                "record_id",
                self.StringSubclass(original.record_id),
            ),
            self.forged_input(
                original,
                "source_ids",
                (
                    self.StringSubclass(original.source_ids[0]),
                    *original.source_ids[1:],
                ),
            ),
            self.forged_input(
                original, "source_ids", list(original.source_ids)
            ),
            self.forged_input(
                original, "normalized_at", subclass_time
            ),
        )
        for forged_input in cases:
            forged_lineage = forge(
                result.lineage,
                inputs=(forged_input,) + result.lineage.inputs[1:],
            )
            with self.subTest(forged_input=forged_input):
                with self.assertRaises(TypeError):
                    StructureAffordabilityAssessmentResult(
                        result.record, forged_lineage
                    )

    def test_affordability_has_no_expiration_private_validator_dependency(self):
        result = assess()
        with mock.patch.object(
            market_data_transformations,
            "_validate_expiration_threshold_structure",
            side_effect=AssertionError("Milestone 4 validator invoked"),
        ):
            produced = assess()
            evidence = StructureAffordabilityEvidence(
                **{
                    field.name: getattr(result.record, field.name)
                    for field in dataclasses.fields(result.record)
                }
            )
            wrapped = StructureAffordabilityAssessmentResult(
                result.record, result.lineage
            )
        self.assertIs(produced.record.status, AffordabilityStatus.AFFORDABLE)
        self.assertEqual(evidence, result.record)
        self.assertEqual(wrapped, result)


if __name__ == "__main__":
    unittest.main()
