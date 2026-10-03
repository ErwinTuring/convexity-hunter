import copy
import dataclasses
import datetime
import decimal
import json
import unittest
from fractions import Fraction

from convexity_hunter import core_research as core
from convexity_hunter import host_core_snapshot as snapshot_codec
from convexity_hunter.market_data import (
    DataOrigin,
    SourceQualityFlag,
    SourceReference,
)
from convexity_hunter.market_data_transformations import (
    VolatilityEnvironmentTransformationResult,
)


D = decimal.Decimal
UTC = datetime.timezone.utc


def make_source():
    observed = datetime.datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
    return SourceReference(
        source_id="source-1",
        provider_name="synthetic-provider",
        dataset_name="option-quotes",
        provider_record_id="record-1",
        provider_request_id="request-1",
        source_symbol="XYZ",
        source_uri="https://example.test/quotes/1",
        observed_at=observed,
        retrieved_at=observed + datetime.timedelta(seconds=3),
        provider_timezone="America/New_York",
        timestamp_methodology="provider event timestamp",
        origin=DataOrigin.EXCHANGE_OBSERVED,
        is_delayed=True,
        declared_delay_seconds=60,
        payload_sha256="a" * 64,
        revision_number=1,
        provider_correction_id="correction-1",
        quality_flags=(SourceQualityFlag.DELAYED, SourceQualityFlag.CORRECTED),
    )


def make_request(*, insufficient=False, enhancements=()):
    source = make_source()
    provenance = core.CoreProvenance(source, "synthetic source basis")
    leg = core.CoreLeg(
        leg_id="call-1",
        underlying="XYZ",
        currency="USD",
        option_type=core.CoreOptionType.CALL,
        strike=D("100.00"),
        expiration=datetime.date(2027, 1, 15),
        quantity=1,
        contract_multiplier=100,
        ask_per_underlying_unit=D("0.0500"),
        ask_authority=core.CoreAskAuthority.INDICATIVE_ONLY,
        description="synthetic long call",
        provenance=provenance,
    )
    structure = core.CoreStructure((leg,), "synthetic structure", provenance)
    payoff = None
    ledger = None
    risk = None
    sensitivity = None
    if not insufficient:
        payoff = core.CorePayoffModel(
            core.CorePayoffAuthority.CONDITIONAL_STANDARD_PAYOFF,
            "standard-payoff",
            "v0.1",
            "conditional expiry payoff",
            provenance,
        )
        fee = core.CoreCostComponent(
            "fee",
            core.CoreCostComponentStatus.EXPLICIT_UPPER_BOUND,
            D("2.000"),
            "USD",
            "synthetic fee bound",
            "fee upper bound",
            provenance,
        )
        ledger = core.CoreCostLedger(
            D("8.000"), (fee,), ("fee",), "USD", "synthetic bound",
            "cost ledger", provenance,
        )
        risk = core.CoreRiskRepeatPolicy(
            D("1000"), D("0.02"), D("0.04"), 2,
            "synthetic policy", "USD", "risk policy", provenance,
        )
        point = core.CoreSensitivityPoint(
            "point-1", D("100.00"), (D("0.0600"),),
            "synthetic point", provenance,
        )
        sensitivity = core.CoreSensitivity(
            (point,), "synthetic sensitivity", provenance
        )
    return core.CoreResearchRequest(
        "case-1", structure, payoff, ledger, risk, sensitivity,
        tuple(enhancements), "synthetic request", provenance,
    )


class HostCoreSnapshotTests(unittest.TestCase):
    def test_literal_golden_tags_and_source_reference_fields(self):
        encode = snapshot_codec._encode_value
        self.assertEqual(encode(D("1.2300")), {"$decimal": "1.2300"})
        self.assertEqual(
            encode(datetime.date(2027, 1, 15)), {"$date": "2027-01-15"}
        )
        self.assertEqual(
            encode(core.CoreOptionType.CALL),
            {"$enum": "core_research.CoreOptionType", "value": "CALL"},
        )
        self.assertEqual(
            encode((D("0.0500"), datetime.date(2027, 1, 15))),
            {"$tuple": [
                {"$decimal": "0.0500"},
                {"$date": "2027-01-15"},
            ]},
        )

        source = encode(make_source())
        self.assertEqual(
            {key: source[key] for key in (
                "$type", "source_id", "provider_request_id", "observed_at",
                "origin", "quality_flags",
            )},
            {
                "$type": "market_data.SourceReference",
                "source_id": "source-1",
                "provider_request_id": "request-1",
                "observed_at": {
                    "$datetime": "2026-03-04T05:06:07+00:00",
                    "tzname": "UTC",
                    "fold": 0,
                },
                "origin": {
                    "$enum": "market_data.DataOrigin",
                    "value": "exchange_observed",
                },
                "quality_flags": {"$tuple": [
                    {"$enum": "market_data.SourceQualityFlag", "value": "delayed"},
                    {"$enum": "market_data.SourceQualityFlag", "value": "corrected"},
                ]},
            },
        )

    def test_complete_result_round_trip_retains_typed_request_and_provenance(self):
        request = make_request()
        result = core.evaluate_core_research(request)
        encoded = snapshot_codec.encode_core_result(result)

        self.assertEqual(encoded["version"], "host-core-result-v0.1")
        self.assertEqual(set(encoded), {"version", "request", "result"})
        self.assertNotIn("request", encoded["result"])
        json.dumps(encoded)

        decoded = snapshot_codec.decode_core_result(encoded)
        self.assertEqual(decoded, result)
        self.assertIs(
            decoded.reviewed_enhancements,
            decoded.request.reviewed_enhancements,
        )
        source = request.provenance.source_reference
        restored = decoded.request.provenance.source_reference
        self.assertEqual(restored, source)
        for field in source.__dataclass_fields__:
            self.assertEqual(getattr(restored, field), getattr(source, field))

    def test_data_insufficient_and_empty_enhancements_round_trip(self):
        result = core.evaluate_core_research(make_request(insufficient=True))
        self.assertEqual(result.disposition, core.CoreDisposition.DATA_INSUFFICIENT_CORE)
        restored = snapshot_codec.decode_core_result(
            snapshot_codec.encode_core_result(result)
        )
        self.assertEqual(restored, result)
        self.assertEqual(restored.request.reviewed_enhancements, ())
        self.assertIs(restored.reviewed_enhancements,
                      restored.request.reviewed_enhancements)

    def test_exact_scalar_and_container_values_round_trip(self):
        aware = datetime.datetime(
            2024, 11, 3, 1, 30, 0, 123456,
            tzinfo=datetime.timezone(datetime.timedelta(hours=-4), "EDT"),
            fold=1,
        )
        value = (
            D("-0.0012300"), Fraction(-14, 35),
            datetime.date(2020, 2, 29), aware,
        )
        restored = snapshot_codec._decode_value(snapshot_codec._encode_value(value))
        self.assertEqual(restored, value)
        self.assertEqual(restored[0].as_tuple(), value[0].as_tuple())
        self.assertEqual(restored[1].numerator, value[1].numerator)
        self.assertEqual(restored[1].denominator, value[1].denominator)
        self.assertEqual(restored[3].utcoffset(), aware.utcoffset())
        self.assertEqual(restored[3].tzname(), aware.tzname())
        self.assertEqual(restored[3].fold, aware.fold)

    def test_rejects_nonfinite_naive_boolean_numeric_and_unsupported_values(self):
        with self.assertRaisesRegex(ValueError, "non-finite"):
            snapshot_codec._encode_value(D("Infinity"))
        with self.assertRaisesRegex(ValueError, "finite and canonical"):
            snapshot_codec._decode_value({"$decimal": "NaN"})
        with self.assertRaisesRegex(ValueError, "naive"):
            snapshot_codec._encode_value(datetime.datetime(2026, 1, 1))
        with self.assertRaisesRegex(TypeError, "integers"):
            snapshot_codec._decode_value({"$fraction": [True, 1]})
        with self.assertRaisesRegex(TypeError, "unsupported"):
            snapshot_codec._encode_value(1.0)
        with self.assertRaisesRegex(TypeError, "unsupported"):
            snapshot_codec._encode_value(object())

    def test_reviewed_transformation_artifacts_fail_explicitly(self):
        artifact = object.__new__(VolatilityEnvironmentTransformationResult)
        with self.assertRaisesRegex(TypeError, "artifacts are unsupported"):
            snapshot_codec._encode_value(artifact)

    def test_rejects_unknown_version_fields_and_missing_fields(self):
        encoded = snapshot_codec.encode_core_result(
            core.evaluate_core_research(make_request())
        )
        changed = copy.deepcopy(encoded)
        changed["version"] = "host-core-result-v0.2"
        with self.assertRaisesRegex(ValueError, "version"):
            snapshot_codec.decode_core_result(changed)

        changed = copy.deepcopy(encoded)
        changed["unexpected"] = None
        with self.assertRaisesRegex(ValueError, "unknown or missing"):
            snapshot_codec.decode_core_result(changed)

        changed = copy.deepcopy(encoded)
        del changed["request"]
        with self.assertRaisesRegex(ValueError, "unknown or missing"):
            snapshot_codec.decode_core_result(changed)

        changed = copy.deepcopy(encoded)
        del changed["request"]["description"]
        with self.assertRaisesRegex(ValueError, "unknown or missing"):
            snapshot_codec.decode_core_result(changed)

        changed = copy.deepcopy(encoded)
        del changed["result"]["budget_stress"]
        with self.assertRaisesRegex(ValueError, "unknown or missing"):
            snapshot_codec.decode_core_result(changed)

    def test_rejects_unknown_types_and_tampered_derived_outputs(self):
        encoded = snapshot_codec.encode_core_result(
            core.evaluate_core_research(make_request())
        )
        changed = copy.deepcopy(encoded)
        changed["request"]["structure"]["$type"] = "untrusted.PluginType"
        with self.assertRaisesRegex(ValueError, "unknown Core snapshot type"):
            snapshot_codec.decode_core_result(changed)

        changed = copy.deepcopy(encoded)
        changed["result"]["geometry"]["ask_basis_per_underlying_unit"] = {
            "$decimal": "99"
        }
        with self.assertRaisesRegex(ValueError, "deterministic evaluation"):
            snapshot_codec.decode_core_result(changed)

        changed = copy.deepcopy(encoded)
        changed["result"]["disposition"]["value"] = "REJECT"
        with self.assertRaisesRegex(ValueError, "deterministic evaluation"):
            snapshot_codec.decode_core_result(changed)

        changed = copy.deepcopy(encoded)
        changed["result"]["reviewed_enhancements"] = {"$tuple": [None]}
        with self.assertRaisesRegex(ValueError, "enhancements do not match"):
            snapshot_codec.decode_core_result(changed)

    def test_boolean_cannot_impersonate_integer_in_encode_or_decode(self):
        result = core.evaluate_core_research(make_request())
        encoded = snapshot_codec.encode_core_result(result)
        changed = copy.deepcopy(encoded)
        changed["result"]["geometry"]["hurdles"]["$tuple"][0][
            "gross_value_multiple"
        ] = True
        with self.assertRaisesRegex(ValueError, "deterministic evaluation"):
            snapshot_codec.decode_core_result(changed)

        hurdles = list(result.geometry.hurdles)
        hurdles[0] = dataclasses.replace(hurdles[0], gross_value_multiple=True)
        tampered_result = dataclasses.replace(
            result,
            geometry=dataclasses.replace(result.geometry, hurdles=tuple(hurdles)),
        )
        with self.assertRaisesRegex(ValueError, "deterministic evaluation"):
            snapshot_codec.encode_core_result(tampered_result)


if __name__ == "__main__":
    unittest.main()
