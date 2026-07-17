"""Immutable records used to assemble investigation reports."""

import datetime
import math
from dataclasses import dataclass
from numbers import Real
from typing import Optional, Tuple

from .evidence import (
    CandidateState,
    ClassifiedEvidence,
    EvidenceImpact,
    EvidenceKind,
    OptionLeg,
    OptionStructure,
    Scenario,
    StructureCosts,
    TailPricingSlice,
    VolatilityEnvironment,
)


def _validate_real(name: str, value: object) -> None:
    """Require a finite real number that is not a Boolean."""

    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _validate_positive_real(name: str, value: object) -> None:
    """Require a finite real number greater than zero."""

    _validate_real(name, value)
    if value <= 0:  # type: ignore[operator]
        raise ValueError(f"{name} must be greater than 0")


def _validate_nonnegative_real(name: str, value: object) -> None:
    """Require a finite real number greater than or equal to zero."""

    _validate_real(name, value)
    if value < 0:  # type: ignore[operator]
        raise ValueError(f"{name} must be 0 or greater")


def _validate_nonnegative_int(name: str, value: object) -> None:
    """Require a nonnegative integer that is not a Boolean."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be 0 or greater")


def _validate_date_only(name: str, value: object) -> None:
    """Require a calendar date without a time component."""

    if isinstance(value, datetime.datetime) or not isinstance(value, datetime.date):
        raise TypeError(f"{name} must be a date without a time component")


def _normalize_required_string(name: str, value: object) -> str:
    """Require and strip a non-empty string."""

    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _earliest_expiration(structure: OptionStructure) -> datetime.date:
    """Return the earliest expiration in a validated option structure."""

    return min(leg.expiration for leg in structure.legs)


@dataclass(frozen=True)
class LegVolatilityInput:
    """Starting implied volatility supplied for one exact option leg."""

    leg: OptionLeg
    base_iv: float

    def __post_init__(self) -> None:
        if not isinstance(self.leg, OptionLeg):
            raise TypeError("leg must be an OptionLeg")
        _validate_positive_real("base_iv", self.base_iv)


@dataclass(frozen=True)
class StructureLiquidity:
    """Total-position quote and weakest-leg liquidity evidence."""

    structure: OptionStructure
    as_of_date: datetime.date
    quoted_bid_value: float
    quoted_ask_value: float
    minimum_leg_open_interest: int
    minimum_leg_daily_volume: int
    quote_methodology: str

    def __post_init__(self) -> None:
        if not isinstance(self.structure, OptionStructure):
            raise TypeError("structure must be an OptionStructure")
        _validate_date_only("as_of_date", self.as_of_date)
        if self.as_of_date >= _earliest_expiration(self.structure):
            raise ValueError("as_of_date must be earlier than every leg expiration")
        _validate_nonnegative_real("quoted_bid_value", self.quoted_bid_value)
        _validate_positive_real("quoted_ask_value", self.quoted_ask_value)
        if self.quoted_ask_value < self.quoted_bid_value:
            raise ValueError("quoted_ask_value must be at least quoted_bid_value")
        _validate_nonnegative_int(
            "minimum_leg_open_interest", self.minimum_leg_open_interest
        )
        _validate_nonnegative_int(
            "minimum_leg_daily_volume", self.minimum_leg_daily_volume
        )
        quote_methodology = _normalize_required_string(
            "quote_methodology", self.quote_methodology
        )
        object.__setattr__(self, "quote_methodology", quote_methodology)

    @property
    def quoted_mid_value(self) -> float:
        """Return the total-position quote midpoint."""

        return (self.quoted_bid_value + self.quoted_ask_value) / 2

    @property
    def bid_ask_spread(self) -> float:
        """Return the absolute total-position bid-ask spread."""

        return self.quoted_ask_value - self.quoted_bid_value

    @property
    def bid_ask_spread_percentage(self) -> float:
        """Return the spread as a fraction of quoted midpoint value."""

        return self.bid_ask_spread / self.quoted_mid_value


@dataclass(frozen=True)
class ScenarioResult:
    """A supplied total-position valuation under one declared scenario.

    This record stores a result from a pricing engine or provider; it does not
    price options. P&L includes declared entry and estimated exit costs and is
    neither an expected return nor a probability-weighted forecast. For MVP
    long-only structures, economically rational abandonment floors liquidation
    value at zero when exit cost exceeds position value. This preserves loss
    bounded by entry cost while retaining the exit-cost estimate for audit.
    The floor does not apply to future short-option structures. Each
    ``LegVolatilityInput`` records the actual starting IV supplied for one
    declared structure leg. At expiration, these inputs remain for auditability
    even when terminal payoff no longer depends on volatility. Pricing
    methodology must describe the model or provider, rates, dividends,
    volatility-surface construction, interpolation, and limitations.
    """

    structure: OptionStructure
    as_of_date: datetime.date
    scenario: Scenario
    valuation_date: datetime.date
    base_underlying_price: float
    leg_volatility_inputs: Tuple[LegVolatilityInput, ...]
    estimated_position_value: float
    entry_cost_basis: float
    estimated_exit_cost: float
    pricing_methodology: str

    def __post_init__(self) -> None:
        if not isinstance(self.structure, OptionStructure):
            raise TypeError("structure must be an OptionStructure")
        if not isinstance(self.scenario, Scenario):
            raise TypeError("scenario must be a Scenario")
        _validate_date_only("as_of_date", self.as_of_date)
        _validate_date_only("valuation_date", self.valuation_date)

        earliest_expiration = _earliest_expiration(self.structure)
        if self.as_of_date >= earliest_expiration:
            raise ValueError("as_of_date must be earlier than every leg expiration")
        if self.valuation_date < self.as_of_date:
            raise ValueError("valuation_date must not be earlier than as_of_date")
        if self.valuation_date > earliest_expiration:
            raise ValueError("valuation_date must not be later than expiration")

        if self.scenario.valuation_time == "immediate":
            required_valuation_date = self.as_of_date
        elif self.scenario.valuation_time == "days_forward":
            required_valuation_date = self.as_of_date + datetime.timedelta(
                days=self.scenario.days_forward
            )
        elif self.scenario.valuation_time == "holding_horizon":
            required_valuation_date = self.as_of_date + datetime.timedelta(
                days=self.structure.expected_holding_days
            )
        else:
            required_valuation_date = earliest_expiration

        if required_valuation_date > earliest_expiration:
            raise ValueError("scenario valuation time resolves after expiration")
        if self.valuation_date != required_valuation_date:
            raise ValueError("valuation_date does not match the declared scenario")

        if not isinstance(self.leg_volatility_inputs, (tuple, list)):
            raise TypeError("leg_volatility_inputs must be a tuple or list")
        volatility_inputs = tuple(self.leg_volatility_inputs)
        if not all(
            isinstance(item, LegVolatilityInput) for item in volatility_inputs
        ):
            raise TypeError(
                "every leg_volatility_inputs item must be a LegVolatilityInput"
            )
        if len(volatility_inputs) != len(self.structure.legs):
            raise ValueError("one volatility input is required for every structure leg")
        input_legs = [item.leg for item in volatility_inputs]
        if len(set(input_legs)) != len(input_legs):
            raise ValueError("duplicate leg volatility inputs are not allowed")
        if any(leg not in self.structure.legs for leg in input_legs):
            raise ValueError("volatility input leg is not contained in the structure")
        ordered_inputs = tuple(
            next(item for item in volatility_inputs if item.leg == structure_leg)
            for structure_leg in self.structure.legs
        )
        object.__setattr__(self, "leg_volatility_inputs", ordered_inputs)

        _validate_positive_real("base_underlying_price", self.base_underlying_price)
        _validate_nonnegative_real(
            "estimated_position_value", self.estimated_position_value
        )
        _validate_positive_real("entry_cost_basis", self.entry_cost_basis)
        _validate_nonnegative_real("estimated_exit_cost", self.estimated_exit_cost)
        pricing_methodology = _normalize_required_string(
            "pricing_methodology", self.pricing_methodology
        )
        object.__setattr__(self, "pricing_methodology", pricing_methodology)

        # Cross-record consistency with StructureCosts and StructureLiquidity
        # belongs to the later CandidateResearchRecord, not this value record.

    @property
    def shocked_underlying_price(self) -> float:
        """Return the underlying price after the scenario's relative move."""

        return self.base_underlying_price * (1 + self.scenario.underlying_move)

    @property
    def base_ivs(self) -> Tuple[float, ...]:
        """Return starting IVs ordered consistently with structure legs."""

        return tuple(item.base_iv for item in self.leg_volatility_inputs)

    @property
    def shocked_ivs(self) -> Tuple[float, ...]:
        """Return each leg's IV after a parallel proportional shock.

        MVP v0.1 applies the same relative IV shock to every leg while
        preserving each starting IV. This does not model changes in skew,
        smile curvature, or term-structure shape and is not a complete
        volatility-surface scenario.
        """

        return tuple(
            base_iv * (1 + self.scenario.iv_change) for base_iv in self.base_ivs
        )

    @property
    def net_liquidation_value(self) -> float:
        """Return economically available value after estimated exit cost.

        A holder of an MVP long-only option structure may abandon the position
        rather than pay more to close it than it is worth, so the result is
        floored at zero. The estimated exit cost remains recorded on the
        scenario result. This treatment is not valid for future short-option
        structures, which are outside MVP v0.1.
        """

        return max(self.estimated_position_value - self.estimated_exit_cost, 0.0)

    @property
    def pnl_after_costs(self) -> float:
        """Return net liquidation value less the declared entry cost."""

        return self.net_liquidation_value - self.entry_cost_basis

    @property
    def return_on_entry_cost(self) -> float:
        """Return after-cost P&L as a fraction of declared entry cost."""

        return self.pnl_after_costs / self.entry_cost_basis

    @property
    def loss_is_within_entry_cost(self) -> bool:
        """Return the auditable MVP invariant that loss does not exceed entry cost."""

        return self.pnl_after_costs >= -self.entry_cost_basis


@dataclass(frozen=True)
class CandidateResearchRecord:
    """Canonical internally consistent research record for one candidate."""

    candidate_id: str
    state: CandidateState
    state_rationale: str
    as_of_date: datetime.date
    hypothesis: str
    structure: OptionStructure
    volatility_environment: Optional[VolatilityEnvironment] = None
    tail_pricing_slices: Tuple[TailPricingSlice, ...] = ()
    costs: Optional[StructureCosts] = None
    liquidity: Optional[StructureLiquidity] = None
    scenario_results: Tuple[ScenarioResult, ...] = ()
    evidence: Tuple[ClassifiedEvidence, ...] = ()
    falsification_conditions: Tuple[str, ...] = ()
    missing_data: Tuple[str, ...] = ()
    false_positive_reasons: Tuple[str, ...] = ()
    ai_interpretation: Optional[str] = None
    human_review_questions: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        candidate_id = _normalize_required_string("candidate_id", self.candidate_id)
        state_rationale = _normalize_required_string(
            "state_rationale", self.state_rationale
        )
        hypothesis = _normalize_required_string("hypothesis", self.hypothesis)
        if not isinstance(self.state, CandidateState):
            raise TypeError("state must be a CandidateState")
        _validate_date_only("as_of_date", self.as_of_date)
        if not isinstance(self.structure, OptionStructure):
            raise TypeError("structure must be an OptionStructure")
        if any(self.as_of_date >= leg.expiration for leg in self.structure.legs):
            raise ValueError("as_of_date must be earlier than every leg expiration")

        if self.volatility_environment is not None and not isinstance(
            self.volatility_environment, VolatilityEnvironment
        ):
            raise TypeError(
                "volatility_environment must be a VolatilityEnvironment or None"
            )
        if self.costs is not None and not isinstance(self.costs, StructureCosts):
            raise TypeError("costs must be a StructureCosts or None")
        if self.liquidity is not None and not isinstance(
            self.liquidity, StructureLiquidity
        ):
            raise TypeError("liquidity must be a StructureLiquidity or None")

        tail_slices = self._normalize_typed_collection(
            "tail_pricing_slices", self.tail_pricing_slices, TailPricingSlice
        )
        scenario_results = self._normalize_typed_collection(
            "scenario_results", self.scenario_results, ScenarioResult
        )
        evidence = self._normalize_typed_collection(
            "evidence", self.evidence, ClassifiedEvidence
        )
        falsification_conditions = self._normalize_text_collection(
            "falsification_conditions", self.falsification_conditions
        )
        missing_data = self._normalize_text_collection(
            "missing_data", self.missing_data
        )
        false_positive_reasons = self._normalize_text_collection(
            "false_positive_reasons", self.false_positive_reasons
        )
        human_review_questions = self._normalize_text_collection(
            "human_review_questions", self.human_review_questions
        )

        if not evidence:
            raise ValueError("evidence must contain at least one item")
        if not falsification_conditions:
            raise ValueError("falsification_conditions must contain at least one item")
        if not false_positive_reasons:
            raise ValueError("false_positive_reasons must contain at least one item")
        if not human_review_questions:
            raise ValueError("human_review_questions must contain at least one item")
        evidence_ids = [item.evidence_id for item in evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence IDs must be unique")

        expiration = _earliest_expiration(self.structure)
        tail_expirations = [item.expiration for item in tail_slices]
        if len(set(tail_expirations)) != len(tail_expirations):
            raise ValueError("tail-pricing expiration values must be unique")
        for item in tail_slices:
            if item.underlying != self.structure.underlying:
                raise ValueError("tail-pricing underlying must match structure")
            if item.as_of_date != self.as_of_date:
                raise ValueError("tail-pricing as_of_date must match candidate")
        if tail_slices and tail_expirations.count(expiration) != 1:
            raise ValueError(
                "tail pricing must contain exactly one structure-expiration slice"
            )
        tail_slices = tuple(sorted(tail_slices, key=lambda item: item.expiration))

        if self.volatility_environment is not None:
            if self.volatility_environment.underlying != self.structure.underlying:
                raise ValueError("volatility underlying must match structure")
            if self.volatility_environment.as_of_date != self.as_of_date:
                raise ValueError("volatility as_of_date must match candidate")

        if self.costs is not None:
            if self.costs.structure != self.structure:
                raise ValueError("cost structure must match candidate structure")
            if self.costs.as_of_date != self.as_of_date:
                raise ValueError("cost as_of_date must match candidate")
        if self.liquidity is not None:
            if self.liquidity.structure != self.structure:
                raise ValueError("liquidity structure must match candidate structure")
            if self.liquidity.as_of_date != self.as_of_date:
                raise ValueError("liquidity as_of_date must match candidate")
        if self.costs is not None and self.liquidity is not None:
            if not math.isclose(
                self.costs.quoted_mid_premium,
                self.liquidity.quoted_mid_value,
                rel_tol=1e-9,
                abs_tol=1e-9,
            ):
                raise ValueError("cost and liquidity quoted midpoints must match")

        scenarios = [item.scenario for item in scenario_results]
        if len(set(scenarios)) != len(scenarios):
            raise ValueError("scenario definitions must be unique")
        for result in scenario_results:
            if result.structure != self.structure:
                raise ValueError("scenario-result structure must match candidate")
            if result.as_of_date != self.as_of_date:
                raise ValueError("scenario-result as_of_date must match candidate")
            if self.costs is not None:
                if not math.isclose(
                    result.entry_cost_basis,
                    self.costs.total_entry_cost,
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                ):
                    raise ValueError("scenario entry cost must match structure costs")
                if not math.isclose(
                    result.base_underlying_price,
                    self.costs.underlying_price,
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                ):
                    raise ValueError(
                        "scenario underlying-price basis must match structure costs"
                    )

        if self.state is CandidateState.DATA_INSUFFICIENT and not missing_data:
            raise ValueError("data-insufficient candidates must disclose missing data")
        if self.state is CandidateState.INVESTIGATE:
            if self.volatility_environment is None:
                raise ValueError("investigate candidates require volatility evidence")
            if not tail_slices:
                raise ValueError("investigate candidates require tail-pricing evidence")
            if self.costs is None:
                raise ValueError("investigate candidates require structure costs")
            if self.liquidity is None:
                raise ValueError("investigate candidates require liquidity evidence")
            if not scenario_results:
                raise ValueError("investigate candidates require scenario results")
            if not any(
                item.impact is EvidenceImpact.SUPPORTS
                and item.kind
                in {
                    EvidenceKind.OBSERVED_FACT,
                    EvidenceKind.CALCULATED_METRIC,
                }
                for item in evidence
            ):
                raise ValueError(
                    "investigate candidates require supporting empirical evidence"
                )

        ai_interpretation = None
        if self.ai_interpretation is not None:
            ai_interpretation = _normalize_required_string(
                "ai_interpretation", self.ai_interpretation
            )

        object.__setattr__(self, "candidate_id", candidate_id)
        object.__setattr__(self, "state_rationale", state_rationale)
        object.__setattr__(self, "hypothesis", hypothesis)
        object.__setattr__(self, "tail_pricing_slices", tail_slices)
        object.__setattr__(self, "scenario_results", scenario_results)
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(
            self, "falsification_conditions", falsification_conditions
        )
        object.__setattr__(self, "missing_data", missing_data)
        object.__setattr__(self, "false_positive_reasons", false_positive_reasons)
        object.__setattr__(self, "ai_interpretation", ai_interpretation)
        object.__setattr__(
            self, "human_review_questions", human_review_questions
        )

    @staticmethod
    def _normalize_typed_collection(
        name: str, value: object, item_type: type
    ) -> tuple:
        """Normalize a tuple-or-list collection and validate its item type."""

        if not isinstance(value, (tuple, list)):
            raise TypeError(f"{name} must be a tuple or list")
        normalized = tuple(value)
        if not all(isinstance(item, item_type) for item in normalized):
            raise TypeError(f"every {name} item must be a {item_type.__name__}")
        return normalized

    @staticmethod
    def _normalize_text_collection(name: str, value: object) -> Tuple[str, ...]:
        """Normalize ordered text items and reject normalized duplicates."""

        if not isinstance(value, (tuple, list)):
            raise TypeError(f"{name} must be a tuple or list")
        normalized = tuple(
            _normalize_required_string(f"{name} item", item) for item in value
        )
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"{name} must not contain duplicate items")
        return normalized

    @property
    def expiration(self) -> datetime.date:
        """Return the earliest structure-leg expiration."""

        return _earliest_expiration(self.structure)

    @property
    def supporting_evidence(self) -> Tuple[ClassifiedEvidence, ...]:
        """Return evidence declared to support the hypothesis."""

        return tuple(
            item for item in self.evidence if item.impact is EvidenceImpact.SUPPORTS
        )

    @property
    def weakening_evidence(self) -> Tuple[ClassifiedEvidence, ...]:
        """Return evidence declared to weaken the hypothesis."""

        return tuple(
            item for item in self.evidence if item.impact is EvidenceImpact.WEAKENS
        )

    @property
    def neutral_evidence(self) -> Tuple[ClassifiedEvidence, ...]:
        """Return evidence with neutral declared impact."""

        return tuple(
            item for item in self.evidence if item.impact is EvidenceImpact.NEUTRAL
        )

    def _evidence_of_kind(
        self, kind: EvidenceKind
    ) -> Tuple[ClassifiedEvidence, ...]:
        """Return evidence with one declared classification."""

        return tuple(item for item in self.evidence if item.kind is kind)

    @property
    def observed_facts(self) -> Tuple[ClassifiedEvidence, ...]:
        """Return evidence classified as observed fact."""

        return self._evidence_of_kind(EvidenceKind.OBSERVED_FACT)

    @property
    def calculated_metrics(self) -> Tuple[ClassifiedEvidence, ...]:
        """Return evidence classified as calculated metric."""

        return self._evidence_of_kind(EvidenceKind.CALCULATED_METRIC)

    @property
    def assumptions(self) -> Tuple[ClassifiedEvidence, ...]:
        """Return evidence classified as assumption."""

        return self._evidence_of_kind(EvidenceKind.ASSUMPTION)

    @property
    def ai_interpretation_evidence(self) -> Tuple[ClassifiedEvidence, ...]:
        """Return evidence classified as AI interpretation."""

        return self._evidence_of_kind(EvidenceKind.AI_INTERPRETATION)


def _format_money(value: float) -> str:
    """Format a USD value without locale-dependent behavior."""

    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.2f}"


def _format_percentage(value: float) -> str:
    """Format a decimal ratio as a percentage."""

    return f"{value * 100:.2f}%"


def _format_decimal(value: float, precision: int = 6) -> str:
    """Format a decimal without unnecessary trailing zeroes."""

    formatted = f"{value:.{precision}f}".rstrip("0").rstrip(".")
    if formatted in {"", "-0"}:
        return "0"
    return formatted


def _format_gamma(value: float) -> str:
    """Format Gamma with enough precision to keep nonzero values visible."""

    formatted = _format_decimal(value, precision=12)
    if formatted == "0" and value != 0:
        return f"{value:.12g}"
    return formatted


def _format_leg_ivs(
    candidate: CandidateResearchRecord, values: Tuple[float, ...]
) -> str:
    """Format leg-level IVs in structure order."""

    return "; ".join(
        f"{leg.option_type.title()}: {_format_percentage(value)}"
        for leg, value in zip(candidate.structure.legs, values)
    )


def _append_evidence_group(
    lines: list, heading: str, items: Tuple[ClassifiedEvidence, ...]
) -> None:
    """Append one evidence-impact group with provenance fields."""

    lines.extend((f"### {heading}", ""))
    if not items:
        lines.extend(("None reported.", ""))
        return
    for item in items:
        lines.extend(
            (
                f"- **Evidence ID:** {item.evidence_id}",
                f"  - **Kind:** {item.kind.value}",
                f"  - **Statement:** {item.statement}",
                f"  - **Source:** {item.source or 'Not supplied'}",
                f"  - **Methodology:** {item.methodology or 'Not supplied'}",
            )
        )
    lines.append("")


def render_candidate_markdown(candidate: CandidateResearchRecord) -> str:
    """Render one candidate research record as deterministic Markdown."""

    if not isinstance(candidate, CandidateResearchRecord):
        raise TypeError("candidate must be a CandidateResearchRecord")

    lines = ["# Convexity Hunter Research Record", ""]
    if candidate.candidate_id.startswith("SYNTHETIC-"):
        lines.extend(
            (
                "> **SYNTHETIC DEMONSTRATION — NOT CURRENT MARKET DATA AND NOT A TRADE RECOMMENDATION**",
                "",
            )
        )
    lines.extend(
        (
            f"- **Candidate ID:** {candidate.candidate_id}",
            f"- **State:** {candidate.state.value}",
            f"- **State rationale:** {candidate.state_rationale}",
            f"- **As-of date:** {candidate.as_of_date.isoformat()}",
            f"- **Underlying:** {candidate.structure.underlying}",
            f"- **Structure type:** {candidate.structure.structure_type}",
            f"- **Expiration:** {candidate.expiration.isoformat()}",
            f"- **Expected holding days:** {candidate.structure.expected_holding_days}",
            "",
            "## Research hypothesis",
            "",
            candidate.hypothesis,
            "",
            "## Concrete option structure",
            "",
            "| Leg | Type | Strike | Expiration | Quantity | Multiplier |",
            "| ---: | --- | ---: | --- | ---: | ---: |",
        )
    )
    for index, leg in enumerate(candidate.structure.legs, start=1):
        lines.append(
            f"| {index} | {leg.option_type} | {_format_money(leg.strike)} | "
            f"{leg.expiration.isoformat()} | {leg.quantity} | "
            f"{leg.contract_multiplier} |"
        )

    lines.extend(("", "## Bounded downside and costs", ""))
    if candidate.costs is None:
        lines.extend(("Not supplied.", ""))
    else:
        costs = candidate.costs
        lines.extend(
            (
                f"- **Assumed portfolio value:** {_format_money(candidate.structure.assumed_portfolio_value)}",
                f"- **Quoted midpoint premium:** {_format_money(costs.quoted_mid_premium)}",
                f"- **Estimated spread cost:** {_format_money(costs.estimated_spread_cost)}",
                f"- **Commissions and fees:** {_format_money(costs.commissions_and_fees)}",
                f"- **Total entry cost:** {_format_money(costs.total_entry_cost)}",
                f"- **Maximum loss:** {_format_money(costs.maximum_loss)}",
                f"- **Maximum loss percentage:** {_format_percentage(costs.maximum_loss_percentage)}",
                f"- **Repeated-bet count:** {costs.repeated_bet_count}",
                f"- **Cumulative repeated-bet cost:** {_format_money(costs.cumulative_repeated_bet_cost)}",
                f"- **Cumulative repeated-bet percentage:** {_format_percentage(costs.cumulative_repeated_bet_percentage)}",
                f"- **Theta per day:** {_format_money(costs.theta_per_day)}",
                f"- **Total-position Gamma:** {_format_gamma(costs.gamma)}",
                f"- **Local Gamma P&L for a 1% move:** {_format_money(costs.gamma_pnl_for_one_percent_move)}",
                f"- **Local Gamma-cost ratio for a 1% move:** {_format_percentage(costs.gamma_cost_ratio_for_one_percent_move)}",
                f"- **Greeks methodology:** {costs.greeks_methodology}",
                "",
            )
        )

    lines.extend(("## Liquidity", ""))
    if candidate.liquidity is None:
        lines.extend(("Not supplied.", ""))
    else:
        liquidity = candidate.liquidity
        lines.extend(
            (
                f"- **Total-position bid:** {_format_money(liquidity.quoted_bid_value)}",
                f"- **Total-position ask:** {_format_money(liquidity.quoted_ask_value)}",
                f"- **Quoted midpoint:** {_format_money(liquidity.quoted_mid_value)}",
                f"- **Absolute bid-ask spread:** {_format_money(liquidity.bid_ask_spread)}",
                f"- **Bid-ask spread percentage:** {_format_percentage(liquidity.bid_ask_spread_percentage)}",
                f"- **Minimum leg open interest:** {liquidity.minimum_leg_open_interest}",
                f"- **Minimum leg daily volume:** {liquidity.minimum_leg_daily_volume}",
                f"- **Quote methodology:** {liquidity.quote_methodology}",
                "",
            )
        )

    lines.extend(("## Layer 1 — Volatility pricing environment", ""))
    if candidate.volatility_environment is None:
        lines.extend(("Not supplied.", ""))
    else:
        environment = candidate.volatility_environment
        lines.extend(
            (
                f"- **Reference tenor:** {environment.reference_tenor_days} days",
                f"- **ATM IV:** {_format_percentage(environment.atm_iv)}",
                f"- **IV percentile:** {_format_percentage(environment.iv_percentile)}",
                f"- **IV history observations:** {environment.iv_history_lookback_observations}",
                f"- **Historical median ATM IV:** {_format_percentage(environment.historical_median_atm_iv)}",
                f"- **ATM IV minus historical median:** {_format_percentage(environment.iv_vs_historical_median)}",
                f"- **Matched realized volatility:** {_format_percentage(environment.matched_realized_volatility)}",
                f"- **Matched realized window:** {environment.matched_realized_window_days} days",
                f"- **Implied-realized gap:** {_format_percentage(environment.implied_realized_gap)}",
                "",
                "| Tenor days | ATM IV |",
                "| ---: | ---: |",
            )
        )
        for point in environment.term_structure:
            lines.append(f"| {point.tenor_days} | {_format_percentage(point.atm_iv)} |")
        lines.append("")

    lines.extend(("## Layer 2 — Tail relative pricing", ""))
    if not candidate.tail_pricing_slices:
        lines.extend(("Not supplied.", ""))
    else:
        lines.extend(
            (
                "| Expiration | Days to expiration | ATM IV | 25Δ put IV | 25Δ call IV | Downside 25Δ skew | Upside 25Δ skew | Downside wing curvature | Upside wing curvature | Skew percentile | History observations |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            )
        )
        for item in candidate.tail_pricing_slices:
            lines.append(
                f"| {item.expiration.isoformat()} | {item.days_to_expiration} | "
                f"{_format_percentage(item.atm_iv)} | "
                f"{_format_percentage(item.put_25_delta_iv)} | "
                f"{_format_percentage(item.call_25_delta_iv)} | "
                f"{_format_percentage(item.downside_25_delta_skew)} | "
                f"{_format_percentage(item.upside_25_delta_skew)} | "
                f"{_format_percentage(item.downside_wing_curvature)} | "
                f"{_format_percentage(item.upside_wing_curvature)} | "
                f"{_format_percentage(item.skew_percentile)} | "
                f"{item.skew_history_lookback_observations} |"
            )
        lines.append("")
        for item in candidate.tail_pricing_slices:
            lines.append(
                f"- **{item.expiration.isoformat()} delta methodology:** "
                f"{item.delta_methodology}"
            )
        lines.append("")

    lines.extend(("## Scenario analysis", ""))
    if not candidate.scenario_results:
        lines.extend(("Not supplied.", ""))
    else:
        lines.extend(
            (
                "| Valuation time | Valuation date | Underlying move | IV shock | Shocked underlying | Base IVs | Shocked IVs | Position value | Exit cost | Net liquidation value | P&L after costs | Return on entry cost |",
                "| --- | --- | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |",
            )
        )
        for result in candidate.scenario_results:
            lines.append(
                f"| {result.scenario.valuation_time} | "
                f"{result.valuation_date.isoformat()} | "
                f"{_format_percentage(result.scenario.underlying_move)} | "
                f"{_format_percentage(result.scenario.iv_change)} | "
                f"{_format_money(result.shocked_underlying_price)} | "
                f"{_format_leg_ivs(candidate, result.base_ivs)} | "
                f"{_format_leg_ivs(candidate, result.shocked_ivs)} | "
                f"{_format_money(result.estimated_position_value)} | "
                f"{_format_money(result.estimated_exit_cost)} | "
                f"{_format_money(result.net_liquidation_value)} | "
                f"{_format_money(result.pnl_after_costs)} | "
                f"{_format_percentage(result.return_on_entry_cost)} |"
            )
        lines.append("")
        seen_methodologies = set()
        for result in candidate.scenario_results:
            if result.pricing_methodology not in seen_methodologies:
                seen_methodologies.add(result.pricing_methodology)
                lines.append(f"- **Pricing methodology:** {result.pricing_methodology}")
        lines.append("")
    lines.extend(
        (
            "Scenario values are supplied research results, not expected returns or probability-weighted forecasts.",
            "",
            "## Evidence",
            "",
        )
    )
    _append_evidence_group(lines, "Supporting evidence", candidate.supporting_evidence)
    _append_evidence_group(lines, "Weakening evidence", candidate.weakening_evidence)
    _append_evidence_group(lines, "Neutral evidence", candidate.neutral_evidence)

    lines.extend(("## Falsification conditions", ""))
    for index, condition in enumerate(candidate.falsification_conditions, start=1):
        lines.append(f"{index}. {condition}")

    lines.extend(("", "## Missing data", ""))
    if candidate.missing_data:
        lines.extend(f"- {item}" for item in candidate.missing_data)
    else:
        lines.append("None reported.")

    lines.extend(("", "## False-positive risks", ""))
    lines.extend(f"- {item}" for item in candidate.false_positive_reasons)

    lines.extend(("", "## AI interpretation", ""))
    lines.append(candidate.ai_interpretation or "Not supplied.")

    lines.extend(("", "## Human-review questions", ""))
    for index, question in enumerate(candidate.human_review_questions, start=1):
        lines.append(f"{index}. {question}")

    lines.extend(
        (
            "",
            "This record organizes research evidence. It does not recommend, execute, or guarantee any trade or investment outcome.",
        )
    )
    return "\n".join(lines).rstrip("\n") + "\n"
