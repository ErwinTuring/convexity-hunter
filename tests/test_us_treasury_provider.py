"""Synthetic offline tests for the bounded U.S. Treasury provider."""

import dataclasses
import datetime
import decimal
import builtins
import hashlib
import importlib
import pathlib
import sys
import urllib.error
import urllib.request
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter  # noqa: E402
from convexity_hunter.market_data import (  # noqa: E402
    DataOrigin,
    NormalizationQualityFlag,
    RateCurvePointObservation,
    SourceQualityFlag,
)
from convexity_hunter.providers import us_treasury  # noqa: E402


class SyntheticResponse:
    def __init__(self, body, *, status=200, final_url=None, read_error=None):
        self.body = body
        self.status = status
        self.final_url = final_url
        self.read_error = read_error
        self.read_sizes = []
        self.closed = False

    def read(self, size=-1):
        self.read_sizes.append(size)
        if self.read_error is not None:
            raise self.read_error
        return self.body

    def geturl(self):
        return self.final_url

    def close(self):
        self.closed = True


class UsTreasuryProviderTests(unittest.TestCase):
    EFFECTIVE_DATE = datetime.date(2030, 1, 2)
    EFFECTIVE_DATE_TEXT = "01/02/2030"
    REQUEST_URI = (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        "daily-treasury-rates.csv/2030/all"
        "?_format=csv&field_tdr_date_value=2030&page=&type=daily_treasury_yield_curve"
    )
    HEADER = (
        "Date,1 Mo,1.5 Month,2 Mo,3 Mo,4 Mo,6 Mo,Extra Provider Column\n"
    )
    RATES = "3.79,3.805,-0.25,4.01,4.125,4.50"
    BODY = (
        HEADER
        + "12/31/2029,not-a-rate,not-a-rate,not-a-rate,not-a-rate,not-a-rate,not-a-rate,ignored\n"
        + EFFECTIVE_DATE_TEXT
        + ","
        + RATES
        + ",ignored\n"
    ).encode("utf-8")

    def retrieve(self, body=None, *, effective_date=None, response=None):
        response = response or SyntheticResponse(self.BODY if body is None else body)
        selected_date = (
            self.EFFECTIVE_DATE if effective_date is None else effective_date
        )
        retrieved_at = datetime.datetime.combine(
            selected_date + datetime.timedelta(days=1),
            datetime.time(16, 0),
            tzinfo=datetime.timezone.utc,
        )
        normalized_at = retrieved_at + datetime.timedelta(seconds=1)
        with mock.patch.object(
            us_treasury,
            "_urlopen",
            return_value=response,
        ) as opener, mock.patch.object(
            us_treasury,
            "_utc_now",
            side_effect=(retrieved_at, normalized_at),
        ):
            result = us_treasury.retrieve_us_treasury_daily_par_yield_curve(
                effective_date=selected_date,
            )
        return result, response, opener

    def test_exact_request_is_one_get_with_bounded_timeout_and_user_agent(self):
        result, response, opener = self.retrieve()
        self.assertEqual(len(result), 6)
        opener.assert_called_once()
        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, self.REQUEST_URI)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.get_header("User-agent"), "ConvexityHunter/0.1")
        self.assertEqual(opener.call_args.kwargs, {"timeout": 10.0})
        self.assertEqual(response.read_sizes, [1024 * 1024 + 1])
        self.assertTrue(response.closed)

    def test_exact_date_selection_ignores_unrelated_malformed_values(self):
        result, _, _ = self.retrieve()
        self.assertEqual(
            tuple(point.tenor_days for point in result),
            (30, 45, 60, 90, 120, 180),
        )
        self.assertEqual(
            tuple(point.annualized_rate for point in result),
            (
                decimal.Decimal("0.0379"),
                decimal.Decimal("0.03805"),
                decimal.Decimal("-0.0025"),
                decimal.Decimal("0.0401"),
                decimal.Decimal("0.04125"),
                decimal.Decimal("0.0450"),
            ),
        )

    def test_bom_and_provider_column_order_are_supported(self):
        body = (
            "\ufeff6 Mo,Date,4 Mo,3 Mo,2 Mo,1.5 Month,1 Mo\n"
            "4.50,01/02/2030,4.125,4.01,-0.25,3.805,3.79\n"
        ).encode("utf-8")
        result, _, _ = self.retrieve(body)
        self.assertEqual(tuple(point.tenor_days for point in result), (30, 45, 60, 90, 120, 180))
        self.assertEqual(result[2].annualized_rate, decimal.Decimal("-0.0025"))

    def test_est_and_edt_assigned_observation_times(self):
        jan, _, _ = self.retrieve()
        july_date = datetime.date(2030, 7, 1)
        july_body = self.BODY.replace(b"01/02/2030", b"07/01/2030")
        july, _, _ = self.retrieve(july_body, effective_date=july_date)
        self.assertEqual(
            jan[0].metadata.effective_observed_at,
            datetime.datetime(2030, 1, 2, 20, 30, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(
            july[0].metadata.effective_observed_at,
            datetime.datetime(2030, 7, 1, 19, 30, tzinfo=datetime.timezone.utc),
        )
        self.assertEqual(
            jan[0].metadata.quality_flags,
            (
                NormalizationQualityFlag.UNIT_CONVERTED,
                NormalizationQualityFlag.TIMESTAMP_ASSIGNED,
            ),
        )

    def test_provenance_digest_identity_and_normalization_are_literal(self):
        result, _, _ = self.retrieve()
        digest = hashlib.sha256(self.BODY).hexdigest()
        for point, label in zip(result, ("1 Mo", "1.5 Month", "2 Mo", "3 Mo", "4 Mo", "6 Mo")):
            self.assertIs(type(point), RateCurvePointObservation)
            self.assertEqual(point.curve_id, "USD-US-TREASURY-DAILY-PAR-YIELD")
            self.assertEqual(point.currency, "USD")
            self.assertEqual(point.compounding_convention, "Bond-equivalent yield; simple annualized with semiannual interest convention")
            self.assertEqual(point.day_count_convention, "Actual days; 365- or 366-day year")
            self.assertEqual(point.effective_date, self.EFFECTIVE_DATE)
            self.assertEqual(point.metadata.record_origin, DataOrigin.PROVIDER_CALCULATED)
            self.assertEqual(point.metadata.normalization_version, "us-treasury-daily-par-yield-v0.1")
            self.assertIn("Decimal('100')", point.metadata.normalization_methodology)
            self.assertIn("30/45/60/90/120/180", point.metadata.normalization_methodology)
            self.assertIn("bond-equivalent par-yield", point.metadata.normalization_methodology)
            source = point.metadata.source_references[0]
            self.assertEqual(source.provider_name, "U.S. Department of the Treasury")
            self.assertEqual(source.dataset_name, "Daily Treasury Par Yield Curve Rates")
            self.assertEqual(source.source_uri, self.REQUEST_URI)
            self.assertEqual(source.provider_record_id, "2030-01-02:" + label)
            self.assertEqual(source.payload_sha256, digest)
            self.assertEqual(source.origin, DataOrigin.PROVIDER_CALCULATED)
            self.assertEqual(source.provider_timezone, "America/New_York")
            self.assertEqual(
                source.quality_flags,
                (SourceQualityFlag.INDICATIVE, SourceQualityFlag.NON_FIRM),
            )
            self.assertIn("not an exact trade", source.timestamp_methodology)
            self.assertIn(digest, source.source_id)
            self.assertIn("2030-01-02", source.source_id)
            self.assertIn(label, source.source_id)
            self.assertIn(digest, point.metadata.record_id)

    def test_result_is_tuple_and_core_records_are_frozen(self):
        result, _, _ = self.retrieve()
        self.assertIs(type(result), tuple)
        self.assertEqual(len(result), 6)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result[0].tenor_days = 31

    def test_missing_duplicate_and_incomplete_selected_rows_fail_closed(self):
        missing = self.BODY.replace(b"01/02/2030", b"01/03/2030")
        with self.assertRaisesRegex(ValueError, "effective-date row"):
            self.retrieve(missing)

        duplicate = self.BODY + (
            self.EFFECTIVE_DATE_TEXT + "," + self.RATES + ",ignored\n"
        ).encode("utf-8")
        with self.assertRaisesRegex(ValueError, "effective-date row"):
            self.retrieve(duplicate)

        incomplete = (
            self.HEADER + self.EFFECTIVE_DATE_TEXT + ",3.79,3.805,-0.25,4.01\n"
        ).encode("utf-8")
        with self.assertRaisesRegex(ValueError, "invalid rate values"):
            self.retrieve(incomplete)

    def test_invalid_header_encoding_and_body_size_are_sanitized(self):
        cases = (
            (b"Date,1 Mo,1 Mo,2 Mo,3 Mo,4 Mo,6 Mo\n", "response is invalid"),
            (b"\xff\xfe", "response is invalid"),
            (b"x" * (1024 * 1024 + 1), "exceeds 1 MiB"),
        )
        for body, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, message):
                    self.retrieve(body)

    def test_each_invalid_rate_token_is_the_sole_invalid_tenor(self):
        valid_rates = ["3.79", "3.805", "-0.25", "4.01", "4.125", "4.50"]
        invalid_cases = (
            ("1 Mo", "N/A"),
            ("1.5 Month", "Infinity"),
            ("2 Mo", "NaN"),
            ("3 Mo", "True"),
            ("4 Mo", ""),
        )
        labels = ("1 Mo", "1.5 Month", "2 Mo", "3 Mo", "4 Mo", "6 Mo")
        for label, invalid_token in invalid_cases:
            with self.subTest(label=label, invalid_token=invalid_token):
                rates = list(valid_rates)
                rates[labels.index(label)] = invalid_token
                body = (
                    self.HEADER
                    + self.EFFECTIVE_DATE_TEXT
                    + ","
                    + ",".join(rates)
                    + ",ignored\n"
                ).encode("utf-8")
                with self.assertRaisesRegex(ValueError, "invalid rate values"):
                    self.retrieve(body)

    def test_decimal_tuple_conversion_ignores_ambient_precision_and_exponents(self):
        body = (
            self.HEADER
            + self.EFFECTIVE_DATE_TEXT
            + ",1E-1000000,3.805,-0.25,4.01,4.125,4.50,ignored\n"
        ).encode("utf-8")
        with decimal.localcontext() as context:
            context.prec = 1
            context.Emin = -2
            context.Emax = 2
            result, _, _ = self.retrieve(body)
        self.assertEqual(result[0].annualized_rate, decimal.Decimal("1E-1000002"))
        self.assertEqual(str(result[0].annualized_rate), "1E-1000002")

    def test_transport_and_csv_failures_do_not_leak_secrets(self):
        secret = "synthetic-provider-secret"
        response = SyntheticResponse(self.BODY, read_error=RuntimeError(secret))
        with self.assertRaisesRegex(RuntimeError, "retrieval failed") as raised:
            self.retrieve(response=response)
        self.assertNotIn(secret, str(raised.exception))

        response = SyntheticResponse(self.BODY, final_url="https://attacker.invalid")
        with self.assertRaisesRegex(RuntimeError, "retrieval failed") as raised:
            self.retrieve(response=response)
        self.assertNotIn("attacker.invalid", str(raised.exception))

        response = SyntheticResponse(self.BODY, status=500)
        with self.assertRaisesRegex(RuntimeError, "retrieval failed"):
            self.retrieve(response=response)

    def test_local_redirect_handler_fails_before_a_second_request(self):
        request = urllib.request.Request(
            "https://home.treasury.gov/start",
            method="GET",
        )
        response = mock.Mock()
        parent = mock.Mock()
        handler = us_treasury._NoRedirectHandler()
        handler.parent = parent
        with self.assertRaises(urllib.error.HTTPError) as raised:
            handler.redirect_request(
                request,
                response,
                302,
                "Found",
                {"Location": "https://home.treasury.gov/final"},
                "https://home.treasury.gov/final",
            )
        self.assertEqual(raised.exception.code, 302)
        self.assertEqual(raised.exception.url, request.full_url)
        self.assertEqual(raised.exception.reason, "redirects are disabled")
        parent.open.assert_not_called()

        opener = mock.Mock()
        with mock.patch.object(
            us_treasury._urllib_request,
            "build_opener",
            return_value=opener,
        ) as build_opener:
            self.assertIs(
                us_treasury._urlopen(request, timeout=1.0),
                opener.open.return_value,
            )
        build_opener.assert_called_once()
        self.assertIsInstance(
            build_opener.call_args.args[0], us_treasury._NoRedirectHandler
        )
        opener.open.assert_called_once_with(request, timeout=1.0)

        redirect_error = urllib.error.HTTPError(
            request.full_url,
            302,
            "redirects are disabled",
            {},
            response,
        )
        with mock.patch.object(
            us_treasury,
            "_urlopen",
            side_effect=redirect_error,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "^U\\.S\\. Treasury curve retrieval failed$",
            ):
                us_treasury._retrieve_body(request.full_url)

    def test_exact_date_validation_precedes_request(self):
        with mock.patch.object(us_treasury, "_urlopen") as opener:
            with self.assertRaises(TypeError):
                us_treasury.retrieve_us_treasury_daily_par_yield_curve(
                    effective_date=datetime.datetime(2030, 1, 2)
                )
            opener.assert_not_called()

    def test_fresh_module_execution_has_no_network_or_credential_side_effect(self):
        module_path = ROOT / "src" / "convexity_hunter" / "providers" / "us_treasury.py"
        module_name = "_fresh_us_treasury_side_effect_test"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        imported_names = []
        real_import = builtins.__import__

        def tracking_import(name, globals=None, locals=None, fromlist=(), level=0):
            imported_names.append(name)
            return real_import(name, globals, locals, fromlist, level)

        with mock.patch.object(
            urllib.request,
            "urlopen",
            side_effect=AssertionError("network access during import"),
        ), mock.patch.object(
            builtins,
            "__import__",
            side_effect=tracking_import,
        ):
            spec.loader.exec_module(module)

        self.assertEqual(module.__all__, ("retrieve_us_treasury_daily_par_yield_curve",))
        self.assertEqual(
            tuple(name for name in vars(module) if not name.startswith("_")),
            module.__all__,
        )
        self.assertFalse(hasattr(convexity_hunter, module.__all__[0]))
        self.assertFalse(
            any(
                name.split(".", 1)[0]
                in {"boto", "dotenv", "keyring", "requests", "tigeropen"}
                for name in imported_names
            )
        )


if __name__ == "__main__":
    unittest.main()
