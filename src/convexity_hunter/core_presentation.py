"""Pure presentation for the current Core application records."""

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
    else:
        lines.extend(("处置: unknown", "几何: unknown", "cash: unknown"))
    lines.append("原因: " + ("、".join(reasons) if reasons else "无"))
    lines.append("本报告仅保留条件性研究证据，不构成方向预测、交易建议或可执行价格声明。")
    return "\n".join(lines)
