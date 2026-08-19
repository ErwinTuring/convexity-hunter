"""Tests for the bounded Futu Exact Contract Browser and selection."""

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
from convexity_hunter.evidence import OptionStructure
from convexity_hunter.option_chain_discovery import (
    create_option_chain_discovery_request,
)
from convexity_hunter.providers import futu
from tests.test_option_chain_discovery import make_handoff
from tests.test_futu_option_chain_discovery import (
    LOWER,
    UPPER,
    DiscoveryContext,
    chain_row,
    expiration_row,
    make_request,
)


UTC = datetime.timezone.utc
RETRIEVED_AT = datetime.datetime(2030, 1, 1, 12, 0, tzinfo=UTC)


def make_evidence(expirations=None, chains=None):
    expiration_rows = (
        [expiration_row(LOWER)] if expirations is None else expirations
    )
    chain_rows = (
        {
            LOWER.isoformat(): [
                chain_row(LOWER, "CALL", "100"),
                chain_row(LOWER, "PUT", "100"),
            ]
        }
        if chains is None
        else chains
    )
    context = DiscoveryContext(expiration_rows, chain_rows)
    with mock.patch.object(futu, "_utc_now", return_value=RETRIEVED_AT):
        result = futu.retrieve_futu_option_chain_discovery_evidence(
            context,
            discovery_request=make_request(),
        )
    return result, context


def browser_with_rows(rows, expiration=LOWER):
    evidence, context = make_evidence(
        [expiration_row(expiration)],
        {expiration.isoformat(): rows},
    )
    return futu.create_futu_exact_contract_browser(evidence), context


class PublicContractTests(unittest.TestCase):
    def test_exact_records_signatures_and_reexport_boundary(self):
        self.assertEqual(
            tuple(field.name for field in fields(futu.FutuExactContractBrowser)),
            ("discovery_evidence",),
        )
        self.assertEqual(
            tuple(field.name for field in fields(futu.FutuExactContractSelection)),
            ("browser", "selected_contracts", "structure"),
        )
        create_signature = inspect.signature(
            futu.create_futu_exact_contract_browser
        )
        self.assertEqual(tuple(create_signature.parameters), ("discovery_evidence",))
        select_signature = inspect.signature(futu.select_futu_exact_contracts)
        self.assertEqual(
            tuple(select_signature.parameters),
            (
                "browser",
                "provider_identifiers",
                "assumed_portfolio_value",
                "expected_holding_days",
                "quantity",
            ),
        )
        for name in (
            "FutuExactContractBrowser",
            "FutuExactContractSelection",
            "create_futu_exact_contract_browser",
            "select_futu_exact_contracts",
        ):
            self.assertFalse(hasattr(convexity_hunter, name))
            self.assertFalse(
                hasattr(sys.modules["convexity_hunter.providers"], name)
            )


class BrowserTests(unittest.TestCase):
    def test_browser_retains_evidence_and_filters_only_visible_rows(self):
        rows = []
        index = 0
        for monthly in (True, False):
            for standard in (True, False):
                for suspended in (False, True):
                    index += 1
                    rows.append(
                        chain_row(
                            LOWER,
                            "CALL",
                            str(100 + index),
                            cycle="MONTH" if monthly else "WEEK",
                            standard=(
                                "STANDARD" if standard else "NON_STANDARD"
                            ),
                            suspension=suspended,
                        )
                    )
        evidence, context = make_evidence(
            [expiration_row(LOWER)],
            {LOWER.isoformat(): rows},
        )
        browser = futu.create_futu_exact_contract_browser(evidence)
        self.assertIs(browser.discovery_evidence, evidence)
        self.assertEqual(len(browser.rows), 1)
        self.assertIs(browser.rows[0], evidence.contracts[0])
        self.assertEqual(
            browser.rows[0].statuses,
            (futu.FutuOptionChainRowStatus.ELIGIBLE,),
        )
        self.assertEqual(
            context.calls,
            [
                ("expiration", "US.ABC"),
                ("chain", "US.ABC", LOWER.isoformat(), LOWER.isoformat()),
            ],
        )

    def test_browser_preserves_neutral_order_and_inherited_request_bounds(self):
        weekly = datetime.date(2030, 3, 15)
        evidence, _ = make_evidence(
            [
                expiration_row(UPPER),
                expiration_row(weekly, "WEEK"),
                expiration_row(LOWER),
            ],
            {
                LOWER.isoformat(): [
                    chain_row(LOWER, "PUT", "101"),
                    chain_row(LOWER, "PUT", "100"),
                    chain_row(LOWER, "CALL", "100"),
                ],
                UPPER.isoformat(): [chain_row(UPPER, "CALL", "90")],
            },
        )
        browser = futu.create_futu_exact_contract_browser(evidence)
        self.assertEqual(
            tuple(
                (row.expiration, row.strike, row.option_type)
                for row in browser.rows
            ),
            (
                (LOWER, decimal.Decimal("100"), "call"),
                (LOWER, decimal.Decimal("100"), "put"),
                (LOWER, decimal.Decimal("101"), "put"),
                (UPPER, decimal.Decimal("90"), "call"),
            ),
        )
        request = browser.discovery_evidence.discovery_request
        self.assertEqual(request.minimum_expiration_date, LOWER)
        self.assertEqual(request.maximum_expiration_date, UPPER)
        self.assertTrue(
            all(
                request.minimum_expiration_date
                <= row.expiration
                <= request.maximum_expiration_date
                for row in browser.rows
            )
        )

    def test_event_window_plus_30_boundary_is_inherited_exactly(self):
        evaluation_date = datetime.date(2030, 1, 1)
        event_end = datetime.date(2030, 2, 1)
        request = create_option_chain_discovery_request(
            make_handoff(event_window_end=event_end),
            evaluation_date=evaluation_date,
        )
        outside = datetime.date(2030, 3, 2)
        boundary = datetime.date(2030, 3, 3)
        context = DiscoveryContext(
            [expiration_row(outside), expiration_row(boundary)],
            {
                outside.isoformat(): [chain_row(outside, "CALL", "100")],
                boundary.isoformat(): [chain_row(boundary, "CALL", "100")],
            },
        )
        with mock.patch.object(futu, "_utc_now", return_value=RETRIEVED_AT):
            evidence = futu.retrieve_futu_option_chain_discovery_evidence(
                context,
                discovery_request=request,
            )
        browser = futu.create_futu_exact_contract_browser(evidence)
        self.assertEqual(request.minimum_expiration_date, boundary)
        self.assertEqual(
            tuple(row.expiration for row in browser.rows),
            (boundary,),
        )
        self.assertNotIn(
            ("chain", "US.ABC", outside.isoformat(), outside.isoformat()),
            context.calls,
        )

    def test_empty_browser_is_valid_and_has_no_default_selection(self):
        evidence, _ = make_evidence([], {})
        browser = futu.create_futu_exact_contract_browser(evidence)
        self.assertEqual(browser.rows, ())
        self.assertFalse(hasattr(browser, "selection"))
        self.assertFalse(hasattr(browser, "selected_contract"))
        with self.assertRaises(FrozenInstanceError):
            browser.discovery_evidence = evidence

    def test_browser_rejects_wrong_type_and_constructor_bypassed_evidence(self):
        with self.assertRaises(TypeError):
            futu.create_futu_exact_contract_browser(object())
        malformed = object.__new__(futu.FutuOptionChainDiscoveryEvidence)
        with self.assertRaises(ValueError):
            futu.create_futu_exact_contract_browser(malformed)


class SelectionTests(unittest.TestCase):
    def test_single_call_and_put_are_explicit_unverified_research_intent(self):
        browser, _ = browser_with_rows(
            [
                chain_row(LOWER, "CALL", "100"),
                chain_row(LOWER, "PUT", "101"),
            ]
        )
        for row in browser.rows:
            with self.subTest(option_type=row.option_type):
                selection = futu.select_futu_exact_contracts(
                    browser,
                    provider_identifiers=(row.provider_identifier,),
                    assumed_portfolio_value=100000.0,
                    expected_holding_days=20,
                    quantity=3,
                )
                self.assertIs(selection.browser, browser)
                self.assertIs(selection.selected_contracts[0], row)
                self.assertIsInstance(selection.structure, OptionStructure)
                self.assertEqual(
                    selection.structure.structure_type,
                    "long_call" if row.option_type == "call" else "long_put",
                )
                leg = selection.structure.legs[0]
                self.assertEqual(leg.quantity, 3)
                self.assertEqual(leg.contract_multiplier, row.lot_size)
                self.assertEqual(decimal.Decimal(str(leg.strike)), row.strike)
                self.assertFalse(hasattr(selection, "candidate"))
                self.assertFalse(hasattr(selection, "research_readiness"))

    def test_explicit_straddle_is_canonical_and_retains_exact_rows(self):
        browser, _ = browser_with_rows(
            [
                chain_row(LOWER, "PUT", "100"),
                chain_row(LOWER, "CALL", "100"),
            ]
        )
        call, put = browser.rows
        selection = futu.select_futu_exact_contracts(
            browser,
            provider_identifiers=(
                put.provider_identifier,
                call.provider_identifier,
            ),
            assumed_portfolio_value=250000.0,
            expected_holding_days=30,
        )
        self.assertEqual(selection.structure.structure_type, "long_straddle")
        self.assertIs(selection.selected_contracts[0], call)
        self.assertIs(selection.selected_contracts[1], put)
        self.assertEqual(
            tuple(leg.option_type for leg in selection.structure.legs),
            ("call", "put"),
        )

    def test_identifier_types_cardinality_duplicates_unknown_and_hidden_fail(self):
        visible = chain_row(LOWER, "CALL", "100")
        hidden = chain_row(
            LOWER,
            "PUT",
            "100",
            standard="NON_STANDARD",
        )
        browser, _ = browser_with_rows([visible, hidden])
        identifier = browser.rows[0].provider_identifier
        invalid_values = (
            None,
            [identifier],
            (),
            (identifier, identifier),
            (identifier, "US.UNKNOWN"),
            (identifier, "x", "y"),
            (1,),
            ("",),
        )
        for invalid in invalid_values:
            with self.subTest(invalid=invalid), self.assertRaises(
                (TypeError, ValueError)
            ):
                futu.select_futu_exact_contracts(
                    browser,
                    provider_identifiers=invalid,
                    assumed_portfolio_value=100000.0,
                    expected_holding_days=20,
                )
        hidden_identifier = next(
            row.provider_identifier
            for row in browser.discovery_evidence.contracts
            if row not in browser.rows
        )
        with self.assertRaises(ValueError):
            futu.select_futu_exact_contracts(
                browser,
                provider_identifiers=(hidden_identifier,),
                assumed_portfolio_value=100000.0,
                expected_holding_days=20,
            )

    def test_invalid_two_leg_combinations_fail_closed(self):
        other_date = UPPER
        cases = (
            [
                chain_row(LOWER, "CALL", "100"),
                chain_row(LOWER, "CALL", "101"),
            ],
            [
                chain_row(LOWER, "CALL", "100"),
                chain_row(LOWER, "PUT", "101"),
            ],
        )
        for rows in cases:
            with self.subTest(rows=rows):
                browser, _ = browser_with_rows(rows)
                with self.assertRaises(ValueError):
                    futu.select_futu_exact_contracts(
                        browser,
                        provider_identifiers=tuple(
                            row.provider_identifier for row in browser.rows
                        ),
                        assumed_portfolio_value=100000.0,
                        expected_holding_days=20,
                    )

        call = chain_row(LOWER, "CALL", "100")
        put = chain_row(other_date, "PUT", "100")
        evidence, _ = make_evidence(
            [expiration_row(LOWER), expiration_row(other_date)],
            {
                LOWER.isoformat(): [call],
                other_date.isoformat(): [put],
            },
        )
        browser = futu.create_futu_exact_contract_browser(evidence)
        with self.assertRaises(ValueError):
            futu.select_futu_exact_contracts(
                browser,
                provider_identifiers=tuple(
                    row.provider_identifier for row in browser.rows
                ),
                assumed_portfolio_value=100000.0,
                expected_holding_days=20,
            )

        mismatch_lot_rows = [
            chain_row(LOWER, "CALL", "100"),
            chain_row(LOWER, "PUT", "100"),
        ]
        mismatch_lot_rows[1]["lot_size"] = 50
        browser, _ = browser_with_rows(mismatch_lot_rows)
        with self.assertRaises(ValueError):
            futu.select_futu_exact_contracts(
                browser,
                provider_identifiers=tuple(
                    row.provider_identifier for row in browser.rows
                ),
                assumed_portfolio_value=100000.0,
                expected_holding_days=20,
            )

    def test_selection_parameters_use_existing_structure_validation(self):
        browser, _ = browser_with_rows([chain_row(LOWER, "CALL", "100")])
        identifier = browser.rows[0].provider_identifier
        for overrides in (
            {"assumed_portfolio_value": 0.0},
            {"expected_holding_days": -1},
            {"quantity": 0},
            {"quantity": True},
        ):
            kwargs = {
                "provider_identifiers": (identifier,),
                "assumed_portfolio_value": 100000.0,
                "expected_holding_days": 20,
                "quantity": 1,
            }
            kwargs.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(
                (TypeError, ValueError)
            ):
                futu.select_futu_exact_contracts(browser, **kwargs)

    def test_non_roundtrippable_decimal_strike_fails_without_substitution(self):
        strike = decimal.Decimal("9007199254740.993")
        browser, _ = browser_with_rows(
            [chain_row(LOWER, "CALL", strike)]
        )
        with self.assertRaisesRegex(ValueError, "represented exactly"):
            futu.select_futu_exact_contracts(
                browser,
                provider_identifiers=(browser.rows[0].provider_identifier,),
                assumed_portfolio_value=100000.0,
                expected_holding_days=20,
            )

    def test_direct_constructor_rejects_equal_copy_cross_browser_and_bad_structure(self):
        browser, _ = browser_with_rows([chain_row(LOWER, "CALL", "100")])
        selection = futu.select_futu_exact_contracts(
            browser,
            provider_identifiers=(browser.rows[0].provider_identifier,),
            assumed_portfolio_value=100000.0,
            expected_holding_days=20,
        )
        copied_row = dataclasses.replace(selection.selected_contracts[0])
        self.assertEqual(copied_row, selection.selected_contracts[0])
        self.assertIsNot(copied_row, selection.selected_contracts[0])
        with self.assertRaises(ValueError):
            futu.FutuExactContractSelection(
                browser,
                (copied_row,),
                selection.structure,
            )
        other_browser, _ = browser_with_rows(
            [chain_row(LOWER, "CALL", "100")]
        )
        with self.assertRaises(ValueError):
            futu.FutuExactContractSelection(
                other_browser,
                selection.selected_contracts,
                selection.structure,
            )
        bad_structure = dataclasses.replace(
            selection.structure,
            assumed_portfolio_value=200000.0,
        )
        bad_leg = dataclasses.replace(
            bad_structure.legs[0],
            strike=101.0,
        )
        bad_structure = dataclasses.replace(bad_structure, legs=(bad_leg,))
        with self.assertRaises(ValueError):
            futu.FutuExactContractSelection(
                browser,
                selection.selected_contracts,
                bad_structure,
            )

    def test_browser_and_selection_make_no_provider_or_research_calls(self):
        evidence, context = make_evidence()
        calls_before = tuple(context.calls)
        with mock.patch.object(
            futu,
            "verify_futu_monthly_option_contract",
            side_effect=AssertionError("verification invoked"),
        ), mock.patch(
            "convexity_hunter.direct_entry_verification."
            "verify_direct_entry_exact_contracts",
            side_effect=AssertionError("Direct Entry invoked"),
        ):
            browser = futu.create_futu_exact_contract_browser(evidence)
            futu.select_futu_exact_contracts(
                browser,
                provider_identifiers=(browser.rows[0].provider_identifier,),
                assumed_portfolio_value=100000.0,
                expected_holding_days=20,
            )
        self.assertEqual(tuple(context.calls), calls_before)


if __name__ == "__main__":
    unittest.main()
