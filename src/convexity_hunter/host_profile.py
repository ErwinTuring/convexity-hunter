"""Host-owned approved Standard Research Profile v0.1.

This module supplies the one user-approved economic profile to the existing
application and Core records.  Evaluation, maturity, and operational bounds
remain explicit caller inputs; this module does not provide provider data,
cost estimates, or sensitivity scenarios.
"""

from __future__ import annotations

import datetime
import decimal
import json
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from .core_application import CoreOperationalBounds, CoreResearchPolicy
from .core_research import (
    CorePayoffAuthority,
    CorePayoffModel,
    CoreProvenance,
    CoreReasonCode,
    CoreResearchRequest,
    CoreRiskRepeatPolicy,
    CoreStructure,
)
from .option_chain_discovery import OptionMaturityAuthority


PROFILE_ID = "standard-research-profile"
PROFILE_VERSION = "v0.1"
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
        if (self.profile_id, self.version, self.currency) != (
            PROFILE_ID, PROFILE_VERSION, "USD"
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

        return {
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
            methodology="approved-standard-research-profile-v0.1",
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
        return CoreResearchRequest(
            case_id=case_id,
            structure=structure,
            payoff_model=payoff,
            cost_ledger=None,
            risk_policy=self.to_core_risk_policy(structure),
            sensitivity=None,
            reviewed_enhancements=(),
            description="Core request using Standard Research Profile v0.1.",
            provenance=provenance,
        )

    def _provenance(self, structure: CoreStructure, purpose: str) -> CoreProvenance:
        return CoreProvenance(
            source_reference=structure.provenance.source_reference,
            description="{}; profile_snapshot={}".format(purpose, self.snapshot_json()),
        )


STANDARD_RESEARCH_PROFILE = StandardResearchProfile()
APPROVED_STANDARD_RESEARCH_PROFILE = STANDARD_RESEARCH_PROFILE


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
