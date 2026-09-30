"""Offline contract tests for the bounded Tavily source transport."""

import json
import pathlib
import sys
import tempfile
import unittest
from urllib.error import URLError


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter.host_sources import (  # noqa: E402
    TavilyConfigurationError,
    TavilyCredentialError,
    TavilyCredentialRef,
    TavilyExtractResult,
    TavilySourceBody,
    TavilySourceClient,
    TavilySourceConfig,
    TavilySourceReference,
    TavilyTransportError,
)


KEY = "tvly-synthetic-only-key"
SEARCH_URL = "https://example.com/first"
SECOND_URL = "https://example.org/second"
THIRD_URL = "http://example.net/third"


class SyntheticResponse:
    def __init__(self, body, *, status=200, final_url=None, headers=None, read_error=None):
        self.body = body
        self.status = status
        self.final_url = final_url
        self.headers = headers or {}
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


class SyntheticTransport:
    def __init__(self, responses=(), error=None):
        self.responses = list(responses)
        self.error = error
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        if not self.responses:
            raise AssertionError("unexpected transport call")
        return self.responses.pop(0)


def response_body(payload):
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def search_payload(results, *, request_id="search-1", credits=1):
    return {
        "query": "synthetic query",
        "results": results,
        "response_time": "0.02",
        "usage": {"credits": credits},
        "request_id": request_id,
    }


def extract_payload(results, failed_results, *, request_id="extract-1", credits=1):
    return {
        "results": results,
        "failed_results": failed_results,
        "response_time": 0.02,
        "usage": {"credits": credits},
        "request_id": request_id,
    }


def search_result(url, title, content, score, *, published_date=None, result_id=None):
    result = {
        "url": url,
        "title": title,
        "content": content,
        "score": score,
    }
    if published_date is not None:
        result["published_date"] = published_date
    if result_id is not None:
        result["id"] = result_id
    return result


class HostSourcesTests(unittest.TestCase):
    def make_client(
        self,
        transport,
        *,
        request_budget=4,
        credit_budget=4,
        max_request_bytes=4096,
        max_response_bytes=4096,
        timeout_seconds=7.5,
        byte_budget=None,
    ):
        config = TavilySourceConfig(
            credential_ref=TavilyCredentialRef(env_name="SYNTHETIC_TAVILY_KEY"),
            paygo_off_confirmed=True,
            request_budget=request_budget,
            credit_budget=credit_budget,
            max_request_bytes=max_request_bytes,
            max_response_bytes=max_response_bytes,
            timeout_seconds=timeout_seconds,
            byte_budget=byte_budget,
        )
        return TavilySourceClient(
            config,
            repo_root=ROOT,
            transport=transport,
            credential_resolver=lambda _ref: KEY,
        )

    def test_search_uses_canonical_basic_request_and_preserves_provider_order(self):
        body = response_body(
            search_payload(
                [
                    search_result(
                        SEARCH_URL,
                        "First",
                        "first snippet",
                        0.01,
                        published_date="Tue, 11 Mar 2025 17:00:00 GMT",
                        result_id="first-id",
                    ),
                    search_result(
                        SECOND_URL,
                        "Second",
                        "second snippet",
                        0.99,
                        result_id="second-id",
                    ),
                ]
            )
        )
        response = SyntheticResponse(body, final_url="https://api.tavily.com/search")
        transport = SyntheticTransport([response])
        client = self.make_client(transport)

        result = client.search("synthetic query", max_results=2)

        self.assertEqual([source.source_id for source in result.sources], ["first-id", "second-id"])
        self.assertEqual([source.url for source in result.sources], [SEARCH_URL, SECOND_URL])
        self.assertEqual(result.sources[0].native_score, 0.01)
        self.assertEqual(result.sources[0].published_at, "Tue, 11 Mar 2025 17:00:00 GMT")
        self.assertFalse(result.sources[0].verified)
        self.assertEqual(result.coverage.status, "COMPLETE")
        self.assertEqual(result.coverage.source_ids, ("first-id", "second-id"))
        self.assertEqual(result.receipt.reported_credits, 1)
        self.assertEqual(client.remaining_request_budget, 3)
        self.assertEqual(client.remaining_credit_budget, 3)

        request, timeout = transport.calls[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://api.tavily.com/search")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {KEY}")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(request.get_header("Content-length"), str(len(request.data)))
        self.assertEqual(request.get_header("User-agent"), "ConvexityHunter/0.1")
        self.assertEqual(timeout, 7.5)
        self.assertEqual(payload["search_depth"], "basic")
        self.assertFalse(payload["auto_parameters"])
        self.assertFalse(payload["include_answer"])
        self.assertTrue(payload["include_usage"])
        self.assertNotIn("api_key", payload)
        self.assertEqual(response.read_sizes, [4097])
        self.assertTrue(response.closed)

    def test_empty_search_is_explicitly_not_complete(self):
        response = SyntheticResponse(
            response_body(search_payload([], request_id="empty-search")),
            final_url="https://api.tavily.com/search",
        )
        client = self.make_client(SyntheticTransport([response]))

        result = client.search("synthetic query")

        self.assertEqual(result.sources, ())
        self.assertEqual(result.coverage.status, "EMPTY")
        self.assertFalse(result.coverage.is_complete)
        self.assertEqual(result.receipt.returned_count, 0)

    def test_search_accepts_null_follow_up_questions(self):
        payload = search_payload([])
        payload["follow_up_questions"] = None
        response = SyntheticResponse(
            response_body(payload),
            final_url="https://api.tavily.com/search",
        )
        client = self.make_client(SyntheticTransport([response]))

        result = client.search("synthetic query")

        self.assertEqual(result.sources, ())
        self.assertEqual(result.coverage.status, "EMPTY")

    def test_search_rejects_non_null_follow_up_questions(self):
        payload = search_payload([])
        payload["follow_up_questions"] = ["do not consume this suggestion"]
        response = SyntheticResponse(
            response_body(payload),
            final_url="https://api.tavily.com/search",
        )
        client = self.make_client(
            SyntheticTransport([response]),
            request_budget=1,
            credit_budget=1,
        )

        with self.assertRaises(TavilyTransportError) as raised:
            client.search("synthetic query")

        self.assertEqual(raised.exception.code, "MALFORMED_RESPONSE")
        self.assertEqual(client.remaining_request_budget, 0)
        self.assertEqual(client.remaining_credit_budget, 0)

    def test_search_still_rejects_other_unknown_fields(self):
        payload = search_payload([])
        payload["follow_up_questions"] = None
        payload["unregistered_field"] = "still rejected"
        response = SyntheticResponse(
            response_body(payload),
            final_url="https://api.tavily.com/search",
        )
        client = self.make_client(SyntheticTransport([response]))

        with self.assertRaises(TavilyTransportError) as raised:
            client.search("synthetic query")

        self.assertEqual(raised.exception.code, "UNKNOWN_RESPONSE_FIELD")

    def test_extract_reorders_partial_response_and_redacts_provider_error(self):
        raw_error = f"provider leaked {KEY} and private details"
        response = SyntheticResponse(
            response_body(
                extract_payload(
                    [
                        {"url": SECOND_URL, "raw_content": "second body"},
                        {"url": SEARCH_URL, "raw_content": "untrusted __import__('os')"},
                    ],
                    [{"url": THIRD_URL, "error": raw_error}],
                    request_id="extract-partial",
                )
            ),
            final_url="https://api.tavily.com/extract",
        )
        transport = SyntheticTransport([response])
        refs = (
            TavilySourceReference("first-id", SEARCH_URL, "First", "snippet", "published", "first-id", 0.1),
            TavilySourceReference("second-id", SECOND_URL, "Second", "snippet", None, "second-id", 0.2),
            TavilySourceReference("third-id", THIRD_URL, "Third", "snippet", None, "third-id", 0.3),
        )
        client = self.make_client(transport)

        result = client.extract(
            (SEARCH_URL, SECOND_URL, THIRD_URL),
            query="grounding query",
            source_refs=refs,
        )

        self.assertIsInstance(result, TavilyExtractResult)
        self.assertEqual([body.source_id for body in result.bodies], ["first-id", "second-id"])
        self.assertEqual([body.url for body in result.bodies], [SEARCH_URL, SECOND_URL])
        self.assertEqual(result.bodies[0].publication_date, "published")
        self.assertEqual(result.bodies[0].body, "untrusted __import__('os')")
        self.assertEqual([item.source_id for item in result.failed_extracts], ["third-id"])
        self.assertEqual(result.failed_extracts[0].reason_code, "PROVIDER_REPORTED_FAILURE")
        self.assertEqual(result.coverage.status, "PARTIAL")
        self.assertEqual(result.coverage.requested_count, 3)
        self.assertEqual(result.coverage.returned_count, 2)
        self.assertEqual(result.coverage.failed_count, 1)
        self.assertEqual(result.receipt.source_ids, ("first-id", "second-id", "third-id"))
        self.assertEqual(json.loads(transport.calls[0][0].data)["urls"], [SEARCH_URL, SECOND_URL, THIRD_URL])
        self.assertNotIn(raw_error, repr(result))
        self.assertEqual(client.remaining_credit_budget, 3)

    def test_extract_all_failed_is_empty_not_complete_and_keeps_order(self):
        response = SyntheticResponse(
            response_body(
                extract_payload(
                    [],
                    [{"url": SECOND_URL, "error": "no"}, {"url": SEARCH_URL, "error": "no"}],
                    request_id="extract-empty",
                )
            ),
            final_url="https://api.tavily.com/extract",
        )
        client = self.make_client(SyntheticTransport([response]))

        result = client.extract((SEARCH_URL, SECOND_URL))

        self.assertEqual(result.bodies, ())
        self.assertEqual([item.url for item in result.failed_extracts], [SEARCH_URL, SECOND_URL])
        self.assertEqual(result.coverage.status, "EMPTY")
        self.assertFalse(result.coverage.is_complete)

    def test_extract_accepts_optional_string_title_and_discards_it(self):
        response = SyntheticResponse(
            response_body(
                extract_payload(
                    [{"url": SEARCH_URL, "raw_content": "body", "title": "provider title"}],
                    [],
                )
            ),
            final_url="https://api.tavily.com/extract",
        )
        client = self.make_client(SyntheticTransport([response]))

        result = client.extract((SEARCH_URL,))

        self.assertEqual(result.bodies[0].body, "body")
        self.assertFalse(hasattr(result.bodies[0], "title"))

    def test_extract_accepts_null_optional_title_and_discards_it(self):
        response = SyntheticResponse(
            response_body(
                extract_payload(
                    [{"url": SEARCH_URL, "raw_content": "body", "title": None}],
                    [],
                )
            ),
            final_url="https://api.tavily.com/extract",
        )
        client = self.make_client(SyntheticTransport([response]))

        result = client.extract((SEARCH_URL,))

        self.assertEqual(result.urls, (SEARCH_URL,))
        self.assertEqual(result.bodies[0].url, SEARCH_URL)
        self.assertEqual(result.bodies[0].body, "body")
        self.assertFalse(hasattr(result.bodies[0], "title"))

    def test_extract_still_rejects_non_string_non_null_optional_title(self):
        response = SyntheticResponse(
            response_body(
                extract_payload(
                    [{"url": SEARCH_URL, "raw_content": "body", "title": 123}],
                    [],
                )
            ),
            final_url="https://api.tavily.com/extract",
        )
        client = self.make_client(
            SyntheticTransport([response]),
            request_budget=1,
            credit_budget=1,
        )

        with self.assertRaises(TavilyTransportError) as raised:
            client.extract((SEARCH_URL,))

        self.assertEqual(raised.exception.code, "MALFORMED_RESPONSE")
        self.assertEqual(client.remaining_request_budget, 0)
        self.assertEqual(client.remaining_credit_budget, 0)

    def test_extract_still_rejects_non_string_source_body_with_null_title(self):
        response = SyntheticResponse(
            response_body(
                extract_payload(
                    [{"url": SEARCH_URL, "raw_content": {"not": "text"}, "title": None}],
                    [],
                )
            ),
            final_url="https://api.tavily.com/extract",
        )
        client = self.make_client(SyntheticTransport([response]))

        with self.assertRaises(TavilyTransportError) as raised:
            client.extract((SEARCH_URL,))

        self.assertEqual(raised.exception.code, "MALFORMED_RESPONSE")

    def test_extract_still_rejects_unrequested_result_url_with_null_title(self):
        response = SyntheticResponse(
            response_body(
                extract_payload(
                    [{"url": SECOND_URL, "raw_content": "body", "title": None}],
                    [],
                )
            ),
            final_url="https://api.tavily.com/extract",
        )
        client = self.make_client(SyntheticTransport([response]))

        with self.assertRaises(TavilyTransportError) as raised:
            client.extract((SEARCH_URL,))

        self.assertEqual(raised.exception.code, "MALFORMED_RESPONSE")

    def test_extract_still_rejects_other_unknown_success_fields(self):
        response = SyntheticResponse(
            response_body(
                extract_payload(
                    [
                        {
                            "url": SEARCH_URL,
                            "raw_content": "body",
                            "title": "provider title",
                            "unregistered_field": "still rejected",
                        }
                    ],
                    [],
                )
            ),
            final_url="https://api.tavily.com/extract",
        )
        client = self.make_client(SyntheticTransport([response]))

        with self.assertRaises(TavilyTransportError) as raised:
            client.extract((SEARCH_URL,))

        self.assertEqual(raised.exception.code, "UNKNOWN_RESPONSE_FIELD")

    def test_failed_transport_is_one_attempt_and_does_not_refund_budget(self):
        transport = SyntheticTransport(error=URLError(f"raw {KEY} error"))
        client = self.make_client(transport, request_budget=1, credit_budget=1)

        with self.assertRaises(TavilyTransportError) as raised:
            client.search("synthetic query")

        self.assertEqual(raised.exception.code, "NETWORK_ERROR")
        self.assertNotIn(KEY, str(raised.exception))
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(client.remaining_request_budget, 0)
        self.assertEqual(client.remaining_credit_budget, 0)
        with self.assertRaises(TavilyTransportError) as second:
            client.search("synthetic query")
        self.assertEqual(second.exception.code, "REQUEST_BUDGET_EXHAUSTED")
        self.assertEqual(len(transport.calls), 1)

    def test_malformed_response_is_rejected_after_reservation(self):
        response = SyntheticResponse(
            b'{"results": [], "results": []}',
            final_url="https://api.tavily.com/search",
        )
        client = self.make_client(SyntheticTransport([response]), request_budget=1, credit_budget=1)

        with self.assertRaises(TavilyTransportError) as raised:
            client.search("synthetic query")

        self.assertEqual(raised.exception.code, "DUPLICATE_JSON_KEY")
        self.assertEqual(client.remaining_request_budget, 0)
        self.assertEqual(client.remaining_credit_budget, 0)

    def test_response_and_request_byte_bounds_are_enforced(self):
        large_response = SyntheticResponse(
            response_body(search_payload([])),
            final_url="https://api.tavily.com/search",
        )
        client = self.make_client(
            SyntheticTransport([large_response]),
            request_budget=1,
            credit_budget=1,
            max_response_bytes=8,
        )
        with self.assertRaises(TavilyTransportError) as response_error:
            client.search("synthetic query")
        self.assertEqual(response_error.exception.code, "RESPONSE_TOO_LARGE")
        self.assertEqual(large_response.read_sizes, [9])
        self.assertEqual(client.remaining_request_budget, 0)

        request_bound_client = self.make_client(
            SyntheticTransport(),
            max_request_bytes=8,
        )
        with self.assertRaises(TavilyTransportError) as request_error:
            request_bound_client.search("synthetic query")
        self.assertEqual(request_error.exception.code, "REQUEST_TOO_LARGE")
        self.assertEqual(request_bound_client.remaining_request_budget, 4)

    def test_redirect_is_rejected_without_following(self):
        response = SyntheticResponse(
            b"ignored",
            status=302,
            final_url="https://example.com/redirected",
        )
        transport = SyntheticTransport([response])
        client = self.make_client(transport, request_budget=1, credit_budget=1)

        with self.assertRaises(TavilyTransportError) as raised:
            client.search("synthetic query")

        self.assertEqual(raised.exception.code, "REDIRECT_REJECTED")
        self.assertEqual(len(transport.calls), 1)
        self.assertTrue(response.closed)

    def test_unsafe_extract_urls_never_reach_transport(self):
        transport = SyntheticTransport()
        client = self.make_client(transport)
        unsafe_urls = (
            "file:///tmp/private",
            "http://127.0.0.1/private",
            "https://user:pass@example.com/private",
            "https://example.com/private?access_token=secret",
            "https://localhost/private",
            "https://[::1]/private",
        )

        for url in unsafe_urls:
            with self.subTest(url=url):
                with self.assertRaises(TavilyConfigurationError) as raised:
                    client.extract((url,))
                self.assertEqual(raised.exception.code, "UNSAFE_SOURCE_URL")
        self.assertEqual(transport.calls, [])
        self.assertEqual(client.remaining_request_budget, 4)
        self.assertEqual(client.remaining_credit_budget, 4)

    def test_basic_only_paygo_gate_and_credential_redaction(self):
        with self.assertRaises(TavilyConfigurationError) as paygo:
            TavilySourceConfig(
                credential_ref=TavilyCredentialRef(env_name="SYNTHETIC_TAVILY_KEY"),
                paygo_off_confirmed=False,
                request_budget=1,
                credit_budget=1,
                max_request_bytes=100,
                max_response_bytes=100,
                timeout_seconds=1,
            )
        self.assertEqual(paygo.exception.code, "PAYGO_OFF_NOT_CONFIRMED")
        with self.assertRaises(Exception):
            TavilyCredentialRef(properties_path="relative-key-file")
        self.assertNotIn(KEY, repr(TavilyCredentialRef(env_name="SYNTHETIC_TAVILY_KEY")))

    def test_external_credential_path_is_checked_without_reading_it(self):
        config = TavilySourceConfig(
            credential_ref=TavilyCredentialRef(
                properties_path=ROOT / "not-a-real-key-file"
            ),
            paygo_off_confirmed=True,
            request_budget=1,
            credit_budget=1,
            max_request_bytes=100,
            max_response_bytes=100,
            timeout_seconds=1,
        )
        with self.assertRaises(TavilyConfigurationError) as raised:
            TavilySourceClient(config, repo_root=ROOT, transport=SyntheticTransport())
        self.assertEqual(raised.exception.code, "CREDENTIAL_PATH_INSIDE_REPOSITORY")

    def test_external_credential_accepts_api_key_and_tavily_env_key_names(self):
        with tempfile.TemporaryDirectory(prefix="tavily-credential-test-") as directory:
            external = pathlib.Path(directory)
            cases = (
                ("api_key=tvly-api-key\n", "tvly-api-key"),
                ("TAVILY_API_KEY=tvly-env-key\n", "tvly-env-key"),
            )
            for index, (contents, expected) in enumerate(cases):
                with self.subTest(index=index):
                    path = external / f"accepted-{index}.properties"
                    path.write_text(contents, encoding="utf-8")
                    self.assertEqual(
                        TavilyCredentialRef(properties_path=path).resolve(
                            repo_root=ROOT,
                        ),
                        expected,
                    )

    def test_external_credential_rejects_ambiguous_and_unknown_property_names(self):
        with tempfile.TemporaryDirectory(prefix="tavily-credential-test-") as directory:
            external = pathlib.Path(directory)
            cases = (
                "api_key=tvly-one\nTAVILY_API_KEY=tvly-two\n",
                "TAVILY_API_KEY=tvly-one\nTAVILY_API_KEY=tvly-two\n",
                "unknown_key=tvly-unknown\n",
            )
            for index, contents in enumerate(cases):
                with self.subTest(index=index):
                    path = external / f"rejected-{index}.properties"
                    path.write_text(contents, encoding="utf-8")
                    with self.assertRaises(TavilyCredentialError) as raised:
                        TavilyCredentialRef(properties_path=path).resolve(
                            repo_root=ROOT,
                        )
                    self.assertEqual(raised.exception.code, "INVALID_PROPERTIES_FILE")


if __name__ == "__main__":
    unittest.main()
