# 本机 Direct 结构化输入 v0.1

输入适配器与可显式启用的工作台 Direct 执行器已实现。
真实 provider 运行条件与验收结果以 current checkpoint 为准；代码通过测试不等于行情一定可取得。

最小接入先使用确定性的 JSON，而不是让模型猜测 exact structure。
所有字段必须明确提供，不接受未知字段、重复键、非有限数、Markdown 包裹或省略后补默认值。

```json
{
  "schema_version": "host-direct-input-v0.1",
  "evaluation_date": "2026-10-03",
  "structure": "LONG_STRADDLE",
  "legs": [
    {
      "provider_identifier": "US.AMZN261120C255000",
      "underlying": "AMZN",
      "currency": "USD",
      "option_type": "CALL",
      "strike": "255",
      "expiration": "2026-11-20",
      "quantity": 1,
      "contract_multiplier": 100
    },
    {
      "provider_identifier": "US.AMZN261120P255000",
      "underlying": "AMZN",
      "currency": "USD",
      "option_type": "PUT",
      "strike": "255",
      "expiration": "2026-11-20",
      "quantity": 1,
      "contract_multiplier": 100
    }
  ]
}
```

这是输入格式示例，不是已执行案例、当前有效报价或推荐。数量与乘数是调用者
明确声明的预期合约条款；只有后续 provider exact verification 匹配时才能用于研究。
不默认乘数为 100。价格不允许从输入提供；必须经过既有报价证据路径。

支持 `LONG_CALL`、`LONG_PUT`、同执行价同到期日的 `LONG_STRADDLE`。
日期使用严格 ISO 日期，strike 使用十进制字符串，数量与乘数使用正整数且拒绝 Boolean。
操作预算另由调用者明确传入。批准的 Standard Research Profile 与中性期限政策不变；
没有 cost ledger 或 sensitivity 时保留既有缺口，不填零、不借输入绕过证据门槛。

输入适配器必须调用已有 `run_direct_core`。Exact identifier、underlying、Call/Put、
strike、expiration、multiplier 仍由原有 exact verification 检查。
`NEUTRAL_STRUCTURAL_RESEARCH / NOT_ESTABLISHED` 不升级为期限匹配或推荐。
这个工作单元不添加 provider、不改变 Kernel，也不调用模型。
