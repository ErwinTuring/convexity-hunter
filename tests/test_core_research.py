import datetime
import decimal
import unittest

import convexity_hunter
from convexity_hunter import core_research as core
from convexity_hunter.market_data import DataOrigin, SourceReference
from tests.test_market_data_transformations import make_volatility_result


UTC = datetime.timezone.utc
D = decimal.Decimal


def make_source(source_id="source-1"):
    observed = datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    return SourceReference(
        source_id=source_id,
        provider_name="provider",
        dataset_name="dataset",
        provider_record_id="record-1",
        provider_request_id="request-1",
        source_symbol="XYZ",
        source_uri="https://example.test/source-1",
        observed_at=observed,
        retrieved_at=observed + datetime.timedelta(seconds=1),
        provider_timezone="UTC",
        timestamp_methodology="provider timestamp",
        origin=DataOrigin.EXCHANGE_OBSERVED,
        is_delayed=False,
        declared_delay_seconds=None,
        payload_sha256=None,
        revision_number=None,
        provider_correction_id=None,
        quality_flags=(),
    )


def make_provenance(source=None, description="declared basis"):
    return core.CoreProvenance(source, description)


def make_leg(
    option_type=core.CoreOptionType.CALL,
    *,
    leg_id="call-1",
    underlying="XYZ",
    currency="USD",
    strike=D("100"),
    expiration=datetime.date(2027, 1, 15),
    quantity=1,
    contract_multiplier=100,
    ask=D("0.05"),
    source=None,
):
    return core.CoreLeg(
        leg_id=leg_id,
        underlying=underlying,
        currency=currency,
        option_type=option_type,
        strike=strike,
        expiration=expiration,
        quantity=quantity,
        contract_multiplier=contract_multiplier,
        ask_per_underlying_unit=ask,
        ask_authority=core.CoreAskAuthority.INDICATIVE_ONLY,
        description="long option leg",
        provenance=make_provenance(source),
    )


def make_structure(legs, source=None):
    return core.CoreStructure(
        legs=tuple(legs),
        description="declared structure",
        provenance=make_provenance(source),
    )


def make_payoff(source=None):
    return core.CorePayoffModel(
        authority=core.CorePayoffAuthority.CONDITIONAL_STANDARD_PAYOFF,
        model_id="standard-expiration-payoff",
        model_version="v0.1",
        description="approved conditional standard payoff basis",
        provenance=make_provenance(source, "approved model basis"),
    )


def make_component(
    component_id="fee",
    *,
    status=core.CoreCostComponentStatus.EXPLICIT_UPPER_BOUND,
    upper_bound=D("2"),
    currency="USD",
    source=None,
):
    return core.CoreCostComponent(
        component_id=component_id,
        status=status,
        upper_bound=upper_bound,
        currency=currency,
        methodology="caller-declared fee upper bound",
        description="explicit fee basis",
        provenance=make_provenance(source, "fee basis"),
    )


def make_ledger(
    source=None,
    *,
    premium_bound=D("8"),
    components=(None,),
    required=("fee",),
    currency="USD",
):
    if components == (None,):
        components = (make_component(source=source, currency=currency),)
    return core.CoreCostLedger(
        premium_bound=premium_bound,
        impact_components=tuple(components),
        required_component_ids=tuple(required),
        currency=currency,
        methodology="caller-declared conditional total-cost upper bound",
        description="explicit position-level premium and impact basis",
        provenance=make_provenance(source, "total-cost basis"),
    )


def make_risk(
    source=None,
    *,
    portfolio_value=D("1000"),
    maximum_single=D("0.02"),
    maximum_repeated=D("0.04"),
    repeat_count=2,
    currency="USD",
):
    return core.CoreRiskRepeatPolicy(
        portfolio_value=portfolio_value,
        maximum_single_loss_fraction=maximum_single,
        maximum_repeated_loss_fraction=maximum_repeated,
        repeat_count=repeat_count,
        methodology="caller-declared conditional loss budget",
        currency=currency,
        description="explicit conditional loss and repeat basis",
        provenance=make_provenance(source, "loss policy basis"),
    )


def make_sensitivity(source=None, *, legs=1):
    ask_per_leg = tuple(D("0.06") for _ in range(legs))
    point = core.CoreSensitivityPoint(
        point_id="s-1",
        terminal_underlying_price=D("100"),
        ask_per_leg=ask_per_leg,
        description="declared sensitivity point",
        provenance=make_provenance(source, "sensitivity basis"),
    )
    return core.CoreSensitivity(
        points=(point,),
        description="predeclared descriptive sensitivity",
        provenance=make_provenance(source, "sensitivity collection basis"),
    )


def make_request(
    *,
    source=None,
    structure=None,
    payoff=object(),
    ledger=object(),
    risk=object(),
    sensitivity=object(),
    enhancements=(),
):
    if structure is None:
        structure = make_structure((make_leg(source=source),), source)
    if payoff is _MISSING:
        payoff = make_payoff(source)
    if ledger is _MISSING:
        ledger = make_ledger(source)
    if risk is _MISSING:
        risk = make_risk(source)
    if sensitivity is _MISSING:
        sensitivity = make_sensitivity(source)
    return core.CoreResearchRequest(
        case_id="case-1",
        structure=structure,
        payoff_model=payoff,
        cost_ledger=ledger,
        risk_policy=risk,
        sensitivity=sensitivity,
        reviewed_enhancements=tuple(enhancements),
        description="core request",
        provenance=make_provenance(source, "request basis"),
    )


_MISSING = object()


class CoreResearchTests(unittest.TestCase):
    def test_direct_module_surface_and_no_package_root_export(self):
        self.assertTrue(hasattr(core, "evaluate_core_research"))
        self.assertFalse(hasattr(convexity_hunter, "CoreLeg"))
        self.assertEqual(
            core.CorePayoffAuthority.CONDITIONAL_STANDARD_PAYOFF.value,
            "CONDITIONAL_STANDARD_PAYOFF",
        )
        self.assertEqual(
            core.CoreAskAuthority.INDICATIVE_ONLY.value,
            "INDICATIVE_ONLY",
        )

    def test_exact_decimal_validation_and_constructor_bypass_rejection(self):
        with self.assertRaises(TypeError):
            make_leg(strike=1)
        with self.assertRaises(TypeError):
            make_leg(ask=True)
        with self.assertRaises(ValueError):
            make_leg(ask=D("NaN"))

        request = make_request(source=make_source(), payoff=_MISSING, ledger=_MISSING, risk=_MISSING, sensitivity=_MISSING)
        forged_leg = request.structure.legs[0]
        object.__setattr__(forged_leg, "strike", 100)
        with self.assertRaises(TypeError):
            core.evaluate_core_research(request)

    def test_full_source_reference_is_retained_and_request_identity_preserved(self):
        source = make_source("full-source")
        request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source),
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
        )
        result = core.evaluate_core_research(request)
        self.assertIs(result.request, request)
        self.assertIs(result.request.provenance.source_reference, source)
        self.assertIs(result.request.structure.legs[0].provenance.source_reference, source)
        self.assertEqual(source.provider_request_id, "request-1")
        self.assertEqual(source.quality_flags, ())

    def test_call_absolute_golden_hurdles_and_exact_budget(self):
        source = make_source()
        request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source),
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
        )
        result = core.evaluate_core_research(request)
        self.assertIs(result.disposition, core.CoreDisposition.RESEARCHABLE_CONVEXITY)
        self.assertEqual(result.reasons, ())
        self.assertEqual(result.geometry.ask_basis_per_underlying_unit, D("0.05"))
        self.assertEqual(
            tuple(point.terminal_underlying_price for point in result.geometry.hurdles),
            (D("100.05"), D("100.1"), D("100.25"), D("100.5")),
        )
        self.assertEqual(result.cash_ledger.observed_ask_cost, D("5"))
        self.assertEqual(result.cash_ledger.known_total, D("10"))
        self.assertEqual(result.cash_ledger.conditional_total_upper_bound, D("10"))
        self.assertEqual(result.budget_stress.single_cost_upper_bound, D("10"))
        self.assertEqual(result.budget_stress.repeated_cost_upper_bound, D("20"))
        self.assertEqual(result.budget_stress.single_loss_fraction, D("0.01"))
        self.assertEqual(result.budget_stress.repeated_loss_fraction, D("0.02"))
        self.assertEqual(result.geometry.hurdles[0].gross_value_multiple, 1)
        self.assertEqual(
            tuple(h.gross_value_multiple for h in result.geometry.hurdles),
            (1, 2, 5, 10),
        )

    def test_put_negative_downside_is_unavailable_not_negative(self):
        source = make_source()
        put = make_leg(
            core.CoreOptionType.PUT,
            leg_id="put-1",
            strike=D("10"),
            ask=D("3"),
            source=source,
        )
        request = make_request(
            source=source,
            structure=make_structure((put,), source),
            payoff=make_payoff(source),
            ledger=make_ledger(source, premium_bound=D("300")),
            risk=make_risk(source, maximum_single=D("1"), maximum_repeated=D("1")),
            sensitivity=make_sensitivity(source),
        )
        result = core.evaluate_core_research(request)
        self.assertEqual(result.disposition, core.CoreDisposition.RESEARCHABLE_CONVEXITY)
        self.assertEqual(
            tuple(h.terminal_underlying_price for h in result.geometry.hurdles),
            (D("7"), D("4"), None, None),
        )
        self.assertEqual(
            tuple(h.status for h in result.geometry.hurdles),
            (
                core.CoreHurdleStatus.AVAILABLE,
                core.CoreHurdleStatus.AVAILABLE,
                core.CoreHurdleStatus.UNAVAILABLE,
                core.CoreHurdleStatus.UNAVAILABLE,
            ),
        )

    def test_straddle_requires_identity_and_uses_aggregate_ask_basis(self):
        source = make_source()
        call = make_leg(source=source)
        put = make_leg(
            core.CoreOptionType.PUT,
            leg_id="put-1",
            source=source,
        )
        structure = make_structure((call, put), source)
        request = make_request(
            source=source,
            structure=structure,
            payoff=make_payoff(source),
            ledger=make_ledger(source, premium_bound=D("16")),
            risk=make_risk(source, maximum_single=D("0.03"), maximum_repeated=D("0.04")),
            sensitivity=make_sensitivity(source, legs=2),
        )
        result = core.evaluate_core_research(request)
        self.assertEqual(result.geometry.ask_basis_per_underlying_unit, D("0.1"))
        self.assertEqual(
            tuple((h.gross_value_multiple, h.side, h.terminal_underlying_price) for h in result.geometry.hurdles),
            (
                (1, core.CoreHurdleSide.DOWN, D("99.9")),
                (1, core.CoreHurdleSide.UP, D("100.1")),
                (2, core.CoreHurdleSide.DOWN, D("99.8")),
                (2, core.CoreHurdleSide.UP, D("100.2")),
                (5, core.CoreHurdleSide.DOWN, D("99.5")),
                (5, core.CoreHurdleSide.UP, D("100.5")),
                (10, core.CoreHurdleSide.DOWN, D("99.0")),
                (10, core.CoreHurdleSide.UP, D("101.0")),
            ),
        )
        with self.assertRaises(ValueError):
            make_structure(
                (
                    call,
                    make_leg(
                        core.CoreOptionType.PUT,
                        leg_id="put-2",
                        currency="HKD",
                        source=source,
                    ),
                ),
                source,
            )

    def test_missing_ask_retains_leg_and_partial_geometry_cash(self):
        source = make_source()
        leg = make_leg(ask=None, source=source)
        request = make_request(
            source=source,
            structure=make_structure((leg,), source),
            payoff=make_payoff(source),
            ledger=make_ledger(source),
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
        )
        result = core.evaluate_core_research(request)
        self.assertEqual(result.disposition, core.CoreDisposition.DATA_INSUFFICIENT_CORE)
        self.assertIn(core.CoreReasonCode.ASK_MISSING, result.reasons)
        self.assertIsNone(result.geometry.ask_basis_per_underlying_unit)
        self.assertEqual(len(result.geometry.hurdles), 4)
        self.assertTrue(all(h.status is core.CoreHurdleStatus.UNAVAILABLE for h in result.geometry.hurdles))
        self.assertIsNone(result.cash_ledger.observed_ask_cost)
        self.assertEqual(result.cash_ledger.known_total, D("10"))
        self.assertIsNotNone(result.request.structure.legs[0])

    def test_optional_ledger_is_real_missing_not_fake_required_components(self):
        source = make_source()
        request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=None,
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
        )
        result = core.evaluate_core_research(request)
        self.assertEqual(result.disposition, core.CoreDisposition.DATA_INSUFFICIENT_CORE)
        self.assertIn(core.CoreReasonCode.COST_LEDGER_MISSING, result.reasons)
        self.assertEqual(result.cash_ledger.missing_required_component_ids, ())
        self.assertEqual(result.cash_ledger.observed_ask_cost, D("5"))
        self.assertEqual(result.geometry.status, core.CoreGeometryStatus.AVAILABLE)

    def test_required_missing_and_unknown_components_are_dsc(self):
        source = make_source()
        missing = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source, components=(), required=("fee",)),
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
        )
        missing_result = core.evaluate_core_research(missing)
        self.assertEqual(missing_result.disposition, core.CoreDisposition.DATA_INSUFFICIENT_CORE)
        self.assertEqual(missing_result.cash_ledger.missing_required_component_ids, ("fee",))
        self.assertIn(core.CoreReasonCode.MISSING_REQUIRED_COMPONENT, missing_result.reasons)

        unknown_component = make_component(
            status=core.CoreCostComponentStatus.UNKNOWN,
            upper_bound=None,
            source=source,
        )
        unknown = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source, components=(unknown_component,)),
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
        )
        unknown_result = core.evaluate_core_research(unknown)
        self.assertEqual(unknown_result.disposition, core.CoreDisposition.DATA_INSUFFICIENT_CORE)
        self.assertEqual(unknown_result.cash_ledger.unknown_component_ids, ("fee",))
        self.assertIn(core.CoreReasonCode.UNKNOWN_REQUIRED_COMPONENT, unknown_result.reasons)
        self.assertIn(core.CoreReasonCode.UNKNOWN_COST_COMPONENT, unknown_result.reasons)

    def test_explicit_zero_component_with_basis_can_qualify(self):
        source = make_source()
        zero = core.CoreCostComponent(
            component_id="settlement",
            status=core.CoreCostComponentStatus.EXPLICIT_UPPER_BOUND,
            upper_bound=D("0"),
            currency="USD",
            methodology="caller attests no settlement charge for this case",
            description="explicit zero basis: settlement included in premium bound",
            provenance=make_provenance(source, "zero settlement basis"),
        )
        request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source, components=(zero,), required=("settlement",)),
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
        )
        result = core.evaluate_core_research(request)
        self.assertEqual(result.disposition, core.CoreDisposition.RESEARCHABLE_CONVEXITY)
        self.assertEqual(result.cash_ledger.conditional_total_upper_bound, D("8"))

    def test_premium_bound_is_explicit_position_bound_not_inferred_from_ask(self):
        source = make_source()
        too_low = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source, premium_bound=D("4")),
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
        )
        with self.assertRaises(ValueError):
            core.evaluate_core_research(too_low)

    def test_missing_policy_preserves_geometry_and_optional_enhancements_do_not_classify(self):
        source = make_source()
        enhancement = core.CoreReviewedEnhancements(
            enhancement_id="history-1",
            reviewed_artifact=None,
            description="optional historical context",
            provenance=make_provenance(source, "optional context basis"),
        )
        request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source),
            risk=None,
            sensitivity=None,
            enhancements=(enhancement,),
        )
        result = core.evaluate_core_research(request)
        self.assertEqual(result.disposition, core.CoreDisposition.DATA_INSUFFICIENT_CORE)
        self.assertEqual(result.geometry.status, core.CoreGeometryStatus.AVAILABLE)
        self.assertEqual(result.cash_ledger.conditional_total_upper_bound, D("10"))
        self.assertEqual(result.reviewed_enhancements, (enhancement,))
        self.assertIn(core.CoreReasonCode.RISK_POLICY_MISSING, result.reasons)
        self.assertIn(core.CoreReasonCode.SENSITIVITY_MISSING, result.reasons)
        self.assertNotIn(core.CoreReasonCode.STRUCTURE_UNSUPPORTED, result.reasons)

    def test_closed_typed_optional_artifact_is_retained_by_identity(self):
        source = make_source()
        artifact = make_volatility_result()
        enhancement = core.CoreReviewedEnhancements(
            enhancement_id="volatility-1",
            reviewed_artifact=artifact,
            description="optional volatility environment context",
            provenance=make_provenance(source, "optional artifact basis"),
        )
        request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source),
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
            enhancements=(enhancement,),
        )
        result = core.evaluate_core_research(request)
        self.assertEqual(result.disposition, core.CoreDisposition.RESEARCHABLE_CONVEXITY)
        self.assertIs(result.reviewed_enhancements[0].reviewed_artifact, artifact)
        self.assertIs(
            result.request.reviewed_enhancements[0].reviewed_artifact,
            artifact,
        )
        with self.assertRaises(TypeError):
            core.CoreReviewedEnhancements(
                enhancement_id="mutable",
                reviewed_artifact=[],
                description="invalid artifact",
                provenance=make_provenance(source),
            )

    def test_complete_conditional_budget_breach_rejects(self):
        source = make_source()
        request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source),
            risk=make_risk(source, maximum_single=D("0.005"), maximum_repeated=D("0.01")),
            sensitivity=make_sensitivity(source),
        )
        result = core.evaluate_core_research(request)
        self.assertEqual(result.disposition, core.CoreDisposition.REJECT)
        self.assertEqual(result.budget_stress.status, core.CoreBudgetStatus.CONDITIONAL_BREACH)
        self.assertEqual(
            result.reasons,
            (
                core.CoreReasonCode.SINGLE_LOSS_BUDGET_EXCEEDED,
                core.CoreReasonCode.REPEATED_LOSS_BUDGET_EXCEEDED,
            ),
        )

    def test_decimal_context_does_not_change_exact_outputs_and_no_mutation(self):
        source = make_source()
        request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source),
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
        )
        with decimal.localcontext() as context:
            context.prec = 2
            first = core.evaluate_core_research(request)
        with decimal.localcontext() as context:
            context.prec = 50
            second = core.evaluate_core_research(request)
        self.assertEqual(first.geometry, second.geometry)
        self.assertEqual(first.cash_ledger, second.cash_ledger)
        self.assertEqual(first.budget_stress, second.budget_stress)
        self.assertEqual(request.structure.legs[0].ask_per_underlying_unit, D("0.05"))

    def test_sensitivity_golden_and_no_payoff_model_branch(self):
        source = make_source()
        at_strike = core.CoreSensitivityPoint(
            point_id="s-at-strike",
            terminal_underlying_price=D("100"),
            ask_per_leg=(D("0.06"),),
            description="at-strike sensitivity point",
            provenance=make_provenance(source, "at-strike sensitivity basis"),
        )
        above_strike = core.CoreSensitivityPoint(
            point_id="s-above-strike",
            terminal_underlying_price=D("100.30"),
            ask_per_leg=(D("0.06"),),
            description="above-strike sensitivity point",
            provenance=make_provenance(source, "above-strike sensitivity basis"),
        )
        sensitivity = core.CoreSensitivity(
            points=(at_strike, above_strike),
            description="golden sensitivity points",
            provenance=make_provenance(source, "golden sensitivity collection basis"),
        )
        request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source),
            risk=make_risk(source),
            sensitivity=sensitivity,
        )
        result = core.evaluate_core_research(request)
        self.assertIsNotNone(result.sensitivity_results)
        points = result.sensitivity_results.points
        self.assertIs(points[0].point, at_strike)
        self.assertIs(points[1].point, above_strike)
        self.assertEqual(
            (
                points[0].conditional_gross_payoff_per_underlying_unit,
                points[0].conditional_position_payoff,
                points[0].declared_ask_basis_per_underlying_unit,
                points[0].gross_response_multiple,
            ),
            (D("0"), D("0"), D("0.06"), D("0")),
        )
        self.assertEqual(
            (
                points[1].conditional_gross_payoff_per_underlying_unit,
                points[1].conditional_position_payoff,
                points[1].declared_ask_basis_per_underlying_unit,
                points[1].gross_response_multiple,
            ),
            (D("0.30"), D("30"), D("0.06"), D("5")),
        )
        self.assertEqual(
            tuple(h.terminal_underlying_price for h in points[1].gross_hurdles),
            (D("100.06"), D("100.12"), D("100.30"), D("100.60")),
        )
        self.assertTrue(
            all(
                point.unavailable_reason is None
                for point in points
            )
        )

        no_model_request = make_request(
            source=source,
            payoff=None,
            ledger=make_ledger(source),
            risk=make_risk(source),
            sensitivity=sensitivity,
        )
        no_model_result = core.evaluate_core_research(no_model_request)
        self.assertEqual(
            no_model_result.disposition,
            core.CoreDisposition.DATA_INSUFFICIENT_CORE,
        )
        self.assertIn(core.CoreReasonCode.PAYOFF_MODEL_MISSING, no_model_result.reasons)
        self.assertIsNotNone(no_model_result.sensitivity_results)
        no_model_point = no_model_result.sensitivity_results.points[1]
        self.assertIs(no_model_point.point, above_strike)
        self.assertEqual(no_model_point.declared_ask_basis_per_underlying_unit, D("0.06"))
        self.assertIsNone(no_model_point.conditional_gross_payoff_per_underlying_unit)
        self.assertIsNone(no_model_point.conditional_position_payoff)
        self.assertIsNone(no_model_point.gross_response_multiple)
        self.assertEqual(no_model_point.unavailable_reason, "payoff_model_missing")
        self.assertTrue(
            all(h.status is core.CoreHurdleStatus.UNAVAILABLE for h in no_model_point.gross_hurdles)
        )
        self.assertTrue(
            all(h.terminal_underlying_price is None for h in no_model_point.gross_hurdles)
        )

    def test_decimal_context_rounding_and_inexact_trap_do_not_change_outputs(self):
        source = make_source()
        leg = make_leg(ask=D("0.01"), source=source)
        zero_component = make_component(upper_bound=D("0"), source=source)
        point = core.CoreSensitivityPoint(
            point_id="fractional-response",
            terminal_underlying_price=D("101"),
            ask_per_leg=(D("0.3"),),
            description="fractional sensitivity point",
            provenance=make_provenance(source, "fractional sensitivity basis"),
        )
        request = make_request(
            source=source,
            structure=make_structure((leg,), source),
            payoff=make_payoff(source),
            ledger=make_ledger(
                source,
                premium_bound=D("1"),
                components=(zero_component,),
                required=("fee",),
            ),
            risk=make_risk(
                source,
                portfolio_value=D("3"),
                maximum_single=D("0.34"),
                maximum_repeated=D("0.67"),
            ),
            sensitivity=core.CoreSensitivity(
                points=(point,),
                description="fractional sensitivity",
                provenance=make_provenance(source, "fractional sensitivity collection"),
            ),
        )
        with decimal.localcontext() as context:
            context.prec = 2
            context.rounding = decimal.ROUND_UP
            context.traps[decimal.Inexact] = True
            rounded_up = core.evaluate_core_research(request)
        with decimal.localcontext() as context:
            context.prec = 2
            context.rounding = decimal.ROUND_DOWN
            context.traps[decimal.Inexact] = True
            rounded_down = core.evaluate_core_research(request)
        self.assertEqual(rounded_up, rounded_down)
        self.assertEqual(
            rounded_up.budget_stress.status,
            core.CoreBudgetStatus.CONDITIONAL_PASS,
        )
        response = rounded_up.sensitivity_results.points[0].gross_response_multiple
        self.assertGreater(response, D("3"))
        self.assertLess(response, D("4"))

    def test_budget_uses_exact_fraction_comparison_near_decimal_boundaries(self):
        source = make_source()
        leg = make_leg(ask=D("0.01"), source=source)
        zero_component = make_component(upper_bound=D("0"), source=source)
        common = dict(
            source=source,
            structure=make_structure((leg,), source),
            payoff=make_payoff(source),
            ledger=make_ledger(
                source,
                premium_bound=D("1"),
                components=(zero_component,),
                required=("fee",),
            ),
            sensitivity=make_sensitivity(source),
        )
        pass_request = make_request(
            **common,
            risk=make_risk(
                source,
                portfolio_value=D("3"),
                maximum_single=D("0.3333333333333333333333333334"),
                maximum_repeated=D("0.6666666666666666666666666667"),
            ),
        )
        pass_result = core.evaluate_core_research(pass_request)
        self.assertEqual(pass_result.disposition, core.CoreDisposition.RESEARCHABLE_CONVEXITY)
        breach_request = make_request(
            **common,
            risk=make_risk(
                source,
                portfolio_value=D("3"),
                maximum_single=D("0.3333333333333333333333333334"),
                maximum_repeated=D("0.6666666666666666666666666666"),
            ),
        )
        breach_result = core.evaluate_core_research(breach_request)
        self.assertEqual(breach_result.disposition, core.CoreDisposition.REJECT)
        self.assertEqual(
            breach_result.reasons,
            (core.CoreReasonCode.REPEATED_LOSS_BUDGET_EXCEEDED,),
        )

    def test_empty_cost_ledger_must_declare_a_strategy(self):
        source = make_source()
        with self.assertRaises(ValueError):
            make_ledger(source, components=(), required=())
        with self.assertRaises(ValueError):
            make_ledger(
                source,
                components=(make_component(source=source),),
                required=(),
            )

    def test_currency_mismatches_are_rejected_at_ledger_and_request_boundaries(self):
        source = make_source()
        with self.assertRaises(ValueError):
            make_ledger(
                source,
                components=(make_component(source=source, currency="HKD"),),
            )

        hkd_ledger = make_ledger(
            source,
            currency="HKD",
            components=(make_component(source=source, currency="HKD"),),
        )
        ledger_mismatch_request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=hkd_ledger,
            risk=make_risk(source),
            sensitivity=make_sensitivity(source),
        )
        with self.assertRaises(ValueError):
            core.evaluate_core_research(ledger_mismatch_request)

        risk_mismatch_request = make_request(
            source=source,
            payoff=make_payoff(source),
            ledger=make_ledger(source),
            risk=make_risk(source, currency="HKD"),
            sensitivity=make_sensitivity(source),
        )
        with self.assertRaises(ValueError):
            core.evaluate_core_research(risk_mismatch_request)


if __name__ == "__main__":
    unittest.main()
