"""Tests for the bounded Futu selection-to-Direct-Entry bridge."""

import dataclasses
import datetime
import decimal
import inspect
import pathlib
import sys
import unittest
from dataclasses import FrozenInstanceError, fields
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
from convexity_hunter import direct_entry_verification
from convexity_hunter.option_chain_discovery import OptionResearchMaturityContext
from convexity_hunter.providers import futu
from tests.test_futu_exact_contract_browser import browser_with_rows
from tests.test_futu_option_chain_discovery import LOWER, FakeTable, chain_row


class ExactSelectionContext:
    def __init__(self, rows):
        self.rows = tuple(rows)
        self.calls = []

    def get_option_expiration_date(self, code):
        self.calls.append(("expiration", code))
        expirations = sorted({row["strike_time"] for row in self.rows})
        return 0, FakeTable(
            [
                {"strike_time": value, "expiration_cycle": "MONTH"}
                for value in expirations
            ]
        )

    def get_option_chain(self, code, *, start, end, option_type):
        self.calls.append(("chain", code, start, end, option_type))
        selected = [
            row
            for row in self.rows
            if row["strike_time"] == start
            and row["strike_time"] == end
            and row["option_type"] == option_type
        ]
        return 0, FakeTable(selected)

    def get_market_snapshot(self, codes):
        self.calls.append(("snapshot", tuple(codes)))
        selected = [row for row in self.rows if row["code"] in codes]
        return 0, FakeTable(
            [
                {
                    "code": row["code"],
                    "stock_owner": row["stock_owner"],
                    "option_type": row["option_type"],
                    "strike_time": row["strike_time"],
                    "option_strike_price": row["strike_price"],
                    "option_contract_size": row["lot_size"],
                    "option_area_type": "AMERICAN",
                    "option_valid": True,
                }
                for row in selected
            ]
        )


def make_selection(rows, *, quantity=1):
    browser, _ = browser_with_rows(rows)
    return futu.select_futu_exact_contracts(
        browser,
        provider_identifiers=tuple(
            row.provider_identifier for row in browser.rows
        ),
        assumed_portfolio_value=100000.0,
        expected_holding_days=20,
        quantity=quantity,
    )


class PublicContractTests(unittest.TestCase):
    def test_exact_result_signature_api_order_and_reexport_boundary(self):
        result_type = futu.FutuExactContractSelectionVerification
        self.assertTrue(dataclasses.is_dataclass(result_type))
        self.assertTrue(result_type.__dataclass_params__.frozen)
        self.assertEqual(
            tuple(field.name for field in fields(result_type)),
            (
                "selection",
                "contract_verifications",
                "direct_entry_exact_contract_verification",
                "maturity_context",
            ),
        )
        signature = inspect.signature(futu.verify_futu_exact_contract_selection)
        self.assertEqual(tuple(signature.parameters), ("quote_context", "selection"))
        self.assertEqual(
            futu.__all__[8:14],
            (
                "FutuExactContractBrowser",
                "FutuExactContractSelection",
                "create_futu_exact_contract_browser",
                "select_futu_exact_contracts",
                "FutuExactContractSelectionVerification",
                "verify_futu_exact_contract_selection",
            ),
        )
        self.assertEqual(len(futu.__all__), 22)
        for name in (
            "FutuExactContractSelectionVerification",
            "verify_futu_exact_contract_selection",
        ):
            self.assertFalse(hasattr(convexity_hunter, name))
            self.assertFalse(
                hasattr(sys.modules["convexity_hunter.providers"], name)
            )


class SelectionBridgeTests(unittest.TestCase):
    def test_single_leg_uses_exact_selected_values_and_retains_identities(self):
        provider_row = chain_row(LOWER, "CALL", "100")
        selection = make_selection([provider_row], quantity=3)
        context = ExactSelectionContext([provider_row])

        result = futu.verify_futu_exact_contract_selection(context, selection)

        self.assertIs(result.selection, selection)
        self.assertIs(
            result.maturity_context.discovery_request,
            selection.browser.discovery_evidence.discovery_request,
        )
        self.assertIs(result.maturity_context.structure, selection.structure)
        self.assertEqual(len(result.contract_verifications), 1)
        provider_verification = result.contract_verifications[0]
        selected_row = selection.selected_contracts[0]
        self.assertEqual(
            provider_verification.provider_identifier,
            selected_row.provider_identifier,
        )
        self.assertEqual(
            provider_verification.contract_reference.contract_key.strike,
            selected_row.strike,
        )
        direct = result.direct_entry_exact_contract_verification
        self.assertIs(direct.structure, selection.structure)
        self.assertIs(
            direct.contract_references[0],
            provider_verification.contract_reference,
        )
        self.assertEqual(direct.structure.legs[0].quantity, 3)
        self.assertEqual(
            context.calls,
            [
                ("expiration", "US.ABC"),
                (
                    "chain",
                    "US.ABC",
                    LOWER.isoformat(),
                    LOWER.isoformat(),
                    "CALL",
                ),
                ("snapshot", (selected_row.provider_identifier,)),
            ],
        )

    def test_explicit_straddle_verifies_once_per_leg_in_selection_order(self):
        provider_rows = [
            chain_row(LOWER, "PUT", "100"),
            chain_row(LOWER, "CALL", "100"),
        ]
        selection = make_selection(provider_rows)
        context = ExactSelectionContext(provider_rows)

        result = futu.verify_futu_exact_contract_selection(context, selection)

        self.assertEqual(
            tuple(
                verification.provider_identifier
                for verification in result.contract_verifications
            ),
            tuple(
                row.provider_identifier for row in selection.selected_contracts
            ),
        )
        self.assertEqual(
            tuple(leg.option_type for leg in selection.structure.legs),
            ("call", "put"),
        )
        self.assertEqual(
            tuple(call[4] for call in context.calls if call[0] == "chain"),
            ("CALL", "PUT"),
        )
        self.assertEqual(
            tuple(
                reference is verification.contract_reference
                for reference, verification in zip(
                    result.direct_entry_exact_contract_verification.contract_references,
                    result.contract_verifications,
                )
            ),
            (True, True),
        )

    def test_calls_existing_provider_and_direct_entry_verifiers_exactly(self):
        provider_row = chain_row(LOWER, "CALL", "100")
        selection = make_selection([provider_row])
        context = ExactSelectionContext([provider_row])
        with mock.patch.object(
            futu,
            "verify_futu_monthly_option_contract",
            wraps=futu.verify_futu_monthly_option_contract,
        ) as provider_verify, mock.patch.object(
            futu,
            "_verify_direct_entry_exact_contracts",
            wraps=direct_entry_verification.verify_direct_entry_exact_contracts,
        ) as direct_verify:
            result = futu.verify_futu_exact_contract_selection(context, selection)

        provider_verify.assert_called_once_with(
            context,
            underlying_key=(
                selection.browser.discovery_evidence.discovery_request.underlying_key
            ),
            expiration=selection.selected_contracts[0].expiration,
            option_type=selection.selected_contracts[0].option_type,
            strike=selection.selected_contracts[0].strike,
        )
        direct_verify.assert_called_once()
        self.assertIs(direct_verify.call_args.args[0], selection.structure)
        self.assertIs(
            direct_verify.call_args.args[1][0],
            result.contract_verifications[0].contract_reference,
        )

    def test_mismatched_provider_verification_fails_before_direct_entry(self):
        selected_row = chain_row(LOWER, "CALL", "100")
        other_row = chain_row(LOWER, "CALL", "101")
        selection = make_selection([selected_row])
        other_selection = make_selection([other_row])
        other_context = ExactSelectionContext([other_row])
        other = futu.verify_futu_exact_contract_selection(
            other_context,
            other_selection,
        ).contract_verifications[0]
        with mock.patch.object(
            futu,
            "verify_futu_monthly_option_contract",
            return_value=other,
        ), mock.patch.object(
            futu,
            "_verify_direct_entry_exact_contracts",
            side_effect=AssertionError("Direct Entry must not be called"),
        ):
            with self.assertRaisesRegex(ValueError, "does not match"):
                futu.verify_futu_exact_contract_selection(object(), selection)

    def test_wrong_and_constructor_bypassed_selection_fail_before_provider(self):
        malformed = object.__new__(futu.FutuExactContractSelection)
        for value in (object(), malformed):
            with self.subTest(value=value), mock.patch.object(
                futu,
                "verify_futu_monthly_option_contract",
                side_effect=AssertionError("provider must not be called"),
            ):
                with self.assertRaises((TypeError, ValueError)):
                    futu.verify_futu_exact_contract_selection(object(), value)

    def test_provider_failure_propagates_and_stops_before_direct_entry(self):
        selection = make_selection([chain_row(LOWER, "CALL", "100")])
        error = RuntimeError("sanitized provider failure")
        with mock.patch.object(
            futu,
            "verify_futu_monthly_option_contract",
            side_effect=error,
        ), mock.patch.object(
            futu,
            "_verify_direct_entry_exact_contracts",
            side_effect=AssertionError("Direct Entry must not be called"),
        ):
            with self.assertRaises(RuntimeError) as caught:
                futu.verify_futu_exact_contract_selection(object(), selection)
        self.assertIs(caught.exception, error)

    def test_direct_result_construction_enforces_nested_identity(self):
        provider_row = chain_row(LOWER, "CALL", "100")
        selection = make_selection([provider_row])
        result = futu.verify_futu_exact_contract_selection(
            ExactSelectionContext([provider_row]),
            selection,
        )
        verification = result.contract_verifications[0]
        reference = verification.contract_reference

        copied_structure = dataclasses.replace(selection.structure)
        copied_structure_direct = (
            direct_entry_verification.DirectEntryExactContractVerification(
                copied_structure,
                (reference,),
            )
        )
        with self.assertRaisesRegex(ValueError, "exact selection"):
            futu.FutuExactContractSelectionVerification(
                selection,
                result.contract_verifications,
                copied_structure_direct,
                result.maturity_context,
            )

        copied_reference = dataclasses.replace(reference)
        copied_reference_direct = (
            direct_entry_verification.DirectEntryExactContractVerification(
                selection.structure,
                (copied_reference,),
            )
        )
        with self.assertRaisesRegex(ValueError, "exact selection"):
            futu.FutuExactContractSelectionVerification(
                selection,
                result.contract_verifications,
                copied_reference_direct,
                result.maturity_context,
            )

    def test_direct_constructor_rejects_bad_tuple_types_counts_and_matches(self):
        provider_row = chain_row(LOWER, "CALL", "100")
        selection = make_selection([provider_row])
        result = futu.verify_futu_exact_contract_selection(
            ExactSelectionContext([provider_row]),
            selection,
        )
        direct = result.direct_entry_exact_contract_verification
        invalid_values = (
            [result.contract_verifications[0]],
            (),
            (object(),),
        )
        for invalid in invalid_values:
            with self.subTest(invalid=invalid), self.assertRaises(
                (TypeError, ValueError)
            ):
                futu.FutuExactContractSelectionVerification(
                    selection,
                    invalid,
                    direct,
                    result.maturity_context,
                )
        with self.assertRaises(TypeError):
            futu.FutuExactContractSelectionVerification(
                selection,
                result.contract_verifications,
                object(),
                result.maturity_context,
            )
        with self.assertRaises(FrozenInstanceError):
            result.selection = selection

    def test_context_identity_mismatches_fail_closed(self):
        provider_row = chain_row(LOWER, "CALL", "100")
        selection = make_selection([provider_row])
        result = futu.verify_futu_exact_contract_selection(
            ExactSelectionContext([provider_row]),
            selection,
        )
        other_selection = make_selection([provider_row])
        other_result = futu.verify_futu_exact_contract_selection(
            ExactSelectionContext([provider_row]),
            other_selection,
        )
        with self.assertRaisesRegex(
            ValueError, "^maturity_context_request_mismatch$"
        ):
            futu.FutuExactContractSelectionVerification(
                selection,
                result.contract_verifications,
                result.direct_entry_exact_contract_verification,
                other_result.maturity_context,
            )
        copied_context = type(result.maturity_context)(
            result.maturity_context.discovery_request,
            dataclasses.replace(selection.structure),
        )
        with self.assertRaisesRegex(
            ValueError, "^maturity_context_structure_mismatch$"
        ):
            futu.FutuExactContractSelectionVerification(
                selection,
                result.contract_verifications,
                result.direct_entry_exact_contract_verification,
                copied_context,
            )

        malformed_context = object.__new__(OptionResearchMaturityContext)
        object.__setattr__(
            malformed_context,
            "structure",
            selection.structure,
        )
        with self.assertRaisesRegex(
            ValueError, "^maturity_context is malformed$"
        ):
            futu.FutuExactContractSelectionVerification(
                selection,
                result.contract_verifications,
                result.direct_entry_exact_contract_verification,
                malformed_context,
            )

    def test_bridge_does_not_call_downstream_research_or_other_provider_paths(self):
        provider_row = chain_row(LOWER, "CALL", "100")
        selection = make_selection([provider_row])
        context = ExactSelectionContext([provider_row])
        with mock.patch(
            "convexity_hunter.candidate_assembly.assemble_candidate_research_record",
            side_effect=AssertionError("Candidate Assembly invoked"),
        ), mock.patch(
            "convexity_hunter.direct_entry_reviewed_research_service."
            "run_direct_entry_reviewed_research_service",
            side_effect=AssertionError("reviewed-research service invoked"),
        ):
            result = futu.verify_futu_exact_contract_selection(context, selection)
        self.assertIs(
            result.direct_entry_exact_contract_verification.structure,
            selection.structure,
        )
        self.assertEqual(
            {call[0] for call in context.calls},
            {"expiration", "chain", "snapshot"},
        )


if __name__ == "__main__":
    unittest.main()
