"""Synthetic tests for the bounded Tiger provider boundary."""

import dataclasses
import datetime
import decimal
import hashlib
import inspect
import logging
import importlib.util
import os
import pathlib
import stat
import sys
import tempfile
import unittest
import zoneinfo
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
from convexity_hunter.market_data import (
    DataOrigin,
    NormalizationQualityFlag,
    OptionContractReference,
    UnderlyingDailyBarObservation,
    UnderlyingKey,
    UnderlyingSecurityType,
)
from convexity_hunter.providers import tiger


class TigerProviderTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.base = pathlib.Path(self.temporary_directory.name)
        self.repository = self.base / "repository"
        self.repository.mkdir()
        (self.repository / ".git").mkdir()
        self.home = self.base / "home"
        self.home.mkdir()
        self.environment = mock.patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.root_patch = mock.patch.object(
            tiger, "_repository_root", return_value=self.repository.resolve()
        )
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.home_patch = mock.patch.object(
            tiger, "_home_directory", return_value=self.home
        )
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)

    def private_file(self, path, text="synthetic-provider-config"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        return path

    def default_file(self):
        return self.private_file(
            self.home / ".config/tigeropen/tiger_openapi_config.properties"
        )


class PublicBoundaryTests(TigerProviderTestCase):
    def test_exact_fourteen_name_api_and_no_root_or_package_reexport(self):
        self.assertEqual(
            tiger.__all__,
            (
                "resolve_tiger_config_path",
                "initialize_tiger_quote_client",
                "TigerExactOptionContractVerification",
                "TigerExactOptionQuoteEvidence",
                "verify_tiger_monthly_option_contract",
                "retrieve_tiger_exact_option_quote_evidence",
                "retrieve_tiger_underlying_daily_bars",
                "TigerHistoricalDividendEvidence",
                "retrieve_tiger_historical_dividend_evidence",
                "TigerHistoricalOptionBarEvidence",
                "retrieve_tiger_historical_option_bar_evidence",
                "TigerExactOptionAnalyticsActivityEvidence",
                "retrieve_tiger_exact_option_analytics_activity_evidence",
                "compose_tiger_spy_option_product_terms_reference",
            ),
        )
        self.assertEqual(
            tuple(name for name in vars(tiger) if not name.startswith("_")),
            tiger.__all__,
        )
        for name in tiger.__all__:
            self.assertFalse(hasattr(convexity_hunter, name))
            self.assertFalse(hasattr(sys.modules["convexity_hunter.providers"], name))

    def test_module_import_has_no_tiger_sdk_or_credential_side_effect(self):
        self.assertNotIn("tigeropen.quote.quote_client", tiger.__dict__)
        self.assertNotIn("TigerOpenClientConfig", tiger.__dict__)
        self.assertNotIn("QuoteClient", tiger.__dict__)


class ResolutionTests(TigerProviderTestCase):
    def test_explicit_path_precedes_default_and_returns_canonical_target(self):
        self.default_file()
        target = self.private_file(self.base / "external" / "provider.properties")
        alias = self.base / "provider-alias.properties"
        alias.symlink_to(target)
        os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = str(alias)
        self.assertEqual(tiger.resolve_tiger_config_path(), target.resolve())

    def test_default_path_is_used_only_without_override(self):
        expected = self.default_file()
        self.assertEqual(tiger.resolve_tiger_config_path(), expected.resolve())

    def test_tilde_override_is_expanded(self):
        expected = self.private_file(self.home / "provider.properties")
        os.environ["HOME"] = str(self.home)
        os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = "~/provider.properties"
        self.assertEqual(tiger.resolve_tiger_config_path(), expected.resolve())

    def test_invalid_explicit_override_never_falls_back(self):
        self.default_file()
        for value in ("", "   ", "relative.properties", "file:///tmp/x"):
            with self.subTest(value=repr(value)):
                os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = value
                with self.assertRaisesRegex(
                    ValueError, "configuration path is invalid"
                ) as raised:
                    tiger.resolve_tiger_config_path()
                if value:
                    self.assertNotIn(value, str(raised.exception))

    def test_nul_path_is_rejected_by_path_parser_without_echo(self):
        value = "synthetic-secret\0path"
        with self.assertRaisesRegex(ValueError, "configuration path is invalid") as raised:
            tiger._canonical_path(value)
        self.assertNotIn("synthetic-secret", str(raised.exception))

    def test_missing_path_has_safe_setup_instructions(self):
        with self.assertRaises(FileNotFoundError) as raised:
            tiger.resolve_tiger_config_path()
        message = str(raised.exception)
        self.assertIn("tiger_openapi_config.properties", message)
        self.assertIn("CONVEXITY_HUNTER_TIGER_CONFIG", message)
        self.assertNotIn(str(self.home), message)

    def test_directory_is_rejected(self):
        directory = self.base / "external-directory"
        directory.mkdir()
        os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = str(directory)
        with self.assertRaisesRegex(ValueError, "must be a regular file"):
            tiger.resolve_tiger_config_path()

    def test_repository_root_descendant_and_symlink_target_are_rejected(self):
        targets = (
            self.private_file(self.repository / "root.properties"),
            self.private_file(self.repository / "nested" / "nested.properties"),
        )
        alias = self.base / "inside-alias.properties"
        alias.symlink_to(targets[1])
        for target in (*targets, alias):
            with self.subTest(target=target.name):
                os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = str(target)
                with self.assertRaisesRegex(ValueError, "outside the repository"):
                    tiger.resolve_tiger_config_path()

    def test_common_path_prefix_outside_repository_is_accepted(self):
        target = self.private_file(
            self.base / "repository-neighbor" / "provider.properties"
        )
        os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = str(target)
        self.assertEqual(tiger.resolve_tiger_config_path(), target.resolve())

    @unittest.skipUnless(os.name == "posix", "POSIX mode contract")
    def test_posix_mode_and_owner_are_enforced(self):
        target = self.private_file(self.base / "provider.properties")
        os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = str(target)
        target.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private to the current user"):
            tiger.resolve_tiger_config_path()
        target.chmod(0o600)
        with mock.patch.object(os, "getuid", return_value=target.stat().st_uid + 1):
            with self.assertRaisesRegex(ValueError, "private to the current user"):
                tiger.resolve_tiger_config_path()

    @unittest.skipUnless(os.name == "posix", "POSIX mode contract")
    def test_owner_read_only_mode_is_accepted(self):
        target = self.private_file(self.base / "provider.properties")
        target.chmod(0o400)
        os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = str(target)
        self.assertEqual(tiger.resolve_tiger_config_path(), target.resolve())

    def test_adjacent_token_file_has_same_repository_and_mode_boundary(self):
        config = self.private_file(self.base / "external" / "provider.properties")
        token = self.private_file(config.with_name("tiger_openapi_token.properties"))
        os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = str(config)
        token.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private to the current user"):
            tiger.resolve_tiger_config_path()
        token.unlink()
        inside = self.private_file(self.repository / "token.properties")
        token.symlink_to(inside)
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            tiger.resolve_tiger_config_path()

    def test_any_tiger_sdk_environment_key_is_rejected_without_value_leak(self):
        self.default_file()
        secret = "synthetic-private-key-material"
        os.environ["TIGEROPEN_PRIVATE_KEY"] = secret
        with self.assertRaisesRegex(RuntimeError, "environment configuration") as raised:
            tiger.resolve_tiger_config_path()
        self.assertNotIn(secret, str(raised.exception))


class InitializationTests(TigerProviderTestCase):
    def setUp(self):
        super().setUp()
        self.config_path = self.private_file(self.base / "provider.properties")
        os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = str(self.config_path)

    def fake_sdk(self, *, missing_field=None, config_error=None, client_error=None):
        trace = []

        class FakeConfig:
            def __init__(self, **kwargs):
                trace.append(("config", kwargs))
                if config_error is not None:
                    raise RuntimeError(config_error)
                self.tiger_id = None if missing_field == "tiger_id" else "synthetic-id"
                self.account = None if missing_field == "account" else "synthetic-account"
                self.private_key = None if missing_field == "private_key" else "synthetic-key"
                self.token_refresh_duration = 99
                self.log_path = "synthetic-secret-log"
                self.log_level = "DEBUG"

        class FakeQuoteClient:
            def __init__(self, config, **kwargs):
                trace.append(
                    (
                        "client",
                        config.token_refresh_duration,
                        config.log_path,
                        config.log_level,
                        kwargs,
                    )
                )
                if client_error is not None:
                    raise RuntimeError(client_error)

        return FakeConfig, FakeQuoteClient, trace

    def test_exact_safe_sdk_construction_without_permission_grab(self):
        config_type, client_type, trace = self.fake_sdk()
        with mock.patch.object(
            tiger, "_load_tiger_sdk", return_value=(config_type, client_type)
        ):
            result = tiger.initialize_tiger_quote_client()
        self.assertIsInstance(result, client_type)
        self.assertEqual(
            trace[0],
            (
                "config",
                {
                    "props_path": str(self.config_path.resolve()),
                    "enable_dynamic_domain": False,
                },
            ),
        )
        self.assertEqual(trace[1][0:4], ("client", 0, None, None))
        kwargs = trace[1][4]
        self.assertIs(kwargs["is_grab_permission"], False)
        logger = kwargs["logger"]
        self.assertIsInstance(logger, logging.Logger)
        self.assertFalse(logger.propagate)
        self.assertGreater(logger.level, logging.CRITICAL)

    def test_sdk_configuration_root_logging_is_discarded(self):
        secret = "synthetic-private-key-log-material"
        config_type, client_type, _ = self.fake_sdk()
        original_init = config_type.__init__

        def logging_init(instance, **kwargs):
            logging.error(secret)
            original_init(instance, **kwargs)

        records = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        handler = CaptureHandler()
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(handler)
        self.addCleanup(root_logger.removeHandler, handler)
        self.addCleanup(root_logger.setLevel, previous_level)
        with mock.patch.object(config_type, "__init__", logging_init), mock.patch.object(
            tiger, "_load_tiger_sdk", return_value=(config_type, client_type)
        ):
            tiger.initialize_tiger_quote_client()
        self.assertNotIn(secret, records)

    def test_missing_required_fields_are_sanitized_and_client_is_not_built(self):
        for field in ("tiger_id", "account", "private_key"):
            with self.subTest(field=field):
                config_type, client_type, trace = self.fake_sdk(missing_field=field)
                with mock.patch.object(
                    tiger,
                    "_load_tiger_sdk",
                    return_value=(config_type, client_type),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "client initialization failed"
                    ) as raised:
                        tiger.initialize_tiger_quote_client()
                self.assertEqual(tuple(item[0] for item in trace), ("config",))
                self.assertNotIn("synthetic", str(raised.exception))

    def test_sdk_constructor_and_client_errors_do_not_leak(self):
        for failure_at in ("config", "client"):
            with self.subTest(failure_at=failure_at):
                secret = "synthetic-secret-value"
                config_type, client_type, _ = self.fake_sdk(
                    config_error=secret if failure_at == "config" else None,
                    client_error=secret if failure_at == "client" else None,
                )
                with mock.patch.object(
                    tiger,
                    "_load_tiger_sdk",
                    return_value=(config_type, client_type),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "client initialization failed"
                    ) as raised:
                        tiger.initialize_tiger_quote_client()
                self.assertNotIn(secret, str(raised.exception))
                self.assertIsNone(raised.exception.__cause__)

    def test_sdk_unavailable_failure_is_stable(self):
        with mock.patch.object(
            tiger,
            "_load_tiger_sdk",
            side_effect=RuntimeError(
                "Tiger OpenAPI SDK is unavailable. Install convexity-hunter[tiger]."
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "SDK is unavailable"):
                tiger.initialize_tiger_quote_client()

    def test_raw_sdk_import_failure_is_sanitized(self):
        secret = "synthetic-import-secret"
        with mock.patch("builtins.__import__", side_effect=RuntimeError(secret)):
            with self.assertRaisesRegex(RuntimeError, "SDK is unavailable") as raised:
                tiger._load_tiger_sdk()
        self.assertNotIn(secret, str(raised.exception))


@unittest.skipUnless(
    importlib.util.find_spec("tigeropen") is not None,
    "optional tigeropen SDK is not installed",
)
class ActualSdkIsolationTests(TigerProviderTestCase):
    def setUp(self):
        super().setUp()
        self.config_path = self.base / "actual-sdk.properties"
        os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = str(self.config_path)

    def test_actual_sdk_initialization_uses_no_network_or_permission_grab(self):
        self.private_file(
            self.config_path,
            "\n".join(
                (
                    "tiger_id=synthetic-id",
                    "account=synthetic-account",
                    "private_key_pk1=synthetic-private-key",
                    "license=TBSG",
                )
            ),
        )
        import tigeropen.quote.quote_client as quote_client_module
        import tigeropen.tiger_open_config as config_module
        import tigeropen.tiger_open_client as client_module

        with mock.patch.object(
            config_module,
            "do_get",
            side_effect=AssertionError("network forbidden"),
        ), mock.patch.object(
            client_module,
            "do_post",
            side_effect=AssertionError("network forbidden"),
        ), mock.patch.object(
            quote_client_module.QuoteClient,
            "grab_quote_permission",
            side_effect=AssertionError("permission grab forbidden"),
        ):
            client = tiger.initialize_tiger_quote_client()
        self.assertIsInstance(client, quote_client_module.QuoteClient)

    def test_actual_sdk_parse_error_does_not_reach_root_logging(self):
        secret = "synthetic-config-secret"
        self.config_path.write_bytes(b"\xff" + secret.encode("ascii"))
        self.config_path.chmod(0o600)
        records = []

        class CaptureHandler(logging.Handler):
            def emit(self, record):
                records.append(record.getMessage())

        handler = CaptureHandler()
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(handler)
        self.addCleanup(root_logger.removeHandler, handler)
        self.addCleanup(root_logger.setLevel, previous_level)
        with self.assertRaisesRegex(RuntimeError, "client initialization failed"):
            tiger.initialize_tiger_quote_client()
        self.assertFalse(any(secret in message for message in records))


class ExceptionalPathTests(TigerProviderTestCase):
    def test_resolve_failure_is_sanitized_for_adjacent_provider_file(self):
        secret = "synthetic-resolve-secret"
        with mock.patch.object(pathlib.Path, "resolve", side_effect=OSError(secret)):
            with self.assertRaisesRegex(ValueError, "path is invalid") as raised:
                tiger._validate_external_file(
                    self.base / "token.properties", missing_allowed=True
                )
        self.assertNotIn(secret, str(raised.exception))

    def test_stat_failure_is_not_treated_as_missing(self):
        secret = "synthetic-stat-secret"
        target = self.base / "token.properties"
        with mock.patch.object(pathlib.Path, "stat", side_effect=PermissionError(secret)):
            with self.assertRaisesRegex(ValueError, "path is invalid") as raised:
                tiger._validate_external_file(target, missing_allowed=True)
        self.assertNotIn(secret, str(raised.exception))

    def test_failure_precedence_is_environment_then_repository_then_missing(self):
        inside_missing = self.repository / "missing.properties"
        os.environ["CONVEXITY_HUNTER_TIGER_CONFIG"] = str(inside_missing)
        os.environ["TIGEROPEN_ACCOUNT"] = "synthetic-secret-account"
        with self.assertRaisesRegex(RuntimeError, "environment configuration"):
            tiger.resolve_tiger_config_path()
        del os.environ["TIGEROPEN_ACCOUNT"]
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            tiger.resolve_tiger_config_path()


class SyntheticTable:
    def __init__(self, records):
        self.records = records

    def to_dict(self, orientation):
        if orientation != "records":
            raise AssertionError("unexpected orientation")
        return self.records


class SyntheticQuoteClient:
    def __init__(
        self,
        expiration_rows=None,
        chain_rows=None,
        permissions=None,
        nr_bar_rows=None,
        br_bar_rows=None,
    ):
        self.expiration_rows = (
            [
                {
                    "symbol": "SPY",
                    "date": "2030-03-15",
                    "timestamp": 1899781200000,
                    "period_tag": "m",
                }
            ]
            if expiration_rows is None
            else expiration_rows
        )
        self.chain_rows = (
            [
                {
                    "identifier": "SPY   300315C00500000",
                    "symbol": "SPY",
                    "expiry": 1899781200000,
                    "strike": 500.0,
                    "put_call": "CALL",
                    "multiplier": 100,
                    "bid_price": 10.25,
                    "ask_price": 10.35,
                    "bid_size": 12.0,
                    "ask_size": 14.0,
                    "volume": 123,
                    "open_interest": 456,
                    "last_timestamp": 1893589200000,
                    "implied_vol": 0.25,
                    "delta": 0.55,
                    "gamma": 0.012,
                    "theta": -0.08,
                    "vega": 0.15,
                    "rho": 0.10,
                }
            ]
            if chain_rows is None
            else chain_rows
        )
        self.permissions = (
            [{"name": "usOptionQuote", "expire_at": -1}]
            if permissions is None
            else permissions
        )
        bar_time = int(
            datetime.datetime(
                2030,
                1,
                2,
                tzinfo=zoneinfo.ZoneInfo("America/New_York"),
            ).timestamp()
            * 1000
        )
        default_bar = {
            "symbol": "SPY",
            "time": bar_time,
            "open": 500.0,
            "high": 505.0,
            "low": 498.0,
            "close": 503.0,
            "volume": 1000000,
        }
        self.nr_bar_rows = [default_bar] if nr_bar_rows is None else nr_bar_rows
        self.br_bar_rows = (
            [dict(default_bar, open=495.0, high=500.0, low=493.0, close=498.0)]
            if br_bar_rows is None
            else br_bar_rows
        )
        self.calls = []

    def get_quote_permission(self):
        self.calls.append(("permission",))
        return self.permissions

    def get_option_expirations(self, symbol, **kwargs):
        self.calls.append(("expirations", symbol, kwargs))
        return SyntheticTable(self.expiration_rows)

    def get_option_chain(self, symbol, expiry, **kwargs):
        self.calls.append(("chain", symbol, expiry, kwargs))
        return SyntheticTable(self.chain_rows)

    def get_bars_by_page(self, **kwargs):
        self.calls.append(("bars", kwargs))
        rows = self.nr_bar_rows if kwargs["right"] == "nr" else self.br_bar_rows
        return SyntheticTable(rows)


class SyntheticDividendQuoteClient:
    def __init__(self, rows=None):
        if rows is None:
            rows = [
                {
                    "symbol": "SPY",
                    "action_type": "DIVIDEND",
                    "amount": "1.2300",
                    "currency": "USD",
                    "announced_date": "2030-01-01",
                    "execute_date": "2030-01-15",
                    "record_date": "2030-01-20",
                    "pay_date": "2030-01-25",
                    "market": "US",
                    "exchange": "NASDAQ",
                },
                {
                    "symbol": "SPY",
                    "action_type": "DIVIDEND",
                    "amount": decimal.Decimal("0.500"),
                    "currency": "USD",
                    "announced_date": None,
                    "execute_date": "2030-01-10",
                    "record_date": "2030-01-15",
                    "pay_date": None,
                    "market": "US",
                    "exchange": "NYSE",
                },
            ]
        self.response = SyntheticTable(rows)
        self.calls = []

    def get_corporate_dividend(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


_DEFAULT_OPTION_BAR_RESPONSE = object()


class SyntheticOptionBarQuoteClient:
    def __init__(self, response=_DEFAULT_OPTION_BAR_RESPONSE):
        bar_time = int(
            datetime.datetime(
                2030,
                1,
                2,
                tzinfo=zoneinfo.ZoneInfo("America/New_York"),
            ).timestamp()
            * 1000
        )
        default = [
            {
                "identifier": "SPY   300315C00500000",
                "symbol": "SPY",
                "expiry": 1899781200000,
                "put_call": "CALL",
                "strike": 500.0,
                "time": bar_time,
                "open": 10.1,
                "high": 10.8,
                "low": 9.9,
                "close": 10.5,
                "volume": 123,
                "open_interest": 456,
            }
        ]
        self.response = (
            SyntheticTable(default)
            if response is _DEFAULT_OPTION_BAR_RESPONSE
            else response
        )
        self.calls = []

    def get_option_bars(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.response


class ExactContractVerificationTests(TigerProviderTestCase):
    def setUp(self):
        super().setUp()
        self.underlying = UnderlyingKey(
            symbol="SPY",
            listing_mic="ARCX",
            security_type=UnderlyingSecurityType.ETF,
            currency="USD",
        )
        self.expiration = datetime.date(2030, 3, 15)
        self.strike = decimal.Decimal("500")
        self.expiration_retrieved_at = datetime.datetime(
            2030, 1, 2, 15, 30, tzinfo=datetime.timezone.utc
        )
        self.chain_retrieved_at = self.expiration_retrieved_at + datetime.timedelta(
            seconds=1
        )
        self.normalized_at = self.chain_retrieved_at + datetime.timedelta(
            seconds=1
        )

    def verify(self, client=None, **overrides):
        values = {
            "underlying_key": self.underlying,
            "expiration": self.expiration,
            "option_type": "call",
            "strike": self.strike,
        }
        values.update(overrides)
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=(
                self.expiration_retrieved_at,
                self.chain_retrieved_at,
                self.normalized_at,
            ),
        ):
            return tiger.verify_tiger_monthly_option_contract(
                SyntheticQuoteClient() if client is None else client,
                **values,
            )

    def test_exact_monthly_contract_builds_provider_neutral_reference(self):
        client = SyntheticQuoteClient()
        result = self.verify(client)

        self.assertEqual(
            client.calls,
            [
                ("expirations", "SPY", {"market": "US"}),
                (
                    "chain",
                    "SPY",
                    "2030-03-15",
                    {"return_greek_value": False, "market": "US"},
                ),
            ],
        )
        self.assertEqual(result.provider_identifier, "SPY   300315C00500000")
        self.assertEqual(result.provider_period_tag, "m")
        self.assertEqual(result.provider_expiration_timestamp_ms, 1899781200000)
        self.assertIsInstance(result.contract_reference, OptionContractReference)
        key = result.contract_reference.contract_key
        self.assertIs(key.underlying_key, self.underlying)
        self.assertEqual(key.expiration, self.expiration)
        self.assertEqual(key.option_type, "call")
        self.assertEqual(key.strike, decimal.Decimal("500"))
        self.assertEqual(key.contract_multiplier, 100)
        self.assertEqual(key.currency, "USD")
        self.assertIsNone(key.deliverable_id)

        reference = result.contract_reference
        self.assertIsNone(reference.listing_date)
        self.assertIsNone(reference.last_trade_date)
        self.assertIsNone(reference.exercise_style)
        self.assertIsNone(reference.settlement_type)
        sources = {
            source.dataset_name: source
            for source in reference.metadata.source_references
        }
        self.assertEqual(set(sources), {"option_expirations", "option_chain"})
        expiration_source = sources["option_expirations"]
        self.assertEqual(expiration_source.provider_name, "Tiger OpenAPI")
        self.assertEqual(expiration_source.provider_record_id, "SPY:2030-03-15")
        self.assertEqual(expiration_source.source_symbol, "SPY")
        self.assertEqual(
            expiration_source.observed_at, self.expiration_retrieved_at
        )
        self.assertEqual(
            expiration_source.retrieved_at, self.expiration_retrieved_at
        )
        chain_source = sources["option_chain"]
        self.assertEqual(chain_source.provider_name, "Tiger OpenAPI")
        self.assertEqual(chain_source.provider_record_id, result.provider_identifier)
        self.assertEqual(chain_source.source_symbol, result.provider_identifier)
        self.assertEqual(chain_source.observed_at, self.chain_retrieved_at)
        self.assertEqual(chain_source.retrieved_at, self.chain_retrieved_at)
        self.assertEqual(reference.metadata.normalized_at, self.normalized_at)
        self.assertIn(
            "no provider contract-term observation timestamp was supplied",
            reference.metadata.normalization_methodology,
        )
        self.assertEqual(
            set(reference.metadata.quality_flags),
            {
                NormalizationQualityFlag.SYMBOL_MAPPED,
                NormalizationQualityFlag.TIMESTAMP_ASSIGNED,
                NormalizationQualityFlag.INCOMPLETE,
            },
        )

    def test_result_is_frozen_and_provenance_is_deterministic(self):
        first = self.verify()
        second = self.verify()
        self.assertEqual(first, second)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            first.provider_period_tag = "w"

    def test_adapter_captures_receipt_and_normalization_times_in_order(self):
        result = self.verify()
        metadata = result.contract_reference.metadata
        sources = {source.dataset_name: source for source in metadata.source_references}
        self.assertEqual(
            sources["option_expirations"].retrieved_at,
            self.expiration_retrieved_at,
        )
        self.assertEqual(
            sources["option_chain"].retrieved_at,
            self.chain_retrieved_at,
        )
        self.assertEqual(metadata.effective_observed_at, self.chain_retrieved_at)
        self.assertEqual(metadata.normalized_at, self.normalized_at)

    def test_weekly_or_unknown_expiration_fails_before_chain_request(self):
        for period_tag in ("w", "q", None):
            with self.subTest(period_tag=period_tag):
                client = SyntheticQuoteClient()
                client.expiration_rows[0]["period_tag"] = period_tag
                with self.assertRaisesRegex(ValueError, "classify.*monthly"):
                    self.verify(client)
                self.assertEqual(len(client.calls), 1)

    def test_expiration_match_must_be_unique(self):
        exact = SyntheticQuoteClient().expiration_rows[0]
        for rows in ([], [dict(exact), dict(exact)]):
            with self.subTest(count=len(rows)):
                client = SyntheticQuoteClient(expiration_rows=rows)
                with self.assertRaisesRegex(ValueError, "exactly one exact match"):
                    self.verify(client)
                self.assertEqual(len(client.calls), 1)

    def test_chain_match_must_be_exact_and_unique_without_substitution(self):
        exact = SyntheticQuoteClient().chain_rows[0]
        near = dict(exact, strike=501.0, identifier="SPY   300315C00501000")
        for rows in ([near], [dict(exact), dict(exact)]):
            with self.subTest(count=len(rows)):
                with self.assertRaisesRegex(
                    ValueError, "exactly one exact contract match"
                ):
                    self.verify(SyntheticQuoteClient(chain_rows=rows))

    def test_identifier_must_prove_root_date_type_and_strike(self):
        identifiers = (
            "QQQ   300315C00500000",
            "SPY   300322C00500000",
            "SPY   300315P00500000",
            "SPY   300315C00501000",
            "not-an-identifier",
        )
        for identifier in identifiers:
            with self.subTest(identifier=identifier):
                row = dict(SyntheticQuoteClient().chain_rows[0])
                row["identifier"] = identifier
                with self.assertRaisesRegex(ValueError, "identifier is inconsistent"):
                    self.verify(SyntheticQuoteClient(chain_rows=[row]))

    def test_multiplier_is_provider_supplied_and_never_defaulted(self):
        row = dict(SyntheticQuoteClient().chain_rows[0], multiplier=50)
        result = self.verify(SyntheticQuoteClient(chain_rows=[row]))
        self.assertEqual(result.contract_reference.contract_key.contract_multiplier, 50)

        for invalid in (None, True, 0, -1, 100.0):
            with self.subTest(multiplier=invalid):
                row = dict(SyntheticQuoteClient().chain_rows[0], multiplier=invalid)
                with self.assertRaisesRegex(ValueError, "multiplier is invalid"):
                    self.verify(SyntheticQuoteClient(chain_rows=[row]))

    def test_request_failures_are_sanitized(self):
        secret = "synthetic-provider-secret"
        for method, expected in (
            ("get_option_expirations", "expiration retrieval failed"),
            ("get_option_chain", "chain retrieval failed"),
        ):
            with self.subTest(method=method):
                client = SyntheticQuoteClient()
                setattr(client, method, mock.Mock(side_effect=RuntimeError(secret)))
                with self.assertRaisesRegex(RuntimeError, expected) as raised:
                    self.verify(client)
                self.assertNotIn(secret, str(raised.exception))

    def test_invalid_inputs_fail_before_network(self):
        cases = (
            {"underlying_key": object()},
            {"expiration": datetime.datetime(2030, 3, 15)},
            {"option_type": "unknown"},
            {"strike": decimal.Decimal("NaN")},
        )
        for values in cases:
            with self.subTest(values=tuple(values)):
                client = SyntheticQuoteClient()
                with self.assertRaises((TypeError, ValueError)):
                    self.verify(client, **values)
                self.assertEqual(client.calls, [])

    def test_malformed_tables_fail_without_raw_values(self):
        secret = "synthetic-payload-secret"
        client = SyntheticQuoteClient(
            expiration_rows=[{"symbol": secret}]
        )
        with self.assertRaisesRegex(ValueError, "response is invalid") as raised:
            self.verify(client)
        self.assertNotIn(secret, str(raised.exception))

        class ExplodingScalar:
            def __str__(self):
                raise RuntimeError(secret)

        row = dict(
            SyntheticQuoteClient().chain_rows[0],
            strike=ExplodingScalar(),
        )
        with self.assertRaisesRegex(ValueError, "response is invalid") as raised:
            self.verify(SyntheticQuoteClient(chain_rows=[row]))
        self.assertNotIn(secret, str(raised.exception))

    def test_quote_method_accessor_failure_is_sanitized(self):
        secret = "synthetic-client-secret"

        class ExplodingClient:
            @property
            def get_option_expirations(self):
                raise RuntimeError(secret)

        with self.assertRaisesRegex(TypeError, "must provide Tiger quote methods") as raised:
            self.verify(ExplodingClient())
        self.assertNotIn(secret, str(raised.exception))

        row = dict(SyntheticQuoteClient().chain_rows[0], strike=float("nan"))
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            self.verify(SyntheticQuoteClient(chain_rows=[row]))

        class ExplodingTable:
            @property
            def to_dict(self):
                raise RuntimeError(secret)

        client = SyntheticQuoteClient()
        client.get_option_expirations = mock.Mock(return_value=ExplodingTable())
        with self.assertRaisesRegex(ValueError, "response is invalid") as raised:
            self.verify(client)
        self.assertNotIn(secret, str(raised.exception))

    def test_direct_result_construction_rejects_contradictory_evidence(self):
        valid = self.verify()
        with self.assertRaisesRegex(ValueError, "classify.*monthly"):
            dataclasses.replace(valid, provider_period_tag="w")
        with self.assertRaisesRegex(ValueError, "identifier is inconsistent"):
            dataclasses.replace(
                valid,
                provider_identifier="SPY   300315P00500000",
            )
        source = valid.contract_reference.metadata.source_references[0]
        contradictory = dataclasses.replace(
            source,
            provider_name="Other Provider",
        )
        metadata = dataclasses.replace(
            valid.contract_reference.metadata,
            source_references=(
                contradictory,
                valid.contract_reference.metadata.source_references[1],
            ),
        )
        reference = dataclasses.replace(
            valid.contract_reference,
            metadata=metadata,
        )
        with self.assertRaisesRegex(ValueError, "identifier is inconsistent"):
            dataclasses.replace(valid, contract_reference=reference)

        forged_sources = tuple(
            dataclasses.replace(source, source_id="forged-source-id")
            if source.dataset_name == "option_expirations"
            else source
            for source in valid.contract_reference.metadata.source_references
        )
        forged_metadata = dataclasses.replace(
            valid.contract_reference.metadata,
            source_references=forged_sources,
        )
        forged_reference = dataclasses.replace(
            valid.contract_reference,
            metadata=forged_metadata,
        )
        with self.assertRaisesRegex(ValueError, "identifier is inconsistent"):
            dataclasses.replace(valid, contract_reference=forged_reference)


class TigerSpyOptionProductTermsCompositeTests(TigerProviderTestCase):
    def setUp(self):
        super().setUp()
        self.underlying = UnderlyingKey(
            symbol="SPY",
            listing_mic="ARCX",
            security_type=UnderlyingSecurityType.ETF,
            currency="USD",
        )
        self.expiration = datetime.date(2030, 3, 15)
        self.strike = decimal.Decimal("500")
        self.expiration_retrieved_at = datetime.datetime(
            2030, 1, 2, 15, 30, tzinfo=datetime.timezone.utc
        )
        self.chain_retrieved_at = self.expiration_retrieved_at + datetime.timedelta(
            seconds=1
        )
        self.normalized_at = self.chain_retrieved_at + datetime.timedelta(
            seconds=1
        )

    def verify(self, client=None, **overrides):
        values = {
            "underlying_key": self.underlying,
            "expiration": self.expiration,
            "option_type": "call",
            "strike": self.strike,
        }
        values.update(overrides)
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=(
                self.expiration_retrieved_at,
                self.chain_retrieved_at,
                self.normalized_at,
            ),
        ):
            return tiger.verify_tiger_monthly_option_contract(
                SyntheticQuoteClient() if client is None else client,
                **values,
            )

    def compose(self, verification=None, normalized_at=None):
        verification = self.verify() if verification is None else verification
        normalized_at = (
            self.normalized_at + datetime.timedelta(seconds=10)
            if normalized_at is None
            else normalized_at
        )
        return tiger.compose_tiger_spy_option_product_terms_reference(
            verification,
            normalized_at=normalized_at,
        )

    def coherently_retimestamp(self, verification):
        metadata = verification.contract_reference.metadata
        sources = {
            source.dataset_name: source
            for source in metadata.source_references
        }
        expiration_source = sources["option_expirations"]
        chain_source = sources["option_chain"]
        expiration_time = expiration_source.retrieved_at - datetime.timedelta(
            days=1
        )
        chain_time = chain_source.retrieved_at - datetime.timedelta(days=1)
        expiration_id, chain_id, record_id = tiger._provenance_ids(
            verification.provider_identifier,
            expiration_time,
            chain_time,
        )
        object.__setattr__(expiration_source, "observed_at", expiration_time)
        object.__setattr__(expiration_source, "retrieved_at", expiration_time)
        object.__setattr__(expiration_source, "source_id", expiration_id)
        object.__setattr__(chain_source, "observed_at", chain_time)
        object.__setattr__(chain_source, "retrieved_at", chain_time)
        object.__setattr__(chain_source, "source_id", chain_id)
        object.__setattr__(metadata, "record_id", record_id)
        object.__setattr__(metadata, "effective_observed_at", chain_time)

    def test_exact_composition_preserves_key_and_declares_all_metadata(self):
        verification = self.verify()
        input_reference = verification.contract_reference
        result = self.compose(verification)

        self.assertIsInstance(result, OptionContractReference)
        self.assertIs(result.contract_key, input_reference.contract_key)
        self.assertIsNone(result.listing_date)
        self.assertIsNone(result.last_trade_date)
        self.assertIsNone(result.contract_key.deliverable_id)
        self.assertEqual(result.exercise_style, "American")
        self.assertEqual(result.settlement_type, "Physical")
        self.assertIsNone(input_reference.exercise_style)
        self.assertIsNone(input_reference.settlement_type)
        self.assertEqual(
            result.metadata.normalization_version,
            "tiger-spy-option-product-terms-composite-v0.1",
        )
        self.assertIs(result.metadata.record_origin, DataOrigin.SYSTEM_COMPOSITE)
        self.assertEqual(
            result.metadata.quality_flags,
            (
                NormalizationQualityFlag.SYMBOL_MAPPED,
                NormalizationQualityFlag.COMPOSITE_SOURCE,
                NormalizationQualityFlag.TIMESTAMP_ASSIGNED,
                NormalizationQualityFlag.INCOMPLETE,
            ),
        )
        self.assertIn(
            NormalizationQualityFlag.INCOMPLETE,
            result.metadata.quality_flags,
        )
        self.assertEqual(
            result.metadata.effective_observed_at,
            self.chain_retrieved_at,
        )
        self.assertEqual(
            result.metadata.normalized_at,
            self.normalized_at + datetime.timedelta(seconds=10),
        )
        self.assertIn("Tiger OpenAPI", result.metadata.normalization_methodology)
        self.assertIn("Cboe Global Markets", result.metadata.normalization_methodology)
        self.assertIn("OCC Information Memo 26853", result.metadata.normalization_methodology)
        self.assertIn(
            "do not prove the exact contract",
            result.metadata.normalization_methodology,
        )
        self.assertIn(
            "Exact deliverable status remains unresolved",
            result.metadata.normalization_methodology,
        )
        self.assertIn("No listing date", result.metadata.normalization_methodology)

        expected_digest = hashlib.sha256(
            (
                result.metadata.normalization_version
                + "\x00"
                + input_reference.metadata.record_id
                + "\x00"
                + verification.provider_identifier
                + "\x00cboe-spy-option-terms:2026-08-10\x00"
                + "occ-osi-adjusted-symbol-convention:26853"
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(
            result.metadata.record_id,
            "tiger-spy-option-terms:" + expected_digest,
        )
        self.assertEqual(
            result.metadata.record_id,
            "tiger-spy-option-terms:"
            "cfca47f32388d18b3c412ff57928a68642603aa8c6b63dc47bb858472c0f8b10",
        )

        sources = {
            source.source_id: source
            for source in result.metadata.source_references
        }
        self.assertEqual(
            set(sources),
            {
                *(source.source_id for source in input_reference.metadata.source_references),
                "cboe-spy-option-terms:2026-08-10",
                "occ-osi-adjusted-symbol-convention:26853",
            },
        )
        self.assertIs(
            sources[
                input_reference.metadata.source_references[0].source_id
            ],
            input_reference.metadata.source_references[0],
        )
        cboe = sources["cboe-spy-option-terms:2026-08-10"]
        self.assertEqual(cboe.provider_name, "Cboe Global Markets")
        self.assertEqual(
            cboe.dataset_name,
            "S&P Index Options Product Suite Comparison",
        )
        self.assertEqual(cboe.provider_record_id, "SPDR ETF (SPY)")
        self.assertIsNone(cboe.provider_request_id)
        self.assertEqual(cboe.source_symbol, "SPY")
        self.assertEqual(
            cboe.source_uri,
            "https://www.cboe.com/tradable-products/product-comparison/",
        )
        occ = sources["occ-osi-adjusted-symbol-convention:26853"]
        self.assertEqual(occ.provider_name, "The Options Clearing Corporation")
        self.assertEqual(occ.dataset_name, "OCC Information Memos")
        self.assertEqual(occ.provider_record_id, "26853")
        self.assertIsNone(occ.provider_request_id)
        self.assertIsNone(occ.source_symbol)
        self.assertEqual(
            occ.source_uri,
            "https://infomemo.theocc.com/infomemos?number=26853",
        )
        for source in (cboe, occ):
            self.assertEqual(
                source.observed_at,
                datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc),
            )
            self.assertEqual(source.observed_at, source.retrieved_at)
            self.assertIsNone(source.provider_timezone)
            self.assertIs(source.origin, DataOrigin.PROVIDER_REFERENCE)
            self.assertFalse(source.is_delayed)
            self.assertIsNone(source.declared_delay_seconds)
            self.assertIsNone(source.payload_sha256)
            self.assertIsNone(source.revision_number)
            self.assertIsNone(source.provider_correction_id)
            self.assertEqual(source.quality_flags, ())
            self.assertIn("adapter-assigned manual verification-date timestamp", source.timestamp_methodology)
            self.assertIn("not a provider event/publication time", source.timestamp_methodology)

    def test_static_authority_time_is_used_when_tiger_sources_are_earlier(self):
        expiration_time = datetime.datetime(
            2026, 8, 9, 12, tzinfo=datetime.timezone.utc
        )
        chain_time = expiration_time + datetime.timedelta(seconds=1)
        tiger_normalized_at = chain_time + datetime.timedelta(seconds=1)
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=(expiration_time, chain_time, tiger_normalized_at),
        ):
            verification = tiger.verify_tiger_monthly_option_contract(
                SyntheticQuoteClient(),
                underlying_key=self.underlying,
                expiration=self.expiration,
                option_type="call",
                strike=self.strike,
            )
        result = self.compose(
            verification,
            normalized_at=datetime.datetime(
                2026, 8, 10, tzinfo=datetime.timezone.utc
            ),
        )
        self.assertEqual(
            result.metadata.effective_observed_at,
            datetime.datetime(2026, 8, 10, tzinfo=datetime.timezone.utc),
        )

    def test_effective_time_is_exact_max_not_chain_time(self):
        expiration_time = datetime.datetime(
            2030, 1, 2, 15, 30, 3, tzinfo=datetime.timezone.utc
        )
        chain_time = expiration_time - datetime.timedelta(seconds=2)
        tiger_normalized_at = expiration_time + datetime.timedelta(seconds=1)
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=(expiration_time, chain_time, tiger_normalized_at),
        ):
            verification = tiger.verify_tiger_monthly_option_contract(
                SyntheticQuoteClient(),
                underlying_key=self.underlying,
                expiration=self.expiration,
                option_type="call",
                strike=self.strike,
            )
        result = self.compose(
            verification,
            normalized_at=tiger_normalized_at + datetime.timedelta(seconds=1),
        )
        self.assertEqual(result.metadata.effective_observed_at, expiration_time)
        self.assertNotEqual(result.metadata.effective_observed_at, chain_time)

    def test_normalized_at_is_aware_utc_and_chronology_is_fail_closed(self):
        verification = self.verify()
        for candidate in (
            self.chain_retrieved_at - datetime.timedelta(microseconds=1),
            self.normalized_at - datetime.timedelta(microseconds=1),
            datetime.datetime(2030, 1, 2, 15, 30),
        ):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, "chronology"):
                    self.compose(verification, normalized_at=candidate)

        offset = datetime.timezone(datetime.timedelta(hours=8))
        result = self.compose(
            verification,
            normalized_at=datetime.datetime(2030, 1, 3, tzinfo=offset),
        )
        self.assertEqual(
            result.metadata.normalized_at,
            datetime.datetime(2030, 1, 2, 16, tzinfo=datetime.timezone.utc),
        )

    def test_multiplier_and_unsuffixed_root_are_independent_boundaries(self):
        row = dict(SyntheticQuoteClient().chain_rows[0], multiplier=50)
        verification = self.verify(SyntheticQuoteClient(chain_rows=[row]))
        with self.assertRaisesRegex(ValueError, "multiplier"):
            self.compose(verification)

        for identifier in (
            "SPY1  300315C00500000",
            "QQQ   300315C00500000",
        ):
            with self.subTest(identifier=identifier):
                verification = self.verify()
                object.__setattr__(verification, "provider_identifier", identifier)
                with self.assertRaises(ValueError):
                    self.compose(verification)

    def test_exact_scope_terms_provenance_and_tampering_fail_closed(self):
        scope_changes = (
            ("underlying_key", "symbol", "QQQ"),
            ("underlying_key", "listing_mic", "XNAS"),
            ("underlying_key", "security_type", UnderlyingSecurityType.EQUITY),
            ("underlying_key", "currency", "EUR"),
            ("key", "currency", "EUR"),
        )
        for target, field, value in scope_changes:
            with self.subTest(target=target, field=field):
                verification = self.verify()
                target_object = (
                    verification.contract_reference.contract_key.underlying_key
                    if target == "underlying_key"
                    else verification.contract_reference.contract_key
                )
                original_value = getattr(target_object, field)
                object.__setattr__(target_object, field, value)
                try:
                    with self.assertRaises(ValueError):
                        self.compose(verification)
                finally:
                    object.__setattr__(target_object, field, original_value)

        tamper_changes = (
            ("contract_reference", "exercise_style", "European"),
            ("contract_reference", "settlement_type", "Cash"),
            ("contract_reference", "listing_date", datetime.date(2029, 1, 1)),
            ("contract_reference", "last_trade_date", datetime.date(2030, 3, 14)),
            ("key", "deliverable_id", "SPY-shares"),
            (
                "metadata",
                "quality_flags",
                (
                    NormalizationQualityFlag.SYMBOL_MAPPED,
                    NormalizationQualityFlag.TIMESTAMP_ASSIGNED,
                ),
            ),
        )
        for target, field, value in tamper_changes:
            with self.subTest(target=target, field=field):
                verification = self.verify()
                reference = verification.contract_reference
                target_object = {
                    "contract_reference": reference,
                    "key": reference.contract_key,
                    "metadata": reference.metadata,
                }[target]
                object.__setattr__(target_object, field, value)
                with self.assertRaises(ValueError):
                    self.compose(verification)

        verification = self.verify()
        source = verification.contract_reference.metadata.source_references[0]
        object.__setattr__(source, "source_uri", "synthetic://tampered")
        with self.assertRaisesRegex(ValueError, "input"):
            self.compose(verification)

    def test_hostile_nested_source_string_subclass_is_rejected_before_reuse(self):
        class EqualString(str):
            def __eq__(self, other):
                return str(self) == other

            __hash__ = str.__hash__

        verification = self.verify()
        source = verification.contract_reference.metadata.source_references[0]
        original = source.provider_name
        hostile = EqualString(original)
        self.assertEqual(hostile, original)
        object.__setattr__(source, "provider_name", hostile)
        self.assertEqual(
            verification._creation_integrity_fingerprint,
            tiger._tiger_verification_integrity_fingerprint(verification),
        )
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.compose(verification)

    def test_creation_integrity_rejects_coherent_nested_mutation(self):
        verification = self.verify()
        original_fingerprint = verification._creation_integrity_fingerprint
        self.coherently_retimestamp(verification)

        self.assertNotEqual(
            original_fingerprint,
            tiger._tiger_verification_integrity_fingerprint(verification),
        )
        resealed = tiger.TigerExactOptionContractVerification(
            verification.provider_identifier,
            verification.provider_period_tag,
            verification.provider_expiration_timestamp_ms,
            verification.contract_reference,
        )
        self.assertNotEqual(
            resealed._creation_integrity_fingerprint,
            original_fingerprint,
        )
        with self.assertRaisesRegex(ValueError, "input"):
            self.compose(verification)

    def test_normalized_at_validation_precedence_is_exact(self):
        stale = self.verify()
        self.coherently_retimestamp(stale)
        with self.assertRaisesRegex(TypeError, "normalized_at"):
            self.compose(stale, normalized_at=object())
        with self.assertRaisesRegex(ValueError, "input"):
            self.compose(
                stale,
                normalized_at=datetime.datetime(2030, 1, 3),
            )

        out_of_scope = self.verify(
            underlying_key=UnderlyingKey(
                symbol="SPY",
                listing_mic="XNAS",
                security_type=UnderlyingSecurityType.ETF,
                currency="USD",
            )
        )
        with self.assertRaisesRegex(ValueError, "scope"):
            self.compose(
                out_of_scope,
                normalized_at=datetime.datetime(2030, 1, 3),
            )

        class EqualString(str):
            def __eq__(self, other):
                return str(self) == other

            __hash__ = str.__hash__

        source_tampered = self.verify()
        source = source_tampered.contract_reference.metadata.source_references[0]
        object.__setattr__(
            source,
            "provider_name",
            EqualString(source.provider_name),
        )
        source_tampered = tiger.TigerExactOptionContractVerification(
            source_tampered.provider_identifier,
            source_tampered.provider_period_tag,
            source_tampered.provider_expiration_timestamp_ms,
            source_tampered.contract_reference,
        )
        with self.assertRaisesRegex(ValueError, "provenance"):
            self.compose(
                source_tampered,
                normalized_at=datetime.datetime(2030, 1, 3),
            )

    def test_exact_types_frozen_records_and_direct_api_signature(self):
        verification = self.verify()
        result = self.compose(verification)
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(verification)),
            (
                "provider_identifier",
                "provider_period_tag",
                "provider_expiration_timestamp_ms",
                "contract_reference",
            ),
        )
        self.assertIs(type(verification._creation_integrity_fingerprint), str)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.exercise_style = "European"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.metadata.record_id = "forged"

        class VerificationSubclass(tiger.TigerExactOptionContractVerification):
            pass

        subclass = VerificationSubclass(
            verification.provider_identifier,
            verification.provider_period_tag,
            verification.provider_expiration_timestamp_ms,
            verification.contract_reference,
        )
        with self.assertRaises(TypeError):
            self.compose(subclass)

        class DateTimeSubclass(datetime.datetime):
            pass

        with self.assertRaises(TypeError):
            self.compose(
                verification,
                normalized_at=DateTimeSubclass(
                    2030, 1, 3, tzinfo=datetime.timezone.utc
                ),
            )
        signature = inspect.signature(
            tiger.compose_tiger_spy_option_product_terms_reference
        )
        self.assertEqual(tuple(signature.parameters), ("verification", "normalized_at"))
        self.assertEqual(
            signature.parameters["normalized_at"].kind,
            inspect.Parameter.KEYWORD_ONLY,
        )

    def test_composition_has_no_sdk_network_filesystem_environment_or_clock_use(self):
        verification = self.verify()
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=AssertionError("clock access forbidden"),
        ), mock.patch.object(
            tiger,
            "_load_tiger_sdk",
            side_effect=AssertionError("SDK access forbidden"),
        ), mock.patch.object(
            tiger,
            "resolve_tiger_config_path",
            side_effect=AssertionError("filesystem/credential access forbidden"),
        ):
            result = self.compose(verification)
        self.assertEqual(result.exercise_style, "American")

    def test_incomplete_composite_cannot_enter_existing_cost_path(self):
        from tests.market_data_fixtures import (
            build_freshness_context,
            build_freshness_policy,
        )
        from tests.test_market_data import build_timing_binding

        base = datetime.datetime(
            2030, 1, 2, 15, 30, tzinfo=datetime.timezone.utc
        )
        chain_row = dict(
            SyntheticQuoteClient().chain_rows[0],
            identifier="SPY   300315C00100000",
            strike=100.0,
        )
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=(
                base,
                base + datetime.timedelta(microseconds=1),
                base + datetime.timedelta(microseconds=2),
            ),
        ):
            verification = tiger.verify_tiger_monthly_option_contract(
                SyntheticQuoteClient(chain_rows=[chain_row]),
                underlying_key=self.underlying,
                expiration=self.expiration,
                option_type="call",
                strike=decimal.Decimal("100"),
            )
        composite = tiger.compose_tiger_spy_option_product_terms_reference(
            verification,
            normalized_at=base + datetime.timedelta(microseconds=3),
        )

        policy = build_freshness_policy(
            allow_assigned_timestamps=True,
            maximum_reference_age_seconds=200_000_000,
            maximum_source_observation_span_seconds=200_000_000,
            maximum_cross_record_skew_seconds=200_000_000,
        )
        context = build_freshness_context()
        with self.assertRaisesRegex(
            ValueError,
            "selected candidate must be fresh within policy",
        ):
            build_timing_binding(
                composite,
                policy=policy,
                context=context,
            )


class ExactOptionQuoteEvidenceTests(TigerProviderTestCase):
    def setUp(self):
        super().setUp()
        self.underlying = UnderlyingKey(
            symbol="SPY",
            listing_mic="ARCX",
            security_type=UnderlyingSecurityType.ETF,
            currency="USD",
        )
        self.expiration_received_at = datetime.datetime(
            2030, 1, 2, 15, 30, tzinfo=datetime.timezone.utc
        )
        self.chain_received_at = self.expiration_received_at + datetime.timedelta(
            seconds=1
        )
        self.normalized_at = self.chain_received_at + datetime.timedelta(seconds=1)
        verification_client = SyntheticQuoteClient()
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=(
                self.expiration_received_at,
                self.chain_received_at,
                self.normalized_at,
            ),
        ):
            self.verification = tiger.verify_tiger_monthly_option_contract(
                verification_client,
                underlying_key=self.underlying,
                expiration=datetime.date(2030, 3, 15),
                option_type="call",
                strike=decimal.Decimal("500"),
            )
        self.permission_received_at = self.normalized_at + datetime.timedelta(
            seconds=1
        )
        self.quote_received_at = self.permission_received_at + datetime.timedelta(
            seconds=1
        )

    def retrieve(self, client=None):
        client = SyntheticQuoteClient() if client is None else client
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=(self.permission_received_at, self.quote_received_at),
        ):
            return tiger.retrieve_tiger_exact_option_quote_evidence(
                client,
                self.verification,
            )

    def test_permanent_permission_and_exact_quote_are_retained(self):
        client = SyntheticQuoteClient()
        result = self.retrieve(client)
        self.assertEqual(
            client.calls,
            [
                ("permission",),
                (
                    "chain",
                    "SPY",
                    "2030-03-15",
                    {"return_greek_value": False, "market": "US"},
                ),
            ],
        )
        self.assertIs(result.contract_verification, self.verification)
        self.assertEqual(result.bid_premium, decimal.Decimal("10.25"))
        self.assertEqual(result.ask_premium, decimal.Decimal("10.35"))
        self.assertEqual(result.bid_size, 12)
        self.assertEqual(result.ask_size, 14)
        self.assertEqual(result.permission_expire_at_ms, -1)
        self.assertEqual(result.permission_received_at, self.permission_received_at)
        self.assertEqual(result.quote_received_at, self.quote_received_at)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.bid_size = 99

    def test_finite_permission_must_remain_active_through_quote_receipt(self):
        active = tiger._unix_milliseconds(self.quote_received_at) + 1
        result = self.retrieve(
            SyntheticQuoteClient(
                permissions=[{"name": "usOptionQuote", "expire_at": active}]
            )
        )
        self.assertEqual(result.permission_expire_at_ms, active)

        expired = tiger._unix_milliseconds(self.permission_received_at)
        client = SyntheticQuoteClient(
            permissions=[{"name": "usOptionQuote", "expire_at": expired}]
        )
        with self.assertRaisesRegex(ValueError, "permission is not active"):
            self.retrieve(client)
        self.assertEqual(client.calls, [("permission",)])

        between = tiger._unix_milliseconds(self.quote_received_at)
        with self.assertRaisesRegex(ValueError, "permission is not active"):
            self.retrieve(
                SyntheticQuoteClient(
                    permissions=[
                        {"name": "usOptionQuote", "expire_at": between}
                    ]
                )
            )

    def test_permission_must_have_one_exact_valid_entry(self):
        cases = (
            [],
            [{"name": "usQuoteBasic", "expire_at": -1}],
            [
                {"name": "usOptionQuote", "expire_at": -1},
                {"name": "usOptionQuote", "expire_at": -1},
            ],
        )
        for permissions in cases:
            with self.subTest(count=len(permissions)):
                client = SyntheticQuoteClient(permissions=permissions)
                with self.assertRaisesRegex(ValueError, "exactly one"):
                    self.retrieve(client)
                self.assertEqual(client.calls, [("permission",)])

    def test_malformed_permission_fails_safely_before_chain(self):
        secret = "synthetic-permission-secret"
        cases = (
            None,
            [{"name": "usOptionQuote"}],
            [{"name": "usOptionQuote", "expire_at": True}],
            [{"name": "usOptionQuote", "expire_at": 0}],
        )
        for response in cases:
            with self.subTest(response_type=type(response).__name__):
                client = SyntheticQuoteClient()
                client.permissions = response
                with self.assertRaisesRegex(ValueError, "response is invalid"):
                    self.retrieve(client)
                self.assertEqual(client.calls, [("permission",)])

        client = SyntheticQuoteClient()
        client.get_quote_permission = mock.Mock(side_effect=RuntimeError(secret))
        with self.assertRaisesRegex(RuntimeError, "permission retrieval failed") as raised:
            self.retrieve(client)
        self.assertNotIn(secret, str(raised.exception))

        class ExplodingString(str):
            def __eq__(self, other):
                raise RuntimeError(secret)

        class ExplodingInteger(int):
            def __int__(self):
                raise RuntimeError(secret)

        for permission in (
            {"name": ExplodingString("usOptionQuote"), "expire_at": -1},
            {"name": "usOptionQuote", "expire_at": ExplodingInteger(-1)},
        ):
            with self.assertRaisesRegex(ValueError, "response is invalid") as raised:
                self.retrieve(SyntheticQuoteClient(permissions=[permission]))
            self.assertNotIn(secret, str(raised.exception))

    def test_chain_row_must_match_exact_verified_identity_once(self):
        exact = SyntheticQuoteClient().chain_rows[0]
        wrong = dict(exact, identifier="SPY   300315C00501000", strike=501.0)
        for rows in ([wrong], [dict(exact), dict(exact)]):
            with self.subTest(count=len(rows)):
                with self.assertRaisesRegex(ValueError, "exactly one verified"):
                    self.retrieve(SyntheticQuoteClient(chain_rows=rows))

    def test_quote_numeric_conversion_missing_sizes_and_locked_quote(self):
        row = dict(
            SyntheticQuoteClient().chain_rows[0],
            bid_price="10.25",
            ask_price=decimal.Decimal("10.25"),
            bid_size=float("nan"),
            ask_size=None,
        )
        result = self.retrieve(SyntheticQuoteClient(chain_rows=[row]))
        self.assertEqual(result.bid_premium, decimal.Decimal("10.25"))
        self.assertEqual(result.ask_premium, decimal.Decimal("10.25"))
        self.assertIsNone(result.bid_size)
        self.assertIsNone(result.ask_size)

    def test_crossed_or_malformed_quote_fails_safely(self):
        secret = "synthetic-quote-secret"

        class ExplodingScalar:
            def __str__(self):
                raise RuntimeError(secret)

        changes = (
            {"ask_price": 10.0},
            {"bid_price": -1},
            {"ask_price": 0},
            {"bid_size": 1.5},
            {"ask_size": -1},
            {"bid_price": ExplodingScalar()},
        )
        for change in changes:
            with self.subTest(field=tuple(change)):
                row = dict(SyntheticQuoteClient().chain_rows[0], **change)
                with self.assertRaisesRegex(ValueError, "response is invalid") as raised:
                    self.retrieve(SyntheticQuoteClient(chain_rows=[row]))
                self.assertNotIn(secret, str(raised.exception))

        class ExplodingString(str):
            def __eq__(self, other):
                raise RuntimeError(secret)

        row = dict(
            SyntheticQuoteClient().chain_rows[0],
            identifier=ExplodingString("SPY   300315C00500000"),
        )
        with self.assertRaisesRegex(ValueError, "response is invalid") as raised:
            self.retrieve(SyntheticQuoteClient(chain_rows=[row]))
        self.assertNotIn(secret, str(raised.exception))

    def test_quote_validation_precedes_permission_expiry_at_quote_receipt(self):
        expires_at_quote = tiger._unix_milliseconds(self.quote_received_at)
        row = dict(SyntheticQuoteClient().chain_rows[0], ask_price=0)
        client = SyntheticQuoteClient(
            chain_rows=[row],
            permissions=[
                {"name": "usOptionQuote", "expire_at": expires_at_quote}
            ],
        )
        with self.assertRaisesRegex(ValueError, "quote response is invalid"):
            self.retrieve(client)

    def test_chain_request_failure_is_sanitized(self):
        secret = "synthetic-chain-secret"
        client = SyntheticQuoteClient()
        client.get_option_chain = mock.Mock(side_effect=RuntimeError(secret))
        with self.assertRaisesRegex(RuntimeError, "chain retrieval failed") as raised:
            self.retrieve(client)
        self.assertNotIn(secret, str(raised.exception))

    def test_invalid_verification_fails_before_permission(self):
        client = SyntheticQuoteClient()
        with self.assertRaisesRegex(TypeError, "contract_verification"):
            tiger.retrieve_tiger_exact_option_quote_evidence(client, object())
        self.assertEqual(client.calls, [])

    def test_direct_construction_requires_exact_builtin_types(self):
        result = self.retrieve()

        class DecimalSubclass(decimal.Decimal):
            pass

        class IntegerSubclass(int):
            pass

        with self.assertRaisesRegex(TypeError, "bid_premium must be a Decimal"):
            dataclasses.replace(
                result,
                bid_premium=DecimalSubclass("10.25"),
            )
        with self.assertRaisesRegex(ValueError, "bid_size"):
            dataclasses.replace(result, bid_size=IntegerSubclass(12))
        with self.assertRaisesRegex(TypeError, "permission_expire_at_ms"):
            dataclasses.replace(
                result,
                permission_expire_at_ms=IntegerSubclass(-1),
            )

    @unittest.skipUnless(
        importlib.util.find_spec("pandas") is not None,
        "optional pandas dependency is not installed",
    )
    def test_actual_pandas_and_numpy_provider_scalars_are_supported(self):
        import numpy
        import pandas

        class PandasClient(SyntheticQuoteClient):
            def get_quote_permission(self):
                self.calls.append(("permission",))
                return [
                    {
                        "name": "usOptionQuote",
                        "expire_at": numpy.int64(-1),
                    }
                ]

            def get_option_chain(self, symbol, expiry, **kwargs):
                self.calls.append(("chain", symbol, expiry, kwargs))
                row = dict(
                    self.chain_rows[0],
                    expiry=numpy.int64(1899781200000),
                    multiplier=numpy.int64(100),
                    bid_price=numpy.float64(10.25),
                    ask_price=numpy.float64(10.35),
                    bid_size=pandas.NA,
                    ask_size=numpy.float64(14.0),
                )
                return pandas.DataFrame([row])

        result = self.retrieve(PandasClient())
        self.assertEqual(result.bid_premium, decimal.Decimal("10.25"))
        self.assertEqual(result.ask_premium, decimal.Decimal("10.35"))
        self.assertEqual((result.bid_size, result.ask_size), (None, 14))


class HistoricalDividendEvidenceTests(TigerProviderTestCase):
    def setUp(self):
        super().setUp()
        self.underlying = UnderlyingKey(
            symbol="SPY",
            listing_mic="ARCX",
            security_type=UnderlyingSecurityType.ETF,
            currency="USD",
        )
        self.begin_date = datetime.date(2030, 1, 1)
        self.end_date = datetime.date(2030, 1, 31)
        self.latest_completed_date = datetime.date(2030, 1, 31)
        self.retrieved_at = datetime.datetime(
            2030,
            2,
            1,
            12,
            tzinfo=datetime.timezone(datetime.timedelta(hours=8)),
        )

    def retrieve(self, client=None, **overrides):
        values = {
            "underlying_key": self.underlying,
            "begin_date": self.begin_date,
            "end_date": self.end_date,
            "latest_completed_date": self.latest_completed_date,
        }
        values.update(overrides)
        client = SyntheticDividendQuoteClient() if client is None else client
        with mock.patch.object(
            tiger,
            "_utc_now",
            return_value=self.retrieved_at,
        ):
            return tiger.retrieve_tiger_historical_dividend_evidence(
                client,
                **values,
            )

    def test_exact_request_row_mapping_and_utc_receipt(self):
        client = SyntheticDividendQuoteClient()
        result = self.retrieve(client)

        self.assertEqual(
            client.calls,
            [
                (
                    (["SPY"], "US", "2030-01-01", "2030-01-31"),
                    {"timezone": "US/Eastern"},
                )
            ],
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(
            tuple(item.execute_date for item in result),
            (datetime.date(2030, 1, 10), datetime.date(2030, 1, 15)),
        )
        first, second = result
        self.assertIs(first.underlying_key, self.underlying)
        self.assertEqual(first.action_type, "DIVIDEND")
        self.assertEqual(first.provider_amount.as_tuple(), (0, (5, 0, 0), -3))
        self.assertEqual(first.currency, "USD")
        self.assertIsNone(first.announced_date)
        self.assertEqual(first.record_date, datetime.date(2030, 1, 15))
        self.assertIsNone(first.pay_date)
        self.assertEqual(first.market, "US")
        self.assertEqual(first.exchange, "NYSE")
        self.assertEqual(
            first.retrieved_at,
            self.retrieved_at.astimezone(datetime.timezone.utc),
        )
        self.assertEqual(second.provider_amount.as_tuple(), (0, (1, 2, 3, 0, 0), -4))
        self.assertEqual(second.announced_date, datetime.date(2030, 1, 1))
        self.assertEqual(second.pay_date, datetime.date(2030, 1, 25))
        self.assertEqual(second.exchange, "NASDAQ")

    def test_none_and_empty_tables_are_valid_no_data(self):
        for response in (None, SyntheticTable([])):
            with self.subTest(response=response):
                client = SyntheticDividendQuoteClient()
                client.response = response
                self.assertEqual(self.retrieve(client), ())
                self.assertEqual(len(client.calls), 1)

    def test_frozen_record_has_exact_fields_and_no_provider_neutral_dividend(self):
        self.assertEqual(
            tuple(field.name for field in dataclasses.fields(
                tiger.TigerHistoricalDividendEvidence
            )),
            (
                "underlying_key",
                "action_type",
                "provider_amount",
                "currency",
                "announced_date",
                "execute_date",
                "record_date",
                "pay_date",
                "market",
                "exchange",
                "retrieved_at",
            ),
        )
        result = self.retrieve()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result[0].exchange = "NYSE"
        self.assertNotIn("DividendObservation", tiger.__dict__)

    def test_caller_bounds_and_identity_fail_before_request(self):
        cases = (
            {"underlying_key": object()},
            {"begin_date": datetime.datetime(2030, 1, 1)},
            {
                "begin_date": datetime.date(2030, 2, 1),
                "end_date": datetime.date(2030, 1, 31),
            },
            {
                "begin_date": datetime.date(2029, 1, 1),
                "end_date": datetime.date(2030, 1, 7),
                "latest_completed_date": datetime.date(2030, 1, 7),
            },
            {"latest_completed_date": datetime.date(2030, 1, 30)},
        )
        for values in cases:
            with self.subTest(values=tuple(values)):
                client = SyntheticDividendQuoteClient()
                with self.assertRaises((TypeError, ValueError)):
                    self.retrieve(client, **values)
                self.assertEqual(client.calls, [])

    def test_method_availability_and_sdk_failure_are_sanitized(self):
        class MissingMethod:
            pass

        with self.assertRaisesRegex(TypeError, "must provide Tiger quote methods"):
            self.retrieve(MissingMethod())

        secret = "synthetic-dividend-sdk-secret"
        client = SyntheticDividendQuoteClient()
        client.get_corporate_dividend = mock.Mock(
            side_effect=RuntimeError(secret)
        )
        with self.assertRaisesRegex(
            RuntimeError, "historical-dividend retrieval failed"
        ) as raised:
            self.retrieve(client)
        self.assertNotIn(secret, str(raised.exception))

        class ExplodingMethod:
            @property
            def get_corporate_dividend(self):
                raise RuntimeError(secret)

        with self.assertRaisesRegex(TypeError, "must provide Tiger quote methods") as raised:
            self.retrieve(ExplodingMethod())
        self.assertNotIn(secret, str(raised.exception))

    def test_table_shape_and_scalar_failures_are_sanitized(self):
        base = SyntheticDividendQuoteClient().response.records[0]
        responses = (
            SyntheticTable([{"symbol": "SPY"}]),
            SyntheticTable([dict(base, extra="synthetic-secret")]),
            object(),
        )
        for response in responses:
            with self.subTest(response_type=type(response).__name__):
                client = SyntheticDividendQuoteClient()
                client.response = response
                with self.assertRaisesRegex(ValueError, "response is invalid"):
                    self.retrieve(client)

        secret = "synthetic-dividend-payload-secret"

        class ExplodingScalar:
            def __str__(self):
                raise RuntimeError(secret)

        client = SyntheticDividendQuoteClient(
            rows=[dict(base, amount=ExplodingScalar())]
        )
        with self.assertRaisesRegex(ValueError, "response is invalid") as raised:
            self.retrieve(client)
        self.assertNotIn(secret, str(raised.exception))

        class ExplodingTable:
            @property
            def to_dict(self):
                raise RuntimeError(secret)

        client = SyntheticDividendQuoteClient()
        client.response = ExplodingTable()
        with self.assertRaisesRegex(ValueError, "response is invalid") as raised:
            self.retrieve(client)
        self.assertNotIn(secret, str(raised.exception))

    def test_identity_classification_amount_and_date_validation(self):
        base = SyntheticDividendQuoteClient().response.records[0]
        changes = (
            {"symbol": "QQQ"},
            {"action_type": "dividend"},
            {"amount": True},
            {"amount": -decimal.Decimal("0.01")},
            {"amount": decimal.Decimal("NaN")},
            {"currency": "EUR"},
            {"market": "EU"},
            {"exchange": "   "},
            {"execute_date": "2030-1-15"},
            {"announced_date": "2030-01-01T00:00:00"},
        )
        for change in changes:
            with self.subTest(field=tuple(change)):
                client = SyntheticDividendQuoteClient(
                    rows=[dict(base, **change)]
                )
                with self.assertRaisesRegex(ValueError, "response is invalid"):
                    self.retrieve(client)
                self.assertEqual(len(client.calls), 1)

    def test_execute_bounds_and_date_chronology_fail_closed(self):
        base = SyntheticDividendQuoteClient().response.records[0]
        changes = (
            {"announced_date": "2030-01-16"},
            {"record_date": "2030-01-14"},
            {"pay_date": "2030-01-14"},
            {"execute_date": "2029-12-31"},
            {"execute_date": "2030-02-01"},
        )
        for change in changes:
            with self.subTest(field=tuple(change)):
                client = SyntheticDividendQuoteClient(
                    rows=[dict(base, **change)]
                )
                with self.assertRaisesRegex(ValueError, "response is invalid"):
                    self.retrieve(client)

    def test_exact_duplicates_fail_but_same_execute_date_distributions_remain(self):
        base = SyntheticDividendQuoteClient().response.records[0]
        duplicate_client = SyntheticDividendQuoteClient(
            rows=[dict(base), dict(base)]
        )
        with self.assertRaisesRegex(ValueError, "duplicate rows"):
            self.retrieve(duplicate_client)
        self.assertEqual(len(duplicate_client.calls), 1)

        first = dict(
            base,
            amount="1.00",
            execute_date="2030-01-12",
            announced_date="2030-01-01",
            exchange="NASDAQ",
        )
        second = dict(
            base,
            amount="0.50",
            execute_date="2030-01-12",
            announced_date="2030-01-01",
            exchange="NYSE",
        )
        result = self.retrieve(
            SyntheticDividendQuoteClient(rows=[first, second])
        )
        self.assertEqual(
            tuple(item.provider_amount for item in result),
            (decimal.Decimal("0.50"), decimal.Decimal("1.00")),
        )
        self.assertEqual(len(result), 2)

        reversed_result = self.retrieve(
            SyntheticDividendQuoteClient(rows=[second, first])
        )
        self.assertEqual(result, reversed_result)

    def test_direct_record_validation_and_frozen_utc_timestamp(self):
        valid = self.retrieve()[0]
        self.assertEqual(
            valid.retrieved_at.tzinfo,
            datetime.timezone.utc,
        )
        with self.assertRaises(TypeError):
            dataclasses.replace(valid, provider_amount=1)
        with self.assertRaises(ValueError):
            dataclasses.replace(valid, action_type="OTHER")
        with self.assertRaises(ValueError):
            dataclasses.replace(
                valid,
                announced_date=datetime.date(2030, 1, 20),
            )


class UnderlyingDailyBarsTests(TigerProviderTestCase):
    def setUp(self):
        super().setUp()
        self.underlying = UnderlyingKey(
            symbol="SPY",
            listing_mic="ARCX",
            security_type=UnderlyingSecurityType.ETF,
            currency="USD",
        )
        self.nr_received = datetime.datetime(
            2030, 1, 5, 12, tzinfo=datetime.timezone.utc
        )
        self.br_received = self.nr_received + datetime.timedelta(seconds=1)
        self.normalized = self.br_received + datetime.timedelta(seconds=1)

    def retrieve(self, client=None, **overrides):
        values = {
            "underlying_key": self.underlying,
            "begin_date": datetime.date(2030, 1, 1),
            "end_date": datetime.date(2030, 1, 4),
            "latest_completed_session_date": datetime.date(2030, 1, 3),
        }
        values.update(overrides)
        client = SyntheticQuoteClient() if client is None else client
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=(self.nr_received, self.br_received, self.normalized),
        ):
            return tiger.retrieve_tiger_underlying_daily_bars(client, **values)

    def test_exact_nr_br_pair_builds_existing_daily_bar(self):
        client = SyntheticQuoteClient()
        result = self.retrieve(client)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            client.calls,
            [
                (
                    "bars",
                    {
                        "symbol": "SPY",
                        "period": "day",
                        "begin_time": 1893474000000,
                        "end_time": 1893733200000,
                        "total": 1000,
                        "page_size": 1000,
                        "time_interval": 0,
                        "trade_session": None,
                        "with_fundamental": False,
                        "sec_type": None,
                        "right": "nr",
                    },
                ),
                (
                    "bars",
                    {
                        "symbol": "SPY",
                        "period": "day",
                        "begin_time": 1893474000000,
                        "end_time": 1893733200000,
                        "total": 1000,
                        "page_size": 1000,
                        "time_interval": 0,
                        "trade_session": None,
                        "with_fundamental": False,
                        "sec_type": None,
                        "right": "br",
                    },
                ),
            ],
        )
        bar = result[0]
        self.assertIsInstance(bar, UnderlyingDailyBarObservation)
        self.assertEqual(bar.session_date, datetime.date(2030, 1, 2))
        self.assertEqual(bar.open_price, decimal.Decimal("500.0"))
        self.assertEqual(bar.high_price, decimal.Decimal("505.0"))
        self.assertEqual(bar.low_price, decimal.Decimal("498.0"))
        self.assertEqual(bar.close_price, decimal.Decimal("503.0"))
        self.assertEqual(bar.adjusted_close_price, decimal.Decimal("498.0"))
        self.assertEqual(bar.volume, 1000000)
        self.assertTrue(bar.is_session_complete)
        self.assertIn("QuoteRight.BR", bar.adjustment_methodology)
        self.assertEqual(bar.metadata.record_origin, DataOrigin.SYSTEM_COMPOSITE)
        self.assertEqual(
            bar.metadata.quality_flags,
            (NormalizationQualityFlag.COMPOSITE_SOURCE,),
        )
        sources = {source.dataset_name: source for source in bar.metadata.source_references}
        self.assertEqual(
            set(sources),
            {"underlying_daily_bars_nr", "underlying_daily_bars_br"},
        )
        self.assertEqual(sources["underlying_daily_bars_nr"].retrieved_at, self.nr_received)
        self.assertEqual(sources["underlying_daily_bars_br"].retrieved_at, self.br_received)
        self.assertIn("not asserted", sources["underlying_daily_bars_nr"].timestamp_methodology)

    def test_input_range_fails_before_requests(self):
        cases = (
            {"begin_date": datetime.date(2030, 1, 4)},
            {"end_date": datetime.date(2031, 2, 1)},
            {"end_date": datetime.date(2030, 1, 5)},
            {"begin_date": datetime.datetime(2030, 1, 1)},
        )
        for values in cases:
            with self.subTest(values=tuple(values)):
                client = SyntheticQuoteClient()
                with self.assertRaises((TypeError, ValueError)):
                    self.retrieve(client, **values)
                self.assertEqual(client.calls, [])

    def test_empty_mismatched_or_duplicate_series_fails(self):
        row = SyntheticQuoteClient().nr_bar_rows[0]
        next_day = dict(row, time=row["time"] + 86_400_000)
        cases = (
            SyntheticQuoteClient(nr_bar_rows=[], br_bar_rows=[]),
            SyntheticQuoteClient(br_bar_rows=[next_day]),
            SyntheticQuoteClient(nr_bar_rows=[row, dict(row)]),
        )
        for client in cases:
            with self.subTest(calls=len(client.calls)):
                with self.assertRaisesRegex(ValueError, "daily-bar"):
                    self.retrieve(client)
        empty_nr = SyntheticQuoteClient(nr_bar_rows=[])
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            self.retrieve(empty_nr)
        self.assertEqual(len(empty_nr.calls), 1)

    def test_out_of_range_symbol_and_invalid_numbers_fail_safely(self):
        changes = (
            {"symbol": "QQQ"},
            {"open": 0},
            {"high": float("nan")},
            {"volume": -1},
        )
        for change in changes:
            with self.subTest(field=tuple(change)):
                row = dict(SyntheticQuoteClient().nr_bar_rows[0], **change)
                client = SyntheticQuoteClient(nr_bar_rows=[row])
                with self.assertRaisesRegex(ValueError, "response is invalid"):
                    self.retrieve(client)
                self.assertEqual(len(client.calls), 1)

        invalid_ohlc = dict(
            SyntheticQuoteClient().nr_bar_rows[0],
            high=499.0,
        )
        client = SyntheticQuoteClient(nr_bar_rows=[invalid_ohlc])
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            self.retrieve(client)
        self.assertEqual(len(client.calls), 1)

        br_row = dict(SyntheticQuoteClient().br_bar_rows[0], close=float("nan"))
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            self.retrieve(SyntheticQuoteClient(br_bar_rows=[br_row]))

    def test_same_session_different_timestamp_and_future_row_fail(self):
        nr_row = SyntheticQuoteClient().nr_bar_rows[0]
        br_row = dict(
            SyntheticQuoteClient().br_bar_rows[0],
            time=nr_row["time"] + 3_600_000,
        )
        with self.assertRaisesRegex(ValueError, "do not pair exactly"):
            self.retrieve(SyntheticQuoteClient(br_bar_rows=[br_row]))

        future = dict(nr_row, time=nr_row["time"] + 2 * 86_400_000)
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            self.retrieve(SyntheticQuoteClient(nr_bar_rows=[future]))

    def test_session_date_conversion_is_dst_safe(self):
        eastern = zoneinfo.ZoneInfo("America/New_York")
        dates = (datetime.date(2030, 3, 8), datetime.date(2030, 3, 11))
        self.nr_received = datetime.datetime(
            2030, 3, 12, 12, tzinfo=datetime.timezone.utc
        )
        self.br_received = self.nr_received + datetime.timedelta(seconds=1)
        self.normalized = self.br_received + datetime.timedelta(seconds=1)
        nr_rows = []
        br_rows = []
        template_nr = SyntheticQuoteClient().nr_bar_rows[0]
        template_br = SyntheticQuoteClient().br_bar_rows[0]
        for session_date in dates:
            timestamp = int(
                datetime.datetime.combine(
                    session_date,
                    datetime.time(0),
                    tzinfo=eastern,
                ).timestamp()
                * 1000
            )
            nr_rows.append(dict(template_nr, time=timestamp))
            br_rows.append(dict(template_br, time=timestamp))
        client = SyntheticQuoteClient(nr_bar_rows=nr_rows, br_bar_rows=br_rows)
        result = self.retrieve(
            client,
            begin_date=datetime.date(2030, 3, 8),
            end_date=datetime.date(2030, 3, 12),
            latest_completed_session_date=datetime.date(2030, 3, 11),
        )
        self.assertEqual(tuple(bar.session_date for bar in result), dates)
        self.assertEqual(client.calls[0][1]["begin_time"], 1899176400000)
        self.assertEqual(client.calls[0][1]["end_time"], 1899518400000)
        self.assertEqual(client.calls[1][1]["begin_time"], 1899176400000)
        self.assertEqual(client.calls[1][1]["end_time"], 1899518400000)

    def test_retrieval_failure_is_sanitized(self):
        secret = "synthetic-bar-secret"
        client = SyntheticQuoteClient()
        client.get_bars_by_page = mock.Mock(side_effect=RuntimeError(secret))
        with self.assertRaisesRegex(RuntimeError, "daily-bar retrieval failed") as raised:
            self.retrieve(client)
        self.assertNotIn(secret, str(raised.exception))

    def test_output_is_chronological_and_deterministic(self):
        first = SyntheticQuoteClient().nr_bar_rows[0]
        second = dict(first, time=first["time"] + 86_400_000, close=504.0)
        first_br = SyntheticQuoteClient().br_bar_rows[0]
        second_br = dict(first_br, time=second["time"], close=499.0)
        client = SyntheticQuoteClient(
            nr_bar_rows=[second, first],
            br_bar_rows=[second_br, first_br],
        )
        result = self.retrieve(client)
        self.assertEqual(
            tuple(bar.session_date for bar in result),
            (datetime.date(2030, 1, 2), datetime.date(2030, 1, 3)),
        )

    @unittest.skipUnless(
        importlib.util.find_spec("pandas") is not None,
        "optional pandas dependency is not installed",
    )
    def test_actual_pandas_numpy_rows_are_supported(self):
        import numpy
        import pandas

        class PandasBarsClient(SyntheticQuoteClient):
            def get_bars_by_page(self, **kwargs):
                self.calls.append(("bars", kwargs))
                rows = self.nr_bar_rows if kwargs["right"] == "nr" else self.br_bar_rows
                row = dict(rows[0])
                row["time"] = numpy.int64(row["time"])
                row["volume"] = numpy.int64(row["volume"])
                row["close"] = numpy.float64(row["close"])
                return pandas.DataFrame([row])

        result = self.retrieve(PandasBarsClient())
        self.assertEqual(result[0].volume, 1000000)


class HistoricalOptionBarEvidenceTests(TigerProviderTestCase):
    def setUp(self):
        super().setUp()
        self.underlying = UnderlyingKey(
            symbol="SPY",
            listing_mic="ARCX",
            security_type=UnderlyingSecurityType.ETF,
            currency="USD",
        )
        base = datetime.datetime(2030, 1, 1, 12, tzinfo=datetime.timezone.utc)
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=(
                base,
                base + datetime.timedelta(seconds=1),
                base + datetime.timedelta(seconds=2),
            ),
        ):
            self.verification = tiger.verify_tiger_monthly_option_contract(
                SyntheticQuoteClient(),
                underlying_key=self.underlying,
                expiration=datetime.date(2030, 3, 15),
                option_type="call",
                strike=decimal.Decimal("500"),
            )
        self.retrieved_at = datetime.datetime(
            2030, 1, 5, 12, tzinfo=datetime.timezone.utc
        )

    def retrieve(self, client=None, **overrides):
        values = {
            "begin_date": datetime.date(2030, 1, 1),
            "end_date": datetime.date(2030, 1, 4),
            "latest_completed_session_date": datetime.date(2030, 1, 3),
        }
        values.update(overrides)
        client = SyntheticOptionBarQuoteClient() if client is None else client
        with mock.patch.object(tiger, "_utc_now", return_value=self.retrieved_at):
            return tiger.retrieve_tiger_historical_option_bar_evidence(
                client,
                self.verification,
                **values,
            )

    def test_exact_request_builds_frozen_provider_native_evidence(self):
        client = SyntheticOptionBarQuoteClient()
        result = self.retrieve(client)
        self.assertEqual(
            client.calls,
            [
                (
                    (["SPY   300315C00500000"],),
                    {
                        "begin_time": 1893474000000,
                        "end_time": 1893733200000,
                        "period": "day",
                        "limit": None,
                        "sort_dir": None,
                        "market": "US",
                        "timezone": "US/Eastern",
                    },
                )
            ],
        )
        self.assertEqual(len(result), 1)
        item = result[0]
        self.assertIsInstance(item, tiger.TigerHistoricalOptionBarEvidence)
        self.assertIs(item.contract_verification, self.verification)
        self.assertEqual(item.session_date, datetime.date(2030, 1, 2))
        self.assertEqual(item.open_premium, decimal.Decimal("10.1"))
        self.assertEqual(item.high_premium, decimal.Decimal("10.8"))
        self.assertEqual(item.low_premium, decimal.Decimal("9.9"))
        self.assertEqual(item.close_premium, decimal.Decimal("10.5"))
        self.assertEqual(item.volume, 123)
        self.assertEqual(item.open_interest, 456)
        self.assertEqual(item.retrieved_at, self.retrieved_at)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            item.volume = 124

    def test_none_or_empty_response_is_valid_no_bar_evidence(self):
        for response in (None, SyntheticTable([])):
            with self.subTest(response=type(response).__name__):
                self.assertEqual(
                    self.retrieve(SyntheticOptionBarQuoteClient(response)),
                    (),
                )

    def test_input_failures_precede_method_access(self):
        cases = (
            ({"begin_date": datetime.date(2030, 1, 4)}, None),
            ({"end_date": datetime.date(2031, 2, 1)}, None),
            ({"end_date": datetime.date(2030, 1, 5)}, None),
            ({"begin_date": datetime.datetime(2030, 1, 1)}, None),
        )
        for overrides, _ in cases:
            with self.subTest(overrides=tuple(overrides)):
                client = SyntheticOptionBarQuoteClient()
                with self.assertRaises((TypeError, ValueError)):
                    self.retrieve(client, **overrides)
                self.assertEqual(client.calls, [])
        client = SyntheticOptionBarQuoteClient()
        with self.assertRaisesRegex(TypeError, "contract_verification"):
            tiger.retrieve_tiger_historical_option_bar_evidence(
                client,
                object(),
                begin_date=datetime.date(2030, 1, 1),
                end_date=datetime.date(2030, 1, 4),
                latest_completed_session_date=datetime.date(2030, 1, 3),
            )
        self.assertEqual(client.calls, [])

    def test_exact_contract_identity_must_match_every_row(self):
        changes = (
            {"identifier": "SPY   300315P00500000"},
            {"symbol": "QQQ"},
            {"expiry": 1899867600000},
            {"put_call": "PUT"},
            {"strike": 501.0},
        )
        for change in changes:
            with self.subTest(field=tuple(change)):
                client = SyntheticOptionBarQuoteClient()
                client.response.records[0].update(change)
                with self.assertRaisesRegex(ValueError, "response is invalid"):
                    self.retrieve(client)

    def test_invalid_prices_counts_time_and_shape_fail_closed(self):
        changes = (
            {"open": 0},
            {"high": 10.0},
            {"low": float("nan")},
            {"volume": -1},
            {"open_interest": 1.5},
            {"time": True},
        )
        for change in changes:
            with self.subTest(field=tuple(change)):
                client = SyntheticOptionBarQuoteClient()
                client.response.records[0].update(change)
                with self.assertRaisesRegex(ValueError, "response is invalid"):
                    self.retrieve(client)
        client = SyntheticOptionBarQuoteClient()
        del client.response.records[0]["open_interest"]
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            self.retrieve(client)

        client = SyntheticOptionBarQuoteClient()
        client.response.records[0].update(volume=0, open_interest=0)
        item = self.retrieve(client)[0]
        self.assertEqual((item.volume, item.open_interest), (0, 0))

    def test_duplicates_fail_and_output_is_chronological(self):
        client = SyntheticOptionBarQuoteClient()
        first = client.response.records[0]
        client.response.records = [dict(first), dict(first)]
        with self.assertRaisesRegex(ValueError, "duplicate rows"):
            self.retrieve(client)

        client = SyntheticOptionBarQuoteClient()
        first = client.response.records[0]
        second = dict(
            first,
            time=first["time"] + 86_400_000,
            open=10.6,
            high=11.0,
            low=10.4,
            close=10.9,
        )
        client.response.records = [second, first]
        result = self.retrieve(client)
        self.assertEqual(
            tuple(item.session_date for item in result),
            (datetime.date(2030, 1, 2), datetime.date(2030, 1, 3)),
        )

    def test_est_and_edt_request_boundaries_and_session_conversion(self):
        eastern = zoneinfo.ZoneInfo("America/New_York")
        client = SyntheticOptionBarQuoteClient()
        client.response.records[0]["time"] = int(
            datetime.datetime(
                2030, 3, 11, tzinfo=eastern
            ).timestamp()
            * 1000
        )
        self.retrieved_at = datetime.datetime(
            2030, 3, 13, 12, tzinfo=datetime.timezone.utc
        )
        result = self.retrieve(
            client,
            begin_date=datetime.date(2030, 3, 8),
            end_date=datetime.date(2030, 3, 12),
            latest_completed_session_date=datetime.date(2030, 3, 11),
        )
        self.assertEqual(result[0].session_date, datetime.date(2030, 3, 11))
        self.assertEqual(client.calls[0][1]["begin_time"], 1899176400000)
        self.assertEqual(client.calls[0][1]["end_time"], 1899518400000)

    def test_retrieval_and_accessor_failures_are_sanitized(self):
        secret = "synthetic-option-bar-secret"
        client = SyntheticOptionBarQuoteClient()
        client.get_option_bars = mock.Mock(side_effect=RuntimeError(secret))
        with self.assertRaisesRegex(
            RuntimeError, "option-bar retrieval failed"
        ) as raised:
            self.retrieve(client)
        self.assertNotIn(secret, str(raised.exception))

        class ExplodingClient:
            @property
            def get_option_bars(self):
                raise RuntimeError(secret)

        with self.assertRaisesRegex(
            TypeError, "must provide Tiger quote methods"
        ) as raised:
            self.retrieve(ExplodingClient())
        self.assertNotIn(secret, str(raised.exception))

    def test_direct_construction_preserves_exact_types_and_time_binding(self):
        item = self.retrieve()[0]
        with self.assertRaisesRegex(TypeError, "premiums must be Decimal"):
            dataclasses.replace(item, open_premium=10.1)
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            dataclasses.replace(item, session_date=datetime.date(2030, 1, 3))
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            dataclasses.replace(item, volume=-1)

    @unittest.skipUnless(
        importlib.util.find_spec("pandas") is not None,
        "optional pandas dependency is not installed",
    )
    def test_actual_pandas_numpy_rows_are_supported(self):
        import numpy
        import pandas

        client = SyntheticOptionBarQuoteClient()
        row = dict(client.response.records[0])
        row["time"] = numpy.int64(row["time"])
        row["volume"] = numpy.int64(row["volume"])
        row["open_interest"] = numpy.int64(row["open_interest"])
        row["close"] = numpy.float64(row["close"])
        client.response = pandas.DataFrame([row])
        result = self.retrieve(client)
        self.assertEqual(result[0].open_interest, 456)


class ExactOptionAnalyticsActivityEvidenceTests(TigerProviderTestCase):
    def setUp(self):
        super().setUp()
        self.underlying = UnderlyingKey(
            symbol="SPY",
            listing_mic="ARCX",
            security_type=UnderlyingSecurityType.ETF,
            currency="USD",
        )
        base = datetime.datetime(2030, 1, 1, 12, tzinfo=datetime.timezone.utc)
        with mock.patch.object(
            tiger,
            "_utc_now",
            side_effect=(
                base,
                base + datetime.timedelta(seconds=1),
                base + datetime.timedelta(seconds=2),
            ),
        ):
            self.verification = tiger.verify_tiger_monthly_option_contract(
                SyntheticQuoteClient(),
                underlying_key=self.underlying,
                expiration=datetime.date(2030, 3, 15),
                option_type="call",
                strike=decimal.Decimal("500"),
            )
        self.retrieved_at = datetime.datetime(
            2030, 1, 5, 12, tzinfo=datetime.timezone.utc
        )

    def retrieve(self, client=None):
        client = SyntheticQuoteClient() if client is None else client
        with mock.patch.object(tiger, "_utc_now", return_value=self.retrieved_at):
            return tiger.retrieve_tiger_exact_option_analytics_activity_evidence(
                client, self.verification
            )

    def test_exact_request_builds_frozen_provider_native_evidence(self):
        client = SyntheticQuoteClient()
        result = self.retrieve(client)
        self.assertEqual(
            client.calls,
            [
                (
                    "chain",
                    "SPY",
                    "2030-03-15",
                    {"return_greek_value": True, "market": "US"},
                )
            ],
        )
        self.assertIsInstance(
            result, tiger.TigerExactOptionAnalyticsActivityEvidence
        )
        self.assertIs(result.contract_verification, self.verification)
        self.assertEqual((result.volume, result.open_interest), (123, 456))
        self.assertEqual(result.implied_volatility, decimal.Decimal("0.25"))
        self.assertEqual(result.delta, decimal.Decimal("0.55"))
        self.assertEqual(result.gamma, decimal.Decimal("0.012"))
        self.assertEqual(result.theta, decimal.Decimal("-0.08"))
        self.assertEqual(result.vega, decimal.Decimal("0.15"))
        self.assertEqual(result.rho, decimal.Decimal("0.1"))
        self.assertEqual(result.retrieved_at, self.retrieved_at)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.volume = 1

    def test_exact_verified_row_is_required_once_without_substitution(self):
        exact = SyntheticQuoteClient().chain_rows[0]
        nearby = dict(
            exact,
            identifier="SPY   300315C00501000",
            strike=501.0,
        )
        for rows in ([nearby], [dict(exact), dict(exact)]):
            with self.subTest(count=len(rows)):
                client = SyntheticQuoteClient(chain_rows=rows)
                with self.assertRaisesRegex(ValueError, "exactly one verified"):
                    self.retrieve(client)

    def test_zero_activity_and_negative_zero_analytics_are_preserved_safely(self):
        row = dict(
            SyntheticQuoteClient().chain_rows[0],
            volume=0,
            open_interest=0,
            delta="-0.00",
            gamma="-0.00",
            theta="-0.00",
            vega="-0.00",
            rho="-0.00",
        )
        result = self.retrieve(SyntheticQuoteClient(chain_rows=[row]))
        self.assertEqual((result.volume, result.open_interest), (0, 0))
        for value in (
            result.delta,
            result.gamma,
            result.theta,
            result.vega,
            result.rho,
        ):
            self.assertEqual(value, decimal.Decimal(0))
            self.assertFalse(value.is_signed())
            self.assertEqual(value.as_tuple().exponent, -2)

    def test_unrelated_malformed_row_does_not_precede_exact_cardinality(self):
        exact = SyntheticQuoteClient().chain_rows[0]
        malformed_nearby = dict(
            exact,
            identifier="SPY   300315C00501000",
            strike=object(),
            expiry=object(),
            multiplier=object(),
        )
        result = self.retrieve(
            SyntheticQuoteClient(chain_rows=[malformed_nearby, exact])
        )
        self.assertEqual(result.implied_volatility, decimal.Decimal("0.25"))

        contradictory_exact = dict(exact, symbol="QQQ")
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            self.retrieve(SyntheticQuoteClient(chain_rows=[contradictory_exact]))

    def test_numeric_domains_fail_closed(self):
        changes = (
            {"volume": -1},
            {"open_interest": 1.5},
            {"implied_vol": 0},
            {"delta": 1.01},
            {"gamma": -0.01},
            {"theta": float("nan")},
            {"vega": -0.01},
            {"rho": float("inf")},
        )
        for change in changes:
            with self.subTest(field=tuple(change)):
                row = dict(SyntheticQuoteClient().chain_rows[0], **change)
                with self.assertRaisesRegex(ValueError, "response is invalid"):
                    self.retrieve(SyntheticQuoteClient(chain_rows=[row]))

    def test_last_trade_time_is_retained_but_not_used_as_analytics_time(self):
        result = self.retrieve()
        self.assertEqual(
            result.last_trade_at,
            datetime.datetime.fromtimestamp(
                1893589200, tz=datetime.timezone.utc
            ),
        )
        self.assertLess(result.last_trade_at, result.retrieved_at)
        future_ms = int(
            (self.retrieved_at + datetime.timedelta(seconds=1)).timestamp()
            * 1000
        )
        row = dict(
            SyntheticQuoteClient().chain_rows[0],
            last_timestamp=future_ms,
        )
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            self.retrieve(SyntheticQuoteClient(chain_rows=[row]))

    def test_input_method_and_sdk_failures_are_sanitized(self):
        client = SyntheticQuoteClient()
        with self.assertRaisesRegex(TypeError, "contract_verification"):
            tiger.retrieve_tiger_exact_option_analytics_activity_evidence(
                client, object()
            )
        self.assertEqual(client.calls, [])

        secret = "synthetic-analytics-secret"
        client = SyntheticQuoteClient()
        client.get_option_chain = mock.Mock(side_effect=RuntimeError(secret))
        with self.assertRaisesRegex(
            RuntimeError, "analytics/activity retrieval failed"
        ) as raised:
            self.retrieve(client)
        self.assertNotIn(secret, str(raised.exception))

        class ExplodingClient:
            @property
            def get_option_chain(self):
                raise RuntimeError(secret)

        with self.assertRaisesRegex(
            TypeError, "must provide Tiger quote methods"
        ) as raised:
            self.retrieve(ExplodingClient())
        self.assertNotIn(secret, str(raised.exception))

    def test_malformed_table_and_direct_construction_fail_safely(self):
        secret = "synthetic-row-secret"
        row = dict(SyntheticQuoteClient().chain_rows[0])
        del row["theta"]
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            self.retrieve(SyntheticQuoteClient(chain_rows=[row]))

        class ExplodingScalar:
            def __str__(self):
                raise RuntimeError(secret)

        row = dict(SyntheticQuoteClient().chain_rows[0], implied_vol=ExplodingScalar())
        with self.assertRaisesRegex(ValueError, "response is invalid") as raised:
            self.retrieve(SyntheticQuoteClient(chain_rows=[row]))
        self.assertNotIn(secret, str(raised.exception))

        result = self.retrieve()
        with self.assertRaisesRegex(TypeError, "analytics must be Decimal"):
            dataclasses.replace(result, delta=0.5)
        with self.assertRaisesRegex(ValueError, "response is invalid"):
            dataclasses.replace(result, gamma=decimal.Decimal("-0.1"))

    @unittest.skipUnless(
        importlib.util.find_spec("pandas") is not None,
        "optional pandas dependency is not installed",
    )
    def test_actual_pandas_numpy_rows_are_supported(self):
        import numpy
        import pandas

        row = dict(SyntheticQuoteClient().chain_rows[0])
        row["volume"] = numpy.int64(row["volume"])
        row["open_interest"] = numpy.int64(row["open_interest"])
        row["last_timestamp"] = numpy.int64(row["last_timestamp"])
        row["implied_vol"] = numpy.float64(row["implied_vol"])

        class PandasClient(SyntheticQuoteClient):
            def get_option_chain(self, symbol, expiry, **kwargs):
                self.calls.append(("chain", symbol, expiry, kwargs))
                return pandas.DataFrame([row])

        result = self.retrieve(PandasClient())
        self.assertEqual(result.open_interest, 456)


if __name__ == "__main__":
    unittest.main()
