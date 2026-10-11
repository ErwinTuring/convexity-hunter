"""Self-contained Chinese HTML workbench for the frozen local Host API.

This module renders a browser view only. It does not start a server, call the
model, read sources, or invoke Core. The host application owns HTTP routing.
"""

from html import escape


def render_workbench(csrf_token: str) -> str:
    """Return the complete inline workbench document for a host-supplied token."""

    if not isinstance(csrf_token, str):
        raise TypeError("csrf_token must be str")
    safe_token = escape(csrf_token, quote=True)
    return _DOCUMENT.replace("__CH_CSRF_TOKEN__", safe_token)


_DOCUMENT = r'''<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="csrf-token" content="__CH_CSRF_TOKEN__">
  <title>研究工作台</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; color: #18232b; background: #f3f6f7; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    main { width: min(1100px, 100% - 32px); margin: 28px auto 64px; }
    h1, h2, h3, p { margin-top: 0; }
    h1 { margin-bottom: 8px; font-size: clamp(1.6rem, 4vw, 2.2rem); }
    h2 { font-size: 1.15rem; }
    h3 { margin-bottom: 8px; font-size: 1rem; }
    .muted, .help { color: #52616a; }
    .banner, .panel { border: 1px solid #d5dfe3; border-radius: 12px; background: #fff; padding: 18px; margin: 16px 0; }
    .banner { border-left: 5px solid #708793; }
    .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
    .tabs { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 10px; }
    button, input, textarea { font: inherit; }
    button { border: 1px solid #8b9ba3; border-radius: 8px; padding: 9px 13px; background: #fff; color: #18232b; cursor: pointer; }
    button:hover { background: #edf3f5; }
    button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 3px solid #76a9c2; outline-offset: 2px; }
    [role="tab"][aria-selected="true"] { border-color: #155d78; background: #155d78; color: #fff; }
    label { display: block; margin: 12px 0 5px; font-weight: 650; }
    textarea { display: block; width: 100%; min-height: 170px; resize: vertical; }
    input { display: block; width: 100%; min-height: 40px; }
    textarea, input { border: 1px solid #9aaab1; border-radius: 7px; padding: 9px; background: #fff; color: #18232b; }
    .bounds { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 14px; }
    .submit-row { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-top: 18px; }
    .primary { border-color: #155d78; background: #155d78; color: #fff; }
    .primary:disabled { opacity: .55; cursor: wait; }
    .record-list { display: grid; gap: 8px; }
    .record { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; border-top: 1px solid #e1e8eb; padding: 10px 0; }
    .record:first-child { border-top: 0; }
    .compact-case { border-top: 1px solid #e1e8eb; padding: 12px 0; overflow-wrap: anywhere; }
    .compact-case:first-child { border-top: 0; }
    .compact-case p, .compact-case div { margin: 5px 0; }
    .compact-leg { margin-left: 14px !important; }
    .record-id { overflow-wrap: anywhere; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
    pre { max-height: 480px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; border-radius: 8px; padding: 12px; background: #f2f5f6; color: #18232b; }
    .message { min-height: 1.5em; color: #344d59; }
    .status-pill { display: inline-block; border: 1px solid #b9c8ce; border-radius: 999px; padding: 3px 9px; background: #f3f6f7; }
    @media (max-width: 720px) { .grid, .bounds { grid-template-columns: 1fr; } main { width: min(100% - 20px, 1100px); margin-top: 16px; } .panel { padding: 14px; } }
  </style>
</head>
<body>
<main>
  <header>
    <p class="muted">本机研究界面</p>
    <h1>研究工作台</h1>
    <p id="connection-state" class="status-pill" role="status" aria-live="polite">尚未连接</p>
  </header>

  <section class="banner" aria-label="使用边界">
    <strong>边界说明</strong>
    <p class="help">本页只提交原始输入和你填写的操作预算，并显示本机接口返回内容。不会在浏览器中调用模型、读取来源或计算研究结果；Direct 输入也不会因粘贴而自动验证。模型与凭证不在本页配置。</p>
    <p class="help">入口是否可用以本机状态中的 executors 为准；入口标签本身不表示已配置。</p>
    <p class="help">所有预算项均须明确填写；本页不预填预算或经济数值。状态、批准 Profile 与历史记录仅按需读取，不代表运行结果或建议。</p>
  </section>

  <div class="grid">
    <section class="panel" aria-labelledby="status-heading">
      <h2 id="status-heading">本机状态（只读）</h2>
      <pre id="status-view" aria-live="polite">尚未读取状态。</pre>
    </section>
    <section class="panel" aria-labelledby="profile-heading">
      <h2 id="profile-heading">批准的研究 Profile（只读）</h2>
      <pre id="profile-view" aria-live="polite">尚未读取 Profile。</pre>
    </section>
  </div>

  <section class="panel" aria-labelledby="input-heading">
    <h2 id="input-heading">新建研究运行</h2>
    <div class="tabs" role="tablist" aria-label="研究入口">
      <button type="button" role="tab" id="tab-world" data-mode="world" aria-selected="false" disabled>世界</button>
      <button type="button" role="tab" id="tab-event" data-mode="event" aria-selected="false" disabled>事件</button>
      <button type="button" role="tab" id="tab-direct" data-mode="direct" aria-selected="false" disabled>直接输入</button>
    </div>
    <p id="mode-availability" class="help" role="status" aria-live="polite">正在读取入口配置；尚不能确认哪些入口可用。</p>
    <p id="mode-help" class="help">请选择本机状态中已配置的入口。</p>
    <form id="run-form">
      <label id="raw-input-label" for="raw-input">原始输入</label>
      <textarea id="raw-input" name="input" autocomplete="off" required></textarea>
      <p id="input-help" class="help">文本按原样发送；仅检查是否为空，不在浏览器改写或解析。</p>

      <h3>显式操作预算</h3>
      <p class="help">四项上限填写非负整数；报价超时填写大于 0 且不超过 60 秒的数值。留空不会自动补默认值。</p>
      <div class="bounds">
        <div><label for="bound-max-submissions">max_submissions</label><input id="bound-max-submissions" name="max_submissions" type="number" min="0" step="1" required></div>
        <div><label for="bound-max-hypotheses">max_hypotheses</label><input id="bound-max-hypotheses" name="max_hypotheses" type="number" min="0" step="1" required></div>
        <div><label for="bound-max-browser-rows">max_browser_rows</label><input id="bound-max-browser-rows" name="max_browser_rows" type="number" min="0" step="1" required></div>
        <div><label for="bound-max-cases">max_cases</label><input id="bound-max-cases" name="max_cases" type="number" min="0" step="1" required></div>
        <div><label for="bound-quote-timeout">quote_timeout_seconds</label><input id="bound-quote-timeout" name="quote_timeout_seconds" type="number" min="0.000001" max="60" step="any" required></div>
      </div>
      <div class="submit-row">
        <button class="primary" id="submit-run" type="submit">提交新运行</button>
        <span id="submit-state" class="message" role="status" aria-live="polite"></span>
      </div>
    </form>
  </section>

  <div class="grid">
    <section class="panel" aria-labelledby="history-heading">
      <h2 id="history-heading">历史运行</h2>
      <p class="help">按接口返回顺序显示；不排序、不筛选或评价运行。</p>
      <div id="history-state" class="message" role="status" aria-live="polite">尚未读取历史。</div>
      <div id="history-list" class="record-list"></div>
    </section>
    <section class="panel" aria-labelledby="run-heading">
      <h2 id="run-heading">运行详情</h2>
      <p id="run-identity" class="muted">尚未选择运行。</p>
      <p id="run-status" class="status-pill">状态缺失（尚未读取）</p>
      <h3>诊断</h3><pre id="run-diagnostics">运行响应尚未提供。</pre>
      <h3>阶段事件</h3><pre id="run-events">运行响应尚未提供。</pre>
      <h3>其他运行快照</h3><pre id="run-snapshot">尚未读取运行快照。</pre>
      <h3>批量研究摘要</h3>
      <p class="help">Core 分类不是买入建议或估值判断；Ask 基准仅为 INDICATIVE_ONLY。未知成本显示为未提供，不按 0 处理。批量状态只描述已保留研究分支；不证明原始请求已全面核实。</p>
      <pre id="batch-summary-view">运行响应尚未提供批量摘要。</pre>
      <div id="batch-case-list" class="record-list">尚未读取紧凑用例行。</div>
      <h4>不可用分支详情（按需读取）</h4>
      <div id="unavailable-case-list" class="record-list">尚未读取不可用分支详情。</div>
      <h3>用例详情（按需读取）</h3>
      <p class="help">选择稳定 case_id 后才读取对应详情；打开详情不会重新运行。</p>
      <div id="case-list" class="record-list">尚未读取用例索引。</div>
      <h3>所选用例详情</h3><pre id="case-detail">尚未选择用例。</pre>
    </section>
  </div>
</main>
<script>
"use strict";
(() => {
  const API = Object.freeze({
    status: "/api/status",
    profile: "/api/profile",
    runs: "/api/runs"
  });
  const CSRF_TOKEN = document.querySelector('meta[name="csrf-token"]').content;
  const state = { mode: null, runId: null, runMode: null, batchCaseKeys: new Map(), unavailableBatchCaseIds: new Set() };
  const modes = ["world", "event", "direct"];
  const integerBoundNames = ["max_submissions", "max_hypotheses", "max_browser_rows", "max_cases"];
  const privateKey = /token|secret|password|credential|authorization|cookie|api[_-]?key/i;

  function byId(id) { return document.getElementById(id); }
  function setText(node, value) { node.textContent = value; }
  function isRecord(value) { return value !== null && typeof value === "object" && !Array.isArray(value); }

  function safeCopy(value, omitCaseDetails) {
    if (Array.isArray(value)) return value.map((item) => safeCopy(item, omitCaseDetails));
    if (!isRecord(value)) return value;
    const copy = Object.create(null);
    for (const key of Object.keys(value)) {
      if (privateKey.test(key)) continue;
      if (omitCaseDetails && /^(cases?|case_details?|caseDetails?)$/i.test(key)) continue;
      copy[key] = safeCopy(value[key], omitCaseDetails);
    }
    return copy;
  }

  function jsonText(value, omitCaseDetails) {
    const safeValue = safeCopy(value, omitCaseDetails);
    const encoded = JSON.stringify(safeValue, null, 2);
    return encoded === undefined ? "接口未提供可显示详情。" : encoded;
  }

  function safeRunId(value) {
    if (typeof value !== "string" || value.length < 1 || value.length > 128 || !/^[A-Fa-f0-9-]+$/.test(value)) return null;
    return encodeURIComponent(value);
  }

  function safeCaseId(value) {
    if (typeof value !== "string" || value.length < 1 || value.length > 512 || value === "." || value === ".." || !/^[A-Za-z0-9._~:-]+$/.test(value)) return null;
    return encodeURIComponent(value);
  }

  function safeBatchCaseKey(value) {
    if (typeof value !== "string" || !/^[0-9a-f]{64}$/.test(value)) return null;
    return encodeURIComponent(value);
  }

  function applyExecutorAvailability(data) {
    const executors = isRecord(data) && isRecord(data.executors) ? data.executors : null;
    const summaries = [];
    for (const mode of modes) {
      const tab = byId("tab-" + mode);
      const status = executors && typeof executors[mode] === "string" ? executors[mode] : "UNKNOWN";
      const configured = status === "CONFIGURED";
      tab.disabled = !configured;
      tab.title = configured ? "本机状态：CONFIGURED" : "本机状态：" + status;
      if (state.mode === mode && !configured) state.mode = null;
      summaries.push(mode + "：" + status);
    }
    for (const mode of modes) {
      byId("tab-" + mode).setAttribute("aria-selected", state.mode === mode ? "true" : "false");
    }
    setText(
      byId("mode-availability"),
      executors
        ? "入口状态（本机 executors）：" + summaries.join("；")
        : "入口状态未提供或不可识别；为避免误报，入口保持禁用。"
    );
    if (state.mode === null) {
      setText(byId("mode-help"), "请选择本机状态中已配置且可用的入口。");
    }
  }

  function displayedStatus(value) {
    if (typeof value !== "string" || value.length === 0) return "状态缺失（接口未提供）";
    const labels = {
      QUEUED: "排队中（QUEUED）",
      RUNNING: "运行中（RUNNING）",
      COMPLETED: "已完成（COMPLETED）",
      PARTIAL: "部分完成（PARTIAL）",
      BLOCKED: "阻断（BLOCKED）",
      FAILED: "失败（FAILED）",
      INTERRUPTED: "已中断（INTERRUPTED）"
    };
    return Object.prototype.hasOwnProperty.call(labels, value) ? labels[value] : value;
  }

  async function getJson(path) {
    const response = await fetch(path, {
      method: "GET",
      headers: { "Accept": "application/json" },
      credentials: "same-origin",
      cache: "no-store"
    });
    if (!response.ok) throw new Error("HTTP " + response.status);
    return response.json();
  }

  async function loadStatus() {
    try {
      const data = await getJson(API.status);
      applyExecutorAvailability(data);
      setText(byId("connection-state"), "已读取本机状态响应");
      setText(byId("status-view"), jsonText(data, false));
    } catch (error) {
      applyExecutorAvailability(null);
      setText(byId("connection-state"), "尚未连接：状态读取失败");
      setText(byId("status-view"), "本机状态暂不可用（" + error.message + "）。");
    }
  }

  async function loadProfile() {
    try {
      const data = await getJson(API.profile);
      setText(byId("profile-view"), jsonText(data, false));
    } catch (error) {
      setText(byId("profile-view"), "批准的 Profile 暂不可用（" + error.message + "）。");
    }
  }

  function addHistoryRow(metadata) {
    const row = document.createElement("div");
    row.className = "record";
    if (!isRecord(metadata)) {
      setText(row, "历史记录元数据格式不可识别；未发起详情读取。");
      byId("history-list").appendChild(row);
      return;
    }
    const id = safeRunId(metadata.run_id);
    if (id === null) {
      setText(row, "记录缺少可用 run_id；未发起详情读取。");
      byId("history-list").appendChild(row);
      return;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "record-id";
    setText(button, metadata.run_id);
    button.addEventListener("click", () => loadRun(metadata.run_id));
    const status = document.createElement("span");
    status.className = "status-pill";
    setText(status, displayedStatus(metadata.status));
    row.appendChild(button);
    row.appendChild(status);
    for (const key of ["mode", "created_at"]) {
      if (typeof metadata[key] === "string") {
        const detail = document.createElement("span");
        setText(detail, key + ": " + metadata[key]);
        row.appendChild(detail);
      }
    }
    byId("history-list").appendChild(row);
  }

  async function loadRuns() {
    const list = byId("history-list");
    list.textContent = "";
    setText(byId("history-state"), "正在读取历史运行……");
    try {
      const data = await getJson(API.runs);
      if (!isRecord(data) || !Array.isArray(data.runs)) {
        setText(byId("history-state"), "历史响应未提供可识别的 runs 列表。");
        return;
      }
      if (data.runs.length === 0) {
        setText(byId("history-state"), "接口返回的历史运行列表为空。");
        return;
      }
      setText(byId("history-state"), "历史运行（保持接口返回顺序）。");
      for (const item of data.runs) addHistoryRow(item);
    } catch (error) {
      setText(byId("history-state"), "历史读取失败（" + error.message + "）。");
    }
  }

  function renderCaseIndex(cases) {
    const list = byId("case-list");
    const batchMode = state.runMode === "world" || state.runMode === "event";
    list.textContent = "";
    if (!Array.isArray(cases)) {
      setText(list, "运行响应未提供可识别的用例索引。");
      return;
    }
    if (cases.length === 0) {
      setText(list, "该运行响应中的用例列表为空；不据此推断研究结论。");
      return;
    }
    for (const entry of cases) {
      const caseId = caseIdFromEntry(entry);
      const row = document.createElement("div");
      row.className = "record";
      if (batchMode) {
        const caseKey = isRecord(entry) && entry.case_key !== undefined
          ? entry.case_key : state.batchCaseKeys.get(caseId);
        const encodedCaseKey = safeBatchCaseKey(caseKey);
        if (typeof caseId !== "string") {
          setText(row, "用例 ID：" + compactScalar(caseId) + "；未发起详情读取。");
        } else if (state.unavailableBatchCaseIds.has(caseId) || (isRecord(entry) && entry.classification === "UNAVAILABLE")) {
          setText(row, "用例 ID：" + caseId + "；该分支不可用，未发起详情读取。");
        } else if (encodedCaseKey === null) {
          setText(row, "用例 ID：" + caseId + "；缺少有效 case_key，未发起详情读取。");
        } else {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "record-id";
          setText(button, caseId);
          button.addEventListener("click", () => loadCase(caseId, caseKey));
          row.appendChild(button);
        }
      } else {
        const encodedCaseId = safeCaseId(caseId);
        if (encodedCaseId === null) {
          setText(row, "用例条目缺少受支持的稳定 case_id；未发起详情读取。");
        } else {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "record-id";
          setText(button, caseId);
          button.addEventListener("click", () => loadCase(caseId));
          row.appendChild(button);
        }
      }
      list.appendChild(row);
    }
  }

  function caseIdFromEntry(entry) {
    return typeof entry === "string" ? entry : (isRecord(entry) ? entry.case_id : null);
  }

  function compactScalar(value) {
    if (value === null) return "未提供";
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
    return "字段格式不可识别";
  }

  function compactStringList(value) {
    if (!Array.isArray(value)) return value === undefined ? "接口未提供" : "字段格式不可识别";
    if (value.length === 0) return "无";
    return value.map((item) => typeof item === "string" ? item : "字段格式不可识别").join("；");
  }

  function compactCount(value) {
    return Number.isSafeInteger(value) && value >= 0 ? String(value) : "接口未提供可识别计数";
  }

  function dispositionCountText(value) {
    const entries = [];
    if (Array.isArray(value)) {
      for (const entry of value) {
        if (Array.isArray(entry) && entry.length === 2 && typeof entry[0] === "string") {
          entries.push(entry[0] + "：" + compactCount(entry[1]));
        } else {
          entries.push("计数项格式不可识别");
        }
      }
    } else if (isRecord(value)) {
      for (const name of Object.keys(value)) entries.push(name + "：" + compactCount(value[name]));
    } else {
      return "接口未提供可识别的 disposition_counts。";
    }
    return entries.length ? entries.join("\n") : "无";
  }

  function appendCompactField(parent, label, value) {
    const line = document.createElement("div");
    setText(line, label + "：" + compactScalar(value));
    parent.appendChild(line);
  }

  function renderCompactLegs(parent, legs) {
    const heading = document.createElement("div");
    setText(heading, "期权腿：");
    parent.appendChild(heading);
    if (!Array.isArray(legs)) {
      const unavailable = document.createElement("div");
      setText(unavailable, legs === undefined ? "接口未提供腿列表。" : "腿列表格式不可识别。");
      parent.appendChild(unavailable);
      return;
    }
    if (legs.length === 0) {
      const empty = document.createElement("div");
      setText(empty, "无");
      parent.appendChild(empty);
      return;
    }
    const fields = [
      ["leg_id", "腿 ID"], ["underlying", "标的"], ["option_type", "期权类型"],
      ["expiration", "到期日"], ["strike", "行权价"], ["quantity", "数量"],
      ["contract_multiplier", "合约乘数"]
    ];
    for (const leg of legs) {
      const row = document.createElement("div");
      row.className = "compact-leg";
      if (!isRecord(leg)) {
        setText(row, "腿记录格式不可识别。");
      } else {
        const values = fields.map(([key, label]) => label + "：" + compactScalar(leg[key]));
        setText(row, values.join("；"));
      }
      parent.appendChild(row);
    }
  }

  function renderCompactCases(caseSummaries) {
    const list = byId("batch-case-list");
    list.textContent = "";
    if (!Array.isArray(caseSummaries)) {
      setText(list, "批量摘要未提供可识别的 case_summaries。");
      return;
    }
    if (caseSummaries.length === 0) {
      setText(list, "批量摘要中的紧凑用例行为空。");
      return;
    }
    const fields = [
      ["disposition", "研究处置"], ["geometry_status", "几何状态"],
      ["ask_basis_per_underlying_unit", "每标的单位 Ask 基准（INDICATIVE_ONLY）"],
      ["structure_kind", "结构类型"], ["budget_status", "预算状态"],
      ["single_cost_upper_bound", "单次成本上界"],
      ["repeated_cost_upper_bound", "重复成本上界"],
      ["single_loss_fraction", "单次损失比例"],
      ["repeated_loss_fraction", "重复损失比例"]
    ];
    for (const item of caseSummaries) {
      const row = document.createElement("div");
      row.className = "compact-case";
      if (!isRecord(item)) {
        setText(row, "紧凑用例行格式不可识别。");
        list.appendChild(row);
        continue;
      }
      const title = document.createElement("p");
      setText(title, "用例 ID：" + compactScalar(item.case_id));
      row.appendChild(title);
      appendCompactField(row, "case_key", item.case_key);
      for (const [key, label] of fields) appendCompactField(row, label, item[key]);
      const reasons = document.createElement("div");
      setText(reasons, "原因：" + compactStringList(item.reasons));
      row.appendChild(reasons);
      renderCompactLegs(row, item.legs);
      list.appendChild(row);
    }
  }

  function renderUnavailableCases(unavailableCases) {
    const list = byId("unavailable-case-list");
    list.textContent = "";
    if (!Array.isArray(unavailableCases)) {
      setText(list, "批量摘要未提供可识别的 unavailable_cases。");
      return;
    }
    if (unavailableCases.length === 0) {
      setText(list, "无");
      return;
    }
    for (const item of unavailableCases) {
      const row = document.createElement("div");
      row.className = "compact-case";
      if (!isRecord(item)) {
        setText(row, "不可用分支记录格式不可识别。");
        list.appendChild(row);
        continue;
      }
      const caseId = item.case_id;
      const encodedCaseKey = safeBatchCaseKey(item.case_key);
      if (typeof caseId === "string" && encodedCaseKey !== null) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "record-id";
        setText(button, caseId);
        button.addEventListener("click", () => loadCase(caseId, item.case_key));
        row.appendChild(button);
      } else {
        const id = document.createElement("div");
        setText(id, "用例 ID：" + compactScalar(caseId) + "；缺少有效 case_key，未发起详情读取。");
        row.appendChild(id);
      }
      appendCompactField(row, "case_key", item.case_key);
      const reasons = document.createElement("div");
      setText(reasons, "原因：" + compactStringList(item.reasons));
      row.appendChild(reasons);
      list.appendChild(row);
    }
  }

  function renderBatchSummary(summary) {
    const view = byId("batch-summary-view");
    state.batchCaseKeys.clear();
    state.unavailableBatchCaseIds.clear();
    if (!isRecord(summary)) {
      setText(view, "运行响应未提供可识别的批量摘要。");
      renderCompactCases(null);
      renderUnavailableCases(null);
      return;
    }
    if (Array.isArray(summary.case_summaries)) {
      for (const item of summary.case_summaries) {
        if (isRecord(item) && typeof item.case_id === "string") {
          state.batchCaseKeys.set(item.case_id, item.case_key);
        }
      }
    }
    if (Array.isArray(summary.unavailable_case_ids)) {
      for (const item of summary.unavailable_case_ids) {
        if (typeof item === "string") state.unavailableBatchCaseIds.add(item);
      }
    }
    if (Array.isArray(summary.unavailable_cases)) {
      for (const item of summary.unavailable_cases) {
        if (isRecord(item) && typeof item.case_id === "string") {
          state.unavailableBatchCaseIds.add(item.case_id);
          state.batchCaseKeys.set(item.case_id, item.case_key);
        }
      }
    }
    const originLabels = {
      WORLD: "世界", EVENT: "事件", DIRECT: "直接输入",
      AUTONOMOUS_DISCOVERY: "世界发现", EVENT_ENTRY: "事件入口"
    };
    const origin = typeof summary.entry_origin === "string"
      ? summary.entry_origin + (originLabels[summary.entry_origin] ? "（" + originLabels[summary.entry_origin] + "）" : "")
      : "接口未提供可识别入口来源";
    const lines = [
      "入口来源：" + origin,
      "已计算案例数：" + compactCount(summary.case_count),
      "不可用分支数：" + compactCount(summary.unavailable_count),
      "Host 状态：" + displayedStatus(summary.host_status),
      "处置计数：\n" + dispositionCountText(summary.disposition_counts),
      "case_ids：" + compactStringList(summary.case_ids),
      "汇总原因：" + compactStringList(summary.reasons),
      "不可用分支 case_id：" + compactStringList(summary.unavailable_case_ids)
    ];
    setText(view, lines.join("\n"));
    renderCompactCases(summary.case_summaries);
    renderUnavailableCases(summary.unavailable_cases);
  }

  function knownVersion(value) {
    return typeof value === "string" && /^[A-Za-z0-9._:-]{1,128}$/.test(value)
      ? value : "接口未提供可识别版本";
  }

  function knownDigest(value) {
    return typeof value === "string" && /^[0-9a-f]{64}$/.test(value)
      ? value : "接口未提供可识别摘要";
  }

  function renderGrounderStageDetails(outcome) {
    const lines = [];
    const countFields = [
      ["source_body_count", "来源正文数"], ["claim_count", "Claim 数"],
      ["hypothesis_count", "Hypothesis 数"], ["field_binding_count", "Field binding 数"],
      ["coverage_count", "Coverage 数"]
    ];
    lines.push("计数（仅统计，不是评分）：");
    for (const [field, label] of countFields) {
      lines.push("  " + label + "：" + compactCount(isRecord(outcome.counts) ? outcome.counts[field] : undefined));
    }

    lines.push("诊断计数（保留负面结果；不是评分）：");
    if (!Array.isArray(outcome.diagnostic_counts)) {
      lines.push("  接口未提供可识别诊断计数。");
    } else if (outcome.diagnostic_counts.length === 0) {
      lines.push("  无");
    } else {
      for (const item of outcome.diagnostic_counts) {
        lines.push(isRecord(item)
          ? "  " + compactScalar(item.code) + "：" + compactCount(item.count)
          : "  诊断计数项格式不可识别");
      }
    }

    lines.push("Coverage（逐项原顺序；状态不是评分或排名）：");
    if (!Array.isArray(outcome.coverage)) {
      lines.push("  接口未提供可识别 Coverage。");
    } else if (outcome.coverage.length === 0) {
      lines.push("  无");
    } else {
      for (const item of outcome.coverage) {
        if (!isRecord(item)) {
          lines.push("  Coverage 项格式不可识别");
          continue;
        }
        const modelStatus = ["supported", "unresolved", "contradicted"].includes(item.model_status)
          ? item.model_status : "不可识别";
        const validatorStatus = ["supported", "unresolved", "contradicted"].includes(item.validator_status)
          ? item.validator_status : "不可识别";
        const gap = typeof item.gap_present === "boolean" ? (item.gap_present ? "有缺口" : "无缺口") : "缺口字段不可识别";
        lines.push("  Coverage #" + compactCount(item.index) + "；model=" + modelStatus + "；validator=" + validatorStatus
          + "；claim_count=" + compactCount(item.claim_count) + "；" + gap);
      }
    }

    const provenance = isRecord(outcome.provenance) ? outcome.provenance : Object.create(null);
    lines.push("版本与溯源（仅版本、SHA-256 摘要与字节计数；隐藏来源定位和模型标识）：");
    const versionFields = [
      ["receipt_schema_version", "Receipt schema"], ["audit_schema_version", "Audit schema"],
      ["producer_wire_version", "Producer wire"], ["producer_prompt_version", "Producer prompt version"],
      ["verifier_wire_version", "Verifier wire"], ["validator_version", "Validator version"],
      ["localizer_version", "Localizer version"], ["catalog_schema_version", "Catalog schema"],
      ["catalog_generator_version", "Catalog generator"]
    ];
    for (const [field, label] of versionFields) lines.push("  " + label + "：" + knownVersion(provenance[field]));
    const digestFields = [
      ["canonical_input_sha256", "Canonical input SHA-256"], ["host_raw_input_sha256", "Host raw input SHA-256"],
      ["audit_sha256", "Audit SHA-256"], ["catalog_sha256", "Catalog SHA-256"],
      ["producer_content_sha256", "Producer content SHA-256"], ["normalized_envelope_sha256", "Normalized envelope SHA-256"]
    ];
    for (const [field, label] of digestFields) lines.push("  " + label + "：" + knownDigest(provenance[field]));
    const sourceHashes = provenance.source_body_hashes;
    if (Array.isArray(sourceHashes)) {
      lines.push("  Source body SHA-256：" + (sourceHashes.length
        ? sourceHashes.map((item) => isRecord(item) ? knownDigest(item.sha256) : "摘要项不可识别").join("；")
        : "无"));
    } else {
      lines.push("  Source body SHA-256：接口未提供可识别摘要列表");
    }
    if (Array.isArray(provenance.model_calls)) {
      lines.push("  调用字节计数：");
      for (const call of provenance.model_calls) {
        if (!isRecord(call)) {
          lines.push("    调用计数项格式不可识别");
          continue;
        }
        const role = ["discovery", "semantic"].includes(call.role) ? call.role : "调用角色不可识别";
        lines.push("    " + role + "；发送字节=" + compactCount(call.bytes_sent)
          + "；接收字节=" + compactCount(call.bytes_received));
      }
    } else {
      lines.push("  调用字节计数：接口未提供可识别列表");
    }
    return lines;
  }

  function renderGrounderStageOutcome(outcome) {
    const lines = [
      "Grounder 阶段结果（" + compactScalar(outcome.schema_version) + "）：",
      "Grounder：" + (outcome.grounder_status === "COMPLETED" ? "COMPLETED" : "字段缺失或不可识别"),
      "source_status：" + (outcome.source_status === "UNKNOWN" ? "UNKNOWN（不是搜索成功）" : "字段缺失或不可识别"),
      "semantic_status：" + (outcome.semantic_status === "RECEIPT_VALIDATED" ? "RECEIPT_VALIDATED（不是事实真理）" : "字段缺失或不可识别"),
      "builder_status：" + (outcome.builder_status === "COMPLETED" ? "COMPLETED" : "字段缺失或不可识别"),
      "EI submission：" + (outcome.submission_status === "MISSING" ? "MISSING" : "字段缺失或不可识别"),
      "EI：" + (outcome.ei_status === "NOT_RUN" ? "NOT_RUN" : "字段缺失或不可识别"),
      "边界：尚无 EI submission，未进入 Core，未创建 Core 分支；没有 Core 结果或报告。"
    ];
    lines.push(...renderGrounderStageDetails(outcome));
    return lines;
  }

  function renderGrounderSubmissionStageOutcome(outcome) {
    const assessmentStatus = outcome.ei_assessment_status === "accepted"
      ? "ACCEPTED"
      : outcome.ei_assessment_status === "incomplete" ? "INCOMPLETE" : "字段缺失或不可识别";
    const lines = [
      "Grounder 阶段结果（" + compactScalar(outcome.schema_version) + "）：",
      "Grounder：" + (outcome.grounder_status === "COMPLETED" ? "COMPLETED" : "字段缺失或不可识别"),
      "source_status：" + (outcome.source_status === "UNKNOWN" ? "UNKNOWN（不是搜索成功）" : "字段缺失或不可识别"),
      "semantic_status：" + (outcome.semantic_status === "RECEIPT_VALIDATED" ? "RECEIPT_VALIDATED（不是事实真理）" : "字段缺失或不可识别"),
      "builder_status：" + (outcome.builder_status === "COMPLETED" ? "COMPLETED" : "字段缺失或不可识别"),
      "EI submission：" + (outcome.submission_status === "PRESENT" ? "PRESENT" : "字段缺失或不可识别"),
      "EI：" + (outcome.ei_status === "ASSESSED" ? "ASSESSED" : "字段缺失或不可识别"),
      "EI 确定性评估：" + assessmentStatus,
      "Source batch 数：" + (outcome.source_batch_count === 1 ? "1" : "字段缺失或不可识别"),
      "Submission SHA-256：" + knownDigest(outcome.submission_sha256),
      "边界：仅显示实际 EI submission 评估状态；不自动表示研究成功、Core 结果或市场完成。"
    ];
    lines.push(...renderGrounderStageDetails(outcome));
    return lines;
  }

  function renderKnownStageOutcome(outcome, stageName) {
    if (!isRecord(outcome)) return [];
    if (["host-grounder-submission-stage-outcome-v0.1", "host-grounder-submission-stage-outcome-v0.2"].includes(outcome.schema_version)) {
      return stageName === "grounder"
        ? renderGrounderSubmissionStageOutcome(outcome)
        : ["阶段结果与阶段类型不匹配；其他字段未显示。"];
    }
    if (["host-grounder-stage-outcome-v0.1", "host-grounder-stage-outcome-v0.2"].includes(outcome.schema_version)) {
      return stageName === "grounder"
        ? renderGrounderStageOutcome(outcome)
        : ["阶段结果与阶段类型不匹配；其他字段未显示。"];
    }
    if (outcome.schema_version === "host-batch-outcome-v0.1") {
      return ["批量阶段结果：case_count=" + compactCount(outcome.case_count)
        + "；unavailable_count=" + compactCount(outcome.unavailable_count)
        + "；status=" + displayedStatus(outcome.status)];
    }
    if (outcome.schema_version === "host-direct-outcome-v0.1") {
      return ["Direct 阶段结果：case_id=" + compactScalar(outcome.case_id)
        + "；classification=" + compactScalar(outcome.classification)];
    }
    if (typeof outcome.status === "string") return ["阶段结果状态：" + displayedStatus(outcome.status)];
    if (outcome.executor_status === "NOT_CONFIGURED") {
      return ["执行器状态：NOT_CONFIGURED；原因：" + compactScalar(outcome.reason)
        + "；Host shell：" + knownVersion(outcome.host_shell_version)];
    }
    return ["阶段结果格式不可识别；其他字段未显示。"];
  }

  function renderRunEvents(events) {
    const target = byId("run-events");
    if (!Array.isArray(events)) {
      setText(target, "阶段事件字段格式不可识别。");
      return;
    }
    if (events.length === 0) {
      setText(target, "无阶段事件。");
      return;
    }
    const lines = [];
    for (let index = 0; index < events.length; index += 1) {
      const event = events[index];
      if (!isRecord(event)) {
        lines.push("事件 #" + (index + 1) + " 格式不可识别；其他字段未显示。");
        continue;
      }
      const eventName = ["stage_started", "stage_outcome", "stage_finished", "stage_succeeded", "stage_failed"].includes(event.event)
        ? event.event : "未识别阶段事件";
      lines.push("事件 #" + (index + 1) + "：" + eventName);
      if (["executor", "grounder"].includes(event.stage)) lines.push("  阶段：" + event.stage);
      if (typeof event.stage_id === "string" && /^[A-Za-z0-9._~-]{1,128}$/.test(event.stage_id)) {
        lines.push("  阶段 ID：" + event.stage_id);
      }
      if (["QUEUED", "RUNNING", "COMPLETED", "PARTIAL", "BLOCKED", "FAILED", "INTERRUPTED"].includes(event.status)) {
        lines.push("  阶段状态：" + displayedStatus(event.status));
      }
      if (typeof event.started_at === "string" && /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.+-]+(?:Z|[+-][0-9]{2}:[0-9]{2})$/.test(event.started_at)) {
        lines.push("  开始时间：" + event.started_at);
      }
      if (typeof event.completed_at === "string" && /^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.+-]+(?:Z|[+-][0-9]{2}:[0-9]{2})$/.test(event.completed_at)) {
        lines.push("  完成时间：" + event.completed_at);
      }
      if (Array.isArray(event.diagnostics)) lines.push("  阶段诊断码：" + compactStringList(event.diagnostics));
      lines.push(...renderKnownStageOutcome(event.outcome, event.stage));
    }
    setText(target, lines.join("\n"));
  }

  function renderRun(data, requestedRunId) {
    if (!isRecord(data)) {
      state.runMode = null;
      state.batchCaseKeys.clear();
      state.unavailableBatchCaseIds.clear();
      setText(byId("unavailable-case-list"), "运行响应格式不可识别。");
      setText(byId("run-identity"), "运行响应格式不可识别。");
      setText(byId("run-status"), "状态缺失（接口未提供）");
      setText(byId("run-snapshot"), "接口未提供可显示运行快照。");
      return null;
    }
    const suppliedId = safeRunId(data.run_id) === null ? null : data.run_id;
    state.runId = suppliedId || requestedRunId;
    state.runMode = typeof data.mode === "string" ? data.mode : null;
    setText(byId("run-identity"), "运行 ID：" + state.runId);
    setText(byId("run-status"), displayedStatus(data.status));
    setText(byId("run-diagnostics"), data.diagnostics === undefined ? "运行响应未提供 diagnostics 字段。" : jsonText(data.diagnostics, true));
    if (data.events === undefined) setText(byId("run-events"), "运行响应未提供 events 字段。");
    else renderRunEvents(data.events);
    renderBatchSummary(data.batch_summary);
    const extras = Object.create(null);
    for (const key of Object.keys(data)) {
      if (["run_id", "status", "diagnostics", "events", "cases", "batch_summary", "case_details", "caseDetails"].includes(key)) continue;
      extras[key] = data[key];
    }
    setText(byId("run-snapshot"), Object.keys(extras).length ? jsonText(extras, true) : "运行响应未提供其他非用例快照字段。");
    renderCaseIndex(data.cases);
    setText(byId("case-detail"), "尚未选择用例；详情按需读取。");
    if (data.mode === "direct" && Array.isArray(data.cases) && data.cases.length === 1) {
      const caseId = caseIdFromEntry(data.cases[0]);
      if (safeCaseId(caseId) !== null) return caseId;
    }
    return null;
  }

  async function loadRun(runId) {
    const encodedId = safeRunId(runId);
    if (encodedId === null) return;
    state.runId = runId;
    state.runMode = null;
    state.batchCaseKeys.clear();
    state.unavailableBatchCaseIds.clear();
    setText(byId("run-identity"), "正在读取运行 ID：" + runId);
    setText(byId("run-status"), "状态缺失（详情读取中）");
    setText(byId("run-diagnostics"), "正在读取运行详情……");
    setText(byId("run-events"), "正在读取运行详情……");
    setText(byId("run-snapshot"), "正在读取运行快照……");
    setText(byId("batch-summary-view"), "正在读取批量研究摘要……");
    setText(byId("batch-case-list"), "正在读取紧凑用例行……");
    setText(byId("unavailable-case-list"), "正在读取不可用分支详情……");
    setText(byId("case-list"), "正在读取用例索引……");
    setText(byId("case-detail"), "尚未选择用例。");
    try {
      const data = await getJson(API.runs + "/" + encodedId);
      const directCaseId = renderRun(data, runId);
      if (directCaseId !== null) await loadCase(directCaseId);
    } catch (error) {
      setText(byId("run-identity"), "运行详情读取失败（" + error.message + "）。");
      setText(byId("run-status"), "状态缺失（详情读取失败）");
      setText(byId("run-diagnostics"), "接口未提供可读取的诊断内容。");
      setText(byId("run-events"), "接口未提供可读取的阶段事件。");
      setText(byId("run-snapshot"), "接口未提供可读取的运行快照。");
      setText(byId("batch-summary-view"), "批量研究摘要暂不可用。");
      setText(byId("batch-case-list"), "紧凑用例行暂不可用。");
      setText(byId("unavailable-case-list"), "不可用分支详情暂不可用。");
      setText(byId("case-list"), "用例索引暂不可用。");
    }
  }

  async function loadCase(caseId, caseKey) {
    const encodedRunId = safeRunId(state.runId);
    const batchMode = state.runMode === "world" || state.runMode === "event";
    const encodedCaseId = batchMode ? safeBatchCaseKey(caseKey) : safeCaseId(caseId);
    if (encodedRunId === null || encodedCaseId === null) return;
    setText(byId("case-detail"), "正在按需读取用例详情……");
    try {
      const path = API.runs + "/" + encodedRunId + "/cases/" + encodedCaseId;
      const data = await getJson(path);
      if (!isRecord(data) || data.case_id !== caseId || (batchMode && data.case_key !== caseKey)) {
        setText(byId("case-detail"), "用例详情响应的 case_id 缺失、无效或与请求不一致；未显示报告。");
        return;
      }
      const classification = data.classification === undefined
        ? "接口未提供" : (typeof data.classification === "string" ? data.classification : JSON.stringify(data.classification));
      const reasons = data.reasons === undefined
        ? "接口未提供" : JSON.stringify(data.reasons);
      const disclosure = "case_id: " + data.case_id + "\nclassification: " + classification + "\nreasons: " + reasons;
      if (data.report === null) {
        setText(byId("case-detail"), disclosure + "\n\n报告字段为 null；当前没有可显示报告。");
      } else if (typeof data.report === "string") {
        setText(byId("case-detail"), disclosure + "\n\n" + data.report);
      } else {
        setText(byId("case-detail"), disclosure + "\n\n报告字段缺失或类型不受支持；未显示报告。");
      }
    } catch (error) {
      setText(byId("case-detail"), "用例详情读取失败（" + error.message + "）。");
    }
  }

  function collectBounds() {
    const bounds = Object.create(null);
    for (const name of integerBoundNames) {
      const raw = byId("bound-" + name.replaceAll("_", "-")).value;
      if (!/^(0|[1-9][0-9]*)$/.test(raw)) throw new Error(name + " 须填写非负整数。");
      const value = Number(raw);
      if (!Number.isSafeInteger(value)) throw new Error(name + " 超出浏览器可安全表达的整数范围。");
      bounds[name] = value;
    }
    const timeoutRaw = byId("bound-quote-timeout").value;
    const timeout = Number(timeoutRaw);
    if (timeoutRaw === "" || !Number.isFinite(timeout) || timeout <= 0 || timeout > 60) {
      throw new Error("quote_timeout_seconds 须大于 0 且不超过 60。");
    }
    bounds.quote_timeout_seconds = timeout;
    return bounds;
  }

  for (const tab of document.querySelectorAll('[role="tab"][data-mode]')) {
    tab.addEventListener("click", () => {
      if (tab.disabled || !modes.includes(tab.dataset.mode)) return;
      state.mode = tab.dataset.mode;
      for (const other of document.querySelectorAll('[role="tab"][data-mode]')) {
        other.setAttribute("aria-selected", other === tab ? "true" : "false");
      }
      const copy = {
        world: ["世界：填写原始研究意图；提交时保留文本原样。", "填写世界研究的原始意图；不在浏览器改写。"],
        event: ["事件：填写原始事件研究意图；提交时保留文本原样。", "填写事件研究的原始意图；不在浏览器解析。"],
        direct: [
          "直接输入使用 host-direct-input-v0.1。当前没有专用表单；请明确手工输入符合该 schema 的 JSON，不会自动填充示例、替你选择结构或补日期/数量/乘数，也不要输入 ask prices 或任何 keys/secrets。",
          "Direct JSON 按原样提交；不要放入 ask prices 或 keys/secrets。日期、数量、乘数和结构均须由你明确输入；本页不提供 JSON 示例或默认值。"
        ]
      }[state.mode];
      setText(byId("mode-help"), copy[0]);
      setText(byId("input-help"), copy[1]);
      setText(byId("raw-input-label"), state.mode === "direct"
        ? "host-direct-input-v0.1 JSON（手工输入）" : "原始输入");
    });
  }

  byId("run-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.mode === null || !modes.includes(state.mode) || byId("tab-" + state.mode).disabled) {
      setText(byId("submit-state"), "尚未选择本机状态中已配置的入口；未提交。");
      return;
    }
    const rawInput = byId("raw-input").value;
    if (rawInput.trim().length === 0) {
      setText(byId("submit-state"), "请输入原始内容；非空文本会按原样提交。");
      return;
    }
    let bounds;
    try {
      bounds = collectBounds();
    } catch (error) {
      setText(byId("submit-state"), error.message);
      return;
    }
    const payload = { mode: state.mode, input: rawInput, bounds: bounds };
    const button = byId("submit-run");
    button.disabled = true;
    setText(byId("submit-state"), "正在提交新运行……");
    try {
      const response = await fetch(API.runs, {
        method: "POST",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
          "X-CH-CSRF": CSRF_TOKEN
        },
        credentials: "same-origin",
        cache: "no-store",
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      const result = await response.json();
      const resultStatus = displayedStatus(result && result.status);
      const returnedId = result && safeRunId(result.run_id) !== null ? result.run_id : null;
      setText(byId("submit-state"), returnedId === null
        ? "接口已响应；" + resultStatus + "；未返回可读取的 run_id，结果详情未确认。"
        : "接口已响应；" + resultStatus + "；运行 ID：" + returnedId);
      await loadRuns();
      if (returnedId !== null) await loadRun(returnedId);
    } catch (error) {
      setText(byId("submit-state"), "提交未获成功确认（" + error.message + "）。");
    } finally {
      button.disabled = false;
    }
  });

  loadStatus();
  loadProfile();
  loadRuns();
})();
</script>
</body>
</html>
'''
