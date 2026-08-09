"""Synthetic tests for the local Tiger runtime boundary."""

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
    def test_exact_two_name_api_and_no_root_or_package_reexport(self):
        self.assertEqual(
            tiger.__all__,
            (
                "resolve_tiger_config_path",
                "initialize_tiger_quote_client",
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


if __name__ == "__main__":
    unittest.main()
