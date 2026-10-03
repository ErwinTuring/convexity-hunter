# 本机工作台：运行记录与页面外壳

本阶段提供独立于 Codex 的本机 HTTP/CLI 外壳，不等于三入口真实研究已经接通。
研究执行器尚未安装时，提交 World、Event 或 Direct 都必须留下
`BLOCKED / HOST_EXECUTOR_NOT_CONFIGURED`，不能展示为研究成功或没有机会。

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

选择 World、Event 或 Direct，输入原始研究意图，并明确填写五项操作预算：
`max_submissions`、`max_hypotheses`、`max_browser_rows`、`max_cases`、
`quote_timeout_seconds`。这些是工作量上限，不是经济评分或结构推荐。
批准的 Standard Research Profile 只读展示；页面不生成新的风险政策。

## 结果与历史

每次提交创建独立运行记录。历史页读取已有记录，不自动重新调用模型、搜索或行情。
诊断与中断状态应如实显示。未来接入结构化 Core cases 后，单个 case 才能按需展开详情；
当前缺少该结果时，详情接口明确返回不可用，而不是生成模拟研究报告。

本阶段不调用模型、来源或市场服务，也不解除 World/Event 的 Grounder 阻断。
下一阶段才将已实现的 Core 执行路径接入这个外壳，保留相同证据与分类边界。
