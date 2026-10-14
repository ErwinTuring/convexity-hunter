"""Pure presentation for the current Core application records."""

import json as _json
from dataclasses import dataclass as _dataclass
from datetime import date as _Date
from decimal import Decimal as _Decimal
from typing import Mapping as _Mapping
from typing import Optional as _Optional
from typing import Tuple as _Tuple


__all__ = (
    "CoreCompactSummary",
    "CoreCompactLeg",
    "CoreCompactCase",
    "compact_summary",
    "compact",
    "report",
)


def _application_types():
    from .core_application import CoreCaseRecord, CoreCaseSet, CoreDirectResult

    return CoreCaseRecord, CoreCaseSet, CoreDirectResult


def _kernel_result(value: object):
    from .core_research import CoreResearchResult

    if type(value) is not CoreResearchResult:
        raise TypeError("record must retain CoreResearchResult or be blocked")
    return value


def _text(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, _Decimal):
        return str(value)
    return str(getattr(value, "value", value))


def _merged_reasons(application_reasons: object, kernel_result: object) -> _Tuple[str, ...]:
    merged = []
    for reason in tuple(application_reasons) + tuple(
        getattr(kernel_result, "reasons", ())
    ):
        value = getattr(reason, "value", reason)
        if value not in merged:
            merged.append(value)
    return tuple(merged)


@_dataclass(frozen=True)
class CoreCompactSummary:
    """Small immutable summary; it contains no provider or network behavior."""

    entry_origin: str
    case_count: int
    unavailable_count: int
    disposition_counts: _Tuple[tuple, ...]
    case_ids: _Tuple[str, ...]
    reasons: _Tuple[str, ...]
    case_summaries: _Tuple["CoreCompactCase", ...] = ()
    unavailable_case_ids: _Tuple[str, ...] = ()

    @property
    def disposition_map(self) -> _Mapping[str, int]:
        return dict(self.disposition_counts)

    @property
    def count_examined(self) -> int:
        return self.case_count + self.unavailable_count

    @property
    def table(self) -> _Tuple["CoreCompactCase", ...]:
        """Structured comparison rows; no pre-generated per-case prose."""

        return self.case_summaries

    @property
    def cards(self) -> _Tuple["CoreCompactCase", ...]:
        """Alias for callers presenting each compact row as a card."""

        return self.case_summaries


@_dataclass(frozen=True)
class CoreCompactLeg:
    """Exact leg identity retained by one compact comparison row."""

    leg_id: str
    underlying: str
    option_type: str
    expiration: _Date
    strike: _Decimal
    quantity: int
    contract_multiplier: int


@_dataclass(frozen=True)
class CoreCompactCase:
    case_id: str
    disposition: str
    geometry_status: str
    ask_basis_per_underlying_unit: _Optional[_Decimal]
    reasons: _Tuple[str, ...]
    structure_kind: str = "unknown"
    legs: _Tuple[CoreCompactLeg, ...] = ()
    budget_status: str = "unknown"
    single_cost_upper_bound: _Optional[_Decimal] = None
    repeated_cost_upper_bound: _Optional[_Decimal] = None
    single_loss_fraction: _Optional[_Decimal] = None
    repeated_loss_fraction: _Optional[_Decimal] = None


@_dataclass(frozen=True)
class _EntryFeeScenario:
    scenario_id: str
    entry_fee: _Optional[_Decimal]
    partial_subtotal: _Optional[_Decimal]
    unavailable_reason: _Optional[str]


@_dataclass(frozen=True)
class _ConditionalEntryFeeScenarioView:
    total_order_quantity: _Optional[int]
    fixed: _EntryFeeScenario
    tier_first_50: _EntryFeeScenario


def compact_summary(case_set: object) -> CoreCompactSummary:
    """Return deterministic compact data from retained case records only."""

    _CoreCaseRecord, CoreCaseSet, _CoreDirectResult = _application_types()
    if type(case_set) is not CoreCaseSet:
        raise TypeError("compact_summary requires CoreCaseSet")
    cases = case_set.cases
    unavailable = case_set.unavailable
    counts = {}
    ids = []
    reasons = list(case_set.reasons)
    details = []
    for case in cases:
        if type(case) is not _CoreCaseRecord:
            raise TypeError("case set contains a non-CoreCaseRecord")
        case_id = case.case_id
        ids.append(case_id)
        result = _kernel_result(case.kernel_result)
        disposition = result.disposition.value
        counts[disposition] = counts.get(disposition, 0) + 1
        case_reasons = tuple(item.value for item in result.reasons) + case.reasons
        reasons.extend(case_reasons)
        legs = tuple(
            CoreCompactLeg(
                leg_id=leg.leg_id,
                underlying=leg.underlying,
                option_type=leg.option_type.value,
                expiration=leg.expiration,
                strike=leg.strike,
                quantity=leg.quantity,
                contract_multiplier=leg.contract_multiplier,
            )
            for leg in result.request.structure.legs
        )
        if len(legs) == 1:
            structure_kind = legs[0].option_type
        elif len(legs) == 2 and {leg.option_type for leg in legs} == {"CALL", "PUT"}:
            structure_kind = "STRADDLE"
        else:
            structure_kind = "UNSUPPORTED"
        details.append(
            CoreCompactCase(
                case_id=case_id,
                disposition=disposition,
                geometry_status=result.geometry.status.value,
                ask_basis_per_underlying_unit=result.geometry.ask_basis_per_underlying_unit,
                reasons=case_reasons,
                structure_kind=structure_kind,
                legs=legs,
                budget_status=result.budget_stress.status.value,
                single_cost_upper_bound=result.budget_stress.single_cost_upper_bound,
                repeated_cost_upper_bound=result.budget_stress.repeated_cost_upper_bound,
                single_loss_fraction=result.budget_stress.single_loss_fraction,
                repeated_loss_fraction=result.budget_stress.repeated_loss_fraction,
            )
        )
    for item in unavailable:
        if not case_set.reasons:
            reasons.extend(item.reasons)
    return CoreCompactSummary(
        entry_origin=case_set.entry_origin,
        case_count=len(cases),
        unavailable_count=len(unavailable),
        disposition_counts=tuple(sorted(counts.items())),
        case_ids=tuple(ids),
        reasons=tuple(reasons),
        case_summaries=tuple(details),
        unavailable_case_ids=tuple(item.case_id for item in unavailable),
    )


compact = compact_summary


def report(record: object, locale: str = "zh-CN") -> str:
    """Render one retained record without querying a provider.

    The renderer intentionally reports evidence state and authority, never a
    recommendation or an executable-price claim.
    """

    if type(locale) is not str or locale != "zh-CN":
        raise ValueError("only locale='zh-CN' is supported")
    CoreCaseRecord, _CoreCaseSet, CoreDirectResult = _application_types()
    if type(record) is CoreDirectResult:
        case_id = "direct:" + ":".join(
            item.provider_identifier for item in record.exact_verifications
        )
        result = record.kernel_result
        reasons = record.reasons
        disclosure = (
            f"maturity_authority={record.maturity_authority.value}; "
            f"hypothesis_maturity_alignment={record.hypothesis_maturity_alignment.value}; "
            f"quote_reference_temporal_alignment={record.quote_reference_temporal_alignment}; "
            f"cross_structure_quote_synchronicity={record.cross_structure_quote_synchronicity}"
        )
    elif type(record) is CoreCaseRecord:
        case_id = record.case_id
        result = record.kernel_result
        reasons = record.reasons
        disclosure = (
            "maturity_authority=" + record.maturity_authority.value + "; "
            "hypothesis_maturity_alignment="
            + record.discovery_request.hypothesis_maturity_alignment.value
            if record.discovery_request is not None
            else "hypothesis_maturity_alignment=unknown"
        )
    else:
        raise TypeError("report requires CoreCaseRecord or CoreDirectResult")

    reasons = _merged_reasons(reasons, result)
    return _render_core_report(case_id, result, reasons, disclosure)


def _render_core_report(
    case_id: str, result: object, reasons: _Tuple[str, ...], disclosure: str
) -> str:
    """Render an already selected Core result with caller-owned disclosures.

    This private pure helper lets Host archives render lazily from the typed
    numerical result without reconstructing a CoreCaseContext.
    """
    lines = ["核心研究报告", f"案例: {case_id}", disclosure]
    if type(result) is not type(None):
        result = _kernel_result(result)
        request = result.request
        structure = request.structure
        structure_kind = (
            "STRADDLE"
            if len(structure.legs) == 2
            and {leg.option_type.value for leg in structure.legs} == {"CALL", "PUT"}
            else structure.legs[0].option_type.value
            if len(structure.legs) == 1
            else "UNSUPPORTED"
        )
        geometry = result.geometry
        cash = result.cash_ledger
        budget = result.budget_stress
        risk = request.risk_policy
        lines.extend(
            (
                f"处置: {result.disposition.value}",
                "结构: "
                + _text(
                    (
                        structure_kind,
                        tuple(
                            (
                                leg.leg_id,
                                leg.underlying,
                                leg.option_type.value,
                                leg.expiration.isoformat(),
                                _text(leg.strike),
                                leg.quantity,
                                leg.contract_multiplier,
                            )
                            for leg in structure.legs
                        ),
                    )
                ),
                f"几何: {geometry.status.value}; payoff_authority={_text(geometry.payoff_authority)}",
                f"ask_basis_per_underlying_unit={_text(geometry.ask_basis_per_underlying_unit)}",
                "到期门槛: "
                + "; ".join(
                    f"{h.gross_value_multiple}x/{h.side.value}={_text(h.terminal_underlying_price)}"
                    for h in geometry.hurdles
                ),
                "1x/2x/5x/10x 是到期毛价值相对指示性 ask 的倍数，不是利润倍数或正式盈亏平衡；已知 ask 金额不等于总进入成本或实际最大损失；条件预算不证明真实账户安全。",
                f"cash observed={_text(cash.observed_ask_cost)}; known_total={_text(cash.known_total)}; conditional_total_upper_bound={_text(cash.conditional_total_upper_bound)}",
                f"cash unknown_components={_text(cash.unknown_component_ids)}; missing_required={_text(cash.missing_required_component_ids)}",
                f"repeat policy count={_text(risk.repeat_count if risk is not None else None)}; single_limit={_text(risk.maximum_single_loss_fraction if risk is not None else None)}; repeated_limit={_text(risk.maximum_repeated_loss_fraction if risk is not None else None)}",
                f"budget status={budget.status.value}; single={_text(budget.single_cost_upper_bound)}; repeated={_text(budget.repeated_cost_upper_bound)}; single_fraction={_text(budget.single_loss_fraction)}; repeated_fraction={_text(budget.repeated_loss_fraction)}",
                "sensitivity="
                + _text(
                    tuple(
                        (
                            point.point.point_id,
                            _text(point.gross_response_multiple),
                        )
                        for point in result.sensitivity_results.points
                    )
                    if result.sensitivity_results is not None
                    else None
                ),
                "provenance="
                + _text(
                    request.provenance.source_reference.source_id
                    if request.provenance.source_reference is not None
                    else None
                ),
                "ask_authority=INDICATIVE_ONLY; executable_price_claim=none; underpricing_claim=not_established",
            )
        )
        profile = _profile_from_request_provenance(request)
        if profile is not None and profile.version in ("v0.2", "v0.3", "v0.4"):
            policy = profile.snapshot()["cash_sensitivity_policy"]
            funding_disclosure = (
                "own_cash_funding_research_intent=ADOPTED; funding_cost=UNKNOWN; no_zero_cost_or_execution_control_inference"
                if profile.version == "v0.4"
                else "actual_tariff=unknown; funding_strategy=not_assumed; no zero-cost inference"
            )
            lines.append(
                "现金与敏感性政策: "
                + _text(
                    (
                        "profile=standard-research-profile:{}".format(profile.version),
                        "policy={}:{}".format(policy["policy_id"], policy["version"]),
                        "observed_position_ask_basis=" + policy["observed_position_ask_basis"],
                        "conditional_premium_factor=" + policy["conditional_premium_factor"],
                        "unknown_required_costs=entry_fees,strategy_dependent_funding,strategy_dependent_exit,strategy_dependent_settlement",
                        funding_disclosure,
                    )
                )
            )
            sensitivity = request.sensitivity
            grid_results = (
                tuple(
                    (
                        item.point.point_id,
                        item.point.description,
                        item.point.terminal_underlying_price,
                        item.point.ask_per_leg,
                        item.conditional_gross_payoff_per_underlying_unit,
                        item.conditional_position_payoff,
                        item.gross_response_multiple,
                        tuple(
                            (
                                hurdle.gross_value_multiple,
                                hurdle.side.value,
                                hurdle.status.value,
                                hurdle.terminal_underlying_price,
                                hurdle.reason,
                            )
                            for hurdle in item.gross_hurdles
                        ),
                        item.unavailable_reason,
                    )
                    for item in result.sensitivity_results.points
                )
                if result.sensitivity_results is not None
                else None
            )
            lines.append(
                "固定基线敏感性网格: "
                + _text(
                    (
                        None if sensitivity is None else sensitivity.description,
                        grid_results,
                    )
                )
            )
            if profile.version == "v0.3":
                governance = profile.snapshot()["strategy_governance"]
                lines.append(
                    "策略治理意图（非执行控制）: "
                    + _text(
                        (
                            "profile=standard-research-profile:v0.3",
                            "funding_rule=" + governance["funding_rule"],
                            "lifecycle_intent=" + governance["lifecycle_intent"],
                            "exercise_rule=" + governance["exercise_rule"],
                            "execution_enforcement=" + governance["execution_enforcement"],
                            "automatic_exercise_protection="
                            + governance["automatic_exercise_protection"],
                            "研究意图不证明券商控制、已完成平仓或放弃，也不构成自动行权保护；被动不操作不等于已放弃；到期收益几何不是提前退出估值。",
                        )
                    )
                )
            elif profile.version == "v0.4":
                governance = profile.snapshot()["strategy_governance"]
                lines.append(
                    "策略治理意图（非执行控制）: "
                    + _text(
                        (
                            "profile=standard-research-profile:v0.4; unchanged_governance_policy=v0.3",
                            "funding_rule=" + governance["funding_rule"],
                            "lifecycle_intent=" + governance["lifecycle_intent"],
                            "exercise_rule=" + governance["exercise_rule"],
                            "execution_enforcement=" + governance["execution_enforcement"],
                            "automatic_exercise_protection="
                            + governance["automatic_exercise_protection"],
                            "研究意图不证明券商控制、已完成平仓或放弃，也不构成自动行权保护；被动不操作不等于已放弃；到期收益几何不是提前退出估值。",
                        )
                    )
                )
                lines.extend(
                    _render_conditional_entry_fee_scenarios(
                        _conditional_entry_fee_scenario_view(request, profile),
                        profile.snapshot()["conditional_entry_fee_policy"],
                    )
                )
    else:
        lines.extend(("处置: unknown", "几何: unknown", "cash: unknown"))
    lines.append("原因: " + ("、".join(reasons) if reasons else "无"))
    lines.append("本报告仅保留条件性研究证据，不构成方向预测、交易建议或可执行价格声明。")
    return "\n".join(lines)


def _profile_from_request_provenance(request: object):
    """Resolve only an exact registered Host profile embedded by its factory."""

    provenance = getattr(request, "provenance", None)
    description = getattr(provenance, "description", None)
    marker = "profile_snapshot="
    if type(description) is not str or marker not in description:
        return None
    try:
        snapshot = _json.loads(description.split(marker, 1)[1])
        from .host_profile import _profile_for_snapshot

        profile = _profile_for_snapshot(snapshot)
        expected = profile.request_factory(
            case_id=request.case_id,
            structure=request.structure,
            context=None,
        )
        return profile if request == expected else None
    except (TypeError, ValueError, _json.JSONDecodeError):
        return None


def _conditional_entry_fee_scenario_view(
    request: object, profile: object
) -> _ConditionalEntryFeeScenarioView:
    """Build a private, presentation-only view from an exact v0.4 Core record."""

    from .core_research import (
        CoreCostLedger,
        CoreStructure,
        _decimal_from_fraction,
        _fraction_from_decimal,
        _validate_core_structure,
    )
    from .host_profile import StandardResearchProfile, _supported_cash_structure

    def unavailable(reason: str, total_quantity: _Optional[int] = None):
        return _ConditionalEntryFeeScenarioView(
            total_order_quantity=total_quantity,
            fixed=_EntryFeeScenario("FIXED", None, None, reason),
            tier_first_50=_EntryFeeScenario("TIER_FIRST_50", None, None, reason),
        )

    if type(profile) is not StandardResearchProfile or profile.version != "v0.4":
        return unavailable("registered_v0_4_profile_required")
    structure = getattr(request, "structure", None)
    if type(structure) is not CoreStructure:
        return unavailable("unsupported_structure")
    try:
        _validate_core_structure(structure)
    except (TypeError, ValueError):
        return unavailable("invalid_or_missing_ask")
    if not _supported_cash_structure(structure):
        return unavailable("unsupported_structure")
    if any(leg.currency != "USD" for leg in structure.legs):
        return unavailable("unsupported_currency")
    asks = tuple(leg.ask_per_underlying_unit for leg in structure.legs)
    if any(
        type(ask) is not _Decimal or not ask.is_finite() or ask <= _Decimal("0")
        for ask in asks
    ):
        return unavailable("invalid_or_missing_ask")
    if any(type(leg.quantity) is not int or leg.quantity < 1 for leg in structure.legs):
        return unavailable("invalid_quantity")
    total_quantity = sum(leg.quantity for leg in structure.legs)
    ledger = getattr(request, "cost_ledger", None)
    if (
        type(ledger) is not CoreCostLedger
        or type(ledger.premium_bound) is not _Decimal
        or not ledger.premium_bound.is_finite()
        or ledger.premium_bound < _Decimal("0")
    ):
        return unavailable("conditional_premium_budget_unavailable", total_quantity)

    policy = profile.snapshot()["conditional_entry_fee_policy"]
    commission_policy = policy["commission"]
    minimum = _fraction_from_decimal(_Decimal(commission_policy["minimum_per_leg"]))
    threshold = _Decimal(commission_policy["ask_threshold"])
    above_rate = _fraction_from_decimal(
        _Decimal(commission_policy["rate_above_threshold_per_contract"])
    )
    lower_rate = _fraction_from_decimal(
        _Decimal(commission_policy["rate_at_or_below_threshold_per_contract"])
    )
    other_rate = _fraction_from_decimal(
        _Decimal(policy["other_buy_fees_per_contract"])
    )
    premium_fraction = _fraction_from_decimal(ledger.premium_bound)

    def scenario(scenario_id: str, platform_text: str) -> _EntryFeeScenario:
        platform_rate = _fraction_from_decimal(_Decimal(platform_text))
        total_fee = _fraction_from_decimal(_Decimal("0"))
        for leg, ask in zip(structure.legs, asks):
            rate = above_rate if ask > threshold else lower_rate
            commission = max(minimum, leg.quantity * rate)
            total_fee += commission
            total_fee += leg.quantity * platform_rate
            total_fee += leg.quantity * other_rate
        return _EntryFeeScenario(
            scenario_id=scenario_id,
            entry_fee=_decimal_from_fraction(total_fee),
            partial_subtotal=_decimal_from_fraction(premium_fraction + total_fee),
            unavailable_reason=None,
        )

    fixed_rate = policy["scenarios"][0]["platform_fee_per_contract"]
    fixed = scenario("FIXED", fixed_rate)
    tier_policy = policy["scenarios"][1]
    if total_quantity > tier_policy["maximum_total_order_quantity"]:
        tier = _EntryFeeScenario(
            "TIER_FIRST_50", None, None, "total_order_quantity_exceeds_50"
        )
    else:
        tier = scenario("TIER_FIRST_50", tier_policy["platform_fee_per_contract"])
    return _ConditionalEntryFeeScenarioView(total_quantity, fixed, tier)


def _render_conditional_entry_fee_scenarios(
    view: _ConditionalEntryFeeScenarioView, policy: object
) -> _Tuple[str, ...]:
    """Render fixed tariff assumptions without changing Core authority or bounds."""

    def render_scenario(item: _EntryFeeScenario) -> str:
        if item.unavailable_reason is not None:
            return "{}: unavailable[{}]".format(
                item.scenario_id, item.unavailable_reason
            )
        return "{}: entry_fee_USD={}; partial_subtotal_USD={}".format(
            item.scenario_id, item.entry_fee, item.partial_subtotal
        )

    scenarios = policy["scenarios"]
    quantity = (
        "unknown" if view.total_order_quantity is None else str(view.total_order_quantity)
    )
    tier_condition = "prior_monthly_contracts=0; total_order_quantity<=50"
    return (
        "条件化买入开仓费用情景（仅v0.4详情展示，不写入CoreCostLedger）",
        "公开费率来源={}；核对日期={}；币种={}；适用性=CONDITIONAL/NOT_VERIFIED（仅假设美股个股期权，Core未验证equity/index或账户套餐；指数附加费未纳入，实际品种适用性未验证）".format(
            policy["source_url"], policy["verified_on"], policy["currency"]
        ),
        "固定顺序情景：FIXED平台费USD {}/张；TIER_FIRST_50平台费USD {}/张（仅条件{}；不满足时不可用）".format(
            scenarios[0]["platform_fee_per_contract"],
            scenarios[1]["platform_fee_per_contract"],
            tier_condition,
        ),
        "a=CoreLeg.ask_per_underlying_unit，单位USD/标的单位；不是头寸权利金或每张合约现金额。每腿佣金=max(USD {}, q*(USD {}若该腿指示性ask>USD {}，否则USD {})); 其他列示买入费用=USD {}/张；单腿单买单并假设一个交易日内全部成交；Q=sum(q_i)={}（不乘合约乘数）".format(
            policy["commission"]["minimum_per_leg"],
            policy["commission"]["rate_above_threshold_per_contract"],
            policy["commission"]["ask_threshold"],
            policy["commission"]["rate_at_or_below_threshold_per_contract"],
            policy["other_buy_fees_per_contract"],
            quantity,
        ),
        render_scenario(view.fixed),
        render_scenario(view.tier_first_50),
        "部分小计=既有1.10条件性指示ask保费预算+情景买入费用；非总现金需求、全生命周期成本或最大损失；entry_fees及资金/退出/结算仍为UNKNOWN；生存/可负担性未建立。",
        "指示性ask仅选择假设佣金分支，实际成交价/账户费率/舍入规则未验证；不含卖出费、促销、额外服务、汇兑或未来费率变化；不构成推荐、交易建议或可执行报价。",
    )
