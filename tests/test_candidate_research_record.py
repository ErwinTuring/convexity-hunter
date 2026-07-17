"""Tests for the complete candidate-research aggregate record."""

import datetime
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from convexity_hunter.evidence import (
    CandidateState,
    ClassifiedEvidence,
    EvidenceImpact,
    EvidenceKind,
    OptionLeg,
    OptionStructure,
    Scenario,
    StructureCosts,
    TailPricingSlice,
    TermVolatilityPoint,
    VolatilityEnvironment,
)
from convexity_hunter.report import (
    CandidateResearchRecord,
    LegVolatilityInput,
    ScenarioResult,
    StructureLiquidity,
)


AS_OF_DATE = datetime.date(2030, 1, 1)
EXPIRATION = datetime.date(2030, 1, 31)


def make_structure(straddle: bool = False, **overrides: object) -> OptionStructure:
    legs = [OptionLeg("SPY", "call", 500.0, EXPIRATION)]
    if straddle:
        legs.append(OptionLeg("SPY", "put", 500.0, EXPIRATION))
    values = {
        "legs": tuple(legs),
        "assumed_portfolio_value": 100_000.0,
        "expected_holding_days": 10,
    }
    values.update(overrides)
    return OptionStructure(**values)  # type: ignore[arg-type]


def make_environment(**overrides: object) -> VolatilityEnvironment:
    values = {
        "underlying": "SPY",
        "as_of_date": AS_OF_DATE,
        "reference_tenor_days": 30,
        "iv_percentile": 0.35,
        "iv_history_lookback_observations": 252,
        "historical_median_atm_iv": 0.22,
        "matched_realized_volatility": 0.18,
        "matched_realized_window_days": 30,
        "term_structure": (
            TermVolatilityPoint(30, 0.20),
            TermVolatilityPoint(60, 0.24),
        ),
    }
    values.update(overrides)
    return VolatilityEnvironment(**values)  # type: ignore[arg-type]


def make_tail_slice(**overrides: object) -> TailPricingSlice:
    values = {
        "underlying": "SPY",
        "as_of_date": AS_OF_DATE,
        "expiration": EXPIRATION,
        "atm_iv": 0.20,
        "put_25_delta_iv": 0.25,
        "call_25_delta_iv": 0.21,
        "put_10_delta_iv": 0.35,
        "call_10_delta_iv": 0.24,
        "skew_percentile": 0.60,
        "skew_history_lookback_observations": 252,
        "delta_methodology": "spot delta; linear IV interpolation",
    }
    values.update(overrides)
    return TailPricingSlice(**values)  # type: ignore[arg-type]


def make_costs(structure: OptionStructure, **overrides: object) -> StructureCosts:
    values = {
        "structure": structure,
        "as_of_date": AS_OF_DATE,
        "quoted_mid_premium": 1_000.0,
        "estimated_spread_cost": 20.0,
        "commissions_and_fees": 5.0,
        "theta_per_day": -10.0,
        "gamma": 0.40,
        "underlying_price": 500.0,
        "greeks_methodology": "provider Greeks; total-position scaling",
    }
    values.update(overrides)
    return StructureCosts(**values)  # type: ignore[arg-type]


def make_liquidity(
    structure: OptionStructure, **overrides: object
) -> StructureLiquidity:
    values = {
        "structure": structure,
        "as_of_date": AS_OF_DATE,
        "quoted_bid_value": 900.0,
        "quoted_ask_value": 1_100.0,
        "minimum_leg_open_interest": 500,
        "minimum_leg_daily_volume": 100,
        "quote_methodology": "provider close snapshot; aggregated leg quotes",
    }
    values.update(overrides)
    return StructureLiquidity(**values)  # type: ignore[arg-type]


def make_scenario_result(
    structure: OptionStructure, **overrides: object
) -> ScenarioResult:
    values = {
        "structure": structure,
        "as_of_date": AS_OF_DATE,
        "scenario": Scenario(0.10, 0.20, "immediate"),
        "valuation_date": AS_OF_DATE,
        "base_underlying_price": 500.0,
        "leg_volatility_inputs": tuple(
            LegVolatilityInput(leg, 0.20) for leg in structure.legs
        ),
        "estimated_position_value": 1_500.0,
        "entry_cost_basis": 1_025.0,
        "estimated_exit_cost": 20.0,
        "pricing_methodology": "provider model; stated rates and dividends",
    }
    values.update(overrides)
    return ScenarioResult(**values)  # type: ignore[arg-type]


def make_evidence(
    evidence_id: str = "obs-1",
    kind: EvidenceKind = EvidenceKind.OBSERVED_FACT,
    impact: EvidenceImpact = EvidenceImpact.SUPPORTS,
) -> ClassifiedEvidence:
    if kind is EvidenceKind.CALCULATED_METRIC:
        return ClassifiedEvidence(
            evidence_id,
            kind,
            impact,
            "A reproducible metric was calculated.",
            source="provider history",
            methodology="matched observation windows",
        )
    return ClassifiedEvidence(
        evidence_id,
        kind,
        impact,
        "A classified research statement.",
        source="provider snapshot" if kind is EvidenceKind.OBSERVED_FACT else None,
    )


def make_record(**overrides: object) -> CandidateResearchRecord:
    structure = overrides.get("structure", make_structure())
    values = {
        "candidate_id": "candidate-1",
        "state": CandidateState.WATCH,
        "state_rationale": "Evidence is coherent but incomplete.",
        "as_of_date": AS_OF_DATE,
        "hypothesis": "The structure may offer underpriced convexity.",
        "structure": structure,
        "evidence": (make_evidence(),),
        "falsification_conditions": ("Implied volatility reprices sharply higher.",),
        "false_positive_reasons": ("The quiet regime may persist.",),
        "human_review_questions": ("Are the execution assumptions realistic?",),
    }
    values.update(overrides)
    return CandidateResearchRecord(**values)  # type: ignore[arg-type]


def make_investigate_record(**overrides: object) -> CandidateResearchRecord:
    structure = overrides.get("structure", make_structure())
    costs = make_costs(structure)  # type: ignore[arg-type]
    values = {
        "state": CandidateState.INVESTIGATE,
        "state_rationale": "All three evidence layers are present.",
        "structure": structure,
        "volatility_environment": make_environment(),
        "tail_pricing_slices": (make_tail_slice(),),
        "costs": costs,
        "liquidity": make_liquidity(structure),  # type: ignore[arg-type]
        "scenario_results": (make_scenario_result(structure),),  # type: ignore[arg-type]
    }
    values.update(overrides)
    return make_record(**values)


class CandidateResearchRecordValidTests(unittest.TestCase):
    def test_valid_watch_with_partial_data(self) -> None:
        record = make_record(missing_data=("Tail history is unavailable.",))
        self.assertIs(record.state, CandidateState.WATCH)

    def test_valid_reject_with_partial_data(self) -> None:
        record = make_record(state=CandidateState.REJECT)
        self.assertIs(record.state, CandidateState.REJECT)

    def test_valid_data_insufficient(self) -> None:
        record = make_record(
            state=CandidateState.DATA_INSUFFICIENT,
            missing_data=("Reliable quotes are unavailable.",),
        )
        self.assertEqual(len(record.missing_data), 1)

    def test_valid_fully_populated_investigate(self) -> None:
        record = make_investigate_record()
        self.assertIs(record.state, CandidateState.INVESTIGATE)

    def test_valid_long_call(self) -> None:
        self.assertEqual(make_record().structure.structure_type, "long_call")

    def test_valid_long_straddle(self) -> None:
        structure = make_structure(straddle=True)
        record = make_investigate_record(
            structure=structure,
            costs=make_costs(structure),
            liquidity=make_liquidity(structure),
            scenario_results=(make_scenario_result(structure),),
        )
        self.assertEqual(record.structure.structure_type, "long_straddle")

    def test_immutability(self) -> None:
        record = make_record()
        with self.assertRaises(FrozenInstanceError):
            record.state = CandidateState.REJECT


class CandidateResearchRecordNormalizationTests(unittest.TestCase):
    def test_required_and_optional_strings_are_normalized(self) -> None:
        record = make_record(
            candidate_id="  candidate-1  ",
            state_rationale="  partial evidence  ",
            hypothesis="  testable hypothesis  ",
            ai_interpretation="  cautious interpretation  ",
        )
        self.assertEqual(record.candidate_id, "candidate-1")
        self.assertEqual(record.state_rationale, "partial evidence")
        self.assertEqual(record.hypothesis, "testable hypothesis")
        self.assertEqual(record.ai_interpretation, "cautious interpretation")

    def test_list_collections_are_normalized_and_isolated(self) -> None:
        tails = []
        scenarios = []
        evidence = [make_evidence()]
        falsification = ["  Condition  "]
        missing = ["  Missing item  "]
        false_positives = ["  False positive  "]
        questions = ["  Review question?  "]
        record = make_record(
            tail_pricing_slices=tails,
            scenario_results=scenarios,
            evidence=evidence,
            falsification_conditions=falsification,
            missing_data=missing,
            false_positive_reasons=false_positives,
            human_review_questions=questions,
        )
        for value in (
            record.tail_pricing_slices,
            record.scenario_results,
            record.evidence,
            record.falsification_conditions,
            record.missing_data,
            record.false_positive_reasons,
            record.human_review_questions,
        ):
            self.assertIsInstance(value, tuple)
        tails.append(make_tail_slice())
        scenarios.append(make_scenario_result(record.structure))
        evidence.append(make_evidence("obs-2"))
        falsification.append("Another condition")
        missing.append("Another gap")
        false_positives.append("Another risk")
        questions.append("Another question?")
        self.assertEqual(record.tail_pricing_slices, ())
        self.assertEqual(record.scenario_results, ())
        self.assertEqual(len(record.evidence), 1)
        self.assertEqual(record.falsification_conditions, ("Condition",))
        self.assertEqual(record.missing_data, ("Missing item",))
        self.assertEqual(record.false_positive_reasons, ("False positive",))
        self.assertEqual(record.human_review_questions, ("Review question?",))

    def test_tail_slices_sorted_and_scenarios_preserve_order(self) -> None:
        later = make_tail_slice(expiration=datetime.date(2030, 2, 28))
        exact = make_tail_slice()
        first = make_scenario_result(make_structure())
        second = make_scenario_result(
            first.structure,
            scenario=Scenario(-0.10, -0.20, "immediate"),
        )
        record = make_record(
            structure=first.structure,
            tail_pricing_slices=[later, exact],
            scenario_results=[first, second],
        )
        self.assertEqual(record.tail_pricing_slices, (exact, later))
        self.assertEqual(record.scenario_results, (first, second))

    def test_invalid_required_and_optional_strings_rejected(self) -> None:
        for field in ("candidate_id", "state_rationale", "hypothesis"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                make_record(**{field: 1})
            with self.subTest(field=field), self.assertRaises(ValueError):
                make_record(**{field: "  "})
        with self.assertRaises(TypeError):
            make_record(ai_interpretation=1)
        with self.assertRaises(ValueError):
            make_record(ai_interpretation="  ")

    def test_invalid_primary_types_and_date_rejected(self) -> None:
        for field, value in (
            ("state", "watch"),
            ("as_of_date", datetime.datetime(2030, 1, 1, 12, 0)),
            ("structure", "SPY"),
            ("volatility_environment", "volatility"),
            ("costs", "costs"),
            ("liquidity", "liquidity"),
        ):
            with self.subTest(field=field), self.assertRaises(TypeError):
                make_record(**{field: value})

    def test_as_of_date_must_precede_expiration(self) -> None:
        with self.assertRaises(ValueError):
            make_record(as_of_date=EXPIRATION)


class CandidateResearchRecordContentTests(unittest.TestCase):
    def test_required_research_collections_cannot_be_empty(self) -> None:
        for field in (
            "evidence",
            "falsification_conditions",
            "false_positive_reasons",
            "human_review_questions",
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                make_record(**{field: ()})

    def test_duplicate_evidence_ids_rejected(self) -> None:
        with self.assertRaises(ValueError):
            make_record(evidence=(make_evidence(), make_evidence()))

    def test_duplicate_normalized_text_entries_rejected(self) -> None:
        for field in (
            "falsification_conditions",
            "missing_data",
            "false_positive_reasons",
            "human_review_questions",
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                make_record(**{field: ("Duplicate", "  Duplicate  ")})

    def test_invalid_text_item_types_rejected(self) -> None:
        for field in (
            "falsification_conditions",
            "missing_data",
            "false_positive_reasons",
            "human_review_questions",
        ):
            with self.subTest(field=field), self.assertRaises(TypeError):
                make_record(**{field: (1,)})

    def test_invalid_typed_collection_items_rejected(self) -> None:
        for field in ("tail_pricing_slices", "scenario_results", "evidence"):
            with self.subTest(field=field), self.assertRaises(TypeError):
                make_record(**{field: ("invalid",)})

    def test_unsupported_collection_containers_rejected(self) -> None:
        for field in (
            "tail_pricing_slices",
            "scenario_results",
            "evidence",
            "falsification_conditions",
            "missing_data",
            "false_positive_reasons",
            "human_review_questions",
        ):
            for value in (None, "text", b"text", {"item"}):
                with self.subTest(field=field, value=value), self.assertRaises(TypeError):
                    make_record(**{field: value})


class CandidateResearchRecordConsistencyTests(unittest.TestCase):
    def test_volatility_consistency(self) -> None:
        with self.assertRaises(ValueError):
            make_record(volatility_environment=make_environment(underlying="QQQ"))
        with self.assertRaises(ValueError):
            make_record(
                volatility_environment=make_environment(
                    as_of_date=AS_OF_DATE + datetime.timedelta(days=1)
                )
            )

    def test_tail_consistency(self) -> None:
        with self.assertRaises(ValueError):
            make_record(tail_pricing_slices=(make_tail_slice(underlying="QQQ"),))
        with self.assertRaises(ValueError):
            make_record(
                tail_pricing_slices=(
                    make_tail_slice(as_of_date=AS_OF_DATE + datetime.timedelta(days=1)),
                )
            )
        with self.assertRaises(ValueError):
            make_record(tail_pricing_slices=(make_tail_slice(), make_tail_slice()))
        with self.assertRaises(ValueError):
            make_record(
                tail_pricing_slices=(
                    make_tail_slice(expiration=datetime.date(2030, 2, 28)),
                )
            )
        record = make_record(
            tail_pricing_slices=(
                make_tail_slice(),
                make_tail_slice(expiration=datetime.date(2030, 2, 28)),
            )
        )
        self.assertEqual(len(record.tail_pricing_slices), 2)

    def test_cost_consistency(self) -> None:
        structure = make_structure()
        other = make_structure(expected_holding_days=5)
        with self.assertRaises(ValueError):
            make_record(structure=structure, costs=make_costs(other))
        with self.assertRaises(ValueError):
            make_record(
                structure=structure,
                costs=make_costs(
                    structure, as_of_date=AS_OF_DATE + datetime.timedelta(days=1)
                ),
            )

    def test_liquidity_consistency(self) -> None:
        structure = make_structure()
        other = make_structure(expected_holding_days=5)
        with self.assertRaises(ValueError):
            make_record(structure=structure, liquidity=make_liquidity(other))
        with self.assertRaises(ValueError):
            make_record(
                structure=structure,
                liquidity=make_liquidity(
                    structure, as_of_date=AS_OF_DATE + datetime.timedelta(days=1)
                ),
            )

    def test_cost_and_liquidity_midpoint_consistency(self) -> None:
        structure = make_structure()
        costs = make_costs(structure)
        make_record(
            structure=structure,
            costs=costs,
            liquidity=make_liquidity(structure),
        )
        with self.assertRaises(ValueError):
            make_record(
                structure=structure,
                costs=costs,
                liquidity=make_liquidity(structure, quoted_ask_value=1_102.0),
            )
        record = make_record(
            structure=structure,
            costs=costs,
            liquidity=make_liquidity(
                structure, quoted_ask_value=1_100.000000001
            ),
        )
        self.assertIsNotNone(record.liquidity)

    def test_scenario_structure_and_date_consistency(self) -> None:
        structure = make_structure()
        other = make_structure(expected_holding_days=5)
        with self.assertRaises(ValueError):
            make_record(
                structure=structure,
                scenario_results=(make_scenario_result(other),),
            )
        with self.assertRaises(ValueError):
            make_record(
                structure=structure,
                scenario_results=(
                    make_scenario_result(
                        structure,
                        as_of_date=AS_OF_DATE + datetime.timedelta(days=1),
                        valuation_date=AS_OF_DATE + datetime.timedelta(days=1),
                    ),
                ),
            )

    def test_duplicate_scenario_definitions_rejected(self) -> None:
        structure = make_structure()
        first = make_scenario_result(structure)
        second = make_scenario_result(structure, estimated_position_value=2_000.0)
        with self.assertRaises(ValueError):
            make_record(structure=structure, scenario_results=(first, second))

    def test_scenario_cost_and_underlying_basis_consistency(self) -> None:
        structure = make_structure()
        costs = make_costs(structure)
        result = make_scenario_result(structure)
        make_record(
            structure=structure, costs=costs, scenario_results=(result,)
        )
        with self.assertRaises(ValueError):
            make_record(
                structure=structure,
                costs=costs,
                scenario_results=(
                    make_scenario_result(structure, entry_cost_basis=1_026.0),
                ),
            )
        with self.assertRaises(ValueError):
            make_record(
                structure=structure,
                costs=costs,
                scenario_results=(
                    make_scenario_result(structure, base_underlying_price=501.0),
                ),
            )

    def test_scenario_float_tolerance_and_absent_cost_behavior(self) -> None:
        structure = make_structure()
        costs = make_costs(structure)
        tolerant = make_scenario_result(
            structure,
            entry_cost_basis=1_025.0000000005,
            base_underlying_price=500.0000000005,
        )
        make_record(
            structure=structure, costs=costs, scenario_results=(tolerant,)
        )
        record = make_record(
            structure=structure,
            scenario_results=(
                make_scenario_result(
                    structure,
                    entry_cost_basis=2_000.0,
                    base_underlying_price=600.0,
                ),
            ),
        )
        self.assertIsNone(record.costs)


class CandidateResearchRecordStateTests(unittest.TestCase):
    def test_data_insufficient_requires_missing_data(self) -> None:
        make_record(
            state=CandidateState.DATA_INSUFFICIENT,
            missing_data=("History unavailable.",),
        )
        with self.assertRaises(ValueError):
            make_record(state=CandidateState.DATA_INSUFFICIENT)

    def test_investigate_requires_each_evidence_layer(self) -> None:
        complete = make_investigate_record()
        cases = (
            {"volatility_environment": None},
            {"tail_pricing_slices": ()},
            {"costs": None},
            {"liquidity": None},
            {"scenario_results": ()},
            {
                "evidence": (
                    make_evidence("weak-1", impact=EvidenceImpact.WEAKENS),
                )
            },
        )
        for changes in cases:
            values = {
                "state": complete.state,
                "state_rationale": complete.state_rationale,
                "structure": complete.structure,
                "volatility_environment": complete.volatility_environment,
                "tail_pricing_slices": complete.tail_pricing_slices,
                "costs": complete.costs,
                "liquidity": complete.liquidity,
                "scenario_results": complete.scenario_results,
            }
            values.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                make_record(**values)

    def test_investigate_accepts_supporting_observed_fact(self) -> None:
        record = make_investigate_record(
            evidence=(
                make_evidence(
                    "observed-support",
                    EvidenceKind.OBSERVED_FACT,
                    EvidenceImpact.SUPPORTS,
                ),
            )
        )
        self.assertIs(record.state, CandidateState.INVESTIGATE)

    def test_investigate_accepts_supporting_calculated_metric(self) -> None:
        record = make_investigate_record(
            evidence=(
                make_evidence(
                    "calculated-support",
                    EvidenceKind.CALCULATED_METRIC,
                    EvidenceImpact.SUPPORTS,
                ),
            )
        )
        self.assertIs(record.state, CandidateState.INVESTIGATE)

    def test_investigate_rejects_only_supporting_assumption(self) -> None:
        with self.assertRaises(ValueError):
            make_investigate_record(
                evidence=(
                    make_evidence(
                        "assumption-support",
                        EvidenceKind.ASSUMPTION,
                        EvidenceImpact.SUPPORTS,
                    ),
                )
            )

    def test_investigate_rejects_only_supporting_ai_interpretation(self) -> None:
        with self.assertRaises(ValueError):
            make_investigate_record(
                evidence=(
                    make_evidence(
                        "ai-support",
                        EvidenceKind.AI_INTERPRETATION,
                        EvidenceImpact.SUPPORTS,
                    ),
                )
            )

    def test_neutral_observation_and_supporting_ai_do_not_satisfy_investigate(self) -> None:
        with self.assertRaises(ValueError):
            make_investigate_record(
                evidence=(
                    make_evidence(
                        "observed-neutral",
                        EvidenceKind.OBSERVED_FACT,
                        EvidenceImpact.NEUTRAL,
                    ),
                    make_evidence(
                        "ai-support",
                        EvidenceKind.AI_INTERPRETATION,
                        EvidenceImpact.SUPPORTS,
                    ),
                )
            )

    def test_weakening_empirical_and_supporting_assumption_do_not_satisfy_investigate(self) -> None:
        with self.assertRaises(ValueError):
            make_investigate_record(
                evidence=(
                    make_evidence(
                        "observed-weakening",
                        EvidenceKind.OBSERVED_FACT,
                        EvidenceImpact.WEAKENS,
                    ),
                    make_evidence(
                        "assumption-support",
                        EvidenceKind.ASSUMPTION,
                        EvidenceImpact.SUPPORTS,
                    ),
                )
            )

    def test_watch_may_have_missing_data(self) -> None:
        record = make_record(missing_data=("One history is missing.",))
        self.assertEqual(len(record.missing_data), 1)

    def test_watch_may_contain_only_assumptions(self) -> None:
        record = make_record(
            evidence=(
                make_evidence(
                    "assumption",
                    EvidenceKind.ASSUMPTION,
                    EvidenceImpact.SUPPORTS,
                ),
            )
        )
        self.assertIs(record.state, CandidateState.WATCH)

    def test_reject_may_use_partial_records(self) -> None:
        record = make_record(state=CandidateState.REJECT)
        self.assertIsNone(record.costs)

    def test_reject_may_contain_only_ai_interpretations(self) -> None:
        record = make_record(
            state=CandidateState.REJECT,
            evidence=(
                make_evidence(
                    "ai-interpretation",
                    EvidenceKind.AI_INTERPRETATION,
                    EvidenceImpact.SUPPORTS,
                ),
            ),
        )
        self.assertIs(record.state, CandidateState.REJECT)


class CandidateResearchRecordPropertyTests(unittest.TestCase):
    def test_expiration(self) -> None:
        self.assertEqual(make_record().expiration, EXPIRATION)

    def test_evidence_views_by_impact_and_kind(self) -> None:
        observed = make_evidence(
            "observed", EvidenceKind.OBSERVED_FACT, EvidenceImpact.SUPPORTS
        )
        calculated = make_evidence(
            "calculated", EvidenceKind.CALCULATED_METRIC, EvidenceImpact.WEAKENS
        )
        assumption = make_evidence(
            "assumption", EvidenceKind.ASSUMPTION, EvidenceImpact.NEUTRAL
        )
        interpretation = make_evidence(
            "interpretation",
            EvidenceKind.AI_INTERPRETATION,
            EvidenceImpact.SUPPORTS,
        )
        record = make_record(
            evidence=(observed, calculated, assumption, interpretation)
        )
        self.assertEqual(record.supporting_evidence, (observed, interpretation))
        self.assertEqual(record.weakening_evidence, (calculated,))
        self.assertEqual(record.neutral_evidence, (assumption,))
        self.assertEqual(record.observed_facts, (observed,))
        self.assertEqual(record.calculated_metrics, (calculated,))
        self.assertEqual(record.assumptions, (assumption,))
        self.assertEqual(record.ai_interpretation_evidence, (interpretation,))


if __name__ == "__main__":
    unittest.main()
