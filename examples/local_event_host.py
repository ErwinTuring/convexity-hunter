#!/usr/bin/env python3
"""Experimental wiring; default preparation preserves unknowns, not full Grounder,
event-date/listing resolution, or real acceptance/completion.
"""

import argparse
import datetime
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from convexity_hunter import host_server
from convexity_hunter.core_futu import FutuMarketBridge
from convexity_hunter.host_event import create_event_grounder
from convexity_hunter.host_event_config import load_event_grounder_config
from convexity_hunter.host_event_core import create_event_core_executor
from convexity_hunter.option_chain_discovery import OptionMaturityAuthority


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, _message):
        raise ValueError("invalid arguments") from None


def _exact_iso_date(value):
    try:
        parsed = datetime.date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("evaluation date must be YYYY-MM-DD") from None
    return parsed


def _parser():
    parser = _ArgumentParser(description="Run the experimental local Event Host.")
    parser.add_argument("--event-config", required=True, type=Path)
    parser.add_argument("--evaluation-date", required=True, type=_exact_iso_date)
    parser.add_argument("--maturity-authority", required=True,
                        choices=tuple(a.value for a in OptionMaturityAuthority))
    parser.add_argument("--futu-port", required=True, type=host_server._positive_cli_port)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument(
        "--port", type=host_server._positive_cli_port, default=host_server.DEFAULT_PORT
    )
    return parser


def main(argv=None):
    store = server = None
    try:
        args = _parser().parse_args(argv)
        maturity_authority = OptionMaturityAuthority(args.maturity_authority)
        config = load_event_grounder_config(args.event_config, repo_root=_REPO_ROOT)
        market_bridge = FutuMarketBridge(
            quote_context_factory=lambda: host_server._open_suppressed_futu_quote_context(
                args.futu_port
            )
        )
        event_grounder = create_event_grounder(config, repo_root=_REPO_ROOT)
        event_core_executor = create_event_core_executor(
            evaluation_date=args.evaluation_date,
            maturity_authority=maturity_authority,
            market_bridge=market_bridge,
        )
        store = host_server._open_store(args.db)
        server = host_server.create_server(
            store,
            render_workbench=host_server._load_workbench_renderer(),
            event_grounder=event_grounder,
            event_core_executor=event_core_executor,
            port=args.port,
        )
        print("Experimental local Event Host: http://127.0.0.1:{}".format(server.server_port))
        server.serve_forever()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("local Event Host startup failed", file=sys.stderr)
        return 2
    finally:
        if server is not None:
            try:
                server.server_close()
            except Exception:
                pass
        if store is not None:
            try:
                store.close()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
