# 本机 World/Event 批量结果交付 v0.1

本工作单元实现既有独立 MVP 架构的结构化批量存档与展示，不改变 EI、
Core、市场数据或经济研究契约。代码已实现；专项验证通过，最终独立审阅和
完整回归状态见当前断点。它不是实际 Grounder/World 来源验收。

## 边界

- 宿主允许显式注入可信的 Python World/Event 执行器，返回既有
  `CoreRunResult`。HTTP 输入不能注册执行器、构造接受状态或执行代码。
- 默认 CLI 的 World/Event 仍未配置；不得借合成 fixture 启用真实来源路径。
  DeepSeek/Tavily Grounder 的真实语义验收是独立未完成条件。
- 运行开始与执行器版本快照先落盘，然后调用执行器一次；没有隐式重试。
- 全部结构化案例及 unavailable 分支按原顺序原子存档，不截取前缀、排名、
  推荐或默认选中。数值使用既有 Core codec，风险政策仍是已批准的
  Standard Research Profile。
- Core 案例 ID 原样保留和显示。批量详情使用其 UTF-8 SHA-256 `case_key`
  作为本机导航键，避免上游合法的 Unicode、斜线或长 ID 被路径规则过滤。
  同批键冲突必须拒绝整个存档，不覆盖案例；导航键不是新的经济身份或评分。
  Direct 原有详情路径不变。
- EI 审核与假设、来源、事实/解释和时间依据保存为明确的规范化审计投影；
  不声称该投影重建了整个 provider Browser 或原始对象身份图。
  不保存原始模型/行情 payload 或配置密钥。
- 默认展示完整 compact comparison、分类数量和不可用原因，不预生成每个
  案例的全文。人工点击某案例时，仅从已有数值记录和保留的权威披露生成
  中文详情，不重新搜索、推理或取行情。
- 既有 Direct 自动全文行为不变；未知费用和敏感性不自动填补。

## 宿主状态

`COMPLETED` 是全部已执行分支有确定性终态，不代表 Core 证据完整或发现
投资机会。有不可用/未完成分支时保留 `PARTIAL` 和具体原因；没有合法非空
submission、超限或前置门槛失败时 `BLOCKED`。异常 `FAILED` 不冒充没有机会。
这些状态不得替代 EI 或 Core 自己的状态。

此适配器只消费已保留的 Core 分支，不能从 `CoreRunResult` 推断原始请求的
全部子问题覆盖程度。真实 Grounder 接入仍须保留独立 coverage 和阶段诊断；
批量 `COMPLETED` 不能升级成“用户事件已全面核实”。

## 验收

合成集成验证执行器调用、顺序、原子存档、迁移、隐私、compact 与惰性详情；
不得记录成真实 World/Event 三入口验收。已有 v1/v2 数据库非破坏式迁移，
保留 Direct 存档及持久单实例锁。最终代码、审阅与真实能力状态以
[当前断点](current-checkpoint.md) 为准。

## 接口与数据

`create_server(..., world_executor=..., event_executor=...)` 接收由本机程序
配置的可信回调，签名为 `(raw_input, *, bounds) -> CoreRunResult`。
World 结果必须绑定原始字符串；Event 结果必须保留对应
`UserEventInput.description`。未配置入口继续拒绝执行。此接口不授予 HTTP
调用者代码执行权，也不提供绕过 Grounder、EI 或市场验证的生产来源。

存档 schema 为 v3，批量快照为 `host-batch-snapshot-v0.1`，阶段指针为
`host-batch-outcome-v0.1`。compact 保留原字段，新增 `host_status`、案例
`case_key` 和 `unavailable_cases` 原因旁注；`unavailable_case_ids` 仍是
原始 ID 字符串列表。数值用精确字符串表达，不通过 JSON 浮点改变计算。

运行详情只返回摘要和案例索引，不透传 EI 私有审计或 Core 内部快照。
批量案例详情路径使用 `case_key`，原有 Direct 路径使用 exact case ID。
限额失败保留 Core 的 `cases:5>2` 等诊断，而不是截取一个可展示的前缀。
