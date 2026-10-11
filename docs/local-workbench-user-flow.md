# 本机工作台与研究入口

本机 HTTP/CLI 和 Direct 执行器可独立于 Codex 运行，不等于三入口真实研究已经接通。
默认没有研究执行器；未配置的入口必须留下
`BLOCKED / HOST_EXECUTOR_NOT_CONFIGURED`，不能展示为研究成功或没有机会。
未配置的 World/Event 保持禁用；Direct 需显式启用。常规 CLI 的 Event/World
可用显式外部配置接线，真实 EI/Core 结果仍以运行记录为准。

批量交付层现已支持本机程序显式注入可信 World/Event 回调，保存所有案例并
默认显示完整 compact comparison；这不等于无配置启动时具备真实来源。
没有合成生产默认值。接口与存档
边界见 [批量交付说明](local-batch-delivery-v0.1.md)。

## 启动与输入

2026-10-11 本机已有仓库外的私有启动器及配置，须显式提供研究日期：

```bash
/Users/erwinlee/convexity-hunter/local-mvp/start-host.sh YYYY-MM-DD
```

此路径是本机部署，不是 Git 中的共享默认配置。工作台位于
`http://127.0.0.1:8080`，三个入口已接线；启动本身不执行研究。
持久数据库保存了一个真实 Direct 案例，可读取中文报告而不重新查询行情。
其结果为 `DATA_INSUFFICIENT_CORE`，缺少成本账本和敏感性输入，不能显示为
发现可投资机会。日期不会自动滚动；改变日期须明确重启，而不是悄悄延长
假设适用期。当前 Event/World 的真实验收仍被来源/EI 证据阻断，详细结果见
[当前检查点](current-checkpoint.md#three-entry-mvp-continuation--2026-10-11)。

2026-10-10 的两次独立正常运行已完成并存档：Event 在 producer envelope
校验处 `BLOCKED / PRODUCER_ENVELOPE_INVALID`；World 为
`BLOCKED / world_last30days_empty / world_grounder_no_submission`。两者均未
进入 EI/Core，不把失败解释为没有机会。World 的中文 HTTP 与 SQLite 重启
读回通过，Event 仅恢复了 SQLite 状态；缺失的计数不补造。来源 identity
composite 的单独验证成功不代替入口验收，详见当前检查点。

另有显式实验入口 `examples/local_event_host.py`，接入 Tavily Basic Search/Extract、
DeepSeek 两角色核验及同一 Event Core。它可脱离 Codex 启动，但尚未证明真实
Event Intelligence 接受：只按受支持格式解析来源，未知主体与日期证据不补造。
启动须明确提供仓库外的 `host-event-config-v0.1` 配置文件、`--evaluation-date`、
`--maturity-authority`、`--futu-port`、私有 `--db`，可指定 `--port`。
配置只引用外部凭证；预算与授权标志必须显式设置。服务启动不读取凭证或连接行情。
未形成 submission 时显示 `BLOCKED / GROUNDING_NO_SUBMISSION`；形成 submission
时先存档实际 EI assessment，再交给原 Core。搜索成功、EI 接受和 Core 完成互不等同。
完整边界见 [Event 接入说明](local-event-delivery-v0.1.md)。实验入口仍保留，
常规主 CLI 不再要求用户另写 Python 回调才能配置 Event。

常规 Event 启动使用同一严格外部配置、明确日期及成熟期权政策：

```bash
PYTHONPATH=src python3 -m convexity_hunter.host_server \
  --db /private/tmp/convexity-hunter-session/runs.sqlite --port 8080 \
  --event-config /absolute/private/path/event-config.json \
  --evaluation-date 2026-10-07 \
  --maturity-authority neutral_structural_research --futu-port 11111
```

外部配置路径是示例，须替换为实际存在的本机配置；不要把凭证内容写入命令。
日期是明确的研究输入，不是自动滚动政策。加 `--enable-direct` 可同时启用
Direct。启动只安装回调，真实 source/model/行情请求仅在提交研究时发生。
启动成功不等于 EI `ACCEPTED`。本轮一次真实 Event 生成了 submission，但
EI `INCOMPLETE`；直接来源因非公网 DNS 答案被拒绝，不放宽安全规则重试。

World 在同一命令上加 `--world-config /absolute/private/path/world-config.json`。
该独立非秘密 JSON 使用 `host-world-config-v0.1`：`skill` 明确提供固定
last30days 3.21.1 路径/哈希、已批准外部 Python、来源 allowlist、允许传递的
环境变量名称、阶段/字节/TTL 限额；`bounds` 提供五项最大工作量。
共享 Event 的 Tavily/DeepSeek 配置，每模型角色预算至少为两次，分别分配给
Skill 和 Grounder。配置只包含授权名称，不能包含 cookie/key 的值，也不自动
读取 Skill 私有配置或环境凭证。缺少实际授权环境值时，不能声称来源全覆盖。
原始 native 评分不进入 Hunter，全部已接受假设继续进入同一 Core。
操作失败或来源不足保留原因，不解释为“市场没有事件”。
常规 World 启动存档复用已冻结的共享模型/来源配置投影。旧 Store 的
`skills` 数组只接受空值，因此这里的 `skills=[]` 不是“未使用 Skill”的证明；
实际消费的 native 来源通过 Core source provenance 保留，失败/未消费状态
通过 closed reason 保留。此交付不新增 Skill 配置存档 schema。

截至 2026-10-08，Main 已用同一份 reviewed runner 执行一次限额 World run，
该运行已 spent、不可重放：READY、POST 201、Host BLOCKED；无 submission、
hypothesis、Core case 或 unavailable case，EI 为 NOT_RUN。原因仅为
`world_grounder_no_submission` 和 `world_last30days_partial`；
`skill_stage_count`、`provider_request_counts` 为 null，表示未知而非零。
配置和凭证就绪不证明 X/Reddit 已认证或覆盖成功；归档未保留 partial 的
底层来源/阶段原因。SQLite 重启读回与中文 HTTP 文档读取成功，但没有测试
浏览器交互。

后续 World 接线只在既有 partial 分支增加固定的原生来源诊断：
`not_ok` 表示原生报告没有明确报告 `ok`，`unknown` 表示没有可用状态。
它们不是独立核实的鉴权结论。只标记已配置的来源，不显示原始错误文本；
本次已结束运行的缺失详情不会被补造或重跑。

2026-10-08 的 World/Event 两次独立尝试均已 spent：POST 201、Host BLOCKED、
EI NOT_RUN。精确结果与 Grounder review (`NO_DEFECT_PROVEN`) 见
[当前检查点](current-checkpoint.md)；本页不重复计数。

在仓库根目录运行：

```bash
PYTHONPATH=src python3 -m convexity_hunter.host_server --db /private/tmp/convexity-hunter-session/runs.sqlite --port 8080
```

数据库必须位于仓库外的当前用户私有目录（0700）；已有权限过宽的目录会被拒绝，
不会自动改权限。数据库与同目录持久锁文件采用 0600。不要在服务运行时删除或替换锁文件。
同一数据库只允许一个服务实例；符号链接路径会被拒绝。
示例路径仅供本地试用，不是长期保存建议。
启动后打开 `http://127.0.0.1:8080`。服务只绑定本机回环地址，不支持远程共享。
本页不能配置密钥、私有配置路径或执行任意命令。

已有登录的 Futu OpenD 时，可显式启用 Direct（端口须与本机实际配置一致）：

```bash
PYTHONPATH=src python3 -m convexity_hunter.host_server --db /private/tmp/convexity-hunter-session/runs.sqlite --port 8080 --enable-direct --futu-port 11111
```

启动只安装执行器，不初始化 SDK 或探测行情。提交 Direct 才调用已有 Futu
exact verification 和 `run_direct_core`。SDK 输出受控；不读取 Futu 私有配置文件，
不建立交易上下文。具体输入见 [Direct 输入格式](local-direct-input-v0.1.md)。

选择 World、Event 或 Direct，输入原始研究意图，并明确填写五项操作预算：
`max_submissions`、`max_hypotheses`、`max_browser_rows`、`max_cases`、
`quote_timeout_seconds`。这些是工作量上限，不是经济评分或结构推荐。
批准的 Standard Research Profile 只读展示；页面不生成新的风险政策。

## 结果与历史

每次提交创建独立运行记录，先保存原始输入和政策快照，再开始 provider 工作。
当前 schema v3 非破坏式迁移 v1/v2 历史；保存结构化 Core 数值结果作为事实源。
Direct 单案例自动打开中文报告，其缓存是绑定数值快照 digest 的派生视图。
历史/详情读取不会重新调用模型、搜索或行情。没有结果时明确返回不可用，不生成模拟报告。

已配置的 World/Event 结果保存所有
已计算案例和不可用分支，按原顺序展示；不自动打开任意案例，不排名或隐藏
证据不足的行。用户点击详情后才从已有数值记录生成报告，不存 N 份预写全文。
批量详情使用稳定导航键，原始 Core ID 原样显示，包括 Unicode 或长 ID。

Host `COMPLETED` 只表示这次研究计算已结束；Core 可以是
`DATA_INSUFFICIENT_CORE`，并不代表证据完整、发现机会或建议交易。
原始输入、内部配置与完整 Core 存档不从历史接口默认透传；来源 URI 的鉴权信息会被拒绝存档。

Direct 不调用模型、新闻或历史数据；只使用已授权的 Futu 市场数据路径。
这个接入不解除 World/Event 的 Grounder 阻断，不填补费用或敏感性缺口。
Core 结果存档 v0.1 显式拒绝尚未支持的完整 VolEnv/Tail 增强对象，而不是默默丢弃；
现有 Domain 增强能力未删除，也不成为没有增强时的 Core 必需依赖。
