# World Producer 新一轮对比（含预算偏差）

日期：2026-09-23。新实验，不是修复或重写 Sep20 过期记录。

## 协议与执行

同一来源发表窗口：2026-09-17 至 09-23 UTC（含首尾，末日截至实际采集）。
同一美国上市股票/ETF 研究范围及三条 Hunter discovery lanes。
Web 固定六次查询、最多十二次原文读取；Skill 一次原生 Discover 三阶段，
另最多十二次输出来源读取。工作量单位不同，不声称等成本或穷尽覆盖。
两组独立执行，不使用另一组结果补候选。Web 原文打开预算发生偏差，见下文；
不得称为严格预算合规的对照实验。没有额外调参、补数、市场数据、EI
晋级或 Core 执行。

Web 查询为 Sep20 协议的六个主题，仅时间运算符变为
`after:2026-09-16 before:2026-09-24`。领域为监管/诉讼/并购、临床/融资、
AI 基础设施融资、商业模式叙事、供应链二阶影响、经营/资本结构。
搜索结果日期运算符不替代原文发表日期核验。

Skill 为现有安装 v3.21.1，SKILL SHA-256
`cad0d0f0459f05692dddf14ec11d6d9ae9e8e5f1b3a1b7ddb132b4fc6967c5fe`，未升级。
domain=`U.S. public companies regulation technology financing`，
`--days=6`、default depth、来源 `reddit,x,youtube,hackernews`。
原生 `tier=deep` 是默认协议扩展，不是额外 CLI `--deep`。
使用已有授权 Chrome X 会话；没有新增凭证、付费模型或来源。

## last30days：原生流程完整完成

- 新 bundle `267d43dc56a94892`；07:40:17 UTC nomination，
  07:42:57 pending，07:44 finalize 成功，三阶段实际运行 exit 0。
- 没有 TTL 过期，没有修改时间戳，没有为更好结果重复采集。
- 仓库外日志屏蔽器首次导入缺少 `isatty()`，两次在来源调用前退出；只修正
  新外部副本的日志接口，原生 Skill 和生产代码均未修改。
- 初始来源：HN 64 条在领域过滤后为 0；Reddit 返回 0；X 使用 bird 返回 30，
  归一化后 29，进入 15 条提名。15 条均有 host editorial judgments，其中
  两条标记 junk。最终原生报告为 5 个主题。
- 原生 source_status 反映 nomination，不能误写成 enrichment 的最终状态；
  后者主题列有 Reddit/X/YouTube/HN 内容，但渠道计数不是语义相互印证。
- 原生 worthiness、velocity、rank 和 angles 不进入 Hunter；它们仍影响上游
  主题筛选，去掉展示分数不能消除选择偏差。

十二次来源打开：三次正文成功、九次失败。五个原生主题的适配如下（按名称
中性排列，不采用原生 rank）：

| 原生主题 | Hunter 核验结果 |
| --- | --- |
| China six networks infrastructure | 六网络、模型规模、无人机线索混杂；原文与具体上市关系不足，不保留 |
| Grayscale compute bottleneck financing | 仅标题和泛算力讨论；financing 是 host 查询措辞，不能升级成融资事实，不保留 |
| SEC blockchain software safe harbor | 提案正文未核实；共享的 SEC 豁免正文与下一主题去重，不把提案当成已通过规则 |
| Tokenized stocks trading expansion | 保留 SEC 官方公告支持的有条件豁免事件；不声称无条件 24/7 全市场交易 |
| Tyrants of Loving Grace | 正文未取到；原生印证混入家庭借款、宠物主题，不保留 |

已独立打开的 [家庭借款帖](https://www.reddit.com/r/AITAH/comments/1wmnu6q/aitah_for_insisting_our_son_pay_back_a_loan/)
与 AI 主题无关，提供具体的 enrichment 串题证据。
没有全量逐条 enrichment 正文，因此不报告一个看似精确的误报率。
正文打不开意味着本次未核实，不证明原始主张为假。

唯一保留的 provisional EventCandidate：
`2026-09-17-explicit-sec-tokenized-nms-exemption`，lane=`EXPLICIT_CATALYST`。
[SEC 2026-90 公告](https://www.sec.gov/newsroom/press-releases/2026-90-sec-issues-innovation-exemption-facilitate-trading-tokenized-nms-stock-request-comment)
明确 Sep17 发布，规定临时、有条件豁免及交易限制。
Hunter 解释仅为可能改变交易场所竞争和组织方式；经济幅度、具体上市标的
尚未建立。`provisional_underlying_symbols=()`、`expected_window=None`。
来源只有日期精度，`published_at=None`，外部 date audit 保留已核实日期，
不伪造午夜时间戳。法规五年期限不当作市场影响窗口。

现有 EventCandidate / EventCandidateBatch 构造校验通过；它是有效的暂定
市场事件，不是已绑定 ticker 的可执行研究假设，更不是 EI ACCEPTED。

## Web 结果与协议偏差

六条冻结查询均执行，返回 56 个搜索结果条目（不是 56 个独立事件）。
人工归并记录为 18 条线索，4 条保留、14 条排除。线索不是 Skill 的原生
主题计数单位，不能直接据此比较召回率。排除涉及窗口外日期、身份、原文
或事件完整性；这些原因可能重叠，不把本地初稿的分类小计作为精确统计。

Web 初稿将“最多十二次打开”误记为“最多十二个成功正文”。实际日志记录
首次十二引用批量打开返回 HTTP 500，随后九个正文成功及三个单独失败，
合计 **24 个 URL 打开请求项**。失败批次到底执行了多少服务器端读取未知，
但不能按一个 URL 请求计数，也不能免除其预算。保留本轮输出并披露偏差，
不通过改协议、重新抓取或重写时间戳使实验看起来合规。两组可作描述性比较，
**不能证明相同读取预算下的相对效率或优劣**。

中性来源日期/ID 顺序的四条 provisional candidates：

| ID | 已读取来源中的事件事实 | Hunter 暂定解释与限制 |
| --- | --- | --- |
| `web-20260917-a-nfg-strategic-review` | Sep17 Axios 报道 NFG 探索天然气生产资产出售 | 可能改变资产边界和资本配置；探索不等于交易达成 |
| `web-20260917-b-plains-silver-creek` | Sep17 Axios 报道 Plains 收购 Silver Creek 资产；Sep16 IR 原文佐证 | 可能改变资产及资本需求；事件日期 Sep16 与窗口内报道日期分开 |
| `web-20260917-c-unp-nsc-remedy` | Sep17 Axios 报道铁路并购竞争对手提出线路准入要求 | 补救条件可能改变交易结果；没有把要求当作获批条件，ticker 尚未核实 |
| `web-20260921-a-paramount-warner-settlement` | Sep21 AP 报道 Paramount/Warner 并购争议和解，仍待法官确认 | 可能改变交易约束；不是交易完成证明，交易后证券身份未核实 |

来源：[Axios Sep17 newsletter](https://www.axios.com/newsletters/axios-pro-rata-481aa6e7-8911-44ba-9bba-db005c9ea2f0)、
[Plains IR](https://ir.plains.com/news-releases/news-release-details/plains-acquire-powder-river-basin-assets-silver-creek-midstream)、
[AP Sep21](https://apnews.com/article/warner-bros-paramount-skydance-merger-settlement-1aaa7c471d8ba286ccfad92b18bc1ecf)。
Plains IR 是窗口外佐证，不替换窗口内来源。前两条分别有 NFG、PAA/PAGP
映射；后两条保留空 symbols。不把二手报道升级为法律原文或企业已确认事实。
四条均为 EXPLICIT_CATALYST，expected_window 均为空，没有自动提交 EI。

## 本轮比较与结论

| 层次 | bounded Web Search | last30days |
| --- | --- | --- |
| 实际来源起点 | 六查询、56 个结果条目 | HN/Reddit/X nomination，后续含 YouTube 扩展 |
| 中间输出 | 18 条人工归并线索 | 15 nominations → 5 native themes |
| 通过现有候选对象构造检查 | 4 | 1 |
| 两组共同保留的事件 | 0 | 0 |
| 仅本组保留的事件 | 4 | 1 |
| 最终 lane | EXPLICIT_CATALYST | EXPLICIT_CATALYST |

事件层面的增量不同：Web 是资产出售/并购及补救、和解；Skill 是 tokenized
证券交易制度。最终没有独有的 discovery lane，也没有已核实的 narrative /
second-order 候选。原始注意力主题更广不等于已经建立二阶经济传导。

本次证明 Skill 能完成 native → 来源核验 → 既有 EventCandidateBatch；
也暴露了“多渠道计数”可能掩盖串题，需保留逐项来源核验。尚不能证明
独立运行 World 产品适配器已实现，或人类认为该增量值得继续研究。
Web 保留基础来源角色，Skill 可补充注意力线索，不构成替代关系。

## 历史结论边界

本次不是 Sep20 的 `NOT_COMPLETED`：它已经完成原生输出及 Hunter 适配。
本次也不能解释 Aug25 空导出的所有内部原因。现在能具体观察到领域过滤、
原生主题扩展串题和后续来源读取限制；不能把历史零候选说成市场无事件。

保留 Web 为公开信息基线，Skill 为可选注意力线索来源；不要求互相替代。
完整 provider credit/金额差值未计量，Codex 核验消耗订阅额度，不声称免费
或零增量成本。人类新颖性、继续研究意愿及有效增量仍需用户反馈。

## 复核与保存

本轮仅修改本报告、current-checkpoint、project-state；生产和测试文件未改。
两组外部验证脚本构造现有 EventCandidateBatch 均通过，Web 验证另明确输出
预算偏差，不能把对象格式通过当作实验协议通过。
`tests.test_event_discovery` 20 项通过；两验证脚本 compileall、三份文档本地
链接/代码围栏检查和 `git diff --check` 通过。文档工作未运行完整生产回归。
详细采集、中间结果及候选对象留在仓库外
`research/world-source-comparison-2026-09-23/`，不提交原生社交正文或凭证。
独立文档审阅 conditional PASS；条件是保留预算偏差披露及原始 Web JSON，
不得重新归类为协议合规实验。上述条件已满足，无剩余文档阻断。
