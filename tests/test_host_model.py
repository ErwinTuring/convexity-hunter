"""Focused M1a tests for bounded model configuration and transport."""

import json
import os
import pathlib
import shutil
import tempfile
import unittest
from typing import Any, Iterable, Optional
from unittest import mock

import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter.host_model import (  # noqa: E402
    ChatCompletionsClient,
    ModelConfigurationError,
    ModelCredential,
    ModelCredentialError,
    ModelRuntimeConfig,
    ModelTransportError,
)


class FakeResponse:
    def __init__(
        self,
        body: bytes = b"",
        *,
        status: int = 200,
        headers: Optional[dict] = None,
    ) -> None:
        self._body = body
        self.status = status
        self.headers = headers or {}
        self.closed = False
        self.read_limits = []

    def read(self, limit: int = -1) -> bytes:
        self.read_limits.append(limit)
        if limit < 0:
            return self._body
        return self._body[:limit]

    def close(self) -> None:
        self.closed = True


class RecordingTransport:
    def __init__(self, responses: Iterable[Any]) -> None:
        self._responses = iter(responses)
        self.calls = []

    def __call__(self, request: Any, timeout: float) -> Any:
        self.calls.append((request, timeout))
        response = next(self._responses)
        if isinstance(response, BaseException):
            raise response
        return response


def completion_body(
    content: Any = "opaque semantic text",
    *,
    finish_reason: str = "stop",
    extra_root: Optional[dict] = None,
    message_extra: Optional[dict] = None,
    usage: Optional[dict] = None,
) -> bytes:
    message = {
        "role": "assistant",
        "content": content,
    }
    if message_extra:
        message.update(message_extra)
    root = {
        "id": "response-1",
        "object": "chat.completion",
        "model": "provider-echo",
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": finish_reason,
            }
        ],
    }
    if usage is not None:
        root["usage"] = usage
    if extra_root:
        root.update(extra_root)
    return json.dumps(root, separators=(",", ":")).encode("utf-8")


class HostModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = pathlib.Path(tempfile.mkdtemp(prefix="host-model-repo-"))
        self.external = pathlib.Path(tempfile.mkdtemp(prefix="host-model-ext-"))
        self.environment = mock.patch.dict(
            os.environ,
            {"HOST_MODEL_TEST_KEY": "sk-test-secret"},
            clear=False,
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(shutil.rmtree, str(self.external), True)
        self.addCleanup(shutil.rmtree, str(self.repo), True)

    def config(self, **overrides: Any) -> ModelRuntimeConfig:
        values = {
            "provider": "test-provider",
            "model": "configured-model",
            "base_endpoint": "http://127.0.0.1:8080/v1",
            "role": "semantic",
            "capabilities": ("chat.completions", "json_mode", "thinking"),
            "timeout_seconds": 0.25,
            "request_budget": 2,
            "max_tokens": 512,
            "max_input_bytes": 4096,
            "max_output_bytes": 4096,
            "remote_enabled": False,
            "fee_authorized": False,
            "json_mode": True,
            "thinking_enabled": False,
        }
        values.update(overrides)
        return ModelRuntimeConfig(**values)

    def client(
        self,
        transport: RecordingTransport,
        *,
        credential: Optional[ModelCredential] = None,
        **config_overrides: Any,
    ) -> ChatCompletionsClient:
        return ChatCompletionsClient(
            self.config(**config_overrides),
            credential or ModelCredential(env_name="HOST_MODEL_TEST_KEY"),
            repo_root=self.repo,
            transport=transport,
        )

    def assert_transport_error(
        self,
        body: bytes,
        code: str,
        **config_overrides: Any,
    ) -> None:
        transport = RecordingTransport([FakeResponse(body)])
        client = self.client(transport, **config_overrides)
        with self.assertRaises(ModelTransportError) as context:
            client.complete("trusted system", "request")
        self.assertEqual(context.exception.code, code)
        self.assertNotIn("sk-test-secret", str(context.exception))
        self.assertEqual(len(transport.calls), 1)

    def test_configured_model_is_forwarded_and_content_stays_opaque(self) -> None:
        transport = RecordingTransport(
            [
                FakeResponse(
                    completion_body(
                        "not JSON",
                        usage={
                            "prompt_tokens": 439,
                            "completion_tokens": 443,
                            "total_tokens": 882,
                            "prompt_tokens_details": {"cached_tokens": 0},
                            "prompt_cache_hit_tokens": 0,
                            "prompt_cache_miss_tokens": 439,
                        },
                    )
                )
            ]
        )
        client = self.client(transport)

        receipt = client.complete("trusted system", "hello")

        request, timeout = transport.calls[0]
        payload = json.loads(request.data.decode("utf-8"))
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(payload["model"], "configured-model")
        self.assertEqual(payload["max_tokens"], 512)
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "trusted system"},
                {"role": "user", "content": "hello"},
            ],
        )
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(payload["thinking"], {"type": "disabled"})
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(timeout, 0.25)
        self.assertEqual(headers["authorization"], "Bearer sk-test-secret")
        self.assertEqual(receipt.content, "not JSON")
        self.assertEqual(receipt.requested_model, "configured-model")
        self.assertEqual(receipt.returned_model, "provider-echo")
        self.assertEqual(receipt.prompt_tokens, 439)
        self.assertEqual(receipt.completion_tokens, 443)
        self.assertEqual(receipt.total_tokens, 882)
        self.assertEqual(receipt.cached_tokens, 0)
        self.assertEqual(receipt.prompt_cache_hit_tokens, 0)
        self.assertEqual(receipt.prompt_cache_miss_tokens, 439)
        self.assertNotIn("not JSON", repr(receipt))
        self.assertEqual(client.remaining_request_budget, 1)

    def test_external_properties_file_is_explicit_and_repr_is_nonsecret(self) -> None:
        properties = self.external / "model.properties"
        properties.write_text("api_key=sk-file-secret\n", encoding="utf-8")
        transport = RecordingTransport([FakeResponse(completion_body())])
        credential = ModelCredential(properties_path=properties)
        client = self.client(transport, credential=credential)

        client.complete("trusted system", "hello")

        request, _ = transport.calls[0]
        headers = {key.lower(): value for key, value in request.header_items()}
        self.assertEqual(headers["authorization"], "Bearer sk-file-secret")
        self.assertNotIn("sk-file-secret", repr(credential))

    def test_external_properties_file_accepts_one_deepseek_wrapper(self) -> None:
        cases = (
            ("deepseek {\n api_key = sk-plain\n}\n", "sk-plain"),
            ("DeEpSeEk: {\n api_key = sk-colon\n}\n", "sk-colon"),
        )
        for index, (contents, expected) in enumerate(cases):
            with self.subTest(index=index):
                properties = self.external / f"wrapped-{index}.properties"
                properties.write_text(contents, encoding="utf-8")
                credential = ModelCredential(properties_path=properties)
                self.assertEqual(
                    credential.resolve(repo_root=self.repo),
                    expected,
                )

    def test_external_properties_file_rejects_invalid_deepseek_wrappers(self) -> None:
        cases = (
            (
                "duplicate key",
                "deepseek: {\n api_key = sk-one\n api_key = sk-two\n}\n",
                "DUPLICATE_API_KEY",
            ),
            (
                "multiple blocks",
                "deepseek {\n api_key = sk-one\n}\n"
                "DEEPSEEK: {\n api_key = sk-two\n}\n",
                "INVALID_PROPERTIES_FILE",
            ),
            (
                "nested block",
                "deepseek: {\n nested {\n api_key = sk-one\n }\n}\n",
                "INVALID_PROPERTIES_FILE",
            ),
            (
                "unknown field",
                "deepseek {\n endpoint = https://example.test\n}\n",
                "INVALID_PROPERTIES_FILE",
            ),
            (
                "missing close",
                "deepseek: {\n api_key = sk-one\n",
                "INVALID_PROPERTIES_FILE",
            ),
            (
                "extra close",
                "deepseek {\n api_key = sk-one\n}}\n",
                "INVALID_PROPERTIES_FILE",
            ),
            (
                "stray delimiter",
                "{\napi_key = sk-one\n}\n",
                "INVALID_PROPERTIES_FILE",
            ),
        )
        for name, contents, code in cases:
            with self.subTest(name=name):
                filename = f"invalid-{name.replace(' ', '-')}.properties"
                properties = self.external / filename
                properties.write_text(contents, encoding="utf-8")
                with self.assertRaises(ModelCredentialError) as context:
                    ModelCredential(properties_path=properties).resolve(
                        repo_root=self.repo,
                    )
                self.assertEqual(context.exception.code, code)

    def test_repo_internal_and_symlink_into_repo_credentials_are_rejected(self) -> None:
        internal = self.repo / "secret.properties"
        internal.write_text("api_key=sk-internal\n", encoding="utf-8")
        transport = RecordingTransport([])

        with self.assertRaises(ModelCredentialError) as context:
            self.client(
                transport,
                credential=ModelCredential(properties_path=internal),
            ).complete("trusted system", "hello")
        self.assertEqual(context.exception.code, "CREDENTIAL_PATH_INSIDE_REPOSITORY")
        self.assertEqual(transport.calls, [])

        external_link = self.external / "link.properties"
        external_link.symlink_to(internal)
        with self.assertRaises(ModelCredentialError) as context:
            self.client(
                transport,
                credential=ModelCredential(properties_path=external_link),
            ).complete("trusted system", "hello")
        self.assertEqual(context.exception.code, "CREDENTIAL_PATH_INSIDE_REPOSITORY")
        self.assertEqual(transport.calls, [])

    def test_credential_sources_do_not_auto_discover(self) -> None:
        with self.assertRaises(ModelCredentialError) as context:
            ModelCredential()
        self.assertEqual(context.exception.code, "EXACTLY_ONE_CREDENTIAL_SOURCE_REQUIRED")

    def test_401_is_typed_and_body_is_not_exposed(self) -> None:
        transport = RecordingTransport(
            [FakeResponse(b"sk-secret-response", status=401)]
        )
        client = self.client(transport)

        with self.assertRaises(ModelTransportError) as context:
            client.complete("trusted system", "hello")

        self.assertEqual(context.exception.code, "AUTHENTICATION_FAILED")
        self.assertEqual(context.exception.status, 401)
        self.assertNotIn("sk-secret-response", str(context.exception))

    def test_timeout_is_typed_without_raw_exception_text(self) -> None:
        transport = RecordingTransport([TimeoutError("secret timeout detail")])
        client = self.client(transport)

        with self.assertRaises(ModelTransportError) as context:
            client.complete("trusted system", "hello")

        self.assertEqual(context.exception.code, "TIMEOUT")
        self.assertNotIn("secret timeout detail", str(context.exception))

    def test_malformed_oversize_duplicate_nan_and_fence_are_rejected(self) -> None:
        cases = (
            (b"not-json", "MALFORMED_JSON", {}),
            (b'{"choices": [}', "MALFORMED_JSON", {}),
            (b'{"choices":[],"choices":[]}', "DUPLICATE_JSON_KEY", {}),
            (
                b'{"choices":[{"message":{"role":"assistant","content":"x"},'
                b'"finish_reason":"stop"}],"usage":{"prompt_tokens":NaN}}',
                "NONFINITE_JSON",
                {},
            ),
            (b"```json\n{}\n```", "MALFORMED_JSON", {}),
            (completion_body("too large"), "RESPONSE_TOO_LARGE", {"max_output_bytes": 8}),
        )
        for body, code, overrides in cases:
            with self.subTest(code=code):
                self.assert_transport_error(body, code, **overrides)

    def test_fenced_opaque_content_is_allowed_inside_valid_envelope(self) -> None:
        fenced_content = "```json\nopaque semantic content\n```"
        transport = RecordingTransport([FakeResponse(completion_body(fenced_content))])
        receipt = self.client(transport).complete("trusted system", "source")
        self.assertEqual(receipt.content, fenced_content)

    def test_unknown_transport_field_is_rejected(self) -> None:
        self.assert_transport_error(
            completion_body(extra_root={"unexpected": "field"}),
            "UNKNOWN_TRANSPORT_FIELD",
        )

    def test_tool_calls_refusal_and_length_stop_are_rejected(self) -> None:
        cases = (
            (
                completion_body(
                    None,
                    message_extra={"tool_calls": [{"id": "tool-1"}]},
                ),
                "TOOL_CALLS_REJECTED",
            ),
            (
                completion_body(
                    None,
                    message_extra={"refusal": "not allowed"},
                ),
                "REFUSAL_REJECTED",
            ),
            (completion_body("partial", finish_reason="length"), "TRUNCATED_RESPONSE"),
        )
        for body, code in cases:
            with self.subTest(code=code):
                self.assert_transport_error(body, code)

    def test_null_refusal_and_reasoning_content_are_compatible_fields(self) -> None:
        body = completion_body(
            message_extra={"refusal": None, "reasoning_content": None},
        )
        transport = RecordingTransport([FakeResponse(body)])
        receipt = self.client(transport).complete("trusted system", "source")
        self.assertIsNone(receipt.reasoning_content)

    def test_token_and_request_byte_budgets_are_explicit(self) -> None:
        transport = RecordingTransport([])
        client = self.client(transport, max_input_bytes=20)
        with self.assertRaises(ModelTransportError) as context:
            client.complete("trusted system", "this request is too large")
        self.assertEqual(context.exception.code, "REQUEST_TOO_LARGE")
        self.assertEqual(transport.calls, [])
        self.assertEqual(client.remaining_request_budget, 2)

        body = completion_body(
            usage={"prompt_tokens": 1, "completion_tokens": 33, "total_tokens": 34}
        )
        self.assert_transport_error(body, "TOKEN_BUDGET_EXCEEDED", max_tokens=32)

    def test_failed_attempt_reserves_budget_without_retry_or_fallback(self) -> None:
        transport = RecordingTransport(
            [FakeResponse(b"auth body", status=401), FakeResponse(completion_body())]
        )
        client = self.client(transport, request_budget=1)

        with self.assertRaises(ModelTransportError) as context:
            client.complete("trusted system", "first")
        self.assertEqual(context.exception.code, "AUTHENTICATION_FAILED")
        self.assertEqual(client.remaining_request_budget, 0)
        with self.assertRaises(ModelTransportError) as context:
            client.complete("trusted system", "second")
        self.assertEqual(context.exception.code, "REQUEST_BUDGET_EXHAUSTED")
        self.assertEqual(len(transport.calls), 1)

    def test_redirect_is_rejected_without_following_location(self) -> None:
        transport = RecordingTransport(
            [
                FakeResponse(
                    b"redirect body",
                    status=302,
                    headers={"Location": "https://evil.example/collect"},
                )
            ]
        )
        client = self.client(transport)

        with self.assertRaises(ModelTransportError) as context:
            client.complete("trusted system", "hello")

        self.assertEqual(context.exception.code, "REDIRECT_REJECTED")
        self.assertEqual(context.exception.status, 302)
        self.assertEqual(len(transport.calls), 1)

    def test_remote_endpoint_requires_https_permission_and_fee_authorization(self) -> None:
        with self.assertRaises(ModelConfigurationError) as context:
            self.config(
                base_endpoint="https://api.example.test/v1",
                remote_enabled=False,
                fee_authorized=True,
            )
        self.assertEqual(context.exception.code, "REMOTE_NOT_ENABLED")

        with self.assertRaises(ModelConfigurationError) as context:
            self.config(
                base_endpoint="https://api.example.test/v1",
                remote_enabled=True,
                fee_authorized=False,
            )
        self.assertEqual(context.exception.code, "REMOTE_FEE_NOT_AUTHORIZED")

        with self.assertRaises(ModelConfigurationError) as context:
            self.config(
                base_endpoint="http://api.example.test/v1",
                remote_enabled=True,
                fee_authorized=True,
            )
        self.assertEqual(context.exception.code, "NON_LOOPBACK_HTTP_FORBIDDEN")

    def test_endpoint_userinfo_and_query_are_rejected(self) -> None:
        for endpoint, code in (
            ("https://user:pass@example.test/v1", "ENDPOINT_USERINFO_FORBIDDEN"),
            ("https://example.test/v1?token=secret", "ENDPOINT_QUERY_OR_FRAGMENT_FORBIDDEN"),
        ):
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ModelConfigurationError) as context:
                    self.config(
                        base_endpoint=endpoint,
                        remote_enabled=True,
                        fee_authorized=True,
                    )
                self.assertEqual(context.exception.code, code)


if __name__ == "__main__":
    unittest.main()
