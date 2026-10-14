"""Host-owned approved Standard Research Profile versions.

Historical v0.1-v0.3 factories remain exact. The v0.4 profile adds only a
conditional, presentation-only entry-fee scenario policy; none provides
provider data, a confirmed account tariff, execution authority, or broker
controls.
"""

from __future__ import annotations

import datetime
import decimal
import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Dict, Tuple

from .core_application import CoreOperationalBounds, CoreResearchPolicy
from .core_research import (
    CorePayoffAuthority,
    CorePayoffModel,
    CoreProvenance,
    CoreReasonCode,
    CoreCostComponent,
    CoreCostComponentStatus,
    CoreCostLedger,
    CoreResearchRequest,
    CoreRiskRepeatPolicy,
    CoreSensitivity,
    CoreSensitivityPoint,
    CoreStructure,
    _decimal_from_fraction,
    _decimal_product,
    _decimal_sum,
    _fraction_from_decimal,
)
from .option_chain_discovery import OptionMaturityAuthority


PROFILE_ID = "standard-research-profile"
_PROFILE_VERSION_V0_1 = "v0.1"
_PROFILE_VERSION_V0_2 = "v0.2"
_PROFILE_VERSION_V0_3 = "v0.3"
_PROFILE_VERSION_V0_4 = "v0.4"
PROFILE_VERSION = _PROFILE_VERSION_V0_4
_REGISTERED_PROFILE_VERSIONS = (
    _PROFILE_VERSION_V0_1,
    _PROFILE_VERSION_V0_2,
    _PROFILE_VERSION_V0_3,
    _PROFILE_VERSION_V0_4,
)
AUTHORIZED_SOURCE_ID = "standalone-mvp-architecture-v0.1"
AUTHORIZED_SOURCE_VERSION = "v0.1"
AUTHORIZED_SOURCE_BASIS = "user-approved-standard-research-profile"
AUTHORIZED_SOURCE_COMMIT = "1adc636"

CONDITIONAL_STANDARD_PAYOFF_APPROVAL_ID = "conditional-standard-payoff"
CONDITIONAL_STANDARD_PAYOFF_APPROVAL_VERSION = "0.1"
CONDITIONAL_STANDARD_PAYOFF_LIMITATIONS = (
    "conditional standard-payoff geometry only",
    "exact deliverable verification remains unestablished",
    "indicative asks are non-executable and do not establish underpricing",
)

COST_LEDGER_GAP = CoreReasonCode.COST_LEDGER_MISSING
SENSITIVITY_GAP = CoreReasonCode.SENSITIVITY_MISSING
HOST_PROFILE_GAP_REASONS = (COST_LEDGER_GAP, SENSITIVITY_GAP)

_PORTFOLIO_VALUE = decimal.Decimal("100000")
_SINGLE_LOSS_FRACTION = decimal.Decimal("0.005")
_REPEATED_LOSS_FRACTION = decimal.Decimal("0.015")
_CONDITIONAL_PREMIUM_FACTOR = decimal.Decimal("1.10")
_SENSITIVITY_X = (-2, -1, 0, 1, 2)
_SENSITIVITY_ASK_FACTORS = (
    decimal.Decimal("1"),
    decimal.Decimal("1.10"),
    decimal.Decimal("1.25"),
)
_SENSITIVITY_ASK_FACTOR_TEXT = ("1", "1.10", "1.25")
_UNKNOWN_COSTS = (
    (
        "entry_fees",
        "Applicable entry broker/exchange fees; UNKNOWN pending an authoritative account tariff or evidenced bound.",
    ),
    (
        "strategy_dependent_funding",
        "Funding cost is UNKNOWN until strategy and an authoritative bound are declared; no cash-only assumption.",
    ),
    (
        "strategy_dependent_exit",
        "Exit cost is UNKNOWN until strategy and an authoritative bound are declared; no early-exit assumption.",
    ),
    (
        "strategy_dependent_settlement",
        "Exercise/settlement cost is UNKNOWN until strategy and an authoritative bound are declared; no zero-cost assumption.",
    ),
)


def _cash_sensitivity_policy_snapshot() -> Dict[str, Any]:
    return {
        "policy_id": "core-cash-sensitivity-policy",
        "version": "v0.1",
        "observed_position_ask_basis": "sum(ask_per_underlying_unit*quantity*contract_multiplier)",
        "conditional_premium_factor": "1.10",
        "required_unknown_component_ids": [item[0] for item in _UNKNOWN_COSTS],
        "sensitivity": {
            "grammar": "long_straddle_equal_quantity_multiplier_same_underlying_strike_expiration",
            "terminal_formula": "strike+x*baseline_sum_per_underlying_unit_asks",
            "x_offsets": list(_SENSITIVITY_X),
            "per_leg_ask_factors": list(_SENSITIVITY_ASK_FACTOR_TEXT),
            "negative_terminal_price": "NOT_APPLICABLE",
        },
    }


def _strategy_governance_snapshot() -> Dict[str, str]:
    return {
        "version": "v0.1",
        "funding_rule": "OWN_CASH_PREMIUM; MARGIN_FINANCING_PROHIBITED",
        "lifecycle_intent": "CLOSE_OR_ABANDON_BEFORE_EXPIRY",
        "exercise_rule": "EXERCISE_TO_STOCK_PROHIBITED",
        "execution_enforcement": "NOT_ESTABLISHED",
        "automatic_exercise_protection": "NOT_ESTABLISHED",
    }


def _conditional_entry_fee_policy_snapshot() -> Dict[str, Any]:
    """Closed v0.4 presentation assumptions; these are not user parameters."""

    return {
        "policy_id": "conditional-entry-fee-scenarios",
        "version": "v0.1",
        "source_url": "https://www.futuhk.com/hans/support/topic2_283",
        "verified_on": "2026-10-14",
        "currency": "USD",
        "scope": "US_LISTED_EQUITY_OPTIONS_ONLY",
        "applicability": "CONDITIONAL_NOT_VERIFIED",
        "account_tariff": "UNKNOWN",
        "security_type": "NOT_VERIFIED",
        "order_assumption": "one_buy_order_per_leg_wholly_filled_within_one_trading_day",
        "scenarios": [
            {
                "scenario_id": "FIXED",
                "platform_fee_per_contract": "0.30",
            },
            {
                "scenario_id": "TIER_FIRST_50",
                "platform_fee_per_contract": "0.60",
                "prior_monthly_contracts": 0,
                "maximum_total_order_quantity": 50,
            },
        ],
        "commission": {
            "minimum_per_leg": "1.99",
            "ask_threshold": "0.10",
            "rate_above_threshold_per_contract": "0.65",
            "rate_at_or_below_threshold_per_contract": "0.15",
        },
        "other_buy_fees_per_contract": "0.2175",
        "partial_subtotal": "existing_1.10_conditional_premium_budget_plus_scenario_entry_fees",
        "rounding_rule": "NOT_VERIFIED",
        "not_included": [
            "sell_side_charges",
            "promotions",
            "extra_services",
            "index_option_surcharges",
            "currency_conversion",
            "future_tariff_changes",
        ],
    }


def _exact_decimal(name: str, value: object, expected: decimal.Decimal) -> None:
    if type(value) is not decimal.Decimal:
        raise TypeError("{} must be Decimal".format(name))
    if value != expected:
        raise ValueError("{} is not an approved profile value".format(name))


@dataclass(frozen=True)
class StandardResearchProfile:
    """Immutable, user-approved economic profile; not a trading authorization."""

    profile_id: str = PROFILE_ID
    version: str = PROFILE_VERSION
    currency: str = "USD"
    portfolio_value: decimal.Decimal = _PORTFOLIO_VALUE
    maximum_single_loss_fraction: decimal.Decimal = _SINGLE_LOSS_FRACTION
    maximum_repeated_loss_fraction: decimal.Decimal = _REPEATED_LOSS_FRACTION
    repeat_count: int = 3
    quantity: int = 1
    authorized_source_id: str = AUTHORIZED_SOURCE_ID
    authorized_source_version: str = AUTHORIZED_SOURCE_VERSION
    authorized_source_basis: str = AUTHORIZED_SOURCE_BASIS
    authorized_source_commit: str = AUTHORIZED_SOURCE_COMMIT
    payoff_model_id: str = CONDITIONAL_STANDARD_PAYOFF_APPROVAL_ID
    payoff_model_version: str = CONDITIONAL_STANDARD_PAYOFF_APPROVAL_VERSION
    payoff_limitations: Tuple[str, ...] = CONDITIONAL_STANDARD_PAYOFF_LIMITATIONS

    def __post_init__(self) -> None:
        if (
            self.profile_id != PROFILE_ID
            or self.version not in _REGISTERED_PROFILE_VERSIONS
            or self.currency != "USD"
        ):
            raise ValueError("only the approved Standard Research Profile is supported")
        for name, value, expected in (
            ("portfolio_value", self.portfolio_value, _PORTFOLIO_VALUE),
            ("maximum_single_loss_fraction", self.maximum_single_loss_fraction, _SINGLE_LOSS_FRACTION),
            ("maximum_repeated_loss_fraction", self.maximum_repeated_loss_fraction, _REPEATED_LOSS_FRACTION),
        ):
            _exact_decimal(name, value, expected)
        if type(self.repeat_count) is not int or self.repeat_count != 3:
            raise ValueError("repeat_count must be 3")
        if type(self.quantity) is not int or self.quantity != 1:
            raise ValueError("quantity must be 1")
        if (self.authorized_source_id, self.authorized_source_version, self.authorized_source_basis, self.authorized_source_commit) != (
            AUTHORIZED_SOURCE_ID, AUTHORIZED_SOURCE_VERSION, AUTHORIZED_SOURCE_BASIS, AUTHORIZED_SOURCE_COMMIT
        ):
            raise ValueError("authorized source provenance is not approved")
        if (self.payoff_model_id, self.payoff_model_version, self.payoff_limitations) != (
            CONDITIONAL_STANDARD_PAYOFF_APPROVAL_ID,
            CONDITIONAL_STANDARD_PAYOFF_APPROVAL_VERSION,
            CONDITIONAL_STANDARD_PAYOFF_LIMITATIONS,
        ):
            raise ValueError("payoff approval or limitations are not approved")

    def snapshot(self) -> Dict[str, Any]:
        """Return a detached JSON-serializable, sanitized profile snapshot."""

        snapshot = {
            "profile_id": self.profile_id,
            "version": self.version,
            "currency": self.currency,
            "portfolio_value": str(self.portfolio_value),
            "maximum_single_loss_fraction": str(self.maximum_single_loss_fraction),
            "maximum_repeated_loss_fraction": str(self.maximum_repeated_loss_fraction),
            "repeat_count": self.repeat_count,
            "quantity": self.quantity,
            "authorized_source": {
                "source_id": self.authorized_source_id,
                "version": self.authorized_source_version,
                "basis": self.authorized_source_basis,
                "frozen_commit": self.authorized_source_commit,
            },
            "payoff_approval": {
                "model_id": self.payoff_model_id,
                "model_version": self.payoff_model_version,
                "limitations": list(self.payoff_limitations),
            },
        }
        if self.version in (
            _PROFILE_VERSION_V0_2,
            _PROFILE_VERSION_V0_3,
            _PROFILE_VERSION_V0_4,
        ):
            snapshot["cash_sensitivity_policy"] = _cash_sensitivity_policy_snapshot()
        if self.version in (_PROFILE_VERSION_V0_3, _PROFILE_VERSION_V0_4):
            snapshot["strategy_governance"] = _strategy_governance_snapshot()
        if self.version == _PROFILE_VERSION_V0_4:
            snapshot["conditional_entry_fee_policy"] = (
                _conditional_entry_fee_policy_snapshot()
            )
        return snapshot

    def snapshot_json(self) -> str:
        return json.dumps(self.snapshot(), sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def to_core_risk_policy(self, structure: CoreStructure) -> CoreRiskRepeatPolicy:
        """Build the new Core risk record without importing legacy records."""

        provenance = self._provenance(structure, "risk-policy")
        return CoreRiskRepeatPolicy(
            portfolio_value=self.portfolio_value,
            maximum_single_loss_fraction=self.maximum_single_loss_fraction,
            maximum_repeated_loss_fraction=self.maximum_repeated_loss_fraction,
            repeat_count=self.repeat_count,
            methodology="approved-standard-research-profile-{}".format(self.version),
            currency=self.currency,
            description="User-approved loss and repeat policy; not trading authorization.",
            provenance=provenance,
        )

    def request_factory(
        self, *, case_id: str, structure: CoreStructure, context: object
    ) -> CoreResearchRequest:
        """Create a Core request while retaining the exact application structure."""

        if type(structure) is not CoreStructure:
            raise TypeError("structure must have exact type CoreStructure")
        provenance = self._provenance(structure, "core-request")
        payoff = CorePayoffModel(
            authority=CorePayoffAuthority.CONDITIONAL_STANDARD_PAYOFF,
            model_id=self.payoff_model_id,
            model_version=self.payoff_model_version,
            description="; ".join(self.payoff_limitations),
            provenance=provenance,
        )
        cost_ledger = None
        sensitivity = None
        if self.version in (
            _PROFILE_VERSION_V0_2,
            _PROFILE_VERSION_V0_3,
            _PROFILE_VERSION_V0_4,
        ) and _supported_cash_structure(structure):
            asks = tuple(leg.ask_per_underlying_unit for leg in structure.legs)
            if all(ask is not None for ask in asks):
                observed_position_ask = _decimal_sum(
                    _decimal_product(
                        ask,
                        leg.quantity,
                        leg.contract_multiplier,
                    )
                    for leg, ask in zip(structure.legs, asks)
                    if ask is not None
                )
                cost_ledger = _unknown_cost_ledger(
                    structure,
                    provenance,
                    _decimal_product(observed_position_ask, _CONDITIONAL_PREMIUM_FACTOR),
                )
                if _supported_sensitivity_straddle(structure):
                    sensitivity = _straddle_sensitivity(structure, provenance)
        return CoreResearchRequest(
            case_id=case_id,
            structure=structure,
            payoff_model=payoff,
            cost_ledger=cost_ledger,
            risk_policy=self.to_core_risk_policy(structure),
            sensitivity=sensitivity,
            reviewed_enhancements=(),
            description="Core request using Standard Research Profile {}.".format(self.version),
            provenance=provenance,
        )

    def _provenance(self, structure: CoreStructure, purpose: str) -> CoreProvenance:
        return CoreProvenance(
            source_reference=structure.provenance.source_reference,
            description="{}; profile_snapshot={}".format(purpose, self.snapshot_json()),
        )


_STANDARD_RESEARCH_PROFILE_V0_1 = StandardResearchProfile(version=_PROFILE_VERSION_V0_1)
_STANDARD_RESEARCH_PROFILE_V0_2 = StandardResearchProfile(version=_PROFILE_VERSION_V0_2)
_STANDARD_RESEARCH_PROFILE_V0_3 = StandardResearchProfile(version=_PROFILE_VERSION_V0_3)
STANDARD_RESEARCH_PROFILE = StandardResearchProfile()
APPROVED_STANDARD_RESEARCH_PROFILE = STANDARD_RESEARCH_PROFILE


def _profile_for_snapshot(snapshot: object) -> StandardResearchProfile:
    """Resolve only exact, registered profile snapshots."""

    if type(snapshot) is not dict:
        raise TypeError("profile snapshot must be an exact registered mapping")
    for profile in (
        _STANDARD_RESEARCH_PROFILE_V0_1,
        _STANDARD_RESEARCH_PROFILE_V0_2,
        _STANDARD_RESEARCH_PROFILE_V0_3,
        STANDARD_RESEARCH_PROFILE,
    ):
        expected = profile.snapshot()
        try:
            candidate_json = json.dumps(
                snapshot,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            )
        except (TypeError, ValueError):
            continue
        if (
            _exact_snapshot_tree(snapshot, expected)
            and candidate_json == profile.snapshot_json()
        ):
            return profile
    raise ValueError("profile_snapshot is not one of the registered Standard Research Profiles")


def _exact_snapshot_tree(candidate: Any, expected: Any) -> bool:
    """Compare JSON trees without Python's bool/int or int/float equality aliases."""

    if type(candidate) is not type(expected):
        return False
    if type(expected) is dict:
        return (
            candidate.keys() == expected.keys()
            and all(
                type(key) is str
                and _exact_snapshot_tree(candidate[key], expected[key])
                for key in expected
            )
        )
    if type(expected) is list:
        return len(candidate) == len(expected) and all(
            _exact_snapshot_tree(left, right)
            for left, right in zip(candidate, expected)
        )
    return candidate == expected


def _request_has_conflicting_registered_profile(
    request: CoreResearchRequest, expected_version: str
) -> bool:
    """Detect a registered successor profile without constraining legacy custom requests."""

    related = [
        getattr(request, "provenance", None),
        getattr(request, "risk_policy", None),
        getattr(request, "payoff_model", None),
        getattr(request, "cost_ledger", None),
        getattr(request, "sensitivity", None),
    ]
    ledger = getattr(request, "cost_ledger", None)
    related.extend(getattr(ledger, "impact_components", ()) or ())
    sensitivity = getattr(request, "sensitivity", None)
    related.extend(getattr(sensitivity, "points", ()) or ())
    for enhancement in getattr(request, "reviewed_enhancements", ()) or ():
        related.append(enhancement)
        related.append(getattr(enhancement, "reviewed_artifact", None))

    text_values = [getattr(request, "description", None)]
    for item in related:
        if item is not None:
            text_values.extend(
                (getattr(item, "description", None), getattr(item, "methodology", None))
            )
            provenance = getattr(item, "provenance", None)
            if provenance is not None:
                text_values.append(getattr(provenance, "description", None))
    for text in text_values:
        if type(text) is not str:
            continue
        for registered_version in _REGISTERED_PROFILE_VERSIONS:
            if registered_version == expected_version:
                continue
            if (
                "Standard Research Profile {}".format(registered_version) in text
                or "approved-standard-research-profile-{}".format(registered_version) in text
            ):
                return True
        marker = "profile_snapshot="
        if marker in text:
            try:
                marked_snapshot = json.loads(text.split(marker, 1)[1])
                marked_profile = _profile_for_snapshot(marked_snapshot)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if marked_profile.version != expected_version:
                return True
    return False


def _supported_cash_structure(structure: CoreStructure) -> bool:
    legs = structure.legs
    if len(legs) == 1:
        return legs[0].option_type.value in ("CALL", "PUT")
    if len(legs) != 2 or {leg.option_type.value for leg in legs} != {"CALL", "PUT"}:
        return False
    first, second = legs
    return (
        first.underlying == second.underlying
        and first.currency == second.currency
        and first.strike == second.strike
        and first.expiration == second.expiration
    )


def _supported_sensitivity_straddle(structure: CoreStructure) -> bool:
    if not _supported_cash_structure(structure) or len(structure.legs) != 2:
        return False
    first, second = structure.legs
    return (
        first.quantity == second.quantity
        and first.contract_multiplier == second.contract_multiplier
    )


def _unknown_cost_ledger(
    structure: CoreStructure,
    provenance: CoreProvenance,
    premium_bound: decimal.Decimal,
) -> CoreCostLedger:
    currency = structure.legs[0].currency
    components = tuple(
        CoreCostComponent(
            component_id=component_id,
            status=CoreCostComponentStatus.UNKNOWN,
            upper_bound=None,
            currency=currency,
            methodology="approved-standard-research-profile-v0.2; authoritative bound absent",
            description=description,
            provenance=provenance,
        )
        for component_id, description in _UNKNOWN_COSTS
    )
    return CoreCostLedger(
        premium_bound=premium_bound,
        impact_components=components,
        required_component_ids=tuple(component_id for component_id, _ in _UNKNOWN_COSTS),
        currency=currency,
        methodology="observed position ask multiplied by the conditional 1.10 premium factor",
        description=(
            "Conditional premium budget only; not actual transaction cost or a total-cost bound. "
            "All applicable required cost categories remain UNKNOWN."
        ),
        provenance=provenance,
    )


def _straddle_sensitivity(
    structure: CoreStructure, provenance: CoreProvenance
) -> CoreSensitivity:
    legs = structure.legs
    baseline = _decimal_sum(
        leg.ask_per_underlying_unit
        for leg in legs
        if leg.ask_per_underlying_unit is not None
    )
    strike = legs[0].strike
    points = []
    retained_grid = []
    for x in _SENSITIVITY_X:
        terminal = _decimal_from_fraction(
            _fraction_from_decimal(strike) + x * _fraction_from_decimal(baseline)
        )
        for factor, factor_text in zip(
            _SENSITIVITY_ASK_FACTORS, _SENSITIVITY_ASK_FACTOR_TEXT
        ):
            point_id = "x{:+d}-ask-{}".format(x, factor_text)
            retained_grid.append(
                "{}(x={},terminal={},ask_factor={})={}".format(
                    point_id,
                    x,
                    terminal,
                    factor_text,
                    "NOT_APPLICABLE" if terminal < decimal.Decimal("0") else "NUMERIC",
                )
            )
            if terminal < decimal.Decimal("0"):
                continue
            stressed_asks = tuple(
                _decimal_product(leg.ask_per_underlying_unit, factor)
                for leg in legs
                if leg.ask_per_underlying_unit is not None
            )
            points.append(
                CoreSensitivityPoint(
                    point_id=point_id,
                    terminal_underlying_price=terminal,
                    ask_per_leg=stressed_asks,
                    description=(
                        "Fixed-baseline terminal point x={}; per-leg ask factor={}; "
                        "terminal is anchored to baseline asks."
                    ).format(x, factor_text),
                    provenance=provenance,
                )
            )
    return CoreSensitivity(
        points=tuple(points),
        description=(
            "Standard Research Profile v0.2 fixed-baseline Long Straddle grid; "
            "baseline ask sum per underlying unit={}; x order=(-2,-1,0,1,2); "
            "per-leg ask factor order=(1,1.10,1.25); complete point identities and "
            "original terminal values: {}"
        ).format(baseline, "; ".join(retained_grid)),
        provenance=provenance,
    )


def create_core_research_policy(
    profile: StandardResearchProfile = STANDARD_RESEARCH_PROFILE,
    *,
    evaluation_date: datetime.date,
    maturity_authority: OptionMaturityAuthority,
    bounds: CoreOperationalBounds,
) -> CoreResearchPolicy:
    """Create existing application policy with all operational inputs explicit."""

    if type(profile) is not StandardResearchProfile:
        raise TypeError("profile must have exact type StandardResearchProfile")
    return CoreResearchPolicy(
        evaluation_date=evaluation_date,
        maturity_authority=maturity_authority,
        generated_quantity=profile.quantity,
        bounds=bounds,
        request_factory=profile.request_factory,
    )
