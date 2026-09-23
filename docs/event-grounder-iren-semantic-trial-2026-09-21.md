# IREN 有界 Event 语义核验实验

状态：检索、来源主张核验、现有 EI 接受检查完成；最终独立执行审阅 PASS。
真实取数日为 2026-09-21，
中断后于 2026-09-23 复用留存材料；不宣称 9 月 23 日新取数或历史 as-of 回放。
依据：[已审阅设计](event-grounder-semantic-verification-design-v0.1.md)。

## 授权与预算

用户明确授权下一轮有界 Event 实验。选择一例 IREN，输入为研究 2026 年 5 月
GPU 采购及 Microsoft 相关融资是否体现项目融资与运营义务的结构性变化。
先固定协议，再查询：最多 2 次 Basic Search、3 个 Basic Extract URL，
保守上限 5 credits；无重试、无追加查询、无其他搜索服务或付费模型 API。
PAYGO 关闭依据为用户控制台截图；密钥仅由外部受限文件在内存读取。

固定查询：

1. `IREN May 29 2026 GPU financing credit agreement Microsoft May 29 2027 SEC`
2. `IREN Microsoft GPU financing termination default deployment delay September 2026 SEC`

## 检索验收

- 两次搜索均成功，各返回 5 条；不是 10 个独立事实或 10 个候选事件。
  来源包含重复转载，未按 relevance score 排名或将重复视为独立印证。
- 三次提取均成功，返回 URL 与请求一致，`failed_results=[]`。
- 先提取搜索返回的融资披露转载以定位官方链接，再读取融资 SEC 原文和
  第二条查询返回的 Microsoft 基础合同披露；没有额外读取第四个 URL。
- 检索没有返回足以核验 September 当前履约/修订状况的完整原始披露。
  第三个读取选择基础合同的风险条款，不把旧文件称为最新状态证明。

| 原文标识 | 来源与选择依据 |
| --- | --- |
| R0 | [StockTitan 融资披露转载](https://www.stocktitan.net/sec-filings/IREN/8-k-iren-ltd-reports-material-event-3201e478a7b8.html)：仅作官方链接发现；不采用其自动摘要、情绪/影响等级。 |
| F1 | [融资 Form 8-K](https://www.sec.gov/Archives/edgar/data/1878848/000114036126023427/ef20075181_8k.htm)：R0 正文明确链接的 SEC 原文。 |
| F2 | [Microsoft/Dell 基础协议 Form 8-K](https://www.sec.gov/Archives/edgar/data/1878848/000114036125040072/ef20058139_8k.htm)：第二条搜索直接返回，核对基础合同与风险。 |

## 来源主张核验（不是全量合同审计）

| 主张 | 依据与限定 |
| --- | --- |
| 主体 | F1/F2 封面均为 IREN Limited、Nasdaq 普通股 IREN；Hardware 3 为披露所述子公司，不当作独立上市标的。 |
| 事件日期 | F1 明确融资协议日期 2026-05-29，签署日期 2026-06-01；F2 基础协议日期 2025-11-02。不把签署日或抓取时点填成精确发表时间。 |
| 融资范围 | F1 Item 1.01 披露约 36 亿美元融资安排，关联 2025-11-02 Microsoft 合同；不是全部已提款、已验收或已实现收入。 |
| 可观察节点 | F1 Availability and Maturity 披露提款/发行可用期至 2027-05-29，附延展条件。只可作为粗粒度最晚复核节点，非影响终点或期权期限依据。 |
| 资产与现金流联系 | F1 Guarantees and Security 披露抵押资产、子公司股权及 Microsoft 合同现金流；这是运营履约与偿付关联的事实基础。 |
| 不利及制约证据 | F1 有有限母公司保证、未验收/终止相关差额、契约限制、加速偿付及暂时性对冲担保；F2 有交付验收、延期与解约条款，并披露 Dell 采购义务的母公司无条件保证。不能称风险完全隔离或全面无追索。 |

Hunter 解释须单列：合同履约、部署/验收、现金流与债务偿付可能形成不同结果
路径。以上并未证明企业层面影响幅度、当前实际违约、正期望、低估或投资价值。
两份文件自身均说明其摘要不完整、以协议原文为准；本轮未读取完整协议附件。

没有把另一个 May 2026 约 16 亿美元采购直接并入 Microsoft 项目；该部分本轮
未核实，保留为原始输入未解决的子问题，而非悄悄视为同笔交易。F1 的显式
交叉引用支持基础合同关联，不推断 Inc./LLC 之间未经核验的法律变更历史。
有限检索未确认后续修订、实际提款/部署、违约或延展情况，不等于确认其不存在。

## 用量留痕

本轮前 `/usage` 已反映上轮 3 credits，显示剩余 997、PAYGO 使用 0；之前的
计数差异已收敛，延后更新只是解释，不是已验证服务端机制。
本轮 Search 响应各 1 credit，Extract 响应依次 0、0、1，合计报告 3 credits；
末次 `/usage` 仍为累计 3，不能据此称本轮零消耗或 997 是已结算余额。
恢复执行不再次查询额度。无新增购买、账户设置变更或原始 payload 入库。

## 产品边界与待完成验证

### 实际接受结果与原始输入覆盖

外部离线脚本新建 submission，调用未修改的
`assess_event_intelligence_submission`，实际返回 **ACCEPTED / issue_codes=[]**，
版本 `event-intelligence-acceptance-v0.2`。未复用历史 ACCEPTED 对象。

- 原始输入仍为完整 May GPU 采购及 Microsoft 融资研究意图，保留同一个
  `UserEventInput` 对象；`SourceSubmissionBatch.raw_input` 身份检查通过。
- 只有已核实 Microsoft 融资子假设进入非空 batch。另一个采购子问题仍未解决，
  所以 **融资子假设 ACCEPTED ≠ 原始事件已全面核实**。
- 事件日期为 2026-05-29；精确发表时间保持缺失，来源观察时间保留为
  `2026-09-21T12:33:26.397314+00:00`，不改成恢复执行时点。
- `expected_window=None`；复核日期 2027-05-29，basis 为
  `SOURCE_BACKED_MILESTONE`，直接绑定 F1 的可用期事实，并保留延展条件。
  它只是粗粒度复核依据，不是当前事实持续有效的保证或 maturity anchor。
- 10 条有来源事实、1 条明确 interpretation；验收保留风险、未知项和可证伪
  条件。没有发起 option discovery，也没有建立 maturity alignment。
- `core_called=false`；没有配置虚构财务政策或执行下游研究。

离线边界测试实际 **6 tests PASS**：零结果、传输/提取失败、无支持假设，及
构造失败均不产生空 batch 交给 Core；原输入、执行标识和来源请求绑定留存。
合法部分输入仍可返回 INCOMPLETE；完整合法复核依据的合成对照可通过；新构造
不重放旧对象；另有真实来源样本的日期/范围检查。合成测试不是额外真实案例。
这些仅是仓库外实验 helper 的行为，不宣称生产宿主已实现空 batch 防护。

现有 EI/Core Application **42 tests PASS**；`compileall`、文档链接/围栏与
`git diff --check` 通过；生产代码和测试文件未修改，未无故重跑完整回归。
来源事实独立审阅 PASS；实际构造、原始输入身份、留存时间、复核依据、
partial/empty guard 和结果另行独立审阅 PASS，并独立重跑 6 项离线测试。
审阅并未借用旧阶段结论；唯一收尾项为将本文件待审状态更新为已完成。

这是 Tavily 检索 + Codex 主张核验 + 现有 EI 确定性检查的宿主辅助实验。
不是 Tavily 自动生成 submission，也不是脱离 Codex 可部署的 Grounder。
不修改 Kernel、EI 类型或生产代码；无 Core 财务计算、Futu、策略排名或推荐。
现有成本风险政策未获新数值授权，不用 synthetic policy 冒充真实用户输入。
历史案例及 World/last30days 的 NOT_COMPLETED 状态不被本轮覆盖。
