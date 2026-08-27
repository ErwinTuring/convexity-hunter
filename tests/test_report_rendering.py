"""Tests for deterministic bilingual candidate Markdown rendering."""

import ast
import datetime
import dataclasses
import decimal
import hashlib
import inspect
import os
import pathlib
import subprocess
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from examples.sample_candidate_report import build_synthetic_candidate
from convexity_hunter.evidence import (
    CandidateState,
    ClassifiedEvidence,
    EvidenceImpact,
    EvidenceKind,
    OptionLeg,
    OptionStructure,
)
from convexity_hunter.option_chain_discovery import OptionResearchMaturityContext
from convexity_hunter.market_data_transformations import ExactRational
from convexity_hunter.market_data import CalculationQualityFlag
from convexity_hunter.report import (
    SCREENING_REASON_PRESENTATION,
    CandidateResearchRecord,
    _append_overview,
    _append_plan_structure,
    _canonical_decimal_text,
    _decimal_percentage_text,
    _format_plan_threshold,
    _rational_percentage_text,
    _render_plan_technical_block,
    _safe_fenced_lines,
    _technical_body,
    render_candidate_markdown,
)
from convexity_hunter import position_management
from convexity_hunter import report as report_module
from convexity_hunter import candidate_assembly
from convexity_hunter.candidate_assembly import assemble_candidate_research_record
from convexity_hunter.scanner import (
    DATA_INSUFFICIENT_REASON_ORDER,
    INVESTIGATE_REASON_ORDER,
    REJECT_REASON_ORDER,
    WATCH_REASON_ORDER,
    ScreeningDecision,
    ScreeningPolicy,
    ScreeningReasonCode,
    screen_candidate,
)
from test_position_management import _two_leg_assembly, _watch_result

INVESTIGATE_PLAN_MARKDOWN_GOLDEN = """# Convexity Hunter 候选研究报告

## 通俗概要：先看懂这份报告

### 1. 研究的是什么？

本报告研究的是：同时买入相同执行价和到期日的看涨期权与看跌期权。它不需要提前押注上涨或下跌，但标的需要在持有期间出现足够大的波动，才可能覆盖期权费、时间损耗和交易成本。

- **标的:** SPY
- **结构类型:** 买入跨式（long_straddle）
- **执行价:** $100.00
- **到期日:** 2030-03-03
- **预计持有天数:** 14

### 2. 两种状态分别代表什么？

- **研究记录状态:** 深入研究（investigate）
- **研究记录状态理由:** reviewed complete artifacts
- **确定性筛选建议状态:** 深入研究（investigate）
- **筛选政策 ID:** golden-screening
- **筛选政策版本:** v1
- **确定性理由码:**
  - 所有成本承受能力条件均已通过（`affordability_gates_passed`）
  - 所有流动性条件均已通过（`liquidity_gates_passed`）
  - 整体波动率环境通过政策支持条件（`volatility_environment_supportive`）
  - 与结构相关的尾部定价通过政策支持条件（`tail_pricing_supportive`）
  - 所有政策要求的目标变动情景在扣除成本后均盈利（`target_move_scenarios_profitable`）

该候选通过了暂定的确定性门槛，可能值得进一步人工研究。这并不能证明该结构价格便宜或适合交易。

研究记录状态随候选记录一同提供，可能反映样例、分析人员或工作流程中的判断。确定性筛选建议状态由指定政策独立计算，不会修改研究记录。两种状态都不是交易建议。

### 3. 为什么可能值得关注？

- Synthetic reviewed evidence

### 4. 为什么仍然需要谨慎？

**不利或弱化证据**

目前没有已报告的弱化证据。

**尚未提供的数据**

目前没有已报告的缺失数据。

### 5. 最多可能损失多少？

对于当前 MVP 支持的只买入期权结构，已声明的最大模型损失等于总入场成本。

- **总入场成本:** $401.25
- **最大损失:** $401.25
- **最大损失占组合比例:** 0.40%
- **重复尝试次数:** 1
- **累计重复尝试成本:** $401.25
- **累计重复尝试成本占比:** 0.40%

### 6. 在给定情景下，结果可能怎样？

在已提供的情景中：4 个盈利、0 个亏损、0 个盈亏为零。

已提供情景中的最高结果：到期（expiration）；标的变动 10.00%；IV 变动 50.00%；扣除成本后盈亏 $598.75。

已提供情景中的最低结果：持有期末（holding_horizon）；标的变动 -5.00%；IV 变动 -10.00%；扣除成本后盈亏 $96.25。

这里只比较报告中已提供的情景，不代表所有可能结果，也不是收益预测。

### 7. 接下来需要人工核实什么？

**人工复核问题**

1. what changes the conclusion?

**可能推翻研究假设的证伪条件**

1. contrary evidence

### 8. 未来条件声明（仅供后续人工判断）

研究记录状态、确定性筛选建议状态和未来条件声明是三类分开的信息。未来条件声明只描述未来可能需要重新判断的条件；当前未评估这些条件是否已经满足，不构成交易指令，也不表示已经存在或持有该仓位，仅供后续人工判断。
- **研究记录状态：** 深入研究（`investigate`）
- **确定性筛选建议状态：** 深入研究（`investigate`）
- **计划范围：** 前瞻性研究指导（`prospective_research_guidance`）

未来净清算价值倍数是未来扣除退出成本后的净清算价值除以精确复核的总入场成本；它不是 M4 到期毛仓位价值倍数、情景估算仓位价值倍数或扣除成本后盈亏倍数。M4 的 1×、2×、5×、10×证据不会自动成为本条件。

#### 考虑货币化（`monetization`）

- 若未来“未来平值隐含波动率（ATM IV）”小于或等于 Decimal("0.4")（40.00%)，则考虑货币化（条件 ID：`atm_iv`）；当前未评估该条件是否已经满足。
- 若未来发生“事件公开”，则考虑货币化（条件 ID：`event_public`）；当前未评估该条件是否已经满足。
- 若未来“未来净清算价值倍数”大于或等于 Decimal("2.5")（2.5×），则考虑货币化（条件 ID：`nlv_multiple`）；当前未评估该条件是否已经满足。
- 若未来发生“低估定价证据消失”，则考虑货币化（条件 ID：`underpricing_disappears`）；当前未评估该条件是否已经满足。

#### 考虑重新评估（`reassessment`）

- 若未来“剩余到期日天数”小于或等于 59 个日历日，则考虑重新评估（条件 ID：`dte_remaining`）；当前未评估该条件是否已经满足。
- 若未来发生“合约发生调整”，则考虑重新评估（条件 ID：`event_contract`）；当前未评估该条件是否已经满足。
- 若未来发生“影响路径发生重大变化”，则考虑重新评估（条件 ID：`event_impact`）；当前未评估该条件是否已经满足。
- 若未来发生“事件窗口发生变化”，则考虑重新评估（条件 ID：`event_shift`）；当前未评估该条件是否已经满足。
- 若未来发生“证据过时或缺失”，则考虑重新评估（条件 ID：`evidence_stale`）；当前未评估该条件是否已经满足。
- 若未来“重复最大损失比例”大于或等于 ExactRational(1, 50)（2.00%），则考虑重新评估（条件 ID：`repeated_loss`）；当前未评估该条件是否已经满足。
- 若未来“单次最大损失比例”大于或等于 ExactRational(1, 100)（1.00%），则考虑重新评估（条件 ID：`single_loss`）；当前未评估该条件是否已经满足。
- 若未来“未来结构到期日偏斜历史百分位”大于或等于 Decimal("0.5")（50.00%)，则考虑重新评估（条件 ID：`skew_percentile`）；当前未评估该条件是否已经满足。
- 若未来“未来买卖价差占报价中点的比例”大于或等于 Decimal("0.125")（12.50%)，则考虑重新评估（条件 ID：`spread_fraction`）；当前未评估该条件是否已经满足。

#### 考虑退出（`exit`）

- 若未来发生“数据丢失，无法负责地评估”，则考虑退出（条件 ID：`data_loss`）；当前未评估该条件是否已经满足。
- 若未来发生“事件取消”，则考虑退出（条件 ID：`event_cancelled`）；当前未评估该条件是否已经满足。
- 若未来发生“确定性的相反结论”，则考虑退出（条件 ID：`event_contrary`）；当前未评估该条件是否已经满足。
- 若未来发生“豁免得到确认”，则考虑退出（条件 ID：`event_exemption`）；当前未评估该条件是否已经满足。
- 若未来发生“事件窗口结束但假设的变化未发生”，则考虑退出（条件 ID：`event_expired`）；当前未评估该条件是否已经满足。
- 若未来发生“影响路径失效”，则考虑退出（条件 ID：`event_invalidated`）；当前未评估该条件是否已经满足。
- 若未来发生“修订后的事件窗口不在覆盖范围内”，则考虑退出（条件 ID：`event_uncovered`）；当前未评估该条件是否已经满足。

该计划不会监控、提醒、安排评估或执行任何动作。

---

## 技术研究明细

- **候选 ID:** candidate-complete
- **研究记录状态:** 深入研究（investigate）
- **研究记录状态理由:** reviewed complete artifacts
- **数据截至日期:** 2030-01-02
- **标的:** SPY
- **结构类型:** 买入跨式（long_straddle）
- **到期日:** 2030-03-03
- **预计持有天数:** 14

### 确定性筛选决策

- **确定性筛选建议状态:** 深入研究（investigate）
- **筛选政策 ID:** golden-screening
- **筛选政策版本:** v1
- **确定性理由码:**
  - 所有成本承受能力条件均已通过（`affordability_gates_passed`）
  - 所有流动性条件均已通过（`liquidity_gates_passed`）
  - 整体波动率环境通过政策支持条件（`volatility_environment_supportive`）
  - 与结构相关的尾部定价通过政策支持条件（`tail_pricing_supportive`）
  - 所有政策要求的目标变动情景在扣除成本后均盈利（`target_move_scenarios_profitable`）

该候选通过了暂定的确定性门槛，可能值得进一步人工研究。这并不能证明该结构价格便宜或适合交易。

该决策独立于已提供的研究记录状态，不会修改 CandidateResearchRecord。

### 未来条件声明技术明细

- **计划范围：** 前瞻性研究指导（`prospective_research_guidance`）
- **计划候选 ID：**
```
candidate-complete
```
- **计划研究记录状态：** 深入研究（`investigate`）
- **计划数据截至日期：** `2030-01-02`
- **计划结构：**
- **结构类型：** 买入跨式（`long_straddle`）
- **结构标的：**
```
SPY
```
- **假设组合价值：** $100,000.00
- **预计持有天数：** 14
- **共同到期日：** `2030-03-03`
- **期权腿 1：** 看涨（`call`）
- **期权腿 1 标的：**
```
SPY
```
- **期权腿 1 执行价：** $100.00
- **期权腿 1 到期日：** `2030-03-03`
- **期权腿 1 数量：** 1
- **期权腿 1 合约乘数：** 100
- **期权腿 2：** 看跌（`put`）
- **期权腿 2 标的：**
```
SPY
```
- **期权腿 2 执行价：** $100.00
- **期权腿 2 到期日：** `2030-03-03`
- **期权腿 2 数量：** 1
- **期权腿 2 合约乘数：** 100
- **计划计算 ID：**
```
plan-report-investigate
```
- **计算类型：** `position_management_plan`
- **方法 ID：** `prospective-human-judgment-position-management-plan`
- **方法版本：** `v0.1`
- **计算时间（UTC）：** `2030-01-02T15:30:35.000000Z`
- **候选组装计算 ID：**
```
assembly-complete
```
- **候选组装计算类型：** `candidate_research_record_assembly`
- **候选组装方法 ID：** `reviewed-artifact-candidate-research-record-assembly`
- **候选组装方法版本：** `v0.1`
- **质量标记：** `decimal_to_float_converted`、`annualized`、`assumption_applied`

#### 考虑货币化（`monetization`）

- **条件 ID：** `atm_iv`
- **条件类别：** 考虑货币化（`monetization`）
- **条件类型：** 定量（`quantitative`）
- **指标：** 未来平值隐含波动率（ATM IV）（`atm_iv`）
- **比较：** 小于或等于（`less_than_or_equal`）
- **阈值：** Decimal("0.4")（40.00%)
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `event_public`
- **条件类别：** 考虑货币化（`monetization`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 事件公开（`event_becomes_public`）
- **权威：** 调用方（`caller`）
- **来源引用：**
````
source```
reference
````
- **理由：**
`````
rationale````
with delimiter
`````

- **条件 ID：** `nlv_multiple`
- **条件类别：** 考虑货币化（`monetization`）
- **条件类型：** 定量（`quantitative`）
- **指标：** 未来净清算价值倍数（`net_liquidation_value_multiple`）
- **比较：** 大于或等于（`greater_than_or_equal`）
- **阈值：** Decimal("2.5")（2.5×）
- **权威：** 人工分析员（`human_analyst`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `underpricing_disappears`
- **条件类别：** 考虑货币化（`monetization`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 低估定价证据消失（`underpricing_evidence_disappears`）
- **权威：** 人工分析员（`human_analyst`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

#### 考虑重新评估（`reassessment`）

- **条件 ID：** `dte_remaining`
- **条件类别：** 考虑重新评估（`reassessment`）
- **条件类型：** 定量（`quantitative`）
- **指标：** 剩余到期日天数（`remaining_dte`）
- **比较：** 小于或等于（`less_than_or_equal`）
- **阈值：** 59 个日历日
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `event_contract`
- **条件类别：** 考虑重新评估（`reassessment`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 合约发生调整（`contract_adjusted`）
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `event_impact`
- **条件类别：** 考虑重新评估（`reassessment`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 影响路径发生重大变化（`impact_path_materially_changes`）
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `event_shift`
- **条件类别：** 考虑重新评估（`reassessment`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 事件窗口发生变化（`event_window_shifts`）
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `evidence_stale`
- **条件类别：** 考虑重新评估（`reassessment`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 证据过时或缺失（`evidence_stale_or_missing`）
- **权威：** 人工分析员（`human_analyst`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `repeated_loss`
- **条件类别：** 考虑重新评估（`reassessment`）
- **条件类型：** 定量（`quantitative`）
- **指标：** 重复最大损失比例（`repeated_loss_fraction`）
- **比较：** 大于或等于（`greater_than_or_equal`）
- **阈值：** ExactRational(1, 50)（2.00%）
- **权威：** 经审阅证据（`reviewed_artifact`）
- **来源引用：**
```
affordability-two-leg
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `single_loss`
- **条件类别：** 考虑重新评估（`reassessment`）
- **条件类型：** 定量（`quantitative`）
- **指标：** 单次最大损失比例（`single_loss_fraction`）
- **比较：** 大于或等于（`greater_than_or_equal`）
- **阈值：** ExactRational(1, 100)（1.00%）
- **权威：** 经审阅证据（`reviewed_artifact`）
- **来源引用：**
```
affordability-two-leg
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `skew_percentile`
- **条件类别：** 考虑重新评估（`reassessment`）
- **条件类型：** 定量（`quantitative`）
- **指标：** 未来结构到期日偏斜历史百分位（`skew_percentile`）
- **比较：** 大于或等于（`greater_than_or_equal`）
- **阈值：** Decimal("0.5")（50.00%)
- **权威：** 人工分析员（`human_analyst`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `spread_fraction`
- **条件类别：** 考虑重新评估（`reassessment`）
- **条件类型：** 定量（`quantitative`）
- **指标：** 未来买卖价差占报价中点的比例（`bid_ask_spread_fraction`）
- **比较：** 大于或等于（`greater_than_or_equal`）
- **阈值：** Decimal("0.125")（12.50%)
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

#### 考虑退出（`exit`）

- **条件 ID：** `data_loss`
- **条件类别：** 考虑退出（`exit`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 数据丢失，无法负责地评估（`data_loss_prevents_responsible_evaluation`）
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `event_cancelled`
- **条件类别：** 考虑退出（`exit`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 事件取消（`event_cancelled`）
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `event_contrary`
- **条件类别：** 考虑退出（`exit`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 确定性的相反结论（`definitive_contrary_resolution`）
- **权威：** 人工分析员（`human_analyst`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `event_exemption`
- **条件类别：** 考虑退出（`exit`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 豁免得到确认（`exemption_confirmed`）
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `event_expired`
- **条件类别：** 考虑退出（`exit`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 事件窗口结束但假设的变化未发生（`event_window_expires_without_hypothesized_change`）
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `event_invalidated`
- **条件类别：** 考虑退出（`exit`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 影响路径失效（`impact_path_invalidated`）
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

- **条件 ID：** `event_uncovered`
- **条件类别：** 考虑退出（`exit`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 修订后的事件窗口不在覆盖范围内（`revised_event_window_not_covered`）
- **权威：** 调用方（`caller`）
- **来源引用：**
```
golden source
```
- **理由：**
```
golden rationale
```

### 研究假设

testable convexity hypothesis

### 具体期权结构

| 期权腿 | 类型 | 执行价 | 到期日 | 数量 | 合约乘数 |
| ---: | --- | ---: | --- | ---: | ---: |
| 1 | 看涨（call） | $100.00 | 2030-03-03 | 1 | 100 |
| 2 | 看跌（put） | $100.00 | 2030-03-03 | 1 | 100 |

### 有限损失与成本

- **假设组合价值:** $100,000.00
- **报价中点权利金:** $350.00
- **预估买卖价差成本:** $50.00
- **佣金与费用:** $1.25
- **总入场成本:** $401.25
- **最大损失:** $401.25
- **最大损失占组合比例:** 0.40%
- **重复尝试次数:** 1
- **累计重复尝试成本:** $401.25
- **累计重复尝试成本占比:** 0.40%
- **每日 Theta:** -$25.00
- **总仓位 Gamma:** 5
- **标的变动 1% 的局部 Gamma 盈亏:** $2.50
- **标的变动 1% 的局部 Gamma 成本比:** 0.71%
- **希腊字母方法说明:** model=Synthetic Black-Scholes;model_version=fixture-v1;rate_input=Synthetic USD curve input;dividend_input=Synthetic dividend input;theta_day_basis=Provider calendar-day convention;unit_convention=Contract-defined canonical units

### 流动性

- **总仓位买价:** $300.00
- **总仓位卖价:** $400.00
- **报价中点:** $350.00
- **绝对买卖价差:** $100.00
- **买卖价差百分比:** 28.57%
- **各腿最小未平仓量:** 70
- **各腿最小当日成交量:** 30
- **报价方法:** exact selected option quotes scaled by quantity and contract multiplier

### 第一层——整体波动率定价环境

- **参考期限:** 30 天
- **平值隐含波动率（ATM IV）:** 30.00%
- **隐含波动率历史百分位:** 100.00%
- **IV 历史观测数:** 3
- **历史平值隐含波动率中位数:** 21.00%
- **ATM IV 减历史中位数:** 9.00%
- **匹配期限实现波动率:** 33.29%
- **实现波动率匹配窗口:** 30 天
- **隐含波动率与实现波动率差:** -3.29%

| 期限天数 | 平值隐含波动率（ATM IV） |
| ---: | ---: |
| 30 | 30.00% |
| 60 | 40.00% |

### 第二层——尾部相对定价

| 到期日 | 距到期天数 | ATM IV | 25Δ 看跌 IV | 25Δ 看涨 IV | 下行 25Δ 偏斜 | 上行 25Δ 偏斜 | 下行翼曲率 | 上行翼曲率 | 偏斜历史百分位 | 历史观测数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2030-02-01 | 30 | 30.00% | 36.00% | 28.00% | 6.00% | -2.00% | 6.00% | -2.00% | 66.67% | 3 |
| 2030-03-03 | 60 | 40.00% | 46.00% | 38.00% | 6.00% | -2.00% | 6.00% | -2.00% | 66.67% | 3 |

- **2030-02-01 Delta 方法:** {"$map":[["delta_basis","spot"],["interpolation_methodology","none"],["model_provider_methodology","Synthetic Black-Scholes provider delta"],["premium_adjustment","unadjusted"],["signed_delta_convention","call_positive_put_negative"],["target_selection_methodology","nearest_observed_signed_delta"]]}
- **2030-03-03 Delta 方法:** {"$map":[["delta_basis","spot"],["interpolation_methodology","none"],["model_provider_methodology","Synthetic Black-Scholes provider delta"],["premium_adjustment","unadjusted"],["signed_delta_convention","call_positive_put_negative"],["target_selection_methodology","nearest_observed_signed_delta"]]}

### 情景分析

| 估值时间 | 估值日期 | 标的变动 | IV 变动 | 变动后标的价格 | 基础 IV | 变动后 IV | 仓位价值 | 退出成本 | 净清算价值 | 扣除成本后盈亏 | 入场成本回报率 |
| --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 即时（immediate） | 2030-01-02 | 0.00% | 0.00% | $100.00 | 看涨（call）: 20.00%; 看跌（put）: 30.00% | 看涨（call）: 20.00%; 看跌（put）: 30.00% | $600.00 | $2.50 | $597.50 | $196.25 | 48.91% |
| 未来指定日期（days_forward） | 2030-01-09 | 10.00% | 20.00% | $110.00 | 看涨（call）: 20.00%; 看跌（put）: 30.00% | 看涨（call）: 24.00%; 看跌（put）: 36.00% | $700.00 | $2.50 | $697.50 | $296.25 | 73.83% |
| 持有期末（holding_horizon） | 2030-01-16 | -5.00% | -10.00% | $95.00 | 看涨（call）: 20.00%; 看跌（put）: 30.00% | 看涨（call）: 18.00%; 看跌（put）: 27.00% | $500.00 | $2.50 | $497.50 | $96.25 | 23.99% |
| 到期（expiration） | 2030-03-03 | 10.00% | 50.00% | $110.00 | 看涨（call）: 20.00%; 看跌（put）: 30.00% | 看涨（call）: 30.00%; 看跌（put）: 45.00% | $1,000.00 | $0.00 | $1,000.00 | $598.75 | 149.22% |

- **定价方法:** {"$map":[["base_iv_source","ScenarioPricing_v0.1_actual_structure_leg_iv_evidence"],["base_underlying_source","StructureCosts_v0.2_underlying_price_exact"],["entry_cost_rule","StructureCosts_v0.2_stable_total_entry_cost_float"],["exit_cost_rule",{"$map":[["methodology","explicit_fixture_exit_cost_v0.1"],["source","explicit_scenario_specific_decimal_假设（assumption）"]]}],["expiration_rule",{"$map":[["active",false],["call_formula","max(shocked_underlying-strike,0)*quantity*multiplier"],["external_expiration_value","prohibited"],["iv_effect","none_base_leg_ivs_retained_for_audit"],["put_formula","max(strike-shocked_underlying,0)*quantity*multiplier"]]}],["float_conversion_rule","convert_base_iv_gross_and_exit_cost_once_to_finite_float"],["limitations","Internal consistency is validated; self-consistent fabricated dependency artifacts are not cryptographically authenticated."],["nonexpiration_rule",{"$map":[["active",true],["rule","consume_authoritative_gross_value_without_repricing"]]}],["provider_disclosure",{"$map":[["calculation_id","scenario-pricing-calculation-001"],["dividend_methodology",{"$map":[["dividend_coverage_end_date",{"$date":"2030-03-15"}],["dividend_coverage_start_date",{"$date":"2030-01-02"}],["dividend_source","explicit_zero_dividend_假设（assumption）"],["dividend_treatment","explicit_zero_dividend_假设（assumption）"],["explicit_zero_dividend_假设（assumption）",true]]}],["interpolation_treatment","none"],["numerical_boundary","provider option values; local validation only"],["payload_sha256","bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],["position_scaling_rule","per_underlying_unit_value_times_quantity_times_contract_multiplier"],["pricing_model_name","Synthetic disclosed option model"],["pricing_model_version","model-v2"],["producer_calculated_at",{"$datetime":"2030-01-02T15:30:05.000000Z"}],["producer_name","Synthetic Scenario Provider"],["producer_version","provider-v3"],["rate_methodology",{"$map":[["rate_compounding_conversion","continuous equivalent"],["rate_currency","USD"],["rate_curve_identity","synthetic-usd-curve-20300102"],["rate_day_count_convention","actual_365"],["rate_effective_date",{"$date":"2030-01-02"}],["rate_interpolation","none"],["rate_remaining_tenor_treatment","remaining calendar tenor"],["rate_source","Synthetic USD curve"]]}],["remaining_time_rule","expiration_minus_valuation_date_calendar_days"],["request_id","scenario-request-001"],["settlement_treatment","physical settlement at declared terms"],["skew_treatment","preserve leg-level base differences"],["status","active_authoritative_provider_calculated"],["surface_treatment","actual leg IV parallel shock"],["term_treatment","remaining tenor per scenario"]]}],["scenario_identity",{"$map":[["days_forward",0],["iv_change",{"$decimal":"0.0"}],["underlying_move",{"$decimal":"0.0"}],["valuation_time","immediate"]]}],["scenario_pricing_dependency",{"$map":[["calculation_id","scenario-pricing-calculation-001"],["identity",{"$list":["nonexpiration_scenario_pricing","authoritative-provider-option-scenario-pricing-evidence","v0.1"]}]]}],["schema_version","v0.1"],["structure_costs_dependency",{"$map":[["calculation_id","scenario-valuation-costs"],["identity",{"$list":["structure_costs","exact-structure-costs","v0.2"]}]]}],["tail_pricing_dependency",{"$map":[["calculation_id","calculation-3c7e"],["identity",{"$list":["tail_pricing","nearest-observed-delta-wing-tail-relative-pricing","v0.2"]}],["use","context_only"]]}],["valuation_source","authoritative_provider_nonexpiration"]]}
- **定价方法:** {"$map":[["base_iv_source","ScenarioPricing_v0.1_actual_structure_leg_iv_evidence"],["base_underlying_source","StructureCosts_v0.2_underlying_price_exact"],["entry_cost_rule","StructureCosts_v0.2_stable_total_entry_cost_float"],["exit_cost_rule",{"$map":[["methodology","explicit_fixture_exit_cost_v0.1"],["source","explicit_scenario_specific_decimal_假设（assumption）"]]}],["expiration_rule",{"$map":[["active",false],["call_formula","max(shocked_underlying-strike,0)*quantity*multiplier"],["external_expiration_value","prohibited"],["iv_effect","none_base_leg_ivs_retained_for_audit"],["put_formula","max(strike-shocked_underlying,0)*quantity*multiplier"]]}],["float_conversion_rule","convert_base_iv_gross_and_exit_cost_once_to_finite_float"],["limitations","Internal consistency is validated; self-consistent fabricated dependency artifacts are not cryptographically authenticated."],["nonexpiration_rule",{"$map":[["active",true],["rule","consume_authoritative_gross_value_without_repricing"]]}],["provider_disclosure",{"$map":[["calculation_id","scenario-pricing-calculation-001"],["dividend_methodology",{"$map":[["dividend_coverage_end_date",{"$date":"2030-03-15"}],["dividend_coverage_start_date",{"$date":"2030-01-02"}],["dividend_source","explicit_zero_dividend_假设（assumption）"],["dividend_treatment","explicit_zero_dividend_假设（assumption）"],["explicit_zero_dividend_假设（assumption）",true]]}],["interpolation_treatment","none"],["numerical_boundary","provider option values; local validation only"],["payload_sha256","bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],["position_scaling_rule","per_underlying_unit_value_times_quantity_times_contract_multiplier"],["pricing_model_name","Synthetic disclosed option model"],["pricing_model_version","model-v2"],["producer_calculated_at",{"$datetime":"2030-01-02T15:30:05.000000Z"}],["producer_name","Synthetic Scenario Provider"],["producer_version","provider-v3"],["rate_methodology",{"$map":[["rate_compounding_conversion","continuous equivalent"],["rate_currency","USD"],["rate_curve_identity","synthetic-usd-curve-20300102"],["rate_day_count_convention","actual_365"],["rate_effective_date",{"$date":"2030-01-02"}],["rate_interpolation","none"],["rate_remaining_tenor_treatment","remaining calendar tenor"],["rate_source","Synthetic USD curve"]]}],["remaining_time_rule","expiration_minus_valuation_date_calendar_days"],["request_id","scenario-request-001"],["settlement_treatment","physical settlement at declared terms"],["skew_treatment","preserve leg-level base differences"],["status","active_authoritative_provider_calculated"],["surface_treatment","actual leg IV parallel shock"],["term_treatment","remaining tenor per scenario"]]}],["scenario_identity",{"$map":[["days_forward",7],["iv_change",{"$decimal":"0.2"}],["underlying_move",{"$decimal":"0.1"}],["valuation_time","days_forward"]]}],["scenario_pricing_dependency",{"$map":[["calculation_id","scenario-pricing-calculation-001"],["identity",{"$list":["nonexpiration_scenario_pricing","authoritative-provider-option-scenario-pricing-evidence","v0.1"]}]]}],["schema_version","v0.1"],["structure_costs_dependency",{"$map":[["calculation_id","scenario-valuation-costs"],["identity",{"$list":["structure_costs","exact-structure-costs","v0.2"]}]]}],["tail_pricing_dependency",{"$map":[["calculation_id","calculation-3c7e"],["identity",{"$list":["tail_pricing","nearest-observed-delta-wing-tail-relative-pricing","v0.2"]}],["use","context_only"]]}],["valuation_source","authoritative_provider_nonexpiration"]]}
- **定价方法:** {"$map":[["base_iv_source","ScenarioPricing_v0.1_actual_structure_leg_iv_evidence"],["base_underlying_source","StructureCosts_v0.2_underlying_price_exact"],["entry_cost_rule","StructureCosts_v0.2_stable_total_entry_cost_float"],["exit_cost_rule",{"$map":[["methodology","explicit_fixture_exit_cost_v0.1"],["source","explicit_scenario_specific_decimal_假设（assumption）"]]}],["expiration_rule",{"$map":[["active",false],["call_formula","max(shocked_underlying-strike,0)*quantity*multiplier"],["external_expiration_value","prohibited"],["iv_effect","none_base_leg_ivs_retained_for_audit"],["put_formula","max(strike-shocked_underlying,0)*quantity*multiplier"]]}],["float_conversion_rule","convert_base_iv_gross_and_exit_cost_once_to_finite_float"],["limitations","Internal consistency is validated; self-consistent fabricated dependency artifacts are not cryptographically authenticated."],["nonexpiration_rule",{"$map":[["active",true],["rule","consume_authoritative_gross_value_without_repricing"]]}],["provider_disclosure",{"$map":[["calculation_id","scenario-pricing-calculation-001"],["dividend_methodology",{"$map":[["dividend_coverage_end_date",{"$date":"2030-03-15"}],["dividend_coverage_start_date",{"$date":"2030-01-02"}],["dividend_source","explicit_zero_dividend_假设（assumption）"],["dividend_treatment","explicit_zero_dividend_假设（assumption）"],["explicit_zero_dividend_假设（assumption）",true]]}],["interpolation_treatment","none"],["numerical_boundary","provider option values; local validation only"],["payload_sha256","bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],["position_scaling_rule","per_underlying_unit_value_times_quantity_times_contract_multiplier"],["pricing_model_name","Synthetic disclosed option model"],["pricing_model_version","model-v2"],["producer_calculated_at",{"$datetime":"2030-01-02T15:30:05.000000Z"}],["producer_name","Synthetic Scenario Provider"],["producer_version","provider-v3"],["rate_methodology",{"$map":[["rate_compounding_conversion","continuous equivalent"],["rate_currency","USD"],["rate_curve_identity","synthetic-usd-curve-20300102"],["rate_day_count_convention","actual_365"],["rate_effective_date",{"$date":"2030-01-02"}],["rate_interpolation","none"],["rate_remaining_tenor_treatment","remaining calendar tenor"],["rate_source","Synthetic USD curve"]]}],["remaining_time_rule","expiration_minus_valuation_date_calendar_days"],["request_id","scenario-request-001"],["settlement_treatment","physical settlement at declared terms"],["skew_treatment","preserve leg-level base differences"],["status","active_authoritative_provider_calculated"],["surface_treatment","actual leg IV parallel shock"],["term_treatment","remaining tenor per scenario"]]}],["scenario_identity",{"$map":[["days_forward",0],["iv_change",{"$decimal":"-0.1"}],["underlying_move",{"$decimal":"-0.05"}],["valuation_time","holding_horizon"]]}],["scenario_pricing_dependency",{"$map":[["calculation_id","scenario-pricing-calculation-001"],["identity",{"$list":["nonexpiration_scenario_pricing","authoritative-provider-option-scenario-pricing-evidence","v0.1"]}]]}],["schema_version","v0.1"],["structure_costs_dependency",{"$map":[["calculation_id","scenario-valuation-costs"],["identity",{"$list":["structure_costs","exact-structure-costs","v0.2"]}]]}],["tail_pricing_dependency",{"$map":[["calculation_id","calculation-3c7e"],["identity",{"$list":["tail_pricing","nearest-observed-delta-wing-tail-relative-pricing","v0.2"]}],["use","context_only"]]}],["valuation_source","authoritative_provider_nonexpiration"]]}
- **定价方法:** {"$map":[["base_iv_source","ScenarioPricing_v0.1_actual_structure_leg_iv_evidence"],["base_underlying_source","StructureCosts_v0.2_underlying_price_exact"],["entry_cost_rule","StructureCosts_v0.2_stable_total_entry_cost_float"],["exit_cost_rule",{"$map":[["methodology","explicit_fixture_exit_cost_v0.1"],["source","explicit_scenario_specific_decimal_假设（assumption）"]]}],["expiration_rule",{"$map":[["active",true],["call_formula","max(shocked_underlying-strike,0)*quantity*multiplier"],["external_expiration_value","prohibited"],["iv_effect","none_base_leg_ivs_retained_for_audit"],["put_formula","max(strike-shocked_underlying,0)*quantity*multiplier"]]}],["float_conversion_rule","convert_base_iv_gross_and_exit_cost_once_to_finite_float"],["limitations","Internal consistency is validated; self-consistent fabricated dependency artifacts are not cryptographically authenticated."],["nonexpiration_rule",{"$map":[["active",false],["rule","consume_authoritative_gross_value_without_repricing"]]}],["provider_disclosure",{"$map":[["external_expiration_value","prohibited"],["status","inactive_for_expiration"]]}],["scenario_identity",{"$map":[["days_forward",0],["iv_change",{"$decimal":"0.5"}],["underlying_move",{"$decimal":"0.1"}],["valuation_time","expiration"]]}],["scenario_pricing_dependency",{"$map":[["calculation_id","scenario-pricing-calculation-001"],["identity",{"$list":["nonexpiration_scenario_pricing","authoritative-provider-option-scenario-pricing-evidence","v0.1"]}]]}],["schema_version","v0.1"],["structure_costs_dependency",{"$map":[["calculation_id","scenario-valuation-costs"],["identity",{"$list":["structure_costs","exact-structure-costs","v0.2"]}]]}],["tail_pricing_dependency",{"$map":[["calculation_id","calculation-3c7e"],["identity",{"$list":["tail_pricing","nearest-observed-delta-wing-tail-relative-pricing","v0.2"]}],["use","context_only"]]}],["valuation_source","terminal_intrinsic_expiration"]]}

情景数值是已提供的研究结果，不是预期收益，也不是概率加权预测。

### 证据

#### 支持证据

- **证据 ID:** evidence-1
  - **证据类型:** 计算指标（calculated_metric）
  - **陈述:** Synthetic reviewed evidence
  - **来源:** synthetic fixture
  - **方法:** fixture-v1

#### 弱化证据

未报告。

#### 中性证据

未报告。

### 证伪条件

1. contrary evidence

### 缺失数据

未报告。

### 假阳性风险

- false-positive channel

### AI 解读

未提供。

### 人工复核问题

1. what changes the conclusion?

本记录用于整理研究证据，不推荐、不执行，也不保证任何交易或投资结果。
"""

WATCH_PLAN_MARKDOWN_GOLDEN = """# Convexity Hunter 候选研究报告

## 通俗概要：先看懂这份报告

### 1. 研究的是什么？

这份报告研究支付固定入场成本、获得非线性上涨敞口的买入看涨期权。如果标的在到期前上涨幅度不足，仓位可能损失已声明的全部入场成本。

- **标的:** SPY
- **结构类型:** 买入看涨（long_call）
- **执行价:** $100.00
- **到期日:** 2030-03-03
- **预计持有天数:** 14

### 2. 两种状态分别代表什么？

- **研究记录状态:** 观察（watch）
- **研究记录状态理由:** caller supplied state
- **确定性筛选建议状态:** 拒绝（reject）
- **筛选政策 ID:** golden-screening
- **筛选政策版本:** v1
- **确定性理由码:**
  - 最大损失超过政策硬性上限（`max_loss_hard_limit_exceeded`）
  - 累计重复尝试成本超过政策硬性上限（`repeated_bet_hard_limit_exceeded`）
  - 买卖价差超过政策硬性上限（`spread_hard_limit_exceeded`）
  - 期权腿最低未平仓量低于政策硬性下限（`open_interest_hard_minimum_failed`）
  - 期权腿最低当日成交量低于政策硬性下限（`daily_volume_hard_minimum_failed`）
  - 持有期 Theta 损耗负担超过政策硬性上限（`theta_burden_hard_limit_exceeded`）
  - 至少一个政策要求的目标变动情景在扣除成本后未盈利（`target_move_scenario_not_profitable`）

按照该政策，只要存在已知的硬性失败条件，就足以在本轮筛选中拒绝该候选。

研究记录状态随候选记录一同提供，可能反映样例、分析人员或工作流程中的判断。确定性筛选建议状态由指定政策独立计算，不会修改研究记录。两种状态都不是交易建议。

### 3. 为什么可能值得关注？

- Synthetic reviewed evidence

### 4. 为什么仍然需要谨慎？

**不利或弱化证据**

目前没有已报告的弱化证据。

**尚未提供的数据**

- artifacts pending

### 5. 最多可能损失多少？

未提供损失信息。

### 6. 在给定情景下，结果可能怎样？

未提供情景结果。

### 7. 接下来需要人工核实什么？

**人工复核问题**

1. what changes the conclusion?

**可能推翻研究假设的证伪条件**

1. contrary evidence

### 8. 未来条件声明（仅供后续人工判断）

研究记录状态、确定性筛选建议状态和未来条件声明是三类分开的信息。未来条件声明只描述未来可能需要重新判断的条件；当前未评估这些条件是否已经满足，不构成交易指令，也不表示已经存在或持有该仓位，仅供后续人工判断。
- **研究记录状态：** 观察（`watch`）
- **确定性筛选建议状态：** 拒绝（`reject`）
- **计划范围：** 前瞻性研究指导（`prospective_research_guidance`）

研究记录状态与确定性筛选建议状态不一致：研究记录状态为“观察”（`watch`），确定性筛选建议状态为“拒绝”（`reject`）。本节分别展示两者；确定性筛选建议不会修改研究记录状态。

#### 考虑货币化（`monetization`）

- 本 WATCH 计划未声明此类未来条件；报告不会从其他记录生成条件。

#### 考虑重新评估（`reassessment`）

- 若未来发生“事件窗口发生变化”，则考虑重新评估（条件 ID：`review_event`）；当前未评估该条件是否已经满足。

#### 考虑退出（`exit`）

- 本 WATCH 计划未声明此类未来条件；报告不会从其他记录生成条件。

该计划不会监控、提醒、安排评估或执行任何动作。

---

## 技术研究明细

- **候选 ID:** candidate-001
- **研究记录状态:** 观察（watch）
- **研究记录状态理由:** caller supplied state
- **数据截至日期:** 2030-01-02
- **标的:** SPY
- **结构类型:** 买入看涨（long_call）
- **到期日:** 2030-03-03
- **预计持有天数:** 14

### 确定性筛选决策

- **确定性筛选建议状态:** 拒绝（reject）
- **筛选政策 ID:** golden-screening
- **筛选政策版本:** v1
- **确定性理由码:**
  - 最大损失超过政策硬性上限（`max_loss_hard_limit_exceeded`）
  - 累计重复尝试成本超过政策硬性上限（`repeated_bet_hard_limit_exceeded`）
  - 买卖价差超过政策硬性上限（`spread_hard_limit_exceeded`）
  - 期权腿最低未平仓量低于政策硬性下限（`open_interest_hard_minimum_failed`）
  - 期权腿最低当日成交量低于政策硬性下限（`daily_volume_hard_minimum_failed`）
  - 持有期 Theta 损耗负担超过政策硬性上限（`theta_burden_hard_limit_exceeded`）
  - 至少一个政策要求的目标变动情景在扣除成本后未盈利（`target_move_scenario_not_profitable`）

按照该政策，只要存在已知的硬性失败条件，就足以在本轮筛选中拒绝该候选。

该决策独立于已提供的研究记录状态，不会修改 CandidateResearchRecord。

### 未来条件声明技术明细

- **计划范围：** 前瞻性研究指导（`prospective_research_guidance`）
- **计划候选 ID：**
```
candidate-001
```
- **计划研究记录状态：** 观察（`watch`）
- **计划数据截至日期：** `2030-01-02`
- **计划结构：**
- **结构类型：** 买入看涨（`long_call`）
- **结构标的：**
```
SPY
```
- **假设组合价值：** $100,000.00
- **预计持有天数：** 14
- **共同到期日：** `2030-03-03`
- **期权腿 1：** 看涨（`call`）
- **期权腿 1 标的：**
```
SPY
```
- **期权腿 1 执行价：** $100.00
- **期权腿 1 到期日：** `2030-03-03`
- **期权腿 1 数量：** 1
- **期权腿 1 合约乘数：** 100
- **计划计算 ID：**
```
plan-001
```
- **计算类型：** `position_management_plan`
- **方法 ID：** `prospective-human-judgment-position-management-plan`
- **方法版本：** `v0.1`
- **计算时间（UTC）：** `2030-01-02T15:30:01.000000Z`
- **候选组装计算 ID：**
```
assembly-001
```
- **候选组装计算类型：** `candidate_research_record_assembly`
- **候选组装方法 ID：** `reviewed-artifact-candidate-research-record-assembly`
- **候选组装方法版本：** `v0.1`
- **质量标记：** `incomplete_input_used`

#### 考虑货币化（`monetization`）

- 本 WATCH 计划未声明此类未来条件；报告不会从其他记录生成条件。

#### 考虑重新评估（`reassessment`）

- **条件 ID：** `review_event`
- **条件类别：** 考虑重新评估（`reassessment`）
- **条件类型：** 定性（`qualitative`）
- **触发条件：** 事件窗口发生变化（`event_window_shifts`）
- **权威：** 调用方（`caller`）
- **来源引用：**
```
source note
```
- **理由：**
```
rationale
```

#### 考虑退出（`exit`）

- 本 WATCH 计划未声明此类未来条件；报告不会从其他记录生成条件。

### 研究假设

testable convexity hypothesis

### 具体期权结构

| 期权腿 | 类型 | 执行价 | 到期日 | 数量 | 合约乘数 |
| ---: | --- | ---: | --- | ---: | ---: |
| 1 | 看涨（call） | $100.00 | 2030-03-03 | 1 | 100 |

### 有限损失与成本

未提供。

### 流动性

未提供。

### 第一层——整体波动率定价环境

未提供。

### 第二层——尾部相对定价

未提供。

### 情景分析

未提供。

情景数值是已提供的研究结果，不是预期收益，也不是概率加权预测。

### 证据

#### 支持证据

- **证据 ID:** evidence-1
  - **证据类型:** 计算指标（calculated_metric）
  - **陈述:** Synthetic reviewed evidence
  - **来源:** synthetic fixture
  - **方法:** fixture-v1

#### 弱化证据

未报告。

#### 中性证据

未报告。

### 证伪条件

1. contrary evidence

### 缺失数据

- artifacts pending

### 假阳性风险

- false-positive channel

### AI 解读

未提供。

### 人工复核问题

1. what changes the conclusion?

本记录用于整理研究证据，不推荐、不执行，也不保证任何交易或投资结果。
"""

PUT_FIRST_LONG_STRADDLE_STRUCTURE_GOLDEN = """- **结构类型：** 买入跨式（`long_straddle`）
- **结构标的：**
```
SPY
```
- **假设组合价值：** $100,000.00
- **预计持有天数：** 14
- **共同到期日：** `2030-03-03`
- **期权腿 1：** 看跌（`put`）
- **期权腿 1 标的：**
```
SPY
```
- **期权腿 1 执行价：** $100.00
- **期权腿 1 到期日：** `2030-03-03`
- **期权腿 1 数量：** 1
- **期权腿 1 合约乘数：** 100
- **期权腿 2：** 看涨（`call`）
- **期权腿 2 标的：**
```
SPY
```
- **期权腿 2 执行价：** $100.00
- **期权腿 2 到期日：** `2030-03-03`
- **期权腿 2 数量：** 1
- **期权腿 2 合约乘数：** 100
"""

LONG_PUT_STRUCTURE_GOLDEN = """- **结构类型：** 买入看跌（`long_put`）
- **结构标的：**
```
SPY
```
- **假设组合价值：** $100,000.00
- **预计持有天数：** 14
- **共同到期日：** `2030-03-03`
- **期权腿 1：** 看跌（`put`）
- **期权腿 1 标的：**
```
SPY
```
- **期权腿 1 执行价：** $100.00
- **期权腿 1 到期日：** `2030-03-03`
- **期权腿 1 数量：** 1
- **期权腿 1 合约乘数：** 100
"""


def _golden_quantitative(
    identifier,
    category,
    metric,
    comparison,
    threshold,
    authority,
    source="golden source",
    rationale="golden rationale",
):
    return position_management.QuantitativePositionManagementCondition(
        identifier,
        category,
        metric,
        comparison,
        threshold,
        authority,
        source,
        rationale,
    )


def _golden_qualitative(
    identifier,
    category,
    trigger,
    authority=position_management.PositionManagementAuthority.CALLER,
    source="golden source",
    rationale="golden rationale",
):
    return position_management.QualitativePositionManagementCondition(
        identifier, category, trigger, authority, source, rationale
    )


def build_complete_investigate_plan_result() -> object:
    assembly = _two_leg_assembly()
    pm = position_management
    affordability_id = assembly.structure_affordability_result.lineage.calculation_id
    conditions = (
        _golden_quantitative(
            "atm_iv",
            pm.PositionManagementCategory.MONETIZATION,
            pm.PositionManagementMetric.ATM_IV,
            pm.PositionManagementComparison.LESS_THAN_OR_EQUAL,
            decimal.Decimal("0.4"),
            pm.PositionManagementAuthority.CALLER,
        ),
        _golden_qualitative(
            "event_public",
            pm.PositionManagementCategory.MONETIZATION,
            pm.PositionManagementQualitativeTrigger.EVENT_BECOMES_PUBLIC,
            source="source```\r\nreference",
            rationale="rationale````\r\nwith delimiter",
        ),
        _golden_quantitative(
            "nlv_multiple",
            pm.PositionManagementCategory.MONETIZATION,
            pm.PositionManagementMetric.NET_LIQUIDATION_VALUE_MULTIPLE,
            pm.PositionManagementComparison.GREATER_THAN_OR_EQUAL,
            decimal.Decimal("2.5000"),
            pm.PositionManagementAuthority.HUMAN_ANALYST,
        ),
        _golden_qualitative(
            "underpricing_disappears",
            pm.PositionManagementCategory.MONETIZATION,
            pm.PositionManagementQualitativeTrigger.UNDERPRICING_EVIDENCE_DISAPPEARS,
            pm.PositionManagementAuthority.HUMAN_ANALYST,
        ),
        _golden_quantitative(
            "dte_remaining",
            pm.PositionManagementCategory.REASSESSMENT,
            pm.PositionManagementMetric.REMAINING_DTE,
            pm.PositionManagementComparison.LESS_THAN_OR_EQUAL,
            59,
            pm.PositionManagementAuthority.CALLER,
        ),
        _golden_qualitative(
            "event_contract",
            pm.PositionManagementCategory.REASSESSMENT,
            pm.PositionManagementQualitativeTrigger.CONTRACT_ADJUSTED,
        ),
        _golden_qualitative(
            "event_impact",
            pm.PositionManagementCategory.REASSESSMENT,
            pm.PositionManagementQualitativeTrigger.IMPACT_PATH_MATERIALLY_CHANGES,
        ),
        _golden_qualitative(
            "event_shift",
            pm.PositionManagementCategory.REASSESSMENT,
            pm.PositionManagementQualitativeTrigger.EVENT_WINDOW_SHIFTS,
        ),
        _golden_qualitative(
            "evidence_stale",
            pm.PositionManagementCategory.REASSESSMENT,
            pm.PositionManagementQualitativeTrigger.EVIDENCE_STALE_OR_MISSING,
            pm.PositionManagementAuthority.HUMAN_ANALYST,
        ),
        _golden_quantitative(
            "repeated_loss",
            pm.PositionManagementCategory.REASSESSMENT,
            pm.PositionManagementMetric.REPEATED_LOSS_FRACTION,
            pm.PositionManagementComparison.GREATER_THAN_OR_EQUAL,
            ExactRational(1, 50),
            pm.PositionManagementAuthority.REVIEWED_ARTIFACT,
            source=affordability_id,
        ),
        _golden_quantitative(
            "single_loss",
            pm.PositionManagementCategory.REASSESSMENT,
            pm.PositionManagementMetric.SINGLE_LOSS_FRACTION,
            pm.PositionManagementComparison.GREATER_THAN_OR_EQUAL,
            ExactRational(1, 100),
            pm.PositionManagementAuthority.REVIEWED_ARTIFACT,
            source=affordability_id,
        ),
        _golden_quantitative(
            "skew_percentile",
            pm.PositionManagementCategory.REASSESSMENT,
            pm.PositionManagementMetric.SKEW_PERCENTILE,
            pm.PositionManagementComparison.GREATER_THAN_OR_EQUAL,
            decimal.Decimal("0.5"),
            pm.PositionManagementAuthority.HUMAN_ANALYST,
        ),
        _golden_quantitative(
            "spread_fraction",
            pm.PositionManagementCategory.REASSESSMENT,
            pm.PositionManagementMetric.BID_ASK_SPREAD_FRACTION,
            pm.PositionManagementComparison.GREATER_THAN_OR_EQUAL,
            decimal.Decimal("0.125"),
            pm.PositionManagementAuthority.CALLER,
        ),
        _golden_qualitative(
            "data_loss",
            pm.PositionManagementCategory.EXIT,
            pm.PositionManagementQualitativeTrigger.DATA_LOSS_PREVENTS_RESPONSIBLE_EVALUATION,
        ),
        _golden_qualitative(
            "event_cancelled",
            pm.PositionManagementCategory.EXIT,
            pm.PositionManagementQualitativeTrigger.EVENT_CANCELLED,
        ),
        _golden_qualitative(
            "event_contrary",
            pm.PositionManagementCategory.EXIT,
            pm.PositionManagementQualitativeTrigger.DEFINITIVE_CONTRARY_RESOLUTION,
            pm.PositionManagementAuthority.HUMAN_ANALYST,
        ),
        _golden_qualitative(
            "event_exemption",
            pm.PositionManagementCategory.EXIT,
            pm.PositionManagementQualitativeTrigger.EXEMPTION_CONFIRMED,
        ),
        _golden_qualitative(
            "event_expired",
            pm.PositionManagementCategory.EXIT,
            pm.PositionManagementQualitativeTrigger.EVENT_WINDOW_EXPIRES_WITHOUT_HYPOTHESIZED_CHANGE,
        ),
        _golden_qualitative(
            "event_invalidated",
            pm.PositionManagementCategory.EXIT,
            pm.PositionManagementQualitativeTrigger.IMPACT_PATH_INVALIDATED,
        ),
        _golden_qualitative(
            "event_uncovered",
            pm.PositionManagementCategory.EXIT,
            pm.PositionManagementQualitativeTrigger.REVISED_EVENT_WINDOW_NOT_COVERED,
        ),
    )
    return pm.create_position_management_plan(
        "plan-report-investigate",
        assembly,
        conditions,
        assembly.lineage.calculated_at + datetime.timedelta(seconds=1),
    )


def build_minimal_watch() -> CandidateResearchRecord:
    expiration = datetime.date(2030, 6, 21)
    structure = OptionStructure(
        legs=(OptionLeg("SPY", "call", 500.0, expiration),),
        assumed_portfolio_value=100_000.0,
        expected_holding_days=7,
    )
    return CandidateResearchRecord(
        candidate_id="MINIMAL-WATCH-001",
        state=CandidateState.WATCH,
        state_rationale="Optional records are intentionally absent.",
        as_of_date=datetime.date(2030, 5, 1),
        hypothesis="The minimal renderer path should remain explicit.",
        structure=structure,
        evidence=(
            ClassifiedEvidence(
                "assumption-1",
                EvidenceKind.ASSUMPTION,
                EvidenceImpact.NEUTRAL,
                "Optional records are assumed unavailable.",
            ),
        ),
        falsification_conditions=("Optional data becomes available.",),
        false_positive_reasons=("The minimal record may omit decisive context.",),
        human_review_questions=("Which optional record should be added first?",),
    )


def _exact_candidate_clone(candidate, field_name=None, field_value=None):
    clone = object.__new__(CandidateResearchRecord)
    for field in dataclasses.fields(CandidateResearchRecord):
        value = field_value if field.name == field_name else getattr(candidate, field.name)
        object.__setattr__(clone, field.name, value)
    return clone


def _exact_dataclass_clone(value, **changes):
    clone = object.__new__(type(value))
    for field in dataclasses.fields(value):
        object.__setattr__(clone, field.name, changes.get(field.name, getattr(value, field.name)))
    return clone


def _partial_assembly(state=CandidateState.WATCH, *, candidate_id="candidate-authority", assembly_id="assembly-authority", structure=None):
    structure = structure or OptionStructure(
        (OptionLeg("SPY", "call", 100.0, datetime.date(2030, 3, 3)),), 100000.0, 14
    )
    return assemble_candidate_research_record(
        assembly_id, candidate_id, state, "caller supplied state", datetime.date(2030, 1, 2),
        "testable convexity hypothesis", structure, None, None, None, None, None, None, None,
        (ClassifiedEvidence("evidence-authority", EvidenceKind.CALCULATED_METRIC,
                            EvidenceImpact.SUPPORTS, "Synthetic reviewed evidence",
                            "synthetic fixture", "fixture-v1"),),
        ("contrary evidence",), ("artifacts pending",), ("false-positive channel",), None,
        ("what changes the conclusion?",), datetime.datetime(2030, 1, 2, 15, 30, tzinfo=datetime.timezone.utc),
    )


def _partial_watch_plan_result(*, candidate_id="candidate-authority", assembly_id="assembly-authority", plan_id="plan-authority", structure=None, condition=None):
    assembly = _partial_assembly(candidate_id=candidate_id, assembly_id=assembly_id, structure=structure)
    condition = condition or _golden_qualitative(
        "review_event", position_management.PositionManagementCategory.REASSESSMENT,
        position_management.PositionManagementQualitativeTrigger.EVENT_WINDOW_SHIFTS,
    )
    return position_management.create_position_management_plan(
        plan_id, assembly, (condition,), assembly.lineage.calculated_at + datetime.timedelta(seconds=1)
    )


def _screening_for_state(state):
    reasons = {
        CandidateState.REJECT: REJECT_REASON_ORDER,
        CandidateState.WATCH: WATCH_REASON_ORDER,
        CandidateState.INVESTIGATE: INVESTIGATE_REASON_ORDER,
        CandidateState.DATA_INSUFFICIENT: DATA_INSUFFICIENT_REASON_ORDER,
    }[state]
    return ScreeningDecision(state, reasons, "matrix-policy", "v1")


def economic_signature(candidate: CandidateResearchRecord) -> tuple:
    costs = candidate.costs
    liquidity = candidate.liquidity
    environment = candidate.volatility_environment
    return (
        candidate.candidate_id,
        candidate.state,
        candidate.as_of_date,
        candidate.structure,
        None if costs is None else (
            costs.as_of_date,
            costs.quoted_mid_premium,
            costs.estimated_spread_cost,
            costs.commissions_and_fees,
            costs.theta_per_day,
            costs.gamma,
            costs.underlying_price,
            costs.repeated_bet_count,
        ),
        None if liquidity is None else (
            liquidity.as_of_date,
            liquidity.quoted_bid_value,
            liquidity.quoted_ask_value,
            liquidity.minimum_leg_open_interest,
            liquidity.minimum_leg_daily_volume,
        ),
        None if environment is None else (
            environment.underlying,
            environment.as_of_date,
            environment.reference_tenor_days,
            environment.iv_percentile,
            environment.iv_history_lookback_observations,
            environment.historical_median_atm_iv,
            environment.matched_realized_volatility,
            environment.matched_realized_window_days,
            tuple((point.tenor_days, point.atm_iv) for point in environment.term_structure),
        ),
        tuple(
            (
                item.underlying,
                item.as_of_date,
                item.expiration,
                item.atm_iv,
                item.put_25_delta_iv,
                item.call_25_delta_iv,
                item.put_10_delta_iv,
                item.call_10_delta_iv,
                item.skew_percentile,
                item.skew_history_lookback_observations,
            )
            for item in candidate.tail_pricing_slices
        ),
        tuple(
            (
                result.scenario,
                result.valuation_date,
                result.base_underlying_price,
                result.base_ivs,
                result.estimated_position_value,
                result.entry_cost_basis,
                result.estimated_exit_cost,
            )
            for result in candidate.scenario_results
        ),
        tuple((item.evidence_id, item.kind, item.impact) for item in candidate.evidence),
    )


class LocaleValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = build_synthetic_candidate("en")

    def test_renderer_defaults_to_english(self) -> None:
        self.assertEqual(
            render_candidate_markdown(self.candidate),
            render_candidate_markdown(self.candidate, "en"),
        )

    def test_renderer_accepts_supported_and_normalized_locales(self) -> None:
        self.assertIn("# Convexity Hunter Research Record", render_candidate_markdown(self.candidate, "en"))
        self.assertIn("# Convexity Hunter 候选研究报告", render_candidate_markdown(build_synthetic_candidate("zh-CN"), "zh-CN"))
        self.assertEqual(
            render_candidate_markdown(self.candidate, "  en  "),
            render_candidate_markdown(self.candidate, "en"),
        )

    def test_renderer_rejects_invalid_candidate_and_locale(self) -> None:
        with self.assertRaises(TypeError):
            render_candidate_markdown("candidate")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            render_candidate_markdown(self.candidate, 1)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            render_candidate_markdown(self.candidate, "fr")
        with self.assertRaises(TypeError):
            render_candidate_markdown(
                self.candidate,
                screening_decision=object(),  # type: ignore[arg-type]
            )

    def test_renderer_rejects_malformed_maturity_context(self) -> None:
        malformed = object.__new__(OptionResearchMaturityContext)
        object.__setattr__(malformed, "structure", self.candidate.structure)
        with self.assertRaisesRegex(
            ValueError, "^maturity_context is malformed$"
        ):
            render_candidate_markdown(
                self.candidate,
                maturity_context=malformed,
            )

    def test_none_preserves_backward_compatible_rendering(self) -> None:
        implicit = render_candidate_markdown(self.candidate)
        explicit = render_candidate_markdown(
            self.candidate, screening_decision=None
        )
        self.assertEqual(implicit, explicit)
        self.assertIn(
            "No deterministic screening decision was supplied for this report.",
            explicit,
        )
        self.assertNotIn("### Deterministic screening decision", explicit)
        self.assertTrue(explicit.endswith("\n"))
        self.assertFalse(explicit.endswith("\n\n"))

    def test_custom_policy_identity_renders_without_mutation(self) -> None:
        decision = ScreeningDecision(
            CandidateState.WATCH,
            (ScreeningReasonCode.TAIL_PRICING_NOT_SUPPORTIVE,),
            "custom-family",
            "custom-7",
        )
        candidate_before = repr(self.candidate)
        decision_before = repr(decision)
        rendered = render_candidate_markdown(
            self.candidate, screening_decision=decision
        )
        self.assertIn("custom-family", rendered)
        self.assertIn("custom-7", rendered)
        self.assertEqual(repr(self.candidate), candidate_before)
        self.assertEqual(repr(decision), decision_before)

    def test_builder_accepts_supported_locales_and_defaults_to_english(self) -> None:
        self.assertEqual(build_synthetic_candidate().state_rationale, build_synthetic_candidate("en").state_rationale)
        self.assertIn("观察", build_synthetic_candidate("zh-CN").state_rationale)

    def test_builder_rejects_invalid_locale(self) -> None:
        with self.assertRaises(TypeError):
            build_synthetic_candidate(1)  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            build_synthetic_candidate("fr")


class BilingualReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.en_candidate = build_synthetic_candidate("en")
        self.zh_candidate = build_synthetic_candidate("zh-CN")
        policy = ScreeningPolicy()
        self.en_decision = screen_candidate(self.en_candidate, policy)
        self.zh_decision = screen_candidate(self.zh_candidate, policy)
        self.en = render_candidate_markdown(
            self.en_candidate, "en", self.en_decision
        )
        self.zh = render_candidate_markdown(
            self.zh_candidate, "zh-CN", self.zh_decision
        )

    def test_chinese_title_warning_and_overview_order(self) -> None:
        self.assertTrue(self.zh.startswith("# Convexity Hunter 候选研究报告\n"))
        self.assertIn("> **合成演示数据——不是当前市场数据，也不是交易建议**", self.zh)
        self.assertIn("## 通俗概要：先看懂这份报告", self.zh)
        self.assertNotIn("小白", self.zh)
        self.assertLess(self.zh.index("## 通俗概要：先看懂这份报告"), self.zh.index("## 技术研究明细"))

    def test_chinese_seven_overview_sections_are_ordered(self) -> None:
        headings = (
            "### 1. 研究的是什么？", "### 2. 两种状态分别代表什么？",
            "### 3. 为什么可能值得关注？", "### 4. 为什么仍然需要谨慎？",
            "### 5. 最多可能损失多少？", "### 6. 在给定情景下，结果可能怎样？",
            "### 7. 接下来需要人工核实什么？",
        )
        positions = [self.zh.index(item) for item in headings]
        self.assertEqual(positions, sorted(positions))

    def test_chinese_overview_content(self) -> None:
        self.assertIn("观察（watch）", self.zh)
        self.assertIn("同时买入相同执行价和到期日的看涨期权与看跌期权", self.zh)
        self.assertIn("$2,482.60", self.zh)
        self.assertIn("2.48%", self.zh)
        self.assertIn("$7,447.80", self.zh)
        self.assertIn("7.45%", self.zh)
        self.assertIn("3 个盈利、1 个亏损、0 个盈亏为零", self.zh)
        self.assertIn("已提供情景中的最高结果", self.zh)
        self.assertIn("$7,517.40", self.zh)
        self.assertIn("已提供情景中的最低结果", self.zh)
        self.assertIn("-$912.60", self.zh)
        self.assertIn("这里只比较报告中已提供的情景，不代表所有可能结果，也不是收益预测。", self.zh)
        self.assertIn("研究记录状态", self.zh)
        self.assertIn("确定性筛选建议状态", self.zh)
        self.assertIn("观察（watch）", self.zh)
        self.assertIn("数据不足（data_insufficient）", self.zh)
        self.assertIn("筛选政策 ID", self.zh)
        self.assertIn("筛选政策版本", self.zh)
        self.assertIn("确定性理由码", self.zh)
        self.assertIn("缺少政策要求的目标变动情景", self.zh)
        self.assertIn("该决策独立于已提供的研究记录状态", self.zh)

    def test_chinese_technical_report_is_localized(self) -> None:
        for text in (
            "### 研究假设", "### 具体期权结构", "### 有限损失与成本", "### 流动性",
            "### 第一层——整体波动率定价环境", "### 第二层——尾部相对定价",
            "### 情景分析", "### 证据", "#### 支持证据", "#### 弱化证据",
            "#### 中性证据", "### 证伪条件", "### 缺失数据", "### 假阳性风险",
            "### AI 解读", "### 人工复核问题", "| 期权腿 | 类型 | 执行价 |",
            "| 估值时间 | 估值日期 | 标的变动 |", "计算指标（calculated_metric）",
            "合成样例波动率环境数据",
        ):
            with self.subTest(text=text):
                self.assertIn(text, self.zh)
        self.assertTrue(self.zh.endswith("本记录用于整理研究证据，不推荐、不执行，也不保证任何交易或投资结果。\n"))

    def test_chinese_technical_heading_hierarchy(self) -> None:
        lines = self.zh.splitlines()
        parent_index = lines.index("## 技术研究明细")
        child_headings = (
            "研究假设", "具体期权结构", "有限损失与成本", "流动性",
            "第一层——整体波动率定价环境", "第二层——尾部相对定价", "情景分析", "证据",
            "证伪条件", "缺失数据", "假阳性风险", "AI 解读", "人工复核问题",
        )
        for heading in child_headings:
            with self.subTest(heading=heading):
                self.assertGreater(lines.index(f"### {heading}"), parent_index)
                self.assertNotIn(f"## {heading}", lines)
        for heading in ("支持证据", "弱化证据", "中性证据"):
            self.assertGreater(lines.index(f"#### {heading}"), lines.index("### 证据"))

    def test_english_title_warning_and_overview_order(self) -> None:
        self.assertTrue(self.en.startswith("# Convexity Hunter Research Record\n"))
        self.assertIn("> **SYNTHETIC DEMONSTRATION — NOT CURRENT MARKET DATA AND NOT A TRADE RECOMMENDATION**", self.en)
        self.assertLess(self.en.index("## Plain-language overview"), self.en.index("## Technical research details"))

    def test_english_seven_overview_sections_and_content(self) -> None:
        headings = tuple(f"### {number}. {title}" for number, title in (
            (1, "What is being studied?"), (2, "What do the two statuses mean?"),
            (3, "Why might it deserve attention?"), (4, "Why is caution still necessary?"),
            (5, "How much could be lost?"), (6, "What happens in the supplied scenarios?"),
            (7, "What should a human verify next?"),
        ))
        positions = [self.en.index(item) for item in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("buying a call and a put with the same strike and expiration", self.en)
        self.assertIn("$2,482.60", self.en)
        self.assertIn("Among the supplied scenarios: 3 positive, 1 negative", self.en)
        self.assertIn("Highest result among supplied scenarios", self.en)
        self.assertIn("Lowest result among supplied scenarios", self.en)
        self.assertIn("Research-record state", self.en)
        self.assertIn("Deterministic proposed state", self.en)
        self.assertIn("Screening policy ID", self.en)
        self.assertIn("Screening policy version", self.en)
        self.assertIn("Deterministic reason codes", self.en)
        self.assertIn("A required target-move scenario is missing", self.en)
        self.assertIn("This decision is separate from the supplied research-record state", self.en)

    def test_existing_english_technical_semantics_remain(self) -> None:
        for text in (
            "### Research hypothesis", "### Concrete option structure",
            "### Bounded downside and costs", "### Scenario analysis",
            "#### Supporting evidence", "#### Weakening evidence", "#### Neutral evidence",
            "28th historical percentile", "not proof that options are cheap",
            "SYNTHETIC-CALC-WEAKEN-IV-GAP",
            "Volatility-environment support fails if real data show",
        ):
            self.assertIn(text, self.en)
        self.assertTrue(self.en.endswith("This record organizes research evidence. It does not recommend, execute, or guarantee any trade or investment outcome.\n"))

    def test_english_technical_heading_hierarchy(self) -> None:
        lines = self.en.splitlines()
        parent_index = lines.index("## Technical research details")
        child_headings = (
            "Research hypothesis", "Concrete option structure", "Bounded downside and costs", "Liquidity",
            "Layer 1 — Volatility pricing environment", "Layer 2 — Tail relative pricing",
            "Scenario analysis", "Evidence", "Falsification conditions", "Missing data",
            "False-positive risks", "AI interpretation", "Human-review questions",
        )
        for heading in child_headings:
            with self.subTest(heading=heading):
                self.assertGreater(lines.index(f"### {heading}"), parent_index)
                self.assertNotIn(f"## {heading}", lines)
        for heading in ("Supporting evidence", "Weakening evidence", "Neutral evidence"):
            self.assertGreater(lines.index(f"#### {heading}"), lines.index("### Evidence"))
        self.assertLess(
            lines.index("### Deterministic screening decision"),
            lines.index("### Research hypothesis"),
        )

    def test_shared_determinism_newlines_and_no_repr(self) -> None:
        for locale, candidate, decision, rendered in (
            ("en", self.en_candidate, self.en_decision, self.en),
            ("zh-CN", self.zh_candidate, self.zh_decision, self.zh),
        ):
            with self.subTest(locale=locale):
                self.assertEqual(
                    rendered,
                    render_candidate_markdown(candidate, locale, decision),
                )
                self.assertTrue(rendered.endswith("\n"))
                self.assertFalse(rendered.endswith("\n\n"))
                self.assertNotIn("CandidateResearchRecord(", rendered)
                self.assertNotIn(" object at 0x", rendered)

    def test_minimal_candidate_renders_both_locales_with_localized_missing_values(self) -> None:
        candidate = build_minimal_watch()
        en = render_candidate_markdown(candidate, "en")
        zh = render_candidate_markdown(candidate, "zh-CN")
        self.assertIn("## Plain-language overview", en)
        self.assertIn("## 通俗概要：先看懂这份报告", zh)
        self.assertGreaterEqual(en.count("Not supplied."), 6)
        self.assertGreaterEqual(zh.count("未提供。"), 6)
        self.assertIn("No supporting evidence is currently reported.", en)
        self.assertIn("目前没有已报告的支持证据。", zh)

    def test_evidence_groups_remain_separate_in_both_languages(self) -> None:
        for rendered, headings in ((self.en, ("#### Supporting evidence", "#### Weakening evidence", "#### Neutral evidence")), (self.zh, ("#### 支持证据", "#### 弱化证据", "#### 中性证据"))):
            support, weaken, neutral = [rendered.index(item) for item in headings]
            self.assertIn("SYNTHETIC-CALC-SUPPORT", rendered[support:weaken])
            self.assertIn("SYNTHETIC-CALC-WEAKEN-IV-GAP", rendered[weaken:neutral])
            self.assertIn("SYNTHETIC-ASSUMPTION", rendered[neutral:])

    def test_cross_language_economic_and_identity_signature_matches(self) -> None:
        self.assertEqual(economic_signature(self.en_candidate), economic_signature(self.zh_candidate))
        self.assertNotEqual(self.en_candidate.hypothesis, self.zh_candidate.hypothesis)
        self.assertNotEqual(self.en_candidate.state_rationale, self.zh_candidate.state_rationale)

    def test_static_files_match_and_old_file_is_absent(self) -> None:
        zh_path = ROOT / "data" / "samples" / "sample-candidate-report.zh-CN.md"
        en_path = ROOT / "data" / "samples" / "sample-candidate-report.en.md"
        old_path = ROOT / "data" / "samples" / "sample-candidate-report.md"
        self.assertEqual(zh_path.read_text(), self.zh)
        self.assertEqual(en_path.read_text(), self.en)
        self.assertFalse(old_path.exists())
        for rendered in (self.en, self.zh):
            self.assertIn("watch", rendered)
            self.assertIn("data_insufficient", rendered)
            first = rendered.index("`missing_target_move_scenario`")
            second = rendered.index("`missing_volatility_crush_scenario`")
            self.assertLess(first, second)


class ScreeningPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = build_minimal_watch()

    def test_all_26_reason_codes_have_bilingual_presentations(self) -> None:
        expected_values = {reason.value for reason in ScreeningReasonCode}
        self.assertEqual(set(SCREENING_REASON_PRESENTATION), expected_values)
        self.assertEqual(len(expected_values), 26)
        for reason_value, presentation in SCREENING_REASON_PRESENTATION.items():
            with self.subTest(reason=reason_value):
                self.assertTrue(presentation["en"])
                self.assertTrue(presentation["zh-CN"])

    def test_each_state_group_renders_localized_reasons_and_explanation(self) -> None:
        cases = (
            (CandidateState.REJECT, REJECT_REASON_ORDER),
            (CandidateState.DATA_INSUFFICIENT, DATA_INSUFFICIENT_REASON_ORDER),
            (CandidateState.WATCH, WATCH_REASON_ORDER),
            (CandidateState.INVESTIGATE, INVESTIGATE_REASON_ORDER),
        )
        for state, reasons in cases:
            decision = ScreeningDecision(state, reasons, "test-policy", "1")
            for locale in ("en", "zh-CN"):
                with self.subTest(state=state, locale=locale):
                    rendered = render_candidate_markdown(
                        self.candidate, locale, decision
                    )
                    for reason in reasons:
                        self.assertIn(
                            SCREENING_REASON_PRESENTATION[reason.value][locale],
                            rendered,
                        )
                        self.assertIn(f"`{reason.value}`", rendered)

    def test_reason_order_is_preserved_and_no_reason_is_inferred(self) -> None:
        reasons = (
            ScreeningReasonCode.OPEN_INTEREST_BELOW_INVESTIGATE_MINIMUM,
            ScreeningReasonCode.DAILY_VOLUME_BELOW_INVESTIGATE_MINIMUM,
        )
        decision = ScreeningDecision(
            CandidateState.WATCH, reasons, "test-policy", "1"
        )
        rendered = render_candidate_markdown(
            self.candidate, screening_decision=decision
        )
        self.assertLess(
            rendered.index(f"`{reasons[0].value}`"),
            rendered.index(f"`{reasons[1].value}`"),
        )
        self.assertNotIn("`tail_pricing_not_supportive`", rendered)
        self.assertNotIn("`missing_costs`", rendered)

    def test_missing_reason_mapping_raises_instead_of_falling_back(self) -> None:
        reason = ScreeningReasonCode.MISSING_COSTS
        presentation = SCREENING_REASON_PRESENTATION.pop(reason.value)
        try:
            decision = ScreeningDecision(
                CandidateState.DATA_INSUFFICIENT,
                (reason,),
                "test-policy",
                "1",
            )
            with self.assertRaises(ValueError):
                render_candidate_markdown(
                    self.candidate, screening_decision=decision
                )
        finally:
            SCREENING_REASON_PRESENTATION[reason.value] = presentation

    def test_sample_decision_and_state_separation_are_exact(self) -> None:
        candidate = build_synthetic_candidate("en")
        decision = screen_candidate(candidate, ScreeningPolicy())
        self.assertIs(candidate.state, CandidateState.WATCH)
        self.assertIs(decision.proposed_state, CandidateState.DATA_INSUFFICIENT)
        self.assertEqual(
            decision.reason_codes,
            (
                ScreeningReasonCode.MISSING_TARGET_MOVE_SCENARIO,
                ScreeningReasonCode.MISSING_VOLATILITY_CRUSH_SCENARIO,
            ),
        )
        self.assertEqual(decision.policy_id, "synthetic-screening-v0.1")
        self.assertEqual(decision.policy_version, "0.1")


class CircularImportSafetyTests(unittest.TestCase):
    def test_import_orders_and_rendering_succeed_in_clean_interpreters(self) -> None:
        scripts = (
            "import convexity_hunter.report as report; "
            "import convexity_hunter.scanner as scanner; ",
            "import convexity_hunter.scanner as scanner; "
            "import convexity_hunter.report as report; ",
        )
        suffix = (
            "from examples.sample_candidate_report import build_synthetic_candidate; "
            "candidate=build_synthetic_candidate('en'); "
            "decision=scanner.screen_candidate(candidate, scanner.ScreeningPolicy()); "
            "assert 'Deterministic proposed state' in "
            "report.render_candidate_markdown(candidate, 'en', decision)"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = f"{ROOT / 'src'}:{ROOT}"
        for prefix in scripts:
            with self.subTest(prefix=prefix):
                result = subprocess.run(
                    [sys.executable, "-c", prefix + suffix],
                    cwd=ROOT,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)


class PositionManagementPlanPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan_result = _watch_result()
        self.candidate = self.plan_result.assembly_result.record

    def test_renderer_signature_has_exact_fifth_sidecar(self) -> None:
        signature = inspect.signature(render_candidate_markdown)
        parameters = tuple(signature.parameters.values())
        self.assertEqual(
            tuple(parameter.name for parameter in parameters),
            (
                "candidate",
                "locale",
                "screening_decision",
                "position_management_plan_result",
                "maturity_context",
            ),
        )
        self.assertEqual(parameters[3].default, None)
        self.assertEqual(parameters[4].default, None)
        self.assertNotIn(
            inspect.Parameter.VAR_POSITIONAL,
            tuple(parameter.kind for parameter in parameters),
        )
        self.assertNotIn(
            inspect.Parameter.VAR_KEYWORD,
            tuple(parameter.kind for parameter in parameters),
        )

    def test_plan_is_chinese_only_and_requires_exact_record_identity(self) -> None:
        with self.assertRaises(ValueError):
            render_candidate_markdown(
                self.candidate,
                "en",
                position_management_plan_result=self.plan_result,
            )
        equivalent = dataclasses.replace(self.candidate)
        with self.assertRaises(ValueError):
            render_candidate_markdown(
                equivalent,
                "zh-CN",
                position_management_plan_result=self.plan_result,
            )

    def test_plan_overview_and_technical_blocks_are_localized_and_ordered(self) -> None:
        rendered = render_candidate_markdown(
            self.candidate,
            "zh-CN",
            position_management_plan_result=self.plan_result,
        )
        self.assertIn("### 8. 未来条件声明（仅供后续人工判断）", rendered)
        self.assertIn(
            "- **研究记录状态：** 观察（`watch`）",
            rendered,
        )
        self.assertIn(
            "- **确定性筛选建议状态：** 未提供（本报告未提供确定性筛选决策）",
            rendered,
        )
        self.assertIn(
            "#### 考虑重新评估（`reassessment`）",
            rendered,
        )
        self.assertIn(
            "- 若未来发生“事件窗口发生变化”，则考虑重新评估（条件 ID：`review_event`）；当前未评估该条件是否已经满足。",
            rendered,
        )
        self.assertNotIn("观察（watch）（`watch`）", rendered)
        self.assertNotIn("拒绝（reject）（`reject`）", rendered)
        self.assertEqual(rendered.count("### 未来条件声明技术明细"), 1)
        self.assertTrue(rendered.endswith("\n"))
        self.assertFalse(rendered.endswith("\n\n"))

    def test_dynamic_plan_text_uses_a_safe_normalized_fence(self) -> None:
        condition = position_management.QualitativePositionManagementCondition(
            "review_event",
            position_management.PositionManagementCategory.REASSESSMENT,
            position_management.PositionManagementQualitativeTrigger.EVENT_WINDOW_SHIFTS,
            position_management.PositionManagementAuthority.CALLER,
            "source```\r\nreference",
            "reason",
        )
        result = position_management.create_position_management_plan(
            "plan-fenced",
            self.plan_result.assembly_result,
            [condition],
            self.plan_result.lineage.calculated_at + datetime.timedelta(seconds=1),
        )
        rendered = render_candidate_markdown(
            self.candidate,
            "zh-CN",
            position_management_plan_result=result,
        )
        self.assertIn("````\nsource```\nreference\n````", rendered)
        self.assertIn("```\nreason\n```", rendered)


class StaticGoldenAuthorityTests(unittest.TestCase):
    def _golden_screening(self, state):
        reason_order = {
            CandidateState.REJECT: REJECT_REASON_ORDER,
            CandidateState.DATA_INSUFFICIENT: DATA_INSUFFICIENT_REASON_ORDER,
            CandidateState.WATCH: WATCH_REASON_ORDER,
            CandidateState.INVESTIGATE: INVESTIGATE_REASON_ORDER,
        }[state]
        return ScreeningDecision(state, reason_order, "golden-screening", "v1")

    def test_required_goldens_are_direct_static_string_assignments(self) -> None:
        tree = ast.parse((pathlib.Path(__file__)).read_text())
        assignments = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name):
                    assignments[target.id] = node.value
        required = (
            "INVESTIGATE_PLAN_MARKDOWN_GOLDEN",
            "WATCH_PLAN_MARKDOWN_GOLDEN",
            "PUT_FIRST_LONG_STRADDLE_STRUCTURE_GOLDEN",
            "LONG_PUT_STRUCTURE_GOLDEN",
        )
        for name in required:
            with self.subTest(name=name):
                self.assertIn(name, assignments)
                self.assertIsInstance(assignments[name], ast.Constant)
                self.assertIs(type(assignments[name].value), str)
                self.assertNotIsInstance(assignments[name], ast.JoinedStr)
                self.assertNotIsInstance(assignments[name], ast.Call)
                self.assertNotIsInstance(assignments[name], ast.BinOp)

    def test_investigate_complete_report_is_an_independent_byte_golden(self) -> None:
        result = build_complete_investigate_plan_result()
        decision = self._golden_screening(CandidateState.INVESTIGATE)
        actual = render_candidate_markdown(
            result.assembly_result.record,
            "zh-CN",
            decision,
            result,
        )
        self.assertEqual(actual, INVESTIGATE_PLAN_MARKDOWN_GOLDEN)
        self.assertTrue(actual.endswith("\n"))
        self.assertFalse(actual.endswith("\n\n"))
        for value in (
            "net_liquidation_value_multiple",
            "remaining_dte",
            "bid_ask_spread_fraction",
            "atm_iv",
            "skew_percentile",
            "single_loss_fraction",
            "repeated_loss_fraction",
            "event_becomes_public",
            "underpricing_evidence_disappears",
            "event_window_shifts",
            "evidence_stale_or_missing",
            "contract_adjusted",
            "impact_path_materially_changes",
            "event_window_expires_without_hypothesized_change",
            "event_cancelled",
            "definitive_contrary_resolution",
            "exemption_confirmed",
            "impact_path_invalidated",
            "revised_event_window_not_covered",
            "data_loss_prevents_responsible_evaluation",
        ):
            with self.subTest(value=value):
                self.assertIn(f"`{value}`", actual)

    def test_watch_complete_report_is_an_independent_byte_golden(self) -> None:
        result = _watch_result()
        decision = self._golden_screening(CandidateState.REJECT)
        actual = render_candidate_markdown(
            result.assembly_result.record,
            "zh-CN",
            decision,
            result,
        )
        self.assertEqual(actual, WATCH_PLAN_MARKDOWN_GOLDEN)
        self.assertIn("- **研究记录状态：** 观察（`watch`）", actual)
        self.assertIn("- **确定性筛选建议状态：** 拒绝（`reject`）", actual)
        self.assertIn("研究记录状态与确定性筛选建议状态不一致", actual)
        self.assertIn("本 WATCH 计划未声明此类未来条件", actual)
        self.assertNotIn("期权腿 2", actual)
        self.assertTrue(actual.endswith("\n"))

    def test_structure_goldens_preserve_put_first_and_one_leg_shapes(self) -> None:
        cases = (
            (
                PUT_FIRST_LONG_STRADDLE_STRUCTURE_GOLDEN,
                OptionStructure(
                    (
                        OptionLeg("SPY", "put", 100.0, datetime.date(2030, 3, 3)),
                        OptionLeg("SPY", "call", 100.0, datetime.date(2030, 3, 3)),
                    ),
                    100000.0,
                    14,
                ),
                ("put", "call"),
            ),
            (
                LONG_PUT_STRUCTURE_GOLDEN,
                OptionStructure(
                    (OptionLeg("SPY", "put", 100.0, datetime.date(2030, 3, 3)),),
                    100000.0,
                    14,
                ),
                ("put",),
            ),
        )
        for expected, structure, order in cases:
            with self.subTest(order=order):
                lines = []
                _append_plan_structure(lines, structure)
                actual = "\n".join(lines) + "\n"
                self.assertEqual(actual, expected)
                self.assertEqual(tuple(leg.option_type for leg in structure.legs), order)
                self.assertEqual(actual, "\n".join(lines) + "\n")
        self.assertNotIn("期权腿 2", LONG_PUT_STRUCTURE_GOLDEN)

    def test_golden_lengths_hashes_and_final_newlines_are_frozen(self) -> None:
        expected = {
            "INVESTIGATE_PLAN_MARKDOWN_GOLDEN": (
                35769,
                "d0530bf013cc1119b36fda474c12319e836f2c50bbf336af16dac4059e50498c",
            ),
            "WATCH_PLAN_MARKDOWN_GOLDEN": (
                8019,
                "72cd45a0f4a5426ff03bc35a58c85392c441298588d74b355fcfaf5cc76ed553",
            ),
            "PUT_FIRST_LONG_STRADDLE_STRUCTURE_GOLDEN": (
                660,
                "fd1093abfd7619f9556dacde3ae2a10c4d2cc127a54f10649ea7f16f547b372f",
            ),
            "LONG_PUT_STRUCTURE_GOLDEN": (
                424,
                "4389fbc1164e92d51224a292f23dc08f5cbd1c8af2875c5297342216b87c069b",
            ),
        }
        for name, (length, digest) in expected.items():
            value = globals()[name]
            with self.subTest(name=name):
                self.assertEqual(len(value.encode("utf-8")), length)
                self.assertEqual(hashlib.sha256(value.encode("utf-8")).hexdigest(), digest)
                self.assertTrue(value.endswith("\n"))
                self.assertFalse(value.endswith("\n\n"))


class RendererBoundaryMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.investigate = build_complete_investigate_plan_result()
        self.candidate = self.investigate.assembly_result.record

    def test_missing_grouped_conditions_and_anchor_errors_are_exact(self) -> None:
        with self.assertRaisesRegex(ValueError, "^internal plan condition grouping is missing$"):
            _append_overview(
                [], self.candidate, "zh-CN", None, self.investigate, None
            )
        with self.assertRaisesRegex(ValueError, "^internal plan condition grouping is missing$"):
            _technical_body(
                self.candidate, "zh-CN", None, self.investigate, None
            )
        grouped = {"monetization": [], "reassessment": [], "exit": []}
        with mock.patch(
            "convexity_hunter.report._render_technical_english",
            return_value="# title\n\n### another heading\nbody",
        ):
            with self.assertRaisesRegex(RuntimeError, "^internal report anchor must appear exactly once$"):
                _technical_body(self.candidate, "zh-CN", None, self.investigate, grouped)
        with mock.patch(
            "convexity_hunter.report._render_technical_english",
            return_value="# title\n\n### 研究假设\nbody\n### 研究假设\nagain",
        ):
            with self.assertRaisesRegex(RuntimeError, "^internal report anchor must appear exactly once$"):
                _technical_body(self.candidate, "zh-CN", None, self.investigate, grouped)
        source = (ROOT / "src" / "convexity_hunter" / "report.py").read_text()
        self.assertEqual(source.count('raise RuntimeError("internal report anchor must appear exactly once")'), 1)

    def test_exact_candidate_identity_matrix_covers_all_seventeen_fields(self) -> None:
        fields = tuple(field.name for field in dataclasses.fields(CandidateResearchRecord))
        self.assertEqual(len(fields), 17)
        altered = {
            "candidate_id": "candidate-altered",
            "state": CandidateState.WATCH,
            "state_rationale": "altered rationale",
            "as_of_date": self.candidate.as_of_date + datetime.timedelta(days=1),
            "hypothesis": "altered hypothesis",
            "structure": dataclasses.replace(
                self.candidate.structure,
                expected_holding_days=self.candidate.structure.expected_holding_days + 1,
            ),
            "volatility_environment": None,
            "tail_pricing_slices": (),
            "costs": None,
            "liquidity": None,
            "scenario_results": (),
            "evidence": (),
            "falsification_conditions": ("altered",),
            "missing_data": ("altered",),
            "false_positive_reasons": ("altered",),
            "ai_interpretation": "altered",
            "human_review_questions": ("altered",),
        }
        self.assertEqual(set(altered), set(fields))
        with self.assertRaises(ValueError):
            render_candidate_markdown(
                dataclasses.replace(self.candidate),
                "zh-CN",
                position_management_plan_result=self.investigate,
            )
        for field in fields:
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    render_candidate_markdown(
                        dataclasses.replace(self.candidate, **{field: altered[field]}),
                        "zh-CN",
                        position_management_plan_result=self.investigate,
                    )

    def test_state_presence_and_screening_disagreement_matrix(self) -> None:
        for state in CandidateState:
            with self.subTest(research_state=state):
                candidate = dataclasses.replace(
                    self.candidate,
                    state=state,
                    missing_data=("required missing data",)
                    if state is CandidateState.DATA_INSUFFICIENT
                    else self.candidate.missing_data,
                )
                render_candidate_markdown(candidate, "zh-CN")
        render_candidate_markdown(
            self.candidate,
            "zh-CN",
            ScreeningDecision(CandidateState.REJECT, REJECT_REASON_ORDER, "p", "v"),
            self.investigate,
        )
        watch = _watch_result()
        render_candidate_markdown(
            watch.assembly_result.record,
            "zh-CN",
            ScreeningDecision(CandidateState.REJECT, REJECT_REASON_ORDER, "p", "v"),
            watch,
        )
        for state in (CandidateState.REJECT, CandidateState.DATA_INSUFFICIENT):
            forged_plan = object.__new__(type(self.investigate.plan))
            for field in dataclasses.fields(self.investigate.plan):
                value = state if field.name == "candidate_state" else getattr(self.investigate.plan, field.name)
                object.__setattr__(forged_plan, field.name, value)
            forged_result = object.__new__(type(self.investigate))
            object.__setattr__(forged_result, "assembly_result", self.investigate.assembly_result)
            object.__setattr__(forged_result, "plan", forged_plan)
            object.__setattr__(forged_result, "lineage", self.investigate.lineage)
            with self.subTest(plan_state=state), self.assertRaises(ValueError):
                render_candidate_markdown(
                    self.candidate, "zh-CN", position_management_plan_result=forged_result
                )

    def test_screening_decision_type_reason_policy_and_no_call_matrix(self) -> None:
        candidate = build_minimal_watch()
        decisions = (
            ScreeningDecision(CandidateState.REJECT, REJECT_REASON_ORDER, "p", "v"),
            ScreeningDecision(CandidateState.DATA_INSUFFICIENT, DATA_INSUFFICIENT_REASON_ORDER, "p", "v"),
            ScreeningDecision(CandidateState.WATCH, WATCH_REASON_ORDER, "p", "v"),
            ScreeningDecision(CandidateState.INVESTIGATE, INVESTIGATE_REASON_ORDER, "p", "v"),
        )
        for decision in decisions:
            with self.subTest(state=decision.proposed_state):
                render_candidate_markdown(candidate, "zh-CN", decision)

        class DecisionSubclass(ScreeningDecision):
            pass

        render_candidate_markdown(
            candidate,
            "zh-CN",
            DecisionSubclass(CandidateState.WATCH, WATCH_REASON_ORDER, "p", "v"),
        )

        def forged(decision, **changes):
            value = object.__new__(type(decision))
            for field in dataclasses.fields(ScreeningDecision):
                object.__setattr__(value, field.name, changes.get(field.name, getattr(decision, field.name)))
            return value

        valid = decisions[2]
        with self.assertRaises(TypeError):
            render_candidate_markdown(candidate, "zh-CN", object())  # type: ignore[arg-type]
        for missing in ("proposed_state", "reason_codes", "policy_id", "policy_version"):
            value = object.__new__(ScreeningDecision)
            for field in dataclasses.fields(ScreeningDecision):
                if field.name != missing:
                    object.__setattr__(value, field.name, getattr(valid, field.name))
            with self.subTest(missing=missing), self.assertRaises(ValueError):
                render_candidate_markdown(candidate, "zh-CN", value)
        cases = (
            (forged(valid, proposed_state="watch"), TypeError),
            (forged(valid, reason_codes=list(valid.reason_codes)), TypeError),
            (forged(valid, reason_codes=("bad",)), TypeError),
            (forged(valid, reason_codes=(REJECT_REASON_ORDER[0],)), ValueError),
            (forged(valid, reason_codes=valid.reason_codes + (valid.reason_codes[0],)), ValueError),
            (forged(valid, reason_codes=tuple(reversed(valid.reason_codes))), ValueError),
            (forged(decisions[3], reason_codes=INVESTIGATE_REASON_ORDER[:-1]), ValueError),
            (forged(decisions[3], reason_codes=INVESTIGATE_REASON_ORDER + (REJECT_REASON_ORDER[0],)), ValueError),
            (forged(valid, policy_id=1), TypeError),
            (forged(valid, policy_version=object()), TypeError),
            (forged(valid, policy_id=""), ValueError),
            (forged(valid, policy_version=" v "), ValueError),
        )
        for value, error in cases:
            with self.subTest(error=error, value=repr(value)):
                with self.assertRaises(error):
                    render_candidate_markdown(candidate, "zh-CN", value)

        class TupleSubclass(tuple):
            pass

        with self.assertRaises(TypeError):
            render_candidate_markdown(
                candidate,
                "zh-CN",
                forged(valid, reason_codes=TupleSubclass(valid.reason_codes)),
            )
        with mock.patch(
            "convexity_hunter.scanner.screen_candidate",
            side_effect=AssertionError("screen_candidate must not be called"),
        ):
            render_candidate_markdown(candidate, "zh-CN", valid)

    def test_canonical_threshold_formatting_and_shared_report_bytes(self) -> None:
        decimal_cases = (
            (decimal.Decimal("2"), "2"),
            (decimal.Decimal("2.0"), "2"),
            (decimal.Decimal("2.5000"), "2.5"),
            (decimal.Decimal("0"), "0"),
            (decimal.Decimal("-0"), "0"),
            (decimal.Decimal("0E-9"), "0"),
            (decimal.Decimal("1E+3"), "1000"),
            (decimal.Decimal("0.125"), "0.125"),
            (decimal.Decimal("0.005"), "0.005"),
        )
        for value, expected in decimal_cases:
            with self.subTest(value=value):
                self.assertEqual(_canonical_decimal_text(value), expected)
        percentage_cases = (
            ("0", "0.00%"), ("0.00005", "0.01%"), ("0.00015", "0.02%"),
            ("0.00495", "0.50%"), ("0.005", "0.50%"), ("0.12495", "12.50%"),
            ("0.125", "12.50%"), ("0.99995", "100.00%"), ("1", "100.00%"),
        )
        for value, expected in percentage_cases:
            with self.subTest(value=value):
                self.assertEqual(_decimal_percentage_text(decimal.Decimal(value)), expected)
        for value, expected in (
            (ExactRational(0, 1), "0.00%"),
            (ExactRational(1, 20), "5.00%"),
            (ExactRational(1, 3), "33.33%"),
            (ExactRational(2, 3), "66.67%"),
            (ExactRational(1, 1), "100.00%"),
        ):
            with self.subTest(value=value):
                self.assertEqual(_rational_percentage_text(value), expected)
        for dte, expected in ((0, "0 个日历日"), (1, "1 个日历日"), (7, "7 个日历日")):
            condition = _golden_quantitative(
                "dte", position_management.PositionManagementCategory.REASSESSMENT,
                position_management.PositionManagementMetric.REMAINING_DTE,
                position_management.PositionManagementComparison.LESS_THAN_OR_EQUAL,
                dte, position_management.PositionManagementAuthority.CALLER,
            )
            self.assertEqual(_format_plan_threshold(condition), expected)
        rendered = render_candidate_markdown(
            self.candidate,
            "zh-CN",
            ScreeningDecision(CandidateState.INVESTIGATE, INVESTIGATE_REASON_ORDER, "p", "v"),
            self.investigate,
        )
        for threshold in ('Decimal("0.4")（40.00%)', 'Decimal("2.5")（2.5×）', '59 个日历日', 'ExactRational(1, 100)（1.00%）'):
            with self.subTest(threshold=threshold):
                self.assertGreaterEqual(rendered.count(threshold), 2)

    def test_localization_trigger_categories_and_safe_fence_matrix(self) -> None:
        rendered = render_candidate_markdown(
            self.candidate,
            "zh-CN",
            ScreeningDecision(CandidateState.INVESTIGATE, INVESTIGATE_REASON_ORDER, "p", "v"),
            self.investigate,
        )
        plan_part = rendered[rendered.index("### 8."):rendered.index("---")]
        technical_plan = rendered[rendered.index("### 未来条件声明技术明细"):]
        for raw, label in (
            ("monetization", "考虑货币化"),
            ("reassessment", "考虑重新评估"),
            ("exit", "考虑退出"),
            ("event_becomes_public", "事件公开"),
            ("event_window_shifts", "事件窗口发生变化"),
            ("data_loss_prevents_responsible_evaluation", "数据丢失，无法负责地评估"),
        ):
            with self.subTest(raw=raw):
                self.assertIn(f"{label}", plan_part)
                self.assertIn(f"`{raw}`", rendered)
        self.assertNotIn("若未来未来", plan_part)
        condition_lines = "\n".join(
            line for line in plan_part.splitlines() if line.startswith("- 若未来")
        )
        self.assertNotIn("考虑货币化或", condition_lines)
        self.assertNotIn("考虑重新评估或", condition_lines)
        self.assertNotIn("考虑退出或", condition_lines)
        self.assertIn("event_becomes_public", technical_plan)
        self.assertEqual(plan_part.count("#### 考虑货币化"), 1)
        self.assertEqual(plan_part.count("#### 考虑重新评估"), 1)
        self.assertEqual(plan_part.count("#### 考虑退出"), 1)

        cases = (
            ("ordinary text", 3), ("one ` tick", 3), ("two `` ticks", 3),
            ("three ``` ticks", 4), ("five ````` ticks", 6),
            ("a``b```c", 4), ("# heading\n- list\n| table |", 3),
            ("line\r\nnext\rfinal", 3), ("trailing\\", 3),
            ("no newline", 3), ("one newline\n", 3), ("multiple\n\n", 3),
        )
        for value, fence_length in cases:
            with self.subTest(value=value):
                lines = _safe_fenced_lines(value)
                self.assertEqual(lines[0], "`" * fence_length)
                self.assertEqual(lines[-1], "`" * fence_length)
                self.assertNotIn("\r", "\n".join(lines))
                self.assertNotIn("```\n", lines[1:-1])
                self.assertEqual(lines[0], lines[-1])

    def test_quality_flags_technical_order_and_no_call_static_boundary(self) -> None:
        result = _watch_result()
        grouped = {"monetization": [], "reassessment": list(result.plan.conditions), "exit": []}
        no_flags_lineage = dataclasses.replace(result.lineage, quality_flags=())
        no_flags = object.__new__(type(result))
        object.__setattr__(no_flags, "assembly_result", result.assembly_result)
        object.__setattr__(no_flags, "plan", result.plan)
        object.__setattr__(no_flags, "lineage", no_flags_lineage)
        self.assertIn("- **质量标记：** 无", "\n".join(_render_plan_technical_block(no_flags, grouped)))
        all_flags_lineage = dataclasses.replace(
            result.lineage, quality_flags=tuple(CalculationQualityFlag)
        )
        all_flags = object.__new__(type(result))
        object.__setattr__(all_flags, "assembly_result", result.assembly_result)
        object.__setattr__(all_flags, "plan", result.plan)
        object.__setattr__(all_flags, "lineage", all_flags_lineage)
        technical = "\n".join(_render_plan_technical_block(all_flags, grouped))
        self.assertEqual(technical.count("、"), len(CalculationQualityFlag) - 1)
        source = (ROOT / "src" / "convexity_hunter" / "report.py").read_text()
        for forbidden in (
            "screen_candidate(",
            "create_position_management_plan(",
            "assemble_candidate_research_record(",
            "assess_structure_affordability(",
        ):
            self.assertNotIn(forbidden, source)
        technical_source = inspect.getsource(_technical_body)
        self.assertIn("body_lines[anchor:anchor] = insertion", technical_source)


class AuthoritativeRendererMatrixTests(unittest.TestCase):
    def setUp(self):
        self.result = build_complete_investigate_plan_result()
        self.candidate = self.result.assembly_result.record

    def test_identity_matrix_has_nineteen_renderer_boundary_cases(self):
        fields = tuple(field.name for field in dataclasses.fields(CandidateResearchRecord))
        self.assertEqual(len(fields), 17)
        altered = {
            "candidate_id": "candidate-altered", "state": CandidateState.WATCH,
            "state_rationale": "altered rationale", "as_of_date": self.candidate.as_of_date + datetime.timedelta(days=1),
            "hypothesis": "altered hypothesis", "structure": dataclasses.replace(self.candidate.structure, expected_holding_days=15),
            "volatility_environment": None, "tail_pricing_slices": (), "costs": None, "liquidity": None,
            "scenario_results": (), "evidence": (), "falsification_conditions": ("altered",),
            "missing_data": ("altered",), "false_positive_reasons": ("altered",), "ai_interpretation": "altered",
            "human_review_questions": ("altered",),
        }
        counters = {"plan": 0, "identity": 0, "render": 0}
        original_plan = position_management._verify_position_management_plan_result
        original_binding = report_module._validate_plan_binding
        original_overview = report_module._append_overview
        def count_plan(value):
            counters["plan"] += 1
            return original_plan(value)
        def count_binding(*args):
            counters["identity"] += 1
            return original_binding(*args)
        def count_render(*args, **kwargs):
            counters["render"] += 1
            return original_overview(*args, **kwargs)
        with mock.patch.object(position_management, "_verify_position_management_plan_result", side_effect=count_plan), \
             mock.patch.object(report_module, "_validate_plan_binding", side_effect=count_binding), \
             mock.patch.object(report_module, "_append_overview", side_effect=count_render):
            self.assertIn("### 8.", render_candidate_markdown(self.candidate, "zh-CN", position_management_plan_result=self.result))
            equal = _exact_candidate_clone(self.candidate)
            self.assertIsNot(equal, self.candidate)
            self.assertEqual(equal, self.candidate)
            with self.assertRaisesRegex(ValueError, "^position-management plan must bind the exact candidate record object$"):
                render_candidate_markdown(equal, "zh-CN", position_management_plan_result=self.result)
            for field in fields:
                with self.subTest(field=field):
                    clone = _exact_candidate_clone(self.candidate, field, altered[field])
                    self.assertIs(type(clone), CandidateResearchRecord)
                    for other in set(fields) - {field}:
                        self.assertIs(getattr(clone, other), getattr(self.candidate, other))
                    with self.assertRaisesRegex(ValueError, "^position-management plan must bind the exact candidate record object$"):
                        render_candidate_markdown(clone, "zh-CN", position_management_plan_result=self.result)
        self.assertEqual(counters, {"plan": 19, "identity": 19, "render": 1})

    def test_state_screening_presence_matrix_executes_forty_cases(self):
        plans = {CandidateState.WATCH: _watch_result(), CandidateState.INVESTIGATE: self.result}
        candidates = {
            CandidateState.REJECT: _partial_assembly(CandidateState.REJECT).record,
            CandidateState.WATCH: plans[CandidateState.WATCH].assembly_result.record,
            CandidateState.INVESTIGATE: plans[CandidateState.INVESTIGATE].assembly_result.record,
            CandidateState.DATA_INSUFFICIENT: _partial_assembly(CandidateState.DATA_INSUFFICIENT).record,
        }
        counts = {"cases": 0, "success": 0, "reject": 0}
        for state in CandidateState:
            for screening in (None,) + tuple(_screening_for_state(item) for item in CandidateState):
                for present in (False, True):
                    with self.subTest(state=state, screening=None if screening is None else screening.proposed_state, present=present):
                        counts["cases"] += 1
                        candidate = candidates[state]
                        if not present:
                            output = render_candidate_markdown(candidate, "zh-CN", screening)
                            self.assertNotIn("### 8. 未来条件声明", output)
                            self.assertNotIn("### 未来条件声明技术明细", output)
                            if screening is not None:
                                self.assertIn(f"（{screening.proposed_state.value}）", output)
                            counts["success"] += 1
                        elif state in plans:
                            result = plans[state]
                            output = render_candidate_markdown(result.assembly_result.record, "zh-CN", screening, result)
                            self.assertIn("### 8. 未来条件声明", output)
                            self.assertIn("### 未来条件声明技术明细", output)
                            if screening is not None:
                                self.assertIn(f"（{screening.proposed_state.value}）", output)
                            counts["success"] += 1
                        else:
                            assembly = _partial_assembly(state, candidate_id=f"candidate-{state.value}", assembly_id=f"assembly-{state.value}")
                            plan = _exact_dataclass_clone(self.result.plan, candidate_id=assembly.record.candidate_id, candidate_state=state, as_of_date=assembly.record.as_of_date, structure=assembly.record.structure)
                            forged = _exact_dataclass_clone(self.result, assembly_result=assembly, plan=plan)
                            reached = {"plan": 0}
                            original = position_management._verify_plan_intrinsic
                            def count(value):
                                reached["plan"] += 1
                                return original(value)
                            with mock.patch.object(position_management, "_verify_plan_intrinsic", side_effect=count):
                                with self.assertRaisesRegex(ValueError, "^candidate_state is not permitted for a plan$"):
                                    render_candidate_markdown(assembly.record, "zh-CN", screening, forged)
                            self.assertEqual(reached["plan"], 1)
                            counts["reject"] += 1
        self.assertEqual(counts, {"cases": 40, "success": 30, "reject": 10})

    def test_screening_boundary_matrix_has_all_valid_and_malformed_cases(self):
        candidate = build_minimal_watch()
        valid = tuple(_screening_for_state(state) for state in CandidateState)
        self.assertIn("未提供", render_candidate_markdown(candidate, "zh-CN", None))
        for decision in valid:
            with self.subTest(valid=decision.proposed_state):
                output = render_candidate_markdown(candidate, "zh-CN", decision)
                self.assertIn(f"（{decision.proposed_state.value}）", output)
        class DecisionSubclass(ScreeningDecision):
            pass
        self.assertIn("（watch）", render_candidate_markdown(candidate, "zh-CN", DecisionSubclass(CandidateState.WATCH, WATCH_REASON_ORDER, "p", "v")))
        def forged(decision, **changes):
            return _exact_dataclass_clone(decision, **changes)
        base = valid[1]
        plan_result = _watch_result()
        missing_field_cases = []
        for missing in ("proposed_state", "reason_codes", "policy_id", "policy_version"):
            malformed = object.__new__(ScreeningDecision)
            for field in dataclasses.fields(ScreeningDecision):
                if field.name != missing:
                    object.__setattr__(malformed, field.name, getattr(base, field.name))
            missing_field_cases.append((missing, malformed))
        for missing, malformed in missing_field_cases:
            with self.subTest(missing_field=missing):
                validator_calls = 0
                original_validator = report_module._validate_screening_decision
                def counted_validator(value):
                    nonlocal validator_calls
                    validator_calls += 1
                    return original_validator(value)
                with mock.patch.object(report_module, "_validate_screening_decision", side_effect=counted_validator), \
                     mock.patch.object(position_management, "_verify_position_management_plan_result", side_effect=AssertionError("plan verifier must not be reached")), \
                     mock.patch.object(report_module, "_validate_plan_binding", side_effect=AssertionError("candidate identity must not be reached")), \
                     mock.patch.object(report_module, "_append_overview", side_effect=AssertionError("rendering must not begin")):
                    with self.assertRaisesRegex(ValueError, f"^screening decision is missing {missing}$"):
                        try:
                            render_candidate_markdown(plan_result.assembly_result.record, "zh-CN", malformed, plan_result)
                        except AttributeError as error:
                            self.fail(f"raw AttributeError escaped for missing {missing}: {error}")
                self.assertEqual(validator_calls, 1)
        class TupleSubclass(tuple):
            pass
        class StringSubclass(str):
            pass
        class ForeignState:
            value = "watch"
        cases = [("wrong outer", object(), TypeError), ("state scalar", forged(base, proposed_state="watch"), TypeError),
                 ("state foreign", forged(base, proposed_state=ForeignState()), TypeError),
                 ("state forged", forged(base, proposed_state=object.__new__(ForeignState)), TypeError),
                 ("reasons list", forged(base, reason_codes=list(base.reason_codes)), TypeError),
                 ("reasons subclass", forged(base, reason_codes=TupleSubclass(base.reason_codes)), TypeError),
                 ("reason item", forged(base, reason_codes=("bad",)), TypeError),
                 ("wrong group", forged(base, reason_codes=(REJECT_REASON_ORDER[0],)), ValueError),
                 ("duplicate", forged(base, reason_codes=base.reason_codes + (base.reason_codes[0],)), ValueError),
                 ("reordered", forged(base, reason_codes=tuple(reversed(base.reason_codes))), ValueError),
                 ("investigate omitted", forged(valid[2], reason_codes=INVESTIGATE_REASON_ORDER[:-1]), ValueError),
                 ("investigate surplus", forged(valid[2], reason_codes=INVESTIGATE_REASON_ORDER + (REJECT_REASON_ORDER[0],)), ValueError)]
        for field in ("policy_id", "policy_version"):
            cases.extend(((f"{field} type", forged(base, **{field: 1}), TypeError),
                          (f"{field} subclass", forged(base, **{field: StringSubclass("v")}), TypeError),
                          (f"{field} empty", forged(base, **{field: ""}), ValueError),
                          (f"{field} whitespace", forged(base, **{field: "   "}), ValueError),
                          (f"{field} leading", forged(base, **{field: " v"}), ValueError),
                          (f"{field} trailing", forged(base, **{field: "v "}), ValueError)))
        reached = 0
        original = report_module._validate_screening_decision
        def count(value):
            nonlocal reached
            reached += 1
            return original(value)
        with mock.patch.object(report_module, "_validate_screening_decision", side_effect=count), \
             mock.patch("convexity_hunter.scanner.screen_candidate", side_effect=AssertionError("screen_candidate must not be called")):
            for label, decision, exception in cases:
                with self.subTest(malformed=label):
                    with self.assertRaises(exception):
                        render_candidate_markdown(candidate, "zh-CN", decision)
            self.assertIn("（watch）", render_candidate_markdown(candidate, "zh-CN", base))
        self.assertEqual(len(cases), 24)
        self.assertEqual(reached, 25)


class AuthoritativeConditionAndFenceTests(unittest.TestCase):
    def setUp(self):
        self.base = build_complete_investigate_plan_result()
        self.output = render_candidate_markdown(self.base.assembly_result.record, "zh-CN", position_management_plan_result=self.base)

    def _replace(self, original, changed, label):
        conditions = tuple(changed if item is original else item for item in self.base.plan.conditions)
        return position_management.create_position_management_plan(
            f"condition-{label}", self.base.assembly_result, conditions,
            self.base.lineage.calculated_at + datetime.timedelta(seconds=1),
        )

    def _assert_exact_condition_field_change(self, base_condition, mutated_condition, changed_field):
        self.assertIn(type(base_condition), (position_management.QuantitativePositionManagementCondition, position_management.QualitativePositionManagementCondition))
        self.assertIs(type(mutated_condition), type(base_condition))
        fields = tuple(field.name for field in dataclasses.fields(type(base_condition)))
        self.assertEqual(fields, tuple(field.name for field in dataclasses.fields(type(mutated_condition))))
        differences = tuple(
            field for field in fields
            if getattr(base_condition, field) != getattr(mutated_condition, field)
        )
        self.assertEqual(differences, (changed_field,))
        self.assertNotEqual(getattr(base_condition, changed_field), getattr(mutated_condition, changed_field))
        for field in fields:
            if field != changed_field:
                self.assertEqual(getattr(base_condition, field), getattr(mutated_condition, field))
                self.assertIs(getattr(base_condition, field), getattr(mutated_condition, field))

    def test_condition_valid_renderer_reaching_dimensions(self):
        pm = position_management
        atm = next(item for item in self.base.plan.conditions if item.condition_id == "atm_iv")
        event = next(item for item in self.base.plan.conditions if item.condition_id == "event_public")
        cases = (
            ("id", atm, dataclasses.replace(atm, condition_id="atm_iv_alt"), "`atm_iv_alt`"),
            ("metric", atm, dataclasses.replace(atm, metric=pm.PositionManagementMetric.SKEW_PERCENTILE), "未来结构到期日偏斜历史百分位（`skew_percentile`）"),
            ("trigger", event, dataclasses.replace(event, trigger=pm.PositionManagementQualitativeTrigger.UNDERPRICING_EVIDENCE_DISAPPEARS), "低估定价证据消失（`underpricing_evidence_disappears`）"),
            ("comparison", atm, dataclasses.replace(atm, comparison=pm.PositionManagementComparison.GREATER_THAN_OR_EQUAL), "大于或等于（`greater_than_or_equal`）"),
            ("threshold", atm, dataclasses.replace(atm, threshold=decimal.Decimal("0.45")), 'Decimal("0.45")（45.00%)'),
            ("authority", atm, dataclasses.replace(atm, authority=pm.PositionManagementAuthority.HUMAN_ANALYST), "人工分析员（`human_analyst`）"),
            ("source", atm, dataclasses.replace(atm, source_reference="changed source"), "changed source"),
            ("rationale", atm, dataclasses.replace(atm, rationale="changed rationale"), "changed rationale"),
        )
        for label, original, changed, expected in cases:
            with self.subTest(dimension=label):
                changed_field = {
                    "id": "condition_id", "metric": "metric", "trigger": "trigger",
                    "comparison": "comparison", "threshold": "threshold", "authority": "authority",
                    "source": "source_reference", "rationale": "rationale",
                }[label]
                self._assert_exact_condition_field_change(original, changed, changed_field)
                original_index = self.base.plan.conditions.index(original)
                result = self._replace(original, changed, label)
                self.assertEqual(len(result.plan.conditions), len(self.base.plan.conditions))
                self.assertIs(result.plan.conditions[original_index], changed)
                for index, condition in enumerate(self.base.plan.conditions):
                    if index != original_index:
                        self.assertIs(result.plan.conditions[index], condition)
                        self.assertEqual(result.plan.conditions[index], condition)
                self.assertEqual(result.plan.candidate_id, self.base.plan.candidate_id)
                self.assertIs(result.plan.candidate_state, self.base.plan.candidate_state)
                self.assertEqual(result.plan.as_of_date, self.base.plan.as_of_date)
                self.assertIs(result.plan.structure, self.base.plan.structure)
                self.assertIs(result.assembly_result, self.base.assembly_result)
                output = render_candidate_markdown(result.assembly_result.record, "zh-CN", position_management_plan_result=result)
                self.assertNotEqual(output, self.output)
                self.assertIn(expected, output)
                self.assertIn(f"`{changed.condition_id}`", output)
                self.assertIn("golden rationale" if label != "rationale" else "golden source", output)

    def test_exact_condition_field_change_helper_rejects_zero_and_two_fields(self):
        base = next(item for item in self.base.plan.conditions if item.condition_id == "atm_iv")
        two_field_mutation = dataclasses.replace(
            base,
            condition_id="atm_iv_two_field",
            source_reference="two-field source",
        )
        self.assertIs(type(two_field_mutation), type(base))
        fields = tuple(field.name for field in dataclasses.fields(type(base)))
        differences = tuple(
            field for field in fields
            if getattr(base, field) != getattr(two_field_mutation, field)
        )
        self.assertEqual(differences, ("condition_id", "source_reference"))
        with mock.patch.object(
            self,
            "_assert_exact_condition_field_change",
            wraps=self._assert_exact_condition_field_change,
        ) as helper:
            with self.assertRaises(AssertionError):
                self._assert_exact_condition_field_change(
                    base, two_field_mutation, "condition_id"
                )
            with self.assertRaises(AssertionError):
                self._assert_exact_condition_field_change(
                    base, base, "condition_id"
                )
        self.assertEqual(helper.call_count, 2)

    def test_condition_intrinsic_rejection_dimensions_and_order(self):
        pm = position_management
        by_id = {item.condition_id: item for item in self.base.plan.conditions}
        cases = (
            ("category", by_id["atm_iv"], _exact_dataclass_clone(by_id["atm_iv"], category=pm.PositionManagementCategory.EXIT), "^quantitative category is not allowed for metric$"),
            ("metric", by_id["nlv_multiple"], _exact_dataclass_clone(by_id["nlv_multiple"], metric=pm.PositionManagementMetric.BID_ASK_SPREAD_FRACTION), "^quantitative category is not allowed for metric$"),
            ("trigger", by_id["event_public"], _exact_dataclass_clone(by_id["event_public"], trigger=pm.PositionManagementQualitativeTrigger.EVENT_WINDOW_SHIFTS), "^qualitative trigger has a fixed category$"),
            ("comparison", by_id["nlv_multiple"], _exact_dataclass_clone(by_id["nlv_multiple"], comparison=pm.PositionManagementComparison.LESS_THAN_OR_EQUAL), "^quantitative comparison is not allowed for metric$"),
            ("authority", by_id["repeated_loss"], _exact_dataclass_clone(by_id["repeated_loss"], authority=pm.PositionManagementAuthority.CALLER), "^quantitative authority is not allowed for metric$"),
        )
        for label, original, changed, message in cases:
            conditions = tuple(changed if item is original else item for item in self.base.plan.conditions)
            plan = _exact_dataclass_clone(self.base.plan, conditions=conditions)
            result = _exact_dataclass_clone(self.base, plan=plan)
            reached = 0
            verifier = position_management._verify_plan_intrinsic
            def count(value):
                nonlocal reached
                reached += 1
                return verifier(value)
            with self.subTest(dimension=label), mock.patch.object(position_management, "_verify_plan_intrinsic", side_effect=count):
                with self.assertRaisesRegex(ValueError, message):
                    render_candidate_markdown(self.base.candidate if hasattr(self.base, "candidate") else self.base.assembly_result.record, "zh-CN", position_management_plan_result=result)
                self.assertEqual(reached, 1)
        reversed_plan = _exact_dataclass_clone(self.base.plan, conditions=tuple(reversed(self.base.plan.conditions)))
        reversed_result = _exact_dataclass_clone(self.base, plan=reversed_plan)
        with self.assertRaisesRegex(ValueError, "^conditions are not in canonical order$"):
            render_candidate_markdown(self.base.assembly_result.record, "zh-CN", position_management_plan_result=reversed_result)

    def test_condition_order_is_rendered_as_stored(self):
        ids = tuple(item.condition_id for item in self.base.plan.conditions)
        positions = tuple(self.output.index(f"- **条件 ID：** `{item}`") for item in ids)
        self.assertEqual(positions, tuple(sorted(positions)))
        self.assertEqual(tuple(item.condition_id for item in self.base.plan.conditions), ids)

    def test_safe_fence_direct_matrix_and_long_case(self):
        cases = (
            ("ordinary", ["```", "ordinary", "```"]), ("one `", ["```", "one `", "```"]),
            ("two `", ["```", "two `", "```"]), ("two ``", ["```", "two ``", "```"]),
            ("three ```", ["````", "three ```", "````"]), ("five `````", ["``````", "five `````", "``````"]),
            ("a``b```c", ["````", "a``b```c", "````"]),
            ("# h", ["```", "# h", "```"]), ("- l", ["```", "- l", "```"]),
            ("| t |", ["```", "| t |", "```"]),
            ("line one\nline two", ["```", "line one", "line two", "```"]),
            ("line one\r\nline two", ["```", "line one", "line two", "```"]),
            ("line one\rline two", ["```", "line one", "line two", "```"]),
            ("trail\\", ["```", "trail\\", "```"]),
            ("none", ["```", "none", "```"]), ("one\n", ["```", "one", "```"]), ("many\n\n", ["```", "many", "", "```"]),
        )
        for value, expected in cases:
            with self.subTest(value=repr(value)):
                self.assertEqual(_safe_fenced_lines(value), expected)
        value = "x" * 100000
        actual = _safe_fenced_lines(value)
        self.assertEqual(actual, ["```", value, "```"])
        self.assertEqual(len("\n".join(actual)), 100008)
        self.assertEqual(actual[1], value)

    def test_public_dynamic_safe_fence_routes(self):
        pm = position_management
        value = "# route ``` literal"
        expected = "````\n# route ``` literal\n````"
        base_condition = _golden_qualitative("review_event", pm.PositionManagementCategory.REASSESSMENT, pm.PositionManagementQualitativeTrigger.EVENT_WINDOW_SHIFTS)
        cases = (
            ("source", _partial_watch_plan_result(condition=dataclasses.replace(base_condition, source_reference=value)), 1),
            ("rationale", _partial_watch_plan_result(condition=dataclasses.replace(base_condition, rationale=value)), 1),
            ("candidate", _partial_watch_plan_result(candidate_id=value), 1),
            ("plan id", _partial_watch_plan_result(plan_id=value), 1),
            ("assembly id", _partial_watch_plan_result(assembly_id=value), 1),
        )
        for label, result, expected_count in cases:
            with self.subTest(route=label):
                output = render_candidate_markdown(result.assembly_result.record, "zh-CN", position_management_plan_result=result)
                self.assertIn(expected, output)
                self.assertEqual(output.count(expected), expected_count)
                self.assertNotIn("````python", output)
        structure = OptionStructure((OptionLeg(value, "call", 100.0, datetime.date(2030, 3, 3)),), 100000.0, 14)
        result = _partial_watch_plan_result(structure=structure)
        output = render_candidate_markdown(result.assembly_result.record, "zh-CN", position_management_plan_result=result)
        underlying = "````\n# ROUTE ``` LITERAL\n````"
        self.assertEqual(output.count(underlying), 2)
        self.assertIn("- **结构标的：**\n" + underlying, output)
        self.assertIn("- **期权腿 1 标的：**\n" + underlying, output)


class QualityFlagAuthorityTests(unittest.TestCase):
    FLAGS = tuple(CalculationQualityFlag)

    def _with_lineage_flags(self, result, flags, *, assembly=False):
        target = result.assembly_result.lineage if assembly else result.lineage
        lineage = _exact_dataclass_clone(target, quality_flags=flags)
        if assembly:
            assembly_result = _exact_dataclass_clone(result.assembly_result, lineage=lineage)
            return _exact_dataclass_clone(result, assembly_result=assembly_result)
        return _exact_dataclass_clone(result, lineage=lineage)

    def _with_both_lineage_flags(self, result, flags):
        assembly_lineage = _exact_dataclass_clone(result.assembly_result.lineage, quality_flags=flags)
        plan_lineage = _exact_dataclass_clone(result.lineage, quality_flags=flags)
        assembly_result = _exact_dataclass_clone(result.assembly_result, lineage=assembly_lineage)
        return _exact_dataclass_clone(result, assembly_result=assembly_result, lineage=plan_lineage)

    def test_formatter_only_quality_flag_matrix_uses_independent_literals(self):
        result = _watch_result()
        grouped = {"monetization": [], "reassessment": list(result.plan.conditions), "exit": []}
        cases = [
            ("zero", (), "- **质量标记：** 无"),
            ("decimal", (self.FLAGS[0],), "- **质量标记：** `decimal_to_float_converted`"),
            ("interpolated", (self.FLAGS[1],), "- **质量标记：** `interpolated`"),
            ("annualized", (self.FLAGS[2],), "- **质量标记：** `annualized`"),
            ("adjusted", (self.FLAGS[3],), "- **质量标记：** `adjusted_input_used`"),
            ("correction", (self.FLAGS[4],), "- **质量标记：** `correction_selected`"),
            ("composite", (self.FLAGS[5],), "- **质量标记：** `composite_input_used`"),
            ("assumption", (self.FLAGS[6],), "- **质量标记：** `assumption_applied`"),
            ("incomplete", (self.FLAGS[7],), "- **质量标记：** `incomplete_input_used`"),
            ("representative", (self.FLAGS[0], self.FLAGS[2], self.FLAGS[6]), "- **质量标记：** `decimal_to_float_converted`、`annualized`、`assumption_applied`"),
            ("all", self.FLAGS, "- **质量标记：** `decimal_to_float_converted`、`interpolated`、`annualized`、`adjusted_input_used`、`correction_selected`、`composite_input_used`、`assumption_applied`、`incomplete_input_used`"),
        ]
        for label, flags, expected in cases:
            with self.subTest(case=label):
                forged = self._with_lineage_flags(result, flags)
                lines = _render_plan_technical_block(forged, grouped)
                self.assertIn(expected, "\n".join(lines))
                if flags:
                    self.assertEqual("、" in expected, len(flags) > 1)
                self.assertNotIn(" .", expected)

    def test_reachability_contract_and_reachable_public_tuples(self):
        partial = _watch_result()
        complete = build_complete_investigate_plan_result()
        partial_flags = partial.assembly_result.lineage.quality_flags
        complete_flags = complete.assembly_result.lineage.quality_flags
        self.assertIn(CalculationQualityFlag.INCOMPLETE_INPUT_USED, partial_flags)
        self.assertIn(CalculationQualityFlag.DECIMAL_TO_FLOAT_CONVERTED, complete_flags)
        self.assertEqual(tuple(flag.value for flag in complete_flags), ("decimal_to_float_converted", "annualized", "assumption_applied"))
        for result in (partial, complete):
            self.assertEqual(result.lineage.quality_flags, result.assembly_result.lineage.quality_flags)
            output = render_candidate_markdown(result.assembly_result.record, "zh-CN", position_management_plan_result=result)
            expected = "- **质量标记：** " + ("、".join(f"`{flag.value}`" for flag in result.lineage.quality_flags))
            self.assertIn(expected, output)
            self.assertEqual(output.count("`incomplete_input_used`"), 1 if CalculationQualityFlag.INCOMPLETE_INPUT_USED in result.lineage.quality_flags else 0)
            self.assertNotIn(" 、", output)
            self.assertNotIn("、 ", output)
            self.assertNotIn("。", expected)
        self.assertEqual(tuple(flag.value for flag in partial_flags), ("incomplete_input_used",))

    def test_malformed_quality_flags_reach_completed_verifiers(self):
        result = build_complete_investigate_plan_result()
        flags = result.lineage.quality_flags
        class ForeignFlag:
            value = "incomplete_input_used"
        cases = (
            ("wrong order", _exact_dataclass_clone(result, lineage=_exact_dataclass_clone(result.lineage, quality_flags=tuple(reversed(flags)))), ValueError),
            ("duplicate", _exact_dataclass_clone(result, lineage=_exact_dataclass_clone(result.lineage, quality_flags=flags + flags)), ValueError),
            ("wrong outer", _exact_dataclass_clone(result, lineage=_exact_dataclass_clone(result.lineage, quality_flags=list(flags))), TypeError),
            ("wrong item", _exact_dataclass_clone(result, lineage=_exact_dataclass_clone(result.lineage, quality_flags=("incomplete_input_used",))), TypeError),
            ("foreign enum-like", _exact_dataclass_clone(result, lineage=_exact_dataclass_clone(result.lineage, quality_flags=(ForeignFlag(),))), TypeError),
        )
        for label, forged, exception in cases:
            with self.subTest(mutation=label):
                with self.assertRaises(exception):
                    report_module._validate_position_management_plan_result(forged)
        mismatch = _exact_dataclass_clone(result, lineage=_exact_dataclass_clone(result.lineage, quality_flags=()))
        self.assertNotEqual(
            mismatch.assembly_result.lineage.quality_flags,
            mismatch.lineage.quality_flags,
        )
        with self.assertRaisesRegex(
            ValueError,
            "^position-management quality flags must equal assembly flags$",
        ):
            report_module._validate_position_management_plan_result(mismatch)
        union_mismatch = self._with_both_lineage_flags(result, ())
        canonical_artifact_quality_flags = tuple(
            flag
            for flag in CalculationQualityFlag
            if any(
                flag in getattr(result.assembly_result, field).lineage.quality_flags
                for field in (
                    "volatility_environment_result", "tail_pricing_result",
                    "structure_liquidity_result", "structure_costs_result",
                    "scenario_valuation_result", "expiration_payoff_threshold_result",
                    "structure_affordability_result",
                )
            )
        )
        self.assertEqual(
            result.assembly_result.lineage.quality_flags,
            canonical_artifact_quality_flags,
        )
        self.assertEqual(union_mismatch.assembly_result.lineage.quality_flags, union_mismatch.lineage.quality_flags)
        self.assertNotEqual(
            union_mismatch.assembly_result.lineage.quality_flags,
            canonical_artifact_quality_flags,
        )
        self.assertEqual(
            union_mismatch.assembly_result.lineage.quality_flags,
            union_mismatch.lineage.quality_flags,
        )
        self.assertIs(union_mismatch.assembly_result.lineage.inputs, result.assembly_result.lineage.inputs)
        self.assertEqual(
            union_mismatch.assembly_result.lineage.inputs,
            result.assembly_result.lineage.inputs,
        )
        self.assertIs(union_mismatch.lineage.inputs, result.lineage.inputs)
        for before, after in zip(
            result.assembly_result.lineage.inputs,
            union_mismatch.assembly_result.lineage.inputs,
        ):
            self.assertIs(after, before)
        for field in (
            "volatility_environment_result", "tail_pricing_result", "structure_liquidity_result",
            "structure_costs_result", "scenario_valuation_result", "expiration_payoff_threshold_result",
            "structure_affordability_result",
        ):
            self.assertIs(getattr(union_mismatch.assembly_result, field), getattr(result.assembly_result, field))
        original_verifier = candidate_assembly._verify_candidate_research_record_assembly
        verifier_calls = 0
        def counted_verifier(value):
            nonlocal verifier_calls
            verifier_calls += 1
            return original_verifier(value)
        with mock.patch.object(
            candidate_assembly,
            "_verify_candidate_research_record_assembly",
            side_effect=counted_verifier,
        ):
            with self.assertRaisesRegex(
                ValueError,
                r"^assembly lineage does not correspond to the sidecar$",
            ):
                report_module._validate_position_management_plan_result(union_mismatch)
        self.assertGreaterEqual(verifier_calls, 1)


if __name__ == "__main__":
    unittest.main()
