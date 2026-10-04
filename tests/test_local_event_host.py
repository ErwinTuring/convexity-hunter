import contextlib
import datetime
import io
import unittest
from unittest.mock import Mock, patch

from convexity_hunter.option_chain_discovery import OptionMaturityAuthority

from examples import local_event_host


class LocalEventHostTests(unittest.TestCase):
    def setUp(self):
        self.config_path = "/outside/event-config.json"
        self.db_path = "/outside/event.sqlite3"
        self.store = Mock()
        self.server = Mock()
        self.server.server_port = 9234
        self.renderer = Mock(name="renderer")
        self.config = Mock(name="typed-config")
        self.grounder = Mock(name="event-grounder")
        self.executor = Mock(name="core-executor")
        self.bridge = Mock(name="market-bridge")
        self.quote_factory = None
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.load_config = self.stack.enter_context(
            patch.object(local_event_host, "load_event_grounder_config", return_value=self.config)
        )
        self.make_grounder = self.stack.enter_context(
            patch.object(local_event_host, "create_event_grounder", return_value=self.grounder)
        )
        self.make_executor = self.stack.enter_context(
            patch.object(local_event_host, "create_event_core_executor", return_value=self.executor)
        )
        bridge_factory = self.stack.enter_context(
            patch.object(local_event_host, "FutuMarketBridge", side_effect=self._bridge_factory)
        )
        self.bridge_factory = bridge_factory
        self.open_quote = self.stack.enter_context(
            patch.object(local_event_host.host_server, "_open_suppressed_futu_quote_context")
        )
        self.open_store = self.stack.enter_context(
            patch.object(local_event_host.host_server, "_open_store", return_value=self.store)
        )
        self.load_renderer = self.stack.enter_context(
            patch.object(local_event_host.host_server, "_load_workbench_renderer", return_value=self.renderer)
        )
        self.create_server = self.stack.enter_context(
            patch.object(local_event_host.host_server, "create_server", return_value=self.server)
        )

    def _bridge_factory(self, *, quote_context_factory):
        self.quote_factory = quote_context_factory
        return self.bridge

    def _args(self, *extra):
        return [
            "--event-config", self.config_path,
            "--evaluation-date", "2026-10-04",
            "--maturity-authority", "neutral_structural_research",
            "--futu-port", "4567",
            "--db", self.db_path,
            *extra,
        ]

    def test_explicit_configuration_is_forwarded_and_market_open_is_lazy(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(local_event_host.main(self._args("--port", "9123")), 0)

        self.load_config.assert_called_once_with(
            local_event_host.Path(self.config_path), repo_root=local_event_host._REPO_ROOT
        )
        self.make_grounder.assert_called_once_with(
            self.config, repo_root=local_event_host._REPO_ROOT
        )
        self.make_executor.assert_called_once_with(
            evaluation_date=datetime.date(2026, 10, 4),
            maturity_authority=OptionMaturityAuthority.NEUTRAL_STRUCTURAL_RESEARCH,
            market_bridge=self.bridge,
        )
        self.open_store.assert_called_once_with(local_event_host.Path(self.db_path))
        self.create_server.assert_called_once_with(
            self.store,
            render_workbench=self.renderer,
            event_grounder=self.grounder,
            event_core_executor=self.executor,
            port=9123,
        )
        self.assertEqual(self.bridge_factory.call_count, 1)
        self.open_quote.assert_not_called()
        self.quote_factory()
        self.open_quote.assert_called_once_with(4567)
        self.server.server_close.assert_called_once_with()
        self.store.close.assert_called_once_with()

    def test_port_defaults_only_to_existing_host_constant(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(local_event_host.main(self._args()), 0)
        self.assertEqual(
            self.create_server.call_args.kwargs["port"],
            local_event_host.host_server.DEFAULT_PORT,
        )

    def test_invalid_date_and_enum_fail_before_configuration_or_clients(self):
        for changed in (
            ("--evaluation-date", "2026-2-04"),
            ("--maturity-authority", "invented"),
        ):
            args = self._args()
            args[args.index(changed[0]) + 1] = changed[1]
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                self.assertEqual(local_event_host.main(args), 2)
            self.assertEqual(stderr.getvalue(), "local Event Host startup failed\n")
            self.load_config.assert_not_called()
            self.make_grounder.assert_not_called()
            self.make_executor.assert_not_called()
            self.open_store.assert_not_called()
            self.bridge_factory.assert_not_called()

    def test_keyboard_interrupt_and_startup_errors_close_owned_resources(self):
        self.server.serve_forever.side_effect = KeyboardInterrupt
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(local_event_host.main(self._args()), 0)
        self.server.server_close.assert_called_once_with()
        self.store.close.assert_called_once_with()

    def test_server_runtime_error_is_static_and_closes_owned_resources(self):
        self.server.serve_forever.side_effect = RuntimeError("sensitive detail")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(local_event_host.main(self._args()), 2)
        self.assertEqual(stderr.getvalue(), "local Event Host startup failed\n")
        self.server.server_close.assert_called_once_with()
        self.store.close.assert_called_once_with()

    def test_server_creation_error_closes_store_without_exposing_exception(self):
        self.create_server.side_effect = OSError("/private/path")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(local_event_host.main(self._args()), 2)
        self.assertEqual(stderr.getvalue(), "local Event Host startup failed\n")
        self.store.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
