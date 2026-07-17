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

    lines.extend((f"#### {heading}", ""))
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


def _render_technical_english(candidate: CandidateResearchRecord) -> str:
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
            "### Research hypothesis",
            "",
            candidate.hypothesis,
            "",
            "### Concrete option structure",
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

    lines.extend(("", "### Bounded downside and costs", ""))
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

    lines.extend(("### Liquidity", ""))
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

    lines.extend(("### Layer 1 — Volatility pricing environment", ""))
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

    lines.extend(("### Layer 2 — Tail relative pricing", ""))
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

    lines.extend(("### Scenario analysis", ""))
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
            "### Evidence",
            "",
        )
    )
    _append_evidence_group(lines, "Supporting evidence", candidate.supporting_evidence)
    _append_evidence_group(lines, "Weakening evidence", candidate.weakening_evidence)
    _append_evidence_group(lines, "Neutral evidence", candidate.neutral_evidence)

    lines.extend(("### Falsification conditions", ""))
    for index, condition in enumerate(candidate.falsification_conditions, start=1):
        lines.append(f"{index}. {condition}")

    lines.extend(("", "### Missing data", ""))
    if candidate.missing_data:
        lines.extend(f"- {item}" for item in candidate.missing_data)
    else:
        lines.append("None reported.")

    lines.extend(("", "### False-positive risks", ""))
    lines.extend(f"- {item}" for item in candidate.false_positive_reasons)

    lines.extend(("", "### AI interpretation", ""))
    lines.append(candidate.ai_interpretation or "Not supplied.")

    lines.extend(("", "### Human-review questions", ""))
    for index, question in enumerate(candidate.human_review_questions, start=1):
        lines.append(f"{index}. {question}")

    lines.extend(
        (
            "",
            "This record organizes research evidence. It does not recommend, execute, or guarantee any trade or investment outcome.",
        )
    )
    return "\n".join(lines).rstrip("\n") + "\n"


REPORT_TEXT = {
    "en": {
        "title": "# Convexity Hunter Research Record",
        "warning": "> **SYNTHETIC DEMONSTRATION — NOT CURRENT MARKET DATA AND NOT A TRADE RECOMMENDATION**",
        "overview": "## Plain-language overview",
        "technical": "## Technical research details",
        "sections": (
            "### 1. What is being studied?",
            "### 2. What is the current status?",
            "### 3. Why might it deserve attention?",
            "### 4. Why is caution still necessary?",
            "### 5. How much could be lost?",
            "### 6. What happens in the supplied scenarios?",
            "### 7. What should a human verify next?",
        ),
        "structure_explanations": {
            "long_call": "A fixed entry cost is paid for nonlinear upside exposure. The position may lose the declared entry cost if the underlying does not rise enough before expiration.",
            "long_put": "A fixed entry cost is paid for nonlinear downside exposure or protection. The position may lose the declared entry cost if the underlying does not fall enough before expiration.",
            "long_straddle": "This report studies buying a call and a put with the same strike and expiration. It does not require choosing an up or down direction in advance, but the underlying must move enough during the holding period to overcome premium, time decay, and trading costs.",
        },
        "state_labels": {
            "reject": "reject", "watch": "watch", "investigate": "investigate",
            "data_insufficient": "data_insufficient",
        },
        "structure_labels": {
            "long_call": "long_call", "long_put": "long_put",
            "long_straddle": "long_straddle",
        },
        "valuation_labels": {
            "immediate": "immediate", "days_forward": "days_forward",
            "holding_horizon": "holding_horizon", "expiration": "expiration",
        },
        "labels": {
            "underlying": "Underlying", "structure": "Structure type",
            "strikes": "Strike or strikes", "expiration": "Expiration",
            "holding": "Expected holding days", "state": "State",
            "rationale": "State rationale", "weakening": "Weakening evidence",
            "missing": "Missing data", "entry": "Total entry cost",
            "loss": "Maximum loss", "loss_pct": "Maximum loss percentage",
            "repeat_count": "Repeated-bet count",
            "repeat_cost": "Cumulative repeated-bet cost",
            "repeat_pct": "Cumulative repeated-bet percentage",
            "questions": "Human-review questions",
            "falsification": "Conditions that would overturn the research hypothesis",
        },
        "status_note": "This status is supplied by the research record. Milestone 1.1 does not independently calculate it, and it is not a trade recommendation.",
        "no_support": "No supporting evidence is currently reported.",
        "no_weakening": "No weakening evidence is currently reported.",
        "no_missing": "No missing data is currently reported.",
        "loss_note": "For supported long-only MVP structures, the declared maximum modeled loss is the total entry cost.",
        "loss_missing": "Loss information was not supplied.",
        "scenario_counts": "Among the supplied scenarios: {positive} positive, {negative} negative, and {zero} zero P&L results.",
        "highest": "Highest result among supplied scenarios",
        "lowest": "Lowest result among supplied scenarios",
        "scenario_line": "{label}: {time}; underlying move {move}; IV shock {iv}; P&L after costs {pnl}.",
        "scenario_note": "This compares only the scenarios supplied in the report. It does not represent every possible outcome and is not a return forecast.",
        "no_scenarios": "No scenario results were supplied.",
        "footer": "This record organizes research evidence. It does not recommend, execute, or guarantee any trade or investment outcome.",
    },
    "zh-CN": {
        "title": "# Convexity Hunter 候选研究报告",
        "warning": "> **合成演示数据——不是当前市场数据，也不是交易建议**",
        "overview": "## 通俗概要：先看懂这份报告",
        "technical": "## 技术研究明细",
        "sections": (
            "### 1. 研究的是什么？", "### 2. 当前状态是什么？",
            "### 3. 为什么可能值得关注？", "### 4. 为什么仍然需要谨慎？",
            "### 5. 最多可能损失多少？", "### 6. 在给定情景下，结果可能怎样？",
            "### 7. 接下来需要人工核实什么？",
        ),
        "structure_explanations": {
            "long_call": "这份报告研究支付固定入场成本、获得非线性上涨敞口的买入看涨期权。如果标的在到期前上涨幅度不足，仓位可能损失已声明的全部入场成本。",
            "long_put": "这份报告研究支付固定入场成本、获得非线性下跌敞口或保护的买入看跌期权。如果标的在到期前下跌幅度不足，仓位可能损失已声明的全部入场成本。",
            "long_straddle": "本报告研究的是：同时买入相同执行价和到期日的看涨期权与看跌期权。它不需要提前押注上涨或下跌，但标的需要在持有期间出现足够大的波动，才可能覆盖期权费、时间损耗和交易成本。",
        },
        "state_labels": {
            "reject": "拒绝（reject）", "watch": "观察（watch）",
            "investigate": "深入研究（investigate）",
            "data_insufficient": "数据不足（data_insufficient）",
        },
        "structure_labels": {
            "long_call": "买入看涨（long_call）", "long_put": "买入看跌（long_put）",
            "long_straddle": "买入跨式（long_straddle）",
        },
        "valuation_labels": {
            "immediate": "即时（immediate）", "days_forward": "未来指定日期（days_forward）",
            "holding_horizon": "持有期末（holding_horizon）", "expiration": "到期（expiration）",
        },
        "labels": {
            "underlying": "标的", "structure": "结构类型", "strikes": "执行价",
            "expiration": "到期日", "holding": "预计持有天数", "state": "状态",
            "rationale": "状态理由", "weakening": "不利或弱化证据",
            "missing": "尚未提供的数据", "entry": "总入场成本", "loss": "最大损失",
            "loss_pct": "最大损失占组合比例", "repeat_count": "重复尝试次数",
            "repeat_cost": "累计重复尝试成本", "repeat_pct": "累计重复尝试成本占比",
            "questions": "人工复核问题", "falsification": "可能推翻研究假设的证伪条件",
        },
        "status_note": "该状态来自已提供的研究记录。里程碑 1.1 不会独立计算状态，该状态也不是交易建议。",
        "no_support": "目前没有已报告的支持证据。",
        "no_weakening": "目前没有已报告的弱化证据。",
        "no_missing": "目前没有已报告的缺失数据。",
        "loss_note": "对于当前 MVP 支持的只买入期权结构，已声明的最大模型损失等于总入场成本。",
        "loss_missing": "未提供损失信息。",
        "scenario_counts": "在已提供的情景中：{positive} 个盈利、{negative} 个亏损、{zero} 个盈亏为零。",
        "highest": "已提供情景中的最高结果", "lowest": "已提供情景中的最低结果",
        "scenario_line": "{label}：{time}；标的变动 {move}；IV 变动 {iv}；扣除成本后盈亏 {pnl}。",
        "scenario_note": "这里只比较报告中已提供的情景，不代表所有可能结果，也不是收益预测。",
        "no_scenarios": "未提供情景结果。",
        "footer": "本记录用于整理研究证据，不推荐、不执行，也不保证任何交易或投资结果。",
    },
}


ZH_TECHNICAL_REPLACEMENTS = {
    "- **Candidate ID:**": "- **候选 ID:**", "- **State:**": "- **状态:**",
    "- **State rationale:**": "- **状态理由:**", "- **As-of date:**": "- **数据截至日期:**",
    "- **Underlying:**": "- **标的:**", "- **Structure type:**": "- **结构类型:**",
    "- **Expiration:**": "- **到期日:**", "- **Expected holding days:**": "- **预计持有天数:**",
    "### Research hypothesis": "### 研究假设", "### Concrete option structure": "### 具体期权结构",
    "### Bounded downside and costs": "### 有限损失与成本", "### Liquidity": "### 流动性",
    "### Layer 1 — Volatility pricing environment": "### 第一层——整体波动率定价环境",
    "### Layer 2 — Tail relative pricing": "### 第二层——尾部相对定价",
    "### Scenario analysis": "### 情景分析", "### Evidence": "### 证据",
    "#### Supporting evidence": "#### 支持证据", "#### Weakening evidence": "#### 弱化证据",
    "#### Neutral evidence": "#### 中性证据", "### Falsification conditions": "### 证伪条件",
    "### Missing data": "### 缺失数据", "### False-positive risks": "### 假阳性风险",
    "### AI interpretation": "### AI 解读", "### Human-review questions": "### 人工复核问题",
    "| Leg | Type | Strike | Expiration | Quantity | Multiplier |": "| 期权腿 | 类型 | 执行价 | 到期日 | 数量 | 合约乘数 |",
    "| Valuation time | Valuation date | Underlying move | IV shock | Shocked underlying | Base IVs | Shocked IVs | Position value | Exit cost | Net liquidation value | P&L after costs | Return on entry cost |": "| 估值时间 | 估值日期 | 标的变动 | IV 变动 | 变动后标的价格 | 基础 IV | 变动后 IV | 仓位价值 | 退出成本 | 净清算价值 | 扣除成本后盈亏 | 入场成本回报率 |",
    "| Tenor days | ATM IV |": "| 期限天数 | 平值隐含波动率（ATM IV） |",
    "| Expiration | Days to expiration | ATM IV | 25Δ put IV | 25Δ call IV | Downside 25Δ skew | Upside 25Δ skew | Downside wing curvature | Upside wing curvature | Skew percentile | History observations |": "| 到期日 | 距到期天数 | ATM IV | 25Δ 看跌 IV | 25Δ 看涨 IV | 下行 25Δ 偏斜 | 上行 25Δ 偏斜 | 下行翼曲率 | 上行翼曲率 | 偏斜历史百分位 | 历史观测数 |",
    "**Assumed portfolio value:**": "**假设组合价值:**", "**Quoted midpoint premium:**": "**报价中点权利金:**",
    "**Estimated spread cost:**": "**预估买卖价差成本:**", "**Commissions and fees:**": "**佣金与费用:**",
    "**Total entry cost:**": "**总入场成本:**", "**Maximum loss:**": "**最大损失:**",
    "**Maximum loss percentage:**": "**最大损失占组合比例:**", "**Repeated-bet count:**": "**重复尝试次数:**",
    "**Cumulative repeated-bet cost:**": "**累计重复尝试成本:**", "**Cumulative repeated-bet percentage:**": "**累计重复尝试成本占比:**",
    "**Theta per day:**": "**每日 Theta:**", "**Total-position Gamma:**": "**总仓位 Gamma:**",
    "**Local Gamma P&L for a 1% move:**": "**标的变动 1% 的局部 Gamma 盈亏:**",
    "**Local Gamma-cost ratio for a 1% move:**": "**标的变动 1% 的局部 Gamma 成本比:**",
    "**Greeks methodology:**": "**希腊字母方法说明:**", "**Total-position bid:**": "**总仓位买价:**",
    "**Total-position ask:**": "**总仓位卖价:**", "**Quoted midpoint:**": "**报价中点:**",
    "**Absolute bid-ask spread:**": "**绝对买卖价差:**", "**Bid-ask spread percentage:**": "**买卖价差百分比:**",
    "**Minimum leg open interest:**": "**各腿最小未平仓量:**", "**Minimum leg daily volume:**": "**各腿最小当日成交量:**",
    "**Quote methodology:**": "**报价方法:**", "**Reference tenor:**": "**参考期限:**",
    "**ATM IV:**": "**平值隐含波动率（ATM IV）:**", "**IV percentile:**": "**隐含波动率历史百分位:**",
    "**IV history observations:**": "**IV 历史观测数:**", "**Historical median ATM IV:**": "**历史平值隐含波动率中位数:**",
    "**ATM IV minus historical median:**": "**ATM IV 减历史中位数:**", "**Matched realized volatility:**": "**匹配期限实现波动率:**",
    "**Matched realized window:**": "**实现波动率匹配窗口:**", "**Implied-realized gap:**": "**隐含波动率与实现波动率差:**",
    " delta methodology:**": " Delta 方法:**", "**Pricing methodology:**": "**定价方法:**",
    "**Evidence ID:**": "**证据 ID:**", "**Kind:**": "**证据类型:**", "**Statement:**": "**陈述:**",
    "**Source:**": "**来源:**", "**Methodology:**": "**方法:**", "Not supplied.": "未提供。",
    "None reported.": "未报告。", "Scenario values are supplied research results, not expected returns or probability-weighted forecasts.": "情景数值是已提供的研究结果，不是预期收益，也不是概率加权预测。",
    "long_straddle": "买入跨式（long_straddle）", "long_call": "买入看涨（long_call）",
    "long_put": "买入看跌（long_put）", "| call |": "| 看涨（call） |", "| put |": "| 看跌（put） |",
    "| immediate |": "| 即时（immediate） |", "| holding_horizon |": "| 持有期末（holding_horizon） |",
    "| expiration |": "| 到期（expiration） |", "| days_forward |": "| 未来指定日期（days_forward） |",
    "Call:": "看涨（call）:", "Put:": "看跌（put）:", "calculated_metric": "计算指标（calculated_metric）",
    "observed_fact": "观察事实（observed_fact）", "assumption": "假设（assumption）",
    "ai_interpretation": "AI 解读（ai_interpretation）",
    "watch": "观察（watch）", "reject": "拒绝（reject）", "investigate": "深入研究（investigate）",
    "data_insufficient": "数据不足（data_insufficient）",
    " days": " 天",
}


def _normalize_report_locale(locale: object) -> str:
    if not isinstance(locale, str):
        raise TypeError("locale must be a string")
    normalized = locale.strip()
    if normalized not in REPORT_TEXT:
        raise ValueError("locale is not supported")
    return normalized


def _append_overview(lines: list, candidate: CandidateResearchRecord, locale: str) -> None:
    text = REPORT_TEXT[locale]
    labels = text["labels"]
    sections = text["sections"]
    strikes = ", ".join(_format_money(value) for value in dict.fromkeys(leg.strike for leg in candidate.structure.legs))
    lines.extend((text["overview"], "", sections[0], "", text["structure_explanations"][candidate.structure.structure_type], "",
                  f"- **{labels['underlying']}:** {candidate.structure.underlying}",
                  f"- **{labels['structure']}:** {text['structure_labels'][candidate.structure.structure_type]}",
                  f"- **{labels['strikes']}:** {strikes}", f"- **{labels['expiration']}:** {candidate.expiration.isoformat()}",
                  f"- **{labels['holding']}:** {candidate.structure.expected_holding_days}", "", sections[1], "",
                  f"- **{labels['state']}:** {text['state_labels'][candidate.state.value]}", f"- **{labels['rationale']}:** {candidate.state_rationale}", "", text["status_note"], "", sections[2], ""))
    lines.extend((f"- {item.statement}" for item in candidate.supporting_evidence) if candidate.supporting_evidence else (text["no_support"],))
    lines.extend(("", sections[3], "", f"**{labels['weakening']}**", ""))
    lines.extend((f"- {item.statement}" for item in candidate.weakening_evidence) if candidate.weakening_evidence else (text["no_weakening"],))
    lines.extend(("", f"**{labels['missing']}**", ""))
    lines.extend((f"- {item}" for item in candidate.missing_data) if candidate.missing_data else (text["no_missing"],))
    lines.extend(("", sections[4], ""))
    if candidate.costs is None:
        lines.append(text["loss_missing"])
    else:
        costs = candidate.costs
        lines.extend((text["loss_note"], "", f"- **{labels['entry']}:** {_format_money(costs.total_entry_cost)}",
                      f"- **{labels['loss']}:** {_format_money(costs.maximum_loss)}", f"- **{labels['loss_pct']}:** {_format_percentage(costs.maximum_loss_percentage)}",
                      f"- **{labels['repeat_count']}:** {costs.repeated_bet_count}", f"- **{labels['repeat_cost']}:** {_format_money(costs.cumulative_repeated_bet_cost)}",
                      f"- **{labels['repeat_pct']}:** {_format_percentage(costs.cumulative_repeated_bet_percentage)}"))
    lines.extend(("", sections[5], ""))
    if not candidate.scenario_results:
        lines.append(text["no_scenarios"])
    else:
        positive = sum(item.pnl_after_costs > 0 for item in candidate.scenario_results)
        negative = sum(item.pnl_after_costs < 0 for item in candidate.scenario_results)
        zero = len(candidate.scenario_results) - positive - negative
        high = max(candidate.scenario_results, key=lambda item: item.pnl_after_costs)
        low = min(candidate.scenario_results, key=lambda item: item.pnl_after_costs)
        lines.append(text["scenario_counts"].format(positive=positive, negative=negative, zero=zero))
        for label, item in ((text["highest"], high), (text["lowest"], low)):
            lines.extend(("", text["scenario_line"].format(label=label, time=text["valuation_labels"][item.scenario.valuation_time], move=_format_percentage(item.scenario.underlying_move), iv=_format_percentage(item.scenario.iv_change), pnl=_format_money(item.pnl_after_costs))))
        lines.extend(("", text["scenario_note"]))
    lines.extend(("", sections[6], "", f"**{labels['questions']}**", ""))
    for index, question in enumerate(candidate.human_review_questions, start=1):
        lines.append(f"{index}. {question}")
    lines.extend(("", f"**{labels['falsification']}**", ""))
    for index, condition in enumerate(candidate.falsification_conditions, start=1):
        lines.append(f"{index}. {condition}")


def _technical_body(candidate: CandidateResearchRecord, locale: str) -> str:
    lines = _render_technical_english(candidate).rstrip("\n").split("\n")
    lines = lines[2:]
    if candidate.candidate_id.startswith("SYNTHETIC-"):
        lines = lines[2:]
    if lines and lines[-1] == REPORT_TEXT["en"]["footer"]:
        lines = lines[:-1]
    while lines and not lines[-1]:
        lines.pop()
    body = "\n".join(lines)
    if locale == "zh-CN":
        for source, translated in ZH_TECHNICAL_REPLACEMENTS.items():
            body = body.replace(source, translated)
    return body


def render_candidate_markdown(candidate: CandidateResearchRecord, locale: str = "en") -> str:
    """Render one deterministic bilingual candidate research report."""
    if not isinstance(candidate, CandidateResearchRecord):
        raise TypeError("candidate must be a CandidateResearchRecord")
    normalized = _normalize_report_locale(locale)
    text = REPORT_TEXT[normalized]
    lines = [text["title"], ""]
    if candidate.candidate_id.startswith("SYNTHETIC-"):
        lines.extend((text["warning"], ""))
    _append_overview(lines, candidate, normalized)
    lines.extend(("", "---", "", text["technical"], "", _technical_body(candidate, normalized), "", text["footer"]))
    return "\n".join(lines).rstrip("\n") + "\n"
