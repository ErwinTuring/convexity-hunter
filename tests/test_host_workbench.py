"""Focused contract tests for the inline Host workbench renderer."""

import pathlib
import json
import re
import shutil
import subprocess
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
        self.assertIn("host-direct-input-v0.1", page)
        self.assertIn("不会因粘贴而自动验证", page)
        self.assertIn("不提供 JSON 示例或默认值", page)

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
        self.assertIn("function safeRunId(value)", page)
        self.assertIn("function safeCaseId(value)", page)
        self.assertIn("value.length > 512", page)
        self.assertIn("encodeURIComponent(value)", page)
        self.assertIn('"/" + encodedId', page)
        self.assertIn('"/cases/" + encodedCaseId', page)
        self.assertIn("button.addEventListener(\"click\", () => loadCase(caseId))", page)
        self.assertIn('typeof data.report === "string"', page)
        self.assertIn('setText(byId("case-detail"), disclosure + "\\n\\n" + data.report)', page)
        self.assertNotIn("innerHTML", page)
        self.assertNotRegex(page, r"(?i)\beval\s*\(|\bimport\s*\(|javascript\s*:")
        self.assertNotIn(".sort(", page)

    def test_not_configured_modes_are_disabled_until_explicitly_configured(self):
        page = render_workbench("csrf-value")
        self.assertIn('data-mode="world" aria-selected="false" disabled', page)
        self.assertIn('data-mode="event" aria-selected="false" disabled', page)
        self.assertIn("status === \"CONFIGURED\"", page)
        self.assertIn("入口标签本身不表示已配置", page)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for DOM behavior tests")
    def test_node_fake_dom_workflows(self):
        page = render_workbench("csrf-value")
        harness = r'''
const vm = require("node:vm");
const fs = require("node:fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const script = input.page.split("<script>")[1].split("</script>")[0];
const runId = "11111111-1111-4111-8111-111111111111";
let innerHtmlWrites = 0;

class Element {
  constructor(id) {
    this.id = id;
    this.className = "";
    this.dataset = {};
    this.disabled = false;
    this.value = "";
    this.attributes = Object.create(null);
    this.children = [];
    this.handlers = Object.create(null);
    this._text = "";
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map((child) => child.textContent).join(""); }
  set innerHTML(value) { innerHtmlWrites += 1; this._text = String(value); this.children = []; }
  addEventListener(name, callback) {
    (this.handlers[name] || (this.handlers[name] = [])).push(callback);
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  appendChild(child) { this.children.push(child); return child; }
  async click() {
    if (this.disabled) return;
    await Promise.all((this.handlers.click || []).map((handler) => handler({ preventDefault() {} })));
  }
}

async function scenario({ mode, cases, responses = [], listedRunId = runId, executors }) {
  const ids = [...input.page.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  const elements = new Map(ids.map((id) => [id, new Element(id)]));
  const tabs = ["world", "event", "direct"].map((name) => {
    const tab = elements.get("tab-" + name);
    tab.dataset.mode = name;
    return tab;
  });
  const calls = [];
  let caseResponseIndex = 0;
  const document = {
    getElementById(id) { return elements.get(id); },
    querySelector(selector) {
      if (selector === 'meta[name="csrf-token"]') return { content: "synthetic-token" };
      throw new Error("unexpected selector " + selector);
    },
    querySelectorAll(selector) {
      if (selector === '[role="tab"][data-mode]') return tabs;
      throw new Error("unexpected selector " + selector);
    },
    createElement() { return new Element("created"); }
  };
  const run = { run_id: runId, mode, status: "COMPLETED", cases };
  const fetch = async (path, options = {}) => {
    calls.push({ path, method: options.method || "GET" });
    if (path === "/api/status") return response({ executors });
    if (path === "/api/profile") return response({ profile: "synthetic" });
    if (path === "/api/runs") return response({ runs: [{ run_id: listedRunId, mode, status: "COMPLETED" }] });
    if (path === "/api/runs/" + encodeURIComponent(runId)) return response(run);
    if (path.startsWith("/api/runs/" + encodeURIComponent(runId) + "/cases/")) {
      const next = responses[Math.min(caseResponseIndex, responses.length - 1)];
      caseResponseIndex += 1;
      return response(next || { case_id: cases[0].case_id, classification: "SYNTHETIC", reasons: [], report: null });
    }
    throw new Error("unexpected fetch path " + path);
  };
  function response(body) {
    return { ok: true, status: 200, async json() { return body; } };
  }
  vm.runInNewContext(script, { document, fetch });
  for (let index = 0; index < 12; index += 1) await new Promise((resolve) => setImmediate(resolve));
  return { elements, tabs, calls, clickRun: () => elements.get("history-list").children[0].children[0].click() };
}

(async () => {
  const report = "<img src=x onerror=alert(1)>\nplain report";
  const direct = await scenario({
    mode: "direct",
    cases: [{ case_id: "case:XYZ:2026-01-02" }],
    responses: [
      { case_id: "case:XYZ:2026-01-02", classification: "RESEARCHABLE", reasons: ["synthetic reason"], report },
      { case_id: "case:XYZ:2026-01-02", classification: "DATA_INSUFFICIENT", reasons: ["missing"], report: null }
    ],
    executors: { world: "NOT_CONFIGURED", event: "NOT_CONFIGURED", direct: "CONFIGURED" }
  });
  if (!direct.tabs[0].disabled || !direct.tabs[1].disabled || direct.tabs[2].disabled) throw new Error("executor availability was not reflected in tabs");
  await direct.clickRun();
  const casePath = "/api/runs/" + runId + "/cases/case%3AXYZ%3A2026-01-02";
  const directCaseGets = () => direct.calls.filter((call) => call.path === casePath && call.method === "GET").length;
  if (directCaseGets() !== 1) throw new Error("direct singleton case was not fetched exactly once automatically");
  const detail = direct.elements.get("case-detail");
  if (!detail.textContent.includes("classification: RESEARCHABLE") || !detail.textContent.includes("reasons: [\"synthetic reason\"]")) throw new Error("classification/reasons disclosure missing");
  if (!detail.textContent.endsWith(report)) throw new Error("report was not shown as literal text");
  if (innerHtmlWrites !== 0) throw new Error("untrusted report reached innerHTML");
  detail.textContent = "STALE REPORT";
  await direct.elements.get("case-list").children[0].children[0].click();
  if (directCaseGets() !== 2 || detail.textContent.includes("STALE REPORT")) throw new Error("null report did not clear stale content");
  if (!detail.textContent.includes("报告字段为 null")) throw new Error("null report disclosure was not shown honestly");

  for (const [mode, cases] of [["world", [{ case_id: "world:one" }, { case_id: "world:two" }]], ["event", [{ case_id: "event:one" }]]]) {
    const lane = await scenario({
      mode, cases,
      executors: { world: "CONFIGURED", event: "CONFIGURED", direct: "NOT_CONFIGURED" },
      responses: [{ case_id: cases[0].case_id, classification: "SYNTHETIC", reasons: [], report: "on demand" }]
    });
    await lane.clickRun();
    if (lane.calls.some((call) => call.path.includes("/cases/"))) throw new Error(mode + " cases were auto-selected");
    if (!lane.elements.get("case-detail").textContent.includes("尚未选择用例")) throw new Error(mode + " detail was not left on demand");
    await lane.elements.get("case-list").children[0].children[0].click();
    if (!lane.calls.some((call) => call.path.endsWith(encodeURIComponent(cases[0].case_id)))) throw new Error(mode + " human selection did not load its case");
  }

  for (const unsafeId of ["../outside", ".", "..", "bad\u0000id", "x".repeat(513)]) {
    const unsafeCase = await scenario({
      mode: "direct", cases: [{ case_id: unsafeId }],
      executors: { world: "NOT_CONFIGURED", event: "NOT_CONFIGURED", direct: "CONFIGURED" }
    });
    await unsafeCase.clickRun();
    if (unsafeCase.calls.some((call) => call.path.includes("/cases/"))) throw new Error("unsafe case ID was not rejected");
  }

  const unsafeRun = await scenario({
    mode: "direct", cases: [{ case_id: "case:one" }], listedRunId: "bad/run",
    executors: { world: "NOT_CONFIGURED", event: "NOT_CONFIGURED", direct: "CONFIGURED" }
  });
  if (unsafeRun.elements.get("history-list").children[0].children.length !== 0) throw new Error("unsafe run ID received an action");
  if (unsafeRun.calls.some((call) => call.path.includes("bad"))) throw new Error("unsafe run ID reached fetch");

  const unknown = await scenario({
    mode: "direct", cases: [],
    executors: { world: "UNKNOWN", event: "NOT_CONFIGURED", direct: "NOT_CONFIGURED" }
  });
  if (unknown.tabs.some((tab) => !tab.disabled)) throw new Error("unknown executor status was treated as configured");
  if (unknown.calls.some((call) => !["/api/status", "/api/profile", "/api/runs"].includes(call.path))) throw new Error("unexpected external/market call");
  console.log("fake DOM behavior checks passed");
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
'''
        result = subprocess.run(
            ["node", "-e", harness],
            input=json.dumps({"page": page}),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
