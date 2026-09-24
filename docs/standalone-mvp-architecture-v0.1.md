# 独立本地 MVP 架构 v0.1

状态：M0 冻结，独立针对性审阅通过，允许 M1 transport/config BUILD；不是已完成运行能力。
授权：2026-09-24 用户连续 M0–M8 开发任务。

最新运行决策（2026-09-24）：用户要求删除本地模型，改用其仓库外配置的
DeepSeek API。已停止本次 Ollama 服务并删除 qwen3 模型目录（约2.5GB）；
下文 Ollama 下载记录仅为历史实验事实，不再是当前运行方案。
当前模型采用官方 `deepseek-flash`（官方对应 DeepSeek-V4.1-Flash）。
一次真实 DeepSeek API 调用成功，消耗 135 tokens。此测试仅证明鉴权、传输
和一个有提示的 JSON 样例通过，不证明独立 Grounder 语义能力；本地模型已
删除，禁止隐式本地或付费 fallback。配置和密钥保留仓库外，不入库。
依据：[官方模型说明](https://api-docs.deepseek.com/zh-cn/)。

## 优先关系

本次授权优先于历史“仅 Codex 辅助验证”“不建数据库/前端”及人工选择
产品流程限制。历史实验事实不改写。现有 EI v0.2、Core Kernel、市场数据
证据强度、时间及成本约束不变；改变的是宿主自动化和本地交付范围。
[Core Doctrine](core-convexity-research-doctrine-v0.1.md) 的无估值前置、无排名、
非推荐原则继续有效。[原用户流程](core-convexity-mvp-user-flow-v0.1.md) 的
当前 API 事实继续有效，但其无前端/数据库描述不是新版交付限制。

## 最小模块边界

World（Tavily Web + last30days）与 Event（用户事件）使用同一证据核验宿主。
模型只能提出结构化主张、短原文引用、来源 ID、实体/日期和明确解释；不能
调用 shell、改变查询预算、凭证、政策或接受门槛。来源正文、Skill 输出和
模型输出均是不可信输入。摘要不可代替正文。引用必须在实际读取的正文内，
实体、合同、事件和日期绑定须显式留存；精确引用存在仍不证明语义蕴含。
语义能力须另用有反证、错期、串题、注入和部分覆盖的案例验证。

非空且有效的 SourceSubmissionBatch 才能调用既有 run_event_core /
run_world_core。全部 EI ACCEPTED 假设自动分支；没有人工择优、Top-N 或
重新定义 Core。Direct 使用既有 exact verification 和 run_direct_core。
所有运行保存 structured records；World/Event 只默认渲染 compact，单案例
详情按需渲染；Direct 自动报告。渲染不能触发重新取数。

### Host DTO/schema v0.1

模型输出永远先进入未信任 DTO，不直接反序列化为 EI 或 Core dataclass。所有
JSON 必须是 UTF-8、单一顶层 object、无 markdown fence、拒绝重复键、拒绝
未知字段、`NaN`/`Infinity` 和超出本次配置上限的字符串/数组；日期只接受
`YYYY-MM-DD`，时间只接受带时区 RFC3339。schema 版本和阶段必须精确匹配。

```text
ModelConfigSnapshot {
  schema_version: "model-config-v0.1",
  role: "discovery" | "semantic",
  provider: nonempty string,
  model: nonempty string,
  endpoint: nonempty URI,
  credential_ref: null | nonempty external-reference string,
  declared_capabilities: closed string tuple,
  timeout_seconds: explicit positive number,
  max_input_bytes: explicit positive integer,
  max_output_bytes: explicit positive integer,
  remote_enabled: boolean,
  fee_authorized: boolean
}

ModelOutputEnvelope {
  schema_version: "grounder-output-v0.1",
  stage: "discovery" | "semantic",
  request_id: nonempty string,
  claims: ClaimDTO tuple,
  hypotheses: HypothesisDTO tuple,
  coverage: CoverageDTO tuple,
  field_bindings: FieldBindingDTO tuple
}

ClaimDTO {
  claim_id: nonempty string,
  kind: "observed_fact" | "interpretation",
  source_id: nonempty string,
  locator: nonempty string,
  quote: nonempty string,
  text: nonempty string,
  entity_refs: nonempty string tuple,
  event_date: null | YYYY-MM-DD,
  published_at: null | RFC3339,
  dependency_claim_ids: string tuple,
  uncertainty: string tuple,
  falsification_conditions: string tuple
}

HypothesisDTO {
  hypothesis_id: nonempty string,
  underlying_symbol: null | nonempty string,
  impact_path: null | nonempty string,
  distribution_mode: closed EI mode | null,
  distribution_hypothesis: null | nonempty string,
  expected_window: null | {start_date, end_date, methodology},
  reassessment: null | {reassessment_by, methodology, basis_kind, basis_claim_ids},
  supporting_claim_ids: string tuple,
  contradicting_claim_ids: string tuple,
  contradiction_review: null | nonempty string,
  uncertainties: string tuple,
  falsification_conditions: string tuple
}

CoverageDTO {
  subquestion_id: nonempty string,
  status: "supported" | "unresolved" | "contradicted",
  claim_ids: string tuple,
  gap: null | nonempty string
}

FieldBindingDTO {
  field_path: nonempty string,
  source_id: nonempty string,
  quote: nonempty string,
  start: nonnegative integer,
  end: nonnegative integer,
  semantic_role: "hypothesis" | "date" | "entity",
  status: "supported" | "unresolved" | "contradicted"
}
```

除 `CoverageDTO.status` 与 `FieldBindingDTO.status` 外，模型不得写入接受状态；
`accepted`、`disposition`、`cost_ledger`、`risk_policy`、`sensitivity`、
`operational_bounds`、工具调用、查询预算和凭证字段不属于模型 schema；出现即
`MODEL_OUTPUT_INVALID`。`string tuple`（包括 uncertainty、falsification_conditions）
可为空，不为无缺口的纯事实制造未知。Host 检查 `field_path` 确实指向
hypothesis/date/entity 字段，并验证 source/quote/start/end 的一致性；匹配
substring 或偏移只证明词面来源绑定，不证明语义蕴含。`FieldBindingDTO.status`
是字段证据的 supported/unresolved/contradicted，不是接受、选择或 Core 状态。
随后才由确定性 builder 构造现有 `EventIntelligenceSubmission`。
模型不能写入 EI status、issue codes 或 Core policy；`assess_event_intelligence_submission`
是唯一 EI authority，Core 只消费 Host 已构造并验证的 typed records。

## 独立配置与安全边界

- 仓库外本地配置：模型 provider/model/endpoint/credential reference、角色
  （discovery/semantic）、能力及 timeout/上下文/输出上限；无业务硬编码模型。
- 当前优先实现用户明确授权的 DeepSeek compatible API，不再要求本地 Ollama。
  本地模型已删除，不保留本地 fallback。未获许可的其他模型端点仍默认拒绝；
  远端必须明确启用及费用许可，无隐式降级或付费 fallback。
- 密钥引用只能是用户配置的仓库外文件或环境变量名；不上传本地配置正文。
  诊断不得包含异常原文、响应原文、鉴权 header 或凭证路径的敏感内容。
- Skill 仅许可已核验 v3.21.1 的 last30days；校验路径/版本/代码指纹，不从
  模型或网页读取任意可执行路径。子进程 argv 固定、shell=False、环境变量
  白名单、隔离运行目录、阶段 deadline、输出大小限制。不是通用 OS 沙箱。
- last30days 的已知实现事实是 `scripts/lib/env.py` 的 `get_config` 无条件调用
  `_load_keychain`、`_load_pass` 及 `get_openai_auth`；`LAST30DAYS_CONFIG_DIR=''`
  仅禁用文件配置，不禁用自动凭证发现。因此环境变量白名单本身不构成隔离。
  M0 只允许由独立、pin-verified 的受控 launcher 调用该 Skill：launcher 必须
  禁止这些 loader/外部凭证查找，只注入获准的 source credentials，且不得修改
  用户安装。任何自动凭证发现或未获准凭证使用均为安全失败并进入 `BLOCKED`；
  不将此要求表述为通用 OS 沙箱。M1 必须用可观测 spy/fixture 验证无外部
  credential lookup。
- 禁止继承未知付费 API 配置、自动安装/升级 Skill、自动账户授权及交易。
  已批准 Chrome X cookie 仅由原生只读检索使用，不保存 Cookie。
- Discover nominate → 全量 judgments → research → angles → finalize；同一
  bundle/目录，TTL 3600s，过期终止，不改时间戳或自动重新抓取。原生 rank /
  worthiness 仅用于协议，并记录上游选择偏差，不进入 Hunter 排序或 Core。
- Tavily 仅 Basic Search/Extract，PAYGO-off 确认、调用前预算预留，失败请求
  也计入上界。无自动重试；来源工具响应/账户用量滞后分别记录。

## 运行与覆盖状态

运行状态：QUEUED / RUNNING / COMPLETED / PARTIAL / BLOCKED / FAILED /
INTERRUPTED；这些是宿主执行状态，不是 Core disposition。
阶段诊断至少区分 NO_SEARCH_RESULTS、SOURCE_TRANSPORT_FAILURE、
EXTRACTION_FAILURE、MODEL_UNAVAILABLE、MODEL_OUTPUT_INVALID、
MODEL_SEMANTIC_VALIDATION_FAILED、SKILL_FAILURE、
SKILL_TTL_EXPIRED、NO_SUPPORTED_HYPOTHESIS、SUBMISSION_INVALID、
UNRESOLVED_SECURITY、EI_INCOMPLETE、NO_CONTRACTS、OPERATIONAL_LIMIT。
成本未知及预算超限保留既有 Core 原因，不改写为来源失败。

Coverage 按原始请求的子问题记录 supported / unresolved / contradicted，
附来源和缺口。一个子假设 ACCEPTED 不能把请求整体标为全面核实。无合法
submission 必须停在 Core 前，绝不返回空 COMPLETE 或“没有凸性机会”。
已有合法部分 submission 正常接受 EI 检查。模型/来源失效不抹掉已取得证据。

Host status precedence is deterministic and independent of `CoreCaseSet.status`:

1. `INTERRUPTED`: startup recovery or explicit process interruption; an old
   `RUNNING` run is marked this way and is never automatically replayed.
2. `FAILED`: an unclassified Host, invariant, or database failure prevents a
   truthful terminal snapshot.
3. `BLOCKED`: a required pre-Core gate fails, including no valid nonempty
   submission, missing model/config/security/operational bounds, or semantic
   validation failure before any accepted branch exists. It is never rendered as
   Core `REJECT`, “no opportunity”, or empty `COMPLETE`.
4. `PARTIAL`: at least one durable source/EI/Core artifact exists, but requested
   coverage or another branch remains unresolved, incomplete, or failed. A valid
   partial submission is still assessed; accepted hypotheses in the same batch
   still run all their Core branches.
5. `COMPLETED`: every declared branch reached a deterministic terminal state.
   A branch may contain Core `REJECT`, `DATA_INSUFFICIENT_CORE`, `NO_CONTRACTS`,
   or `EI_INCOMPLETE`; these remain structured diagnostics, not recommendations.

`MODEL_SEMANTIC_VALIDATION_FAILED` means transport and JSON shape succeeded but
the evidence-bound semantic check failed. For example, a facility/deployment
deadline cannot become `expected_window.end_date`; it remains an observed fact or
unresolved gap only, and no impact end is synthesized. If a valid typed partial
submission already exists, it is retained and assessed; the failed model stage
does not erase it.

## Standard Research Profile v0.1

用户已批准 USD 100000，单次比例 0.005（USD 500），重复 3 次，总比例
0.015（USD 1500）。自动结构每腿 1 张，乘数只取核验合约。Host 显式构造
`core_research.CoreRiskRepeatPolicy`；不向 Kernel 增加默认值。三入口保存相同版本、原值、
授权来源及每次实际快照。这不是实际资产声明或交易授权。

The exact application-to-kernel mapping is:

```text
CoreResearchPolicy (core_application)
  -> request_factory(*, case_id, structure, context)
  -> CoreResearchRequest (core_research)
       risk_policy = CoreRiskRepeatPolicy(
         portfolio_value=Decimal("100000"),
         maximum_single_loss_fraction=Decimal("0.005"),
         maximum_repeated_loss_fraction=Decimal("0.015"),
         repeat_count=3,
         currency="USD",
         ...
       )
       cost_ledger = None
       sensitivity = None
```

`CoreOperationalBounds` remains an explicit non-economic Host configuration.
`request_factory` must retain the application-owned verified `CoreStructure` by
identity. This mapping uses `core_research.CoreRiskRepeatPolicy`; it does not
construct, import, or reinterpret legacy `StructureCosts`, `risk_assessment`,
screening, or position-management records.

指示性 ask 可作几何 basis，但不产生可信 premium upper bound。缺少上界
时 `cost_ledger` 保持 `None`；费用/资金/结算/冲击未知项只作为 Host gap
diagnostics 保存，不填零、不伪造 `CoreCostComponent`。
既有条件 standard-payoff 批准保留限定，不把 STANDARD 升级为 deliverable。
敏感性扰动幅度尚未得到本次授权；只有已批准/显式配置方法可生成 Core
sensitivity。未配置时保留 sensitivity_missing，不私设 ±10% 或假阈值。
该子项可阻断正向 Core 分类，但不阻断来源/宿主/UI 的诚实不完整结果。

## 最小本地接口与持久化（前端之前冻结）

服务仅绑定 127.0.0.1，拒绝非本机 Host/Origin；写请求需本次启动的防跨站
令牌，不开放 CORS。无远端网络监听、交易路径或任意文件读取接口。

- GET /api/status：脱敏配置和能力诊断，不返回 secrets。
- GET /api/profile：批准的版本化标准研究情景。
- POST /api/runs：mode=world/event/direct、原始输入及显式操作预算；新 run_id。
- GET /api/runs 与 /api/runs/{id}：历史/阶段/诊断/完整中性结果快照。
- GET /api/runs/{id}/cases/{case_id}：由留存结构记录惰性渲染中文详情。
- 配置更新只接受封闭字段，不允许浏览器发送任意命令/文件路径；凭证只在
  本机配置文件设定。模型更换只影响新运行。

SQLite 位于用户数据目录、Git 外。schema_version 显式顺序迁移，未知未来
版本拒绝打开；不做破坏性迁移。研究 run、阶段事件和终态快照追加保存。
重新研究必新 ID，可绑定 parent_run_id，禁止覆盖旧经济输入/结果。保存原始
请求、必要短摘录/定位/正文 hash、候选及覆盖、EI、市场 evidence、Profile、
模型/Skill/代码契约版本、Core records 和按需报告；不默认永久全文缓存。
禁止 pickle 或根据外部类型名动态 import；只用封闭可审计 JSON 编码。
启动时将遗留 RUNNING 记为 INTERRUPTED，不自动重发可能已扣费的调用。

Snapshot transaction and redaction boundary is frozen as follows:

1. Before any external call, one transaction appends the immutable `run_start`
   record: `run_id`, mode, canonical input/hash, sanitized model/Skill/source
   configuration snapshot, Standard Profile snapshot, explicit operational
   bounds, and contract/schema versions.
2. Each stage writes `stage_started` before the call and exactly one durable
   success/failure outcome after it. Outcomes retain provider/model/request IDs,
   timestamps, byte/token counts when supplied, status, and payload hash; they
   do not retain authorization headers, secret values, prompts containing
   secrets, or unredacted exception/response text.
3. Evidence commits retain source identity, locator, publication/retrieval time,
   body hash and the minimum necessary quote/position. Full source bodies are
   opt-in and outside this MVP snapshot contract.
4. Submission commits retain canonical Host DTO, coverage, raw-input identity
   key, typed EI submission, exact assessment version/status/issues, and no
   model-supplied acceptance field. A missing/empty submission commits its
   diagnostics but creates no Core-run record.
5. Market commits retain existing typed provider evidence and operation receipt;
   Core commits retain the exact Profile, `CoreResearchRequest`,
   `CoreResearchResult`, and derived report hash. `cost_ledger=None` and
   `sensitivity=None` are explicit snapshot values.
6. The terminal transaction appends Host status, diagnostics and coverage. No
   prior stage/result is overwritten; a rerun always receives a new `run_id` and
   may reference `parent_run_id`. Reports are derived views, never authorities.

Redaction is allow-list based. `credential_ref` may retain only a non-secret
reference identifier; raw credential paths, tokens, cookies, userinfo/query
secrets in endpoints, and provider account identifiers are rejected or stored
only as a redacted fingerprint. Canonical JSON is the only persistence format.

## 交付次序与验收

M0 冻结本 ADR 中 M1 最小 transport/config 接口 → M1 模型/Skill → M2
详细 builder 与 Grounder 验收；M3 Profile 可在 M1
后独立实现。M4 Event、M5 World 使用同一核验及 Core。M6 接口/SQLite 在
M7 中文工作台之前完成；M8 完成独立进程真实验收和全回归。
DeepSeek transport 成功不等于 semantic validation 成功；在 semantic gate
未通过时，M1 仍可实现并测试最小 transport adapter、配置/模型结构校验；
复杂 Grounder 语义细化另立工作单元。可以实现并测试 Profile/SQLite，但不得
声称 Grounder、真实 World 或 M8 验收通过。

每项分别记录合成测试、真实来源、模型语义、独立宿主、Core 条件研究状态。
必须覆盖模型不可用、TTL、串题、提取失败、无映射、部分覆盖、EI 不完整、
无合约、成本未知、预算超限。负面结果是有效产品结果，不自动等于功能成功。

## 当前实施事实

起点 e788332，main/HEAD/origin/main 一致。Mac M4 / 16GB，macOS 26.6.2。
仅本地模型目录已删除；Ollama 服务已停止，但工具二进制/archive 仍保留，
不再作为运行方案。用户明确授权 DeepSeek API；
`deepseek-flash` 一次真实调用成功（135 tokens），仅记录为 transport/auth
证据，semantic gate 仍未通过。last30days 仍固定已核验 v3.21.1；不静默升级。

M0 独立审阅：字段证据绑定、语义失败与传输失败分离、标准 Profile 到现有
CoreRiskRepeatPolicy 的映射均在修订后通过。PASS 范围为 M0/M1 解锁；
M2 builder/Grounder、Skill 执行隔离及后续生产实现仍需各自验证与审阅。
