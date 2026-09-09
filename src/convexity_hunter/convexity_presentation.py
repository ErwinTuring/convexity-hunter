"""Pure Markdown presentation of retained discrimination evidence.

No market calls or economic calculations. Primary approximations use four
decimal places, round-half-even; the audit retains exact original values.
"""

import datetime
import decimal
import json
from dataclasses import fields, is_dataclass
from enum import Enum

from .convexity_discrimination import (
    IndicativeMetricStatus,
    ProbabilityFreeConvexityDiscriminationResult,
)

__all__ = ("render_convexity_comparison_markdown",)


def _number(value, percent=False):
    # Integer formatting avoids ambient Decimal precision and float overflow.
    numerator = value.numerator * (100 if percent else 1) * 10000
    magnitude, remainder = divmod(abs(numerator), value.denominator)
    if remainder * 2 > value.denominator or (
        remainder * 2 == value.denominator and magnitude % 2
    ):
        magnitude += 1
    sign = "-" if numerator < 0 and magnitude else ""
    return f"{sign}{magnitude // 10000}.{magnitude % 10000:04d}" + (
        "%" if percent else "x"
    )


def _metric(metric, field, percent=False):
    if metric.status is not IndicativeMetricStatus.AVAILABLE:
        return "UNAVAILABLE[" + ",".join(
            reason.value for reason in metric.unavailable_reasons
        ) + "]"
    return _number(getattr(metric, field), percent)


def _audit(value):
    """Lossless scalar spellings and all dataclass fields, in retained order."""
    if isinstance(value, Enum):
        return {"enum": type(value).__name__, "name": value.name, "value": value.value}
    if is_dataclass(value):
        return {field.name: _audit(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (datetime.date, datetime.datetime)):
        return {"type": type(value).__name__, "value": value.isoformat()}
    if isinstance(value, decimal.Decimal):
        return {"type": "Decimal", "value": str(value)}
    if isinstance(value, tuple):
        return [_audit(item) for item in value]
    if value is None or type(value) in (str, int, bool):
        return value
    raise TypeError("Unsupported audit evidence type")


def render_convexity_comparison_markdown(result):
    """Render every comparison once in a compact table, plus full JSON audit.

Input is an existing immutable domain result; no domain reconstruction or
recalculation occurs here. Non-comparison Browser rows remain in the audit.
"""
    if type(result) is not ProbabilityFreeConvexityDiscriminationResult:
        raise TypeError("result must be ProbabilityFreeConvexityDiscriminationResult")
    authority = {
        "quote_authority": result.quote_batch.authority.name,
        **{name: getattr(result, name).name for name in (
            "payoff_geometry_authority", "exact_deliverable_verification",
            "maturity_authority", "hypothesis_maturity_alignment",
            "quote_reference_temporal_alignment", "cross_structure_quote_synchronicity",
            "reference_price_basis",
        )},
    }
    lines = ["# 条件式凸性比较", "", "```text"]
    lines.extend(f"{key} = {value}" for key, value in authority.items())
    lines.extend([
        "```", "",
        f"参考：{result.reference_price.latest_completed_session_date.isoformat()} "
        f"最新完整归一化收盘 {result.reference_price.close_price}；不是 current spot／同步现价。",
        "门槛为相对参考收盘的条件式到期价格变化；response 为到期总价值 / indicative ask，"
        "不是概率、预期回报、预测或净收益。premium/reference 不是可负担性、完整入场成本、"
        "最大损失或便宜程度。审计中的 indicative spread 不是 StructureLiquidity。",
        "期限匹配未建立不代表额外时间没有经济价值。无排名、推荐或默认选择。",
        "主表数值为四位小数近似；完整精确值和缺失原因见审计。"
        "门槛按下/上列出；不适用分支为 NOT_APPLICABLE（不是零）。",
        "", "## 主表", "",
        "|Expiration|Strike|Structure|Quote availability (leg order)|Aggregate indicative ask (points)|"
        "Premium/reference|1x 下/上|2x 下/上|Response -30/-20/-10%|Response +10/+20/+30%|",
        "|---|---|---|---|---|---|---|---|---|---|",
    ])
    for comparison in result.comparisons:
        row = comparison.structure.rows[0]
        premium = comparison.premium_to_reference
        hurdles = []
        for multiple in (1, 2):
            sides = []
            for side in ("DOWNSIDE", "UPSIDE"):
                metric = next((h for h in comparison.payoff_multiple_hurdles
                               if h.gross_value_multiple == multiple and h.side.name == side), None)
                sides.append("NOT_APPLICABLE" if metric is None else
                             _metric(metric, "relative_move_from_reference", True))
            hurdles.append(" / ".join(sides))
        responses = [_metric(comparison.response_ladder[i],
                             "gross_expiration_response_multiple")
                     for i in (1, 2, 3, 5, 6, 7)]
        ask = _metric(premium, "aggregate_ask_premium_points")
        if premium.status is IndicativeMetricStatus.AVAILABLE:
            ask = ask[:-1]  # points, not a response multiple
        cells = [str(row.expiration), str(row.strike), comparison.structure.grammar.name,
                 ", ".join(q.availability.name for q in comparison.quote_evidence), ask,
                 _metric(premium, "ratio_to_reference", True), *hurdles,
                 " / ".join(responses[:3]), " / ".join(responses[3:])]
        lines.append("|" + "|".join(cells) + "|")
    lines.extend(["", "## 完整审计", "",
                  f"未映射为比较结构的 Browser 行数：{len(result.non_comparison_rows)}；"
                  "其原始行及原因同样保留在下面的 non_comparison_rows。",
                  "完整结果字段含每腿标识、报价、九点 ladder、1x/2x/5x/10x、spread、"
                  "精确分子/分母、reference provenance 和 Browser 上下文。", "", "```json",
                  json.dumps({"schema_version": result.schema_version,
                              "authority": authority, "result": _audit(result)},
                             ensure_ascii=True, indent=2).replace("`", "\\u0060"), "```", ""])
    return "\n".join(lines)
