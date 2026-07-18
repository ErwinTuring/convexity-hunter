"""Deterministic screening policy for candidate research records."""

import math
from dataclasses import dataclass
from enum import Enum
from numbers import Real
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from .evidence import CandidateState, TailPricingSlice
from .report import CandidateResearchRecord, ScenarioResult


class ScreeningReasonCode(str, Enum):
    """Stable deterministic screening reason codes in canonical order."""

    MAX_LOSS_HARD_LIMIT_EXCEEDED = "max_loss_hard_limit_exceeded"
    REPEATED_BET_HARD_LIMIT_EXCEEDED = "repeated_bet_hard_limit_exceeded"
    SPREAD_HARD_LIMIT_EXCEEDED = "spread_hard_limit_exceeded"
    OPEN_INTEREST_HARD_MINIMUM_FAILED = "open_interest_hard_minimum_failed"
    DAILY_VOLUME_HARD_MINIMUM_FAILED = "daily_volume_hard_minimum_failed"
    THETA_BURDEN_HARD_LIMIT_EXCEEDED = "theta_burden_hard_limit_exceeded"
    TARGET_MOVE_SCENARIO_NOT_PROFITABLE = "target_move_scenario_not_profitable"

    MISSING_COSTS = "missing_costs"
    MISSING_LIQUIDITY = "missing_liquidity"
    MISSING_VOLATILITY_ENVIRONMENT = "missing_volatility_environment"
    MISSING_STRUCTURE_EXPIRATION_TAIL_SLICE = (
        "missing_structure_expiration_tail_slice"
    )
    MISSING_TARGET_MOVE_SCENARIO = "missing_target_move_scenario"
    MISSING_VOLATILITY_CRUSH_SCENARIO = "missing_volatility_crush_scenario"

    MAX_LOSS_ABOVE_INVESTIGATE_LIMIT = "max_loss_above_investigate_limit"
    REPEATED_BET_ABOVE_INVESTIGATE_LIMIT = (
        "repeated_bet_above_investigate_limit"
    )
    SPREAD_ABOVE_INVESTIGATE_LIMIT = "spread_above_investigate_limit"
    OPEN_INTEREST_BELOW_INVESTIGATE_MINIMUM = (
        "open_interest_below_investigate_minimum"
    )
    DAILY_VOLUME_BELOW_INVESTIGATE_MINIMUM = (
        "daily_volume_below_investigate_minimum"
    )
    THETA_BURDEN_ABOVE_INVESTIGATE_LIMIT = (
        "theta_burden_above_investigate_limit"
    )
    VOLATILITY_ENVIRONMENT_NOT_SUPPORTIVE = (
        "volatility_environment_not_supportive"
    )
    TAIL_PRICING_NOT_SUPPORTIVE = "tail_pricing_not_supportive"

    AFFORDABILITY_GATES_PASSED = "affordability_gates_passed"
    LIQUIDITY_GATES_PASSED = "liquidity_gates_passed"
    VOLATILITY_ENVIRONMENT_SUPPORTIVE = "volatility_environment_supportive"
    TAIL_PRICING_SUPPORTIVE = "tail_pricing_supportive"
    TARGET_MOVE_SCENARIOS_PROFITABLE = "target_move_scenarios_profitable"


REJECT_REASON_ORDER = (
    ScreeningReasonCode.MAX_LOSS_HARD_LIMIT_EXCEEDED,
    ScreeningReasonCode.REPEATED_BET_HARD_LIMIT_EXCEEDED,
    ScreeningReasonCode.SPREAD_HARD_LIMIT_EXCEEDED,
    ScreeningReasonCode.OPEN_INTEREST_HARD_MINIMUM_FAILED,
    ScreeningReasonCode.DAILY_VOLUME_HARD_MINIMUM_FAILED,
    ScreeningReasonCode.THETA_BURDEN_HARD_LIMIT_EXCEEDED,
    ScreeningReasonCode.TARGET_MOVE_SCENARIO_NOT_PROFITABLE,
)

DATA_INSUFFICIENT_REASON_ORDER = (
    ScreeningReasonCode.MISSING_COSTS,
    ScreeningReasonCode.MISSING_LIQUIDITY,
    ScreeningReasonCode.MISSING_VOLATILITY_ENVIRONMENT,
    ScreeningReasonCode.MISSING_STRUCTURE_EXPIRATION_TAIL_SLICE,
    ScreeningReasonCode.MISSING_TARGET_MOVE_SCENARIO,
    ScreeningReasonCode.MISSING_VOLATILITY_CRUSH_SCENARIO,
)

WATCH_REASON_ORDER = (
    ScreeningReasonCode.MAX_LOSS_ABOVE_INVESTIGATE_LIMIT,
    ScreeningReasonCode.REPEATED_BET_ABOVE_INVESTIGATE_LIMIT,
    ScreeningReasonCode.SPREAD_ABOVE_INVESTIGATE_LIMIT,
    ScreeningReasonCode.OPEN_INTEREST_BELOW_INVESTIGATE_MINIMUM,
    ScreeningReasonCode.DAILY_VOLUME_BELOW_INVESTIGATE_MINIMUM,
    ScreeningReasonCode.THETA_BURDEN_ABOVE_INVESTIGATE_LIMIT,
    ScreeningReasonCode.VOLATILITY_ENVIRONMENT_NOT_SUPPORTIVE,
    ScreeningReasonCode.TAIL_PRICING_NOT_SUPPORTIVE,
)

INVESTIGATE_REASON_ORDER = (
    ScreeningReasonCode.AFFORDABILITY_GATES_PASSED,
    ScreeningReasonCode.LIQUIDITY_GATES_PASSED,
    ScreeningReasonCode.VOLATILITY_ENVIRONMENT_SUPPORTIVE,
    ScreeningReasonCode.TAIL_PRICING_SUPPORTIVE,
    ScreeningReasonCode.TARGET_MOVE_SCENARIOS_PROFITABLE,
)


def _normalize_required_string(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _validate_real(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _validate_nonnegative_real(name: str, value: object) -> None:
    _validate_real(name, value)
    if value < 0:  # type: ignore[operator]
        raise ValueError(f"{name} must be 0 or greater")


def _validate_nonnegative_int(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be 0 or greater")


_APPROVED_DEFAULT_POLICY_IDENTITY = (
    "synthetic-screening-v0.1",
    "0.1",
)

_APPROVED_DEFAULT_POLICY_VALUES: Mapping[str, object] = MappingProxyType(
    {
        "maximum_loss_hard_limit": 0.05,
        "repeated_bet_hard_limit": 0.15,
        "spread_hard_limit": 0.12,
        "open_interest_hard_minimum": 50,
        "daily_volume_hard_minimum": 10,
        "theta_burden_hard_limit": 0.50,
        "maximum_loss_investigate_limit": 0.025,
        "repeated_bet_investigate_limit": 0.08,
        "theta_burden_investigate_limit": 0.25,
        "spread_investigate_limit": 0.06,
        "open_interest_investigate_minimum": 200,
        "daily_volume_investigate_minimum": 50,
        "iv_percentile_support_maximum": 0.40,
        "iv_vs_historical_median_support_maximum": 0.0,
        "implied_realized_gap_support_maximum": 0.0,
        "minimum_volatility_support_signals": 2,
        "long_call_upside_skew_maximum": 0.015,
        "long_call_upside_curvature_maximum": 0.025,
        "long_put_downside_skew_maximum": 0.025,
        "long_put_downside_curvature_maximum": 0.035,
        "required_valuation_time": "holding_horizon",
        "long_call_target_underlying_move": 0.10,
        "long_put_target_underlying_move": -0.10,
        "long_straddle_downside_target_underlying_move": -0.10,
        "long_straddle_upside_target_underlying_move": 0.10,
        "target_iv_change": 0.0,
        "volatility_crush_underlying_move": 0.0,
        "volatility_crush_iv_change": -0.20,
        "scenario_relative_tolerance": 1e-9,
        "scenario_absolute_tolerance": 1e-12,
    }
)


@dataclass(frozen=True)
class ScreeningPolicy:
    """Immutable decision-affecting parameters for screening policy v0.1."""

    policy_id: str = _APPROVED_DEFAULT_POLICY_IDENTITY[0]
    policy_version: str = _APPROVED_DEFAULT_POLICY_IDENTITY[1]

    maximum_loss_hard_limit: float = _APPROVED_DEFAULT_POLICY_VALUES["maximum_loss_hard_limit"]  # type: ignore[assignment]
    repeated_bet_hard_limit: float = _APPROVED_DEFAULT_POLICY_VALUES["repeated_bet_hard_limit"]  # type: ignore[assignment]
    spread_hard_limit: float = _APPROVED_DEFAULT_POLICY_VALUES["spread_hard_limit"]  # type: ignore[assignment]
    open_interest_hard_minimum: int = _APPROVED_DEFAULT_POLICY_VALUES["open_interest_hard_minimum"]  # type: ignore[assignment]
    daily_volume_hard_minimum: int = _APPROVED_DEFAULT_POLICY_VALUES["daily_volume_hard_minimum"]  # type: ignore[assignment]
    theta_burden_hard_limit: float = _APPROVED_DEFAULT_POLICY_VALUES["theta_burden_hard_limit"]  # type: ignore[assignment]

    maximum_loss_investigate_limit: float = _APPROVED_DEFAULT_POLICY_VALUES["maximum_loss_investigate_limit"]  # type: ignore[assignment]
    repeated_bet_investigate_limit: float = _APPROVED_DEFAULT_POLICY_VALUES["repeated_bet_investigate_limit"]  # type: ignore[assignment]
    theta_burden_investigate_limit: float = _APPROVED_DEFAULT_POLICY_VALUES["theta_burden_investigate_limit"]  # type: ignore[assignment]

    spread_investigate_limit: float = _APPROVED_DEFAULT_POLICY_VALUES["spread_investigate_limit"]  # type: ignore[assignment]
    open_interest_investigate_minimum: int = _APPROVED_DEFAULT_POLICY_VALUES["open_interest_investigate_minimum"]  # type: ignore[assignment]
    daily_volume_investigate_minimum: int = _APPROVED_DEFAULT_POLICY_VALUES["daily_volume_investigate_minimum"]  # type: ignore[assignment]

    iv_percentile_support_maximum: float = _APPROVED_DEFAULT_POLICY_VALUES["iv_percentile_support_maximum"]  # type: ignore[assignment]
    iv_vs_historical_median_support_maximum: float = _APPROVED_DEFAULT_POLICY_VALUES["iv_vs_historical_median_support_maximum"]  # type: ignore[assignment]
    implied_realized_gap_support_maximum: float = _APPROVED_DEFAULT_POLICY_VALUES["implied_realized_gap_support_maximum"]  # type: ignore[assignment]
    minimum_volatility_support_signals: int = _APPROVED_DEFAULT_POLICY_VALUES["minimum_volatility_support_signals"]  # type: ignore[assignment]

    long_call_upside_skew_maximum: float = _APPROVED_DEFAULT_POLICY_VALUES["long_call_upside_skew_maximum"]  # type: ignore[assignment]
    long_call_upside_curvature_maximum: float = _APPROVED_DEFAULT_POLICY_VALUES["long_call_upside_curvature_maximum"]  # type: ignore[assignment]
    long_put_downside_skew_maximum: float = _APPROVED_DEFAULT_POLICY_VALUES["long_put_downside_skew_maximum"]  # type: ignore[assignment]
    long_put_downside_curvature_maximum: float = _APPROVED_DEFAULT_POLICY_VALUES["long_put_downside_curvature_maximum"]  # type: ignore[assignment]

    required_valuation_time: str = _APPROVED_DEFAULT_POLICY_VALUES["required_valuation_time"]  # type: ignore[assignment]
    long_call_target_underlying_move: float = _APPROVED_DEFAULT_POLICY_VALUES["long_call_target_underlying_move"]  # type: ignore[assignment]
    long_put_target_underlying_move: float = _APPROVED_DEFAULT_POLICY_VALUES["long_put_target_underlying_move"]  # type: ignore[assignment]
    long_straddle_downside_target_underlying_move: float = _APPROVED_DEFAULT_POLICY_VALUES["long_straddle_downside_target_underlying_move"]  # type: ignore[assignment]
    long_straddle_upside_target_underlying_move: float = _APPROVED_DEFAULT_POLICY_VALUES["long_straddle_upside_target_underlying_move"]  # type: ignore[assignment]
    target_iv_change: float = _APPROVED_DEFAULT_POLICY_VALUES["target_iv_change"]  # type: ignore[assignment]
    volatility_crush_underlying_move: float = _APPROVED_DEFAULT_POLICY_VALUES["volatility_crush_underlying_move"]  # type: ignore[assignment]
    volatility_crush_iv_change: float = _APPROVED_DEFAULT_POLICY_VALUES["volatility_crush_iv_change"]  # type: ignore[assignment]
    scenario_relative_tolerance: float = _APPROVED_DEFAULT_POLICY_VALUES["scenario_relative_tolerance"]  # type: ignore[assignment]
    scenario_absolute_tolerance: float = _APPROVED_DEFAULT_POLICY_VALUES["scenario_absolute_tolerance"]  # type: ignore[assignment]

    def __post_init__(self) -> None:
        policy_id = _normalize_required_string("policy_id", self.policy_id)
        policy_version = _normalize_required_string(
            "policy_version", self.policy_version
        )
        valuation_time = _normalize_required_string(
            "required_valuation_time", self.required_valuation_time
        ).lower()
        if valuation_time != "holding_horizon":
            raise ValueError(
                "required_valuation_time must be 'holding_horizon' for policy v0.1"
            )

        nonnegative_reals = (
            "maximum_loss_hard_limit",
            "repeated_bet_hard_limit",
            "spread_hard_limit",
            "theta_burden_hard_limit",
            "maximum_loss_investigate_limit",
            "repeated_bet_investigate_limit",
            "theta_burden_investigate_limit",
            "spread_investigate_limit",
            "iv_percentile_support_maximum",
            "iv_vs_historical_median_support_maximum",
            "implied_realized_gap_support_maximum",
            "long_call_upside_skew_maximum",
            "long_call_upside_curvature_maximum",
            "long_put_downside_skew_maximum",
            "long_put_downside_curvature_maximum",
            "scenario_relative_tolerance",
            "scenario_absolute_tolerance",
        )
        for name in nonnegative_reals:
            _validate_nonnegative_real(name, getattr(self, name))

        for name in (
            "open_interest_hard_minimum",
            "daily_volume_hard_minimum",
            "open_interest_investigate_minimum",
            "daily_volume_investigate_minimum",
        ):
            _validate_nonnegative_int(name, getattr(self, name))

        if (
            isinstance(self.minimum_volatility_support_signals, bool)
            or not isinstance(self.minimum_volatility_support_signals, int)
        ):
            raise TypeError("minimum_volatility_support_signals must be an integer")
        if not 1 <= self.minimum_volatility_support_signals <= 3:
            raise ValueError(
                "minimum_volatility_support_signals must be between 1 and 3"
            )

        maximum_pairs = (
            (
                "maximum_loss_investigate_limit",
                self.maximum_loss_investigate_limit,
                "maximum_loss_hard_limit",
                self.maximum_loss_hard_limit,
            ),
            (
                "repeated_bet_investigate_limit",
                self.repeated_bet_investigate_limit,
                "repeated_bet_hard_limit",
                self.repeated_bet_hard_limit,
            ),
            (
                "spread_investigate_limit",
                self.spread_investigate_limit,
                "spread_hard_limit",
                self.spread_hard_limit,
            ),
            (
                "theta_burden_investigate_limit",
                self.theta_burden_investigate_limit,
                "theta_burden_hard_limit",
                self.theta_burden_hard_limit,
            ),
        )
        for investigate_name, investigate, hard_name, hard in maximum_pairs:
            if investigate > hard:
                raise ValueError(f"{investigate_name} must not exceed {hard_name}")

        minimum_pairs = (
            (
                "open_interest_investigate_minimum",
                self.open_interest_investigate_minimum,
                "open_interest_hard_minimum",
                self.open_interest_hard_minimum,
            ),
            (
                "daily_volume_investigate_minimum",
                self.daily_volume_investigate_minimum,
                "daily_volume_hard_minimum",
                self.daily_volume_hard_minimum,
            ),
        )
        for investigate_name, investigate, hard_name, hard in minimum_pairs:
            if investigate < hard:
                raise ValueError(f"{investigate_name} must not be below {hard_name}")

        scenario_values = (
            "long_call_target_underlying_move",
            "long_put_target_underlying_move",
            "long_straddle_downside_target_underlying_move",
            "long_straddle_upside_target_underlying_move",
            "target_iv_change",
            "volatility_crush_underlying_move",
            "volatility_crush_iv_change",
        )
        for name in scenario_values:
            value = getattr(self, name)
            _validate_real(name, value)
            if value <= -1.0:
                raise ValueError(f"{name} must be greater than -1.0")

        if self.long_call_target_underlying_move <= 0:
            raise ValueError("long_call_target_underlying_move must be positive")
        if self.long_straddle_upside_target_underlying_move <= 0:
            raise ValueError(
                "long_straddle_upside_target_underlying_move must be positive"
            )
        if self.long_put_target_underlying_move >= 0:
            raise ValueError("long_put_target_underlying_move must be negative")
        if self.long_straddle_downside_target_underlying_move >= 0:
            raise ValueError(
                "long_straddle_downside_target_underlying_move must be negative"
            )

        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(self, "policy_version", policy_version)
        object.__setattr__(self, "required_valuation_time", valuation_time)

        if (policy_id, policy_version) == _APPROVED_DEFAULT_POLICY_IDENTITY:
            for name, approved_value in _APPROVED_DEFAULT_POLICY_VALUES.items():
                if getattr(self, name) != approved_value:
                    raise ValueError(
                        "the approved default policy identity requires the exact "
                        "approved v0.1 rule set"
                    )


_REASON_GROUP_BY_STATE = {
    CandidateState.REJECT: REJECT_REASON_ORDER,
    CandidateState.DATA_INSUFFICIENT: DATA_INSUFFICIENT_REASON_ORDER,
    CandidateState.WATCH: WATCH_REASON_ORDER,
    CandidateState.INVESTIGATE: INVESTIGATE_REASON_ORDER,
}


@dataclass(frozen=True)
class ScreeningDecision:
    """One immutable deterministic proposal separate from the research record."""

    proposed_state: CandidateState
    reason_codes: Tuple[ScreeningReasonCode, ...]
    policy_id: str
    policy_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.proposed_state, CandidateState):
            raise TypeError("proposed_state must be a CandidateState")
        if not isinstance(self.reason_codes, (tuple, list)):
            raise TypeError("reason_codes must be a tuple or list")
        reasons = tuple(self.reason_codes)
        if not reasons:
            raise ValueError("reason_codes must contain at least one item")
        if not all(isinstance(reason, ScreeningReasonCode) for reason in reasons):
            raise TypeError("every reason code must be a ScreeningReasonCode")
        if len(set(reasons)) != len(reasons):
            raise ValueError("reason_codes must not contain duplicates")

        canonical_group = _REASON_GROUP_BY_STATE[self.proposed_state]
        if any(reason not in canonical_group for reason in reasons):
            raise ValueError("reason_codes must belong to the proposed state group")
        if tuple(reason for reason in canonical_group if reason in reasons) != reasons:
            raise ValueError("reason_codes must follow canonical order")
        if (
            self.proposed_state is CandidateState.INVESTIGATE
            and reasons != INVESTIGATE_REASON_ORDER
        ):
            raise ValueError(
                "investigate decisions require the complete Investigate reason tuple"
            )

        policy_id = _normalize_required_string("policy_id", self.policy_id)
        policy_version = _normalize_required_string(
            "policy_version", self.policy_version
        )
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "policy_id", policy_id)
        object.__setattr__(self, "policy_version", policy_version)


def _ordered_reasons(
    canonical: Tuple[ScreeningReasonCode, ...],
    selected: set,
) -> Tuple[ScreeningReasonCode, ...]:
    return tuple(reason for reason in canonical if reason in selected)


def _find_required_scenario(
    candidate: CandidateResearchRecord,
    policy: ScreeningPolicy,
    underlying_move: float,
    iv_change: float,
) -> Optional[ScenarioResult]:
    matches = tuple(
        result
        for result in candidate.scenario_results
        if result.scenario.valuation_time == policy.required_valuation_time
        and math.isclose(
            result.scenario.underlying_move,
            underlying_move,
            rel_tol=policy.scenario_relative_tolerance,
            abs_tol=policy.scenario_absolute_tolerance,
        )
        and math.isclose(
            result.scenario.iv_change,
            iv_change,
            rel_tol=policy.scenario_relative_tolerance,
            abs_tol=policy.scenario_absolute_tolerance,
        )
    )
    if len(matches) > 1:
        raise ValueError("multiple ScenarioResult objects match a required scenario")
    return matches[0] if matches else None


def _required_scenarios(
    candidate: CandidateResearchRecord,
    policy: ScreeningPolicy,
) -> Tuple[Tuple[Optional[ScenarioResult], ...], Optional[ScenarioResult]]:
    structure_type = candidate.structure.structure_type
    if structure_type == "long_call":
        target_moves = (policy.long_call_target_underlying_move,)
    elif structure_type == "long_put":
        target_moves = (policy.long_put_target_underlying_move,)
    else:
        target_moves = (
            policy.long_straddle_downside_target_underlying_move,
            policy.long_straddle_upside_target_underlying_move,
        )
    targets = tuple(
        _find_required_scenario(
            candidate, policy, underlying_move, policy.target_iv_change
        )
        for underlying_move in target_moves
    )
    crush = _find_required_scenario(
        candidate,
        policy,
        policy.volatility_crush_underlying_move,
        policy.volatility_crush_iv_change,
    )
    return targets, crush


def _structure_expiration_tail_slice(
    candidate: CandidateResearchRecord,
) -> Optional[TailPricingSlice]:
    return next(
        (
            tail_slice
            for tail_slice in candidate.tail_pricing_slices
            if tail_slice.expiration == candidate.expiration
        ),
        None,
    )


def _volatility_is_supportive(
    candidate: CandidateResearchRecord, policy: ScreeningPolicy
) -> bool:
    environment = candidate.volatility_environment
    if environment is None:
        return False
    passing_signals = sum(
        (
            environment.iv_percentile <= policy.iv_percentile_support_maximum,
            environment.iv_vs_historical_median
            <= policy.iv_vs_historical_median_support_maximum,
            environment.implied_realized_gap
            <= policy.implied_realized_gap_support_maximum,
        )
    )
    return passing_signals >= policy.minimum_volatility_support_signals


def _tail_pricing_is_supportive(
    structure_type: str,
    tail_slice: TailPricingSlice,
    policy: ScreeningPolicy,
) -> bool:
    call_support = (
        tail_slice.upside_25_delta_skew
        <= policy.long_call_upside_skew_maximum
        and tail_slice.upside_wing_curvature
        <= policy.long_call_upside_curvature_maximum
    )
    put_support = (
        tail_slice.downside_25_delta_skew
        <= policy.long_put_downside_skew_maximum
        and tail_slice.downside_wing_curvature
        <= policy.long_put_downside_curvature_maximum
    )
    if structure_type == "long_call":
        return call_support
    if structure_type == "long_put":
        return put_support
    return call_support and put_support


def _decision(
    state: CandidateState,
    reasons: Tuple[ScreeningReasonCode, ...],
    policy: ScreeningPolicy,
) -> ScreeningDecision:
    return ScreeningDecision(
        proposed_state=state,
        reason_codes=reasons,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
    )


def screen_candidate(
    candidate: CandidateResearchRecord,
    policy: ScreeningPolicy,
) -> ScreeningDecision:
    """Return a deterministic proposal without mutating the research record."""

    if not isinstance(candidate, CandidateResearchRecord):
        raise TypeError("candidate must be a CandidateResearchRecord")
    if not isinstance(policy, ScreeningPolicy):
        raise TypeError("policy must be a ScreeningPolicy")

    targets, crush = _required_scenarios(candidate, policy)
    tail_slice = _structure_expiration_tail_slice(candidate)

    reject_reasons = set()
    if candidate.costs is not None:
        costs = candidate.costs
        theta_burden_percentage = (
            abs(costs.theta_per_day) * candidate.structure.expected_holding_days
        ) / costs.quoted_mid_premium
        if costs.maximum_loss_percentage > policy.maximum_loss_hard_limit:
            reject_reasons.add(
                ScreeningReasonCode.MAX_LOSS_HARD_LIMIT_EXCEEDED
            )
        if (
            costs.cumulative_repeated_bet_percentage
            > policy.repeated_bet_hard_limit
        ):
            reject_reasons.add(
                ScreeningReasonCode.REPEATED_BET_HARD_LIMIT_EXCEEDED
            )
        if theta_burden_percentage > policy.theta_burden_hard_limit:
            reject_reasons.add(
                ScreeningReasonCode.THETA_BURDEN_HARD_LIMIT_EXCEEDED
            )

    if candidate.liquidity is not None:
        liquidity = candidate.liquidity
        if liquidity.bid_ask_spread_percentage > policy.spread_hard_limit:
            reject_reasons.add(ScreeningReasonCode.SPREAD_HARD_LIMIT_EXCEEDED)
        if liquidity.minimum_leg_open_interest < policy.open_interest_hard_minimum:
            reject_reasons.add(
                ScreeningReasonCode.OPEN_INTEREST_HARD_MINIMUM_FAILED
            )
        if liquidity.minimum_leg_daily_volume < policy.daily_volume_hard_minimum:
            reject_reasons.add(
                ScreeningReasonCode.DAILY_VOLUME_HARD_MINIMUM_FAILED
            )

    if any(target is not None and target.pnl_after_costs <= 0 for target in targets):
        reject_reasons.add(
            ScreeningReasonCode.TARGET_MOVE_SCENARIO_NOT_PROFITABLE
        )
    if reject_reasons:
        return _decision(
            CandidateState.REJECT,
            _ordered_reasons(REJECT_REASON_ORDER, reject_reasons),
            policy,
        )

    missing_reasons = set()
    if candidate.costs is None:
        missing_reasons.add(ScreeningReasonCode.MISSING_COSTS)
    if candidate.liquidity is None:
        missing_reasons.add(ScreeningReasonCode.MISSING_LIQUIDITY)
    if candidate.volatility_environment is None:
        missing_reasons.add(ScreeningReasonCode.MISSING_VOLATILITY_ENVIRONMENT)
    if tail_slice is None:
        missing_reasons.add(
            ScreeningReasonCode.MISSING_STRUCTURE_EXPIRATION_TAIL_SLICE
        )
    if any(target is None for target in targets):
        missing_reasons.add(ScreeningReasonCode.MISSING_TARGET_MOVE_SCENARIO)
    if crush is None:
        missing_reasons.add(
            ScreeningReasonCode.MISSING_VOLATILITY_CRUSH_SCENARIO
        )
    if missing_reasons:
        return _decision(
            CandidateState.DATA_INSUFFICIENT,
            _ordered_reasons(DATA_INSUFFICIENT_REASON_ORDER, missing_reasons),
            policy,
        )

    costs = candidate.costs
    liquidity = candidate.liquidity
    assert costs is not None
    assert liquidity is not None
    assert tail_slice is not None
    theta_burden_percentage = (
        abs(costs.theta_per_day) * candidate.structure.expected_holding_days
    ) / costs.quoted_mid_premium

    watch_reasons = set()
    if costs.maximum_loss_percentage > policy.maximum_loss_investigate_limit:
        watch_reasons.add(
            ScreeningReasonCode.MAX_LOSS_ABOVE_INVESTIGATE_LIMIT
        )
    if (
        costs.cumulative_repeated_bet_percentage
        > policy.repeated_bet_investigate_limit
    ):
        watch_reasons.add(
            ScreeningReasonCode.REPEATED_BET_ABOVE_INVESTIGATE_LIMIT
        )
    if liquidity.bid_ask_spread_percentage > policy.spread_investigate_limit:
        watch_reasons.add(ScreeningReasonCode.SPREAD_ABOVE_INVESTIGATE_LIMIT)
    if (
        liquidity.minimum_leg_open_interest
        < policy.open_interest_investigate_minimum
    ):
        watch_reasons.add(
            ScreeningReasonCode.OPEN_INTEREST_BELOW_INVESTIGATE_MINIMUM
        )
    if liquidity.minimum_leg_daily_volume < policy.daily_volume_investigate_minimum:
        watch_reasons.add(
            ScreeningReasonCode.DAILY_VOLUME_BELOW_INVESTIGATE_MINIMUM
        )
    if theta_burden_percentage > policy.theta_burden_investigate_limit:
        watch_reasons.add(
            ScreeningReasonCode.THETA_BURDEN_ABOVE_INVESTIGATE_LIMIT
        )
    if not _volatility_is_supportive(candidate, policy):
        watch_reasons.add(
            ScreeningReasonCode.VOLATILITY_ENVIRONMENT_NOT_SUPPORTIVE
        )
    if not _tail_pricing_is_supportive(
        candidate.structure.structure_type, tail_slice, policy
    ):
        watch_reasons.add(ScreeningReasonCode.TAIL_PRICING_NOT_SUPPORTIVE)

    if watch_reasons:
        return _decision(
            CandidateState.WATCH,
            _ordered_reasons(WATCH_REASON_ORDER, watch_reasons),
            policy,
        )

    return _decision(
        CandidateState.INVESTIGATE,
        INVESTIGATE_REASON_ORDER,
        policy,
    )
