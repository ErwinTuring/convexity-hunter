# 本机工作台与 Direct 接入

本机 HTTP/CLI 和 Direct 执行器可独立于 Codex 运行，不等于三入口真实研究已经接通。
默认没有研究执行器；未配置的入口必须留下
`BLOCKED / HOST_EXECUTOR_NOT_CONFIGURED`，不能展示为研究成功或没有机会。
默认 CLI 的 World/Event 尚未接入真实来源，页面保持禁用；Direct 需显式启用。

批量交付层现已支持本机程序显式注入可信 World/Event 回调，保存所有案例并
默认显示完整 compact comparison；这不等于默认 CLI 已配置真实来源。
Grounder 未通过真实验收前，不添加一键启用或合成生产默认值。接口与存档
边界见 [批量交付说明](local-batch-delivery-v0.1.md)。

## 启动与输入

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
