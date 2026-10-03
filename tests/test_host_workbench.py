"""Focused contract tests for the inline Host workbench renderer."""

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from convexity_hunter.host_workbench import render_workbench


class HostWorkbenchTests(unittest.TestCase):
    def test_csrf_token_is_attribute_escaped_and_not_written_into_script(self):
        token = '"><script>alert(1)</script>&'
        page = render_workbench(token)
        self.assertIn(
            'name="csrf-token" content="&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;&amp;"',
            page,
        )
        script = page.split("<script>", 1)[1].split("</script>", 1)[0]
        self.assertNotIn(token, script)
        self.assertIn("meta[name=\"csrf-token\"]", script)

    def test_document_is_self_contained_and_uses_only_same_origin_api_paths(self):
        page = render_workbench("csrf-value")
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertIn("<style>", page)
        self.assertIn("<script>", page)
        self.assertNotRegex(page, r"(?i)https?://|<script[^>]+src=|<link[^>]+href=|@import")
        for endpoint in ("/api/status", "/api/profile", "/api/runs"):
            self.assertIn(endpoint, page)
        self.assertIn('"X-CH-CSRF": CSRF_TOKEN', page)
        self.assertIn('method: "GET"', page)
        self.assertIn('method: "POST"', page)
        self.assertIn('credentials: "same-origin"', page)

    def test_three_modes_use_one_unmodified_raw_string_and_closed_post_body(self):
        page = render_workbench("csrf-value")
        for mode in ("world", "event", "direct"):
            self.assertIn('data-mode="{}"'.format(mode), page)
        self.assertIn('name="input"', page)
        self.assertIn('const payload = { mode: state.mode, input: rawInput, bounds: bounds };', page)
        self.assertIn("input: rawInput", page)
        self.assertIn("直接输入：可粘贴精确结构文本或 JSON", page)
        self.assertIn("不自动验证", page)

    def test_exact_explicit_operational_bounds_have_no_defaults(self):
        page = render_workbench("csrf-value")
        names = re.findall(r'<(?:input|textarea)\b[^>]*\bname="([^"]+)"', page)
        self.assertEqual(
            names,
            [
                "input",
                "max_submissions",
                "max_hypotheses",
                "max_browser_rows",
                "max_cases",
                "quote_timeout_seconds",
            ],
        )
        for name in names[1:5]:
            field = re.search(r'<input\b(?=[^>]*\bname="' + name + r'")[^>]*>', page)
            self.assertIsNotNone(field)
            self.assertIn('min="0"', field.group(0))
            self.assertNotRegex(field.group(0), r'\bvalue=')
        timeout = re.search(r'<input\b(?=[^>]*\bname="quote_timeout_seconds")[^>]*>', page)
        self.assertIsNotNone(timeout)
        self.assertIn('max="60"', timeout.group(0))
        self.assertNotRegex(timeout.group(0), r'\bvalue=')
        self.assertIn("timeout <= 0 || timeout > 60", page)

    def test_case_details_are_lazy_id_validated_and_never_rendered_as_html(self):
        page = render_workbench("csrf-value")
        self.assertIn("function safeId(value)", page)
        self.assertIn("encodeURIComponent(value)", page)
        self.assertIn('"/" + encodedId', page)
        self.assertIn('"/cases/" + encodedCaseId', page)
        self.assertIn("button.addEventListener(\"click\", () => loadCase(caseId))", page)
        self.assertIn("case-detail\"), jsonText(data, false)", page)
        self.assertNotIn("innerHTML", page)
        self.assertNotRegex(page, r"(?i)\beval\s*\(|\bimport\s*\(|javascript\s*:")
        self.assertNotIn(".sort(", page)

    def test_untrusted_views_are_text_only_and_statuses_do_not_invent_results(self):
        page = render_workbench("csrf-value")
        self.assertIn("node.textContent = value", page)
        self.assertIn(">尚未连接</p>", page)
        self.assertIn("部分完成（PARTIAL）", page)
        self.assertIn("阻断（BLOCKED）", page)
        self.assertIn("状态缺失（接口未提供）", page)
        self.assertIn("不据此推断研究结论", page)
        self.assertNotIn("没有机会", page)
        self.assertNotIn("M7 已完成", page)
        self.assertNotRegex(page, r"\b(?:100000|0\.005|500|1500)\b")

    def test_no_model_or_credential_configuration_fields_are_accepted(self):
        page = render_workbench("csrf-value")
        self.assertNotIn('name="model"', page)
        self.assertNotIn('name="credential"', page)
        self.assertNotIn('name="api_key"', page)
        self.assertNotIn('name="password"', page)
        self.assertIn("本机状态（只读）", page)


if __name__ == "__main__":
    unittest.main()
