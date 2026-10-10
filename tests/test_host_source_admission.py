"""Offline security and parsing tests for bounded Host source admission."""

import datetime
import hashlib
import os
import socket
import ssl
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from convexity_hunter import host_source_admission as admission
from convexity_hunter.host_source_admission import (
    MAX_SOURCE_ADMISSION_REDIRECTS,
    MAX_SOURCE_ADMISSION_REQUESTS,
    _PinnedHTTPSConnection,
    _Reply,
    _SourceAdmissionClient,
    _family_target,
    _nasdaq_html,
    _revalidate_source_admission,
    _sec_html,
    _source_id_for_locator,
    _yahoo_html,
)


SEC_PATH = "/Archives/edgar/data/320193/000032019326000123/example.htm"
SEC_LOCATOR = "https://www.sec.gov" + SEC_PATH
SEC_REDIRECT_LOCATOR = "https://sec.gov" + SEC_PATH
SEC_REFERENCE_LOCATOR = "https://www.sec.gov/files/company_tickers_exchange.json"
NASDAQ_LOCATOR = "https://www.nasdaq.com/market-activity/stocks/acme"
YAHOO_LOCATOR = "https://finance.yahoo.com/quote/ACME/"
NOW = datetime.datetime(2026, 10, 7, 8, 30, tzinfo=datetime.timezone.utc)

SEC_HTML = b"""<!doctype html><html><body>
<p>ACME HOLDINGS, INC.</p>
<p>(Exact name of registrant as specified in its charter)</p>
<p>A synthetic event was reported.</p>
<p>On October 3, 2026, ACME HOLDINGS, INC. completed its acquisition of Example Corp.</p>
<table>
<tr><th>Title of each class</th><th>Trading Symbol(s)</th><th>Name of each exchange on which registered</th></tr>
<tr><td>Ordinary shares, no par value</td><td>ACME</td><td>The Nasdaq Stock Market LLC</td></tr>
</table></body></html>"""
NASDAQ_HTML = (
    b"<!doctype html><html><body><h1>ACME HOLDINGS, INC. Ordinary Shares (ACME)</h1></body></html>"
)
YAHOO_HTML = (
    "<!doctype html><html><body><div>NasdaqGS - Delayed Quote&#8226;USD</div>"
    "<h1>ACME HOLDINGS, INC. (ACME)</h1></body></html>"
).encode("utf-8")
SEC_REFERENCE_BODY = (
    '{ "fields" : ["cik","name","ticker","exchange"], "data" : [\n'
    ' [1093691, "Plug Power\\u0020Inc.", "PLUG", "Nasdaq"],\n'
    ' [123456, "Götv Holdings", "GOTV", null],\n'
    ' [77, "A & <Éxample>", "ACME", "Nasdaq"]\n'
    '] }\n'
)


class _ResponseTransport:
    def __init__(self, replies):
        self.replies = {url: list(items) for url, items in replies.items()}
        self.calls = []

    def __call__(self, locator, address, timeout, max_bytes):
        self.calls.append((locator, address, timeout, max_bytes))
        rows = self.replies.get(locator, [])
        if not rows:
            raise OSError("synthetic transport exhausted")
        return rows.pop(0)


def _ok(body, content_type="text/html; charset=UTF-8"):
    return _Reply(200, {"Content-Type": content_type}, body)


def _reference_ok(body, content_type="application/json"):
    if type(body) is str:
        body = body.encode("utf-8")
    return _Reply(200, {"Content-Type": content_type}, body)


def _sec_html_with_cover_text(title, exchange):
    return SEC_HTML.replace(
        b"Ordinary shares, no par value", title.encode("ascii")
    ).replace(b"The Nasdaq Stock Market LLC", exchange.encode("ascii"))


def _sec_layout_v3_html(
    width=5,
    *,
    header_cells=None,
    data_rows=None,
    duplicate_tables=1,
    issuer="Example&nbsp;Holdings, Inc.",
    marker="(Exact&nbsp;name of registrant as specified in its charter)",
):
    field_indices = (0, 1, 2) if width == 3 else (0, 2, 4) if width >= 5 else (0, 1, 2)
    if header_cells is None:
        header_cells = ["&nbsp;" if index not in field_indices else "" for index in range(width)]
        labels = (
            "Title&nbsp;of<br>each class",
            "Trading Symbol(s)",
            "Name of each exchange on which registered",
        )
        for index, label in zip(field_indices, labels):
            header_cells[index] = label
    if data_rows is None:
        values = ["&nbsp;" if index not in field_indices else "" for index in range(width)]
        for index, value in zip(
            field_indices,
            ("Common&nbsp;Stock", "ACME", "The&nbsp;Nasdaq Capital Market"),
        ):
            values[index] = value
        data_rows = (values,)

    def table_markup():
        header = "<tr>{}</tr>".format(
            "".join("<th>{}</th>".format(value) for value in header_cells)
        )
        rows = "".join(
            "<tr>{}</tr>".format(
                "".join("<td>{}</td>".format(value) for value in row)
            )
            for row in data_rows
        )
        return "<table>{}{}</table>".format(header, rows)

    return (
        "<html><body><p>{}</p><p>{}</p><p>An event\u00a0was reported.</p>{}</body></html>"
    ).format(issuer, marker, table_markup() * duplicate_tables).encode("utf-8")


def _sec_layout_v4_html(
    *,
    issuer="Example Holdings, Inc.",
    marker="(Exact name of registrant as specified in its charter)",
    title="Common Stock",
    exchange="Nasdaq Capital Market",
    spacer="&nbsp;",
    duplicate_tables=1,
    trailing="",
):
    def table_markup():
        return (
            "<table><tr><th>Title of each class</th><th>{}</th>"
            "<th>Trading Symbol(s)</th><th>{}</th>"
            "<th>Name of each exchange on which registered</th></tr>"
            "<tr><td>{}</td><td>{}</td><td>ACME</td><td>{}</td>"
            "<td>{}</td></tr></table>"
        ).format(spacer, spacer, title, spacer, spacer, exchange)

    return (
        "<html><body><p>{}</p><p>{}</p>"
        "<p>A visible\t narrative\nstays&nbsp;literal.</p>{}{}"
        "</body></html>"
    ).format(issuer, marker, table_markup() * duplicate_tables, trailing).encode("utf-8")


def _client(transport, *, resolver=None, max_bytes=100_000, byte_budget=500_000):
    return _SourceAdmissionClient(
        timeout_seconds=2.5,
        max_response_bytes=max_bytes,
        byte_budget=byte_budget,
        _transport=transport,
        _resolver=resolver or (lambda _host, _port: ("93.184.216.34",)),
        _clock=lambda: NOW,
    )


class _NoopTimer:
    def __init__(self, *_args, **_kwargs):
        self.daemon = False

    def start(self):
        pass

    def cancel(self):
        pass

    def join(self, timeout=None):
        pass


def _capture_user_agent(locator):
    captured = {}

    class _Response:
        status = 403

        def getheaders(self):
            return []

    class _Connection:
        def __init__(self, *_args, **_kwargs):
            pass

        def abort(self):
            pass

        def request(self, _method, _target, headers):
            captured.update(headers)

        def getresponse(self):
            return _Response()

        def close(self):
            pass

    with patch.object(admission, "_PinnedHTTPSConnection", _Connection), patch.object(
        admission.threading, "Timer", _NoopTimer
    ):
        admission._fetch_response(locator, "93.184.216.34", 1.0, 1024)
    return captured["User-Agent"]


def _write_user_agent(path, contents, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    path.chmod(mode)
    return path


def _production_client():
    return _SourceAdmissionClient(
        timeout_seconds=2.5,
        max_response_bytes=100_000,
        byte_budget=500_000,
        _resolver=lambda _host, _port: ("93.184.216.34",),
        _clock=lambda: NOW,
    )


class HostSourceAdmissionTests(unittest.TestCase):
    def setUp(self):
        self._synthetic_home = tempfile.TemporaryDirectory()
        self.addCleanup(self._synthetic_home.cleanup)
        home_patch = patch(
            "pathlib.Path.home", return_value=Path(self._synthetic_home.name)
        )
        home_patch.start()
        self.addCleanup(home_patch.stop)
        environment_patch = patch.dict(os.environ)
        environment_patch.start()
        self.addCleanup(environment_patch.stop)
        self._synthetic_contact_path = (
            Path(self._synthetic_home.name) / "missing-sec-user-agent.txt"
        )
        os.environ[admission._SEC_USER_AGENT_FILE_ENV] = str(
            self._synthetic_contact_path
        )
        self.assertFalse(self._synthetic_contact_path.exists())

    def test_private_sec_contact_user_agent_is_only_read_for_sec(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write_user_agent(
                Path(directory) / "sec-user-agent.txt",
                b"ConvexityHunter synthetic@example.test\n",
            )
            _write_user_agent(
                Path(directory) / admission._SEC_USER_AGENT_DEFAULT_RELATIVE_PATH,
                b"ConvexityHunter default@example.test",
            )
            with patch("pathlib.Path.home", return_value=Path(directory)):
                with patch.dict(
                    os.environ, {admission._SEC_USER_AGENT_FILE_ENV: str(path)}
                ):
                    with patch.object(
                        admission, "_sec_user_agent", wraps=admission._sec_user_agent
                    ) as read_contact:
                        sec = _capture_user_agent(SEC_LOCATOR)
                        sec_alias = _capture_user_agent(SEC_REDIRECT_LOCATOR)
                        nasdaq = _capture_user_agent(NASDAQ_LOCATOR)
                        yahoo = _capture_user_agent(YAHOO_LOCATOR)
            self.assertEqual(sec, "ConvexityHunter synthetic@example.test")
            self.assertEqual(sec_alias, "ConvexityHunter synthetic@example.test")
            self.assertEqual(nasdaq, admission._SEC_USER_AGENT_LEGACY)
            self.assertEqual(yahoo, admission._SEC_USER_AGENT_LEGACY)
            self.assertEqual(read_contact.call_count, 2)

    def test_missing_contact_file_keeps_legacy_user_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("pathlib.Path.home", return_value=Path(directory)):
                with patch.dict(os.environ):
                    os.environ.pop(admission._SEC_USER_AGENT_FILE_ENV, None)
                    self.assertEqual(
                        _capture_user_agent(SEC_LOCATOR),
                        admission._SEC_USER_AGENT_LEGACY,
                    )

    def _assert_sec_configuration_fails_closed(self, path, secret=None):
        with tempfile.TemporaryDirectory() as home:
            with patch("pathlib.Path.home", return_value=Path(home)):
                with patch.dict(
                    os.environ, {admission._SEC_USER_AGENT_FILE_ENV: str(path)}
                ):
                    with patch.object(admission, "_PinnedHTTPSConnection") as connection:
                        result = _production_client().admit_candidates((SEC_LOCATOR,))
        self.assertEqual(connection.call_count, 0)
        self.assertEqual(result.admissions, ())
        self.assertEqual(result.failures[0].code, "TRANSPORT_FAILED")
        if secret is not None:
            self.assertNotIn(secret, repr(result))
            self.assertNotIn(secret, str(result))

    def test_crlf_injection_is_rejected_without_echoing_file_text(self):
        secret = "synthetic-secret-marker"
        with tempfile.TemporaryDirectory() as directory:
            path = _write_user_agent(
                Path(directory) / "sec-user-agent.txt",
                ("ConvexityHunter synthetic@example.test\r\nX-Injected: " + secret + "\r\n").encode("ascii"),
            )
            self._assert_sec_configuration_fails_closed(path, secret=secret)

    def test_invalid_contact_header_is_rejected_without_echoing_file_text(self):
        secret = "synthetic-secret-marker"
        with tempfile.TemporaryDirectory() as directory:
            path = _write_user_agent(
                Path(directory) / "sec-user-agent.txt",
                ("ConvexityHunter " + secret).encode("ascii"),
            )
            self._assert_sec_configuration_fails_closed(path, secret=secret)

    def test_relative_explicit_contact_path_is_rejected(self):
        self._assert_sec_configuration_fails_closed(Path("relative-contact-file"))

    def test_repository_target_through_external_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            link = Path(directory) / "sec-user-agent.txt"
            link.symlink_to(Path(__file__).resolve())
            self._assert_sec_configuration_fails_closed(link)

    def test_group_or_other_read_permission_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _write_user_agent(
                Path(directory) / "sec-user-agent.txt",
                b"ConvexityHunter synthetic@example.test",
                mode=0o644,
            )
            self._assert_sec_configuration_fails_closed(path)

    def test_private_fifo_contact_file_fails_without_request(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sec-user-agent.fifo"
            os.mkfifo(path, 0o600)
            path.chmod(0o600)
            started = time.monotonic()
            self._assert_sec_configuration_fails_closed(path)
            self.assertLess(time.monotonic() - started, 1.0)

    def test_exact_targets_accept_realistic_tickers_paths_and_headings(self):
        self.assertEqual(_family_target(SEC_LOCATOR)[0], "sec")
        self.assertEqual(_family_target(NASDAQ_LOCATOR)[2][0], "ACME")
        self.assertEqual(_family_target(YAHOO_LOCATOR)[2][0], "ACME")
        self.assertTrue(_family_target("https://www.nasdaq.com/market-activity/stocks/brk-b"))
        self.assertIsNone(_family_target("https://www.sec.gov/Archives/edgar/data/1/abc/../x.htm"))

        sec = _sec_html(SEC_HTML.decode("utf-8"))
        nasdaq = _nasdaq_html(NASDAQ_HTML.decode("utf-8"), "ACME")
        yahoo = _yahoo_html(YAHOO_HTML.decode("utf-8"), "ACME")
        self.assertEqual(sec.symbol, "ACME")
        self.assertIn("On October 3, 2026", sec.body)
        self.assertIn("| Ordinary shares, no par value | ACME | The Nasdaq Stock Market LLC |", sec.body)
        self.assertNotIn("CONFORMED SUBMISSION TYPE", sec.body)
        script_polluted = SEC_HTML.replace(
            b"<body>",
            b"<body><script>FAKE EVENT TEXT; (Exact name of registrant as specified in its charter)</script>",
        )
        script_parsed = _sec_html(script_polluted.decode("utf-8"))
        self.assertIsNotNone(script_parsed)
        self.assertNotIn("FAKE EVENT TEXT", script_parsed.body)
        self.assertEqual(nasdaq.body, "# ACME HOLDINGS, INC. Ordinary Shares (ACME)\n")
        self.assertEqual(yahoo.body, "NasdaqGS - Delayed Quote•USD\n\n# ACME HOLDINGS, INC. (ACME)\n")
        unsupported_common_stock = SEC_HTML.replace(
            b"Ordinary shares, no par value", b"Common Stock"
        )
        text_admitted = _sec_html(unsupported_common_stock.decode("utf-8"))
        self.assertIsNotNone(text_admitted)
        self.assertEqual(text_admitted.parser_id, "sec-edgar-cover-text-v2")
        self.assertEqual(text_admitted.symbol, "ACME")

    def test_sec_cover_text_v2_ascii_markdown_safety_and_cell_boundaries(self):
        maximum = _sec_html_with_cover_text("C" * 256, "E" * 256)
        parsed = _sec_html(maximum.decode("utf-8"))
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.parser_id, "sec-edgar-cover-text-v2")
        self.assertEqual(parsed.symbol, "ACME")

        for title, exchange in (
            ("Common Stock, par value $0.01 per share", "Nasdaq Capital Market"),
            ("Ordinary Common Stock (class)", "Nasdaq Capital Market!"),
            ("Common" + (" " * 300) + "Stock", "Nasdaq Capital Market"),
            ("Class A & B", "Nasdaq Capital Market"),
        ):
            with self.subTest(accepted_title=title):
                candidate = _sec_html_with_cover_text(title, exchange)
                parsed = _sec_html(candidate.decode("utf-8"))
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.parser_id, "sec-edgar-cover-text-v2")

        rejected = (
            ("", "Nasdaq Capital Market"),
            ("Common Stock", ""),
            (" " * 3, "Nasdaq Capital Market"),
            ("C" * 257, "Nasdaq Capital Market"),
            ("Common Stock", "E" * 257),
            ("Common\tStock", "Nasdaq Capital Market"),
            ("Common Stock", "Nasdaq\nCapital Market"),
            ("Common|Stock", "Nasdaq Capital Market"),
            ("Common Stock", "Nasdaq|Capital Market"),
            ("Common *Stock*", "Nasdaq Capital Market"),
            ("Common Stock", "Nasdaq &lt;Capital&gt; Market"),
        )
        for title, exchange in rejected:
            with self.subTest(title=title, exchange=exchange):
                candidate = _sec_html_with_cover_text(title, exchange)
                self.assertIsNone(_sec_html(candidate.decode("utf-8")))

    def test_sec_cover_text_v2_folds_only_parser_generated_paragraph_boundaries(self):
        candidate = _sec_html_with_cover_text(
            "<p>Common<br>Stock</p>",
            "<p>Nasdaq<br>Capital Market</p>",
        ).replace(b"\n", b"")
        self.assertFalse(any(byte < 0x20 or byte == 0x7F for byte in candidate))
        parsed = _sec_html(candidate.decode("utf-8"))
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.parser_id, "sec-edgar-cover-text-v2")
        self.assertIn(
            "| Common Stock | ACME | Nasdaq Capital Market |", parsed.body
        )
        raw_text = candidate.decode("utf-8")
        value_anchor = next(
            anchor for anchor in parsed.anchors if anchor.field == "sec_cover.value.0"
        )
        raw_excerpt = raw_text[value_anchor.raw_start:value_anchor.raw_end]
        self.assertIn("<p>Common<br>Stock", raw_excerpt)
        self.assertEqual(
            value_anchor.raw_sha256,
            hashlib.sha256(raw_excerpt.encode("utf-8")).hexdigest(),
        )

    def test_sec_cover_text_v2_still_rejects_raw_and_entity_decoded_linefeeds(self):
        for title in ("Common\nStock", "Common&#10;Stock"):
            with self.subTest(title=title):
                candidate = _sec_html_with_cover_text(title, "Nasdaq Capital Market")
                self.assertIsNone(_sec_html(candidate.decode("utf-8")))

    def test_sec_cover_text_v2_keeps_single_visible_cover_row_grammar(self):
        candidate = _sec_html_with_cover_text("Common Stock", "Nasdaq Capital Market")
        table_start = candidate.index(b"<table>")
        table_end = candidate.index(b"</table>", table_start) + len(b"</table>")
        table = candidate[table_start:table_end]
        duplicate_table = candidate.replace(table, table + table, 1)
        multirow = candidate.replace(
            b"</tr>\n</table>",
            b"</tr><tr><td>Preferred Stock</td><td>ACME</td>"
            b"<td>Nasdaq Capital Market</td></tr>\n</table>",
            1,
        )
        hidden_table = candidate.replace(b"<table>", b'<table hidden="false">', 1)
        for label, malformed in (
            ("duplicate-table", duplicate_table),
            ("multirow", multirow),
            ("hidden-table", hidden_table),
        ):
            with self.subTest(shape=label):
                self.assertIsNone(_sec_html(malformed.decode("utf-8")))

    def test_hidden_sec_cover_table_and_event_descendants_are_excluded(self):
        raw = SEC_HTML.decode("utf-8")
        attributes = (
            "hidden", 'hidden="false"', 'aria-hidden=" \tTRUE\r\n"',
            'style=" DISPLAY\t:\nNONE !IMPORTANT ; color:red"',
            'style="visibility : HIDDEN"',
            'style=" Visibility : collapse ! important "',
        )
        for attrs in attributes:
            with self.subTest(attrs=attrs):
                self.assertIsNone(_sec_html(raw.replace("<table>", "<table " + attrs + ">")))
                hidden_event = raw.replace(
                    "<p>A synthetic event was reported.</p>",
                    "<div " + attrs + "><p><span>HIDDEN SEC EVENT</span></p></div>",
                )
                parsed = _sec_html(hidden_event)
                self.assertIsNotNone(parsed)
                self.assertNotIn("HIDDEN SEC EVENT", parsed.body)
                self.assertIn("On October 3, 2026", parsed.body)
        visible = _sec_html(raw.replace("<table>", '<table aria-hidden="false" style="display:table">'))
        self.assertEqual(visible.symbol, "ACME")
        self.assertIn("A synthetic event was reported.", visible.body)

    def test_hidden_yahoo_usd_is_not_admitted_as_visible_denomination(self):
        raw = YAHOO_HTML.decode("utf-8")
        for attrs in (
            "hidden", 'aria-hidden="true"', 'style="display : NONE !important"',
            'style="VISIBILITY : hidden !IMPORTANT"', 'style="visibility:collapse"',
        ):
            with self.subTest(attrs=attrs):
                self.assertIsNone(_yahoo_html(raw.replace("USD", "<span " + attrs + "><b>USD</b></span>"), "ACME"))
        visible = raw.replace("USD", '<span aria-hidden="false" style="visibility:visible">USD</span>')
        self.assertEqual(_yahoo_html(visible, "ACME").body, _yahoo_html(raw, "ACME").body)

    def test_hidden_void_elements_leave_following_visible_evidence_intact(self):
        raw = SEC_HTML.decode("utf-8")
        for element in ('<input hidden>', '<br aria-hidden="true">', '<img style="display:none"/>'):
            with self.subTest(element=element):
                parsed = _sec_html(raw.replace("<body>", "<body>" + element))
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed.symbol, "ACME")
                self.assertIn("A synthetic event was reported.", parsed.body)
                self.assertIn("On October 3, 2026", parsed.body)

    def test_target_validation_rejects_ambiguous_or_out_of_scope_urls(self):
        bad = (
            "http://www.sec.gov" + SEC_PATH,
            "https://user@www.sec.gov" + SEC_PATH,
            "https://www.sec.gov:8443" + SEC_PATH,
            SEC_LOCATOR + "?download=1",
            SEC_LOCATOR + "#section",
            "https://www.sec.gov/Archives/edgar/data/320193/%2e%2e/example.htm",
            "https://www.sec.gov.evil.example" + SEC_PATH,
            "https://www.nasdaq.com/market-activity/stocks/ACME/../quote",
            "https://finance.yahoo.com/quote/ACME/?guccounter=1",
        )
        for locator in bad:
            with self.subTest(locator=locator):
                self.assertIsNone(_family_target(locator))

    def test_tls_context_verifies_certificate_and_socket_uses_origin_sni(self):
        connection = _PinnedHTTPSConnection("www.sec.gov", "93.184.216.34", 3.0)
        self.assertTrue(connection._context.check_hostname)
        self.assertEqual(connection._context.verify_mode, ssl.CERT_REQUIRED)

        raw_socket = Mock()
        wrapped_socket = Mock()
        context = Mock()
        context.wrap_socket.return_value = wrapped_socket
        wrapped_socket.do_handshake.side_effect = lambda: self.assertIs(
            connection.sock, wrapped_socket
        )
        connection._context = context
        with patch("convexity_hunter.host_source_admission.socket.create_connection", return_value=raw_socket) as connect:
            connection.connect()
        connect.assert_called_once_with(("93.184.216.34", 443), 3.0)
        context.wrap_socket.assert_called_once_with(
            raw_socket,
            server_hostname="www.sec.gov",
            do_handshake_on_connect=False,
        )
        wrapped_socket.settimeout.assert_called_once_with(3.0)
        wrapped_socket.do_handshake.assert_called_once_with()
        self.assertIs(connection.sock, wrapped_socket)
        connection.close()

    def test_private_or_mixed_dns_answers_fail_before_transport(self):
        for addresses in (("127.0.0.1",), ("93.184.216.34", "169.254.169.254"), ("::1",)):
            with self.subTest(addresses=addresses):
                transport = _ResponseTransport({SEC_LOCATOR: [_ok(SEC_HTML)]})
                client = _client(transport, resolver=lambda _host, _port: addresses)
                result = client.admit_candidates((SEC_LOCATOR,))
                self.assertEqual(result.admissions, ())
                self.assertEqual(result.failures[0].code, "DNS_ADDRESS_BLOCKED")
                self.assertEqual(result.request_count, 0)
                self.assertEqual(transport.calls, [])

    def test_slow_dns_is_daemonized_and_bounded(self):
        entered = threading.Event()
        release = threading.Event()
        threads = []
        real_thread = threading.Thread
        transport = _ResponseTransport({SEC_LOCATOR: [_ok(SEC_HTML)]})

        def slow_resolver(_host, _port):
            entered.set()
            release.wait(1.0)
            return ("93.184.216.34",)

        def thread_factory(*args, **kwargs):
            thread = real_thread(*args, **kwargs)
            threads.append(thread)
            return thread

        client = _SourceAdmissionClient(
            timeout_seconds=0.01,
            max_response_bytes=100_000,
            byte_budget=100_000,
            _transport=transport,
            _resolver=slow_resolver,
            _clock=lambda: NOW,
            _monotonic=time.monotonic,
        )
        started = time.monotonic()
        with patch("convexity_hunter.host_source_admission.threading.Thread", side_effect=thread_factory):
            try:
                result = client.admit_candidates((SEC_LOCATOR,))
            finally:
                release.set()
        for thread in threads:
            thread.join(timeout=1.0)
        elapsed = time.monotonic() - started
        self.assertTrue(entered.is_set())
        self.assertLess(elapsed, 0.5)
        self.assertEqual(result.admissions, ())
        self.assertEqual(result.failures[0].code, "DNS_RESOLUTION_FAILED")
        self.assertEqual(result.request_count, 0)
        self.assertEqual(transport.calls, [])
        self.assertEqual(len(threads), 1)
        self.assertTrue(threads[0].daemon)
        self.assertFalse(threads[0].is_alive())

    def test_monotonic_deadline_rejects_a_late_response_without_retry(self):
        now = [10.0]
        calls = []

        def transport(locator, address, timeout, max_bytes):
            calls.append((locator, address, timeout, max_bytes))
            now[0] = 10.06
            return _ok(SEC_HTML)

        client = _SourceAdmissionClient(
            timeout_seconds=0.01,
            max_response_bytes=100_000,
            byte_budget=100_000,
            _transport=transport,
            _resolver=lambda _host, _port: ("93.184.216.34",),
            _clock=lambda: NOW,
            _monotonic=lambda: now[0],
        )
        result = client.admit_candidates((SEC_LOCATOR,))
        self.assertEqual(result.admissions, ())
        self.assertEqual(result.failures[0].code, "ADMISSION_DEADLINE_EXCEEDED")
        self.assertEqual(result.request_count, 1)
        self.assertEqual(len(calls), 1)
        self.assertLessEqual(calls[0][2], 0.01)

    def test_stalled_production_response_is_closed_by_wall_clock_watchdog(self):
        client_socket, peer_socket = socket.socketpair()
        connect_calls = []

        def stalled_connect(connection):
            connect_calls.append(connection)
            client_socket.settimeout(1.0)
            connection.sock = client_socket

        client = _SourceAdmissionClient(
            timeout_seconds=0.05,
            max_response_bytes=100_000,
            byte_budget=100_000,
            _resolver=lambda _host, _port: ("93.184.216.34",),
            _clock=lambda: NOW,
            _monotonic=time.monotonic,
        )
        started = time.monotonic()
        try:
            with patch.object(_PinnedHTTPSConnection, "connect", stalled_connect):
                result = client.admit_candidates((SEC_LOCATOR,))
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 0.5)
            self.assertEqual(result.admissions, ())
            self.assertEqual(result.failures[0].code, "TRANSPORT_FAILED")
            self.assertEqual(result.request_count, 1)
            self.assertEqual(len(connect_calls), 1)
            self.assertLess(client_socket.fileno(), 0)
        finally:
            client_socket.close()
            peer_socket.close()

    def test_redirect_revalidates_exact_target_and_retains_final_origin(self):
        transport = _ResponseTransport(
            {
                SEC_REDIRECT_LOCATOR: [
                    _Reply(302, {"Location": SEC_LOCATOR}, b"")
                ],
                SEC_LOCATOR: [_ok(SEC_HTML)],
            }
        )
        resolutions = []
        client = _client(
            transport,
            resolver=lambda host, _port: resolutions.append(host) or ("93.184.216.34",),
        )
        result = client.admit_candidates((SEC_REDIRECT_LOCATOR,))
        self.assertEqual(result.request_count, 4)
        self.assertEqual(resolutions[:2], ["sec.gov", "www.sec.gov"])
        self.assertEqual(len(result.admissions), 1)
        admitted = result.admissions[0]
        self.assertEqual(admitted.initial_locator, SEC_REDIRECT_LOCATOR)
        self.assertEqual(admitted.final_locator, SEC_LOCATOR)
        self.assertEqual(admitted.origin, "https://www.sec.gov")
        self.assertEqual(admitted.raw_body_sha256, hashlib.sha256(SEC_HTML).hexdigest())
        self.assertNotEqual(admitted.raw_body_sha256, admitted.parsed_body_sha256)
        self.assertEqual(admitted.raw_body_bytes, len(SEC_HTML))
        self.assertEqual(admitted.retrieved_at, NOW)
        self.assertEqual(admitted.content_type, "text/html")
        self.assertEqual(admitted.parser_id, "sec-edgar-cover-v1")
        self.assertEqual(admitted.parser_version, "1")
        self.assertIn("On October 3, 2026", admitted.parsed_body)
        for anchor in admitted.raw_anchors:
            raw_excerpt = SEC_HTML.decode("utf-8")[anchor.raw_start:anchor.raw_end]
            self.assertEqual(hashlib.sha256(raw_excerpt.encode("utf-8")).hexdigest(), anchor.raw_sha256)
            self.assertLessEqual(anchor.parsed_end, len(admitted.parsed_body))
        self.assertNotIn("<table>", repr(admitted))
        self.assertEqual(
            admitted.source_id,
            _source_id_for_locator(SEC_REDIRECT_LOCATOR),
        )

    def test_parsed_sec_cover_row_authorizes_only_its_ticker_supplements(self):
        transport = _ResponseTransport(
            {
                SEC_LOCATOR: [_ok(SEC_HTML)],
                NASDAQ_LOCATOR: [_ok(NASDAQ_HTML)],
                YAHOO_LOCATOR: [_ok(YAHOO_HTML)],
            }
        )
        result = _client(transport).admit_candidates((SEC_LOCATOR,))
        self.assertEqual(
            [admission.family for admission in result.admissions],
            ["sec", "nasdaq", "yahoo"],
        )
        self.assertEqual(
            [call[0] for call in transport.calls],
            [SEC_LOCATOR, NASDAQ_LOCATOR, YAHOO_LOCATOR],
        )
        self.assertEqual(result.request_count, 3)
        self.assertEqual(result.response_bytes, len(SEC_HTML) + len(NASDAQ_HTML) + len(YAHOO_HTML))
        self.assertEqual(result.admissions[1].parsed_symbol, "ACME")
        self.assertEqual(result.admissions[2].parsed_symbol, "ACME")

    def test_sec_text_v2_retains_ticker_without_auto_supplements_and_revalidates_exactly(self):
        raw_body = _sec_html_with_cover_text("Common Stock", "Nasdaq Capital Market")
        transport = _ResponseTransport(
            {
                SEC_LOCATOR: [_ok(raw_body)],
                NASDAQ_LOCATOR: [_ok(NASDAQ_HTML)],
                YAHOO_LOCATOR: [_ok(YAHOO_HTML)],
            }
        )
        result = _client(transport).admit_candidates((SEC_LOCATOR,))
        self.assertEqual(result.request_count, 1)
        self.assertEqual([call[0] for call in transport.calls], [SEC_LOCATOR])
        self.assertEqual(len(result.admissions), 1)
        admitted = result.admissions[0]
        self.assertEqual(admitted.parser_id, "sec-edgar-cover-text-v2")
        self.assertEqual(admitted.parser_version, "2")
        self.assertEqual(admitted.parsed_symbol, "ACME")
        self.assertEqual(admitted.raw_body_sha256, hashlib.sha256(raw_body).hexdigest())
        self.assertEqual(admitted.raw_body_bytes, len(raw_body))
        self.assertIsNotNone(
            _revalidate_source_admission(
                admitted, max_raw_bytes=100_000, max_parsed_bytes=100_000
            )
        )
        raw_text = raw_body.decode("utf-8")
        anchors_by_field = {anchor.field: anchor for anchor in admitted.raw_anchors}
        for field, expected in (
            ("sec_cover.value.0", "Common Stock"),
            ("sec_cover.value.2", "Nasdaq Capital Market"),
        ):
            anchor = anchors_by_field[field]
            excerpt = raw_text[anchor.raw_start:anchor.raw_end]
            self.assertEqual(excerpt, expected)
            self.assertEqual(
                anchor.raw_sha256, hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
            )

        for spoof in (
            replace(admitted, parser_id="sec-edgar-cover-v1"),
            replace(admitted, parser_version="1"),
            replace(admitted, parser_id="sec-edgar-cover-text-v9"),
        ):
            with self.subTest(parser_id=spoof.parser_id, version=spoof.parser_version):
                self.assertIsNone(
                    _revalidate_source_admission(
                        spoof, max_raw_bytes=100_000, max_parsed_bytes=100_000
                    )
                )

        nasdaq_transport = _ResponseTransport({NASDAQ_LOCATOR: [_ok(NASDAQ_HTML)]})
        nasdaq = _client(nasdaq_transport).admit_candidates((NASDAQ_LOCATOR,)).admissions[0]
        non_sec_v2 = replace(
            nasdaq, parser_id="sec-edgar-cover-text-v2", parser_version="2"
        )
        self.assertIsNone(
            _revalidate_source_admission(
                non_sec_v2, max_raw_bytes=100_000, max_parsed_bytes=100_000
            )
        )

        explicit_transport = _ResponseTransport(
            {
                SEC_LOCATOR: [_ok(raw_body)],
                NASDAQ_LOCATOR: [_ok(NASDAQ_HTML)],
                YAHOO_LOCATOR: [_ok(YAHOO_HTML)],
            }
        )
        explicit = _client(explicit_transport).admit_candidates(
            (SEC_LOCATOR, NASDAQ_LOCATOR, YAHOO_LOCATOR)
        )
        self.assertEqual(
            [call[0] for call in explicit_transport.calls],
            [SEC_LOCATOR, NASDAQ_LOCATOR, YAHOO_LOCATOR],
        )
        self.assertEqual(
            [item.family for item in explicit.admissions], ["sec", "nasdaq", "yahoo"]
        )

    def test_sec_reference_selects_only_requested_original_rows_in_caller_order(self):
        raw_body = SEC_REFERENCE_BODY.encode("utf-8")
        transport = _ResponseTransport(
            {SEC_REFERENCE_LOCATOR: [_reference_ok(raw_body)]}
        )
        client = _client(transport)
        result = client.admit_sec_reference(("ACME", "PLUG"))

        self.assertEqual(len(result.admissions), 1)
        self.assertEqual(result.failures, ())
        self.assertEqual([call[0] for call in transport.calls], [SEC_REFERENCE_LOCATOR])
        self.assertEqual(result.request_count, 1)
        self.assertEqual(result.response_bytes, len(raw_body))
        admitted = result.admissions[0]
        expected_body = (
            '{"fields":["cik","name","ticker","exchange"],"data":['
            '[77, "A & <Éxample>", "ACME", "Nasdaq"],'
            '[1093691, "Plug Power\\u0020Inc.", "PLUG", "Nasdaq"]]}'
        )
        self.assertEqual(admitted.family, "sec")
        self.assertEqual(admitted.content_type, "application/json")
        self.assertEqual(admitted.parser_id, "sec-issuer-reference-v1")
        self.assertEqual(admitted.parser_version, "1")
        self.assertIsNone(admitted.parsed_symbol)
        self.assertEqual(admitted.parsed_body, expected_body)
        self.assertEqual(admitted.parsed_body_sha256, hashlib.sha256(expected_body.encode("utf-8")).hexdigest())
        self.assertEqual(admitted.raw_body_sha256, hashlib.sha256(raw_body).hexdigest())
        self.assertEqual(admitted.raw_body_bytes, len(raw_body))
        self.assertEqual(
            [anchor.field for anchor in admitted.raw_anchors],
            ["sec_issuer_reference.data.ACME", "sec_issuer_reference.data.PLUG"],
        )
        self.assertEqual(
            [
                (
                    anchor.field,
                    anchor.raw_start,
                    anchor.raw_end,
                    anchor.raw_sha256,
                    anchor.parsed_start,
                    anchor.parsed_end,
                )
                for anchor in admitted.raw_anchors
            ],
            [
                (
                    "sec_issuer_reference.data.ACME",
                    158,
                    198,
                    "b4d0407c85ebb92cebec0c7731e7107b64e6d71f0e232e70a5756ae827af6b74",
                    53,
                    92,
                ),
                (
                    "sec_issuer_reference.data.PLUG",
                    61,
                    112,
                    "418fe022df71dd21f24d4796a1cf50369b3ec496259a3d5413c12e3e0894c197",
                    93,
                    144,
                ),
            ],
        )
        self.assertIsNone(
            _revalidate_source_admission(
                admitted, max_raw_bytes=len(raw_body), max_parsed_bytes=len(expected_body.encode("utf-8"))
            )
        )
        self.assertIsNotNone(
            client._revalidate_sec_reference(
                admitted, ("ACME", "PLUG"), max_parsed_bytes=len(expected_body.encode("utf-8"))
            )
        )

    def test_sec_reference_rejects_duplicate_missing_and_unselected_null_exchange(self):
        cases = (
            (
                '{"fields":["cik","name","ticker","exchange"],"data":'
                '[[1,"First","ACME","Nasdaq"],[2,"Second","ACME","NYSE"]]}',
                ("ACME",),
            ),
            (
                '{"fields":["cik","name","ticker","exchange"],"data":'
                '[[1,"Other","OTHER","Nasdaq"]]}',
                ("ACME",),
            ),
            (SEC_REFERENCE_BODY, ("GOTV",)),
        )
        for body, symbols in cases:
            with self.subTest(symbols=symbols, body=body[:70]):
                transport = _ResponseTransport(
                    {SEC_REFERENCE_LOCATOR: [_reference_ok(body)]}
                )
                result = _client(transport).admit_sec_reference(symbols)
                self.assertEqual(result.admissions, ())
                self.assertEqual(result.failures[0].code, "PARSER_UNSUPPORTED")
                self.assertEqual(result.request_count, 1)

    def test_sec_reference_validates_exact_positive_cik_on_every_row(self):
        invalid_ciks = ("true", "1.0", "1e400", "-1", "10000000000", "0")
        for cik in invalid_ciks:
            body = (
                '{"fields":["cik","name","ticker","exchange"],"data":['
                '[1,"Issuer","ACME","Nasdaq"],'
                '[CIK,"Unselected","OTHER",null]]}'
            ).replace("CIK", cik)
            with self.subTest(cik=cik):
                transport = _ResponseTransport(
                    {SEC_REFERENCE_LOCATOR: [_reference_ok(body)]}
                )
                result = _client(transport).admit_sec_reference(("ACME",))
                self.assertEqual(result.admissions, ())
                self.assertEqual(result.failures[0].code, "PARSER_UNSUPPORTED")

    def test_sec_reference_strict_json_and_root_schema_fail_closed(self):
        cases = (
            (
                '{"fields":["cik","name","ticker","exchange"],'
                '"fields":["cik","name","ticker","exchange"],"data":[]}'
            ),
            (
                '{"fields":["cik","name","ticker","exchange"],"data":'
                '[[1,"Issuer","ACME",NaN]]}'
            ),
            (
                '{"data":[],"fields":["cik","name","ticker","exchange"]}'
            ),
            (
                '{"fields":["cik","name","ticker","exchange"],"data":[],'
                '"extra":true}'
            ),
            (
                '{"fields":["cik","name","ticker","exchange"],"data":'
                '[[1,"Issuer","ACME"]]}'
            ),
        )
        for body in cases:
            with self.subTest(body=body):
                transport = _ResponseTransport(
                    {SEC_REFERENCE_LOCATOR: [_reference_ok(body)]}
                )
                result = _client(transport).admit_sec_reference(("ACME",))
                self.assertEqual(result.admissions, ())
                self.assertEqual(result.failures[0].code, "PARSER_UNSUPPORTED")

    def test_sec_reference_safe_strings_preserve_unicode_and_reject_controls_or_surrogates(self):
        bad_rows = (
            '[1,"Issuer\\u0000Name","ACME","Nasdaq"]',
            '[1,"Issuer\\ud800","ACME","Nasdaq"]',
            '[1,"Issuer","ACME","Nasdaq\\u007f"]',
            '[1,"Issuer","GÖTV","Nasdaq"]',
        )
        for row in bad_rows:
            body = (
                '{"fields":["cik","name","ticker","exchange"],"data":['
                + row
                + ']}'
            )
            with self.subTest(row=row):
                transport = _ResponseTransport(
                    {SEC_REFERENCE_LOCATOR: [_reference_ok(body)]}
                )
                result = _client(transport).admit_sec_reference(("ACME",))
                self.assertEqual(result.admissions, ())
                self.assertEqual(result.failures[0].code, "PARSER_UNSUPPORTED")

    def test_sec_reference_selection_arguments_are_exact_and_never_fetch_on_invalid_input(self):
        for symbols, error in (
            ([], TypeError),
            ((), ValueError),
            (("acme",), ValueError),
            (("ACME", "ACME"), ValueError),
            (("A B",), ValueError),
        ):
            transport = _ResponseTransport({})
            with self.subTest(symbols=symbols):
                with self.assertRaises(error):
                    _client(transport).admit_sec_reference(symbols)
                self.assertEqual(transport.calls, [])

    def test_sec_reference_revalidator_rejects_constructor_bypassed_metadata_body_symbol_and_anchors(self):
        raw_body = SEC_REFERENCE_BODY.encode("utf-8")
        client = _client(
            _ResponseTransport({SEC_REFERENCE_LOCATOR: [_reference_ok(raw_body)]})
        )
        admitted = client.admit_sec_reference(("ACME", "PLUG")).admissions[0]

        self.assertIsNotNone(
            client._revalidate_sec_reference(
                admitted, ("ACME", "PLUG"), max_parsed_bytes=100_000
            )
        )
        self.assertIsNone(
            _revalidate_source_admission(
                admitted, max_raw_bytes=100_000, max_parsed_bytes=100_000
            )
        )
        self.assertIsNone(
            client._revalidate_sec_reference(
                admitted, ("PLUG", "ACME"), max_parsed_bytes=100_000
            )
        )
        self.assertIsNone(
            _client(_ResponseTransport({}))._revalidate_sec_reference(
                admitted, ("ACME", "PLUG"), max_parsed_bytes=100_000
            )
        )

        def bypass(**changes):
            clone = object.__new__(type(admitted))
            for name, value in vars(admitted).items():
                object.__setattr__(clone, name, changes.get(name, value))
            return clone

        body_without_acme = admitted.parsed_body.replace('"ACME"', '"FAKE"')
        bad_anchor = replace(
            admitted.raw_anchors[0], parsed_start=admitted.raw_anchors[0].parsed_start + 1
        )
        shifted_raw_anchor = replace(
            admitted.raw_anchors[0],
            raw_start=admitted.raw_anchors[0].raw_start + 1,
            raw_end=admitted.raw_anchors[0].raw_end + 1,
        )
        fake_token = body_without_acme[
            admitted.raw_anchors[0].parsed_start : admitted.raw_anchors[0].parsed_end
        ]
        changed_selection_anchor = replace(
            admitted.raw_anchors[0],
            field="sec_issuer_reference.data.FAKE",
            raw_sha256=hashlib.sha256(fake_token.encode("utf-8")).hexdigest(),
        )
        bad_records = (
            bypass(parser_id="sec-edgar-cover-v1"),
            bypass(content_type="text/html"),
            bypass(initial_locator=SEC_LOCATOR),
            bypass(parsed_symbol="ACME"),
            bypass(raw_body_sha256="0" * 64),
            bypass(raw_anchors=(shifted_raw_anchor,) + admitted.raw_anchors[1:]),
            bypass(
                parsed_body=body_without_acme,
                parsed_body_sha256=hashlib.sha256(body_without_acme.encode("utf-8")).hexdigest(),
                raw_body_sha256="1" * 64,
                raw_anchors=(changed_selection_anchor,) + admitted.raw_anchors[1:],
            ),
            bypass(raw_anchors=(bad_anchor,) + admitted.raw_anchors[1:]),
        )
        for record in bad_records:
            with self.subTest(parser=record.parser_id, content_type=record.content_type):
                self.assertIsNone(
                    client._revalidate_sec_reference(
                        record, ("ACME", "PLUG"), max_parsed_bytes=100_000
                    )
                )
                self.assertIsNone(
                    _revalidate_source_admission(
                        record, max_raw_bytes=100_000, max_parsed_bytes=100_000
                    )
                )

    def test_sec_reference_content_type_encoding_and_existing_candidate_boundary(self):
        accepted = (
            "application/json; charset=utf-8",
            "application/json; charset=UTF-8",
        )
        for content_type in accepted:
            with self.subTest(content_type=content_type):
                transport = _ResponseTransport(
                    {SEC_REFERENCE_LOCATOR: [_reference_ok(SEC_REFERENCE_BODY, content_type)]}
                )
                result = _client(transport).admit_sec_reference(("ACME",))
                self.assertEqual(len(result.admissions), 1)

        for content_type in ("text/html", "application/json; charset=latin-1"):
            with self.subTest(rejected_content_type=content_type):
                transport = _ResponseTransport(
                    {SEC_REFERENCE_LOCATOR: [_reference_ok(SEC_REFERENCE_BODY, content_type)]}
                )
                result = _client(transport).admit_sec_reference(("ACME",))
                self.assertEqual(result.admissions, ())
                self.assertEqual(result.failures[0].code, "CONTENT_TYPE_UNSUPPORTED")

        for encoding in (None, "", "identity"):
            headers = {"Content-Type": "application/json; charset=UTF-8"}
            if encoding is not None:
                headers["Content-Encoding"] = encoding
            transport = _ResponseTransport(
                {SEC_REFERENCE_LOCATOR: [_Reply(200, headers, SEC_REFERENCE_BODY.encode("utf-8"))]}
            )
            self.assertEqual(
                len(_client(transport).admit_sec_reference(("ACME",)).admissions), 1
            )

        for headers, body, expected in (
            ({"Content-Type": "application/json; charset=utf-8; charset=utf-8"}, SEC_REFERENCE_BODY.encode("utf-8"), "CONTENT_TYPE_UNSUPPORTED"),
            ({"Content-Type": "application/json", "Content-Encoding": "gzip"}, SEC_REFERENCE_BODY.encode("utf-8"), "CONTENT_TYPE_UNSUPPORTED"),
            ({"Content-Type": "application/json"}, b"\xff", "UTF8_DECODE_FAILED"),
        ):
            transport = _ResponseTransport(
                {SEC_REFERENCE_LOCATOR: [_Reply(200, headers, body)]}
            )
            result = _client(transport).admit_sec_reference(("ACME",))
            self.assertEqual(result.admissions, ())
            self.assertEqual(result.failures[0].code, expected)

        transport = _ResponseTransport(
            {SEC_REFERENCE_LOCATOR: [_reference_ok(SEC_REFERENCE_BODY)]}
        )
        generic = _client(transport).admit_candidates((SEC_REFERENCE_LOCATOR,))
        self.assertEqual(generic.admissions, ())
        self.assertEqual(generic.request_count, 0)
        self.assertEqual(transport.calls, [])

    def test_sec_reference_uses_existing_body_byte_and_deadline_budgets(self):
        raw_body = SEC_REFERENCE_BODY.encode("utf-8")
        cases = (
            (len(raw_body) - 1, 100_000),
            (100_000, len(raw_body) - 1),
        )
        for max_bytes, byte_budget in cases:
            transport = _ResponseTransport(
                {SEC_REFERENCE_LOCATOR: [_reference_ok(raw_body)]}
            )
            result = _client(
                transport, max_bytes=max_bytes, byte_budget=byte_budget
            ).admit_sec_reference(("ACME",))
            self.assertEqual(result.admissions, ())
            self.assertEqual(result.failures[0].code, "BODY_LIMIT_EXCEEDED")
            self.assertEqual(result.request_count, 1)

        now = [0.0]

        def late_transport(locator, address, timeout, max_bytes):
            now[0] = 100.0
            return _reference_ok(raw_body)

        late_client = _SourceAdmissionClient(
            timeout_seconds=2.5,
            max_response_bytes=100_000,
            byte_budget=500_000,
            _transport=late_transport,
            _resolver=lambda _host, _port: ("93.184.216.34",),
            _clock=lambda: NOW,
            _monotonic=lambda: now[0],
        )
        late = late_client.admit_sec_reference(("ACME",))
        self.assertEqual(late.admissions, ())
        self.assertEqual(late.failures[0].code, "ADMISSION_DEADLINE_EXCEEDED")
        self.assertEqual(late.request_count, 1)

        locators = tuple(
            "https://www.sec.gov/Archives/edgar/data/320193/000032019326000123/file{}.htm".format(index)
            for index in range(MAX_SOURCE_ADMISSION_REQUESTS)
        )
        exhausted_transport = _ResponseTransport(
            {locator: [_Reply(404, {}, b"")] for locator in locators}
        )
        exhausted_client = _client(exhausted_transport)
        exhausted = exhausted_client.admit_candidates(locators)
        self.assertEqual(exhausted.request_count, MAX_SOURCE_ADMISSION_REQUESTS)
        reference = exhausted_client.admit_sec_reference(("ACME",))
        self.assertEqual(reference.admissions, ())
        self.assertEqual(reference.failures[0].code, "REQUEST_LIMIT_REACHED")
        self.assertEqual(reference.request_count, MAX_SOURCE_ADMISSION_REQUESTS)
        self.assertEqual(len(exhausted_transport.calls), MAX_SOURCE_ADMISSION_REQUESTS)

    def test_sec_reference_redirect_remains_same_endpoint_and_counts_each_get(self):
        redirect = _Reply(302, {"Location": SEC_REFERENCE_LOCATOR}, b"")
        transport = _ResponseTransport(
            {
                SEC_REFERENCE_LOCATOR: [
                    redirect,
                    _reference_ok(SEC_REFERENCE_BODY),
                ]
            }
        )
        result = _client(transport).admit_sec_reference(("ACME",))
        self.assertEqual(len(result.admissions), 1)
        self.assertEqual(result.request_count, 2)
        self.assertEqual([call[0] for call in transport.calls], [SEC_REFERENCE_LOCATOR] * 2)

        rejected_transport = _ResponseTransport(
            {
                SEC_REFERENCE_LOCATOR: [
                    _Reply(302, {"Location": "https://sec.gov/files/company_tickers_exchange.json"}, b"")
                ]
            }
        )
        rejected = _client(rejected_transport).admit_sec_reference(("ACME",))
        self.assertEqual(rejected.admissions, ())
        self.assertEqual(rejected.failures[0].code, "REDIRECT_INVALID")
        self.assertEqual(rejected.request_count, 1)

    def test_sec_layout_v3_normalizes_only_cover_layout_and_keeps_physical_anchors(self):
        for width in (3, 5):
            with self.subTest(width=width):
                raw_body = _sec_layout_v3_html(width)
                transport = _ResponseTransport({SEC_LOCATOR: [_ok(raw_body)]})
                result = _client(transport).admit_candidates((SEC_LOCATOR,))
                self.assertEqual(result.request_count, 1)
                self.assertEqual([call[0] for call in transport.calls], [SEC_LOCATOR])
                self.assertEqual(len(result.admissions), 1)
                admitted = result.admissions[0]
                self.assertEqual(admitted.parser_id, "sec-edgar-cover-layout-v3")
                self.assertEqual(admitted.parser_version, "3")
                self.assertEqual(admitted.parsed_symbol, "ACME")
                self.assertIn("An event\u00a0was reported.", admitted.parsed_body)
                self.assertIn("| Common Stock | ACME | The Nasdaq Capital Market |", admitted.parsed_body)
                self.assertIsNotNone(
                    _revalidate_source_admission(
                        admitted, max_raw_bytes=100_000, max_parsed_bytes=100_000
                    )
                )

                raw_text = raw_body.decode("utf-8")
                anchors_by_field = {anchor.field: anchor for anchor in admitted.raw_anchors}
                for field, raw_excerpt, parsed_excerpt in (
                    ("sec_cover.header.0", "Title&nbsp;of<br>each class", "Title of each class"),
                    ("sec_cover.value.0", "Common&nbsp;Stock", "Common Stock"),
                    ("sec_cover.value.2", "The&nbsp;Nasdaq Capital Market", "The Nasdaq Capital Market"),
                    ("sec_cover.registrant", "Example&nbsp;Holdings, Inc.", "Example\u00a0Holdings, Inc."),
                    (
                        "sec_cover.registrant_marker",
                        "(Exact&nbsp;name of registrant as specified in its charter)",
                        "(Exact\u00a0name of registrant as specified in its charter)",
                    ),
                ):
                    anchor = anchors_by_field[field]
                    self.assertEqual(raw_text[anchor.raw_start:anchor.raw_end], raw_excerpt)
                    self.assertEqual(
                        admitted.parsed_body[anchor.parsed_start:anchor.parsed_end],
                        parsed_excerpt,
                    )
                for spoof in (
                    replace(admitted, parser_version="2"),
                    replace(admitted, parser_id="sec-edgar-cover-text-v2"),
                    replace(admitted, parser_id="sec-edgar-cover-layout-v9"),
                ):
                    self.assertIsNone(
                        _revalidate_source_admission(
                            spoof, max_raw_bytes=100_000, max_parsed_bytes=100_000
                        )
                    )

    def test_sec_layout_v3_rejects_unclosed_or_controlled_shapes(self):
        default_row = [
            "Common&nbsp;Stock",
            "",
            "ACME",
            "",
            "The&nbsp;Nasdaq Capital Market",
        ]
        nonempty_header_spacer = [
            "Title&nbsp;of<br>each class",
            "spacer",
            "Trading Symbol(s)",
            "",
            "Name of each exchange on which registered",
        ]
        long_s_header = [
            "Title&nbsp;of<br>each class",
            "&nbsp;",
            "Trading ſymbol(s)",
            "&nbsp;",
            "Name of each exchange on which registered",
        ]
        nonempty_data_spacer = list(default_row)
        nonempty_data_spacer[3] = "spacer"
        cases = (
            ("width-4", _sec_layout_v3_html(4)),
            ("width-6", _sec_layout_v3_html(6)),
            ("nonempty-header-spacer", _sec_layout_v3_html(header_cells=nonempty_header_spacer)),
            ("long-s-header", _sec_layout_v3_html(header_cells=long_s_header)),
            ("nonempty-data-spacer", _sec_layout_v3_html(data_rows=(nonempty_data_spacer,))),
            (
                "multiple-data-rows",
                _sec_layout_v3_html(data_rows=(default_row, default_row)),
            ),
            ("duplicate-cover-table", _sec_layout_v3_html(duplicate_tables=2)),
            (
                "raw-line-feed",
                _sec_layout_v3_html(data_rows=(["Common\nStock", "", "ACME", "", "Nasdaq"],)),
            ),
            (
                "entity-line-feed",
                _sec_layout_v3_html(
                    data_rows=(["Common&#10;Stock", "", "ACME", "", "Nasdaq"],)
                ),
            ),
        )
        for label, raw_body in cases:
            with self.subTest(shape=label):
                self.assertIsNone(
                    admission._sec_cover_layout_v3(raw_body.decode("utf-8"))
                )

    def test_sec_layout_v4_folds_declared_controls_and_preserves_raw_anchors(self):
        cases = (
            (
                "entities",
                _sec_layout_v4_html(
                    issuer="Example&#9;Holdings, Inc.",
                    marker="(Exact&#10;name of registrant as specified in its charter)",
                    title="Common&#13;Stock",
                    exchange="Nasdaq&#13;Capital&#10;Market",
                ),
                (
                    ("sec_cover.registrant", "Example&#9;Holdings, Inc.", "Example\tHoldings, Inc."),
                    (
                        "sec_cover.registrant_marker",
                        "(Exact&#10;name of registrant as specified in its charter)",
                        "(Exact\nname of registrant as specified in its charter)",
                    ),
                    ("sec_cover.value.0", "Common&#13;Stock", "Common Stock"),
                    ("sec_cover.value.2", "Nasdaq&#13;Capital&#10;Market", "Nasdaq Capital Market"),
                ),
            ),
            (
                "literal-controls",
                _sec_layout_v4_html(
                    issuer="Example\tHoldings, Inc.",
                    marker="(Exact\rname of registrant as specified in its charter)",
                    title="Common\tStock",
                    exchange="Nasdaq\rCapital\nMarket",
                ),
                (
                    ("sec_cover.registrant", "Example\tHoldings, Inc.", "Example\tHoldings, Inc."),
                    (
                        "sec_cover.registrant_marker",
                        "(Exact\rname of registrant as specified in its charter)",
                        "(Exact\rname of registrant as specified in its charter)",
                    ),
                    ("sec_cover.value.0", "Common\tStock", "Common Stock"),
                    ("sec_cover.value.2", "Nasdaq\rCapital\nMarket", "Nasdaq Capital Market"),
                ),
            ),
        )
        for label, raw_body, expected_anchors in cases:
            with self.subTest(format=label):
                transport = _ResponseTransport({SEC_LOCATOR: [_ok(raw_body)]})
                result = _client(transport).admit_candidates((SEC_LOCATOR,))
                self.assertEqual(result.request_count, 1)
                self.assertEqual([call[0] for call in transport.calls], [SEC_LOCATOR])
                self.assertEqual(len(result.admissions), 1)
                admitted = result.admissions[0]
                self.assertEqual(admitted.parser_id, "sec-edgar-cover-layout-v4")
                self.assertEqual(admitted.parser_version, "4")
                self.assertEqual(admitted.parsed_symbol, "ACME")
                self.assertIn("A visible\t narrative\nstays\u00a0literal.", admitted.parsed_body)
                self.assertIn(
                    "| Common Stock | ACME | Nasdaq Capital Market |", admitted.parsed_body
                )
                self.assertEqual(admitted.raw_body_sha256, hashlib.sha256(raw_body).hexdigest())
                self.assertIsNotNone(
                    _revalidate_source_admission(
                        admitted, max_raw_bytes=100_000, max_parsed_bytes=100_000
                    )
                )
                raw_text = raw_body.decode("utf-8")
                anchors_by_field = {anchor.field: anchor for anchor in admitted.raw_anchors}
                for field, raw_excerpt, parsed_excerpt in expected_anchors:
                    anchor = anchors_by_field[field]
                    self.assertEqual(raw_text[anchor.raw_start:anchor.raw_end], raw_excerpt)
                    self.assertEqual(
                        anchor.raw_sha256, hashlib.sha256(raw_excerpt.encode("utf-8")).hexdigest()
                    )
                    self.assertEqual(
                        admitted.parsed_body[anchor.parsed_start:anchor.parsed_end],
                        parsed_excerpt,
                    )
                self.assertIsNone(admission._sec_cover_layout_v3(raw_text))
                for spoof in (
                    replace(admitted, parser_id="sec-edgar-cover-layout-v3"),
                    replace(admitted, parser_version="3"),
                ):
                    self.assertIsNone(
                        _revalidate_source_admission(
                            spoof, max_raw_bytes=100_000, max_parsed_bytes=100_000
                        )
                    )

    def test_sec_layout_v4_requires_complete_segments_and_safe_unique_shape(self):
        marker = admission._SEC_MARKER
        cases = (
            ("form-feed-field", _sec_layout_v4_html(title="Common&#12;Stock")),
            ("vertical-tab-marker", _sec_layout_v4_html(marker=marker.replace("name", "\vname"))),
            ("c1-issuer", _sec_layout_v4_html(issuer="Example&#128; Holdings, Inc.")),
            ("unsafe-spacer", _sec_layout_v4_html(spacer="not empty")),
            ("hidden-marker", _sec_layout_v4_html(marker="<span hidden>{}</span>".format(marker))),
            (
                "hidden-inline-cannot-isolate-marker",
                _sec_layout_v4_html(marker="prefix<script>hidden</script>{}".format(marker)),
            ),
            (
                "hidden-inline-cannot-isolate-issuer",
                _sec_layout_v4_html(
                    issuer="Bad | <script>hidden</script>Example Holdings, Inc.",
                    marker="(Exact&#10;name of registrant as specified in its charter)",
                ),
            ),
            ("marker-substring", _sec_layout_v4_html(marker="prefix {} suffix".format(marker))),
            ("duplicate-marker", _sec_layout_v4_html(trailing="<p>{}</p>".format(marker))),
            ("missing-issuer", _sec_layout_v4_html(issuer="")),
            ("invalid-issuer", _sec_layout_v4_html(issuer="Bad | Company")),
            ("duplicate-table", _sec_layout_v4_html(duplicate_tables=2)),
        )
        for label, raw_body in cases:
            with self.subTest(shape=label):
                self.assertIsNone(
                    admission._parse_page(
                        "sec", raw_body.decode("utf-8"), None, "text/html"
                    )
                )

    def test_raw_html_envelope_cap_is_independent_of_parsed_body_cap(self):
        raw_html = SEC_HTML.replace(
            b"<body>", b"<body><!--" + (b"x" * 25_000) + b"-->"
        )
        transport = _ResponseTransport({SEC_LOCATOR: [_ok(raw_html)]})
        result = _client(transport, max_bytes=50_000, byte_budget=50_000).admit_candidates(
            (SEC_LOCATOR,)
        )
        self.assertEqual(len(result.admissions), 1)
        admitted = result.admissions[0]
        self.assertGreater(admitted.raw_body_bytes, 20_000)
        self.assertLessEqual(len(admitted.parsed_body.encode("utf-8")), 20_000)
        self.assertIsNotNone(
            _revalidate_source_admission(
                admitted, max_raw_bytes=50_000, max_parsed_bytes=20_000
            )
        )
        self.assertIsNone(
            _revalidate_source_admission(
                admitted, max_raw_bytes=20_000, max_parsed_bytes=20_000
            )
        )

    def test_redirect_to_other_origin_or_target_is_rejected_without_origin_claim(self):
        bad_target = "https://www.nasdaq.com/market-activity/stocks/acme"
        transport = _ResponseTransport(
            {SEC_LOCATOR: [_Reply(302, {"Location": bad_target}, b"")]}
        )
        result = _client(transport).admit_candidates((SEC_LOCATOR,))
        self.assertEqual(result.admissions, ())
        self.assertEqual(result.failures[0].code, "REDIRECT_INVALID")
        self.assertNotIn("origin", vars(result.failures[0]))
        self.assertEqual(result.request_count, 1)

    def test_redirect_limit_and_global_get_cap_include_redirect_requests(self):
        extra_sec = "https://www.sec.gov/Archives/edgar/data/320193/000032019326000123/other.htm"
        redirect = _Reply(302, {"Location": SEC_LOCATOR}, b"")
        transport = _ResponseTransport(
            {
                SEC_LOCATOR: [redirect, redirect, redirect],
                extra_sec: [_ok(SEC_HTML)],
                NASDAQ_LOCATOR: [_ok(NASDAQ_HTML)],
                YAHOO_LOCATOR: [_ok(YAHOO_HTML)],
            }
        )
        result = _client(transport).admit_candidates(
            (SEC_LOCATOR, extra_sec, NASDAQ_LOCATOR, YAHOO_LOCATOR)
        )
        self.assertEqual(MAX_SOURCE_ADMISSION_REDIRECTS, 2)
        self.assertLessEqual(result.request_count, MAX_SOURCE_ADMISSION_REQUESTS)
        self.assertEqual(result.request_count, 5)
        self.assertEqual(len(transport.calls), 5)

    def test_content_type_utf8_and_body_caps_fail_closed_without_clipping(self):
        cases = (
            (_ok(SEC_HTML, "application/pdf"), 100_000, "CONTENT_TYPE_UNSUPPORTED"),
            (_ok(b"\xff\xfe", "text/html; charset=utf-8"), 100_000, "UTF8_DECODE_FAILED"),
            (_ok(SEC_HTML), 12, "BODY_LIMIT_EXCEEDED"),
            (_ok(SEC_HTML, "text/plain; charset=iso-8859-1"), 100_000, "CONTENT_TYPE_UNSUPPORTED"),
        )
        for reply, cap, expected in cases:
            with self.subTest(expected=expected):
                transport = _ResponseTransport({SEC_LOCATOR: [reply]})
                result = _client(transport, max_bytes=cap).admit_candidates((SEC_LOCATOR,))
                self.assertEqual(result.admissions, ())
                self.assertEqual(result.failures[0].code, expected)
                self.assertEqual(result.request_count, 1)

    def test_unsupported_html_shape_is_not_registered(self):
        transport = _ResponseTransport({SEC_LOCATOR: [_ok(b"<html><body>Not a filing cover</body></html>")]})
        result = _client(transport).admit_candidates((SEC_LOCATOR,))
        self.assertEqual(result.admissions, ())
        self.assertEqual(result.failures[0].code, "PARSER_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()
