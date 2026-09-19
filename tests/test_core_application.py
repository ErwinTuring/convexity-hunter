"""Focused fake integration tests for the Core MVP application boundary."""

import datetime
import decimal
import pathlib
import sys
import unittest
from dataclasses import replace
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter import core_research
from convexity_hunter.core_application import (
    CoreOperationalBounds,
    CoreResearchPolicy,
    SourceSubmissionBatch,
    run_direct_core,
    run_event_core,
    run_world_core,
)
from convexity_hunter.core_futu import (
    FutuMarketBridge,
    FutuNativeDirectAskEvidence,
    FutuNativeDirectAskReceipt,
    NativeQuoteAuthority,
    retrieve_futu_native_direct_ask_evidence,
)
from convexity_hunter.core_presentation import report
from convexity_hunter.event_entry import UserEventInput
from convexity_hunter.event_intelligence import (
    DistributionChangeMode,
    EventIntelligenceSubmission,
    EventSourceReference,
    EventStatement,
    EventStatementKind,
    EventUnderlyingHypothesis,
    HypothesisReassessment,
    MethodologizedDateRange,
    ReassessmentBasisKind,
    assess_event_intelligence_submission,
)
from convexity_hunter.market_data import UnderlyingKey, UnderlyingSecurityType
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority
from convexity_hunter.providers import futu


UTC = datetime.timezone.utc
EVALUATION_DATE = datetime.date(2030, 1, 1)
RETRIEVED_AT = datetime.datetime(2030, 1, 2, 12, 0, tzinfo=UTC)
UNDERLYING = UnderlyingKey("ABC", "XNAS", UnderlyingSecurityType.EQUITY, "USD")


class FakeTable:
    def __init__(self, rows):
        self.rows = rows

    def to_dict(self, *, orient):
        if orient != "records":
            raise AssertionError(orient)
        return list(self.rows)


def identifier(expiration, option_type, strike):
    marker = "C" if option_type == "CALL" else "P"
    encoded_strike = int(decimal.Decimal(str(strike)) * 1000)
    return f"US.ABC{expiration:%y%m%d}{marker}{encoded_strike}"


def make_row(expiration, option_type, strike, *, lot_size=100):
    return futu.FutuOptionChainContractEvidence(
        provider_identifier=identifier(expiration, option_type, strike),
        provider_underlying="US.ABC",
        expiration=expiration,
        option_type=option_type,
        strike=decimal.Decimal(str(strike)),
        lot_size=lot_size,
        provider_expiration_cycle="MONTH",
        provider_standard_type="STANDARD",
        suspension=False,
        statuses=(futu.FutuOptionChainRowStatus.ELIGIBLE,),
        retrieved_at=RETRIEVED_AT,
    )


class ExactContext:
    def __init__(self, row):
        self.row = row

    def get_option_expiration_date(self, code):
        return 0, FakeTable(
            [
                {
                    "strike_time": self.row.expiration.isoformat(),
                    "expiration_cycle": "MONTH",
                }
            ]
        )

    def get_option_chain(self, code, *, start, end, option_type):
        return 0, FakeTable(
            [
                {
                    "code": self.row.provider_identifier,
                    "lot_size": self.row.lot_size,
                    "option_type": self.row.option_type.upper(),
                    "stock_owner": self.row.provider_underlying,
                    "strike_time": self.row.expiration.isoformat(),
                    "strike_price": self.row.strike,
                    "suspension": False,
                    "expiration_cycle": "MONTH",
                    "option_standard_type": "STANDARD",
                }
            ]
        )

    def get_market_snapshot(self, identifiers):
        return 0, FakeTable(
            [
                {
                    "code": self.row.provider_identifier,
                    "stock_owner": self.row.provider_underlying,
                    "option_type": self.row.option_type.upper(),
                    "strike_time": self.row.expiration.isoformat(),
                    "option_strike_price": self.row.strike,
                    "option_contract_size": self.row.lot_size,
                    "option_area_type": "American",
                    "option_valid": True,
                }
            ]
        )


def make_verification(row):
    with mock.patch.object(futu, "_utc_now", return_value=RETRIEVED_AT):
        return futu.verify_futu_monthly_option_contract(
            ExactContext(row),
            underlying_key=UNDERLYING,
            expiration=row.expiration,
            option_type=row.option_type,
            strike=row.strike,
        )


def forge_verification_identifier(verification, provider_identifier):
    forged = object.__new__(type(verification))
    for name, value in vars(verification).items():
        object.__setattr__(forged, name, value)
    object.__setattr__(forged, "provider_identifier", provider_identifier)
    return forged


def make_browser(request, rows):
    rows = tuple(
        sorted(rows, key=lambda row: (row.expiration, row.strike, row.option_type))
    )
    expirations = []
    for expiration in sorted({row.expiration for row in rows}):
        expirations.append(
            futu.FutuOptionChainExpirationEvidence(
                expiration=expiration,
                provider_expiration_cycle="MONTH",
                expiration_retrieved_at=RETRIEVED_AT,
                chain_retrieved_at=RETRIEVED_AT,
            )
        )
    evidence = futu.FutuOptionChainDiscoveryEvidence(
        discovery_request=request,
        provider_underlying="US.ABC",
        expirations=tuple(expirations),
        contracts=rows,
    )
    return futu.create_futu_exact_contract_browser(evidence)


def make_quote_batch(browser, asks):
    chunks = []
    for chunk_index, expiration in enumerate(
        dict.fromkeys(row.expiration for row in browser.rows)
    ):
        requested_rows = tuple(row for row in browser.rows if row.expiration == expiration)
        quotes = []
        for row in requested_rows:
            ask = asks.get(row.provider_identifier)
            if ask is None:
                quotes.append(
                    futu.FutuBrowserQuoteEvidence(
                        browser_row=row,
                        chunk_index=chunk_index,
                        availability=futu.FutuBrowserQuoteAvailability.UNAVAILABLE,
                        bid_price=None,
                        ask_price=None,
                        bid_size=None,
                        ask_size=None,
                        received_at=RETRIEVED_AT,
                        provider_bid_timestamp_value=None,
                        provider_ask_timestamp_value=None,
                        reason_codes=(futu.FutuBrowserQuoteReasonCode.ASK_ABSENT,),
                    )
                )
            else:
                quotes.append(
                    futu.FutuBrowserQuoteEvidence(
                        browser_row=row,
                        chunk_index=chunk_index,
                        availability=futu.FutuBrowserQuoteAvailability.ASK_SIDE_AVAILABLE,
                        bid_price=None,
                        ask_price=ask,
                        bid_size=None,
                        ask_size=1,
                        received_at=RETRIEVED_AT,
                        provider_bid_timestamp_value=None,
                        provider_ask_timestamp_value=None,
                        reason_codes=(futu.FutuBrowserQuoteReasonCode.BID_ABSENT,),
                    )
                )
        chunks.append(
            futu.FutuBrowserQuoteChunkEvidence(
                chunk_index=chunk_index,
                expiration=expiration,
                requested_rows=requested_rows,
                quotes=tuple(quotes),
                started_at=RETRIEVED_AT,
                completed_at=RETRIEVED_AT,
            )
        )
    return futu.FutuBrowserQuoteBatchEvidence(browser=browser, chunks=tuple(chunks))


def make_hypothesis(hypothesis_id, mode=DistributionChangeMode.BIDIRECTIONAL_EXPANSION):
    source_id = f"source-{hypothesis_id}"
    fact_id = f"fact-{hypothesis_id}"
    interpretation_id = f"interpretation-{hypothesis_id}"
    reassessment_date = datetime.date(2030, 1, 10)
    reassessment = HypothesisReassessment(
        reassessment_by=reassessment_date,
        methodology=(
            "caller-research-policy-assumption:"
            f"{reassessment_date.isoformat()}:focused integration test"
        ),
        basis_kind=ReassessmentBasisKind.CALLER_RESEARCH_POLICY_ASSUMPTION,
        basis_statement_ids=(interpretation_id,),
    )
    return (
        EventSourceReference(
            source_id,
            f"https://example.test/{source_id}",
            "Focused source",
            datetime.datetime(2029, 12, 31, tzinfo=UTC),
        ),
        EventStatement(
            fact_id,
            EventStatementKind.OBSERVED_FACT,
            "The source records the event.",
            (source_id,),
        ),
        EventStatement(
            interpretation_id,
            EventStatementKind.INTERPRETATION,
            "The event may widen the return distribution.",
            (),
            (fact_id,),
        ),
        EventUnderlyingHypothesis(
            hypothesis_id=hypothesis_id,
            underlying_key=UNDERLYING,
            impact_path="A specific commercial outcome changes.",
            distribution_mode=mode,
            distribution_hypothesis="The future return distribution may widen.",
            expected_window=None,
            reassessment=reassessment,
            supporting_statement_ids=(interpretation_id,),
            contradicting_statement_ids=(),
            contradiction_review="Contradictory evidence was reviewed.",
            uncertainties=("The timing may change.",),
            falsification_conditions=("The event is cancelled.",),
        ),
    )


def make_submission(submission_id="submission-1", hypothesis_ids=("hypothesis-1",), mode=DistributionChangeMode.BIDIRECTIONAL_EXPANSION):
    built = [make_hypothesis(item, mode) for item in hypothesis_ids]
    source = built[0][0]
    facts = tuple(item[1] for item in built)
    interpretations = tuple(item[2] for item in built)
    hypotheses = tuple(item[3] for item in built)
    event_range = MethodologizedDateRange(
        EVALUATION_DATE,
        EVALUATION_DATE,
        "Focused event date.",
    )
    return EventIntelligenceSubmission(
        submission_id=submission_id,
        event_id=f"event-{submission_id}",
        producer_id="focused-test-producer",
        producer_version="1.0",
        observed_at=datetime.datetime(2030, 1, 1, tzinfo=UTC),
        event_description="A focused integration-test event.",
        event_date_range=event_range,
        sources=tuple(item[0] for item in built),
        statements=facts + interpretations,
        hypotheses=hypotheses,
    )


def make_request_factory(calls, *, case_id_transform=None):
    def factory(*, case_id, structure, context):
        calls.append((case_id, structure, context))
        provenance = core_research.CoreProvenance(
            source_reference=structure.provenance.source_reference,
            description="Focused test provenance",
        )
        payoff = core_research.CorePayoffModel(
            authority=core_research.CorePayoffAuthority.CONDITIONAL_STANDARD_PAYOFF,
            model_id="conditional-standard-payoff",
            model_version="0.1",
            description="Explicit test-only conditional standard payoff.",
            provenance=provenance,
        )
        return core_research.CoreResearchRequest(
            case_id=(
                case_id
                if case_id_transform is None
                else case_id_transform(case_id)
            ),
            structure=structure,
            payoff_model=payoff,
            cost_ledger=None,
            risk_policy=None,
            sensitivity=None,
            reviewed_enhancements=(),
            description="Focused Core application integration request.",
            provenance=provenance,
        )

    return factory


def make_policy(
    calls,
    *,
    max_submissions=8,
    max_hypotheses=8,
    max_browser_rows=100,
    max_cases=100,
    case_id_transform=None,
):
    return CoreResearchPolicy(
        evaluation_date=EVALUATION_DATE,
        maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
        generated_quantity=1,
        bounds=CoreOperationalBounds(
            max_submissions=max_submissions,
            max_hypotheses=max_hypotheses,
            max_browser_rows=max_browser_rows,
            max_cases=max_cases,
            quote_timeout_seconds=1.0,
        ),
        request_factory=make_request_factory(
            calls, case_id_transform=case_id_transform
        ),
    )


class FakeMarketBridge:
    def __init__(self, rows, asks=None):
        self.rows = tuple(rows)
        self.asks = asks or {row.provider_identifier: decimal.Decimal("2.50") for row in rows}
        self.verifications = {row.provider_identifier: make_verification(row) for row in rows}
        self.calls = []

    def discover_browser(self, request):
        self.calls.append(("discover", request))
        return make_browser(request, self.rows)

    def verify_browser_row(self, request, row):
        self.calls.append(("verify", request, row))
        return self.verifications[row.provider_identifier]

    def quote_browser(self, browser, *, timeout_seconds):
        self.calls.append(("quote", browser, timeout_seconds))
        return make_quote_batch(browser, self.asks)


class FakeDirectBridge:
    def __init__(self, verifications, quotes):
        self.verifications = dict(verifications)
        self.quotes = dict(quotes)
        self.calls = []

    def verify_exact_leg(self, leg):
        self.calls.append(("verify", leg))
        return self.verifications[leg.leg_id]

    def quote_direct(self, verification, *, timeout_seconds):
        self.calls.append(("quote", verification, timeout_seconds))
        return self.quotes[verification.provider_identifier]


def make_direct_structure(row, verification, *, ask=decimal.Decimal("99.00")):
    reference = verification.contract_reference
    provenance = core_research.CoreProvenance(
        source_reference=reference.metadata.source_references[0],
        description="Caller supplied exact structure provenance.",
    )
    leg = core_research.CoreLeg(
        leg_id=row.provider_identifier,
        underlying="ABC",
        currency="USD",
        option_type=(
            core_research.CoreOptionType.CALL
            if row.option_type == "call"
            else core_research.CoreOptionType.PUT
        ),
        strike=row.strike,
        expiration=row.expiration,
        quantity=1,
        contract_multiplier=row.lot_size,
        ask_per_underlying_unit=ask,
        ask_authority=core_research.CoreAskAuthority.INDICATIVE_ONLY,
        description="Caller exact structure leg.",
        provenance=provenance,
    )
    return core_research.CoreStructure(
        legs=(leg,),
        description="Caller exact structure.",
        provenance=provenance,
    )


def make_native_quote(verification, ask):
    return FutuNativeDirectAskEvidence(
        provider_identifier=verification.provider_identifier,
        ask_per_underlying_unit=ask,
        ask_size=None if ask is None else 1,
        receipt=FutuNativeDirectAskReceipt(
            operation="get_order_book",
            provider_identifier=verification.provider_identifier,
            received_at=RETRIEVED_AT,
        ),
        quote_authority=NativeQuoteAuthority.INDICATIVE_ONLY,
    )


class CoreApplicationIntegrationTests(unittest.TestCase):
    def test_three_entries_share_kernel_all_hypotheses_and_no_policy_is_dsc(self):
        row_call = make_row(datetime.date(2030, 1, 31), "CALL", "100")
        row_put = make_row(datetime.date(2030, 1, 31), "PUT", "100")
        bridge = FakeMarketBridge((row_call, row_put))
        factory_calls = []
        policy = make_policy(factory_calls)

        world_raw = object()
        world_submission = make_submission("world-sub", ("hyp-a", "hyp-b"))
        world_batch = SourceSubmissionBatch(world_raw, (world_submission,))
        world = run_world_core(
            world_raw,
            source_producer=lambda raw: world_batch,
            market_bridge=bridge,
            policy=policy,
        )

        event_raw = UserEventInput("Investigate this user event.")
        event_submission = make_submission("event-sub", ("hyp-event",))
        event_batch = SourceSubmissionBatch(event_raw, (event_submission,))
        event = run_event_core(
            event_raw,
            grounder=lambda raw: event_batch,
            market_bridge=bridge,
            policy=policy,
        )

        verification = bridge.verifications[row_call.provider_identifier]
        direct_structure = make_direct_structure(row_call, verification)
        direct_quote = make_native_quote(verification, decimal.Decimal("2.50"))
        direct_bridge = FakeDirectBridge(
            {row_call.provider_identifier: verification},
            {row_call.provider_identifier: direct_quote},
        )
        direct = run_direct_core(
            direct_structure,
            exact_provider_bridge=direct_bridge,
            direct_quote_evidence=direct_quote,
            policy=policy,
        )

        self.assertEqual(len(world.case_set.cases), 2)
        self.assertEqual(len(event.case_set.cases), 1)
        self.assertTrue(all(item.kernel_result.request is item.kernel_request for item in world.case_set.cases))
        self.assertIs(event.case_set.cases[0].kernel_result.request, event.case_set.cases[0].kernel_request)
        self.assertIs(direct.kernel_result.request, direct.kernel_request)
        self.assertEqual(
            {
                item.kernel_result.disposition
                for item in world.case_set.cases + event.case_set.cases + (direct,)
            },
            {core_research.CoreDisposition.DATA_INSUFFICIENT_CORE},
        )
        self.assertEqual(len(factory_calls), 4)
        self.assertTrue(all(call[1] is call[2].core_structure for call in factory_calls))
        self.assertTrue(all(item.kernel_result.geometry.status is core_research.CoreGeometryStatus.AVAILABLE for item in world.case_set.cases))
        self.assertIn(core_research.CoreReasonCode.COST_LEDGER_MISSING, world.case_set.cases[0].kernel_result.reasons)
        self.assertIn(core_research.CoreReasonCode.RISK_POLICY_MISSING, world.case_set.cases[0].kernel_result.reasons)

    def test_source_identity_and_case_ids_are_stable_across_all_accepted_hypotheses(self):
        row_call = make_row(datetime.date(2030, 1, 31), "CALL", "100")
        row_put = make_row(datetime.date(2030, 1, 31), "PUT", "100")
        bridge = FakeMarketBridge((row_call, row_put))
        raw = object()
        submission = make_submission("stable-sub", ("hyp-b", "hyp-a"))
        batch = SourceSubmissionBatch(raw, (submission,))
        policy = make_policy([])

        first = run_world_core(
            raw,
            source_producer=lambda actual: batch,
            market_bridge=bridge,
            policy=policy,
        )
        second = run_world_core(
            raw,
            source_producer=lambda actual: batch,
            market_bridge=bridge,
            policy=policy,
        )
        first_ids = tuple(item.case_id for item in first.case_set.cases)
        second_ids = tuple(item.case_id for item in second.case_set.cases)
        self.assertEqual(first_ids, second_ids)
        self.assertEqual(first_ids, ("stable-sub:hyp-a:US.ABC300131C100000:US.ABC300131P100000", "stable-sub:hyp-b:US.ABC300131C100000:US.ABC300131P100000"))
        self.assertIs(first.case_set.submissions, batch)
        self.assertIs(first.case_set.cases[0].submissions, batch)
        self.assertIs(first.case_set.cases[0].assessment.submission, submission)
        self.assertIs(first.case_set.cases[0].hypothesis, submission.hypotheses[0])

    def test_neutral_browser_is_exhaustive_and_bounds_fail_closed_before_quotes(self):
        rows = (
            make_row(datetime.date(2030, 1, 31), "CALL", "100"),
            make_row(datetime.date(2030, 1, 31), "PUT", "100"),
            make_row(datetime.date(2030, 1, 31), "CALL", "105"),
            make_row(datetime.date(2030, 1, 31), "PUT", "95"),
            make_row(datetime.date(2030, 2, 28), "CALL", "110"),
            make_row(datetime.date(2030, 2, 28), "PUT", "110"),
        )
        raw = object()
        submission = make_submission("enum-sub")
        batch = SourceSubmissionBatch(raw, (submission,))

        bridge = FakeMarketBridge(rows)
        complete = run_world_core(
            raw,
            source_producer=lambda actual: batch,
            market_bridge=bridge,
            policy=make_policy([]),
        )
        self.assertEqual(len(complete.case_set.cases), 2)
        self.assertEqual(len(complete.case_set.unavailable), 2)
        self.assertEqual(len([item for item in bridge.calls if item[0] == "quote"]), 1)
        cards = complete.compact.table
        self.assertEqual([card.structure_kind for card in cards], ["STRADDLE", "STRADDLE"])
        self.assertEqual(cards[0].legs[0].expiration, datetime.date(2030, 1, 31))
        self.assertEqual(cards[0].legs[0].strike, decimal.Decimal("100"))
        self.assertEqual(cards[0].budget_status, "DATA_INSUFFICIENT_CORE")
        self.assertIsNone(cards[0].single_cost_upper_bound)
        case_report = report(complete.case_set.cases[0])
        self.assertIn(core_research.CoreReasonCode.COST_LEDGER_MISSING.value, case_report)
        self.assertIn(core_research.CoreReasonCode.RISK_POLICY_MISSING.value, case_report)
        self.assertIn(core_research.CoreReasonCode.SENSITIVITY_MISSING.value, case_report)
        duplicate_case_report = report(
            replace(
                complete.case_set.cases[0],
                reasons=(core_research.CoreReasonCode.COST_LEDGER_MISSING.value,),
            )
        )
        self.assertEqual(
            duplicate_case_report.count(
                core_research.CoreReasonCode.COST_LEDGER_MISSING.value
            ),
            1,
        )

        limited_bridge = FakeMarketBridge(rows)
        limited = run_world_core(
            raw,
            source_producer=lambda actual: batch,
            market_bridge=limited_bridge,
            policy=make_policy([], max_cases=1),
        )
        self.assertEqual(limited.case_set.status, "LIMIT_EXCEEDED")
        self.assertEqual(limited.case_set.cases, ())
        self.assertEqual([item[0] for item in limited_bridge.calls], ["discover"])

        row_limited_bridge = FakeMarketBridge(rows)
        row_limited = run_world_core(
            raw,
            source_producer=lambda actual: batch,
            market_bridge=row_limited_bridge,
            policy=make_policy([], max_browser_rows=5),
        )
        self.assertEqual(row_limited.case_set.cases, ())
        self.assertIn("LIMIT_EXCEEDED", row_limited.case_set.reasons)
        self.assertEqual([item[0] for item in row_limited_bridge.calls], ["discover"])

    def test_source_bounds_stop_discovery_before_next_accepted_hypothesis(self):
        rows = (
            make_row(datetime.date(2030, 1, 31), "CALL", "100"),
            make_row(datetime.date(2030, 1, 31), "PUT", "100"),
        )
        raw = object()
        batch = SourceSubmissionBatch(
            raw, (make_submission("early-stop", ("hyp-a", "hyp-b")),)
        )

        row_bounded_bridge = FakeMarketBridge(rows)
        row_bounded = run_world_core(
            raw,
            source_producer=lambda actual: batch,
            market_bridge=row_bounded_bridge,
            policy=make_policy([], max_browser_rows=1),
        )
        self.assertEqual(row_bounded.case_set.status, "LIMIT_EXCEEDED")
        self.assertEqual(row_bounded.case_set.cases, ())
        self.assertEqual([item[0] for item in row_bounded_bridge.calls], ["discover"])

        case_bounded_bridge = FakeMarketBridge(rows)
        case_bounded = run_world_core(
            raw,
            source_producer=lambda actual: batch,
            market_bridge=case_bounded_bridge,
            policy=make_policy([], max_cases=0),
        )
        self.assertEqual(case_bounded.case_set.status, "LIMIT_EXCEEDED")
        self.assertEqual(case_bounded.case_set.cases, ())
        self.assertEqual([item[0] for item in case_bounded_bridge.calls], ["discover"])

    def test_missing_source_and_grounder_are_honest_blockers(self):
        policy = make_policy([])
        world_raw = object()
        world = run_world_core(
            world_raw,
            source_producer=None,
            market_bridge=object(),
            policy=policy,
        )
        self.assertEqual(world.case_set.cases, ())
        self.assertEqual(world.case_set.unavailable, ())
        self.assertIn("missing_source_producer", world.case_set.reasons)
        self.assertEqual(world.case_set.status, "BLOCKED")

        event_raw = UserEventInput("Ground this event.")
        event = run_event_core(
            event_raw,
            grounder=None,
            market_bridge=object(),
            policy=policy,
        )
        self.assertEqual(event.case_set.cases, ())
        self.assertIn("missing_grounder", event.case_set.reasons)
        self.assertEqual(event.case_set.status, "BLOCKED")

    def test_direct_dte_endpoints_native_order_book_missing_ask_and_lazy_report(self):
        row = make_row(datetime.date(2030, 1, 31), "CALL", "100")
        verification = make_verification(row)
        direct_structure = make_direct_structure(row, verification)
        quote = make_native_quote(verification, decimal.Decimal("2.50"))
        bridge = FakeDirectBridge(
            {row.provider_identifier: verification},
            {row.provider_identifier: quote},
        )
        factory_calls = []
        result = run_direct_core(
            direct_structure,
            exact_provider_bridge=bridge,
            direct_quote_evidence=quote,
            policy=make_policy(factory_calls),
        )
        self.assertFalse(result.blocked)
        self.assertIsNot(result.core_structure, direct_structure)
        self.assertIs(result.kernel_request.structure, result.core_structure)
        self.assertEqual(result.core_structure.legs[0].ask_per_underlying_unit, decimal.Decimal("2.50"))
        self.assertIn("2030-01-31", result.full_report)
        self.assertIn("1x", result.full_report)
        calls_before_render = tuple(bridge.calls)
        rendered = report(result)
        self.assertEqual(tuple(bridge.calls), calls_before_render)
        self.assertIn("核心研究报告", rendered)
        self.assertIn("DATA_INSUFFICIENT_CORE", rendered)
        self.assertIn(
            "1x/2x/5x/10x 是到期毛价值相对指示性 ask 的倍数，不是利润倍数或正式盈亏平衡；已知 ask 金额不等于总进入成本或实际最大损失；条件预算不证明真实账户安全。",
            rendered,
        )
        for reason in (
            core_research.CoreReasonCode.COST_LEDGER_MISSING,
            core_research.CoreReasonCode.RISK_POLICY_MISSING,
            core_research.CoreReasonCode.SENSITIVITY_MISSING,
        ):
            self.assertIn(reason.value, rendered)
        duplicate_rendered = report(
            replace(
                result,
                reasons=(core_research.CoreReasonCode.COST_LEDGER_MISSING.value,),
            )
        )
        self.assertEqual(
            duplicate_rendered.count(
                core_research.CoreReasonCode.COST_LEDGER_MISSING.value
            ),
            1,
        )

        out_of_bounds = make_row(datetime.date(2030, 1, 30), "CALL", "100")
        out_verification = make_verification(out_of_bounds)
        out_structure = make_direct_structure(out_of_bounds, out_verification)
        out_bridge = FakeDirectBridge(
            {out_verification.provider_identifier: out_verification},
            {out_verification.provider_identifier: make_native_quote(out_verification, decimal.Decimal("2.50"))},
        )
        rejected = run_direct_core(
            out_structure,
            exact_provider_bridge=out_bridge,
            direct_quote_evidence=out_bridge.quotes[out_verification.provider_identifier],
            policy=make_policy([]),
        )
        self.assertTrue(rejected.blocked)
        self.assertIn("direct_maturity_out_of_bounds", rejected.reasons)
        self.assertEqual(out_bridge.calls, [])

        missing = make_native_quote(verification, None)
        missing_result = run_direct_core(
            direct_structure,
            exact_provider_bridge=bridge,
            direct_quote_evidence=missing,
            policy=make_policy([]),
        )
        self.assertFalse(missing_result.blocked)
        self.assertIsNone(missing_result.kernel_request.structure.legs[0].ask_per_underlying_unit)
        self.assertIn(core_research.CoreReasonCode.ASK_MISSING, missing_result.kernel_result.reasons)

    def test_direct_verification_identifier_mismatch_fails_closed(self):
        row = make_row(datetime.date(2030, 1, 31), "CALL", "100")
        verification = make_verification(row)
        forged = forge_verification_identifier(
            verification, verification.provider_identifier + "-forged"
        )
        bridge = FakeDirectBridge(
            {row.provider_identifier: forged},
            {},
        )
        result = run_direct_core(
            make_direct_structure(row, verification),
            exact_provider_bridge=bridge,
            direct_quote_evidence=None,
            policy=make_policy([]),
        )
        self.assertTrue(result.blocked)
        self.assertEqual(result.reasons, ("exact_verification_failure",))
        self.assertEqual([item[0] for item in bridge.calls], ["verify"])

    def test_nondirect_verification_identifier_mismatch_fails_closed(self):
        row_call = make_row(datetime.date(2030, 1, 31), "CALL", "100")
        row_put = make_row(datetime.date(2030, 1, 31), "PUT", "100")
        bridge = FakeMarketBridge((row_call, row_put))
        bridge.verifications[row_call.provider_identifier] = forge_verification_identifier(
            bridge.verifications[row_call.provider_identifier],
            row_call.provider_identifier + "-forged",
        )
        raw = object()
        batch = SourceSubmissionBatch(raw, (make_submission("identity-sub"),))
        result = run_world_core(
            raw,
            source_producer=lambda actual: batch,
            market_bridge=bridge,
            policy=make_policy([]),
        )
        self.assertEqual(result.case_set.cases, ())
        self.assertEqual(len(result.case_set.unavailable), 1)
        self.assertEqual(
            result.case_set.unavailable[0].reasons,
            ("exact_verification_failure",),
        )

    def test_factory_case_id_mismatch_fails_closed_for_direct_and_nondirect(self):
        row_call = make_row(datetime.date(2030, 1, 31), "CALL", "100")
        row_put = make_row(datetime.date(2030, 1, 31), "PUT", "100")
        raw = object()
        batch = SourceSubmissionBatch(raw, (make_submission("factory-sub"),))
        bridge = FakeMarketBridge((row_call, row_put))
        mismatched_policy = make_policy(
            [], case_id_transform=lambda case_id: case_id + ":mismatch"
        )
        world = run_world_core(
            raw,
            source_producer=lambda actual: batch,
            market_bridge=bridge,
            policy=mismatched_policy,
        )
        self.assertEqual(world.case_set.cases, ())
        self.assertEqual(len(world.case_set.unavailable), 1)
        self.assertEqual(
            world.case_set.unavailable[0].reasons,
            ("kernel_case_failure",),
        )

        verification = bridge.verifications[row_call.provider_identifier]
        direct_bridge = FakeDirectBridge(
            {row_call.provider_identifier: verification},
            {row_call.provider_identifier: make_native_quote(verification, decimal.Decimal("2.50"))},
        )
        direct = run_direct_core(
            make_direct_structure(row_call, verification),
            exact_provider_bridge=direct_bridge,
            direct_quote_evidence=direct_bridge.quotes[verification.provider_identifier],
            policy=mismatched_policy,
        )
        self.assertTrue(direct.blocked)
        self.assertIn("kernel_case_failure", direct.reasons)

    def test_option_only_order_book_closes_context_and_wrong_native_authority_blocks(self):
        row = make_row(datetime.date(2030, 1, 31), "CALL", "100")
        verification = make_verification(row)

        class OptionOnlyContext:
            def __init__(self):
                self.calls = []
                self.operations = []
                self.closed = False
                self.subscription_result = (0, "")
                self.order_book_data = None

            def subscribe(self, codes, subtypes, **kwargs):
                self.operations.append(
                    ("subscribe", tuple(codes), tuple(subtypes), dict(kwargs))
                )
                return self.subscription_result

            def get_order_book(self, code, *, num):
                self.calls.append((code, num))
                self.operations.append(("get_order_book", code, num))
                return 0, self.order_book_data or {
                    "code": code,
                    "Ask": [[decimal.Decimal("2.50"), 1]],
                }

            def close(self):
                self.closed = True

        context = OptionOnlyContext()
        fake_sdk = mock.Mock(
            RET_OK=0,
            SubType=mock.Mock(ORDER_BOOK="ORDER_BOOK"),
        )
        with mock.patch.object(futu, "_load_futu_sdk", return_value=fake_sdk):
            evidence = retrieve_futu_native_direct_ask_evidence(
                context, verification, timeout_seconds=1.0
            )
        self.assertEqual(evidence.ask_per_underlying_unit, decimal.Decimal("2.50"))
        self.assertEqual(context.calls, [(verification.provider_identifier, 1)])
        self.assertEqual(
            context.operations,
            [
                (
                    "subscribe",
                    (verification.provider_identifier,),
                    ("ORDER_BOOK",),
                    {"subscribe_push": False},
                ),
                ("get_order_book", verification.provider_identifier, 1),
            ],
        )

        bridge_context = OptionOnlyContext()
        market_bridge = FutuMarketBridge(lambda: bridge_context)
        with mock.patch.object(futu, "_load_futu_sdk", return_value=fake_sdk):
            bridged = market_bridge.quote_direct(verification, timeout_seconds=1.0)
        self.assertEqual(bridged.ask_per_underlying_unit, decimal.Decimal("2.50"))
        self.assertTrue(bridge_context.closed)
        self.assertEqual(bridge_context.operations[0][0], "subscribe")
        self.assertEqual(bridge_context.operations[1][0], "get_order_book")

        malformed_bid = OptionOnlyContext()
        malformed_bid.order_book_data = {
            "code": verification.provider_identifier,
            "Ask": [[decimal.Decimal("2.50"), 1]],
            "Bid": "malformed",
        }
        with mock.patch.object(futu, "_load_futu_sdk", return_value=fake_sdk):
            malformed_evidence = retrieve_futu_native_direct_ask_evidence(
                malformed_bid, verification, timeout_seconds=1.0
            )
        self.assertIsNone(malformed_evidence.ask_per_underlying_unit)
        self.assertIsNone(malformed_evidence.ask_size)
        self.assertEqual(
            malformed_evidence.reason_code,
            futu.FutuBrowserQuoteReasonCode.MALFORMED_FRAME,
        )

        subscription_failure = OptionOnlyContext()
        subscription_failure.subscription_result = (1, "rejected")
        with mock.patch.object(futu, "_load_futu_sdk", return_value=fake_sdk):
            with self.assertRaisesRegex(RuntimeError, "subscription"):
                FutuMarketBridge(lambda: subscription_failure).quote_direct(
                    verification, timeout_seconds=1.0
                )
        self.assertEqual(subscription_failure.calls, [])
        self.assertTrue(subscription_failure.closed)
        self.assertEqual(subscription_failure.operations[0][0], "subscribe")

        invalid = object.__new__(FutuNativeDirectAskEvidence)
        for name, value in vars(evidence).items():
            object.__setattr__(invalid, name, value)
        object.__setattr__(invalid, "quote_authority", None)
        direct_structure = make_direct_structure(row, verification)
        direct_bridge = FakeDirectBridge(
            {row.provider_identifier: verification},
            {row.provider_identifier: evidence},
        )
        blocked = run_direct_core(
            direct_structure,
            exact_provider_bridge=direct_bridge,
            direct_quote_evidence=invalid,
            policy=make_policy([]),
        )
        self.assertTrue(blocked.blocked)
        self.assertIn("quote_operation_blocked", blocked.reasons)


if __name__ == "__main__":
    unittest.main()
