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
        self.assertIn("Core 分类不是买入建议或估值判断", page)
        self.assertIn("Ask 基准仅为 INDICATIVE_ONLY", page)
        self.assertIn("未知成本显示为未提供，不按 0 处理", page)
        self.assertIn("批量状态只描述已保留研究分支；不证明原始请求已全面核实。", page)

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

    def test_batch_host_status_uses_completed_partial_blocked_vocabulary(self):
        page = render_workbench("csrf-value")
        for status, label in (
            ("COMPLETED", "已完成"),
            ("PARTIAL", "部分完成"),
            ("BLOCKED", "阻断"),
        ):
            self.assertIn('{}: "{}（{}）"'.format(status, label, status), page)
        self.assertIn('"Host 状态：" + displayedStatus(summary.host_status)', page)
        self.assertNotIn("COMPELETED", page)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required for DOM behavior tests")
    def test_node_fake_dom_workflows(self):
        page = render_workbench("csrf-value")
        harness = r'''
const vm = require("node:vm");
const fs = require("node:fs");
const crypto = require("node:crypto");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const script = input.page.split("<script>")[1].split("</script>")[0];
const runId = "11111111-1111-4111-8111-111111111111";
const caseKeyFor = (caseId) => crypto.createHash("sha256").update(caseId, "utf8").digest("hex");
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

async function scenario({ mode, cases, batchSummary = null, events, runStatus = "COMPLETED", responses = [], listedRunId = runId, executors }) {
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
  const run = { run_id: runId, mode, status: runStatus, cases, batch_summary: batchSummary, events };
  const fetch = async (path, options = {}) => {
    calls.push({ path, method: options.method || "GET" });
    if (path === "/api/status") return response({ executors });
    if (path === "/api/profile") return response({ profile: "synthetic" });
    if (path === "/api/runs") return response({ runs: [{ run_id: listedRunId, mode, status: runStatus }] });
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

  const digest = (letter) => letter.repeat(64);
  const grounderOutcome = {
    schema_version: "host-grounder-stage-outcome-v0.1",
    grounder_status: "COMPLETED", source_status: "UNKNOWN", semantic_status: "RECEIPT_VALIDATED",
    builder_status: "COMPLETED", submission_status: "MISSING", ei_status: "NOT_RUN",
    counts: { source_body_count: 1, claim_count: 1, hypothesis_count: 0, field_binding_count: 1, coverage_count: 2 },
    diagnostic_counts: [
      { code: "CLAIM_NOT_PROJECTABLE", count: 1 },
      { code: "NO_PROJECTABLE_HYPOTHESIS", count: 1 }
    ],
    coverage: [
      { index: 0, subquestion_id: "question-1", model_status: "unresolved", validator_status: "unresolved", claim_count: 0, gap_present: true },
      { index: 1, subquestion_id: "question-2", model_status: "contradicted", validator_status: "contradicted", claim_count: 1, gap_present: false }
    ],
    provenance: {
      receipt_schema_version: "semantic-validation-v0.2",
      audit_schema_version: "host-grounder-quote-localization-audit-v0.3",
      producer_wire_version: "grounder-output-v0.3",
      producer_prompt_version: "host-grounder-discovery-prompt-v0.6",
      verifier_wire_version: "semantic-verdict-v0.3",
      validator_version: "host-grounder-semantic-verifier-prompt-v0.7",
      localizer_version: "host-evidence-catalog-resolver-v0.1",
      catalog_schema_version: "host-grounder-evidence-catalog-v0.1",
      catalog_generator_version: "host-evidence-paragraph-generator-v0.1",
      canonical_input_sha256: digest("a"), host_raw_input_sha256: digest("b"),
      audit_sha256: digest("c"), catalog_sha256: digest("d"),
      producer_content_sha256: digest("e"), normalized_envelope_sha256: digest("f"),
      source_body_hashes: [{ source_id: "https://private.example/path?token=DO_NOT_DISPLAY", sha256: digest("1") }],
      model_calls: [
        { role: "discovery", provider: "PRIVATE_PROVIDER", requested_model: "PRIVATE_MODEL_NAME", returned_model: "PRIVATE_MODEL_NAME", finish_reason: "stop", bytes_sent: 10, bytes_received: 20 },
        { role: "semantic", provider: "PRIVATE_PROVIDER", requested_model: "PRIVATE_MODEL_NAME", returned_model: "PRIVATE_MODEL_NAME", finish_reason: "stop", bytes_sent: 30, bytes_received: 40 }
      ],
      raw_model_body: "RAW_MODEL_BODY_SENTINEL",
      config_path: "CONFIG_PATH_SENTINEL",
      credential: "CREDENTIAL_SENTINEL"
    },
    raw_body: "RAW_BODY_SENTINEL"
  };
  const grounder = await scenario({
    mode: "event", cases: [], runStatus: "BLOCKED",
    events: [{
      event: "stage_finished", stage: "grounder", stage_id: "stage-grounder-1", status: "COMPLETED",
      started_at: "2026-10-04T00:00:00.000Z", completed_at: "2026-10-04T00:00:01.000Z",
      diagnostics: ["GROUNDING_NO_SUBMISSION"], outcome: grounderOutcome,
      private_future_field: "UNKNOWN_EVENT_FIELD_SENTINEL"
    }],
    executors: { world: "NOT_CONFIGURED", event: "NOT_CONFIGURED", direct: "CONFIGURED" }
  });
  await grounder.clickRun();
  if (!grounder.tabs[1].disabled) throw new Error("historical Grounder detail enabled the Event entry");
  const grounderText = grounder.elements.get("run-events").textContent;
  for (const expected of [
    "阶段状态：已完成（COMPLETED）", "Grounder：COMPLETED", "source_status：UNKNOWN（不是搜索成功）",
    "semantic_status：RECEIPT_VALIDATED（不是事实真理）", "builder_status：COMPLETED",
    "EI submission：MISSING", "EI：NOT_RUN", "没有 Core 结果或报告",
    "诊断计数（保留负面结果；不是评分）", "CLAIM_NOT_PROJECTABLE：1",
    "model=unresolved", "validator=contradicted", "Hypothesis 数：0", "Coverage 数：2",
    "Producer wire：grounder-output-v0.3", digest("a"), "发送字节=10", "接收字节=40"
  ]) {
    if (!grounderText.includes(expected)) throw new Error("Grounder safe stage field was omitted: " + expected);
  }
  if (!grounder.elements.get("run-status").textContent.includes("阻断（BLOCKED）")) throw new Error("blocked run status was not kept distinct from completed Grounder stage");
  for (const forbidden of [
    "PRIVATE_PROVIDER", "PRIVATE_MODEL_NAME", "RAW_MODEL_BODY_SENTINEL", "RAW_BODY_SENTINEL",
    "CONFIG_PATH_SENTINEL", "CREDENTIAL_SENTINEL", "DO_NOT_DISPLAY", "UNKNOWN_EVENT_FIELD_SENTINEL"
  ]) {
    if (grounderText.includes(forbidden)) throw new Error("private or unknown Grounder data was displayed: " + forbidden);
  }
  if (!grounderText.includes("Coverage #0") || !grounderText.includes("Coverage #1")) throw new Error("coverage rows/order were omitted");
  if (grounderText.includes("question-1") || grounderText.includes("question-2")) throw new Error("unbounded subquestion identifiers were exposed");
  if (innerHtmlWrites !== 0) throw new Error("Grounder outcome reached innerHTML");
  if (grounder.calls.some((call) => call.path.includes("/cases/"))) throw new Error("Grounder stage rendering triggered an extra detail request");

  for (const [mode, cases] of [["world", [{ case_id: "world:one" }, { case_id: "world:two" }]], ["event", [{ case_id: "event:one" }]]]) {
    const keyedCases = cases.map((item) => ({ case_id: item.case_id, case_key: caseKeyFor(item.case_id) }));
    const lane = await scenario({
      mode, cases: keyedCases,
      batchSummary: {
        entry_origin: mode.toUpperCase(), case_count: cases.length, unavailable_count: 0,
        disposition_counts: [], case_ids: keyedCases.map((item) => item.case_id), reasons: [],
        case_summaries: keyedCases.map((item) => ({ case_id: item.case_id, case_key: item.case_key, reasons: [], legs: [] })),
        unavailable_case_ids: []
      },
      executors: { world: "CONFIGURED", event: "CONFIGURED", direct: "NOT_CONFIGURED" },
      responses: [{ case_id: cases[0].case_id, case_key: keyedCases[0].case_key, classification: "SYNTHETIC", reasons: [], report: "on demand" }]
    });
    await lane.clickRun();
    if (lane.calls.some((call) => call.path.includes("/cases/"))) throw new Error(mode + " cases were auto-selected");
    if (!lane.elements.get("case-detail").textContent.includes("尚未选择用例")) throw new Error(mode + " detail was not left on demand");
    await lane.elements.get("case-list").children[0].children[0].click();
    if (!lane.calls.some((call) => call.path.endsWith(encodeURIComponent(keyedCases[0].case_key)))) throw new Error(mode + " human selection did not load its case by case_key");
  }

  const longBatchId = "研究/✨:" + "x".repeat(600);
  const batchCaseKey = caseKeyFor(longBatchId);
  const zetaCaseKey = caseKeyFor("world:zeta");
  const muCaseKey = caseKeyFor("world:mu");
  const batchCases = [
    {
      case_id: "world:zeta", case_key: zetaCaseKey, disposition: "DATA_INSUFFICIENT_CORE", geometry_status: "AVAILABLE",
      ask_basis_per_underlying_unit: "0.25", reasons: ["cost_ledger_missing"], structure_kind: "STRADDLE",
      legs: [
        { leg_id: "call-leg", underlying: "XYZ", option_type: "CALL", expiration: "2026-12-18", strike: "95.00", quantity: 1, contract_multiplier: 100 },
        { leg_id: "put-leg", underlying: "XYZ", option_type: "PUT", expiration: "2026-12-18", strike: "95.00", quantity: 1, contract_multiplier: 100 }
      ],
      budget_status: "DATA_INSUFFICIENT", single_cost_upper_bound: null,
      repeated_cost_upper_bound: null, single_loss_fraction: "0.01", repeated_loss_fraction: "0.03"
    },
    {
      case_id: longBatchId, case_key: batchCaseKey, disposition: "RESEARCHABLE_CONVEXITY", geometry_status: "AVAILABLE",
      ask_basis_per_underlying_unit: "1.20", reasons: [], structure_kind: "CALL", legs: [],
      budget_status: "AVAILABLE", single_cost_upper_bound: "120.00", repeated_cost_upper_bound: "360.00",
      single_loss_fraction: "0.02", repeated_loss_fraction: "0.06"
    },
    {
      case_id: "world:mu", case_key: muCaseKey, disposition: "REJECT", geometry_status: "REJECTED",
      ask_basis_per_underlying_unit: null, reasons: ["unsupported_geometry"], structure_kind: "PUT", legs: [],
      budget_status: "NOT_ASSESSED", single_cost_upper_bound: null, repeated_cost_upper_bound: null,
      single_loss_fraction: null, repeated_loss_fraction: null
    }
  ];
  const unavailableBatchId = "世界/不可用" + "z".repeat(300);
  const unavailableBatchKey = caseKeyFor(unavailableBatchId);
  const batch = await scenario({
    mode: "world",
    cases: batchCases.map((item) => ({ case_id: item.case_id, case_key: item.case_key })),
    batchSummary: {
      entry_origin: "WORLD", case_count: 3, unavailable_count: 1,
      host_status: "PARTIAL",
      disposition_counts: { DATA_INSUFFICIENT_CORE: 1, RESEARCHABLE_CONVEXITY: 1, REJECT: 1 },
      case_ids: batchCases.map((item) => item.case_id), reasons: ["partial_summary_reason"],
      case_summaries: batchCases,
      unavailable_case_ids: [unavailableBatchId],
      unavailable_cases: [{ case_id: unavailableBatchId, case_key: unavailableBatchKey, reasons: ["branch_unavailable"] }]
    },
    executors: { world: "CONFIGURED", event: "CONFIGURED", direct: "NOT_CONFIGURED" },
    responses: [
      { case_id: longBatchId, case_key: batchCaseKey, classification: "SYNTHETIC", reasons: [], report: "on demand" },
      { case_id: unavailableBatchId, case_key: unavailableBatchKey, classification: "UNAVAILABLE", reasons: ["branch_unavailable"], report: null }
    ]
  });
  await batch.clickRun();
  if (batch.calls.some((call) => call.path.includes("/cases/"))) throw new Error("batch compact rows triggered case detail GETs");
  const summaryView = batch.elements.get("batch-summary-view").textContent;
  if (!summaryView.includes("已计算案例数：3") || !summaryView.includes("不可用分支数：1")) throw new Error("batch case counts were not displayed with frozen labels");
  if (summaryView.includes("可用用例数") || summaryView.includes("不可用用例数")) throw new Error("batch counts imply availability instead of computed/unavailable branches");
  if (!summaryView.includes("Host 状态：部分完成（PARTIAL）")) throw new Error("batch host_status was not displayed");
  if (!summaryView.includes("partial_summary_reason") || !summaryView.includes(unavailableBatchId) || !summaryView.includes("不可用分支 case_id：" + unavailableBatchId)) throw new Error("summary reasons or string-only unavailable case IDs were omitted");
  if (!summaryView.includes("DATA_INSUFFICIENT_CORE：1") || !summaryView.includes("RESEARCHABLE_CONVEXITY：1")) throw new Error("batch disposition counts were not displayed");
  const unavailableRows = batch.elements.get("unavailable-case-list").children;
  if (unavailableRows.length !== 1 || unavailableRows[0].children[0].textContent !== unavailableBatchId) throw new Error("unavailable sidecar did not preserve exact case_id text");
  if (!unavailableRows[0].textContent.includes(unavailableBatchKey) || !unavailableRows[0].textContent.includes("branch_unavailable")) throw new Error("unavailable sidecar key or reasons were omitted");
  const compactRows = batch.elements.get("batch-case-list").children;
  if (compactRows.length !== 3) throw new Error("not every compact case row was displayed");
  const compactText = batch.elements.get("batch-case-list").textContent;
  if (!(compactText.indexOf("world:zeta") < compactText.indexOf(longBatchId) && compactText.indexOf(longBatchId) < compactText.indexOf("world:mu"))) throw new Error("compact rows were reordered");
  if (!compactRows[0].textContent.includes("2026-12-18") || !compactRows[0].textContent.includes("95.00") || !compactRows[0].textContent.includes("cost_ledger_missing")) throw new Error("compact leg/date/Decimal-string fields were not displayed");
  if (!compactRows[0].textContent.includes("INDICATIVE_ONLY") || !compactRows[0].textContent.includes("单次成本上界：未提供")) throw new Error("Ask authority or unknown-cost presentation was changed");
  if (!compactRows[0].textContent.includes("case_key：" + zetaCaseKey)) throw new Error("compact case_key was omitted");
  if (!compactText.includes(longBatchId) || batch.elements.get("case-list").children[1].children[0].textContent !== longBatchId) throw new Error("batch case ID was filtered or altered for display");
  await batch.elements.get("case-list").children[1].children[0].click();
  if (!batch.calls.some((call) => call.path === "/api/runs/" + runId + "/cases/" + batchCaseKey && call.method === "GET")) throw new Error("explicit batch case click did not use case_key");
  if (batch.calls.some((call) => call.path.includes(encodeURIComponent(longBatchId)))) throw new Error("raw batch case ID was used in the detail path");
  await unavailableRows[0].children[0].click();
  if (!batch.calls.some((call) => call.path === "/api/runs/" + runId + "/cases/" + unavailableBatchKey && call.method === "GET")) throw new Error("explicit unavailable-case click did not use sidecar case_key");
  if (batch.calls.some((call) => call.path.includes(encodeURIComponent(unavailableBatchId)))) throw new Error("raw unavailable case ID was used in the detail path");
  if (!batch.elements.get("case-detail").textContent.includes("报告字段为 null")) throw new Error("unavailable sidecar detail did not preserve null-report disclosure");

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
