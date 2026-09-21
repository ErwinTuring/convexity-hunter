# World / Event 来源验证阶段性决策报告

协议日期：2026-09-20；路线更新：2026-09-21。状态：**阶段性 BLOCKED
CHECKPOINT**，不是成功的完整实验。本文件只记录已证实事实。

## 1. 边界与窗口

- 本轮 protocol 的来源发表窗口是 **2026-09-14 至 2026-09-20 UTC，含首尾**，
  但 9 月 20 日尚未完整结束，实际观察时间封顶；Discover 的七日差值为
  `--days=6`，不使用 `--as-of`。
- 本轮范围是公开信息及有支持依据的暂定美国上市 equity/ETF 关系；不使用
  市场价格反馈、排名、推荐或经济政策参数。
- 历史对照并非同窗：Web Search 与 adapted `morning-note` 使用
  **2026-08-18–2026-08-24**；`last30days` 正确 rerun 使用
  **2026-08-19–2026-08-25**，错开一天。
- 历史 Web/SOC 批次有 9 个 validated candidates；同窗 adapted
  `morning-note` 也有 9 个记录，5 个语义重叠、各 4 个独有。历史
  `last30days` 的 proper rerun 是 native `clusters=[]`、`results=[]`，适配批次
  为 0；其内部产生空导出的具体阶段未知。

历史对照证据：[event-discovery-soc-real-exercise.md](event-discovery-soc-real-exercise.md)、
[event-discovery-producer-comparison.md](event-discovery-producer-comparison.md)、
[event-discovery-last30days-evaluation.md](event-discovery-last30days-evaluation.md)。
本轮 protocol / history 是外部执行记录，路径不作为 GitHub 链接。

冻结的 Web 查询均附加 `after:2026-09-13 before:2026-09-21`：

1. `US public company regulatory litigation merger announcement`
2. `US listed company clinical trial FDA financing announcement`
3. `AI infrastructure financing customer contracts public companies`
4. `technology industry business model belief shift public companies`
5. `supply chain power regulation second order company impact`
6. `US company operational disruption capital structure funding`

Web 原文打开上限 12 次。Skill 固定 domain 为
`U.S. public companies regulation technology financing`，default 深度，
`--search=reddit,x,youtube,hackernews`；YouTube 仅用于 enrichment。
两者是同窗、同市场的不同原生工作量边界，不声称等成本或穷尽覆盖。

## 2. 本轮 Web Search：未形成已验证候选

- 六条固定查询各执行一次，分两次三查询调用；没有改写查询或新增搜索。
- 已记录 **8 次读取尝试**：初始 Main 4 次 opens，加后续 4 次受限来源读取；
  未保存全文。搜索摘要只是 raw leads，不是事实认证。
- 已验证候选数：**0**。原因是原始来源打开失败或受限，且来源发表时间、
  U.S.-listed identity、事件日期或具体事实仍缺失；没有 padding，也没有把
  未认证线索转成候选。这不是“没有事件”的结论。
- Axios 线索的直接来源不可访问；SEC 线索超过读取器 4 MB 限制。Nscale
  未确认上市，因此不做强映射。其他已读材料也未提供满足窗口、主体和事实
  绑定的候选。

本轮 6-query / 8-read / 0-validated 结论直接记录于本节；历史批次边界见
[event-discovery-producer-comparison.md](event-discovery-producer-comparison.md)
与 [event-discovery-last30days-evaluation.md](event-discovery-last30days-evaluation.md)。
本轮 web-audit 是外部执行记录，不提供本机路径链接。

## 3. `last30days` 本轮状态：BLOCKED，最终适配未完成

本轮已实际执行一次 nomination，且 leg 2 已完成；原始 aggregate 与
`native/discover-nominations.json` 保存在外部目录，本文不复制 nomination
全文。外部 `native/discover-pending.json` 记录 5 个 pending topics；当前可确认
的计数链为：

```text
X:      native 29 -> normalized 26 -> nomination 15
HN:     native 66  -> domain gate 0
Reddit: native 0   -> normalized 0
```

- Main 已阅读全部 15 条 nomination 并写入 judgments；leg 2 成功完成 5 个
  pending topics。Main 的 `read_pending_report` 已直接验证
  `pending_valid=false; stale=true`。
- 记录时钟为 `2026-09-20T23:47Z`；nomination 记录为 `15:32`，pending 记录为
  `15:38`。相对于原生 TTL `3600s` 已过期；finalize 离线尝试为 exit 2。
  不修改 timestamp，不重新拉源，不重跑，也不把它写成“待正常 finalize”。
- leg 1 成功产生 15 nominations，leg 2 成功产生 5 pending topics，leg 3 因
  会话中断而 stale；最终 `EventCandidateBatch` 为 **NOT_COMPLETED**，不是 0。
- HN 的 native `no-results` 被定位为本轮 domain gate 过滤掩盖了已有源内容；
  这只能解释本轮，不能反推历史 run 的原因。
- native `tierdeep=默认 enrichment` 已记录；这不是 CLI `deep` flags，也不是
  未授权的深度运行。
- 实际 Skill 文件路径为 `/Users/erwinlee/.codex/skills/last30days/SKILL.md`，已安装
  版本 `v3.21.1`，Skill 文件 SHA-256 为
  `cad0d0f0459f05692dddf14ec11d6d9ae9e8e5f1b3a1b7ddb132b4fc6967c5fe`。历史
  评估 upstream pin 为 `d05389d39b2ce09a13f71b01e68562f077c766df`；已知
  upstream `v3.25.0` / `349ca444b4fda466e74d471dffa2aff36bb997f1`，本轮未升级。
- 上游 native counts 带有 selection bias；adapter discard score 不会消除该
  bias。计数与 nomination 仍是中间观察，不是最终 Hunter candidates、EI
  `ACCEPTED` 或 Core 结果。
- pending 存在可疑主题/日期混杂：`Digital asset regulatory clarity` 的证据 URL
  含 `digital-addiction`，`AI weekly` 列有带 June 与 September 13 日期路径的
  链接。这些原文尚未独立打开核验，不能仅凭 URL 确定发表日或最终排除。
  来源渠道覆盖数不等于事实相互印证，仍需独立 source qualification。

不得把历史 2026-08-19–25 的 zero 复制为本轮结果，也不得因本轮已有内容就
宣称 `last30days` 价值、完整性或最终候选已经成立。本轮最终适配未完成；上述
nomination 与 pending 文件均为外部执行记录，不提供本机路径链接。

本轮最终共同/独有事件数尚不可比较：Web 为零个验证后候选，Skill 最终批次
未完成。仅在线索层，Web 看到了铁路并购、IPO/融资和 AI 商业化评论；Skill
看到了 AI 安全分歧与代币化股票监管话题。这不是已核实事件增量或优胜结论。
目前保留 Web 为公开资料基线、Skill 为注意力线索补充，不要求互相替代。
目前未取得 Web 与 Skill 的完整货币/credit 消耗计量，不能称为零成本；Codex
核实过程也消耗订阅额度。原生渠道数和互动量不进入 Hunter 经济判断。

## 4. Grounder 路线更新：OpenAI 历史路线已 superseded

- 旧 OpenAI preflight 仅保留两项事实：Responses API live calls 为 **0**、事实
  质量为 **NOT_MEASURED**；该付费路线已被当前方案 superseded，不再等待 OpenAI
  key。
- 当前先验证 Tavily 免费层的 search、extract 与额度；必要时才使用 SearXNG +
  Jina，不扩展其他商业 API。初次检查时进程及 external config 均无
  `TAVILY_API_KEY`，API 调用为 **0**，免费剩余额度为 **UNKNOWN**，不能假定为
  1000；缺 key 不证明方案不满足，当前不转 fallback。
- 随后用户报告已配置。只读文件元数据检查发现约定的 `.env` 路径实际是
  directory（0755），不是可加载的普通配置文件；未读取其中内容，未修改
  目录权限，也未发出 Tavily API 请求。
- 2026-09-21 后续配置已成功：仓库外纯文本文件（0600）通过鉴权；实际一次
  `GET /usage` 返回 `current_plan=Researcher`、`plan_limit=1000`、
  `plan_usage=0`、`paygo_usage=0`，因此观察到剩余 **1000 plan credits**。
  `paygo_limit=null` 与 key `limit=null`，不能将 null 解释成付费功能已关闭。
  这一阶段暂未运行 Search/Extract；随后用户的 Researcher 控制台截图明确
  显示 Pay as you go **关闭**，free-only gate 满足。无需再次配置密钥。
- Tavily 官方支持要点：免费层为 1000 credits/月且无需卡；`/usage` 查询
  key/account limit/usage/paygo；Basic Search 每次 1 credit，使用
  `auto_parameters=false, include_answer=false, include_usage=true`；Basic
  Extract 每 5 个成功 URL 消耗 1 credit，保留 `results`、`failed_results` 和
  URL，HTTP 200 不单独证明 extract 成功。
- Tavily API 的独立 search/extract 输出不等于 Codex 语义核实或可直接生成
  submission；二者之间的 bridge 仍需独立部署与验证。

官方参考：[Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search)、
[Tavily Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract)、
[Tavily Usage](https://docs.tavily.com/documentation/api-reference/endpoint/usage)、
[Tavily API credits](https://docs.tavily.com/documentation/api-credits)。

### 2026-09-21 真实免费检索/提取结果

冻结查询不变（IPW July 6 note draw；SOC August 21 ruling/appeal；IREN May
Microsoft/Dell financing），不是历史 as-of 回放。三次 Basic Search 全部成功，
各返回五条来源，URL/title/content 保留，原生 score 不进入 Hunter。
全部十五条 `published_date` 均为 null；正文中可见日期必须另行解释为事件日、
文件日或报道日，不能成为 expected impact end。

| 案例 | 本轮选取的返回来源 | 实际结果与边界 |
| --- | --- | --- |
| IPW | [SEC 8-K](https://www.sec.gov/Archives/edgar/data/1830072/000168316826005288/ipower_8k.htm) | Basic Extract 成功，返回 URL 与请求一致；正文确认 July 6 事件、Nasdaq/IPW、200 万美元票据本金及 188 万美元费用前所得。不是净现金或已证实融资充足。没有虚构影响结束日。 |
| SOC | [DOJ 声明](https://www.justice.gov/opa/pr/federal-court-protects-national-energy-security-and-rejects-dangerous-state-efforts-obstruct) | Basic Extract 成功；这是政府诉讼方叙述，不是完整裁定。返回正文缺少确切裁定日期，包含已更新说明；不能忽略其他检索摘要提及的罚款、上诉或将官方修辞写成中性事实。 |
| IREN | [匹配 May 事件的披露转载](https://www.stocktitan.net/sec-filings/IREN/8-k-iren-ltd-reports-material-event-675eb20880e1.html) | 提取工作流发生 `URLError`，无成功正文；未重试。该流程先查 usage 再 Extract，错误未记录阶段，因此不能确认 Extract 请求是否送达，更不能称 provider 拒绝该 URL。 |

IREN 搜索还返回 Nov 2025 的官方文件、May 2026 的采购和 June 2026 的融资
材料。选择匹配 May 事件的转载而非错期官方文件，保留非原始来源限制；不得把
不同客户合同、采购与融资拼成同一笔交易。返回的 Yahoo/Blockspace 摘要还披露
了先前误把 NVIDIA 关联至融资的编辑更正，说明相反/修正证据需要显式保留。
本轮未追加搜索、未改查询、未借 Codex Web Search 替补失败来源。

用量：三个 Search 响应各报告 `credits=1`；两个成功 Extract 各报告
`credits=0`。执行后两次只读 `/usage` 的 key/account 仍报告使用 0、plan limit
1000、PAYGO 使用 0。**端点响应与账户计数不一致，原因未定位**；不能称检索
零消耗，也不能将 1000 当作已结算剩余量。没有第四次搜索或重试提取；最坏
预算仍在预注册六个 credits 内。失败流程是否到达服务端未确证。

独立部署边界：Tavily API 检索及两次提取已经真实运行；事实审阅、归因及输入
构造仍由 Codex 完成，不等于脱离 Codex 可自动运行的 `grounder`。现有
`run_event_core`/`run_world_core` 需要 source-backed submission，不是搜索
结果列表。没有将临时执行脚本冒充 production adapter。

当前没有证据证明免费方案本身不满足来源或成本约束，因此不启动 SearXNG +
Jina fallback。最小后续边界是来源时间/主体/相反证据核验及可审计的 submission
构造，不是更换检索商、恢复付费 OpenAI 或修改接受门槛。

### 现有 Event Intelligence v0.2 接受检查（真实来源的部分输入）

外部 `ei_trial.py` 从本轮返回的 URL 和已读取正文构造部分 submission，运行
未修改的 `assess_event_intelligence_submission`。这不是旧结果重放，不是
Tavily 直接生成的 submission，也不是模型输出 JSON 即通过事实认证。

- **IPW：INCOMPLETE**，`missing_temporal_applicability`。交易日可确认，
  expected impact window 与 reassessment 均无本轮已核实依据，保持 absent。
- **SOC：INCOMPLETE**，`incomplete_event_date_range`、`missing_underlying_key`、
  `missing_distribution_mode`、`missing_temporal_applicability`、
  `missing_contradiction_review`、`missing_falsification_conditions`。
  DOJ 正文不单独认证证券身份，也不替代对罚款、上诉及裁定原文的核验。
- **IREN：INCOMPLETE**，`incomplete_event_date_range`、`no_statements`、
  `missing_underlying_key`、`missing_impact_path`、`missing_distribution_mode`、
  `missing_distribution_hypothesis`、`missing_temporal_applicability`、
  `missing_supporting_evidence`、`missing_contradiction_review`、
  `missing_falsification_conditions`。检索摘要没有升级为已核实事实。

这些是有意保留未核实字段的部分输入结果，不是 Tavily 自动 Grounder 的
准确率指标，更不能归因为“免费搜索无用”。当前没有生成 Core case，没有
设置财务政策，没有运行市场数据或 Futu。

## 5. 数据边界与未授权事项

- `core_application.SourceSubmissionBatch` 绑定 exact raw input 和
  source-backed `EventIntelligenceSubmission` 元组；它**不等于**
  `EventCandidateBatch`。
- `EventCandidateBatch` 只证明 discovery 层发现了 provisional candidates；
  仍需已验证的 translation / grounding bridge，不能直接宣称 EI `ACCEPTED`
  或 Core 结果。
- 本轮不设置任何未经批准的风险、成本、loss budget、repeat-loss 或
  sensitivity 数值模板；缺失 policy 继续保持缺失，不以零或 synthetic policy
  补齐。该边界独立于来源验证。
- 不据此宣称全部任务完成、当前无事件、`last30days` 无价值、或任何投资/凸性
  结论。TTL 过期、leg 3 stale、`NOT_COMPLETED` 仍是本轮 World 实验限制；
  凭证、免费方案和付费开关确认已解决。当前 Event 限制是上述提取
  传输故障、用量计数不一致与未完成语义核验，不通过默认值或重拉源补齐。

实现边界可核对 [core_application.py](../src/convexity_hunter/core_application.py)
和 [event-discovery-intake-contract.md](event-discovery-intake-contract.md)。
其余 Grounder 结论来自外部 preflight 执行记录（不提供本机路径链接）。

## 6. 实现与验证边界

本次仓库变更仅为本报告及两个状态文档，未改生产代码、测试、Kernel、
EI 接受契约或经济参数。现有构造器已验证本轮 Web 空批次；Skill 的最终
批次未构造。Tavily 真实检索和部分真实输入的 EI 检查已执行，不是独立部署的
产品集成成功。已执行文档相对链接与代码
围栏检查、`compileall` 和 `git diff --check`；没有因文档修改重跑完整回归。
这份记录保存可恢复断点，不把准备好的接口或合成能力升级为真实接入。
先前阶段及本次新增真实试验结果均已通过独立文档语义审阅。
恢复的 Luna 执行任务未返回结果，已停止以避免重复请求；Main 随后核对
usage=0 再执行固定试验。本次审阅直接覆盖新增事实，不借用旧审阅结果。
生产实现仍未改变。

本次后置验证：`tests.test_event_intelligence` **32 tests PASS**，`compileall`
通过，三份变更文档的相对链接/代码围栏检查与 `git diff --check` 通过。
最终独立审阅 PASS；唯一收尾意见为更新“审阅尚未返回”的过时文字，已修正。
未运行无必要的全套回归。阶段性报告可提交；实际提交与推送状态以 Git 为准。
下一执行点：单独设计 Grounder 语义核验环节。下一轮端到端实验需明确授权，
不自动重发三次搜索/提取；last30days 另行完整实验，不补跑已过期记录。
