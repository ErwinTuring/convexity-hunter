"""Synthetic tests for the bounded Tiger provider boundary."""

import dataclasses
import datetime
import decimal
import logging
import importlib.util
import os
import pathlib
import stat
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import convexity_hunter
from convexity_hunter.market_data import (
    NormalizationQualityFlag,
    OptionContractReference,
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
    def test_exact_six_name_api_and_no_root_or_package_reexport(self):
        self.assertEqual(
            tiger.__all__,
            (
                "resolve_tiger_config_path",
                "initialize_tiger_quote_client",
                "TigerExactOptionContractVerification",
                "TigerExactOptionQuoteEvidence",
                "verify_tiger_monthly_option_contract",
                "retrieve_tiger_exact_option_quote_evidence",
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
    def __init__(self, expiration_rows=None, chain_rows=None, permissions=None):
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


if __name__ == "__main__":
    unittest.main()
