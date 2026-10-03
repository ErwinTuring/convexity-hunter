"""Focused synthetic contract tests for the host Direct input adapter."""

import copy
import datetime
import decimal
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tests import test_core_application as core_fixtures

from convexity_hunter.core_application import CoreOperationalBounds
from convexity_hunter.core_research import (
    CoreAskAuthority,
    CoreDisposition,
    CoreOptionType,
    CoreReasonCode,
)
from convexity_hunter.host_direct import (
    HostDirectBoundsError,
    HostDirectInputError,
    parse_direct_input,
    run_direct_input,
)
from convexity_hunter.host_profile import STANDARD_RESEARCH_PROFILE
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority


EVALUATION_DATE = datetime.date(2030, 1, 1)
EXPIRATION = datetime.date(2030, 1, 31)


def _leg(option_type, *, strike="100", expiration=EXPIRATION, **overrides):
    values = {
        "provider_identifier": core_fixtures.identifier(
            expiration, option_type, strike
        ),
        "underlying": "ABC",
        "currency": "USD",
        "option_type": option_type,
        "strike": strike,
        "expiration": expiration.isoformat(),
        "quantity": 1,
        "contract_multiplier": 100,
    }
    values.update(overrides)
    return values


def _payload(structure="LONG_CALL", legs=None):
    if legs is None:
        option_type = "PUT" if structure == "LONG_PUT" else "CALL"
        legs = [_leg(option_type)]
    return {
        "schema_version": "host-direct-input-v0.1",
        "evaluation_date": EVALUATION_DATE.isoformat(),
        "structure": structure,
        "legs": legs,
    }


def _bounds(*, max_cases=1, max_submissions=0, max_hypotheses=0, max_browser_rows=0):
    return CoreOperationalBounds(
        max_submissions=max_submissions,
        max_hypotheses=max_hypotheses,
        max_browser_rows=max_browser_rows,
        max_cases=max_cases,
        quote_timeout_seconds=1.0,
    )


def _bridge_for(payload, *, ask=decimal.Decimal("2.50")):
    rows = tuple(
        core_fixtures.make_row(
            datetime.date.fromisoformat(leg["expiration"]),
            leg["option_type"],
            leg["strike"],
            lot_size=leg["contract_multiplier"],
        )
        for leg in payload["legs"]
    )
    verifications = {
        row.provider_identifier: core_fixtures.make_verification(row)
        for row in rows
    }
    quotes = {
        identifier: core_fixtures.make_native_quote(verification, ask)
        for identifier, verification in verifications.items()
    }
    return core_fixtures.FakeDirectBridge(verifications, quotes), verifications, quotes


class HostDirectParserTests(unittest.TestCase):
    def test_parses_exact_user_terms_without_invented_defaults(self):
        payload = _payload(
            "LONG_STRADDLE",
            [_leg("CALL", contract_multiplier=25), _leg("PUT", contract_multiplier=25)],
        )
        parsed = parse_direct_input(json.dumps(payload))
        self.assertEqual(parsed.evaluation_date, EVALUATION_DATE)
        self.assertEqual(len(parsed.structure.legs), 2)
        self.assertEqual(
            tuple(leg.option_type for leg in parsed.structure.legs),
            (CoreOptionType.CALL, CoreOptionType.PUT),
        )
        self.assertEqual(parsed.structure.legs[0].contract_multiplier, 25)
        for leg in parsed.structure.legs:
            self.assertIsNone(leg.ask_per_underlying_unit)
            self.assertIs(leg.ask_authority, CoreAskAuthority.INDICATIVE_ONLY)
            self.assertIsNone(leg.provenance.source_reference)

    def test_closed_schema_and_invalid_semantics_fail_before_any_bridge_call(self):
        valid = _payload()
        invalid_payloads = []

        extra_top = copy.deepcopy(valid)
        extra_top["ask"] = "2.50"
        invalid_payloads.append(json.dumps(extra_top))

        missing_top = copy.deepcopy(valid)
        del missing_top["evaluation_date"]
        invalid_payloads.append(json.dumps(missing_top))

        extra_leg = copy.deepcopy(valid)
        extra_leg["legs"][0]["ask"] = "2.50"
        invalid_payloads.append(json.dumps(extra_leg))

        numeric_strike = copy.deepcopy(valid)
        numeric_strike["legs"][0]["strike"] = 100
        invalid_payloads.append(json.dumps(numeric_strike))

        bad_date = copy.deepcopy(valid)
        bad_date["evaluation_date"] = "2030-1-1"
        invalid_payloads.append(json.dumps(bad_date))

        boolean_quantity = copy.deepcopy(valid)
        boolean_quantity["legs"][0]["quantity"] = True
        invalid_payloads.append(json.dumps(boolean_quantity))

        zero_multiplier = copy.deepcopy(valid)
        zero_multiplier["legs"][0]["contract_multiplier"] = 0
        invalid_payloads.append(json.dumps(zero_multiplier))

        invalid_id = copy.deepcopy(valid)
        invalid_id["legs"][0]["provider_identifier"] = "not-an-option-id"
        invalid_payloads.append(json.dumps(invalid_id))

        mismatched_id = copy.deepcopy(valid)
        mismatched_id["legs"][0]["underlying"] = "OTHER"
        invalid_payloads.append(json.dumps(mismatched_id))

        wrong_pair = _payload("LONG_CALL", [_leg("PUT")])
        invalid_payloads.append(json.dumps(wrong_pair))

        duplicate_leg_id = _payload(
            "LONG_STRADDLE", [_leg("CALL"), _leg("PUT")]
        )
        duplicate_leg_id["legs"][1]["provider_identifier"] = (
            duplicate_leg_id["legs"][0]["provider_identifier"]
        )
        invalid_payloads.append(json.dumps(duplicate_leg_id))

        mismatched_straddle = _payload(
            "LONG_STRADDLE", [_leg("CALL"), _leg("PUT", strike="105")]
        )
        invalid_payloads.append(json.dumps(mismatched_straddle))

        duplicate_json = (
            '{"schema_version":"host-direct-input-v0.1",'
            '"schema_version":"host-direct-input-v0.1",'
            '"evaluation_date":"2030-01-01","structure":"LONG_CALL","legs":[]}'
        )
        invalid_payloads.extend(
            (
                duplicate_json,
                json.dumps(valid).replace('"strike": "100"', '"strike": NaN'),
                json.dumps(valid).replace('"strike": "100"', '"strike": 1e999'),
                chr(96) * 3 + "json\\n" + json.dumps(valid) + "\\n" + chr(96) * 3,
            )
        )

        bridge, _, _ = _bridge_for(valid)
        for raw_input in invalid_payloads:
            with self.subTest(raw_input=raw_input[:80]):
                with self.assertRaises(HostDirectInputError):
                    run_direct_input(
                        raw_input,
                        bounds=_bounds(),
                        exact_provider_bridge=bridge,
                    )
                self.assertEqual(bridge.calls, [])

    def test_unknown_structure_and_straddle_leg_count_fail_closed(self):
        invalid = (
            _payload("CONDOR", [_leg("CALL")]),
            _payload("LONG_STRADDLE", [_leg("CALL")]),
            _payload("LONG_STRADDLE", [_leg("CALL"), _leg("CALL", strike="105")]),
            _payload("LONG_PUT", [_leg("CALL")]),
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(HostDirectInputError):
                    parse_direct_input(json.dumps(payload))


class HostDirectExecutionTests(unittest.TestCase):
    def test_all_supported_shapes_use_existing_direct_core_and_neutral_profile(self):
        original_profile = STANDARD_RESEARCH_PROFILE.snapshot()
        cases = (
            ("LONG_CALL", [_leg("CALL")]),
            ("LONG_PUT", [_leg("PUT")]),
            ("LONG_STRADDLE", [_leg("CALL"), _leg("PUT")]),
        )
        for structure, legs in cases:
            with self.subTest(structure=structure):
                payload = _payload(structure, legs)
                bridge, verifications, _quotes = _bridge_for(payload)
                result = run_direct_input(
                    json.dumps(payload),
                    bounds=_bounds(),
                    exact_provider_bridge=bridge,
                )
                self.assertFalse(result.blocked)
                self.assertIs(
                    result.kernel_result.disposition,
                    CoreDisposition.DATA_INSUFFICIENT_CORE,
                )
                self.assertIs(
                    result.maturity_authority,
                    OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
                )
                self.assertIs(result.kernel_result.request, result.kernel_request)
                self.assertIsNone(result.kernel_request.cost_ledger)
                self.assertIsNone(result.kernel_request.sensitivity)
                self.assertIsNotNone(result.kernel_request.risk_policy)
                self.assertIn(
                    CoreReasonCode.COST_LEDGER_MISSING,
                    result.kernel_result.reasons,
                )
                self.assertIn(
                    CoreReasonCode.SENSITIVITY_MISSING,
                    result.kernel_result.reasons,
                )
                self.assertEqual(
                    tuple(call[0] for call in bridge.calls),
                    tuple(
                        ("verify",) * len(legs) + ("quote",) * len(legs)
                    ),
                )
                self.assertEqual(
                    tuple(
                        call[1].provider_identifier
                        for call in bridge.calls
                        if call[0] == "quote"
                    ),
                    tuple(leg["provider_identifier"] for leg in legs),
                )
                self.assertEqual(
                    tuple(result.kernel_request.structure.legs),
                    tuple(result.core_structure.legs),
                )
        self.assertEqual(STANDARD_RESEARCH_PROFILE.snapshot(), original_profile)

    def test_explicit_quote_evidence_and_missing_ask_are_preserved(self):
        payload = _payload()
        bridge, verifications, _quotes = _bridge_for(payload)
        verification = next(iter(verifications.values()))
        supplied_quote = core_fixtures.make_native_quote(
            verification, decimal.Decimal("3.25")
        )
        with_supplied_quote = run_direct_input(
            json.dumps(payload),
            bounds=_bounds(),
            exact_provider_bridge=bridge,
            direct_quote_evidence=supplied_quote,
        )
        self.assertFalse(with_supplied_quote.blocked)
        self.assertEqual(
            with_supplied_quote.core_structure.legs[0].ask_per_underlying_unit,
            decimal.Decimal("3.25"),
        )
        self.assertEqual(tuple(call[0] for call in bridge.calls), ("verify",))

        missing_bridge, _, _ = _bridge_for(payload, ask=None)
        missing_ask = run_direct_input(
            json.dumps(payload),
            bounds=_bounds(),
            exact_provider_bridge=missing_bridge,
        )
        self.assertFalse(missing_ask.blocked)
        self.assertIsNone(
            missing_ask.kernel_request.structure.legs[0].ask_per_underlying_unit
        )
        self.assertIn(CoreReasonCode.ASK_MISSING, missing_ask.kernel_result.reasons)
        self.assertIsNone(missing_ask.kernel_request.cost_ledger)
        self.assertIsNone(missing_ask.kernel_request.sensitivity)

    def test_explicit_multiplier_is_checked_by_core_verification(self):
        payload = _payload()
        payload["legs"][0]["contract_multiplier"] = 25
        parsed = parse_direct_input(json.dumps(payload))
        self.assertEqual(parsed.structure.legs[0].contract_multiplier, 25)

        bridge, _, _ = _bridge_for(_payload())
        result = run_direct_input(
            json.dumps(payload),
            bounds=_bounds(),
            exact_provider_bridge=bridge,
        )
        self.assertTrue(result.blocked)
        self.assertEqual(result.reasons, ("exact_verification_failure",))
        self.assertEqual(tuple(call[0] for call in bridge.calls), ("verify",))

    def test_max_cases_zero_is_a_typed_pre_external_error_only(self):
        payload = _payload()
        bridge, _, _ = _bridge_for(payload)
        with self.assertRaises(HostDirectBoundsError):
            run_direct_input(
                json.dumps(payload),
                bounds=_bounds(max_cases=0),
                exact_provider_bridge=bridge,
            )
        self.assertEqual(bridge.calls, [])

        # Other explicit bounds are not reinterpreted as Direct case limits.
        result = run_direct_input(
            json.dumps(payload),
            bounds=_bounds(
                max_cases=1,
                max_submissions=0,
                max_hypotheses=0,
                max_browser_rows=0,
            ),
            exact_provider_bridge=bridge,
        )
        self.assertFalse(result.blocked)


if __name__ == "__main__":
    unittest.main()
